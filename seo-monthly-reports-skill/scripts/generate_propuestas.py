#!/usr/bin/env python3
"""
Archivos INTERNOS de propuestas. Se generan junto al informe del cliente y los trabajan dos
agentes de Claude, en este orden:

  1. WEB (agente de Diseño web, Elementor MCP): posts en borrador con la configuración de
     Rank Math en verde, Word por post para el cliente y cambios/revisiones de la web.
     Se activa por cliente con WEB_EN_INFORME_<CLIENTE>=true.
  2. MARKETING (agente de herramientas de Google): análisis con GA4, Search Console y Ads, y
     pedidos a Diseño web. Se activa con ADS_EN_INFORME_<CLIENTE>=true.

  - Señales y tablas: reglas en Python (sin coste de tokens).
  - El brief de los 2 posts del archivo WEB: 1 llamada a Gemini (gratis). Con él, el archivo trae
    un prompt completo por post (datos del informe + criterio de Rank Math en verde) para que el agente
    de Diseño web lo redacte; sin cupo, un prompt para que proponga y redacte los 2 posts.
  - Siempre con datos reales (sin el ajuste +10%…+50% del informe).
"""

import hashlib
import json
import os
import re
import time
import unicodedata

from utils import MESES, get_output_dir, cache_read, cache_write, gemini_usage, GEMINI_DAILY_LIMIT, gemini_bump, gemini_mark_exhausted
from seo_posts import brief_issues, check_url, url_ok, norm

AI_TIMEOUT_MS = 90_000

STOP = set("""de la el en y a los las del para con por un una unos unas que se es al lo mi tu su sus o u
mas muy sin sobre entre hay como cual cuando donde este esta estos estas the of and for to in""".split())
GENERIC = set("""piscinas piscines piscina clinica clnica dental dentista psicologa psiclga psicologo especialista
asesor asesoria grupo procuradores tattoo studio estudio fotografia lotera loteria food fuego tejidos
abogados consultoria arquitectura inmobiliaria santander madrid barcelona""".split())
# Preguntas e intención informativa (castellano y catalán, sin tildes)
INFO_RE = re.compile(r"^(como|que|cual|cuales|cuanto|cuanta|cuantos|cuantas|cada cuanto|cuando|donde|por que|"
                     r"precio|precios|coste|costo|mejor|mejores|diferencia|diferencias|tipos|guia|ideas|ventajas|"
                     r"requisitos|se puede|puedo|necesito|es necesario|es obligatorio|"
                     r"com|quant|quanta|quants|quan|quin|quina|quins|per que|preu|preus|millor|millors|tipus|avantatges)\b"
                     r"|\bcuanto cuesta\b|\bquant costa\b|\bprecio\b|\bpreu\b")
LANG_PREFIX = re.compile(r"^/(es|ca|en|fr|de|it|pt|eu|gl)(/|$)")
CONV_BIDDING = {"MAXIMIZE_CONVERSIONS", "TARGET_CPA", "MAXIMIZE_CONVERSION_VALUE", "TARGET_ROAS"}
STATE_TEXT = {
    "ok": "medidas correctamente",
    "sin_configurar": "sin acciones de conversión configuradas",
    "sin_datos": "acciones configuradas pero sin ninguna conversión en 90 días",
    "sin_conversiones_mes": "0 este mes (sí hubo en los 90 días anteriores)",
}


# ── Texto ──────────────────────────────────────────────────────
def _words(s: str) -> list:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).split()


def _tokens(s: str) -> set:
    return {w[:5] for w in _words(s) if w not in STOP and len(w) > 1}


def _covered(a: str, b: str) -> float:
    """Fracción de los tokens de `a` presentes en `b` (prefijos de 5 letras)."""
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta) if ta else 0.0


def _brand_tokens(client: str) -> set:
    return {w[:5] for w in _words(client.replace("_", " ")) if len(w) >= 3 and w not in GENERIC and w not in STOP}


def _is_brand(term: str, brand: set) -> bool:
    from difflib import SequenceMatcher
    for t in _tokens(term):
        if any(t == b or SequenceMatcher(None, t, b).ratio() >= 0.8 for b in brand):
            return True
    return False


def _money(v: float, cur: str = "€") -> str:
    return f"{v:,.2f} {cur}".replace(",", "X").replace(".", ",").replace("X", ".")


def _n(v) -> str:
    return f"{int(v):,}".replace(",", ".")


def _page_key(url: str) -> str:
    """Misma página aunque cambie la barra final o el prefijo de idioma (/es/, /ca/…)."""
    from urllib.parse import urlparse
    path = LANG_PREFIX.sub("/", urlparse(url).path).rstrip("/")
    return path or "/"


def _cid(c: str) -> str:
    return f"{c[:3]}-{c[3:6]}-{c[6:]}" if len(c) == 10 else c


# ── Señales (reglas) ───────────────────────────────────────────
def _organic_pos(term: str, queries: list):
    w = " ".join(_words(term))
    best = None
    for q in queries:
        if " ".join(_words(q["query"])) == w or (_covered(term, q["query"]) == 1 and _covered(q["query"], term) >= 0.75):
            best = q["position"] if best is None else min(best, q["position"])
    return best


def _existing_post(text: str, posts: list):
    for p in posts:
        if _covered(text, p["title"]) >= 0.75 or _covered(text, p["url"].replace("-", " ")) >= 0.75:
            return p
    return None


def compute_signals(client: str, ads: dict, scq: dict, wp: dict, trends: dict, paid: list) -> dict:
    brand = _brand_tokens(client)
    queries = scq.get("queries", [])
    posts = wp.get("posts", [])
    state = ads.get("conversion_state", "")
    avg_cpc = ads.get("avg_cpc", 0) or 0

    terms = []
    for t in ads.get("search_terms", []):
        t = dict(t, organic=_organic_pos(t["term"], queries), brand=_is_brand(t["term"], brand))
        t["post"] = _existing_post(t["term"], posts)
        terms.append(t)

    demand = [t for t in terms if not t["brand"] and (t["clicks"] > 0 or t["conversions"] > 0)
              and (t["organic"] is None or t["organic"] > 20) and not t["post"]]
    # Con 1-2 clics no se sabe nada de un término; y el gasto no dice si es relevante para el
    # negocio, así que son candidatas a revisar, no negativas automáticas.
    negatives = ([t for t in terms if t["conversions"] == 0 and t["clicks"] >= 3
                  and t["cost"] >= max(10, 3 * avg_cpc)] if state == "ok" else [])
    paid_organic = [t for t in terms if t["organic"] is not None and t["organic"] <= 3 and t["cost"] > 0]

    info = [q for q in queries if INFO_RE.search(" ".join(_words(q["query"])))
            and q["position"] > 10 and not _is_brand(q["query"], brand)]
    info.sort(key=lambda q: -q["impressions"])
    near_top = [q for q in queries if 4 <= q["position"] <= 15 and q["impressions"] >= 5
                and not _is_brand(q["query"], brand) and q not in info]
    near_top.sort(key=lambda q: -q["impressions"])

    by_query, by_bare = {}, {}
    for r in scq.get("query_pages", []):
        by_query.setdefault(r["query"], []).append(r)
        by_bare.setdefault(r["page"].rstrip("/"), set()).add(r["page"])
    # Canibalización real: 2+ páginas distintas (no la misma con otra barra o en otro idioma) en posición ≤ 40
    cannibal = []
    for q, rows in by_query.items():
        best = {}
        for r in rows:
            k = _page_key(r["page"])
            if r["position"] <= 40 and (k not in best or r["impressions"] > best[k]["impressions"]):
                best[k] = r
        if len(best) >= 2 and sum(r["impressions"] for r in best.values()) >= 10 and not _is_brand(q, brand):
            cannibal.append({"query": q, "pages": sorted(best.values(), key=lambda r: -r["impressions"])[:3]})
    cannibal.sort(key=lambda c: -sum(r["impressions"] for r in c["pages"]))
    # La misma URL indexada con y sin barra final: contenido duplicado técnico
    dupes = sorted(bare for bare, variants in by_bare.items() if len(variants) >= 2)

    # Sin eventos clave solo es señal de landing floja si la medición funciona
    weak_landings = [p for p in paid if p["sessions"] >= 10 and
                     (p["bounce_rate"] >= 60 or (p["key_events"] == 0 and state == "ok" and p["sessions"] >= 20))]
    low_qs = [k for k in ads.get("keywords", []) if 0 < k["quality_score"] <= 5]
    conv_bidding = [c for c in ads.get("campaigns", []) if c.get("bidding") in CONV_BIDDING] if state != "ok" else []

    return {
        "terms": terms, "demand": demand[:8], "negatives": negatives[:10], "paid_organic": paid_organic[:6],
        "info": info[:10], "near_top": near_top[:8], "cannibal": cannibal[:5], "slash_dupes": dupes[:5],
        "rising": (trends or {}).get("rising", [])[:8], "peaks": (trends or {}).get("peaks", {}),
        "weak_landings": weak_landings[:5], "low_qs": low_qs[:10], "conv_bidding": conv_bidding,
    }


