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
