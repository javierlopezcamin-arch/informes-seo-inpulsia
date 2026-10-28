#!/usr/bin/env python3
"""
Gráficos estilo Google (GA4 / Search Console) renderizados con matplotlib.
Cada función devuelve la ruta de un PNG temporal de alta resolución, o None si falla.
"""

import os
import tempfile

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator, FuncFormatter
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# Paleta Google
G_BLUE   = "#4285F4"
G_PURPLE = "#7B1FA2"
G_GREEN  = "#34A853"
G_YELLOW = "#FBBC04"
G_RED    = "#EA4335"
G_GRAY   = "#5F6368"
BG       = "#FFFFFF"
GRID     = "#E8EAED"

from utils import fmt_int, fmt_num, fmt_pct

DONUT_COLORS = [G_BLUE, G_GREEN, G_YELLOW, G_RED, G_PURPLE, "#00ACC2", "#FF7043", "#9E9E9E"]


def _save(fig) -> str:
    path = tempfile.mktemp(suffix=".png", prefix="seochart_")
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return path


def _base_ax(ax):
    ax.set_facecolor(BG)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=G_GRAY, labelsize=12, length=0)
    _es_ticks(ax)


def _es_ticks(ax):
    """Cifras del eje Y con punto de miles y coma decimal (sin negativos: son solo margen)."""
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_num(v) if v >= 0 else ""))


def _full_month(daily: list, keys: tuple) -> list:
    """Rellena con 0 los días sin datos (GA4 omite los días sin visitas), del 1 al último
    día con datos, para que el eje no salte del 04 al 07 sin avisar."""
    import calendar
    raw = {d["date"].replace("-", ""): d for d in daily}
    first = min(raw)
    y, m = int(first[:4]), int(first[4:6])
    last = min(int(max(raw)[6:8]), calendar.monthrange(y, m)[1])
    return [raw.get(f"{y}{m:02d}{day:02d}", {"date": f"{y}{m:02d}{day:02d}", **{k: 0 for k in keys}})
            for day in range(1, last + 1)]


def gsc_performance_line(daily: list) -> str | None:
    """Línea doble clics/impresiones estilo Search Console."""
    if not HAS_MPL or len(daily) < 2:
        return None
    daily = _full_month(daily, ("clicks", "impressions"))
    days = [d["date"][-2:] for d in daily]
    clicks = [d["clicks"] for d in daily]
    imps = [d["impressions"] for d in daily]

    fig, ax1 = plt.subplots(figsize=(10.2, 3.6))
    _base_ax(ax1)

    ax1.plot(days, clicks, color=G_BLUE, linewidth=2.2, label="Clics")
    ax1.fill_between(days, clicks, alpha=0.08, color=G_BLUE)
    ax1.set_ylabel("Clics", color=G_BLUE, fontsize=13, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=G_BLUE)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))

    ax2 = ax1.twinx()
    ax2.plot(days, imps, color=G_PURPLE, linewidth=2.2, label="Impresiones")
    ax2.fill_between(days, imps, alpha=0.06, color=G_PURPLE)
    ax2.set_ylabel("Impresiones", color=G_PURPLE, fontsize=13, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=G_PURPLE, labelsize=12, length=0)
    _es_ticks(ax2)
    for spine in ("top", "left", "right", "bottom"):
        ax2.spines[spine].set_visible(False)

    # Mostrar solo ~10 etiquetas de día
    step = max(1, len(days) // 10)
    for i, lbl in enumerate(ax1.get_xticklabels()):
        lbl.set_visible(i % step == 0)

    fig.legend(loc="upper left", bbox_to_anchor=(0.07, 1.04), ncol=2,
               frameon=False, fontsize=13)
    return _save(fig)


def ga4_users_line(daily: list) -> str | None:
    """Área de usuarios diarios estilo GA4."""
    if not HAS_MPL or len(daily) < 2:
        return None
    daily = _full_month(daily, ("users", "sessions"))
    days = [d["date"][-2:] for d in daily]
    users = [d["users"] for d in daily]

    fig, ax = plt.subplots(figsize=(10.2, 3.6))
    _base_ax(ax)
    ax.plot(days, users, color=G_BLUE, linewidth=2.4)
    ax.fill_between(days, users, alpha=0.12, color=G_BLUE)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))

    step = max(1, len(days) // 10)
    for i, lbl in enumerate(ax.get_xticklabels()):
        lbl.set_visible(i % step == 0)
    return _save(fig)


def channels_donut(channels: list) -> str | None:
    """Donut de canales de adquisición estilo GA4."""
    if not HAS_MPL or not channels:
        return None
    labels = [c["channel"] for c in channels[:6]]
    values = [c["sessions"] for c in channels[:6]]
    total = sum(values)

    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    wedges, _ = ax.pie(
        values, colors=DONUT_COLORS[:len(values)], startangle=90,
        counterclock=False, wedgeprops=dict(width=0.42, edgecolor=BG, linewidth=2),
    )
    ax.text(0, 0.06, fmt_int(total), ha="center", fontsize=26, fontweight="bold", color="#202124")
    ax.text(0, -0.22, "sesiones", ha="center", fontsize=13, color=G_GRAY)

    legend_labels = [f"{l}  ·  {fmt_pct(v / total * 100)}" for l, v in zip(labels, values)]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=13)
    return _save(fig)


