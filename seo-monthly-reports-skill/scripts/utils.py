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


_ENV_BACKUPS = 10


def write_env(path: str, content: str) -> None:
    """Reescribe el .env de forma segura: copia de la versión actual en
    ~/.cache/seo-reports/env_backups (se guardan las últimas 10) y escritura atómica,
    para que un fallo a mitad no deje el archivo cortado."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        if content.count("\n") < old.count("\n") * 0.5:
            raise ValueError("El .env nuevo perdería más de la mitad de sus líneas: no se guarda")
        if old != content:
            bdir = os.path.join(_CACHE_DIR, "env_backups")
            os.makedirs(bdir, exist_ok=True)
            bpath = os.path.join(bdir, f"env_{datetime.now():%Y%m%d_%H%M%S_%f}.bak")
            fd = os.open(bpath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(old)
            for old_b in sorted(os.listdir(bdir))[:-_ENV_BACKUPS]:
                os.remove(os.path.join(bdir, old_b))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


_NAME_LOWER = {"de", "del", "la", "las", "el", "los", "y", "e", "en"}


def display_name(key: str) -> str:
    """Nombre legible de un cliente a partir de su clave interna (NOMBRE_CLIENTE del .env):
    '10DECO' → '10DECO' · 'ANA_ISABEL_BONITO_PSICLOGA' → 'Ana Isabel Bonito Psicloga'.
    Las palabras con cifras se dejan en mayúsculas; los artículos y preposiciones, en minúscula."""
    words = [w for w in key.replace("-", "_").split("_") if w]
    out = []
    for i, w in enumerate(words):
        if any(ch.isdigit() for ch in w):
            out.append(w.upper())
        elif i and w.lower() in _NAME_LOWER:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out) or key


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


# ── Números en formato español: punto de miles, coma decimal ──
NBSP = " "   # entre la cifra y el % para que no se separen al partir línea


def fmt_int(v) -> str:
    """Entero con punto de miles: 1330 → '1.330'."""
    return f"{round(v or 0):,}".replace(",", ".")


def fmt_dec(v, nd: int = 1, sign: bool = False) -> str:
    """Decimal con coma y punto de miles: 1.45 → '1,45' · 12345.6 → '12.345,6'.
    sign=True añade '+' a los positivos ('+0,7')."""
    s = f"{(v or 0):{'+' if sign else ''},.{nd}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_pct(v, nd: int = 1, sign: bool = False) -> str:
    """Porcentaje: 1.45 → '1,45 %' (espacio irrompible antes del %)."""
    return f"{fmt_dec(v, nd, sign)}{NBSP}%"


def fmt_text_num(text) -> str:
    """Texto con cifras en formato inglés de una API ('4.7 s', '1,230 ms') → '4,7 s', '1.230 ms'."""
    return str(text).replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_num(v) -> str:
    """Cifra de un eje o etiqueta: entera con punto de miles, o con un decimal si lo tiene."""
    return fmt_int(v) if float(v).is_integer() else fmt_dec(v, 1)


def pct_delta(current: float, previous: float) -> str:
    """Formatea la variación vs mes anterior: '▲ +12 %' / '▼ -5 %' / '—'."""
    if not previous:
        return "—"
    diff = (current - previous) / previous * 100
    if abs(diff) < 0.5:
        return f"≈ 0{NBSP}%"
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {fmt_pct(diff, 0, sign=True)}"


def abs_delta(current: float, previous: float, nd: int = 1, unit: str = "") -> str:
    """Variación absoluta vs mes anterior, para tasas y posiciones: '▼ -3,2 pp' / '▲ +1,5 pos.'."""
    if not previous:
        return "—"
    diff = current - previous
    if abs(diff) < 0.5 * 10 ** -nd:
        return f"≈ 0{unit}"
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {fmt_dec(diff, nd, sign=True)}{unit}"


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