def keyword_table(sig: dict) -> list:
    rows, seen = [], set()

    def add(kw, fuente, impr, pos, conv, uso):
        k = " ".join(_words(kw))
        if k and k not in seen:
            seen.add(k)
            rows.append({"kw": kw, "fuente": fuente, "impr": impr, "pos": pos, "conv": conv, "uso": uso})

    for t in sig["demand"]:
        add(t["term"], "Ads", f"{t['clicks']} clics", t["organic"], t["conversions"], "post (demanda probada en Ads)")
    for q in sig["info"]:
        add(q["query"], "SC", f"{q['impressions']} impr.", q["position"], None, "post (pregunta informativa)")
    for r in sig["rising"][:5]:
        add(r["query"], "Trends", f"subida {r['value']}", None, None, "post (tendencia, validar)")
    for q in sig["near_top"]:
        add(q["query"], "SC", f"{q['impressions']} impr.", q["position"], None, "optimizar página existente")
    for t in sig["paid_organic"]:
        add(t["term"], "Ads + SC", f"{t['clicks']} clics", t["organic"], t["conversions"],
            "revisar puja (ya top 3 en orgánico)" + (" · marca" if t["brand"] else ""))
    for t in sig["negatives"]:
        add(t["term"], "Ads", f"{_money(t['cost'])}", t["organic"], 0, "posible negativa (revisar)")
    return rows[:20]


# ── IA: 2 posts con el brief completo (solo Gemini) ───────────
def _norm_kw(p: dict) -> str:
    return norm(p.get("keyword_principal", "")) or "\x00"


def web_enabled_for(client: str) -> bool:
    """Archivo de diseño web: se genera si el cliente tiene capturas guardadas o WEB_EN_INFORME_<CLIENTE>=true."""
    if os.getenv(f"WEB_EN_INFORME_{client.upper()}", "").strip().lower() in ("true", "1", "si", "sí"):
        return True
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, "capturas", client.upper().replace(" ", "_"))
    return os.path.isdir(d) and any(f.lower().endswith((".png", ".jpg", ".jpeg")) for f in os.listdir(d))


def _ai_posts(client: str, base: str, month: int, year: int, sig: dict, kw_rows: list, wp: dict) -> list:
    if os.getenv("IA_ENABLED", "true").lower() == "false":
        print("  ℹ️  Propuestas: IA desactivada; los posts quedan como tarea para Claude")
        return []
    links = [p["url"] for p in wp.get("pages", [])[:30]] + [p["url"] for p in wp.get("posts", [])[:30]]
    existing = [p["title"] for p in wp.get("posts", [])[:60]]
    kw_txt = "\n".join(f"- {r['kw']} | {r['fuente']} | {r['impr']} | pos {r['pos'] or '—'} | {r['uso']}" for r in kw_rows) or "- (sin datos)"
    peaks = ", ".join(f"{k}: pico en {v}" for k, v in sig["peaks"].items()) or "sin datos"
    prompt = (
        "Eres consultor SEO de una agencia y conoces Rank Math. Propón EXACTAMENTE 2 posts nuevos para el blog de esta web, "
        "preparados para que el diseñador web los cree con la puntuación de Rank Math en verde. "
        "Responde SOLO con JSON válido con esta estructura:\n"
        '{"posts":[{"titulo":"","variante":"","keyword_principal":"","keywords_secundarias":["",""],"intencion":"",'
        '"slug":"","titulo_seo":"","meta_description":"","categoria":"","etiquetas":["",""],"extracto":"",'
        '"secciones":[{"h2":"","respuesta_directa":"","h3":["",""]}],'
        '"faq":[{"pregunta":"","respuesta":""}],"schema":["Article","FAQPage"],'
        '"enlaces_internos":[{"url":"","anchor":""}],"paginas_que_enlazan":[{"url":"","anchor":""}],'
        '"enlaces_externos":[{"url":"","anchor":"","fuente":""}],"fuentes_externas":[""],'
        '"cta":"","palabras":900,"imagenes":[{"idea":"","alt":""}],"por_que":""}]}\n'
        "Reglas:\n"
        "- Idioma: el de los posts ya publicados.\n"
        "- titulo ≤ 60 caracteres; variante = otro TÍTULO alternativo ≤ 60 (no una frase promocional).\n"
        "- keyword_principal: una expresión de búsqueda real de las candidatas que no coincida con un post existente; "
        "keywords_secundarias: 2-4.\n"
        "- titulo_seo ≤ 60 caracteres con la keyword_principal al principio y, si encaja, un número. "
        "meta_description de 120 a 155 caracteres con la keyword_principal y una llamada a la acción. "
        "slug en minúsculas, sin tildes, con guiones, con la keyword_principal y menos de 75 caracteres.\n"
        "- secciones: 5-7 H2; al menos uno contiene la keyword_principal; los 2-3 primeros formulados como pregunta y con "
        "respuesta_directa de 40 a 60 palabras; h3: 0-3 por sección.\n"
        "- faq: 3-4 preguntas reales con respuesta de 1-2 frases. schema: siempre \"Article\"; añade \"FAQPage\" si hay faq "
        "y \"HowTo\" solo si es una guía paso a paso.\n"
        "- enlaces_internos: 3-5 usando SOLO URLs de la lista; paginas_que_enlazan: 2 URLs de la lista que deberían enlazar al post nuevo.\n"
        "- enlaces_externos: SOLO si conoces una URL oficial que existe con seguridad (instituciones, normativa, organismos); "
        "si no, déjalo vacío y describe el tipo de fuente en fuentes_externas. No cites competidores.\n"
        "- imagenes: 2-3 con idea y alt; el alt de una contiene la keyword_principal.\n"
        "- por_que = 1-2 frases con al menos una cifra copiada de las keywords candidatas (clics, impresiones o posición; "
        "no inventes ninguna).\n"
        "- No repitas temas de los posts existentes; prioriza keywords con uso 'post'.\n\n"
        f"Cliente: {client} · Web: {base} · Mes analizado: {MESES.get(month)} {year}\n"
        f"Estacionalidad (Google Trends): {peaks}\n"
        f"Keywords candidatas (keyword | fuente | volumen | posición orgánica | uso):\n{kw_txt}\n"
        f"Posts ya publicados: {json.dumps(existing, ensure_ascii=False)}\n"
        f"URLs disponibles para enlazar: {json.dumps(links, ensure_ascii=False)}"
    )
    # Mismos datos → mismos posts guardados, sin gastar otra llamada (IA_NUEVA=true los pide de nuevo)
    cache_key = "ai_posts_v2_" + hashlib.md5(prompt.encode()).hexdigest()
    cached = None if os.getenv("IA_NUEVA", "false").lower() == "true" else cache_read(cache_key, 24 * 60)
    key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
    if cached:
        print("  ♻️  Propuestas: se reutilizan los posts guardados para estos datos (0 llamadas)")
        posts = cached.get("posts", [])
    elif (not key or gemini_usage() >= GEMINI_DAILY_LIMIT
          or os.getenv("IA_SIN_LLAMADAS", "false").lower() == "true"):
        print("  ℹ️  Propuestas: sin cupo de Gemini; los posts quedan como tarea para Claude")
        return []
    else:
        posts = _ai_posts_call(key, prompt)
        if posts is None:
            return []
        cache_write(cache_key, {"posts": posts})
    return _valid_posts(posts, links, wp, base)


