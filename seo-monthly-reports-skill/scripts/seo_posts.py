#!/usr/bin/env python3
"""
Post de blog estructurado: lectura del contenido en Markdown y semáforo de Rank Math.

El semáforo es una RÉPLICA ORIENTATIVA de los tests de Rank Math (el agente no puede leer la
puntuación real, que se calcula en el navegador). Los umbrales se calibran contra el panel de
cada web. Todo lo de este módulo es determinista y no usa IA.

Campos del post (dict):
    titulo, slug, titulo_seo, meta_description, keyword_principal, keywords_secundarias[],
    categoria, etiquetas[], extracto, schema[] (Article, FAQPage, HowTo…),
    imagen_destacada_alt, tabla_contenidos (bool), contenido (Markdown sin el H1).

En `contenido`: `## ` = H2, `### ` = H3, `> ` = llamada a la acción, listas con `-` o `1.`, tablas con `|`, imágenes como
`![texto alternativo](idea de la imagen)` y enlaces como `[ancla](https://…)` o `[ancla](/ruta/)`.
"""

import math
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

STOP = set("de la el en y a los las del para con por un una unos unas que se al lo o u the of and for to in".split())
FAQ_H2 = re.compile(r"preguntas (frecuentes|y respuestas)|faq|preguntes (freq|i resp)|questions fr[eé]quentes")
QUESTION = re.compile(r"^(como|que|cual|cuales|cuanto|cuanta|cuantos|cuantas|cuando|donde|por que|quien|quienes|"
                      r"es|son|puedo|se puede|hay|vale la pena|com|quant|quanta|quants|quan|quin|quina|quins|on|"
                      r"per que|qui|es pot|comment|quel|quelle|pourquoi|combien|how|what|why|when|which)\b")
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)")
IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]*)\)\s*$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


# ── Texto ──────────────────────────────────────────────────────
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def plain(md: str) -> str:
    """Texto sin sintaxis Markdown (los enlaces quedan como su ancla)."""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md or "")
    s = LINK_RE.sub(r"\1", s)
    s = re.sub(r"[*_`]+", "", s)
    return re.sub(r"<[^>]+>", " ", s)


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", plain(text), re.UNICODE))


def _count(text_norm: str, kw_norm: str) -> int:
    if not kw_norm:
        return 0
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])", text_norm))


def _has(text: str, kw_norm: str) -> bool:
    return _count(norm(plain(text)), kw_norm) > 0


# ── Contenido Markdown ─────────────────────────────────────────
def parse_content(md: str) -> list:
    """Bloques: h1..h6, p, quote (> llamada a la acción), ul, ol, table, img."""
    lines = (md or "").replace("\r\n", "\n").split("\n")
    blocks, para, i = [], [], 0

    def flush():
        if para:
            blocks.append({"t": "p", "text": " ".join(para).strip()})
            para.clear()

    while i < len(lines):
        s = lines[i].strip()
        if not s:
            flush(); i += 1; continue
        m = HEAD_RE.match(s)
        if m:
            flush(); blocks.append({"t": f"h{len(m.group(1))}", "text": m.group(2)}); i += 1; continue
        m = IMG_RE.match(s)
        if m:
            flush(); blocks.append({"t": "img", "alt": m.group(1).strip(), "ref": m.group(2).strip()}); i += 1; continue
        if s.startswith(">"):
            flush(); quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip()); i += 1
            blocks.append({"t": "quote", "text": " ".join(q for q in quote if q)}); continue
        if s.startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"\s*:?-{2,}:?\s*", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            blocks.append({"t": "table", "rows": rows}); continue
        for kind, pat in (("ul", r"^[-*•]\s+(.*)"), ("ol", r"^\d+[.)]\s+(.*)")):
            if re.match(pat, s):
                flush(); items = []
                while i < len(lines) and re.match(pat, lines[i].strip()):
                    items.append(re.match(pat, lines[i].strip()).group(1).strip()); i += 1
                blocks.append({"t": kind, "items": items})
                break
        else:
            para.append(s); i += 1
    flush()
    return blocks


def _block_texts(b: dict) -> list:
    if b["t"] == "table":
        return [c for r in b["rows"] for c in r]
    if b["t"] in ("ul", "ol"):
        return b["items"]
    if b["t"] == "img":
        return []
    return [b["text"]]


def links_in(blocks: list) -> list:
    return [(a.strip(), u.strip()) for b in blocks for t in _block_texts(b) for a, u in LINK_RE.findall(t)]


