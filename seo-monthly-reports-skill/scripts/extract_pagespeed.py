#!/usr/bin/env python3
"""
Extractor de PageSpeed Insights — API gratuita (con API key opcional para mayor cuota).
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime
from utils import cache_read, cache_write

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def extract_pagespeed(url: str) -> dict:
    cache_key = f"pagespeed_{url.replace('/', '_').replace(':', '')}_{datetime.now().strftime('%Y_%m')}"
    cached = cache_read(cache_key)
    if cached:
        print(f"  ✅ PageSpeed: datos en caché")
        return cached

    print(f"  🔍 PageSpeed: analizando {url}...")
    params = f"url={urllib.parse.quote(url, safe='')}&category=performance&category=seo&category=accessibility&strategy=mobile"

    api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY", "").strip()
    if api_key:
        params += f"&key={api_key}"

    req_url = f"{API}?{params}"

    data = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(req_url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  ⏳ PageSpeed: rate limit, reintentando en {wait}s...")
                time.sleep(wait)
                continue
            print(f"  ⚠️  PageSpeed: error HTTP {e.code}")
            if not api_key:
                print(f"  💡 Consejo: añade GOOGLE_PAGESPEED_API_KEY en .env para mayor cuota (gratis en console.cloud.google.com)")
            return {}
        except Exception as e:
            print(f"  ⚠️  PageSpeed: error — {e}")
            return {}

    if not data:
        return {}

    cats = data.get("lighthouseResult", {}).get("categories", {})
    audits = data.get("lighthouseResult", {}).get("audits", {})

    result = {
        "performance": int((cats.get("performance", {}).get("score") or 0) * 100),
        "seo": int((cats.get("seo", {}).get("score") or 0) * 100),
        "accessibility": int((cats.get("accessibility", {}).get("score") or 0) * 100),
        "fcp": audits.get("first-contentful-paint", {}).get("displayValue", "—"),
        "lcp": audits.get("largest-contentful-paint", {}).get("displayValue", "—"),
        "cls": audits.get("cumulative-layout-shift", {}).get("displayValue", "—"),
        "tbt": audits.get("total-blocking-time", {}).get("displayValue", "—"),
    }

    cache_write(cache_key, result)
    print(f"  ✅ PageSpeed: Performance={result['performance']}, SEO={result['seo']}, Accessibility={result['accessibility']}")
    return result


# ── CrUX: velocidad real de los usuarios (Chrome UX Report, gratis con la misma clave) ──
CRUX_API = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"
# Umbrales «bueno» de Google para p75
CRUX_GOOD = {"largest_contentful_paint": 2500, "interaction_to_next_paint": 200, "cumulative_layout_shift": 0.1}


def extract_crux(url: str) -> dict:
    """p75 en móvil de LCP, INP y CLS: hace ~6 meses y ahora. {} si no hay clave, la API no
    está activada o la web tiene poco tráfico de Chrome (CrUX no publica datos)."""
    api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY", "").strip()
    if not api_key:
        return {}
    origin = "://".join(urllib.parse.urlparse(url.replace("sc-domain:", "https://"))[:2])
    cache_key = f"crux_{origin.replace('/', '_').replace(':', '')}_{datetime.now().strftime('%Y_%m')}"
    cached = cache_read(cache_key)
    if cached is not None:
        return cached
    scheme, host = origin.split("://", 1)
    alt = f"{scheme}://{host[4:]}" if host.startswith("www.") else f"{scheme}://www.{host}"
    rec = None
    for o in (origin, alt):
        body = json.dumps({"origin": o, "formFactor": "PHONE", "metrics": list(CRUX_GOOD)}).encode()
        req = urllib.request.Request(f"{CRUX_API}?key={api_key}", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                rec = json.loads(resp.read()).get("record", {})
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:   # sin datos para este origen: se prueba la otra variante
                continue
            print(f"  ⚠️  CrUX: error HTTP {e.code} (¿API «Chrome UX Report» activada en Google Cloud?)")
            return {}
        except Exception as e:
            print(f"  ⚠️  CrUX: {e}")
            return {}
    if rec is None:   # ninguna variante tiene datos: se guarda para no repetir la consulta este mes
        cache_write(cache_key, {})
        return {}

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    periods = rec.get("collectionPeriods", [])
    out = {"metrics": {}}
    for m, good in CRUX_GOOD.items():
        p75 = [_num(v) for v in rec.get("metrics", {}).get(m, {}).get("percentilesTimeseries", {}).get("p75s", [])]
        vals = [v for v in p75 if v is not None]
        if len(vals) < 2:
            continue
        before = next((v for v in p75[-26:] if v is not None), vals[0])   # ~6 meses (periodos semanales)
        out["metrics"][m] = {"before": before, "now": vals[-1], "good": vals[-1] <= good}
    if periods:
        last = periods[-1].get("lastDate", {})
        out["last_date"] = f"{last.get('day', 1):02d}/{last.get('month', 1):02d}/{last.get('year', '')}"
    out = out if out["metrics"] else {}
    cache_write(cache_key, out)
    return out