def _ai_posts_call(key: str, prompt: str):
    try:
        from google import genai
    except ImportError:
        return None
    try:
        # El cliente debe vivir en una variable: si se encadena, se cierra antes de la petición
        client_ai = genai.Client(api_key=key, http_options={"timeout": AI_TIMEOUT_MS})
        try:
            from google.genai import types
            cfg = types.GenerateContentConfig(response_mime_type="application/json", max_output_tokens=8192)
        except Exception:
            cfg = None
        resp = None
        for attempt in (1, 2):  # un reintento si el servidor de Google falla (500/503)
            try:
                resp = client_ai.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt, config=cfg)
                break
            except Exception as e:
                if attempt == 2 or not any(c in str(e) for c in ("500", "503", "UNAVAILABLE", "INTERNAL", "overloaded")):
                    raise
                print(f"  ⚠️  Propuestas: Gemini no responde ({str(e)[:90]}); reintentando…")
                time.sleep(5)
        gemini_bump()
        txt = (resp.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        posts = json.loads(txt).get("posts", [])
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            gemini_mark_exhausted()
        print(f"  ⚠️  Propuestas: IA sin respuesta válida ({type(e).__name__}: {str(e)[:160]}); los posts quedan como tarea")
        return None
    return posts if isinstance(posts, list) else None


def _valid_posts(posts: list, links: list, wp: dict, base: str = "") -> list:
    """Se queda con enlaces internos reales y enlaces externos que responden; añade avisos del brief."""
    from urllib.parse import urlparse
    valid = set(links)
    host = urlparse(base).netloc.lower().removeprefix("www.") if base else ""
    out = []
    for p in posts[:2]:
        if not isinstance(p, dict) or not p.get("titulo"):
            continue
        for k in ("enlaces_internos", "paginas_que_enlazan"):
            p[k] = [l for l in p.get(k, []) if isinstance(l, dict) and l.get("url") in valid]
        ext = []
        for l in p.get("enlaces_externos", []):
            u = str(l.get("url", "")) if isinstance(l, dict) else ""
            if not u.startswith("http") or (host and host in urlparse(u).netloc.lower()):
                continue
            if url_ok(check_url(u)[0]) == "ok":
                ext.append(l)
            else:
                print(f"  ℹ️  Propuestas: enlace externo descartado (no responde): {u}")
        p["enlaces_externos"] = ext
        p["avisos_brief"] = brief_issues(p)
        imgs = [i for i in p.get("imagenes", []) if isinstance(i, dict)]
        if any(not i.get("alt") for i in imgs):
            p["avisos_brief"].append("hay imágenes sin texto alternativo")
        if imgs and not any(_norm_kw(p) in _norm_kw({"keyword_principal": i.get("alt", "")}) for i in imgs):
            p["avisos_brief"].append("ningún texto alternativo lleva la palabra clave principal")
        p["existente"] = _existing_post(p.get("keyword_principal") or p["titulo"], wp.get("posts", []))
        out.append(p)
    print(f"  ✅ Propuestas: {len(out)} posts propuestos con IA")
    return out


# ── Markdown ───────────────────────────────────────────────────
def _table(head: list, rows: list) -> str:
    if not rows:
        return "_Sin datos._\n"
    esc = lambda v: str(v if v is not None else "—").replace("|", "/")
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
                     + ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]) + "\n"


def _conversion_section(ads: dict, tracking: dict, paid: list, sig: dict) -> str:
    state = ads.get("conversion_state")
    acts = ads.get("conversion_actions", [])
    t = tracking or {}
    ga4 = sorted(set(t.get("ga4", [])) | set(t.get("gtm_contains", {}).get("ga4", [])))
    aw = sorted(set(t.get("ads", [])) | set(t.get("gtm_contains", {}).get("ads", [])))
    lines = ["## 5. Seguimiento de conversiones", "",
             f"**Estado:** {STATE_TEXT.get(state, state)}."]
    if acts:
        lines.append("**Acciones activas en Ads:** " + "; ".join(
            f"{a['name']} ({a['category'].lower()}{', principal' if a['primary'] else ''})" for a in acts[:8]) + ".")
    lines += ["", "**Instalado en la web** (lectura del HTML y del contenedor GTM):",
              f"- GA4: {', '.join(ga4) or ('no visible en el HTML; Site Kit activo, probablemente lo carga él' if t.get('site_kit') else 'no detectado')}",
              f"- Etiqueta de Google Ads: {', '.join(aw) or 'no detectada'}",
              f"- Google Tag Manager: {', '.join(t.get('gtm', [])) or 'no'}",
              f"- Cookies / Consent Mode: {', '.join(t.get('consent_tool', [])) or 'sin gestor detectado'} · "
              f"Consent Mode {'detectado' if t.get('consent_mode') else 'no detectado'}",
              f"- Formularios: {', '.join(t.get('forms', [])) or 'no detectados en la home ni en la landing'} · "
              f"enlaces de teléfono: {t.get('phone_links', 0)}"]
    if paid:
        ke = sum(p["key_events"] for p in paid)
        lines.append(f"- GA4, tráfico de Paid Search: {sum(p['sessions'] for p in paid)} sesiones y {ke:g} eventos clave")

    steps = []
    if not aw:
        steps.append("Instalar la etiqueta de Google Ads " + ("en GTM (ya existe contenedor)." if t.get("gtm") else "(Site Kit o GTM)."))
    if state == "sin_configurar":
        steps.append("Crear la acción de conversión principal en Ads (Objetivos → Conversiones): «Envío de formulario de contacto» "
                     "como principal; el resto, secundarias.")
    if "Elementor Forms" in t.get("forms", []):
        steps.append("Elementor Forms: disparar la conversión al enviar con éxito (activador de GTM sobre el evento de envío, "
                     "o redirigir a una página de «gracias» y medir su visita).")
    elif "Contact Form 7" in t.get("forms", []):
        steps.append("Contact Form 7: disparar la conversión con el evento `wpcf7mailsent` (activador de evento personalizado en GTM).")
    elif t.get("forms"):
        steps.append(f"Formulario {t['forms'][0]}: disparar la conversión en el envío correcto, no en el clic del botón.")
    else:
        steps.append("Localizar el formulario de contacto/presupuesto (no está en la home ni en la landing de Ads) y medir su envío.")
    if t.get("phone_links"):
        steps.append("Medir los clics en el teléfono (activador de clic en enlaces `tel:`) como conversión secundaria y revisar la extensión de llamada.")
    if paid and sum(p["key_events"] for p in paid) == 0:
        steps.append("En GA4, marcar `generate_lead` (o el evento del formulario) como evento clave, vincular GA4 con Ads e importarlo.")
    if not t.get("consent_mode"):
        steps.append("Activar Consent Mode v2 (en la UE, sin él Ads deja de medir y de usar remarketing).")
    if sig["conv_bidding"]:
        names = ", ".join(c["name"] for c in sig["conv_bidding"][:3])
        steps.append(f"Ojo: {names} puja por conversiones sin conversiones medidas. Pasar temporalmente a Maximizar clics "
                     "(con CPC máximo) hasta tener ~15-30 conversiones al mes.")
    steps.append("Comprobar con Tag Assistant y, a las 24-48 h, que la acción aparece como «Registrando conversiones» en Ads.")
    lines += ["", "**Pasos recomendados:**"] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    return "\n".join(lines) + "\n"


