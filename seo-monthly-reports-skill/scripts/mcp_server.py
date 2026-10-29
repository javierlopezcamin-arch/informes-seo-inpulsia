#!/usr/bin/env python3
"""
Servidor MCP local (stdio) para consultar GA4 / Search Console desde Claude Desktop.

Reutiliza extract_ga4.py, extract_search_console.py y analyze.py del generador
de informes (seo-monthly-reports-skill/scripts/). No genera PPTX: es para
consulta interna rápida ("¿cómo va el tráfico de armonicar este mes?").

Ver docs/MCP_SERVER_PLAN.md para el contexto de la decisión de arquitectura.
"""

import os
import sys
from datetime import date
from typing import Union

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(SKILL_DIR, ".env"))

# Las rutas en .env (ej. credenciales/cappuccino-key.json) son relativas a
# SKILL_DIR. Claude Desktop lanza este proceso con un cwd desconocido, así
# que las resolvemos a absolutas aquí.
_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
if _creds and not os.path.isabs(_creds):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(SKILL_DIR, _creds)

from mcp.server.fastmcp import FastMCP
from utils import MESES
from extract_ga4 import extract_ga4_data
from extract_search_console import extract_search_console_data
from analyze import analyze_seo_data

mcp = FastMCP("seo-inpulsia")


def _discover_clients() -> dict:
    """Mapea nombre de cliente (en minúsculas) -> {property_id, site_url} desde .env"""
    clients = {}
    for key, value in os.environ.items():
        if key.startswith("GA4_PROPERTY_ID_"):
            name = key[len("GA4_PROPERTY_ID_"):].lower()
            clients.setdefault(name, {})["property_id"] = value
        elif key.startswith("SEARCH_CONSOLE_URL_"):
            name = key[len("SEARCH_CONSOLE_URL_"):].lower()
            clients.setdefault(name, {})["site_url"] = value
    return clients


def _resolve_client(cliente: str) -> dict:
    clients = _discover_clients()
    key = cliente.strip().lower().replace(" ", "_")
    if key not in clients:
        disponibles = ", ".join(sorted(clients.keys()))
        raise ValueError(f"Cliente '{cliente}' no encontrado. Disponibles: {disponibles}")
    return clients[key]


def _resolve_month_year(mes: int = None, anio: int = None) -> tuple:
    """Si no se especifican, usa el mes actual."""
    today = date.today()
    return (mes or today.month, anio or today.year)


@mcp.tool()
def list_clientes() -> str:
    """Lista los clientes disponibles para consultar (GA4 / Search Console)."""
    clients = _discover_clients()
    if not clients:
        return "No hay clientes configurados en .env"
    lineas = []
    for name, cfg in sorted(clients.items()):
        tiene_ga4 = "GA4" if "property_id" in cfg else ""
        tiene_sc = "Search Console" if "site_url" in cfg else ""
        fuentes = " + ".join(f for f in (tiene_ga4, tiene_sc) if f)
        extra = ""
        if os.getenv(f"GOOGLE_ADS_CUSTOMER_ID_{name.upper()}"):
            marcado = os.getenv(f"ADS_EN_INFORME_{name.upper()}", "").lower() == "true"
            extra = " · Google Ads" + (" (marcado: informe + archivo de marketing)" if marcado else "")
        if os.getenv(f"WEB_EN_INFORME_{name.upper()}", "").lower() == "true":
            extra += " · archivo de diseño web activado"
        if os.getenv(f"WP_MCP_{name.upper()}"):
            extra += f" · MCP web: {os.getenv(f'WP_MCP_{name.upper()}')}"
        lineas.append(f"- {name} ({fuentes}){extra}")
    return "\n".join(lineas)


