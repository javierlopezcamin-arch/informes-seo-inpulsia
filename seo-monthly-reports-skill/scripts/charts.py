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
    from matplotlib.ticker import MaxNLocator
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
    ax.tick_params(colors=G_GRAY, labelsize=9, length=0)


def gsc_performance_line(daily: list) -> str | None:
    """Línea doble clics/impresiones estilo Search Console."""
    if not HAS_MPL or len(daily) < 2:
        return None
    days = [d["date"][-2:] for d in daily]
    clicks = [d["clicks"] for d in daily]
    imps = [d["impressions"] for d in daily]

    fig, ax1 = plt.subplots(figsize=(10.2, 3.6))
    _base_ax(ax1)

    ax1.plot(days, clicks, color=G_BLUE, linewidth=2.2, label="Clics")
    ax1.fill_between(days, clicks, alpha=0.08, color=G_BLUE)
    ax1.set_ylabel("Clics", color=G_BLUE, fontsize=10, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=G_BLUE)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))

    ax2 = ax1.twinx()
    ax2.plot(days, imps, color=G_PURPLE, linewidth=2.2, label="Impresiones")
    ax2.fill_between(days, imps, alpha=0.06, color=G_PURPLE)
    ax2.set_ylabel("Impresiones", color=G_PURPLE, fontsize=10, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=G_PURPLE, labelsize=9, length=0)
    for spine in ("top", "left", "right", "bottom"):
        ax2.spines[spine].set_visible(False)

    # Mostrar solo ~10 etiquetas de día
    step = max(1, len(days) // 10)
    for i, lbl in enumerate(ax1.get_xticklabels()):
        lbl.set_visible(i % step == 0)

    fig.legend(loc="upper left", bbox_to_anchor=(0.07, 1.02), ncol=2,
               frameon=False, fontsize=10)
    return _save(fig)


def ga4_users_line(daily: list) -> str | None:
    """Área de usuarios diarios estilo GA4."""
    if not HAS_MPL or len(daily) < 2:
        return None
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
    ax.text(0, 0.08, f"{total:,}", ha="center", fontsize=20, fontweight="bold", color="#202124")
    ax.text(0, -0.18, "sesiones", ha="center", fontsize=10, color=G_GRAY)

    legend_labels = [f"{l}  ·  {v/total*100:.1f}%" for l, v in zip(labels, values)]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=10)
    return _save(fig)


def hbar(items: list, label_key: str, value_key: str, color: str = G_BLUE) -> str | None:
    """Barras horizontales (dispositivos, países…)."""
    if not HAS_MPL or not items:
        return None
    labels = [str(i[label_key]).capitalize() for i in items][::-1]
    values = [i[value_key] for i in items][::-1]

    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    ax.set_facecolor(BG)
    for spine in ("top", "right", "bottom"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(GRID)
    bars = ax.barh(labels, values, color=color, height=0.55)
    ax.bar_label(bars, padding=4, fontsize=9, color="#202124", fmt="{:,.0f}")
    ax.tick_params(colors=G_GRAY, labelsize=10, length=0)
    ax.xaxis.set_visible(False)
    ax.margins(x=0.12)
    return _save(fig)


def mom_grouped_bars(metrics: list, month_curr: str, month_prev: str) -> str | None:
    """Barras agrupadas MoM: actual (lima) vs anterior (gris)."""
    if not HAS_MPL or not metrics:
        return None
    labels = [m["label"] for m in metrics]
    curr = [m["current"] for m in metrics]
    prev = [m["previous"] for m in metrics]

    x = range(len(labels))
    w = 0.34
    fig, ax = plt.subplots(figsize=(10.2, 4.0))
    _base_ax(ax)
    bars1 = ax.bar([i - w/2 for i in x], curr, w, color="#C6FF2A", label=month_curr, zorder=3)
    bars2 = ax.bar([i + w/2 for i in x], prev, w, color="#9E9E9E", label=month_prev, zorder=3)
    ax.bar_label(bars1, padding=3, fontsize=9, fontweight="bold", color="#202124", fmt="{:,.0f}")
    ax.bar_label(bars2, padding=3, fontsize=9, color=G_GRAY, fmt="{:,.0f}")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=11)
    ax.yaxis.set_visible(False)
    ax.grid(False)
    ax.legend(frameon=False, fontsize=10, loc="upper right")
    return _save(fig)


def trend_line_6m(historical: list) -> str | None:
    """Línea de tendencia de 6 meses: usuarios (lima) + impresiones (azul) en doble eje."""
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
    ax1.set_ylabel("Usuarios", fontsize=10, color=NAVY)
    ax1.tick_params(axis="y", labelcolor=NAVY, labelsize=9)
    u_rng = (max(users) - min(users)) or 1
    ax1.set_ylim(min(users) - u_rng * 0.45, max(users) + u_rng * 0.40)
    for i, v in enumerate(users):
        ax1.annotate(f"{v:,}", (i, v), textcoords="offset points", xytext=(0, 11),
                     ha="center", fontsize=9, fontweight="bold", color=NAVY, zorder=6)

    # Impresiones (eje derecho)
    ax2 = ax1.twinx()
    l2, = ax2.plot(labels, impressions, color=G_BLUE, linewidth=2.2, marker="s",
                   markersize=6, linestyle="--", alpha=0.9, zorder=4, label="Impresiones")
    ax2.set_ylabel("Impresiones", fontsize=10, color=G_BLUE)
    ax2.tick_params(axis="y", labelcolor=G_BLUE, labelsize=9, length=0)
    i_rng = (max(impressions) - min(impressions)) or 1
    ax2.set_ylim(min(impressions) - i_rng * 0.45, max(impressions) + i_rng * 0.40)
    for i, v in enumerate(impressions):
        ax2.annotate(f"{v:,}", (i, v), textcoords="offset points", xytext=(0, -16),
                     ha="center", fontsize=8, color=G_BLUE, zorder=6)
    for spine in ("top", "left", "right"):
        ax2.spines[spine].set_visible(False)

    ax1.tick_params(axis="x", labelsize=10)
    ax1.margins(x=0.08)
    ax1.yaxis.set_major_locator(MaxNLocator(5))
    ax2.yaxis.set_major_locator(MaxNLocator(5))

    # Leyenda fuera del área de datos (arriba, centrada, horizontal)
    ax1.legend(handles=[l1, l2], loc="lower center", bbox_to_anchor=(0.5, 1.01),
               ncol=2, frameon=False, fontsize=10)
    return _save(fig)


def metric_bars(data: dict, color: str = G_BLUE) -> str | None:
    """Barras verticales simples con data labels (fallback del chart nativo)."""
    if not HAS_MPL or not data:
        return None
    fig, ax = plt.subplots(figsize=(10.2, 3.7))
    _base_ax(ax)
    bars = ax.bar(list(data.keys()), list(data.values()), color=color, width=0.5)
    ax.bar_label(bars, padding=4, fontsize=11, fontweight="bold", color="#202124", fmt="{:,.0f}")
    ax.yaxis.set_visible(False)
    ax.grid(False)
    ax.tick_params(labelsize=11)
    return _save(fig)
