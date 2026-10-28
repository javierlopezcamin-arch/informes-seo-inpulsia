#!/usr/bin/env python3
"""
Contenido publicado en la web del cliente (posts y páginas), sin credenciales.

1. REST pública de WordPress (/wp-json/wp/v2/posts y /pages)
2. Si está cerrada: sitemaps (Yoast / Rank Math / WordPress nativo)

Sirve para no proponer posts que ya existen y para sugerir enlaces internos reales.
"""

import html
import re
from urllib.parse import urlparse

import requests

from utils import cache_read, cache_write

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) InpulsiaSEOReports/1.0"}
TIMEOUT = 15


def site_base(sc_url: str) -> str:
    """'sc-domain:ejemplo.com' o 'https://ejemplo.com/' → 'https://ejemplo.com'"""
    if sc_url.startswith("sc-domain:"):
        return "https://" + sc_url.split(":", 1)[1].strip().strip("/")
    p = urlparse(sc_url)
    return f"{p.scheme or 'https'}://{p.netloc}"


def _rest(base: str, kind: str, max_pages: int = 3) -> list:
    items = []
    for page in range(1, max_pages + 1):
        r = requests.get(f"{base}/wp-json/wp/v2/{kind}",
                         params={"per_page": 100, "page": page, "_fields": "title,link,date"},
                         headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            if page == 1:
                raise RuntimeError(f"REST {kind}: HTTP {r.status_code}")
            break
        batch = r.json()
        if not isinstance(batch, list):
            raise RuntimeError(f"REST {kind}: respuesta inesperada")
        items += [{"title": html.unescape(re.sub(r"<[^>]+>", "", (i.get("title") or {}).get("rendered", ""))).strip(),
                   "url": i.get("link", ""), "date": (i.get("date") or "")[:10]} for i in batch]
        if len(batch) < 100 or page >= int(r.headers.get("X-WP-TotalPages", page)):
            break
    return items


def _title_from_url(url: str) -> str:
    slug = urlparse(url).path.strip("/").split("/")[-1] if urlparse(url).path.strip("/") else ""
    return slug.replace("-", " ").capitalize() if slug else "Inicio"


def _sitemap_urls(url: str) -> list:
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200 or "<" not in r.text[:200]:
        return []
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)


def _sitemaps(base: str) -> dict:
    candidates = {
        "posts": ["/post-sitemap.xml", "/wp-sitemap-posts-post-1.xml"],
        "pages": ["/page-sitemap.xml", "/wp-sitemap-posts-page-1.xml"],
    }
    out = {"posts": [], "pages": []}
    for kind, paths in candidates.items():
        for path in paths:
            urls = _sitemap_urls(base + path)
            if urls:
                out[kind] = [{"title": _title_from_url(u), "url": u, "date": ""} for u in urls]
                break
    return out


def extract_wp_content(sc_url: str) -> dict:
    """{'base', 'source': 'rest'|'sitemap'|'', 'posts': [...], 'pages': [...], 'error'?}"""
    base = site_base(sc_url)
    cache_key = f"wp_content_{base}_v1"
    cached = cache_read(cache_key)
    if cached:
        print("  ⚡ Web: contenido desde caché")
        return cached

    data = {"base": base, "source": "", "posts": [], "pages": []}
    try:
        data["posts"] = _rest(base, "posts")
        try:
            data["pages"] = _rest(base, "pages")
        except Exception:
            pass
        data["source"] = "rest"
    except Exception as e:
        try:
            sm = _sitemaps(base)
            if sm["posts"] or sm["pages"]:
                data.update(sm, source="sitemap")
            else:
                data["error"] = f"Sin REST ni sitemap legible ({e})"
        except Exception as e2:
            data["error"] = f"{type(e2).__name__}: {e2}"[:140]

    if data["source"]:
        print(f"  ✅ Web: {len(data['posts'])} posts y {len(data['pages'])} páginas ({data['source']})")
        cache_write(cache_key, data)
    else:
        print(f"  ⚠️  Web: no se pudo leer el contenido — {data.get('error')}")
    return data


if __name__ == "__main__":
    import sys
    d = extract_wp_content(sys.argv[1] if len(sys.argv) > 1 else "https://inpulsia.es/")
    print(d["source"], len(d["posts"]), len(d["pages"]), d["posts"][:3])