@mcp.tool()
def get_ga4_overview(cliente: str, mes: int = None, anio: int = None) -> str:
    """
    Resumen de tráfico de Google Analytics 4 para un cliente.

    Args:
        cliente: nombre del cliente (ej: "armonicar", "10deco", "inpulsia")
        mes: número de mes 1-12 (opcional, por defecto el mes actual)
        anio: año (opcional, por defecto el año actual)
    """
    cfg = _resolve_client(cliente)
    if "property_id" not in cfg:
        return f"El cliente '{cliente}' no tiene GA4_PROPERTY_ID configurado."

    mes, anio = _resolve_month_year(mes, anio)
    data = extract_ga4_data(cfg["property_id"], mes, anio)
    if not data:
        return "No se pudieron obtener datos de GA4 (revisa credenciales)."

    m = data["metrics"]
    nombre_mes = MESES.get(mes, str(mes))
    top_canales = ", ".join(
        f"{c['channel']} ({c['percentage']}%)" for c in data["traffic_channels"][:5]
    )
    top_paginas = "\n".join(
        f"  - {p['path']} ({p['views']} vistas, {p['percentage']}%)"
        for p in data["top_pages"][:5]
    )

    return (
        f"GA4 — {cliente} — {nombre_mes} {anio}\n"
        f"Usuarios totales: {m['total_users']} | Sesiones: {m['sessions']}\n"
        f"Páginas vistas: {m['pageviews']} | Duración media: {m['avg_session_duration']:.0f}s\n"
        f"Tasa de rebote: {m['bounce_rate']:.1f}% | Engagement: {m['engagement_rate']:.1f}%\n"
        f"Canales principales: {top_canales}\n"
        f"Top páginas:\n{top_paginas}"
    )


@mcp.tool()
def get_search_console_status(cliente: str, mes: int = None, anio: int = None) -> str:
    """
    Resumen de Google Search Console (impresiones, clics, CTR, posición, keywords) para un cliente.

    Args:
        cliente: nombre del cliente (ej: "armonicar", "10deco", "inpulsia")
        mes: número de mes 1-12 (opcional, por defecto el mes actual)
        anio: año (opcional, por defecto el año actual)
    """
    cfg = _resolve_client(cliente)
    if "site_url" not in cfg:
        return f"El cliente '{cliente}' no tiene SEARCH_CONSOLE_URL configurado."

    mes, anio = _resolve_month_year(mes, anio)
    data = extract_search_console_data(cfg["site_url"], mes, anio)
    if not data:
        return "No se pudieron obtener datos de Search Console (revisa credenciales)."

    s = data["summary"]
    nombre_mes = MESES.get(mes, str(mes))
    top_keywords = "\n".join(
        f"  - {k['query']} (imp: {k['impressions']}, clics: {k['clicks']}, pos: {k['position']})"
        for k in data["top_keywords"][:10]
    )

    return (
        f"Search Console — {cliente} — {nombre_mes} {anio}\n"
        f"Impresiones: {s['impressions']} | Clics: {s['clicks']}\n"
        f"CTR: {s['ctr']}% | Posición media: {s['position']}\n"
        f"Top keywords:\n{top_keywords}"
    )


@mcp.tool()
def get_recommendations(cliente: str, mes: int = None, anio: int = None) -> str:
    """
    Genera recomendaciones e insights SEO/IA para un cliente, combinando GA4 y Search Console.

    Args:
        cliente: nombre del cliente (ej: "armonicar", "10deco", "inpulsia")
        mes: número de mes 1-12 (opcional, por defecto el mes actual)
        anio: año (opcional, por defecto el año actual)
    """
    cfg = _resolve_client(cliente)
    mes, anio = _resolve_month_year(mes, anio)

    ga4_data = extract_ga4_data(cfg["property_id"], mes, anio) if "property_id" in cfg else {}
    sc_data = extract_search_console_data(cfg["site_url"], mes, anio) if "site_url" in cfg else {}
    if not ga4_data and not sc_data:
        return "No se pudieron obtener datos de GA4 ni de Search Console."

    analysis = analyze_seo_data(ga4_data, sc_data)
    nombre_mes = MESES.get(mes, str(mes))

    recomendaciones = "\n".join(f"- {r}" for r in analysis.get("recommendations", []))
    opp_items = analysis.get("opportunities", {}).get("opportunities", [])
    oportunidades = "\n".join(
        f"- {o['query']} (posición {o['position']}, {o['impressions']} impresiones, "
        f"a {o['gap']} de entrar en el Top 10)"
        for o in opp_items
    )

    return (
        f"Recomendaciones — {cliente} — {nombre_mes} {anio}\n\n"
        f"Resumen ejecutivo:\n{analysis.get('executive_summary', '(sin resumen)')}\n\n"
        f"Recomendaciones:\n{recomendaciones or '(ninguna)'}\n\n"
        f"Oportunidades:\n{oportunidades or '(ninguna)'}"
    )


