#!/usr/bin/env python3
"""
Seguimiento de keywords en Search Console, mes a mes (6 meses):
- Búsquedas que dominamos: consultas en el top 3 (y en el top 10).
- Páginas que aparecen en Google: URLs con impresiones en el mes.
- Keywords objetivo del cliente (KEYWORDS_OBJETIVO_<CLIENTE> en el .env, separadas por comas):
  posición, clics e impresiones de cada una aunque no esté entre las búsquedas principales.
"""

import hashlib
import os
import re
from utils import cache_read, cache_write, month_ttl_hours, prev_month, MESES

TOP3_MIN_IMPRESSIONS = 5   # sin ruido: una búsqueda con 1 impresión en posición 2 no es «dominar»
ROWS = 5000


def target_keywords_for(client: str) -> list:
    """Palabras clave principales de Rank Math; si la web no está conectada, KEYWORDS_OBJETIVO_<C>."""
    from extract_rankmath import rankmath_configured, focus_keywords
    if rankmath_configured(client):
        kws = focus_keywords(client)
        if kws:
            return kws
    raw = os.getenv(f"KEYWORDS_OBJETIVO_{client.upper()}", "")
    seen, out = set(), []
    for k in raw.split(","):
        k = " ".join(k.strip().lower().split())
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:60]


def _month(ext, site_url: str, month: int, year: int, targets: list) -> dict:
    key = (f"kwtrack_{hashlib.md5(site_url.encode()).hexdigest()[:8]}_{year}_{month:02d}_"
           f"{hashlib.md5('|'.join(targets).encode()).hexdigest()[:6]}_v1")
    cached = cache_read(key, month_ttl_hours(month, year))
    if cached:
        return cached
    start, end = ext._date_range(month, year)

    def q(body):
        body = {'startDate': start, 'endDate': end, **body}
        return ext.service.searchanalytics().query(siteUrl=site_url, body=body).execute().get('rows', [])

    queries = q({'dimensions': ['query'], 'rowLimit': ROWS})
    top3 = sorted(({'query': r['keys'][0], 'position': round(r['position'], 1),
                    'clicks': int(r.get('clicks', 0)), 'impressions': int(r.get('impressions', 0))}
                   for r in queries if r['position'] <= 3 and r.get('impressions', 0) >= TOP3_MIN_IMPRESSIONS),
                  key=lambda k: (-k['clicks'], -k['impressions']))
    top10 = sum(1 for r in queries if r['position'] <= 10 and r.get('impressions', 0) >= TOP3_MIN_IMPRESSIONS)
    pages = q({'dimensions': ['page'], 'rowLimit': ROWS})

    tgt = {}
    if targets:
        rx = "^(" + "|".join(re.escape(t) for t in targets) + ")$"
        rows = q({'dimensions': ['query'], 'rowLimit': 100, 'dimensionFilterGroups': [{'filters': [
            {'dimension': 'query', 'operator': 'includingRegex', 'expression': rx}]}]})
        for r in rows:
            k = r['keys'][0].lower()
            tgt[k] = {'position': round(r['position'], 1), 'clicks': int(r.get('clicks', 0)),
                      'impressions': int(r.get('impressions', 0))}

    data = {'month': month, 'year': year, 'label': f"{MESES.get(month, month)[:3]} {year}",
            'top3_count': len(top3), 'top3': top3[:10], 'top10_count': top10,
            'pages_count': sum(1 for r in pages if r.get('impressions', 0) > 0), 'targets': tgt}
    cache_write(key, data)
    return data


def extract_keyword_tracking(site_url: str, month: int, year: int, targets: list = None, months: int = 6) -> dict:
    """Devuelve {'months': [del más antiguo al actual], 'targets': [...]}; {} si falla."""
    from extract_search_console import SearchConsoleExtractor
    creds = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
    if not creds or not os.path.exists(creds):
        return {}
    targets = targets or []
    ext = SearchConsoleExtractor(creds, site_url)
    hist, m, y = [], month, year
    for _ in range(months):
        hist.append(_month(ext, site_url, m, y, targets))
        m, y = prev_month(m, y)
    hist.reverse()
    return {'months': hist, 'targets': targets}