def _insight_blocks(ins: dict, parts: tuple) -> list:
    """Contenido que pierde clics, cruce Search Console × GA4 por URL y visitas desde asistentes de IA."""
    dec, land, ai = ins.get("decay") or {}, ins.get("landings") or {}, ins.get("ai") or {}
    out = []
    if "decay" in parts and dec.get("pages"):
        out.append(f"**Páginas que pierden clics** ({dec['window']}). Candidatas a actualizar antes de crear contenido nuevo:")
        out.append(_table(["Página", "Clics antes", "Clics ahora", "Cambio", "Posición antes → ahora"],
                          [[p["page"], _n(p["clicks_before"]), _n(p["clicks_now"]), f"{p['pct']}%",
                            f"{p['pos_before']} → {p['pos_now'] or 'ya no aparece'}"] for p in dec["pages"]]))
    if "landings" in parts:
        if land.get("visible_no_conv"):
            out.append("**Llegan desde Google pero no convierten** (revisar CTA, formulario y contenido):")
            out.append(_table(["Página", "Clics SC", "Sesiones orgánicas", "Eventos clave"],
                              [[r["page"], _n(r["clicks"]), _n(r["sessions"]), "0"] for r in land["visible_no_conv"]]))
        if land.get("conv_low_vis"):
            out.append("**Convierten pero apenas se ven en Google** (posición > 10: reforzar SEO y enlazado interno):")
            out.append(_table(["Página", "Eventos clave", "Posición", "Impresiones"],
                              [[r["page"], f"{r['key_events']:g}", r["position"], _n(r["impressions"])] for r in land["conv_low_vis"]]))
        if "measured" in land and not land["measured"]:
            out += ["*GA4 no registra eventos clave en el tráfico orgánico: no se puede saber qué páginas convierten. "
                    "Configurar eventos clave (formulario, llamada, WhatsApp) en GA4.*", ""]
    if "ai" in parts and ai.get("sessions"):
        prev = ai.get("prev_sessions")
        out.append(f"**Visitas desde asistentes de IA:** {_n(ai['sessions'])} sesiones"
                   + (f" (mes anterior: {_n(prev)})" if prev is not None else "") + ". "
                   + ", ".join(f"{a['assistant']} {_n(a['sessions'])}" for a in ai["sources"]) + ".")
        out.append("")
    return out


def _title(d: dict, kind: str, role: str) -> list:
    mes = f"{MESES.get(d['month'], d['month']).capitalize()} {d['year']}"
    return [f"# Archivo {kind} — {d['client'].replace('_', ' ').title()} — {mes}  (INTERNO · {role})", ""]


def _summary_lines(d: dict, ads: bool, web: bool) -> list:
    cur = d["ads"].get("currency", "€")
    state = d["ads"].get("conversion_state", "")
    m, s = d["ga4"].get("metrics", {}), d["sc"].get("summary", {})
    paid_sessions = next((c["sessions"] for c in d["ga4"].get("traffic_channels", []) if c["channel"] == "Paid Search"), 0)
    out = ["## 1. Resumen de datos"]
    if ads:
        a = d["ads"]
        if a and a.get("impressions"):
            conv_txt = (f"{a['conversions']:g} {'conversión' if a['conversions'] == 1 else 'conversiones'}, CPA {_money(a['cpa'], cur)}"
                        if state == "ok" else f"conversiones: {STATE_TEXT.get(state, state)}")
            out.append(f"- **Google Ads:** {_money(a['cost'], cur)} invertidos · {_n(a['impressions'])} impresiones · "
                       f"{_n(a['clicks'])} clics · CTR {a['ctr']}% · CPC {_money(a['avg_cpc'], cur)} · {conv_txt}")
        else:
            out.append(f"- **Google Ads:** {d['ads_error'] or 'sin actividad este mes'}")
    out.append(f"- **Search Console:** {_n(s.get('impressions', 0))} impresiones · {_n(s.get('clicks', 0))} clics · "
               f"CTR {s.get('ctr', 0)}% · posición media {s.get('position', 0)} · {len(d['scq'].get('queries', []))} consultas")
    out.append(f"- **GA4:** {_n(m.get('total_users', 0))} usuarios · {_n(m.get('sessions', 0))} sesiones"
               + (f" ({_n(paid_sessions)} de Paid Search)" if ads else "") + f" · rebote {m.get('bounce_rate', 0):.1f}%")
    if web:
        wp = d["wp"]
        out.append(f"- **Web:** {len(wp.get('posts', []))} posts y {len(wp.get('pages', []))} páginas publicadas"
                   + (f" · último post {wp['posts'][0]['date']}" if wp.get("posts") and wp["posts"][0].get("date") else "")
                   + (f" · {wp['error']}" if wp.get("error") else ""))
    t = d["trends"]
    if t and not t.get("error"):
        out.append("- **Google Trends (ES, 12 meses):** " + (", ".join(f"«{k}» pico en {v}" for k, v in d["sig"]["peaks"].items()) or "sin picos")
                   + f" · {len(d['sig']['rising'])} consultas en subida")
    else:
        out.append(f"- **Google Trends:** no disponible{' (' + t['error'] + ')' if t and t.get('error') else ''}")
    return out + [""]


def _post_md(i: int, p: dict) -> list:
    """Resumen del post para Javi; el detalle completo va en su prompt."""
    tl = len(p.get("titulo", ""))
    out = ["", f"### Post {i}: {p['titulo']}" + (f"  ⚠️ {tl} caracteres" if tl > 60 else ""),
           f"- **Palabra clave:** {p.get('keyword_principal', '—')} · **Intención:** {p.get('intencion', '—')} · "
           f"**URL:** `/{p.get('slug', '').strip('/')}/` · **Schema:** {', '.join(p.get('schema', [])) or 'Article'}",
           f"- **Por qué ahora:** {p.get('por_que', '—')}"]
    if p.get("avisos_brief"):
        out.append("- ⚠️ **Avisos del brief:** " + "; ".join(p["avisos_brief"]))
    if p.get("existente"):
        out.append(f"- ⚠️ **Actualizar en vez de crear:** ya existe [{p['existente']['title']}]({p['existente']['url']})")
    return out


# Criterio de Rank Math en verde (el mismo que comprueba seo_posts.validate_post)
RANK_MATH_VERDE = [
    "Título SEO de 60 caracteres o menos, con la palabra clave al principio y, si encaja, un número.",
    "Meta descripción de 120 a 155 caracteres con la palabra clave y una llamada a la acción.",
    "Slug en minúsculas, sin tildes, con guiones, con la palabra clave entera y menos de 75 caracteres.",
    "Palabra clave en el H1, en el primer 10 % del texto, en al menos un H2 y en el texto alternativo de una imagen.",
    "Densidad de la palabra clave entre 0,5 % y 2,5 % (sin forzarla); usa también las secundarias.",
    "Un solo H1 (el título). H2 → H3 sin saltar niveles.",
    "Mínimo 600 palabras; párrafos de 120 palabras o menos.",
    "Tabla de contenidos si hay 4 H2 o más.",
    "3-5 enlaces internos a páginas que EXISTEN (usa solo las URLs indicadas) y 1-3 externos a fuentes fiables que respondan; nunca a competidores.",
    "Schema Article; añade FAQPage con 3 o más preguntas visibles en el texto, o HowTo solo si es una guía paso a paso.",
    "Los primeros H2 en forma de pregunta, con una respuesta directa de 40-60 palabras justo debajo (fragmento destacado).",
    "Todas las imágenes con texto alternativo. Categoría, 1-5 etiquetas y extracto rellenos.",
    "La palabra clave no debe estar ya usada como principal en otro post de la web.",
]

