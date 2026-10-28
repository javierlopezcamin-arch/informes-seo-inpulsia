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
            extra = " · Google Ads" + (" (marcado: informe + propuestas)" if marcado else "")
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


@mcp.tool()
def get_propuestas(cliente: str, mes: int = None, anio: int = None) -> str:
    """
    Devuelve el archivo INTERNO de propuestas del mes (posts para el blog, keywords, datos de Ads,
    seguimiento de conversiones y tareas), tal como lo generó la web de informes.
    Si no se indica mes, devuelve el más reciente del cliente.

    Args:
        cliente: nombre del cliente (ej: "piscinas_riviera")
        mes: número de mes 1-12 (opcional)
        anio: año (opcional)
    """
    import glob
    from utils import get_output_dir
    key = cliente.strip().upper().replace(" ", "_")
    folder = os.path.join(get_output_dir(), "internos")
    if mes:
        path = os.path.join(folder, f"PROPUESTAS_{key}_{int(mes):02d}_{anio or date.today().year}.md")
        candidates = [path] if os.path.exists(path) else []
    else:
        candidates = sorted(glob.glob(os.path.join(folder, f"PROPUESTAS_{key}_*.md")), key=os.path.getmtime)
    if not candidates:
        return (f"No hay archivo de propuestas de '{cliente}' en {folder}. "
                "Se genera desde la web de informes para clientes con Google Ads marcado.")
    with open(candidates[-1], encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    mcp.run(transport="stdio")
