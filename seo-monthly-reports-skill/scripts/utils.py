#!/usr/bin/env python3
import os, json, hashlib
from datetime import datetime

MESES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
}

_CACHE_DIR = os.path.expanduser("~/.cache/seo-reports")
_TTL_HOURS = 24
_TTL_CLOSED_MONTH_HOURS = 24 * 30


def prev_month(month: int, year: int) -> tuple[int, int]:
    """Devuelve (mes, año) del mes anterior."""
    return (12, year - 1) if month == 1 else (month - 1, year)


def month_ttl_hours(month: int, year: int) -> int:
    """TTL de caché para un mes: los meses cerrados (con margen de 3 días para que
    Google consolide datos) ya no cambian, así que se cachean mucho más tiempo."""
    from datetime import timedelta
    nm, ny = (1, year + 1) if month == 12 else (month + 1, year)
    closed_at = datetime(ny, nm, 1) + timedelta(days=3)
    return _TTL_CLOSED_MONTH_HOURS if datetime.now() >= closed_at else _TTL_HOURS


def pct_delta(current: float, previous: float) -> str:
    """Formatea la variación vs mes anterior: '▲ +12%' / '▼ -5%' / '—'."""
    if not previous:
        return "—"
    diff = (current - previous) / previous * 100
    if abs(diff) < 0.5:
        return "≈ 0%"
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {diff:+.0f}%"


def get_output_dir() -> str:
    path = os.path.expanduser(os.getenv("OUTPUT_DIR", "~/Desktop"))
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path(key: str) -> str:
    safe = hashlib.md5(key.encode()).hexdigest()
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{safe}.json")


def cache_read(key: str, ttl_hours: int | None = None) -> dict | None:
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    age_h = (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
    if age_h > (ttl_hours or _TTL_HOURS):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (ValueError, OSError):
        # Fichero corrupto (p. ej. proceso interrumpido a mitad de escritura)
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def cache_write(key: str, data: dict) -> None:
    path = _cache_path(key)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


# ── Uso de la API de Gemini (free tier: 20 req/día) ──────────
GEMINI_DAILY_LIMIT = 20
_GEMINI_USAGE = os.path.join(_CACHE_DIR, "gemini_usage.json")


def gemini_usage() -> int:
    """Llamadas a Gemini realizadas hoy (resetea al cambiar de día)."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(_GEMINI_USAGE, "r") as f:
            data = json.load(f)
        return data.get("count", 0) if data.get("date") == today else 0
    except Exception:
        return 0


def _gemini_write(count: int):
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_GEMINI_USAGE, "w") as f:
            json.dump({"date": today, "count": count}, f)
    except Exception:
        pass


def gemini_bump() -> int:
    """Suma una llamada al contador diario y devuelve el total de hoy."""
    count = gemini_usage() + 1
    _gemini_write(count)
    return count


def gemini_mark_exhausted():
    """Marca la cuota como agotada hoy (al recibir un 429 de Google)."""
    _gemini_write(GEMINI_DAILY_LIMIT)