@mcp.tool()
def get_google_ads_overview(cliente: str, mes: int = None, anio: int = None) -> str:
    """
    Google Ads de un cliente (solo lectura): inversión, clics, CPC, estado de las conversiones,
    campañas, términos de búsqueda, keywords con nivel de calidad bajo y cuota de impresiones.

    Args:
        cliente: nombre del cliente (ej: "piscinas_riviera")
        mes: número de mes 1-12 (opcional, por defecto el mes actual)
        anio: año (opcional, por defecto el año actual)
    """
    from extract_google_ads import extract_google_ads_data, customer_id_for, credentials_configured, friendly_error
    key = cliente.strip().upper().replace(" ", "_")
    cid = customer_id_for(key)
    if not cid:
        return f"El cliente '{cliente}' no tiene GOOGLE_ADS_CUSTOMER_ID configurado."
    if not credentials_configured():
        return "Faltan credenciales de Google Ads en el .env."
    mes, anio = _resolve_month_year(mes, anio)
    try:
        a = extract_google_ads_data(cid, mes, anio)
    except Exception as e:
        return f"Google Ads no disponible: {friendly_error(e)}"

    cur = a.get("currency", "€")
    estado = a.get("conversion_state", "")
    lines = [f"Google Ads — {cliente} — {MESES.get(mes, mes)} {anio} (Customer ID {cid})",
             f"Inversión: {a['cost']:.2f} {cur} | Impresiones: {a['impressions']} | Clics: {a['clicks']} | "
             f"CTR: {a['ctr']}% | CPC: {a['avg_cpc']:.2f} {cur}",
             f"Conversiones: {a['conversions']:g} (estado: {estado})" + (f" | CPA: {a['cpa']:.2f} {cur}" if a.get("cpa") else "")]
    if a.get("conversion_actions"):
        lines.append("Acciones de conversión activas: " + ", ".join(x["name"] for x in a["conversion_actions"]))
    lines.append("Campañas:")
    lines += [f"  - {c['name']} [{c.get('type', '')}, {c.get('bidding', '')}]: {c['cost']:.2f} {cur}, "
              f"{c['clicks']} clics, {c['conversions']:g} conv." for c in a.get("campaigns", [])]
    if a.get("search_terms"):
        lines.append("Términos de búsqueda (por inversión):")
        lines += [f"  - {t['term']}: {t['clicks']} clics, {t['cost']:.2f} {cur}, {t['conversions']:g} conv."
                  for t in a["search_terms"][:15]]
    low_qs = [k for k in a.get("keywords", []) if 0 < k["quality_score"] <= 5]
    if low_qs:
        lines.append("Keywords con QS ≤ 5: " + ", ".join(f"{k['keyword']} ({k['quality_score']})" for k in low_qs[:10]))
    for i in a.get("impression_share", []):
        lines.append(f"Cuota de impresiones «{i['campaign']}»: {i['impression_share']}% "
                     f"(perdida por presupuesto {i['lost_budget']}%, por ranking {i['lost_rank']}%)")
    if a.get("final_urls"):
        lines.append("Landings: " + ", ".join(u["url"] for u in a["final_urls"]))
    return "\n".join(lines)


# ── Archivos de los dos agentes (Diseño web → Marketing) ───────
def _internos() -> str:
    from utils import get_output_dir
    return os.path.join(get_output_dir(), "internos")


def _key(cliente: str) -> str:
    _resolve_client(cliente)  # falla si el cliente no existe: así el nombre de archivo es siempre seguro
    return cliente.strip().upper().replace(" ", "_")