def split_links(links: list, site_base: str = "") -> tuple:
    """(internos, externos). Interno = ruta relativa o mismo dominio que la web."""
    host = urlparse(site_base).netloc.lower().removeprefix("www.") if site_base else ""
    internal, external = [], []
    for a, u in links:
        p = urlparse(u)
        if not p.netloc or (host and p.netloc.lower().removeprefix("www.") == host):
            internal.append((a, u))
        elif p.netloc:
            external.append((a, u))
    return internal, external


# ── Comprobación de URLs ───────────────────────────────────────
def check_url(url: str, timeout: int = 10):
    """(código HTTP | None, nota). Algunas webs bloquean a los robots (403/429/999): no es un enlace roto."""
    import requests
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True, stream=True)
        r.close()
        return r.status_code, ""
    except Exception as e:
        return None, type(e).__name__


def url_ok(code) -> str:
    """'ok' | 'bloquea' | 'roto'"""
    if code is None:
        return "roto"
    if code < 400:
        return "ok"
    return "bloquea" if code in (401, 403, 405, 429, 999) else "roto"


def check_urls(urls: list) -> dict:
    urls = sorted(set(urls))
    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(zip(urls, pool.map(check_url, urls)))


# ── Tests ──────────────────────────────────────────────────────
def _t(tests, id_, grupo, nombre, nivel, estado, detalle=""):
    tests.append({"id": id_, "grupo": grupo, "nombre": nombre, "nivel": nivel, "estado": estado, "detalle": detalle})


def _range_state(v, green, orange):
    """green/orange = (min, max) inclusivos."""
    if green[0] <= v <= green[1]:
        return "verde"
    return "naranja" if orange[0] <= v <= orange[1] else "rojo"


