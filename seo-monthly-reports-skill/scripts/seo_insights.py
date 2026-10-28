#!/usr/bin/env python3
"""
Señales SEO que cruzan fuentes, sin IA:
- Radar de contenido: páginas que pierden clics (últimos 3 meses vs los 3 anteriores).
- Cruce Search Console + GA4 por URL: páginas visibles que no convierten y
  páginas que convierten pero apenas se ven en Google.
- Tráfico desde asistentes de IA (ChatGPT, Perplexity, Gemini, Copilot, Claude…).

Siempre con datos reales de la API (el ajuste de datos del informe no se aplica aquí).
"""

import calendar
import hashlib
import os
import re
from urllib.parse import urlparse

from utils import cache_read, cache_write, month_ttl_hours, prev_month, MESES

AI_SOURCES = [
    ("chatgpt", "ChatGPT"), ("openai", "ChatGPT"), ("perplexity", "Perplexity"),
    ("gemini", "Gemini"), ("bard", "Gemini"), ("copilot", "Copilot"), ("bing.com/chat", "Copilot"),
    ("claude", "Claude"), ("deepseek", "DeepSeek"), ("meta.ai", "Meta AI"), ("grok", "Grok"),
    ("mistral", "Mistral"), ("you.com", "You.com"),
]
AI_REGEX = "|".join(re.escape(k) for k, _ in AI_SOURCES)


def _creds():
    return os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))


def _key(url: str) -> str:
    """Ruta normalizada para cruzar URLs de Search Console (absolutas) con landings de GA4 (rutas)."""
    path = urlparse(url if "://" in url else "https://x" + url).path.lower().rstrip("/")
    return path or "/"


def _shift(month: int, year: int, n: int) -> tuple:
    for _ in range(n):
        month, year = prev_month(month, year)
    return month, year


def _range(m1: int, y1: int, m2: int, y2: int) -> tuple:
    return f"{y1}-{m1:02d}-01", f"{y2}-{m2:02d}-{calendar.monthrange(y2, m2)[1]:02d}"


def _label(m1, y1, m2, y2) -> str:
    a, b = MESES.get(m1, m1)[:3], MESES.get(m2, m2)[:3]
    return f"{a}–{b} {y2}" if y1 == y2 else f"{a} {y1}–{b} {y2}"


# ── Search Console ────────────────────────────────────────────
def _sc_pages(site_url: str, start: str, end: str, limit: int = 1000) -> list:
    from extract_search_console import SearchConsoleExtractor
    ext = SearchConsoleExtractor(_creds(), site_url)
    rows = ext.service.searchanalytics().query(siteUrl=site_url, body={
        'startDate': start, 'endDate': end, 'dimensions': ['page'], 'rowLimit': limit,
    }).execute().get('rows', [])
    return [{'page': r['keys'][0], 'clicks': int(r.get('clicks', 0)),
             'impressions': int(r.get('impressions', 0)),
             'position': round(float(r.get('position', 0)), 1)} for r in rows]


def _by_page(rows: list) -> dict:
    """Agrupa por ruta (http/https, con o sin barra final): suma clics e impresiones y
    pondera la posición por impresiones."""
    out = {}
    for r in rows:
        a = out.setdefault(_key(r['page']), {'page': r['page'], 'clicks': 0, 'impressions': 0, '_pw': 0.0})
        if r['clicks'] > a['clicks']:
            a['page'] = r['page']
        a['clicks'] += r['clicks']
        a['impressions'] += r['impressions']
        a['_pw'] += r['position'] * r['impressions']
    for a in out.values():
        a['position'] = round(a.pop('_pw') / a['impressions'], 1) if a['impressions'] else 0
    return out


def content_decay(site_url: str, month: int, year: int) -> dict:
    """Páginas con caída de clics: últimos 3 meses (hasta `month`) frente a los 3 anteriores."""
    tag = hashlib.md5(site_url.encode()).hexdigest()[:8]
    cache_key = f"decay_{tag}_{year}_{month:02d}_v2"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        return cached

    cm1, cy1 = _shift(month, year, 2)
    pm2, py2 = _shift(month, year, 3)
    pm1, py1 = _shift(month, year, 5)
    now = _by_page(_sc_pages(site_url, *_range(cm1, cy1, month, year)))
    before = _by_page(_sc_pages(site_url, *_range(pm1, py1, pm2, py2)))

    pages = []
    for k, b in before.items():
        n = now.get(k, {'clicks': 0, 'impressions': 0, 'position': 0})
        lost = b['clicks'] - n['clicks']
        if b['clicks'] >= 15 and lost >= 8 and lost / b['clicks'] >= 0.3:
            pages.append({'page': b['page'], 'clicks_before': b['clicks'], 'clicks_now': n['clicks'],
                          'lost': lost, 'pct': round(-lost / b['clicks'] * 100),
                          'pos_before': b['position'], 'pos_now': n['position'] or None})
    pages.sort(key=lambda p: -p['lost'])
    data = {'pages': pages[:10],
            'window': f"{_label(cm1, cy1, month, year)} frente a {_label(pm1, py1, pm2, py2)}"}
    cache_write(cache_key, data)
    return data


