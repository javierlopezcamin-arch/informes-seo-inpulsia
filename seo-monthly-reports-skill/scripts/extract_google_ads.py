#!/usr/bin/env python3
"""
Extractor de Google Ads (opcional).
Cuenta Manager (MCC) como login_customer_id + Customer ID de cada cliente.
Si falta cualquier credencial, la sección se omite sin afectar al informe.
"""

import calendar
import os
import re

from dotenv import load_dotenv

from utils import cache_read, cache_write, month_ttl_hours

load_dotenv()

REQUIRED_ENV = ("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
                "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
                "GOOGLE_ADS_LOGIN_CUSTOMER_ID")
CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}


def customer_id_for(client: str) -> str:
    """Customer ID de Ads del cliente (10 dígitos, sin guiones) o ''."""
    raw = os.getenv(f"GOOGLE_ADS_CUSTOMER_ID_{client.upper()}", "")
    return re.sub(r"\D", "", raw)


def ads_enabled_for(client: str) -> bool:
    """True si el cliente está marcado para llevar Google Ads + archivo de propuestas."""
    flag = os.getenv(f"ADS_EN_INFORME_{client.upper()}", "").strip().lower()
    return flag in ("true", "1", "si", "sí") and bool(customer_id_for(client))


def credentials_configured() -> bool:
    return all(os.getenv(k, "").strip() for k in REQUIRED_ENV)


def friendly_error(exc: Exception) -> str:
    """Traduce los errores habituales de la API a una acción concreta."""
    name = type(exc).__name__
    text = str(exc)
    codes = ""
    failure = getattr(exc, "failure", None)
    if failure is not None:
        try:
            codes = " ".join(str(e.error_code).replace("\n", " ") for e in failure.errors)
        except Exception:
            codes = ""
    blob = f"{name} {text} {codes}"
    if "invalid_grant" in blob or name == "RefreshError":
        return "Refresh token caducado: ejecuta scripts/generate_ads_refresh_token.py"
    if any(k in blob for k in ("DEVELOPER_TOKEN_NOT_APPROVED", "DEVELOPER_TOKEN_PROHIBITED", "ACTION_NOT_PERMITTED",
                               "only approved for use with test accounts")):
        return ("Acceso a la API en nivel de prueba: solicita acceso Explorer/Basic en "
                "Google Ads → Centro de API (la cuenta MCC)")
    if "REQUESTED_METRICS_FOR_MANAGER" in blob:
        return "Ese ID es de una cuenta Manager (MCC): usa el Customer ID de la cuenta de Ads del cliente"
    if any(k in blob for k in ("USER_PERMISSION_DENIED", "CUSTOMER_NOT_ENABLED", "NOT_ADS_USER", "CUSTOMER_NOT_FOUND")):
        return "Sin acceso a esa cuenta: comprueba el Customer ID y que esté vinculada a la MCC"
    if "ImportError" in blob or "No module named" in blob:
        return "Falta la librería google-ads (pip install google-ads)"
    return re.sub(r"\s+", " ", text)[:140] or name


def _client():
    from google.ads.googleads.client import GoogleAdsClient
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"].strip(),
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"].strip(),
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"].strip(),
        "login_customer_id": re.sub(r"\D", "", os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"]),
        "use_proto_plus": True,
    })


def check_access(customer_id: str) -> dict:
    """Comprobación ligera de acceso a una cuenta de Ads. {'ok': bool, 'error'?: str}"""
    if not customer_id:
        return {"ok": False, "error": "Sin Customer ID"}
    if not credentials_configured():
        return {"ok": False, "error": "Faltan credenciales de Google Ads en el .env"}
    if customer_id == re.sub(r"\D", "", os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")):
        return {"ok": False, "error": "Ese ID es el de tu MCC: usa el Customer ID de la cuenta de Ads del cliente"}
    try:
        service = _client().get_service("GoogleAdsService")
        list(service.search(customer_id=customer_id,
                            query="SELECT customer.id FROM customer LIMIT 1"))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": friendly_error(e)}


def _date_range(month: int, year: int) -> tuple:
    last = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last:02d}"


def _safe(label: str, fn, default):
    """Las consultas de detalle son opcionales: si una falla, se sigue sin ella."""
    try:
        return fn()
    except Exception as e:
        print(f"  ⚠️  Google Ads ({label}): {friendly_error(e)}")
        return default


def _conversion_actions(service, customer_id: str) -> list:
    q = ("SELECT conversion_action.name, conversion_action.type, conversion_action.category, "
         "conversion_action.primary_for_goal FROM conversion_action "
         "WHERE conversion_action.status = 'ENABLED'")
    return [{
        "name": r.conversion_action.name,
        "type": r.conversion_action.type_.name,
        "category": r.conversion_action.category.name,
        "primary": bool(r.conversion_action.primary_for_goal),
    } for r in service.search(customer_id=customer_id, query=q)]


