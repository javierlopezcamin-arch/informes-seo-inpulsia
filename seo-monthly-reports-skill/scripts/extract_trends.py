#!/usr/bin/env python3
"""
Google Trends (opcional) con pytrends — librería no oficial.

Para hasta 5 semillas en España, últimos 12 meses:
  - mes de pico de interés de cada semilla (estacionalidad)
  - consultas relacionadas "en subida"
Google limita estas peticiones por IP (429): se cachea 7 días y, si falla,
el archivo de propuestas se genera sin este bloque.
"""

import time

from utils import cache_read, cache_write, MESES

TTL_HOURS = 24 * 7


def extract_trends(seeds: list, geo: str = "ES") -> dict:
    """{'seeds': [...], 'peaks': {kw: 'mes'}, 'rising': [{'query', 'seed', 'value'}], 'error'?}"""
    seeds = [s.strip().lower() for s in dict.fromkeys(seeds) if s and s.strip()][:5]
    if not seeds:
        return {}
    cache_key = f"trends_{geo}_{'|'.join(sorted(seeds))}_v1"
    cached = cache_read(cache_key, TTL_HOURS)
    if cached:
        print("  ⚡ Trends: desde caché")
        return cached

    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {"seeds": seeds, "error": "Falta pytrends (pip install pytrends)"}

    data = {"seeds": seeds, "peaks": {}, "rising": []}
    last_err = None
    for attempt in range(3):
        try:
            pt = TrendReq(hl="es-ES", tz=60, timeout=(5, 20))
            pt.build_payload(seeds, timeframe="today 12-m", geo=geo)
            iot = pt.interest_over_time()
            if iot is not None and not iot.empty:
                for kw in seeds:
                    if kw in iot and iot[kw].max() > 0:
                        data["peaks"][kw] = MESES.get(int(iot[kw].idxmax().month), "")
            related = pt.related_queries() or {}
            for kw, tables in related.items():
                rising = (tables or {}).get("rising")
                if rising is not None and not rising.empty:
                    for _, row in rising.head(5).iterrows():
                        data["rising"].append({"query": str(row["query"]), "seed": kw, "value": str(row["value"])})
            print(f"  ✅ Trends: {len(data['peaks'])} semillas · {len(data['rising'])} consultas en subida")
            cache_write(cache_key, data)
            return data
        except Exception as e:
            last_err = e
            if "429" in str(e):
                time.sleep(8 * (attempt + 1))
                continue
            break
    data["error"] = f"{type(last_err).__name__}: {str(last_err)[:120]}"
    print(f"  ⚠️  Trends: {data['error']}")
    return data


if __name__ == "__main__":
    import sys, json
    print(json.dumps(extract_trends(sys.argv[1:] or ["piscinas", "mantenimiento piscinas"]), indent=1, ensure_ascii=False))