def _find(prefix: str, mes: int = None, anio: int = None):
    """Archivo `<prefix>_<MM>_<AAAA>.md` pedido, o el más reciente si no se indica el mes."""
    import glob
    folder = _internos()
    if mes:
        path = os.path.join(folder, f"{prefix}_{int(mes):02d}_{anio or date.today().year}.md")
        return path if os.path.exists(path) else None
    found = sorted(glob.glob(os.path.join(folder, f"{prefix}_*.md")), key=os.path.getmtime)
    return found[-1] if found else None


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _save(prefix: str, contenido: str, mes: int = None, anio: int = None) -> str:
    if not contenido or not contenido.strip():
        raise ValueError("El contenido está vacío")
    if len(contenido) > 200_000:
        raise ValueError("El contenido supera los 200.000 caracteres")
    m, y = _resolve_month_year(mes, anio)
    os.makedirs(_internos(), exist_ok=True)
    path = os.path.join(_internos(), f"{prefix}_{m:02d}_{y}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido.strip() + "\n")
    return path


@mcp.tool()
def get_propuestas(cliente: str, tipo: str = "web", mes: int = None, anio: int = None) -> str:
    """
    Devuelve el archivo INTERNO del mes para un agente, tal como lo generó la web de informes.
    - tipo="web": para el agente de Diseño web (posts con brief completo, páginas a revisar). Si Marketing
      dejó pedidos que aún no se han atendido (más recientes que la última entrega), se añaden al final.
    - tipo="marketing": para el agente de Marketing (Ads, GA4, Search Console, pedidos). Si Diseño web ya
      guardó su entrega, se añade al final.
    Si no se indica mes, devuelve el más reciente del cliente.

    Args:
        cliente: nombre del cliente (ej: "piscinas_riviera")
        tipo: "web" o "marketing"
        mes: número de mes 1-12 (opcional)
        anio: año (opcional)
    """
    tipo = (tipo or "").strip().lower()
    if tipo not in ("web", "marketing"):
        return 'El tipo debe ser "web" o "marketing".'
    key = _key(cliente)
    path = _find(f"PROPUESTAS_{tipo.upper()}_{key}", mes, anio)
    if not path:
        return (f"No hay archivo {tipo.upper()} de '{cliente}' en {_internos()}. Se genera desde la web de informes: "
                + ("activando «Archivo de diseño web» (WEB_EN_INFORME_%s=true)." % key if tipo == "web"
                   else "marcando Google Ads (ADS_EN_INFORME_%s=true)." % key))
    text = _read(path)
    entrega = _find(f"ENTREGA_WEB_{key}")
    pedidos = _find(f"PEDIDOS_WEB_{key}")
    if tipo == "marketing" and entrega:
        text += f"\n\n---\n## Entrega de Diseño web ({os.path.basename(entrega)})\n\n" + _read(entrega)
    if tipo == "web" and pedidos and (not entrega or os.path.getmtime(pedidos) > os.path.getmtime(entrega)):
        text += f"\n\n---\n## Pedidos pendientes de Marketing ({os.path.basename(pedidos)})\n\n" + _read(pedidos)
    return text


@mcp.tool()
def guardar_entrega(cliente: str, contenido: str, mes: int = None, anio: int = None) -> str:
    """
    El agente de Diseño web guarda su HOJA DE ENTREGA (una fila por pieza: ID, estado, enlace de edición,
    Word, SEO aplicado, semáforo y lo que falta a mano). Marketing la lee con get_propuestas(tipo="marketing")
    o get_entrega. Reemplaza la entrega de ese mes. Solo escribe en la carpeta interna.

    Args:
        cliente: nombre del cliente
        contenido: la hoja de entrega en Markdown
        mes: número de mes 1-12 (opcional; por defecto el actual)
        anio: año (opcional)
    """
    return "Entrega guardada: " + _save(f"ENTREGA_WEB_{_key(cliente)}", contenido, mes, anio)


@mcp.tool()
def get_entrega(cliente: str, mes: int = None, anio: int = None) -> str:
    """Devuelve la hoja de entrega de Diseño web (la del mes indicado o la más reciente)."""
    path = _find(f"ENTREGA_WEB_{_key(cliente)}", mes, anio)
    return _read(path) if path else f"Todavía no hay entrega de Diseño web para '{cliente}'."


@mcp.tool()
def guardar_pedidos_web(cliente: str, contenido: str, mes: int = None, anio: int = None) -> str:
    """
    El agente de Marketing guarda sus PEDIDOS A DISEÑO WEB. Formato por pedido:
    `#n · Qué · Dónde (URL) · Por qué (dato del archivo) · Criterio de aceptación`.
    Diseño web los verá al final de get_propuestas(tipo="web") hasta que guarde una entrega nueva.
    Reemplaza los pedidos de ese mes.

    Args:
        cliente: nombre del cliente
        contenido: los pedidos en Markdown
        mes: número de mes 1-12 (opcional; por defecto el actual)
        anio: año (opcional)
    """
    return "Pedidos guardados: " + _save(f"PEDIDOS_WEB_{_key(cliente)}", contenido, mes, anio)


@mcp.tool()
def get_pedidos_web(cliente: str, mes: int = None, anio: int = None) -> str:
    """Devuelve los pedidos de Marketing a Diseño web (los del mes indicado o los más recientes)."""
    path = _find(f"PEDIDOS_WEB_{_key(cliente)}", mes, anio)
    return _read(path) if path else f"No hay pedidos de Marketing para '{cliente}'."


# ── Posts: semáforo de Rank Math y Word para el cliente ─────────
POST_DOC = """
    El post es un objeto con estos campos:
      titulo (H1), slug, titulo_seo, meta_description, keyword_principal, keywords_secundarias[],
      categoria, etiquetas[], extracto, schema[] ("Article", "FAQPage", "HowTo"),
      imagen_destacada_alt, tabla_contenidos (true si el post lleva el widget de tabla de contenidos),
      contenido (Markdown SIN el H1: `## ` H2, `### ` H3, `> ` llamada a la acción, listas con `-` o `1.`,
      tablas con `|`, imágenes como `![texto alternativo](idea de la imagen)`, enlaces como
      `[ancla](https://…)` o `[ancla](/ruta/)`; las preguntas frecuentes van bajo un H2 «Preguntas
      frecuentes» con cada pregunta como H3 seguida de su respuesta).
"""


def _post_context(post, cliente: str):
    import json
    from extract_wp_content import extract_wp_content, site_base
    if isinstance(post, str):
        post = json.loads(post)
    if not isinstance(post, dict):
        raise ValueError("El post debe ser un objeto con los campos indicados")
    key = _key(cliente)
    sc_url = os.getenv(f"SEARCH_CONSOLE_URL_{key}", "")
    base = site_base(sc_url) if sc_url else ""
    existing = []
    try:
        wp = extract_wp_content(sc_url) if sc_url else {}
        existing = [{"title": x.get("title", ""), "url": x.get("url", "")} for x in wp.get("posts", []) + wp.get("pages", [])]
    except Exception:
        pass
    return post, key, base, existing


@mcp.tool()
def validar_seo_post(post: Union[dict, str], cliente: str, comprobar_enlaces: bool = True) -> str:
    """
    Semáforo de Rank Math para un post ANTES de crear el borrador: réplica orientativa de los tests
    (título SEO, meta, URL, palabra clave, densidad, H1-H3, enlaces internos y externos, schema, snippets
    destacados…). Devuelve qué corregir. Verde = todos los tests en verde. Usarlo en bucle hasta que no
    queden rojos ni naranjas (o justificar el que no pueda cumplirse). No usa IA ni gasta cuota.
    """ + POST_DOC + """
    Args:
        post: el post (objeto)
        cliente: nombre del cliente (para comprobar enlaces y que la palabra clave no esté ya usada)
        comprobar_enlaces: si es true, comprueba que los enlaces responden (unos segundos)
    """
    import seo_posts
    post, key, base, existing = _post_context(post, cliente)
    return seo_posts.render_report(seo_posts.validate_post(post, base, existing, check_links=comprobar_enlaces))


@mcp.tool()
def crear_word_post(post: Union[dict, str], cliente: str, mes: int = None, anio: int = None) -> str:
    """
    Genera el WORD del post para que Javi lo envíe al cliente: texto completo con formato Inpulsia y, al final,
    la «Ficha SEO». No incluye nada interno (ni cifras de Ads, ni volúmenes, ni IDs, ni el semáforo). Cada
    llamada crea una versión nueva (v1, v2…): usarlo otra vez cuando el cliente pida cambios.
    Se guarda en <carpeta de informes>/para_cliente/<CLIENTE>/.
    """ + POST_DOC + """
    Args:
        post: el post (objeto)
        cliente: nombre del cliente
        mes: número de mes 1-12 (opcional; por defecto el actual)
        anio: año (opcional)
    """
    import seo_posts
    from word_post import create_word
    post, key, base, existing = _post_context(post, cliente)
    res = create_word(post, key, base, mes, anio)
    val = seo_posts.validate_post(post, base, existing)
    out = f"Word creado (v{res['version']}): {res['path']}"
    rojos = [t["nombre"] for t in val["tests"] if t["estado"] == "rojo"]
    if rojos:
        out += "\nAVISO: el semáforo de Rank Math tiene rojos; corrígelos antes de enviarlo: " + "; ".join(rojos)
    return out


if __name__ == "__main__":
    mcp.run(transport="stdio")
