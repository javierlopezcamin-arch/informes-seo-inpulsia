#!/usr/bin/env python3
"""
Comprobaciones rápidas para el panel: acceso a GA4 / Search Console por cliente,
estado persistido y revisión de datos sospechosos antes de generar un informe.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

from utils import _CACHE_DIR, prev_month, MESES

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
STATUS_PATH = os.path.join(_CACHE_DIR, "access_status.json")
SERVICE_ACCOUNT = "seo-reports@cappuccino.iam.gserviceaccount.com"


def _env():
    load_dotenv(ENV_PATH, override=True)
    creds = os.path.expanduser(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
    if creds and not os.path.isabs(creds):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(BASE_DIR, creds)
    return os.environ


load_env = _env


def _creds_path():
    return os.path.expanduser(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))


def client_config(client: str, reload: bool = True) -> dict:
    env = _env() if reload else os.environ
    c = client.upper()
    return {
        "ga4": (env.get(f"GA4_PROPERTY_ID_{c}") or "").strip(),
        "sc": (env.get(f"SEARCH_CONSOLE_URL_{c}") or "").strip(),
        "ads": re.sub(r"\D", "", env.get(f"GOOGLE_ADS_CUSTOMER_ID_{c}") or ""),
    }


# ── Acceso ───────────────────────────────────────────────────

def _friendly(service: str, exc: Exception) -> str:
    text = str(exc)
    status = getattr(getattr(exc, "resp", None), "status", None) or getattr(exc, "code", None)
    low = text.lower()
    if status in (403,) or "permission" in low or "forbidden" in low:
        if service == "ga4":
            return f"Sin acceso: añade {SERVICE_ACCOUNT} como Lector, o revisa el Property ID"
        return (f"Sin acceso: añade {SERVICE_ACCOUNT} con permiso Completo, "
                "o revisa que la URL coincida con la propiedad (¿sc-domain:?)")
    if status in (404,) or "not found" in low:
        return "Propiedad no encontrada: revisa la URL (¿es sc-domain:?)" if service == "sc" else "Property ID no encontrado"
    if "invalid" in low or status == 400:
        return "Identificador inválido" if service == "ga4" else "URL inválida"
    return re.sub(r"\s+", " ", text)[:120]


def _check_ga4(prop: str) -> dict:
    if not prop:
        return {"ok": False, "error": "Sin GA4 Property ID"}
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest, Metric, DateRange
        creds = Credentials.from_service_account_file(
            _creds_path(), scopes=["https://www.googleapis.com/auth/analytics.readonly"])
        client = BetaAnalyticsDataClient(credentials=creds)
        client.run_report(RunReportRequest(
            property=f"properties/{prop}",
            metrics=[Metric(name="activeUsers")],
            date_ranges=[DateRange(start_date="7daysAgo", end_date="yesterday")],
            limit=1))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": _friendly("ga4", e)}


def _check_sc(url: str) -> dict:
    if not url:
        return {"ok": False, "error": "Sin URL de Search Console"}
    try:
        from googleapiclient.discovery import build
        creds = Credentials.from_service_account_file(
            _creds_path(), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        svc = build("webmasters", "v3", credentials=creds, cache_discovery=False)
        day = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        svc.searchanalytics().query(
            siteUrl=url, body={"startDate": day, "endDate": day, "rowLimit": 1}).execute()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": _friendly("sc", e)}


def check_client(client: str, reload: bool = True) -> dict:
    cfg = client_config(client, reload)
    entry = {
        "ga4": _check_ga4(cfg["ga4"]),
        "sc": _check_sc(cfg["sc"]),
        "checked": datetime.now().isoformat(timespec="seconds"),
        "ga4_id": cfg["ga4"],
        "sc_url": cfg["sc"],
    }
    if cfg.get("ads"):  # opcional: solo si el cliente tiene Customer ID de Google Ads
        import extract_google_ads as eg
        entry["ads"] = eg.check_access(cfg["ads"])
    return entry


# ── Estado persistido ────────────────────────────────────────

def load_status() -> dict:
    try:
        with open(STATUS_PATH, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_status(data: dict) -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    tmp = f"{STATUS_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, STATUS_PATH)


def check_and_store(clients: list, progress=None, workers: int = 8) -> dict:
    """Comprueba varios clientes en paralelo y persiste el resultado.
    `progress(done, total, client)` se llama desde el hilo principal."""
    results = {}
    _env()  # una sola recarga del .env; los hilos leen os.environ
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {c: pool.submit(check_client, c, False) for c in clients}
        for i, (c, fut) in enumerate(futures.items(), 1):
            try:
                results[c] = fut.result()
            except Exception as e:
                results[c] = {"ga4": {"ok": False, "error": str(e)[:120]},
                              "sc": {"ok": False, "error": str(e)[:120]},
                              "checked": datetime.now().isoformat(timespec="seconds")}
            if progress:
                progress(i, len(futures), c)
    status = load_status()
    status.update(results)
    _save_status(status)
    return results


def forget_client(client: str) -> None:
    status = load_status()
    if status.pop(client, None) is not None:
        _save_status(status)


def state_of(entry) -> str:
    """'ok' | 'error' | 'unknown' para una entrada del estado."""
    if not entry:
        return "unknown"
    return "ok" if entry["ga4"]["ok"] and entry["sc"]["ok"] else "error"


def error_text(entry) -> str:
    if not entry:
        return ""
    parts = []
    if not entry["ga4"]["ok"]:
        parts.append(f"GA4: {entry['ga4'].get('error', 'error')}")
    if not entry["sc"]["ok"]:
        parts.append(f"Search Console: {entry['sc'].get('error', 'error')}")
    return " · ".join(parts)


def ads_error_text(entry) -> str:
    ads = (entry or {}).get("ads")
    return f"Google Ads: {ads.get('error', 'error')}" if ads and not ads["ok"] else ""


def age_label(entry) -> str:
    if not entry or not entry.get("checked"):
        return "sin verificar"
    secs = (datetime.now() - datetime.fromisoformat(entry["checked"])).total_seconds()
    if secs < 90:
        return "ahora"
    if secs < 3600:
        return f"hace {int(secs // 60)} min"
    if secs < 86400:
        return f"hace {int(secs // 3600)} h"
    return f"hace {int(secs // 86400)} d"


# ── Datos sospechosos antes de generar ───────────────────────

def sanity_check(client: str, month: int, year: int) -> list:
    """Devuelve [(nivel, texto)] con nivel 'error' | 'warn' | 'info'. Lista vacía = todo normal.
    Usa los extractores (con caché), así que los datos quedan listos para el informe."""
    from extract_ga4 import extract_ga4_data
    from extract_search_console import extract_search_console_data

    cfg = client_config(client, reload=False)
    issues = []
    try:
        ga4 = extract_ga4_data(cfg["ga4"], month, year) or {}
    except Exception as e:
        return [("error", f"GA4: {_friendly('ga4', e)}")]
    try:
        sc = extract_search_console_data(cfg["sc"], month, year) or {}
    except Exception as e:
        return [("error", f"Search Console: {_friendly('sc', e)}")]

    now = datetime.now()
    if (year, month) == (now.year, now.month):
        issues.append(("info", "Mes en curso: los datos son parciales"))
    elif (year, month) > (now.year, now.month):
        return [("error", "El mes seleccionado es futuro")]

    sessions = (ga4.get("metrics") or {}).get("sessions", 0)
    imps = (sc.get("summary") or {}).get("impressions", 0)
    clicks = (sc.get("summary") or {}).get("clicks", 0)

    if sessions == 0 and imps == 0:
        issues.append(("warn", "Sin datos en GA4 ni en Search Console este mes"))
    elif sessions == 0 and clicks > 0:
        issues.append(("warn", f"GA4 sin sesiones pero Search Console tiene {clicks} clics (¿etiqueta GA4 rota?)"))
    elif imps == 0 and sessions > 0:
        issues.append(("warn", "Search Console sin impresiones (¿propiedad o URL incorrecta?)"))

    if (year, month) != (now.year, now.month):
        pm, py = prev_month(month, year)
        try:
            ga4p = extract_ga4_data(cfg["ga4"], pm, py) or {}
            scp = extract_search_console_data(cfg["sc"], pm, py) or {}
            ps = (ga4p.get("metrics") or {}).get("sessions", 0)
            pi = (scp.get("summary") or {}).get("impressions", 0)
            if pi >= 100 and imps < pi * 0.1:
                issues.append(("warn", f"Impresiones {imps} vs {pi} en {MESES.get(pm, pm)}: caída de más del 90%"))
            if ps >= 30 and sessions < ps * 0.1 and sessions > 0:
                issues.append(("warn", f"Sesiones {sessions} vs {ps} en {MESES.get(pm, pm)}: caída de más del 90%"))
        except Exception:
            pass
    return issues