def _conversions_by_action(service, customer_id: str, where: str) -> list:
    q = ("SELECT segments.conversion_action_name, metrics.conversions, metrics.conversions_value "
         f"FROM campaign WHERE {where} AND metrics.conversions > 0")
    acc = {}
    for r in service.search(customer_id=customer_id, query=q):
        a = acc.setdefault(r.segments.conversion_action_name, {"conversions": 0.0, "value": 0.0})
        a["conversions"] += float(r.metrics.conversions)
        a["value"] += float(r.metrics.conversions_value)
    return sorted(({"name": k, "conversions": round(v["conversions"], 1), "value": round(v["value"], 2)}
                   for k, v in acc.items()), key=lambda x: -x["conversions"])


def _conversions_last_90(service, customer_id: str, month: int, year: int) -> float:
    from datetime import date, timedelta
    end = date(year, month, calendar.monthrange(year, month)[1])
    start = end - timedelta(days=90)
    q = ("SELECT metrics.conversions FROM customer "
         f"WHERE segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'")
    return sum(float(r.metrics.conversions) for r in service.search(customer_id=customer_id, query=q))


def _search_terms(service, customer_id: str, where: str) -> list:
    q = ("SELECT search_term_view.search_term, metrics.impressions, metrics.clicks, "
         "metrics.cost_micros, metrics.conversions FROM search_term_view "
         f"WHERE {where} AND metrics.impressions > 0 ORDER BY metrics.cost_micros DESC LIMIT 200")
    acc = {}
    for r in service.search(customer_id=customer_id, query=q):
        t = acc.setdefault(r.search_term_view.search_term.lower(),
                           {"impressions": 0, "clicks": 0, "cost": 0.0, "conversions": 0.0})
        t["impressions"] += int(r.metrics.impressions)
        t["clicks"] += int(r.metrics.clicks)
        t["cost"] += r.metrics.cost_micros / 1_000_000
        t["conversions"] += float(r.metrics.conversions)
    terms = [{"term": k, **v, "cost": round(v["cost"], 2), "conversions": round(v["conversions"], 1)}
             for k, v in acc.items()]
    terms.sort(key=lambda x: (-x["cost"], -x["clicks"]))
    return terms[:25]


def _keywords(service, customer_id: str, where: str) -> list:
    q = ("SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, "
         "ad_group_criterion.quality_info.quality_score, metrics.impressions, metrics.clicks, "
         "metrics.cost_micros, metrics.conversions FROM keyword_view "
         f"WHERE {where} AND ad_group_criterion.status = 'ENABLED' AND metrics.impressions > 0 "
         "ORDER BY metrics.impressions DESC LIMIT 50")
    return [{
        "keyword": r.ad_group_criterion.keyword.text,
        "match": r.ad_group_criterion.keyword.match_type.name,
        "quality_score": int(r.ad_group_criterion.quality_info.quality_score or 0),
        "impressions": int(r.metrics.impressions),
        "clicks": int(r.metrics.clicks),
        "cost": round(r.metrics.cost_micros / 1_000_000, 2),
        "conversions": round(float(r.metrics.conversions), 1),
    } for r in service.search(customer_id=customer_id, query=q)]


def _final_urls(service, customer_id: str, where: str) -> list:
    q = ("SELECT ad_group_ad.ad.final_urls, metrics.clicks FROM ad_group_ad "
         f"WHERE {where} AND metrics.impressions > 0 ORDER BY metrics.clicks DESC LIMIT 50")
    acc = {}
    for r in service.search(customer_id=customer_id, query=q):
        for url in r.ad_group_ad.ad.final_urls:
            acc[url] = acc.get(url, 0) + int(r.metrics.clicks)
    return [{"url": u, "clicks": c} for u, c in sorted(acc.items(), key=lambda x: -x[1])[:5]]


def _impression_share(service, customer_id: str, where: str) -> list:
    q = ("SELECT campaign.name, metrics.search_impression_share, "
         "metrics.search_budget_lost_impression_share, metrics.search_rank_lost_impression_share "
         f"FROM campaign WHERE {where} AND campaign.advertising_channel_type = 'SEARCH' "
         "AND metrics.impressions > 0")
    return [{
        "campaign": r.campaign.name,
        "impression_share": round(float(r.metrics.search_impression_share) * 100, 1),
        "lost_budget": round(float(r.metrics.search_budget_lost_impression_share) * 100, 1),
        "lost_rank": round(float(r.metrics.search_rank_lost_impression_share) * 100, 1),
    } for r in service.search(customer_id=customer_id, query=q)]