def validate_post(post: dict, site_base: str = "", existing: list = None, check_links: bool = False) -> dict:
    """Semáforo de Rank Math. `existing` = [{'title', 'url'}] del contenido ya publicado."""
    tests = []
    kw = norm(post.get("keyword_principal"))
    titulo, tseo = post.get("titulo", ""), post.get("titulo_seo", "")
    meta, slug = post.get("meta_description", ""), (post.get("slug") or "").strip().strip("/")
    blocks = parse_content(post.get("contenido", ""))
    schema = {norm(x) for x in (post.get("schema") or [])}
    G_S, G_K, G_E, G_L, G_SN, G_SC, G_O = ("Snippet de resultado", "Palabras clave", "Estructura", "Enlaces",
                                         "Snippets destacados", "Schema", "Otros")

    if not kw:
        _t(tests, "kw", G_K, "Palabra clave principal", "obligatorio", "rojo", "Falta keyword_principal")
        return _summary(tests)

    # Snippet
    _t(tests, "kw_titulo_seo", G_S, "Palabra clave en el título SEO", "obligatorio",
       "verde" if _has(tseo, kw) else "rojo", f"«{tseo}»" if tseo else "Falta titulo_seo")
    pos = norm(tseo).find(kw)
    _t(tests, "kw_titulo_inicio", G_S, "Palabra clave al principio del título SEO", "recomendado",
       "verde" if 0 <= pos <= max(1, len(norm(tseo)) // 2) else "naranja", "")
    n = len(tseo)
    _t(tests, "titulo_seo_long", G_S, "Longitud del título SEO", "obligatorio",
       _range_state(n, (1, 60), (61, 65)), f"{n} caracteres (máximo 60)")
    _t(tests, "titulo_seo_numero", G_S, "Número en el título SEO", "recomendado",
       "verde" if re.search(r"\d", tseo) else "naranja", "Un número mejora el CTR" if not re.search(r"\d", tseo) else "")
    _t(tests, "kw_meta", G_S, "Palabra clave en la meta descripción", "obligatorio",
       "verde" if _has(meta, kw) else "rojo", "")
    n = len(meta)
    _t(tests, "meta_long", G_S, "Longitud de la meta descripción", "obligatorio",
       _range_state(n, (120, 155), (100, 160)), f"{n} caracteres (120-155)")
    slug_tokens = {t for t in slug.split("-") if t}
    kw_tokens = [t for t in kw.split() if t not in STOP and len(t) > 1]
    hit = sum(1 for t in kw_tokens if t in slug_tokens)
    _t(tests, "kw_slug", G_S, "Palabra clave en la URL", "obligatorio",
       "verde" if kw_tokens and hit == len(kw_tokens) else ("naranja" if kw_tokens and hit * 2 >= len(kw_tokens) else "rojo"),
       f"/{slug}/" if slug else "Falta slug")
    _t(tests, "slug_formato", G_S, "Formato de la URL", "obligatorio",
       "verde" if SLUG_RE.match(slug) else "rojo", "minúsculas, sin tildes, con guiones" if not SLUG_RE.match(slug) else "")
    _t(tests, "slug_long", G_S, "Longitud de la URL", "recomendado",
       "verde" if len(slug) < 75 else "naranja", f"{len(slug)} caracteres (menos de 75)")

    # Contenido en texto
    texts = [t for b in blocks if b["t"] != "img" for t in _block_texts(b)]
    full = norm(plain(" ".join(texts)))
    words = re.findall(r"\w+", plain(" ".join(texts)), re.UNICODE)
    total = len(words)
    first = norm(plain(" ".join(words[:max(1, math.ceil(total * 0.10))])))
    heads = [b for b in blocks if re.fullmatch(r"h[1-6]", b["t"])]
    imgs = [b for b in blocks if b["t"] == "img"]
    alts = [b["alt"] for b in imgs] + ([post["imagen_destacada_alt"]] if post.get("imagen_destacada_alt") else [])

    # Palabras clave
    _t(tests, "kw_h1", G_K, "Palabra clave en el H1 (título del post)", "obligatorio",
       "verde" if _has(titulo, kw) else "rojo", f"«{titulo}»")
    _t(tests, "kw_inicio", G_K, "Palabra clave en el primer 10 % del contenido", "obligatorio",
       "verde" if _count(first, kw) else "rojo", "")
    c = _count(full, kw)
    _t(tests, "kw_contenido", G_K, "Palabra clave en el contenido", "obligatorio", "verde" if c else "rojo", f"{c} veces")
    dens = round(c / total * 100, 2) if total else 0
    _t(tests, "kw_densidad", G_K, "Densidad de la palabra clave", "obligatorio",
       _range_state(dens, (0.5, 2.5), (0.3, 3.0)), f"{dens} % (entre 0,5 y 2,5)")
    _t(tests, "kw_subtitulo", G_K, "Palabra clave en algún subtítulo (H2-H6)", "obligatorio",
       "verde" if any(_has(h["text"], kw) for h in heads if h["t"] != "h1") else "rojo", "")
    _t(tests, "kw_alt", G_K, "Palabra clave en el texto alternativo de una imagen", "obligatorio",
       "verde" if any(_has(a, kw) for a in alts) else "rojo", "")
    sec = post.get("keywords_secundarias") or []
    missing = [s for s in sec if not _count(full, norm(s))]
    _t(tests, "kw_secundarias", G_K, "Palabras clave secundarias (2-4) usadas en el texto", "recomendado",
       "verde" if 2 <= len(sec) <= 4 and not missing else "naranja",
       f"{len(sec)} indicadas" + (f"; sin usar en el texto: {', '.join(missing)}" if missing else ""))
    dup = next((e for e in (existing or []) if _covered(kw, e.get("title", "") + " " + e.get("url", "").replace("-", " ")) >= 0.99), None)
    _t(tests, "kw_unica", G_K, "Palabra clave no usada en otro contenido de la web", "recomendado",
       "naranja" if dup else "verde", f"Parecida a «{dup['title']}» ({dup['url']})" if dup else "(aproximado: compara títulos y URLs)")

    # Estructura
    h1s = [h for h in heads if h["t"] == "h1"]
    _t(tests, "h1_unico", G_E, "Un solo H1", "obligatorio", "rojo" if h1s else "verde",
       f"El contenido trae {len(h1s)} H1; el título del post ya es el H1" if h1s else "")
    levels = [int(h["t"][1]) for h in heads if h["t"] != "h1"]
    bad = None
    if levels and levels[0] != 2:
        bad = "empieza por un H3 o inferior; debe empezar por H2"
    for a, b in zip(levels, levels[1:]):
        if b - a > 1:
            bad = f"salta de H{a} a H{b}"
            break
    _t(tests, "jerarquia", G_E, "Jerarquía de encabezados (H2 → H3 sin saltos)", "obligatorio",
       "rojo" if bad or not levels else "verde", bad or ("No hay subtítulos" if not levels else f"{levels.count(2)} H2 y {levels.count(3)} H3"))
    _t(tests, "longitud", G_E, "Longitud del contenido", "obligatorio",
       _range_state(total, (600, 10**6), (300, 599)), f"{total} palabras (mínimo 600)")
    long_p = [b for b in blocks if b["t"] == "p" and count_words(b["text"]) > 120]
    _t(tests, "parrafos", G_E, "Párrafos cortos (120 palabras o menos)", "recomendado",
       "naranja" if long_p else "verde", f"{len(long_p)} párrafo(s) demasiado largo(s)" if long_p else "")
    n_h2 = levels.count(2)
    _t(tests, "toc", G_E, "Tabla de contenidos (desde 4 H2)", "recomendado",
       "verde" if n_h2 < 4 or post.get("tabla_contenidos") else "naranja",
       "Añadir el widget de tabla de contenidos y marcar tabla_contenidos=true" if n_h2 >= 4 and not post.get("tabla_contenidos") else "")
    _t(tests, "media", G_E, "Imagen o vídeo en el contenido", "obligatorio", "verde" if imgs or alts else "rojo", f"{len(imgs)} en el texto")
    no_alt = [b for b in imgs if not b["alt"]]
    _t(tests, "alts", G_E, "Texto alternativo en todas las imágenes", "recomendado",
       "naranja" if no_alt or not post.get("imagen_destacada_alt") else "verde",
       "Falta alt en alguna imagen o en la destacada" if no_alt or not post.get("imagen_destacada_alt") else "")

    # Enlaces
    internal, external = split_links(links_in(blocks), site_base)
    ni = len(internal)
    _t(tests, "enl_int", G_L, "Enlaces internos (3-5)", "obligatorio",
       "verde" if ni >= 3 else ("naranja" if ni else "rojo"), f"{ni} enlaces")
    ne = len(external)
    _t(tests, "enl_ext", G_L, "Enlaces externos (1-3)", "obligatorio",
       "verde" if 1 <= ne <= 3 else ("naranja" if ne > 3 else "rojo"), f"{ne} enlaces")
    anchors = [norm(a) for a, _ in internal]
    rep = sorted({a for a in anchors if anchors.count(a) > 1})
    _t(tests, "anclas", G_L, "Anclas internas sin repetir", "recomendado", "naranja" if rep else "verde", ", ".join(rep))
    if check_links and (internal or external):
        base = site_base.rstrip("/")
        results = check_urls([u if urlparse(u).netloc else base + u for _, u in internal + external])
        broken = [u for u, (code, _) in results.items() if url_ok(code) == "roto"]
        blocked = [u for u, (code, _) in results.items() if url_ok(code) == "bloquea"]
        _t(tests, "enl_activos", G_L, "Los enlaces responden", "obligatorio",
           "rojo" if broken else ("naranja" if blocked else "verde"),
           ("Rotos: " + ", ".join(broken) if broken else "") + (" · Bloquean a robots (revisar a mano): " + ", ".join(blocked) if blocked else ""))
    else:
        _t(tests, "enl_activos", G_L, "Los enlaces responden", "obligatorio", "no_comprobado", "Sin comprobar")

    # Snippets destacados
    qh2 = [i for i, b in enumerate(blocks) if b["t"] == "h2" and (b["text"].rstrip().endswith("?") or QUESTION.match(norm(b["text"])))]
    answers = []
    for i in qh2:
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if nxt and nxt["t"] == "p":
            answers.append(count_words(nxt["text"]))
    good = [w for w in answers if 40 <= w <= 60]
    _t(tests, "respuesta", G_SN, "H2 en forma de pregunta con respuesta directa (40-60 palabras)", "recomendado",
       "verde" if good else "naranja",
       f"{len(qh2)} H2 en pregunta; respuestas de {', '.join(map(str, answers)) or '—'} palabras" if qh2 else "Ningún H2 formulado como pregunta")
    faq_i = next((i for i, b in enumerate(blocks) if b["t"] == "h2" and FAQ_H2.search(norm(b["text"]))), None)
    faq_n = 0
    if faq_i is not None:
        j = faq_i + 1
        while j < len(blocks) and blocks[j]["t"] != "h2":
            if blocks[j]["t"] == "h3" and j + 1 < len(blocks) and blocks[j + 1]["t"] == "p":
                faq_n += 1
            j += 1
    _t(tests, "faq", G_SN, "Preguntas frecuentes (3-5, cada H3 con su respuesta)", "recomendado",
       "verde" if faq_n >= 3 else "naranja", f"{faq_n} preguntas")

    # Schema
    _t(tests, "schema_art", G_SC, "Schema Article o BlogPosting", "obligatorio",
       "verde" if schema & {"article", "blogposting", "newsarticle"} else "rojo", ", ".join(post.get("schema") or []) or "Sin schema")
    if "faqpage" in schema:
        _t(tests, "schema_faq", G_SC, "FAQPage coincide con las preguntas visibles", "obligatorio",
           "verde" if faq_n >= 3 else "rojo", f"{faq_n} preguntas visibles (mínimo 3)")
    elif faq_n >= 3:
        _t(tests, "schema_faq", G_SC, "FAQPage: hay preguntas visibles y falta el schema", "recomendado", "naranja", "Añadir FAQPage")
    if "howto" in schema:
        steps = max([len(b["items"]) for b in blocks if b["t"] == "ol"] or [0])
        _t(tests, "schema_howto", G_SC, "HowTo coincide con una lista de pasos", "obligatorio",
           "verde" if steps >= 3 else "rojo", f"{steps} pasos en lista numerada (mínimo 3)")

    # Otros
    _t(tests, "categoria", G_O, "Categoría", "recomendado", "verde" if post.get("categoria") else "naranja", "")
    et = post.get("etiquetas") or []
    _t(tests, "etiquetas", G_O, "Etiquetas (1-5)", "recomendado", "verde" if 1 <= len(et) <= 5 else "naranja", f"{len(et)}")
    _t(tests, "extracto", G_O, "Extracto", "recomendado", "verde" if post.get("extracto") else "naranja", "")
    return _summary(tests)


def _covered(a: str, b: str) -> float:
    ta = {w[:5] for w in norm(a).split() if w not in STOP and len(w) > 1}
    tb = {w[:5] for w in norm(b).split() if w not in STOP and len(w) > 1}
    return len(ta & tb) / len(ta) if ta else 0.0


def _summary(tests: list) -> dict:
    c = {k: sum(1 for t in tests if t["estado"] == k) for k in ("verde", "naranja", "rojo", "no_comprobado")}
    g = "ROJO" if c["rojo"] else ("NARANJA" if c["naranja"] else "VERDE")
    return {"tests": tests, "conteo": c, "global": g}


ICON = {"verde": "🟢", "naranja": "🟠", "rojo": "🔴", "no_comprobado": "⚪"}


def render_report(res: dict) -> str:
    c, tests = res["conteo"], res["tests"]
    out = [f"Semáforo Rank Math (réplica orientativa): {ICON[{'VERDE': 'verde', 'NARANJA': 'naranja', 'ROJO': 'rojo'}[res['global']]]} "
           f"{res['global']} — {c['verde']} verdes · {c['naranja']} naranjas · {c['rojo']} rojos"
           + (f" · {c['no_comprobado']} sin comprobar" if c["no_comprobado"] else ""), ""]
    todo = [t for t in tests if t["estado"] in ("rojo", "naranja")]
    if todo:
        out.append("Para corregir (primero los rojos):")
        for t in sorted(todo, key=lambda t: t["estado"] != "rojo"):
            out.append(f"- {ICON[t['estado']]} {t['nombre']}" + (f": {t['detalle']}" if t["detalle"] else ""))
        out.append("")
    out.append("Detalle:")
    grupo = None
    for t in tests:
        if t["grupo"] != grupo:
            grupo = t["grupo"]
            out.append(f"**{grupo}**")
        out.append(f"{ICON[t['estado']]} {t['nombre']}" + (f" — {t['detalle']}" if t["detalle"] and t["estado"] == "verde" else ""))
    return "\n".join(out)


def brief_issues(b: dict) -> list:
    """Avisos del brief que genera la IA (antes de que exista el texto)."""
    kw = norm(b.get("keyword_principal"))
    issues = []
    if not kw:
        return ["falta la palabra clave principal"]
    tseo, meta, slug = b.get("titulo_seo", ""), b.get("meta_description", ""), (b.get("slug") or "").strip("/")
    if len(tseo) > 60:
        issues.append(f"título SEO de {len(tseo)} caracteres (máx. 60)")
    if not _has(tseo, kw):
        issues.append("la palabra clave no está en el título SEO")
    if not 120 <= len(meta) <= 155:
        issues.append(f"meta descripción de {len(meta)} caracteres (120-155)")
    if not _has(meta, kw):
        issues.append("la palabra clave no está en la meta descripción")
    if not SLUG_RE.match(slug) or len(slug) >= 75:
        issues.append("slug con formato o longitud no válidos")
    toks = [t for t in kw.split() if t not in STOP and len(t) > 1]
    if toks and not all(t in slug.split("-") for t in toks):
        issues.append("la palabra clave no está entera en el slug")
    return issues
