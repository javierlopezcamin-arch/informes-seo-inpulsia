#!/usr/bin/env python3
"""
Puntuaciones de Rank Math desde la API de WordPress (Abilities API, solo lectura).

Configuración por cliente en el .env:
  WP_USER_<CLIENTE>=usuario de WordPress
  WP_APP_PASSWORD_<CLIENTE>=contraseña de aplicación (Usuarios → Perfil → Contraseñas de aplicación)
  WP_URL_<CLIENTE>=https://web.com   (opcional; por defecto, la URL de Search Console)

Rank Math solo da la foto de hoy, así que cada mes se guarda en datos/rankmath/<cliente>.json
para mostrar la evolución.
"""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos", "rankmath")
API = "/wp-json/wp-abilities/v1/abilities/{name}/run"


def rankmath_configured(client: str) -> bool:
    c = client.upper()
    return bool(os.getenv(f"WP_USER_{c}", "").strip() and os.getenv(f"WP_APP_PASSWORD_{c}", "").strip())


def _site_url(client: str) -> str:
    c = client.upper()
    url = os.getenv(f"WP_URL_{c}", "").strip() or os.getenv(f"SEARCH_CONSOLE_URL_{c}", "").strip()
    if url.startswith("sc-domain:"):
        url = "https://" + url.split(":", 1)[1]
    return url.rstrip("/")


def _run(client: str, name: str, inp: dict, timeout: int = 60):
    c = client.upper()
    token = base64.b64encode(f"{os.getenv(f'WP_USER_{c}').strip()}:"
                             f"{os.getenv(f'WP_APP_PASSWORD_{c}').strip()}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Accept": "application/json", "User-Agent": "seo-reports"}
    base = _site_url(client) + API.format(name=name)
    # Las habilidades de solo lectura se ejecutan con GET (input en la URL); si el sitio pide POST, se reintenta.
    qs = urllib.parse.urlencode({f"input[{k}]": (str(v).lower() if isinstance(v, bool) else v) for k, v in inp.items()})
    try:
        req = urllib.request.Request(f"{base}?{qs}" if qs else base, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code != 405:
            raise
    req = urllib.request.Request(base, data=json.dumps({"input": inp}).encode(), method="POST",
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _history_path(client: str) -> str:
    return os.path.join(_BASE, f"{client.lower()}.json")


def load_history(client: str) -> dict:
    try:
        with open(_history_path(client)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_history(client: str, hist: dict):
    os.makedirs(_BASE, exist_ok=True)
    with open(_history_path(client), "w") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1, sort_keys=True)


def extract_rankmath(client: str, month: int, year: int) -> dict:
    """{'now': foto del mes, 'prev': foto guardada anterior o None}. {} si no está configurado o falla."""
    if not rankmath_configured(client):
        return {}
    key = f"{year}-{month:02d}"
    hist = load_history(client)
    snap = {}
    try:
        posts = {}
        for flt in ("great", "good", "bad"):
            for p in _run(client, "rank-math/get-seo-scores", {"seo_filter": flt, "number_of_posts": 100}) or []:
                if isinstance(p, dict) and p.get("score") is not None:
                    posts[p.get("post_id")] = p["score"]
        scores = list(posts.values())
        if scores:
            snap.update({"posts_scored": len(scores), "avg_score": round(sum(scores) / len(scores)),
                         "posts_green": sum(1 for s in scores if s > 80)})
    except Exception as e:
        print(f"  ⚠️  Rank Math (puntuaciones): {type(e).__name__}: {str(e)[:120]}")
    try:
        audit = _run(client, "rank-math/audit-site-seo", {"refresh": True}, timeout=120) or {}
        if isinstance(audit, dict) and audit.get("score") is not None:
            st = audit.get("statuses") or {}
            snap.update({"site_score": audit["score"], "tests_ok": st.get("ok", 0),
                         "tests_total": audit.get("total_tests", 0)})
    except Exception as e:
        print(f"  ⚠️  Rank Math (auditoría): {type(e).__name__}: {str(e)[:120]}")

    if snap:
        hist[key] = snap
        _save_history(client, hist)
    elif key in hist:   # sin conexión este mes, pero ya se guardó antes
        snap = hist[key]
    else:
        return {}
    earlier = sorted(k for k in hist if k < key)
    return {"now": snap, "prev": hist[earlier[-1]] if earlier else None,
            "prev_label": earlier[-1] if earlier else None}