_PROMPT_DELIVERY = [
    "ENTREGA (en este orden)",
    "1. El texto del post en Markdown SIN el H1: `## ` H2, `### ` H3, `> ` llamada a la acción, imágenes como",
    "   `![texto alternativo](idea de la imagen)` y enlaces como `[ancla](URL)`.",
    "2. La ficha SEO final: título del post, título SEO, meta descripción, slug, palabra clave principal y",
    "   secundarias, categoría, etiquetas, extracto, schema, alt de la imagen destacada.",
    "3. El repaso del criterio de verde: punto por punto, cumplido o no y por qué.",
    "4. Crea el post como BORRADOR en Elementor (entrada, sin publicar) con esa ficha. Lo que el conector no",
    "   pueda escribir (slug, campos de Rank Math, categoría, etiquetas, imagen destacada…) no lo des por hecho:",
    "   anótalo como «Falta a mano» con el valor exacto a pegar. Nunca digas que algo está aplicado sin leerlo de vuelta.",
]


_NO_LINK = re.compile(r"gracias|thank|cookies|privacidad|privacitat|aviso-legal|avis-legal|legal|condiciones|carrito|cart|checkout|mi-cuenta")


def _site_links(d: dict, limit: int = 40) -> list:
    """Páginas y posts que existen y sirven para enlazar (sin legales ni de agradecimiento)."""
    wp = d["wp"]
    return [x for x in wp.get("pages", [])[:limit // 2] + wp.get("posts", [])[:limit // 2]
            if x.get("url") and not _NO_LINK.search(x["url"].lower())]


def _kw_data(d: dict, kw: str) -> str:
    """Cifras del informe para una palabra clave (si está en la tabla de keywords)."""
    k = norm(kw)
    r = next((r for r in d["kw_rows"] if norm(r["kw"]) == k), None)
    if not r:
        return ""
    return f"{r['fuente']}: {r['impr']}" + (f", posición orgánica actual {r['pos']}" if r["pos"] else ", aún sin posición orgánica")


def _prompt_header(d: dict, what: str = "el post completo") -> list:
    wp = d["wp"]
    mes = f"{MESES.get(d['month'], d['month'])} {d['year']}"
    existing = " · ".join(p["title"] for p in wp.get("posts", [])[:20]) or "ninguno detectado"
    return [f"Eres redactor SEO de Inpulsia. Escribe {what} para el blog de {d['client'].replace('_', ' ').title()} "
            f"({d['base'] or 'web del cliente'}) y déjalo listo para que Rank Math lo puntúe en VERDE.",
            "Usa solo los datos de este prompt; si falta alguno, dilo en vez de inventarlo. No inventes cifras, precios ni normativa.",
            "Idioma: el de los posts ya publicados. Tono profesional y cercano, frases claras, sin relleno.",
            "",
            f"DATOS DEL INFORME ({mes})",
            f"- Posts ya publicados (no repitas su tema; puedes enlazarlos): {existing}"]


def _post_prompt(i: int, p: dict, d: dict) -> list:
    """Prompt autosuficiente para que el agente de Diseño web redacte el post (sin herramientas del conector)."""
    L = _prompt_header(d)
    kw = p.get("keyword_principal", "")
    kd = _kw_data(d, kw)
    L += [f"- Por qué este post ahora: {p.get('por_que', '—')}",
          f"- Palabra clave principal: «{kw}»" + (f" ({kd})" if kd else ""),
          f"- Palabras clave secundarias: {', '.join(p.get('keywords_secundarias', [])) or '—'}",
          f"- Intención de búsqueda: {p.get('intencion', '—')}"]
    if p.get("existente"):
        L.append(f"- OJO: ya existe un post parecido ({p['existente']['title']}, {p['existente']['url']}): "
                 "valora actualizarlo en vez de crear uno nuevo y dímelo antes de empezar.")
    tseo, meta = p.get("titulo_seo", ""), p.get("meta_description", "")
    imgs = [im for im in p.get("imagenes", []) if isinstance(im, dict)]
    L += ["", "FICHA SEO (úsala tal cual; corrige solo lo que incumpla el criterio de verde y dime qué cambiaste)",
          f"- Título del post (H1): {p.get('h1') or p.get('titulo', '')}",
          f"- Título alternativo: {p.get('variante', '—')}",
          f"- Título SEO ({len(tseo)} caracteres): {tseo or '—'}",
          f"- Meta descripción ({len(meta)} caracteres): {meta or '—'}",
          f"- Slug: {(p.get('slug') or '').strip('/') or '—'}",
          f"- Categoría: {p.get('categoria', '—')} · Etiquetas: {', '.join(p.get('etiquetas', [])) or '—'}",
          f"- Extracto: {p.get('extracto', '—')}",
          f"- Schema: {', '.join(p.get('schema', [])) or 'Article'}",
          f"- Imagen destacada: {imgs[0].get('idea', '') + ' · alt: «' + imgs[0].get('alt', '') + '»' if imgs else 'propón una (alt con la palabra clave)'}",
          "", "ESTRUCTURA (respeta el orden de los H2)"]
    for j, sec in enumerate(p.get("secciones") or [{"h2": h} for h in p.get("h2", [])], 1):
        if not isinstance(sec, dict):
            continue
        L.append(f"{j}. H2: {sec.get('h2', '')}")
        if sec.get("respuesta_directa"):
            L.append(f"   Respuesta directa justo debajo (40-60 palabras), punto de partida: {sec['respuesta_directa']}")
        L += [f"   H3: {h}" for h in sec.get("h3", []) if h]
    if p.get("faq"):
        L.append("Preguntas frecuentes (H2 «Preguntas frecuentes», cada pregunta como H3 con su respuesta; alimentan el schema FAQPage):")
        L += [f"- {f.get('pregunta', '')} → {f.get('respuesta', '')}" for f in p["faq"] if isinstance(f, dict)]
    L += ["", "ENLACES"]
    if p.get("enlaces_internos"):
        L.append("- Internos (URLs exactas, todas existen): " + " · ".join(
            f"[{l.get('anchor') or l['url']}]({l['url']})" for l in p["enlaces_internos"]))
    else:
        L.append("- Internos: elige 3-5 de estas URLs, que existen: " + " · ".join(x["url"] for x in _site_links(d)))
    if p.get("enlaces_externos"):
        L.append("- Externos (comprobados, responden): " + " · ".join(
            f"[{l.get('anchor') or l['url']}]({l['url']})" + (f" ({l['fuente']})" if l.get("fuente") else "")
            for l in p["enlaces_externos"]))
    else:
        L.append("- Externos: 1-3 fuentes fiables" + (f" ({'; '.join(p['fuentes_externas'])})" if p.get("fuentes_externas") else "")
                 + ". Comprueba que la URL existe; si no puedes comprobarla, no la pongas y dímelo.")
    if p.get("paginas_que_enlazan"):
        L.append("- Después, enlaza al post nuevo desde: " + " · ".join(
            f"{l['url']} (ancla «{l.get('anchor', '')}»)" for l in p["paginas_que_enlazan"]) + " (edita una copia en borrador).")
    if imgs:
        L += ["", "IMÁGENES"] + [f"- {im.get('idea', '')} · alt: «{im.get('alt', '')}»" for im in imgs]
    L += ["", f"LLAMADA A LA ACCIÓN: {p.get('cta', '—')}",
          f"LONGITUD: unas {p.get('palabras') or 900} palabras (mínimo 600)."]
    if p.get("avisos_brief"):
        L.append("AVISOS (corrígelos al escribir): " + "; ".join(p["avisos_brief"]))
    L += ["", "CRITERIO DE VERDE EN RANK MATH (repásalo punto por punto antes de entregar)"]
    L += [f"- {c}" for c in RANK_MATH_VERDE]
    return ["", f"#### Prompt para redactar el post {i}", "", "````text", *L, "", *_PROMPT_DELIVERY, "````"]


def _fallback_prompts(d: dict) -> list:
    """Sin brief de IA: prompt para que el agente proponga y redacte 2 posts con los datos del informe."""
    kws = [r for r in d["kw_rows"] if r["uso"].startswith("post")][:6]
    L = _prompt_header(d, "2 posts completos")
    L += ["- Palabras clave candidatas para posts (elige 2 distintas que no repitan un post publicado):"]
    L += [f"  - «{r['kw']}» — {r['fuente']}: {r['impr']}" + (f", posición orgánica {r['pos']}" if r["pos"] else "")
          + f" · {r['uso']}" for r in kws] or ["  - (el informe no trae candidatas claras)"]
    top = [k for k in d["sc"].get("top_keywords", []) if k.get("impressions", 0) >= 10][:8]
    if top:
        L.append("- Consultas con más impresiones en Google este mes (contexto; no repitas lo que ya posiciona bien): " + " · ".join(
            f"«{k['query']}» ({k['impressions']} impr., pos. {k.get('position', '—')})" for k in top))
    L += ["- URLs que existen para los enlaces internos: " + (" · ".join(x["url"] for x in _site_links(d)) or "—"),
          "", "QUÉ HACER",
          "Propón primero los 2 posts (palabra clave, título, intención y por qué, con una cifra de las candidatas) y espera mi OK.",
          "Después, para cada uno: ficha SEO, estructura de 5-7 H2 (los primeros como pregunta con respuesta directa de",
          "40-60 palabras), 3-4 preguntas frecuentes, 2-3 imágenes con alt, enlaces y llamada a la acción, y redacta el post.",
          "", "CRITERIO DE VERDE EN RANK MATH (repásalo punto por punto antes de entregar)"]
    L += [f"- {c}" for c in RANK_MATH_VERDE]
    return ["", "#### Prompt para proponer y redactar los 2 posts", "", "````text", *L, "", *_PROMPT_DELIVERY, "````"]


def _tracking_lines(t: dict, paid: list) -> list:
    t = t or {}
    ga4 = sorted(set(t.get("ga4", [])) | set(t.get("gtm_contains", {}).get("ga4", [])))
    aw = sorted(set(t.get("ads", [])) | set(t.get("gtm_contains", {}).get("ads", [])))
    out = [f"- GA4: {', '.join(ga4) or ('no visible en el HTML; Site Kit activo' if t.get('site_kit') else 'no detectado')}",
           f"- Etiqueta de Google Ads: {', '.join(aw) or 'no detectada'}",
           f"- Google Tag Manager: {', '.join(t.get('gtm', [])) or 'no'}",
           f"- Cookies / Consent Mode: {', '.join(t.get('consent_tool', [])) or 'sin gestor detectado'} · "
           f"Consent Mode {'detectado' if t.get('consent_mode') else 'no detectado'}",
           f"- Formularios: {', '.join(t.get('forms', [])) or 'no detectados en la home ni en la landing'} · enlaces de teléfono: {t.get('phone_links', 0)}"]
    if paid:
        out.append(f"- GA4, tráfico de Paid Search: {sum(p['sessions'] for p in paid)} sesiones y {sum(p['key_events'] for p in paid):g} eventos clave")
    return out


def _ads_blocks(d: dict) -> list:
    ads, sig, paid = d["ads"], d["sig"], d["paid"]
    cur, state = ads.get("currency", "€"), ads.get("conversion_state", "")
    out = ["## 4. Google Ads: datos del mes"]
    if ads and ads.get("impressions"):
        show = state == "ok"
        out.append("**Campañas**")
        out.append(_table(["Campaña", "Tipo", "Puja", "Inversión", "Clics", "CPC"] + (["Conv.", "CPA"] if show else []),
                          [[c["name"], c.get("type", ""), c.get("bidding", ""), _money(c["cost"], cur), c["clicks"], _money(c["cpc"], cur)]
                           + ([f"{c['conversions']:g}", _money(c["cpa"], cur) if c.get("cpa") else "—"] if show else [])
                           for c in ads.get("campaigns", [])]))
        out.append("**Términos de búsqueda** (por inversión)")
        out.append(_table(["Término", "Clics", "Inversión", "Conv.", "Pos. orgánica", "Marca"],
                          [[t["term"], t["clicks"], _money(t["cost"], cur), f"{t['conversions']:g}", t["organic"], "sí" if t["brand"] else ""]
                           for t in sig["terms"][:15]]))
        if sig["low_qs"]:
            out.append("**Keywords con nivel de calidad bajo (≤ 5)**")
            out.append(_table(["Keyword", "Concordancia", "QS", "Impr.", "Clics"],
                              [[k["keyword"], k["match"].lower(), k["quality_score"], k["impressions"], k["clicks"]] for k in sig["low_qs"]]))
        if ads.get("impression_share"):
            out.append("**Cuota de impresiones (Search)**")
            out.append(_table(["Campaña", "Cuota", "Perdida por presupuesto", "Perdida por ranking"],
                              [[i["campaign"], f"{i['impression_share']}%", f"{i['lost_budget']}%", f"{i['lost_rank']}%"]
                               for i in ads["impression_share"]]))
        if ads.get("final_urls") or paid:
            out.append("**Landings**")
            out += [f"- Anuncio → {u['url']} ({u['clicks']} clics)" for u in ads.get("final_urls", [])]
            out += [f"- GA4 Paid Search → {p['landing']}: {p['sessions']} sesiones, rebote {p['bounce_rate']}%, {p['key_events']:g} eventos clave"
                    for p in paid[:5]]
            out.append("")
    else:
        out.append(f"_{d['ads_error'] or 'Sin actividad en el mes.'}_\n")
    return out


# ── Archivo WEB (agente de Diseño web) ────────────────────────
def build_web_markdown(d: dict) -> str:
    sig, wp, ins, ads, paid, posts = d["sig"], d["wp"], d["insights"], d["ads"], d["paid"], d["posts"]
    out = _title(d, "WEB", "para el agente de Diseño web")
    out += [f"Web: {d['base']} · MCP Elementor: `{d['mcp'] or 'no configurado'}` · SEO: Rank Math", "",
            "> **Tu trabajo:** redactar cada post con su prompt (sección 2), crearlo en BORRADOR con la configuración de Rank Math "
            "en verde y hacer los cambios y revisiones de la web. No publiques nada ni envíes nada al cliente. "
            "Este archivo lleva todo lo necesario: no hace falta ningún otro conector que el Elementor de esta web. "
            "Al terminar, devuelve la hoja de entrega (sección 7) en el chat.", ""]
    out += _summary_lines(d, ads=False, web=True)

    out += ["## 2. Posts a crear",
            "Cada post trae su prompt completo (datos del informe, ficha SEO, estructura, enlaces y criterio de Rank Math en verde). "
            "Úsalo tal cual para redactarlo; las preguntas o cambios de enfoque, consúltalos antes."]
    if posts:
        for i, p in enumerate(posts, 1):
            out += _post_md(i, p)
            out += _post_prompt(i, p, d)
    else:
        out.append("\n_La web no generó el brief de los posts (sin IA o sin cupo de Gemini). Usa este prompt, que lleva los datos del informe:_")
        out += _fallback_prompts(d)
    if wp.get("posts"):
        out += ["", "**Posts ya publicados (no repetir):** " + " · ".join(p["title"] for p in wp["posts"][:15])]
    out.append("")

    kw = [r for r in d["kw_rows"] if r["uso"].startswith(("post", "optimizar"))]
    out += ["## 3. Palabras clave para el contenido",
            _table(["Keyword", "Fuente", "Volumen", "Pos. orgánica", "Uso propuesto"],
                   [[r["kw"], r["fuente"], r["impr"], r["pos"], r["uso"]] for r in kw])]

    out.append("## 4. Páginas a revisar o actualizar")
    blocks = _insight_blocks(ins, ("decay", "landings"))
    out += blocks or ["_Sin páginas que pierdan clics ni cruces con datos este mes._", ""]
    if ads.get("final_urls") or paid:
        out.append("**Landings de Google Ads** (revisar coherencia con el anuncio, CTA, formulario y velocidad; los datos de Ads los lleva Marketing):")
        out += [f"- Anuncio → {u['url']} ({u['clicks']} clics)" for u in ads.get("final_urls", [])]
        out += [f"- GA4 Paid Search → {p['landing']}: {p['sessions']} sesiones, rebote {p['bounce_rate']}%, {p['key_events']:g} eventos clave"
                for p in paid[:5]]
        out.append("")
    if sig["slash_dupes"]:
        out.append("**URLs indexadas con y sin barra final** (contenido duplicado). Elementor no hace redirecciones: prepara la lista y se aplica en el hosting o con un plugin de redirecciones:")
        out += [f"- {u} y {u}/" for u in sig["slash_dupes"]]
        out.append("")
    if sig["cannibal"]:
        out.append("**Posible canibalización** (varias URLs para la misma consulta):")
        out += [f"- «{c['query']}»: " + " · ".join(f"{r['page']} ({r['impressions']} impr., pos {r['position']})" for r in c["pages"])
                for c in sig["cannibal"]]
        out.append("")

    out += ["## 5. Medición instalada en la web", *_tracking_lines(d["tracking"], paid), ""]

    tasks = []
    for i, p in enumerate(posts, 1):
        tasks.append(f"Post {i} «{p['titulo']}»: redactarlo con su prompt → repasar el criterio de verde → crear el borrador (entrada, "
                     "sin publicar) con título SEO, meta, slug, palabra clave, categoría, etiquetas, extracto, schema e imagen destacada "
                     "de Rank Math → anotarlo en la hoja de entrega")
        tasks += [f"Enlazar a «{p['titulo']}» desde {l['url']} (ancla «{l.get('anchor', '')}»), editando una copia en borrador"
                  for l in p.get("paginas_que_enlazan", [])]
    if not posts:
        tasks.append("Proponer y redactar 2 posts con el prompt de la sección 2 y crearlos como borrador")
    for pg in (ins.get("decay") or {}).get("pages", [])[:3]:
        if not pg["pos_now"]:
            tasks.append(f"Comprobar si {pg['page']} sigue activa o se redirigió: ya no aparece en Google ({pg['clicks_before']} clics antes)")
        else:
            tasks.append(f"Actualizar {pg['page']}: ha perdido {pg['lost']} clics ({pg['pct']}%) en 3 meses (copia en borrador)")
    for r in (ins.get("landings") or {}).get("visible_no_conv", [])[:2]:
        tasks.append(f"Añadir llamada a la acción en {r['page']}: {r['clicks']} clics de Google y 0 conversiones")
    for u in ads.get("final_urls", [])[:1]:
        tasks.append(f"Revisar la landing {u['url']}: titular, CTA, formulario y velocidad")
    for pg in sig["weak_landings"][:2]:
        tasks.append(f"Mejorar la landing {pg['landing']}: rebote {pg['bounce_rate']}% y {pg['key_events']:g} eventos clave desde Paid Search")
    if sig["slash_dupes"]:
        tasks.append(f"Preparar las redirecciones de las URLs duplicadas con/sin barra final ({len(sig['slash_dupes'])})")
    for c in sig["cannibal"][:2]:
        tasks.append(f"Resolver la canibalización de «{c['query']}»: decidir qué página gana y enlazar la otra a ella")
    if d.get("pedidos_web"):
        tasks.append("Atender los pedidos pendientes de Marketing (sección 8)")
    tasks.append("Devolver la hoja de entrega (sección 7) en el chat")
    out += ["## 6. Tareas"] + [f"- [ ] {t}" for t in tasks] + [""]

    out += ["## 7. Entrega",
            "Al terminar, devuelve en el chat esta tabla con una fila por pieza, y debajo el texto final y la ficha SEO de cada post "
            "(con eso Javi genera el Word para el cliente y Marketing revisa lo hecho):", "",
            "| Pieza | Tipo | ID | Estado | Enlace de edición | SEO aplicado | Criterio de verde | Falta a mano |",
            "|---|---|---|---|---|---|---|---|", ""]
    if d.get("pedidos_web"):
        out += ["## 8. Pedidos pendientes de Marketing", "", d["pedidos_web"].strip(), ""]
    return "\n".join(out)


# ── Archivo MARKETING (agente de herramientas de Google) ──────
def build_marketing_markdown(d: dict) -> str:
    sig, ins, ads, paid, tracking = d["sig"], d["insights"], d["ads"], d["paid"], d["tracking"]
    state = ads.get("conversion_state", "")
    out = _title(d, "MARKETING", "para el agente de Marketing")
    out += [f"Web: {d['base']} · Customer ID de Ads: {_cid(d['customer_id']) or '—'}", "",
            "> **Tu trabajo:** análisis y decisiones con GA4, Search Console y Google Ads (solo lectura). No cambias la web: lo que haga "
            "falta en ella se lo pides a Diseño web en la sección 7. Antes de empezar, lee la entrega de Diseño web si existe "
            "(va al final de este archivo).", ""]
    out += _summary_lines(d, ads=True, web=False)

    out += ["## 2. Palabras clave priorizadas",
            _table(["Keyword", "Fuente", "Volumen", "Pos. orgánica", "Conv. Ads", "Uso propuesto"],
                   [[r["kw"], r["fuente"], r["impr"], r["pos"], r["conv"], r["uso"]] for r in d["kw_rows"]])]
    if sig["cannibal"]:
        out.append("**Posible canibalización** (varias URLs para la misma consulta; lo resuelve Diseño web):")
        out += [f"- «{c['query']}»: " + " · ".join(f"{r['page']} ({r['impressions']} impr., pos {r['position']})" for r in c["pages"])
                for c in sig["cannibal"]]
        out.append("")

    out += ["## 3. Tráfico y visibilidad"]
    blocks = _insight_blocks(ins, ("ai", "landings"))
    out += blocks or ["_Sin señales de tráfico desde IA ni cruces con datos este mes._", ""]

    out += _ads_blocks(d)
    if ads and state != "ok":
        out.append(_conversion_section(ads, tracking, paid, sig))

    tasks = []
    if ads and state and state != "ok":
        tasks.append("Configurar la medición de conversiones siguiendo la sección 5, antes de optimizar por CPA")
    for u in ads.get("final_urls", [])[:1]:
        tasks.append(f"Comparar los titulares de los anuncios con la landing {u['url']}; si hay que cambiarla, pedirlo en la sección 7")
    if sig["negatives"]:
        tasks.append("Revisar si son relevantes para el negocio y, si no lo son, añadirlas como negativas: " + ", ".join(f"«{t['term']}»" for t in sig["negatives"][:6]))
    elif ads and ads.get("search_terms"):
        tasks.append("Revisar los términos de búsqueda de la sección 4 y proponer negativas por relevancia")
    if sig["low_qs"]:
        tasks.append("Mejorar la relevancia anuncio/landing de las keywords con QS bajo: " + ", ".join(k["keyword"] for k in sig["low_qs"][:4]))
    for i in ads.get("impression_share", []):
        if i["lost_budget"] >= 20:
            tasks.append(f"Valorar subir presupuesto en «{i['campaign']}»: pierde {i['lost_budget']}% de impresiones por presupuesto")
        if i["lost_rank"] >= 30:
            tasks.append(f"Mejorar anuncios y QS en «{i['campaign']}»: pierde {i['lost_rank']}% de impresiones por ranking")
    if sig["paid_organic"]:
        tasks.append("Decidir si seguir pujando por términos que ya están top 3 en orgánico: " + ", ".join(f"«{t['term']}»" for t in sig["paid_organic"][:4]))
    if ads and ads.get("impressions"):
        tasks.append("Proponer 15 titulares (≤ 30 caracteres) y 4 descripciones (≤ 90) para los RSA con las keywords de la sección 2")
    tasks.append("Revisar la entrega de Diseño web y comprobar que lo hecho no cambia la medición")
    tasks.append("Dejar los pedidos a diseño web con `guardar_pedidos_web` (sección 7)")
    tasks.append("Resumir lo hecho y lo pendiente para el próximo mes")
    out += ["## 6. Tareas"] + [f"- [ ] {t}" for t in tasks] + [""]

    # Pedidos candidatos a Diseño web
    orders = []
    for pg in sig["weak_landings"][:2]:
        if pg["bounce_rate"] >= 60:
            why, crit = (f"rebote del {pg['bounce_rate']}% en {pg['sessions']} sesiones de Paid Search",
                         "rebote por debajo del 45 % en 30 días")
        else:
            why, crit = (f"{pg['sessions']} sesiones de Paid Search y {pg['key_events']:g} eventos clave",
                         "al menos 1 evento clave registrado en 30 días (formulario, WhatsApp o llamada)")
        orders.append(("Mejorar la landing para que genere conversiones", pg["landing"], why, crit))
    if ads and state != "ok" and "Elementor Forms" in (tracking or {}).get("forms", []):
        orders.append(("Redirigir el envío del formulario a una página de «gracias»", "formulario de contacto",
                       "permite medir la conversión sin depender del evento del formulario",
                       "la página /gracias/ existe, no está indexada y se alcanza solo tras enviar el formulario"))
    if ads and ads.get("impressions") and not (tracking or {}).get("phone_links"):
        orders.append(("Añadir teléfono o WhatsApp con enlace visible", (ads.get("final_urls") or [{"url": "landing de Ads"}])[0]["url"],
                       "no hay enlaces de teléfono en la web: se pierden llamadas medibles",
                       "enlace `tel:` o de WhatsApp visible sin hacer scroll en móvil"))
    out += ["## 7. Pedidos a diseño web",
            "Formato: `#n · Qué · Dónde · Por qué (dato) · Criterio de aceptación`. Los siguientes son candidatos automáticos: "
            "confírmalos, edítalos o descártalos y guárdalos con `guardar_pedidos_web`.", ""]
    if orders:
        for n, (what, where, why, crit) in enumerate(orders, 1):
            out.append(f"- **#{n} · {what}** · Dónde: {where} · Por qué: {why} · Criterio de aceptación: {crit}")
    else:
        out.append("_Sin candidatos automáticos este mes._")
    out.append("")
    return "\n".join(out)


# ── Orquestación ──────────────────────────────────────────────
def _pending_orders(folder: str, cu: str) -> str:
    """Pedidos de Marketing a Diseño web aún sin atender (más recientes que la última entrega), para
    incluirlos en el archivo WEB: el agente de Diseño web no tiene el conector de informes."""
    import glob
    latest = lambda pre: max(glob.glob(os.path.join(folder, f"{pre}_{cu}_*.md")), key=os.path.getmtime, default=None)
    ped, ent = latest("PEDIDOS_WEB"), latest("ENTREGA_WEB")
    if not ped or (ent and os.path.getmtime(ent) >= os.path.getmtime(ped)):
        return ""
    with open(ped, encoding="utf-8") as f:
        return f.read()


def generate_propuestas(client: str, month: int, year: int, ga4_data: dict, sc_data: dict,
                        ads_data: dict, ads_error: str = "", insights: dict = None,
                        web: bool = True, marketing: bool = True) -> dict:
    """Genera los .md en OUTPUT_DIR/internos/ y devuelve {'web': ruta|None, 'marketing': ruta|None}."""
    from extract_wp_content import extract_wp_content, site_base
    from check_tracking import check_tracking
    from extract_trends import extract_trends
    from extract_search_console import extract_sc_queries
    from extract_ga4 import extract_paid_landings
    from extract_google_ads import customer_id_for

    cu = client.upper()
    sc_url = os.getenv(f"SEARCH_CONSOLE_URL_{cu}", "")
    ga4_id = os.getenv(f"GA4_PROPERTY_ID_{cu}", "")
    base = site_base(sc_url) if sc_url else ""
    ads = ads_data or {}

    def opt(label, fn, default):
        try:
            return fn()
        except Exception as e:
            print(f"  ⚠️  Propuestas ({label}): {type(e).__name__}: {str(e)[:120]}")
            return default

    scq = opt("Search Console", lambda: extract_sc_queries(sc_url, month, year), {})
    paid = opt("GA4 Paid Search", lambda: extract_paid_landings(ga4_id, month, year), [])
    wp = opt("contenido web", lambda: extract_wp_content(sc_url), {})
    tracking = opt("etiquetas", lambda: check_tracking(base, [u["url"] for u in ads.get("final_urls", [])]), {})

    seeds = [q["query"] for q in sorted(scq.get("queries", []), key=lambda q: -q["impressions"])
             if not _is_brand(q["query"], _brand_tokens(client))][:3]
    seeds += [t["term"] for t in sorted(ads.get("search_terms", []), key=lambda t: -t["clicks"])
              if not _is_brand(t["term"], _brand_tokens(client))][:2]
    trends = opt("Trends", lambda: extract_trends(seeds), {})

    sig = compute_signals(client, ads, scq, wp, trends, paid)
    kw_rows = keyword_table(sig)
    d = {"client": client, "month": month, "year": year, "base": base, "customer_id": customer_id_for(client),
         "mcp": os.getenv(f"WP_MCP_{cu}", "").strip(), "ga4": ga4_data, "sc": sc_data, "ads": ads, "ads_error": ads_error,
         "scq": scq, "paid": paid, "wp": wp, "tracking": tracking, "trends": trends, "sig": sig, "kw_rows": kw_rows,
         "insights": insights or {}, "posts": []}

    out_dir = os.path.join(get_output_dir(), "internos")
    os.makedirs(out_dir, exist_ok=True)
    d["pedidos_web"] = _pending_orders(out_dir, cu)
    paths = {"web": None, "marketing": None}
    for kind, on, build in (("WEB", web, build_web_markdown), ("MARKETING", marketing, build_marketing_markdown)):
        if not on:
            continue
        if kind == "WEB":
            d["posts"] = _ai_posts(client, base, month, year, sig, kw_rows, wp)
        path = os.path.join(out_dir, f"PROPUESTAS_{kind}_{cu}_{month:02d}_{year}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build(d))
        paths[kind.lower()] = path
    return paths
