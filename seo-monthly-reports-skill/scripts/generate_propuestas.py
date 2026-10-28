#!/usr/bin/env python3
"""
Archivo INTERNO de propuestas para clientes con Google Ads marcado.

Lo genera la web junto al PDF del cliente y se trabaja después en el proyecto de
Claude "Clientes Inpulsia" (MCP de Google Ads + MCP de Elementor de la web).

  - Señales y tablas: reglas en Python (sin coste de tokens).
  - 2 propuestas de post para el blog: 1 llamada a Gemini (gratis). Sin respaldo de
    pago: si no hay cupo, el archivo deja la tarea para el proyecto de Claude.
  - Siempre con datos reales (sin el ajuste +10%…+50% del informe).
"""

import json
import os
import re
import unicodedata

from utils import MESES, get_output_dir, gemini_usage, GEMINI_DAILY_LIMIT, gemini_bump, gemini_mark_exhausted

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
    negatives = ([t for t in terms if t["conversions"] == 0 and t["cost"] >= max(10, 3 * avg_cpc)]
                 if state == "ok" else [])
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
        add(t["term"], "Ads", f"{_money(t['cost'])}", t["organic"], 0, "negativa")
    return rows[:20]


# ── IA: 2 propuestas de post (solo Gemini) ────────────────────
def _ai_posts(client: str, base: str, month: int, year: int, sig: dict, kw_rows: list, wp: dict) -> list:
    if os.getenv("IA_ENABLED", "true").lower() == "false":
        print("  ℹ️  Propuestas: IA desactivada; los posts quedan como tarea para Claude")
        return []
    key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
    if not key or gemini_usage() >= GEMINI_DAILY_LIMIT:
        print("  ℹ️  Propuestas: sin cupo de Gemini; los posts quedan como tarea para Claude")
        return []
    try:
        from google import genai
    except ImportError:
        return []

    links = [p["url"] for p in wp.get("pages", [])[:30]] + [p["url"] for p in wp.get("posts", [])[:30]]
    existing = [p["title"] for p in wp.get("posts", [])[:60]]
    kw_txt = "\n".join(f"- {r['kw']} | {r['fuente']} | {r['impr']} | pos {r['pos'] or '—'} | {r['uso']}" for r in kw_rows) or "- (sin datos)"
    peaks = ", ".join(f"{k}: pico en {v}" for k, v in sig["peaks"].items()) or "sin datos"
    prompt = (
        "Eres consultor SEO de una agencia. Propón EXACTAMENTE 2 posts nuevos para el blog de esta web. "
        "Responde SOLO con JSON válido, sin markdown, con esta estructura:\n"
        '{"posts":[{"titulo":"","variante":"","keyword_principal":"","keywords_secundarias":["",""],'
        '"intencion":"","slug":"","meta_description":"","h1":"","h2":["","","","",""],'
        '"enlaces_internos":[{"url":"","anchor":""}],"cta":"","por_que":""}]}\n'
        "Reglas: español; titulo ≤ 60 caracteres; variante = otro TÍTULO alternativo ≤ 60 caracteres (no una frase "
        "promocional); meta_description ≤ 155; 5-7 h2, cada uno formulado como pregunta o con la respuesta concreta; "
        "2-3 enlaces_internos usando SOLO URLs de la lista; cta hacia el servicio principal; por_que = 1-2 frases "
        "con al menos una cifra copiada de las keywords candidatas (clics, impresiones o posición; no inventes ninguna); "
        "no repitas temas de los posts existentes; prioriza keywords con uso 'post'.\n\n"
        f"Cliente: {client} · Web: {base} · Mes analizado: {MESES.get(month)} {year}\n"
        f"Estacionalidad (Google Trends): {peaks}\n"
        f"Keywords candidatas (keyword | fuente | volumen | posición orgánica | uso):\n{kw_txt}\n"
        f"Posts ya publicados: {json.dumps(existing, ensure_ascii=False)}\n"
        f"URLs disponibles para enlazar: {json.dumps(links, ensure_ascii=False)}"
    )
    try:
        # El cliente debe vivir en una variable: si se encadena, se cierra antes de la petición
        client_ai = genai.Client(api_key=key, http_options={"timeout": AI_TIMEOUT_MS})
        resp = client_ai.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        gemini_bump()
        txt = (resp.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        posts = json.loads(txt).get("posts", [])
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            gemini_mark_exhausted()
        print(f"  ⚠️  Propuestas: IA sin respuesta válida ({type(e).__name__}); los posts quedan como tarea")
        return []

    valid = set(links)
    out = []
    for p in posts[:2]:
        if not isinstance(p, dict) or not p.get("titulo"):
            continue
        p["enlaces_internos"] = [l for l in p.get("enlaces_internos", []) if isinstance(l, dict) and l.get("url") in valid]
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


def _insights_section(ins: dict) -> list:
    """Sección 3b: contenido que pierde clics, cruce Search Console × GA4 por URL y tráfico desde IA."""
    dec, land, ai = ins.get("decay") or {}, ins.get("landings") or {}, ins.get("ai") or {}
    if not (dec.get("pages") or land.get("visible_no_conv") or land.get("conv_low_vis") or ai.get("sessions")
            or ("measured" in land and not land["measured"])):
        return []
    out = ["## 3b. Contenido, páginas y tráfico desde IA", ""]
    if dec.get("pages"):
        out.append(f"**Páginas que pierden clics** ({dec['window']}). Candidatas a actualizar antes de crear contenido nuevo:")
        out.append(_table(["Página", "Clics antes", "Clics ahora", "Cambio", "Posición antes → ahora"],
                          [[p["page"], _n(p["clicks_before"]), _n(p["clicks_now"]), f"{p['pct']}%",
                            f"{p['pos_before']} → {p['pos_now'] or 'ya no aparece'}"] for p in dec["pages"]]))
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
    if ai.get("sessions"):
        prev = ai.get("prev_sessions")
        out.append(f"**Visitas desde asistentes de IA:** {_n(ai['sessions'])} sesiones"
                   + (f" (mes anterior: {_n(prev)})" if prev is not None else "") + ". "
                   + ", ".join(f"{a['assistant']} {_n(a['sessions'])}" for a in ai["sources"]) + ".")
        out.append("")
    return out


def build_markdown(client: str, month: int, year: int, base: str, customer_id: str, mcp: str,
                   ga4: dict, sc: dict, ads: dict, ads_error: str, scq: dict, paid: list,
                   wp: dict, tracking: dict, trends: dict, posts: list, sig: dict, kw_rows: list,
                   insights: dict = None) -> str:
    cur = ads.get("currency", "€")
    state = ads.get("conversion_state", "")
    mes = f"{MESES.get(month, month).capitalize()} {year}"
    out = [f"# Propuestas — {client.replace('_', ' ').title()} — {mes}  (INTERNO, no enviar al cliente)", "",
           f"Web: {base} · Customer ID de Ads: {_cid(customer_id) or '—'} · "
           f"MCP Elementor: `{mcp}`" if mcp else
           f"Web: {base} · Customer ID de Ads: {_cid(customer_id) or '—'} · MCP Elementor: no configurado", ""]

    # 1. Resumen
    m, s = ga4.get("metrics", {}), sc.get("summary", {})
    paid_sessions = next((c["sessions"] for c in ga4.get("traffic_channels", []) if c["channel"] == "Paid Search"), 0)
    out.append("## 1. Resumen de datos")
    if ads and ads.get("impressions"):
        conv_txt = (f"{ads['conversions']:g} conversiones, CPA {_money(ads['cpa'], cur)}" if state == "ok"
                    else f"conversiones: {STATE_TEXT.get(state, state)}")
        out.append(f"- **Google Ads:** {_money(ads['cost'], cur)} invertidos · {_n(ads['impressions'])} impresiones · "
                   f"{_n(ads['clicks'])} clics · CTR {ads['ctr']}% · CPC {_money(ads['avg_cpc'], cur)} · {conv_txt}")
    else:
        out.append(f"- **Google Ads:** {ads_error or 'sin actividad este mes'}")
    out.append(f"- **Search Console:** {_n(s.get('impressions', 0))} impresiones · {_n(s.get('clicks', 0))} clics · "
               f"CTR {s.get('ctr', 0)}% · posición media {s.get('position', 0)} · {len(scq.get('queries', []))} consultas")
    out.append(f"- **GA4:** {_n(m.get('total_users', 0))} usuarios · {_n(m.get('sessions', 0))} sesiones "
               f"({_n(paid_sessions)} de Paid Search) · rebote {m.get('bounce_rate', 0):.1f}%")
    out.append(f"- **Web:** {len(wp.get('posts', []))} posts y {len(wp.get('pages', []))} páginas publicadas"
               + (f" · último post {wp['posts'][0]['date']}" if wp.get("posts") and wp["posts"][0].get("date") else "")
               + (f" · {wp['error']}" if wp.get("error") else ""))
    if trends and not trends.get("error"):
        out.append(f"- **Google Trends (ES, 12 meses):** " + (", ".join(f"«{k}» pico en {v}" for k, v in sig["peaks"].items()) or "sin picos")
                   + f" · {len(sig['rising'])} consultas en subida")
    else:
        out.append(f"- **Google Trends:** no disponible{' (' + trends['error'] + ')' if trends and trends.get('error') else ''}")
    out.append("")

    # 2. Posts
    out.append("## 2. Propuestas de post para el blog")
    if posts:
        for i, p in enumerate(posts, 1):
            tl = len(p.get("titulo", ""))
            out += ["", f"### Post {i}: {p['titulo']}" + (f"  ⚠️ {tl} caracteres" if tl > 60 else ""),
                    f"- **Variante:** {p.get('variante', '—')}",
                    f"- **Keyword principal:** {p.get('keyword_principal', '—')} · **secundarias:** {', '.join(p.get('keywords_secundarias', [])) or '—'}",
                    f"- **Intención:** {p.get('intencion', '—')}",
                    f"- **Slug:** `/{p.get('slug', '').strip('/')}/` · **Meta description:** {p.get('meta_description', '—')}",
                    f"- **H1:** {p.get('h1', p['titulo'])}",
                    "- **Estructura (H2):**"] + [f"  {j}. {h}" for j, h in enumerate(p.get("h2", []), 1)]
            if p.get("enlaces_internos"):
                out.append("- **Enlaces internos:** " + " · ".join(f"[{l.get('anchor') or l['url']}]({l['url']})" for l in p["enlaces_internos"]))
            out += [f"- **CTA:** {p.get('cta', '—')}", f"- **Por qué ahora:** {p.get('por_que', '—')}"]
            if p.get("existente"):
                out.append(f"- ⚠️ **Actualizar en vez de crear:** ya existe [{p['existente']['title']}]({p['existente']['url']})")
    else:
        out.append("\n_Pendiente: la web no generó las propuestas (sin IA o sin cupo de Gemini). "
                   "Tarea para Claude en la sección 6 a partir de las secciones 1 y 3._")
    if wp.get("posts"):
        out += ["", "**Posts ya publicados (no repetir):** " + " · ".join(p["title"] for p in wp["posts"][:15])]
    out.append("")

    # 3. Keywords
    out += ["## 3. Palabras clave priorizadas",
            _table(["Keyword", "Fuente", "Volumen", "Pos. orgánica", "Conv. Ads", "Uso propuesto"],
                   [[r["kw"], r["fuente"], r["impr"], r["pos"], r["conv"], r["uso"]] for r in kw_rows])]
    if sig["slash_dupes"]:
        out.append("**URLs indexadas con y sin barra final** (contenido duplicado: redirigir una a la otra):")
        out += [f"- {u} y {u}/" for u in sig["slash_dupes"]]
        out.append("")
    if sig["cannibal"]:
        out.append("**Posible canibalización** (varias URLs para la misma consulta):")
        out += [f"- «{c['query']}»: " + " · ".join(f"{r['page']} ({r['impressions']} impr., pos {r['position']})" for r in c["pages"])
                for c in sig["cannibal"]]
        out.append("")

    out += _insights_section(insights or {})

    # 4. Ads
    out.append("## 4. Google Ads: datos del mes")
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
        out.append(f"_{ads_error or 'Sin actividad en el mes.'}_\n")

    # 5. Conversiones
    if ads and state != "ok":
        out.append(_conversion_section(ads, tracking, paid, sig))

    # 6. Tareas
    tasks = []
    ins = insights or {}
    for p in (ins.get("decay") or {}).get("pages", [])[:3]:
        if not p["pos_now"]:
            tasks.append(f"Comprobar si {p['page']} sigue activa o se redirigió: ya no aparece en Google ({p['clicks_before']} clics antes, sección 3b)")
        else:
            tasks.append(f"Actualizar {p['page']}: ha perdido {p['lost']} clics ({p['pct']}%) en 3 meses (sección 3b, MCP Elementor)")
    for r in (ins.get("landings") or {}).get("visible_no_conv", [])[:2]:
        tasks.append(f"Añadir llamada a la acción en {r['page']}: {r['clicks']} clics de Google y 0 conversiones (sección 3b)")
    if ads and state and state != "ok":
        tasks.append("Configurar la medición de conversiones siguiendo la sección 5, antes de optimizar por CPA")
    for u in ads.get("final_urls", [])[:1]:
        tasks.append(f"Revisar la landing {u['url']} frente a los titulares del anuncio, el CTA y el formulario (MCP Elementor)")
    for p in sig["weak_landings"][:2]:
        tasks.append(f"Mejorar la landing {p['landing']}: rebote {p['bounce_rate']}% y {p['key_events']:g} eventos clave desde Paid Search")
    if sig["negatives"]:
        tasks.append("Añadir como negativas, tras revisarlas: " + ", ".join(f"«{t['term']}»" for t in sig["negatives"][:6]) + " (MCP Ads)")
    elif ads and ads.get("search_terms"):
        tasks.append("Revisar los términos de búsqueda de la sección 4 y proponer negativas por relevancia (MCP Ads)")
    if sig["low_qs"]:
        tasks.append("Mejorar la relevancia anuncio/landing de las keywords con QS bajo: " + ", ".join(k["keyword"] for k in sig["low_qs"][:4]))
    for i in ads.get("impression_share", []):
        if i["lost_budget"] >= 20:
            tasks.append(f"Valorar subir presupuesto en «{i['campaign']}»: pierde {i['lost_budget']}% de impresiones por presupuesto")
        if i["lost_rank"] >= 30:
            tasks.append(f"Mejorar anuncios y QS en «{i['campaign']}»: pierde {i['lost_rank']}% de impresiones por ranking")
    if sig["paid_organic"]:
        tasks.append("Decidir si seguir pujando por términos que ya están top 3 en orgánico: "
                     + ", ".join(f"«{t['term']}»" for t in sig["paid_organic"][:4]))
    if posts:
        tasks += [f"Crear como borrador el post {i}: «{p['titulo']}» (MCP Elementor)" for i, p in enumerate(posts, 1)]
    else:
        tasks.append("Proponer 2 posts para el blog con las secciones 1 y 3 y crearlos como borrador (MCP Elementor)")
    if sig["slash_dupes"]:
        tasks.append(f"Redirigir las URLs duplicadas con/sin barra final ({len(sig['slash_dupes'])}, sección 3)")
    for c in sig["cannibal"][:2]:
        tasks.append(f"Resolver la canibalización de «{c['query']}» (sección 3)")
    if ads and ads.get("impressions"):
        tasks.append("Proponer 15 titulares (≤ 30 caracteres) y 4 descripciones (≤ 90) para los RSA con las keywords de la sección 3")
    tasks.append("Resumir lo hecho y lo pendiente para el próximo mes")
    out += ["## 6. Tareas para la conversación de Claude"] + [f"- [ ] {t}" for t in tasks] + [""]
    return "\n".join(out)


# ── Orquestación ──────────────────────────────────────────────
def generate_propuestas(client: str, month: int, year: int, ga4_data: dict, sc_data: dict,
                        ads_data: dict, ads_error: str = "", insights: dict = None) -> str | None:
    """Genera el .md en OUTPUT_DIR/internos/ y devuelve la ruta. Cada fuente extra es opcional."""
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
    posts = _ai_posts(client, base, month, year, sig, kw_rows, wp)
    md = build_markdown(client, month, year, base, customer_id_for(client), os.getenv(f"WP_MCP_{cu}", "").strip(),
                        ga4_data, sc_data, ads, ads_error, scq, paid, wp, tracking, trends, posts, sig, kw_rows, insights)

    out_dir = os.path.join(get_output_dir(), "internos")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"PROPUESTAS_{cu}_{month:02d}_{year}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path
