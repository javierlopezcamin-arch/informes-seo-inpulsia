#!/usr/bin/env python3
"""
Qué etiquetas de medición hay instaladas en la web (lectura pública del HTML).

Detecta GA4 (G-), Google Ads (AW-), Google Tag Manager (GTM-), gestor de cookies /
Consent Mode y tipo de formulario. Si hay GTM, descarga el contenedor público
(gtm.js) para ver los IDs de GA4/Ads que carga dentro.
"""

import re

import requests

from utils import cache_read, cache_write

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) InpulsiaSEOReports/1.0"}
TIMEOUT = 15

CONSENT = {
    "Complianz": r"complianz|cmplz",
    "Cookiebot": r"cookiebot",
    "CookieYes": r"cookieyes|cky-consent",
    "Iubenda": r"iubenda",
    "Borlabs": r"borlabs",
    "OneTrust": r"onetrust|optanon",
}
FORMS = {
    "Elementor Forms": r"elementor-form",
    "Contact Form 7": r"wpcf7",
    "WPForms": r"wpforms",
    "Gravity Forms": r"gform_wrapper",
    "Fluent Forms": r"fluentform",
}


def _ids(text: str) -> dict:
    return {
        "ga4": sorted(set(re.findall(r"\bG-[A-Z0-9]{6,12}\b", text))),
        "ads": sorted(set(re.findall(r"\bAW-\d{6,12}\b", text))),
        "gtm": sorted(set(re.findall(r"\bGTM-[A-Z0-9]{4,10}\b", text))),
    }


def _scan(url: str) -> dict:
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    text = r.text
    low = text.lower()
    out = _ids(text)
    out["consent_tool"] = [k for k, pat in CONSENT.items() if re.search(pat, low)]
    out["consent_mode"] = bool(re.search(r"""['"]consent['"]\s*,\s*['"]default['"]""", text))
    out["forms"] = [k for k, pat in FORMS.items() if re.search(pat, low)]
    out["phone_links"] = len(set(re.findall(r'href=["\']tel:([^"\']+)', text)))
    out["site_kit"] = "google site kit" in low or "googlesitekit" in low
    return out


def check_tracking(base: str, landing_urls: list = None) -> dict:
    """Escanea la home y hasta 2 landings de Ads. Devuelve un resumen combinado."""
    urls = [base.rstrip("/") + "/"] + [u for u in (landing_urls or []) if u][:2]
    cache_key = f"tracking_{'|'.join(urls)}_v1"
    cached = cache_read(cache_key)
    if cached:
        print("  ⚡ Etiquetas: desde caché")
        return cached

    res = {"pages": {}, "ga4": [], "ads": [], "gtm": [], "gtm_contains": {"ga4": [], "ads": []},
           "consent_tool": [], "consent_mode": False, "forms": [], "phone_links": 0, "site_kit": False}
    for u in dict.fromkeys(urls):
        try:
            s = _scan(u)
        except Exception as e:
            res["pages"][u] = {"error": f"{type(e).__name__}"}
            continue
        res["pages"][u] = {"forms": s["forms"], "phone_links": s["phone_links"]}
        for k in ("ga4", "ads", "gtm", "consent_tool", "forms"):
            res[k] = sorted(set(res[k]) | set(s[k]))
        res["consent_mode"] |= s["consent_mode"]
        res["site_kit"] |= s["site_kit"]
        res["phone_links"] = max(res["phone_links"], s["phone_links"])

    for gtm in res["gtm"][:2]:
        try:
            r = requests.get("https://www.googletagmanager.com/gtm.js", params={"id": gtm}, headers=UA, timeout=TIMEOUT)
            if r.ok:
                ids = _ids(r.text)
                res["gtm_contains"]["ga4"] = sorted(set(res["gtm_contains"]["ga4"]) | set(ids["ga4"]))
                res["gtm_contains"]["ads"] = sorted(set(res["gtm_contains"]["ads"]) | set(ids["ads"]))
                # Consent Mode configurado dentro de GTM
                res["consent_mode"] |= "consent" in r.text and "ad_storage" in r.text
        except Exception:
            pass

    ok_pages = [p for p in res["pages"].values() if "error" not in p]
    if ok_pages:
        ga4 = sorted(set(res['ga4']) | set(res['gtm_contains']['ga4']))
        ads = sorted(set(res['ads']) | set(res['gtm_contains']['ads']))
        print(f"  ✅ Etiquetas: GA4 {', '.join(ga4) or '—'} · Ads {', '.join(ads) or '—'} · "
              f"GTM {', '.join(res['gtm']) or '—'}")
        cache_write(cache_key, res)
    else:
        print("  ⚠️  Etiquetas: no se pudo leer la web")
    return res


if __name__ == "__main__":
    import sys, json
    print(json.dumps(check_tracking(sys.argv[1] if len(sys.argv) > 1 else "https://inpulsia.es"), indent=1))