# ── GA4 ───────────────────────────────────────────────────────
def _ga4_rows(property_id: str, month: int, year: int, dimension: str, channel: str = "",
              source_regex: str = "", limit: int = 200) -> list:
    from extract_ga4 import GA4Extractor
    from google.analytics.data_v1beta.types import (RunReportRequest, Dimension, Metric, DateRange,
                                                    OrderBy, Filter, FilterExpression)
    ext = GA4Extractor(_creds(), property_id)
    start, end = ext._date_range(month, year)
    if channel:
        flt = FilterExpression(filter=Filter(field_name="sessionDefaultChannelGroup",
                                             string_filter=Filter.StringFilter(value=channel)))
    else:
        flt = FilterExpression(filter=Filter(field_name="sessionSource", string_filter=Filter.StringFilter(
            value=f".*({source_regex}).*", match_type=Filter.StringFilter.MatchType.FULL_REGEXP,
            case_sensitive=False)))
    req = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name=dimension)],
        metrics=[Metric(name="sessions"), Metric(name="keyEvents"), Metric(name="engagementRate")],
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimension_filter=flt, limit=limit,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    )
    return [{'key': r.dimension_values[0].value, 'sessions': int(r.metric_values[0].value),
             'key_events': round(float(r.metric_values[1].value), 1),
             'engagement': round(float(r.metric_values[2].value) * 100, 1)}
            for r in ext.client.run_report(req).rows]


def ai_traffic(property_id: str, month: int, year: int) -> dict:
    """Sesiones que llegan desde asistentes de IA, agrupadas por asistente, con el mes anterior."""
    def one(m, y):
        cache_key = f"ga4_ai_{property_id}_{y}_{m:02d}_v1"
        cached = cache_read(cache_key, month_ttl_hours(m, y))
        if cached:
            return cached
        by = {}
        for r in _ga4_rows(property_id, m, y, "sessionSource", source_regex=AI_REGEX, limit=50):
            label = next((lbl for k, lbl in AI_SOURCES if k in r['key'].lower()), r['key'])
            a = by.setdefault(label, {'assistant': label, 'sessions': 0, 'key_events': 0})
            a['sessions'] += r['sessions']
            a['key_events'] += r['key_events']
        data = {'sources': sorted(by.values(), key=lambda a: -a['sessions'])}
        data['sessions'] = sum(a['sessions'] for a in data['sources'])
        data['key_events'] = round(sum(a['key_events'] for a in data['sources']), 1)
        cache_write(cache_key, data)
        return data

    cur = one(month, year)
    pm, py = prev_month(month, year)
    try:
        prev = one(pm, py)
    except Exception as e:
        print(f"  ⚠️  Tráfico IA mes anterior: {type(e).__name__} — sin comparativa")
        prev = {}
    return {**cur, 'prev_sessions': prev.get('sessions')}


def organic_landings(property_id: str, site_url: str, month: int, year: int) -> dict:
    """Cruce por URL de Search Console (visibilidad) y GA4 Organic Search (conversión)."""
    tag = hashlib.md5(site_url.encode()).hexdigest()[:8]
    cache_key = f"landings_{property_id}_{tag}_{year}_{month:02d}_v2"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        return cached

    ga = {}
    for r in _ga4_rows(property_id, month, year, "landingPage", channel="Organic Search"):
        k = _key(r['key'].split("?")[0])
        a = ga.setdefault(k, {'sessions': 0, 'key_events': 0, 'engagement': r['engagement']})
        a['sessions'] += r['sessions']
        a['key_events'] += r['key_events']
    sc = _by_page(_sc_pages(site_url, *_range(month, year, month, year), limit=500))

    measured = sum(a['key_events'] for a in ga.values()) > 0
    rows = [{'page': s['page'], 'clicks': s['clicks'], 'impressions': s['impressions'], 'position': s['position'],
             'sessions': ga.get(k, {}).get('sessions', 0), 'key_events': ga.get(k, {}).get('key_events', 0),
             'engagement': ga.get(k, {}).get('engagement')} for k, s in sc.items()]
    visible_no_conv = sorted([r for r in rows if measured and r['clicks'] >= 20 and r['sessions'] >= 20
                              and r['key_events'] == 0], key=lambda r: -r['clicks'])[:8]
    conv_low_vis = sorted([r for r in rows if r['key_events'] >= 1 and r['position'] > 10],
                          key=lambda r: -r['key_events'])[:8]
    data = {'measured': measured, 'visible_no_conv': visible_no_conv, 'conv_low_vis': conv_low_vis}
    cache_write(cache_key, data)
    return data


def build_insights(property_id: str, site_url: str, month: int, year: int) -> dict:
    """Las tres señales; cada una es opcional y un fallo solo deja un aviso."""
    out = {}
    for name, fn in (("decay", lambda: content_decay(site_url, month, year)),
                     ("landings", lambda: organic_landings(property_id, site_url, month, year)),
                     ("ai", lambda: ai_traffic(property_id, month, year))):
        try:
            out[name] = fn()
        except Exception as e:
            print(f"  ⚠️  Señales SEO ({name}): {type(e).__name__}: {str(e)[:120]} — se omite")
    return out