def conversion_state(actions: list, conv_month: float, conv_90: float) -> str:
    """sin_configurar · sin_datos · sin_conversiones_mes · ok"""
    if conv_month > 0:
        return "ok"
    if not actions:
        return "sin_configurar"
    return "sin_conversiones_mes" if conv_90 > 0 else "sin_datos"


def run_queries(service, customer_id: str, month: int, year: int) -> dict:
    """Ejecuta las consultas GAQL del mes y devuelve el resumen. `service` = GoogleAdsService."""
    start, end = _date_range(month, year)
    where = f"segments.date BETWEEN '{start}' AND '{end}'"

    totals = {"impressions": 0, "clicks": 0, "cost": 0.0, "conversions": 0.0, "conv_value": 0.0}
    currency = ""
    q_total = ("SELECT customer.currency_code, metrics.impressions, metrics.clicks, "
               "metrics.cost_micros, metrics.conversions, metrics.conversions_value "
               f"FROM customer WHERE {where}")
    for row in service.search(customer_id=customer_id, query=q_total):
        currency = row.customer.currency_code or currency
        m = row.metrics
        totals["impressions"] += int(m.impressions)
        totals["clicks"] += int(m.clicks)
        totals["cost"] += m.cost_micros / 1_000_000
        totals["conversions"] += float(m.conversions)
        totals["conv_value"] += float(m.conversions_value)

    campaigns = []
    q_camp = ("SELECT campaign.name, campaign.advertising_channel_type, campaign.bidding_strategy_type, "
              "metrics.impressions, metrics.clicks, "
              "metrics.cost_micros, metrics.conversions "
              f"FROM campaign WHERE {where} AND metrics.impressions > 0 "
              "ORDER BY metrics.cost_micros DESC LIMIT 8")
    for row in service.search(customer_id=customer_id, query=q_camp):
        m = row.metrics
        clicks = int(m.clicks)
        cost = m.cost_micros / 1_000_000
        conv = float(m.conversions)
        campaigns.append({
            "name": row.campaign.name,
            "type": row.campaign.advertising_channel_type.name,
            "bidding": row.campaign.bidding_strategy_type.name,
            "impressions": int(m.impressions),
            "clicks": clicks,
            "cost": cost,
            "conversions": conv,
            "cpc": cost / clicks if clicks else 0.0,
            "cpa": cost / conv if conv else 0.0,
        })

    actions = _safe("acciones de conversión", lambda: _conversion_actions(service, customer_id), [])
    conv_90 = (totals["conversions"] if totals["conversions"] > 0 else
               _safe("histórico de conversiones", lambda: _conversions_last_90(service, customer_id, month, year), 0.0))

    imps, clicks = totals["impressions"], totals["clicks"]
    return {
        "conversion_state": conversion_state(actions, totals["conversions"], conv_90),
        "conversion_actions": actions,
        "conversions_by_action": _safe("conversiones por acción",
                                       lambda: _conversions_by_action(service, customer_id, where), []),
        "cpa": round(totals["cost"] / totals["conversions"], 2) if totals["conversions"] else 0.0,
        "search_terms": _safe("términos de búsqueda", lambda: _search_terms(service, customer_id, where), []),
        "keywords": _safe("keywords", lambda: _keywords(service, customer_id, where), []),
        "final_urls": _safe("URLs finales", lambda: _final_urls(service, customer_id, where), []),
        "impression_share": _safe("cuota de impresiones", lambda: _impression_share(service, customer_id, where), []),
        "month": month, "year": year,
        "currency": CURRENCY_SYMBOLS.get(currency, currency or "€"),
        "impressions": imps,
        "clicks": clicks,
        "cost": round(totals["cost"], 2),
        "ctr": round(clicks / imps * 100, 2) if imps else 0.0,
        "avg_cpc": round(totals["cost"] / clicks, 2) if clicks else 0.0,
        "conversions": round(totals["conversions"], 1),
        "conv_value": round(totals["conv_value"], 2),
        "campaigns": campaigns,
    }


def extract_google_ads_data(customer_id: str, month: int, year: int) -> dict:
    """Datos de Ads del mes (con caché). Lanza excepción si la API falla."""
    cache_key = f"ads_{customer_id}_{year}_{month:02d}_v2"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        print("  ⚡ Google Ads: datos desde caché")
        return cached
    if customer_id == re.sub(r"\D", "", os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")):
        raise ValueError("REQUESTED_METRICS_FOR_MANAGER: el ID configurado es el de la MCC")
    service = _client().get_service("GoogleAdsService")
    data = run_queries(service, customer_id, month, year)
    print(f"  ✅ Google Ads: {data['impressions']} impresiones | {data['clicks']} clics | "
          f"{data['cost']:.2f} {data['currency']}")
    cache_write(cache_key, data)
    return data


if __name__ == "__main__":
    import sys
    cid = customer_id_for(sys.argv[1]) if len(sys.argv) > 1 else ""
    print(check_access(cid))