def hbar(items: list, label_key: str, value_key: str, color: str = G_BLUE) -> str | None:
    """Barras horizontales (dispositivos, países…)."""
    if not HAS_MPL or not items:
        return None
    labels = [(lambda t: t[:1].upper() + t[1:])(str(i[label_key])) for i in items][::-1]   # «United States», no «United states»
    values = [i[value_key] for i in items][::-1]

    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    ax.set_facecolor(BG)
    for spine in ("top", "right", "bottom"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(GRID)
    bars = ax.barh(labels, values, color=color, height=0.55)
    ax.bar_label(bars, padding=4, fontsize=13, color="#202124", fmt=fmt_int)
    ax.tick_params(colors=G_GRAY, labelsize=13, length=0)
    ax.xaxis.set_visible(False)
    ax.margins(x=0.12)
    return _save(fig)


def mom_change_bars(metrics: list, month_prev: str) -> str | None:
    """% de cambio frente al mes anterior por métrica (barras horizontales): verde si sube,
    rojo si baja, con el valor actual y el del mes anterior a la derecha. Sustituye a las
    barras absolutas, que mezclaban escalas (impresiones frente a clics) y no se leían."""
    if not HAS_MPL or not metrics:
        return None
    rows = metrics[::-1]   # barh dibuja de abajo arriba: la primera métrica queda arriba
    pct = [(m["current"] - m["previous"]) / m["previous"] * 100 if m["previous"] else None for m in rows]
    vals = [p or 0 for p in pct]
    lim = max([abs(v) for v in vals] + [10]) * 1.5   # hueco para la etiqueta del % al final de la barra
    colors = [G_GREEN if v >= 0 else G_RED for v in vals]

    fig, ax = plt.subplots(figsize=(10.2, 0.8 * len(rows) + 0.6))
    ax.set_facecolor(BG)
    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(False)
    bars = ax.barh(range(len(rows)), vals, color=colors, height=0.58, zorder=3)
    ax.axvline(0, color="#BDC1C6", linewidth=1.2, zorder=4)
    ax.set_xlim(-lim if min(vals) < 0 else -lim * 0.04, lim)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([m["label"] for m in rows], fontsize=15, color="#202124")
    ax.tick_params(axis="y", length=0, pad=12)
    ax.xaxis.set_visible(False)

    for i, (bar, p, m) in enumerate(zip(bars, pct, rows)):
        w = bar.get_width()
        ax.text(w + (lim * 0.025 if w >= 0 else -lim * 0.025), i,
                fmt_pct(p, 0, sign=True) if p is not None else "nuevo",
                va="center", ha="left" if w >= 0 else "right", fontsize=15, fontweight="bold",
                color=colors[i] if p is not None else G_GRAY, zorder=5)
        ax.text(1.02, i, f"{fmt_int(m['current'])}  frente a {fmt_int(m['previous'])} en {month_prev}",
                transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=13, color=G_GRAY)
    return _save(fig)


def trend_line_6m(historical: list) -> str | None:
    """Línea de tendencia de 6 meses: usuarios (lima) + impresiones (azul) en doble eje."""
    # Fuera los primeros meses sin ningún dato (web recién medida): no son un «0» real
    while historical and not (historical[0]['users'] or historical[0]['impressions']):
        historical = historical[1:]
    if not HAS_MPL or len(historical) < 3:
        return None
    labels = [h['label'] for h in historical]
    users = [h['users'] for h in historical]
    impressions = [h['impressions'] for h in historical]

    LIME_LINE = "#9ECC00"   # lima más oscura para que contraste sobre blanco
    NAVY      = "#1C1F37"

    fig, ax1 = plt.subplots(figsize=(10.2, 4.0))
    _base_ax(ax1)

    # Usuarios (eje izquierdo)
    l1, = ax1.plot(labels, users, color=LIME_LINE, linewidth=2.6, marker="o",
                   markersize=8, markerfacecolor=LIME_LINE, markeredgecolor="white",
                   markeredgewidth=1.2, zorder=5, label="Usuarios")
    ax1.set_ylabel("Usuarios", fontsize=13, color=NAVY)
    ax1.tick_params(axis="y", labelcolor=NAVY, labelsize=12)
    u_rng = (max(users) - min(users)) or 1
    ax1.set_ylim(min(users) - u_rng * 0.45, max(users) + u_rng * 0.40)
    for i, v in [(i, v) for i, v in enumerate(users) if v]:
        ax1.annotate(fmt_int(v), (i, v), textcoords="offset points", xytext=(0, 12),
                     ha="center", fontsize=12, fontweight="bold", color=NAVY, zorder=6)

    # Impresiones (eje derecho)
    ax2 = ax1.twinx()
    l2, = ax2.plot(labels, impressions, color=G_BLUE, linewidth=2.2, marker="s",
                   markersize=6, linestyle="--", alpha=0.9, zorder=4, label="Impresiones")
    ax2.set_ylabel("Impresiones", fontsize=13, color=G_BLUE)
    ax2.tick_params(axis="y", labelcolor=G_BLUE, labelsize=12, length=0)
    _es_ticks(ax2)
    i_rng = (max(impressions) - min(impressions)) or 1
    ax2.set_ylim(min(impressions) - i_rng * 0.45, max(impressions) + i_rng * 0.40)
    for i, v in [(i, v) for i, v in enumerate(impressions) if v]:
        ax2.annotate(fmt_int(v), (i, v), textcoords="offset points", xytext=(0, -19),
                     ha="center", fontsize=11, color=G_BLUE, zorder=6)
    for spine in ("top", "left", "right"):
        ax2.spines[spine].set_visible(False)

    ax1.tick_params(axis="x", labelsize=13)
    ax1.margins(x=0.08)
    ax1.yaxis.set_major_locator(MaxNLocator(5))
    ax2.yaxis.set_major_locator(MaxNLocator(5))

    # Leyenda fuera del área de datos (arriba, centrada, horizontal)
    ax1.legend(handles=[l1, l2], loc="lower center", bbox_to_anchor=(0.5, 1.01),
               ncol=2, frameon=False, fontsize=13)
    return _save(fig)


def metric_bars(data: dict, color: str = G_BLUE) -> str | None:
    """Barras verticales simples con data labels (fallback del chart nativo)."""
    if not HAS_MPL or not data:
        return None
    fig, ax = plt.subplots(figsize=(10.2, 3.7))
    _base_ax(ax)
    bars = ax.bar(list(data.keys()), list(data.values()), color=color, width=0.5)
    ax.bar_label(bars, padding=4, fontsize=14, fontweight="bold", color="#202124", fmt=fmt_int)
    ax.yaxis.set_visible(False)
    ax.grid(False)
    ax.tick_params(labelsize=14)
    return _save(fig)
