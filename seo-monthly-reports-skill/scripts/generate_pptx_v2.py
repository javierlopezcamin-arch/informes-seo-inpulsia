#!/usr/bin/env python3
"""
Generador de presentaciones PPTX — Sistema de diseño INPULSIA 2.

Estética editorial clara: fondo blanco, tipografía navy, acentos lima.
Títulos en Montserrat Black (caps), entradillas en Playfair Display itálica.
Elementos recurrentes: círculo lima con ">", manchas lima en el borde derecho,
watermark fantasma y tarjetas con esquinas redondeadas.

No modifica el diseño clásico (INPULSIA 1). Reutiliza helpers y gráficos de v1.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor

from utils import MESES, get_output_dir
from generate_pptx import _get_logo, _get_client_logo, convert_to_pdf, _CACHE_DIR  # noqa: F401 (reexport)
from generate_pptx import ROW_H, ROW_H_MIN, _rows_fit, _paginate_rows, _paginate_text

try:
    import charts as gcharts
except ImportError:
    gcharts = None

# ── Paleta INPULSIA 2 ────────────────────────────────────────
NAVY   = RGBColor(0x1E, 0x1E, 0x6E)
NAVY_D = RGBColor(0x15, 0x15, 0x50)
LIME   = RGBColor(0xC8, 0xFF, 0x00)
CORAL  = RGBColor(0xFF, 0x70, 0x43)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
GHOST  = RGBColor(0xF0, 0xF1, 0xF6)
SOFT   = RGBColor(0xF5, 0xF6, 0xFB)
MUTE   = RGBColor(0x7A, 0x7C, 0x9C)
GREEN  = RGBColor(0x1D, 0xB9, 0x54)

F_TITLE  = "Montserrat Black"
F_KICKER = "Playfair Display"
F_BODY   = "Montserrat"
F_BODY_SB = "Montserrat SemiBold"

MESES_UPPER = {k: v.upper() for k, v in MESES.items()}


def _get_logo_navy():
    """Logo de Inpulsia recoloreado a una sola tinta navy (sobre fondo claro)."""
    src = _get_logo()
    if not src:
        return None
    out = os.path.join(_CACHE_DIR, "inpulsia-navy.png")
    if os.path.exists(out):
        return out
    try:
        from PIL import Image
        im = Image.open(src).convert("RGBA")
        px = im.load()
        for yy in range(im.height):
            for xx in range(im.width):
                r, g, b, a = px[xx, yy]
                if a > 12:
                    px[xx, yy] = (0x1E, 0x1E, 0x6E, a)
        im.save(out)
        return out
    except Exception:
        return src


_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def _get_logo_cover():
    """Logo para portada con fondo claro: usa el logo a color de assets/ si existe."""
    for name in ("inpulsia-logo-cover.png", "inpulsia-logo-color.png"):
        p = os.path.join(_ASSET_DIR, name)
        if os.path.exists(p):
            return p
    return _get_logo_navy()


# ── Helpers de bajo nivel ────────────────────────────────────

def _slide(prs, bg=WHITE):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s


def _text(slide, x, y, w, h, text, *, size, color, font=F_BODY, bold=False,
          italic=False, align=PP_ALIGN.LEFT, caps=False, track=None,
          anchor=None, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = Inches(0)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    if anchor is not None:
        tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text.upper() if caps else text
    r.font.size = Pt(size)
    r.font.name = font
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    if track is not None:
        r._r.get_or_add_rPr().set("spc", str(track))
    return tb


def _round(slide, x, y, w, h, color, radius=0.12, line=None, line_w=1.0):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    try:
        shp.adjustments[0] = radius
    except Exception:
        pass
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    if line is not None:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _oval(slide, x, y, d, color):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _circle_arrow(slide, x=9.02, y=4.78, d=0.62):
    """Círculo lima con '>' — botón de avance característico."""
    o = _oval(slide, x, y, d, LIME)
    tf = o.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "›"
    r.font.size = Pt(26)
    r.font.bold = True
    r.font.name = F_BODY
    r.font.color.rgb = NAVY


def _blobs(slide):
    """Manchas lima que asoman desde el borde derecho (arriba y abajo)."""
    _round(slide, 9.78, 0.95, 0.6, 1.15, LIME, radius=0.5)
    _round(slide, 9.78, 3.55, 0.6, 1.15, LIME, radius=0.5)


def _decor(slide):
    _blobs(slide)
    _circle_arrow(slide)


def _header(slide, kicker, title, section=""):
    _text(slide, 0.58, 0.46, 8.5, 0.42, kicker, size=17, color=NAVY,
          font=F_KICKER, italic=True)
    _text(slide, 0.55, 0.84, 8.9, 0.72, title, size=31, color=NAVY,
          font=F_TITLE, caps=True, track=40)
    _round(slide, 0.6, 1.62, 0.95, 0.075, LIME, radius=0.5)
    if section:
        _text(slide, 5.5, 0.58, 3.9, 0.3, section, size=9, color=MUTE,
              font=F_BODY_SB, align=PP_ALIGN.RIGHT, caps=True, track=60)


def _delta_color(delta: str) -> RGBColor:
    if delta.startswith("▲"):
        return GREEN
    if delta.startswith("▼"):
        return CORAL
    return MUTE


# ── Portada ──────────────────────────────────────────────────

def add_cover(prs, client_name, month, year, client_logo=None):
    s = _slide(prs)
    _blobs(s)

    logo = _get_logo_cover()
    if logo:
        s.shapes.add_picture(logo, Inches(0.55), Inches(0.5), height=Inches(0.62))

    # Columna izquierda — títulos (dos tercios)
    _text(s, 0.6, 1.7, 5.6, 0.5, "informe de rendimiento", size=22, color=NAVY,
          font=F_KICKER, italic=True)
    _text(s, 0.56, 2.25, 5.7, 1.0, "SEO", size=55, color=NAVY,
          font=F_TITLE, caps=True, track=20)
    _round(s, 0.62, 3.5, 1.1, 0.085, LIME, radius=0.5)
    _text(s, 0.62, 3.74, 5.5, 0.45, client_name.upper(), size=18, color=NAVY,
          font=F_BODY_SB, caps=True, track=80)
    _text(s, 0.62, 4.18, 5.5, 0.4, f"{MESES_UPPER.get(month, 'MES')} · {year}",
          size=13, color=MUTE, font=F_BODY)

    # Columna derecha — círculo grande con el logo del cliente dentro
    ring_d = 3.05
    rx, ry = 6.45, 1.05
    _oval(s, rx - 0.12, ry - 0.12, ring_d + 0.24, LIME)        # halo lima
    ring = _oval(s, rx, ry, ring_d, WHITE)                      # disco blanco
    ring.line.color.rgb = NAVY
    ring.line.width = Pt(2.5)
    if client_logo:
        from PIL import Image as _PIL
        try:
            with _PIL.open(client_logo) as im:
                ratio = im.width / im.height
        except Exception:
            ratio = 1.0
        fit = 1.95
        if ratio >= 1:
            w = fit; h = fit / ratio
        else:
            h = fit; w = fit * ratio
        pic = s.shapes.add_picture(client_logo, Inches(0), Inches(0),
                                   width=Inches(w), height=Inches(h))
        pic.left = int(Inches(rx) + (Inches(ring_d) - pic.width) / 2)
        pic.top = int(Inches(ry) + (Inches(ring_d) - pic.height) / 2)
    else:
        _text(s, rx, ry, ring_d, ring_d, "inpulsia.", size=30, color=NAVY,
              font=F_TITLE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _circle_arrow(s, x=8.62, y=3.62, d=0.66)

    # URL centrada en el pie
    _text(s, 0, 5.12, 10, 0.35, "www.inpulsia.es", size=12, color=NAVY,
          font=F_BODY_SB, align=PP_ALIGN.CENTER, track=120)


# ── Resumen ejecutivo ────────────────────────────────────────

def add_executive(prs, summary, month, year):
    if not summary:
        return
    s = _slide(prs, bg=NAVY)
    # manchas lima borde derecho (sobre navy)
    _round(s, 9.78, 0.95, 0.6, 1.15, LIME, radius=0.5)
    _round(s, 9.78, 3.55, 0.6, 1.15, LIME, radius=0.5)

    logo = _get_logo()
    if logo:
        s.shapes.add_picture(logo, Inches(0.58), Inches(0.5), height=Inches(0.48))

    _text(s, 0.6, 1.35, 8.6, 0.45, "el mes en una mirada", size=20, color=LIME,
          font=F_KICKER, italic=True)
    _text(s, 0.57, 1.8, 8.7, 0.72, "RESUMEN EJECUTIVO", size=30, color=WHITE,
          font=F_TITLE, caps=True, track=40)
    _text(s, 0.6, 2.5, 5, 0.3, f"{MESES_UPPER.get(month, 'MES')} {year}",
          size=11, color=MUTE, font=F_BODY_SB, track=60)

    lines = [l.strip() for l in summary.split('\n') if l.strip()]
    y = 3.05
    for line in lines[:3]:
        _oval(s, 0.62, y + 0.07, 0.14, LIME)
        _text(s, 0.95, y, 8.3, 0.55, line, size=14, color=WHITE, font=F_BODY)
        y += 0.66


# ── Índice ───────────────────────────────────────────────────

def add_index(prs, sections):
    s = _slide(prs)
    _blobs(s)

    _text(s, 0.6, 0.5, 8.5, 0.45, "qué encontrarás", size=20, color=NAVY,
          font=F_KICKER, italic=True)
    _text(s, 0.57, 0.92, 8.7, 0.72, "CONTENIDO", size=32, color=NAVY,
          font=F_TITLE, caps=True, track=40)
    _round(s, 0.62, 1.7, 0.95, 0.075, LIME, radius=0.5)

    n = len(sections)
    step = min(0.6, (5.1 - 2.05) / max(n, 1))
    row_h = min(0.46, step - 0.08)
    y = 2.05
    for num, name in sections:
        _round(s, 0.62, y, 0.52, row_h, LIME, radius=0.3)
        _text(s, 0.62, y, 0.52, row_h, num, size=14, color=NAVY,
              font=F_TITLE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        _text(s, 1.32, y, 7.8, row_h, name, size=15, color=NAVY,
              font=F_BODY_SB, anchor=MSO_ANCHOR.MIDDLE)
        y += step


# ── KPIs ─────────────────────────────────────────────────────

def add_kpi(prs, kicker, title, narrative, kpis, section):
    s = _slide(prs)
    _decor(s)
    _header(s, kicker, title, section)

    if narrative:
        _text(s, 0.6, 1.78, 8.7, 0.5, narrative, size=11, color=MUTE, font=F_BODY)

    n = len(kpis)
    margin, gap = 0.6, 0.18
    card_w = (10 - 2 * margin - gap * (n - 1)) / n
    card_h, card_y = 2.25, 2.5

    for i, kpi in enumerate(kpis):
        x = margin + i * (card_w + gap)
        delta = kpi.get("delta", "")
        dcol = _delta_color(delta)

        _round(s, x, card_y, card_w, card_h, SOFT, radius=0.1, line=GHOST, line_w=1.0)
        _round(s, x + 0.18, card_y + 0.22, 0.4, 0.07, LIME, radius=0.5)
        _text(s, x + 0.18, card_y + 0.42, card_w - 0.3, 0.3, kpi["label"],
              size=8.5, color=MUTE, font=F_BODY_SB, caps=True, track=40)
        _text(s, x + 0.16, card_y + 0.75, card_w - 0.28, 0.85, str(kpi["value"]),
              size=29, color=NAVY, font=F_TITLE)
        if delta:
            _text(s, x + 0.18, card_y + 1.68, card_w - 0.3, 0.4,
                  f"{delta}  vs mes anterior", size=9, color=dcol, font=F_BODY_SB)


# ── Slide con imagen (gráficos matplotlib) ───────────────────

def add_image(prs, kicker, title, img_path, narrative, section, note=None):
    s = _slide(prs)
    _decor(s)
    _header(s, kicker, title, section)

    y_img = 1.85
    if narrative:
        _text(s, 0.6, 1.78, 8.7, 0.45, narrative, size=11, color=MUTE, font=F_BODY)
        y_img = 2.2

    if img_path:
        from PIL import Image as _PIL
        try:
            with _PIL.open(img_path) as im:
                ratio = im.width / im.height
        except Exception:
            ratio = 16 / 9
        max_w, max_h = 8.7, (4.55 - y_img) if not note else (4.35 - y_img)
        w = min(max_w, max_h * ratio)
        h = w / ratio
        x = (10 - w) / 2 - 0.2
        s.shapes.add_picture(img_path, Inches(x), Inches(y_img), width=Inches(w), height=Inches(h))

    if note:
        _insight_box(s, note)


def add_double_image(prs, kicker, title, img_l, label_l, img_r, label_r, section):
    s = _slide(prs)
    _decor(s)
    _header(s, kicker, title, section)

    half = 4.25
    for img, label, x0 in ((img_l, label_l, 0.6), (img_r, label_r, 5.15)):
        if not img:
            continue
        _text(s, x0, 1.85, half, 0.32, label, size=11, color=NAVY, font=F_BODY_SB)
        from PIL import Image as _PIL
        try:
            with _PIL.open(img) as im:
                ratio = im.width / im.height
        except Exception:
            ratio = 4 / 3
        max_w, max_h = half - 0.2, 2.6
        w = min(max_w, max_h * ratio)
        h = w / ratio
        s.shapes.add_picture(img, Inches(x0), Inches(2.25), width=Inches(w), height=Inches(h))


# ── Tablas ───────────────────────────────────────────────────

# Las tablas terminan en x = 8.9 para no pisar el círculo "›" (x 9.02-9.64, y 4.78-5.40)
TABLE_W = 8.3


def _render_table(slide, headers, rows, y_table, col_widths, row_h=ROW_H):
    n_rows, n_cols = len(rows) + 1, len(headers)
    gframe = slide.shapes.add_table(n_rows, n_cols, Inches(0.6), Inches(y_table),
                                    Inches(TABLE_W), Inches(row_h * n_rows))
    table = gframe.table
    table.first_row = False
    table.horz_banding = False
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            table.columns[i].width = Inches(TABLE_W * cw / total)

    for j, hd in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        p = cell.text_frame.paragraphs[0]
        p.text = hd.upper()
        p.font.size = Pt(9)
        p.font.bold = True
        p.font.name = F_BODY_SB
        p.font.color.rgb = LIME
        if j > 0:
            p.alignment = PP_ALIGN.RIGHT

    for i, row in enumerate(rows, 1):
        for j, val in enumerate(row):
            cell = table.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 else SOFT
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            p = cell.text_frame.paragraphs[0]
            p.text = str(val)
            p.font.size = Pt(9.5)
            p.font.name = F_BODY
            p.font.color.rgb = NAVY
            if j > 0:
                p.alignment = PP_ALIGN.RIGHT


def add_table(prs, kicker, title, headers, rows, narrative, section, col_widths=None, note=None):
    """Tabla paginada: si no cabe sigue en «(cont.)», nunca con solo 1-2 filas."""
    y_first, y_rest = (2.2 if narrative else 1.85), 1.85
    bottom = 4.95 if note else 5.35
    pages = _paginate_rows(len(rows), _rows_fit(y_first, bottom, ROW_H), _rows_fit(y_rest, bottom, ROW_H),
                           _rows_fit(y_first, bottom, ROW_H_MIN), _rows_fit(y_rest, bottom, ROW_H_MIN))
    idx = 0
    for page, (count, tight) in enumerate(pages):
        first = page == 0
        s = _slide(prs)
        _decor(s)
        _header(s, kicker, title if first else f"{title} (cont.)", section)

        y_table = y_first if first else y_rest
        if first and narrative:
            _text(s, 0.6, 1.78, 8.7, 0.4, narrative, size=11, color=MUTE, font=F_BODY)

        row_h = min(ROW_H, (bottom - y_table) / (count + 1)) if tight else ROW_H
        _render_table(s, headers, rows[idx:idx + count], y_table, col_widths, row_h)
        idx += count
        if note and page == len(pages) - 1:
            _insight_box(s, note)


# ── Keywords ganadas / perdidas ──────────────────────────────

def add_keyword_movements(prs, movements, section):
    gained = movements.get("gained", [])
    lost = movements.get("lost", [])
    if not gained and not lost:
        return
    s = _slide(prs)
    _decor(s)
    _header(s, "posiciones que se mueven", "KEYWORDS EN MOVIMIENTO", section)

    def _col(items, x0, title, accent, up):
        _round(s, x0, 1.9, 0.32, 0.32, accent, radius=0.5)
        _text(s, x0 + 0.05, 1.92, 0.3, 0.3, "↑" if up else "↓", size=13,
              color=WHITE, font=F_BODY_SB, align=PP_ALIGN.CENTER)
        _text(s, x0 + 0.45, 1.93, 3.6, 0.32, title, size=12, color=NAVY, font=F_BODY_SB)
        y = 2.4
        for m in items[:5]:
            _round(s, x0, y, 4.05, 0.5, SOFT, radius=0.18)
            _text(s, x0 + 0.18, y + 0.06, 2.7, 0.38, m.get("query", ""),
                  size=10, color=NAVY, font=F_BODY, wrap=False)
            delta = m.get("delta", 0)
            sign = "+" if delta > 0 else ""
            _text(s, x0 + 2.9, y + 0.06, 1.0, 0.38, f"{sign}{delta}",
                  size=11, color=accent, font=F_BODY_SB, align=PP_ALIGN.RIGHT)
            y += 0.58

    _col(gained, 0.6, "Subieron", GREEN, True)
    _col(lost, 5.0, "Bajaron", CORAL, False)


# ── Oportunidades página 2 ───────────────────────────────────

def add_opportunities(prs, opps_data, section):
    opps = opps_data.get("opportunities", []) if isinstance(opps_data, dict) else opps_data
    if not opps:
        return
    rows = [[o.get("query", ""), f"{o.get('position', 0):.1f}",
             f"{o.get('impressions', 0):,}", f"{o.get('gap', 0):.1f}"] for o in opps[:8]]
    add_table(prs, "a un paso del top 10", "OPORTUNIDADES",
              ["Keyword", "Posición", "Impresiones", "Gap"], rows,
              "Keywords en la página 2 con mayor potencial de subida.",
              section, col_widths=[4, 1.2, 1.6, 1])


# ── SEO técnico (PageSpeed) ──────────────────────────────────

def add_pagespeed(prs, ps_data, section):
    s = _slide(prs)
    _decor(s)
    _header(s, "salud técnica del sitio", "SEO TÉCNICO", section)
    _text(s, 0.6, 1.78, 8.7, 0.45,
          "Rendimiento, SEO técnico y accesibilidad según Google PageSpeed Insights.",
          size=11, color=MUTE, font=F_BODY)

    def _score_color(score):
        if score >= 90: return GREEN
        if score >= 50: return RGBColor(0xF0, 0xA8, 0x20)
        return CORAL

    scores = [("PERFORMANCE", ps_data.get("performance", 0)),
              ("SEO", ps_data.get("seo", 0)),
              ("ACCESIBILIDAD", ps_data.get("accessibility", 0))]
    card_w, gap = 2.6, 0.3
    start_x = (10 - len(scores) * card_w - (len(scores) - 1) * gap) / 2 - 0.2

    for i, (label, score) in enumerate(scores):
        x = start_x + i * (card_w + gap)
        _round(s, x, 2.4, card_w, 1.85, SOFT, radius=0.1, line=GHOST)
        _round(s, x, 2.4, card_w, 0.08, _score_color(score), radius=0.3)
        _text(s, x, 2.62, card_w, 0.3, label, size=9, color=MUTE,
              font=F_BODY_SB, align=PP_ALIGN.CENTER, caps=True, track=40)
        _text(s, x, 2.95, card_w, 0.95, str(score), size=44,
              color=_score_color(score), font=F_TITLE, align=PP_ALIGN.CENTER)

    cwv = [("FCP", ps_data.get("fcp", "—")), ("LCP", ps_data.get("lcp", "—")),
           ("CLS", ps_data.get("cls", "—")), ("TBT", ps_data.get("tbt", "—"))]
    _text(s, 0.6, 4.45, 8.7, 0.4,
          "Core Web Vitals:   " + "    ·    ".join(f"{k}: {v}" for k, v in cwv),
          size=10, color=NAVY, font=F_BODY_SB)


# ── Texto / conclusiones ─────────────────────────────────────

def add_text(prs, kicker, title, content, section):
    paras = [l.strip() for l in content.split('\n') if l.strip()]
    pages, size = _paginate_text(paras, 12.5, box_w=8.3, box_h=3.0, space=8)

    for i, page in enumerate(pages):
        s = _slide(prs)
        _decor(s)
        _header(s, kicker, title if i == 0 else f"{title} (cont.)", section)
        box = s.shapes.add_textbox(Inches(0.6), Inches(1.95), Inches(8.3), Inches(3.0))
        tf = box.text_frame
        tf.word_wrap = True
        tf.clear()
        for j, para in enumerate(page):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.text = para
            p.font.size = Pt(size)
            p.font.name = F_BODY
            p.font.color.rgb = NAVY
            p.space_before = Pt(4)
            p.space_after = Pt(4)


# ── Capturas de paneles ──────────────────────────────────────

def add_panel_screenshots(prs, client_name):
    import glob
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client_dir = os.path.join(base, "capturas", client_name.upper().replace(" ", "_"))
    if not os.path.isdir(client_dir):
        return
    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        images.extend(glob.glob(os.path.join(client_dir, ext)))
        images.extend(glob.glob(os.path.join(client_dir, ext.upper())))
    if not images:
        return
    print(f"  📸 Encontradas {len(images)} capturas para insertar")
    for img_path in sorted(set(images)):
        name = os.path.splitext(os.path.basename(img_path))[0].replace("_", " ").replace("-", " ").title()
        s = _slide(prs)
        _decor(s)
        _header(s, "panel oficial", name, "Capturas")
        from PIL import Image as _PIL
        try:
            with _PIL.open(img_path) as im:
                ratio = im.width / im.height
        except Exception:
            ratio = 16 / 9
        max_w, max_h = 8.5, 3.0
        w = min(max_w, max_h * ratio)
        h = w / ratio
        x = (10 - w) / 2 - 0.2
        y = 2.0
        _round(s, x - 0.08, y - 0.08, w + 0.16, h + 0.16, NAVY, radius=0.04)
        s.shapes.add_picture(img_path, Inches(x), Inches(y), width=Inches(w), height=Inches(h))


# ── Análisis y Recomendaciones ───────────────────────────────

def add_recommendations(prs, recommendations, anomalies, section):
    # Con puntos de atención el contenido no cabe en 1 slide → 2 slides.
    # Sin anomalías todo encaja en 1 slide.
    if anomalies:
        _add_recommendations_slide1(prs, anomalies, section)
        _add_recommendations_slide2(prs, recommendations, section)
    else:
        _add_recommendations_single(prs, recommendations, section)


def _add_recommendations_slide1(prs, anomalies, section):
    """Slide 1/2 — Puntos de atención (hasta 5 items)."""
    s = _slide(prs)
    _decor(s)
    _header(s, "puntos a vigilar", "ANÁLISIS Y RECOMENDACIONES", section)

    y = 1.95
    _text(s, 0.6, y, 8.4, 0.3, "Puntos de atención", size=12, color=NAVY, font=F_BODY_SB)
    y += 0.42
    for a in anomalies[:5]:
        _round(s, 0.6, y + 0.04, 0.05, 0.34, RGBColor(0xF0, 0xA8, 0x20), radius=0.0)
        _text(s, 0.8, y, 8.0, 0.45, a, size=11, color=NAVY, font=F_BODY)
        y += 0.5


def _add_recommendations_slide2(prs, recommendations, section):
    """Slide 2/2 — Recomendaciones (hasta 4 items)."""
    s = _slide(prs)
    _decor(s)
    _header(s, "qué hacer ahora", "ANÁLISIS Y RECOMENDACIONES", section)

    y = 1.95
    _text(s, 0.6, y, 8.4, 0.3, "Recomendaciones", size=12, color=NAVY, font=F_BODY_SB)
    y += 0.45
    for i, rec in enumerate(recommendations[:4], 1):
        chip = _round(s, 0.6, y, 0.4, 0.4, NAVY, radius=0.3)
        cp = chip.text_frame.paragraphs[0]
        cp.alignment = PP_ALIGN.CENTER
        cr = cp.add_run(); cr.text = str(i); cr.font.size = Pt(13); cr.font.bold = True
        cr.font.name = F_TITLE; cr.font.color.rgb = LIME
        _text(s, 1.15, y + 0.02, 7.7, 0.5, rec, size=12, color=NAVY, font=F_BODY,
              anchor=MSO_ANCHOR.MIDDLE)
        y += 0.6


def _add_recommendations_single(prs, recommendations, section):
    """Slide única cuando no hay puntos de atención."""
    s = _slide(prs)
    _decor(s)
    _header(s, "qué hacer ahora", "ANÁLISIS Y RECOMENDACIONES", section)

    y = 1.95
    _text(s, 0.6, y, 8.4, 0.3, "Recomendaciones", size=12, color=NAVY, font=F_BODY_SB)
    y += 0.45
    for i, rec in enumerate(recommendations[:5], 1):
        chip = _round(s, 0.6, y, 0.4, 0.4, NAVY, radius=0.3)
        cp = chip.text_frame.paragraphs[0]
        cp.alignment = PP_ALIGN.CENTER
        cr = cp.add_run(); cr.text = str(i); cr.font.size = Pt(13); cr.font.bold = True
        cr.font.name = F_TITLE; cr.font.color.rgb = LIME
        _text(s, 1.15, y + 0.02, 7.7, 0.5, rec, size=12, color=NAVY, font=F_BODY,
              anchor=MSO_ANCHOR.MIDDLE)
        y += 0.6


# ── Glosario ─────────────────────────────────────────────────

GLOSSARY = [
    ("Usuarios", "Personas únicas que visitan tu web en el periodo."),
    ("Sesiones", "Visitas a la web; un usuario puede generar varias."),
    ("Páginas vistas", "Número total de páginas cargadas en la web."),
    ("Tasa de rebote", "Porcentaje de visitas que se van sin interactuar."),
    ("Impresiones", "Veces que tu web apareció en los resultados de Google."),
    ("Clics", "Veces que los usuarios pulsaron tu resultado en Google."),
    ("CTR", "Porcentaje de impresiones que se convierten en clic."),
    ("Posición media", "Lugar promedio de tu web en los resultados de búsqueda."),
]


def add_glossary(prs):
    s = _slide(prs)
    _decor(s)
    _header(s, "para entenderlo todo", "GLOSARIO", "Metodología")
    _text(s, 0.6, 1.78, 8.7, 0.4,
          "Qué significa cada métrica que aparece en este informe.",
          size=11, color=MUTE, font=F_BODY)

    half = (len(GLOSSARY) + 1) // 2
    for x0, items in ((0.6, GLOSSARY[:half]), (5.05, GLOSSARY[half:])):
        y = 2.3
        for term, desc in items:
            _round(s, x0, y + 0.03, 0.06, 0.6, LIME, radius=0.0)
            _text(s, x0 + 0.22, y, 4.1, 0.3, term, size=12, color=NAVY, font=F_BODY_SB)
            _text(s, x0 + 0.22, y + 0.3, 4.1, 0.5, desc, size=9.5, color=MUTE, font=F_BODY)
            y += 0.82


# ── Contacto ─────────────────────────────────────────────────

def add_contact(prs):
    s = _slide(prs, bg=NAVY)
    _round(s, 9.78, 0.95, 0.6, 1.15, LIME, radius=0.5)
    _round(s, 9.78, 3.55, 0.6, 1.15, LIME, radius=0.5)

    logo = _get_logo()
    if logo:
        pic = s.shapes.add_picture(logo, Inches(0), Inches(0.7), height=Inches(0.7))
        pic.left = int((prs.slide_width - pic.width) / 2)

    _text(s, 0, 1.6, 10, 0.45, "hablemos de tu proyecto", size=20, color=LIME,
          font=F_KICKER, italic=True, align=PP_ALIGN.CENTER)
    _text(s, 0, 2.05, 10, 0.65, "CONTÁCTANOS", size=32, color=WHITE,
          font=F_TITLE, align=PP_ALIGN.CENTER, caps=True, track=60)

    lines = [
        ("hola@inpulsia.es", True),
        ("(+34) 942 135 917  ·  (+34) 609 340 441", False),
        ("Avda. Eduardo García del Río, 39 · 39011 Santander", False),
        ("www.inpulsia.es", True),
    ]
    y = 2.95
    for text, accent in lines:
        _text(s, 0, y, 10, 0.34, text, size=12.5,
              color=LIME if accent else WHITE, font=F_BODY_SB if accent else F_BODY,
              align=PP_ALIGN.CENTER)
        y += 0.42



# ── Señales SEO para el cliente (tráfico desde IA y páginas a actualizar) ──
def _ai_slide_data(analysis):
    ai = (analysis.get('seo_insights') or {}).get('ai') or {}
    if not ai.get('sessions'):
        return None
    prev = ai.get('prev_sessions')
    trend = ""
    if prev:
        trend = f" ({'+' if ai['sessions'] >= prev else ''}{round((ai['sessions'] - prev) / prev * 100)}% frente al mes anterior)"
    narrative = (f"{ai['sessions']:,} visitas llegaron este mes desde asistentes de IA{trend}. "
                 "Significa que estos asistentes enlazan la web en sus respuestas: un canal nuevo que conviene seguir.").replace(",", ".")
    rows = [[a['assistant'], f"{a['sessions']:,}".replace(",", ".")] for a in ai['sources'][:6]]
    return rows, narrative


def _decay_slide_data(analysis):
    dec = (analysis.get('seo_insights') or {}).get('decay') or {}
    pages = dec.get('pages', [])[:6]
    if not pages:
        return None
    from urllib.parse import urlparse
    def short(u):
        p = urlparse(u).path or "/"
        return p if len(p) <= 52 else p[:50] + "…"
    rows = [[short(p['page']), f"{p['clicks_before']:,}".replace(",", "."), f"{p['clicks_now']:,}".replace(",", "."),
             f"{p['pct']}%"] for p in pages]
    narrative = (f"Páginas que han perdido clics desde Google ({dec.get('window', 'últimos 3 meses')}). "
                 "Actualizar su contenido suele dar resultados antes que crear páginas nuevas.")
    return rows, narrative


# ── Caja de nota IA ──────────────────────────────────────────

def _insight_box(slide, text, y=5.07):
    _round(slide, 0.6, y, 8.0, 0.42, RGBColor(0xF2, 0xFB, 0xD6), radius=0.3)
    _round(slide, 0.6, y, 0.06, 0.42, LIME, radius=0.0)
    chip = _round(slide, 0.78, y + 0.08, 0.62, 0.26, LIME, radius=0.4)
    cp = chip.text_frame.paragraphs[0]
    cp.alignment = PP_ALIGN.CENTER
    cr = cp.add_run()
    cr.text = "NOTA"
    cr.font.size = Pt(7.5)
    cr.font.bold = True
    cr.font.name = F_BODY_SB
    cr.font.color.rgb = NAVY
    _text(slide, 1.55, y + 0.08, 7.65, 0.32, text, size=9.5, color=NAVY,
          font=F_BODY, italic=True)


# ── Orquestador ──────────────────────────────────────────────

def generate_pptx_v2(analysis: dict, client_name: str, sections: set = None,
                     include_notes: bool = True) -> str:
    ALL = {'resumen', 'trafico', 'canales', 'search', 'keywords', 'pagespeed', 'conclusiones'}
    sec = sections if sections else ALL

    month = analysis['month']
    year = analysis['year']
    traffic = analysis['traffic']
    sc = analysis['search_console']
    kw = analysis['keywords']

    client_logo = _get_client_logo(client_name)

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)

    daily_users = analysis.get('daily_users', [])
    daily_sc = analysis.get('daily_trends', {}).get('daily', []) or analysis.get('daily_sc', [])
    top_countries = analysis.get('top_countries', [])
    channels_d = analysis.get('traffic_channels', {})
    devices_d = analysis.get('devices', {})
    pagespeed = analysis.get('pagespeed', {})
    ads = analysis.get('ads', {})
    mom = analysis.get('mom', {})
    kw_moves = analysis.get('keyword_movements', {})
    opps = analysis.get('opportunities', {})
    insights = analysis.get('insights', {})
    exec_summary = analysis.get('executive_summary', '')
    historical = analysis.get('historical', [])

    add_cover(prs, client_name, month, year, client_logo)

    if 'resumen' in sec:
        add_executive(prs, exec_summary, month, year)

    # Índice dinámico
    idx, n = [], 1
    order = [('trafico', "Tráfico Web"), ('canales', "Canales y Audiencia"),
             ('search', "Rendimiento en Google"), ('keywords', "Keywords y Páginas")]
    for key, name in order:
        if key in sec:
            idx.append((f"{n:02d}", name)); n += 1
    if 'ads' in sec and ads:
        idx.append((f"{n:02d}", "Google Ads")); n += 1
    if 'pagespeed' in sec and pagespeed:
        idx.append((f"{n:02d}", "SEO Técnico")); n += 1
    if 'recomendaciones' in sec and (analysis.get('recommendations') or analysis.get('anomalies')):
        idx.append((f"{n:02d}", "Análisis y Recomendaciones")); n += 1
    if 'conclusiones' in sec:
        idx.append((f"{n:02d}", "Conclusiones y Próximos Pasos"))
    sec_nums = {name: num for num, name in idx}
    add_index(prs, idx)

    # TRÁFICO
    if 'trafico' in sec:
        num = sec_nums.get("Tráfico Web", "01")
        lbl = f"{int(num)}. Tráfico Web"

        mom_metrics = mom.get('metrics', [])
        if gcharts and mom_metrics:
            pm = month - 1 if month > 1 else 12
            img = gcharts.mom_grouped_bars(mom_metrics, MESES.get(month, "Actual").capitalize(),
                                           MESES.get(pm, "Anterior").capitalize())
            if img:
                add_image(prs, "mes contra mes", "COMPARATIVA MENSUAL", img,
                          mom.get('narrative', ''), lbl)

        if gcharts and len(historical) >= 3:
            img = gcharts.trend_line_6m(historical)
            if img:
                add_image(prs, "la evolución reciente", "TENDENCIA · 6 MESES", img,
                          "Usuarios e impresiones en los últimos meses.", lbl)

        add_kpi(prs, "lo más importante", "TRÁFICO WEB", traffic['narrative'], [
            {"label": "Usuarios", "value": f"{traffic['users']:,}", "delta": traffic.get('d_users', '')},
            {"label": "Sesiones", "value": f"{traffic['sessions']:,}", "delta": traffic.get('d_sessions', '')},
            {"label": "Páginas vistas", "value": f"{traffic.get('pageviews', 0):,}", "delta": traffic.get('d_pageviews', '')},
            {"label": "Tasa de rebote", "value": f"{traffic['bounce_rate']:.1f}%", "delta": ""},
        ], lbl)
        if include_notes and insights.get('traffic'):
            _insight_box(prs.slides[-1], insights['traffic'])

        if gcharts and daily_users:
            img = gcharts.ga4_users_line(daily_users)
            if img:
                add_image(prs, "día a día", "EVOLUCIÓN DIARIA", img,
                          "Usuarios únicos por día durante el mes.", lbl)

    # CANALES
    if 'canales' in sec:
        num = sec_nums.get("Canales y Audiencia", "02")
        lbl = f"{int(num)}. Canales y Audiencia"

        ch_list = channels_d.get('channels', [])
        if gcharts and ch_list:
            img = gcharts.channels_donut(ch_list)
            if img:
                add_image(prs, "de dónde llegan", "CANALES DE ADQUISICIÓN", img,
                          channels_d.get('narrative', ''), lbl)

        dev_dict = devices_d.get('devices', {})
        if gcharts and (dev_dict or top_countries):
            img_dev = gcharts.hbar([{'label': k, 'value': v} for k, v in dev_dict.items()],
                                   'label', 'value') if dev_dict else None
            img_geo = gcharts.hbar(top_countries, 'country', 'users', color="#34A853") if top_countries else None
            if img_dev or img_geo:
                add_double_image(prs, "quién y desde dónde", "DISPOSITIVOS Y PAÍSES",
                                 img_dev, "Sesiones por dispositivo",
                                 img_geo, "Usuarios por país", lbl)

        _ai = _ai_slide_data(analysis)
        if _ai:
            add_table(prs, "nuevas formas de llegar", "VISITAS DESDE ASISTENTES DE IA", ["Asistente", "Visitas"],
                      _ai[0], _ai[1], lbl, col_widths=[6.5, 2.2])

    # SEARCH
    if 'search' in sec:
        num = sec_nums.get("Rendimiento en Google", "03")
        lbl = f"{int(num)}. Rendimiento en Google"

        add_kpi(prs, "tu visibilidad en google", "RENDIMIENTO EN BÚSQUEDA", sc['narrative'], [
            {"label": "Impresiones", "value": f"{sc['impressions']:,}", "delta": sc.get('d_impressions', '')},
            {"label": "Clics", "value": f"{sc['clicks']:,}", "delta": sc.get('d_clicks', '')},
            {"label": "CTR", "value": f"{sc['ctr']:.2f}%", "delta": sc.get('d_ctr', '')},
            {"label": "Posición media", "value": f"{sc['position']:.1f}", "delta": ""},
        ], lbl)
        if include_notes and insights.get('search'):
            _insight_box(prs.slides[-1], insights['search'])

        if gcharts and daily_sc:
            img = gcharts.gsc_performance_line(daily_sc)
            if img:
                add_image(prs, "clics e impresiones", "EVOLUCIÓN EN BÚSQUEDA", img,
                          analysis.get('daily_trends', {}).get('narrative', ''), lbl)

    # KEYWORDS
    if 'keywords' in sec:
        num = sec_nums.get("Keywords y Páginas", "04")
        lbl = f"{int(num)}. Keywords y Páginas"

        kws = kw.get('top_keywords', [])[:9]
        if kws:
            note = insights.get('keywords') if include_notes else None
            add_table(prs, "tus mejores términos", "TOP KEYWORDS",
                      ["Keyword", "Posición", "Impresiones", "Clics", "CTR"],
                      [[k['query'], f"{k['position']}", f"{k['impressions']:,}",
                        f"{k['clicks']}", f"{k.get('ctr', 0):.1f}%"] for k in kws],
                      kw['narrative'], lbl, col_widths=[4, 1.2, 1.5, 1, 1], note=note)

        add_keyword_movements(prs, kw_moves, lbl)
        add_opportunities(prs, opps, lbl)

        pages_ga4 = analysis.get('pages', {}).get('top_pages_ga4', [])
        if pages_ga4:
            add_table(prs, "las páginas que funcionan", "PÁGINAS MÁS VISITADAS",
                      ["Página", "Visitas", "% del total"],
                      [[pg['path'], f"{pg['views']:,}", f"{pg.get('percentage', 0):.1f}%"]
                       for pg in pages_ga4[:9]],
                      "Páginas con más visitas durante el mes (GA4).",
                      lbl, col_widths=[6, 1.5, 1.5])

    # GOOGLE ADS (opcional)
    if 'ads' in sec and ads:
        num = sec_nums.get("Google Ads", "05")
        lbl = f"{int(num)}. Google Ads"
        cur = ads['currency']
        show_conv = ads.get('show_conversions', False)
        last_kpi = ({"label": "Conversiones", "value": f"{ads['conversions']:,.0f}", "delta": ads.get('d_conversions', '')}
                    if show_conv else
                    {"label": "CPC medio", "value": f"{ads['avg_cpc']:.2f} {cur}", "delta": ads.get('d_cpc', '')})
        add_kpi(prs, "tu inversión publicitaria", "GOOGLE ADS", ads['narrative'], [
            {"label": "Inversión", "value": ads['cost_label'], "delta": ""},
            {"label": "Impresiones", "value": f"{ads['impressions']:,}", "delta": ads.get('d_impressions', '')},
            {"label": "Clics", "value": f"{ads['clicks']:,}", "delta": ads.get('d_clicks', '')},
            last_kpi,
        ], lbl)
        if include_notes and ads.get('insight'):
            _insight_box(prs.slides[-1], ads['insight'])
        if ads.get('campaigns'):
            _name = lambda c: (c['name'][:42] + '…') if len(c['name']) > 42 else c['name']
            if show_conv:
                cols = ["Campaña", "Inversión", "Clics", "Conv.", "CPA"]
                rows = [[_name(c), f"{c['cost']:,.2f} {cur}", f"{c['clicks']:,}", f"{c['conversions']:,.0f}",
                         f"{c['cpa']:.2f} {cur}" if c.get('cpa') else "—"] for c in ads['campaigns'][:8]]
            else:
                cols = ["Campaña", "Inversión", "Impresiones", "Clics", "CPC"]
                rows = [[_name(c), f"{c['cost']:,.2f} {cur}", f"{c['impressions']:,}", f"{c['clicks']:,}",
                         f"{c['cpc']:.2f} {cur}"] for c in ads['campaigns'][:8]]
            add_table(prs, "dónde se invierte", "CAMPAÑAS PRINCIPALES", cols, rows,
                      "Campañas con mayor inversión durante el mes.",
                      lbl, col_widths=[3.7, 1.5, 1.1, 1.1, 1.3])
        if show_conv and ads.get('conversions_by_action'):
            add_table(prs, "qué genera resultados", "CONVERSIONES POR TIPO", ["Acción de conversión", "Conversiones"],
                      [[a['name'], f"{a['conversions']:,.0f}"] for a in ads['conversions_by_action'][:8]],
                      f"Coste por conversión del mes: {ads['cpa_label']}.",
                      lbl, col_widths=[6.5, 2.2])

    add_panel_screenshots(prs, client_name)

    if 'pagespeed' in sec and pagespeed:
        num = sec_nums.get("SEO Técnico", "05")
        add_pagespeed(prs, pagespeed, f"{int(num)}. SEO Técnico")

    _recs = analysis.get('recommendations', [])
    _anom = analysis.get('anomalies', [])
    _dec = _decay_slide_data(analysis) if 'recomendaciones' in sec else None
    if _dec:
        num = sec_nums.get("Análisis y Recomendaciones", "06")
        add_table(prs, "qué conviene actualizar", "PÁGINAS QUE PIERDEN VISITAS",
                  ["Página", "Clics antes", "Clics ahora", "Cambio"], _dec[0], _dec[1],
                  f"{int(num)}. Recomendaciones", col_widths=[4.9, 1.3, 1.3, 1.2])
    if 'recomendaciones' in sec and (_recs or _anom):
        num = sec_nums.get("Análisis y Recomendaciones", "06")
        add_recommendations(prs, _recs, _anom, f"{int(num)}. Recomendaciones")

    if 'conclusiones' in sec:
        num = sec_nums.get("Conclusiones y Próximos Pasos", "05")
        add_text(prs, "hacia dónde vamos", "CONCLUSIONES",
                 analysis['conclusions'], f"{int(num)}. Conclusiones")

    if 'glosario' in sec:
        add_glossary(prs)

    add_contact(prs)

    month_name = MESES_UPPER.get(month, 'MES')
    filename = f"INFORME_SEO_{client_name.upper().replace(' ', '_')}_{month_name}_{year}.pptx"
    filepath = os.path.join(get_output_dir(), filename)
    prs.save(filepath)
    return filepath
