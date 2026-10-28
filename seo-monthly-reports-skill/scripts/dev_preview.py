#!/usr/bin/env python3
"""
Revisión visual de los informes (solo desarrollo; la web no lo usa).

Exporta las diapositivas con Keynote a JPEG y monta hojas de contacto (9 por imagen)
para comparar antes/después de cada cambio en los dos diseños.

Uso:
    # 1. Guardar una vez los datos de un cliente (APIs + IA) como fixture fija
    python3 scripts/dev_preview.py --capture 10deco 9 2026
    python3 scripts/dev_preview.py --capture piscinas_riviera 9 2026 --no-ia

    # 2. Generar los dos diseños desde la fixture y montar las hojas de contacto
    python3 scripts/dev_preview.py scratch/fixtures/10deco_2026_09.json --tag antes

    # o revisar un PPTX ya generado
    python3 scripts/dev_preview.py ~/Desktop/INFORME_SEO_10DECO_SEPTIEMBRE_2026.pptx

Todo se guarda en scratch/ (ignorado por git).
"""

import os
import sys
import json
import glob
import shutil
import argparse
import subprocess

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRATCH = os.path.join(_BASE, "scratch")
_FIXTURES = os.path.join(_SCRATCH, "fixtures")
_PREVIEW = os.path.join(_SCRATCH, "preview")
sys.path.insert(0, os.path.join(_BASE, "scripts"))
sys.path.insert(0, _BASE)

# Todas las secciones que ofrece la web, más Ads (solo sale si hay datos)
ALL_SECTIONS = {"resumen", "destacados", "trafico", "canales", "search", "keywords", "conversiones", "ads",
                "pagespeed", "recomendaciones", "conclusiones", "glosario"}


# ── Fixture: datos reales de un mes guardados una vez ────────

def capture(client: str, month: int, year: int, use_ia: bool = True) -> str:
    """Ejecuta el flujo de main.py hasta el análisis y guarda como JSON sus datos de
    entrada y la respuesta de la IA, para repetir el análisis sin APIs ni IA.
    No genera PDF, propuestas ni subida a Drive."""
    import main as app_main
    import analyze
    if not use_ia:
        os.environ["IA_ENABLED"] = "false"
    captured = {}

    def _inputs(ga4_data, sc_data, ga4_prev=None, sc_prev=None, historical=None,
                notes_level="analitico", **kw):
        captured["inputs"] = dict(ga4_data=ga4_data, sc_data=sc_data, ga4_prev=ga4_prev, sc_prev=sc_prev,
                                  historical=historical, notes_level=notes_level, **kw)
        return _analyze_seo_data(ga4_data, sc_data, ga4_prev, sc_prev, historical, notes_level, **kw)

    def _bundle(self, level="analitico"):
        captured["bundle"] = _ai_bundle(self, level)
        return captured["bundle"]

    def _grab(analysis, client_name, sections=None, include_notes=True):
        captured["pagespeed"] = analysis.get("pagespeed", {})
        return ""

    _analyze_seo_data, _ai_bundle = app_main.analyze_seo_data, analyze.SEOAnalyzer.generate_ai_bundle
    app_main.analyze_seo_data = _inputs
    analyze.SEOAnalyzer.generate_ai_bundle = _bundle
    app_main.generate_pptx = app_main.generate_pptx_v2 = _grab
    app_main.convert_to_pdf = lambda path: None
    sys.argv = ["main.py", "--client", client, "--month", str(month), "--year", str(year),
                "--sections", ",".join(sorted(ALL_SECTIONS)), "--no-propuestas"]
    app_main.main()
    if "pagespeed" not in captured:
        sys.exit("❌ No se llegó a generar el análisis (revisa la salida de arriba)")

    os.makedirs(_FIXTURES, exist_ok=True)
    path = os.path.join(_FIXTURES, f"{client.lower()}_{year}_{month:02d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"client": client, **captured}, f, ensure_ascii=False, indent=1)
    print(f"\n💾 Fixture guardada: {path}")
    return path


def analysis_from(data: dict) -> dict:
    """Repite el análisis de una fixture con el código actual (la IA devuelve lo guardado)."""
    from analyze import SEOAnalyzer
    i = data["inputs"]
    an = SEOAnalyzer(i["ga4_data"], i["sc_data"], i.get("ga4_prev"), i.get("sc_prev"),
                     i.get("ads_data"), i.get("ads_prev"), i.get("insights"))
    an.generate_ai_bundle = lambda level="analitico": data.get("bundle") or {}
    analysis = an.get_full_analysis(i.get("historical"), i.get("notes_level", "analitico"))
    if data.get("pagespeed"):
        analysis["pagespeed"] = data["pagespeed"]
    return analysis


def render(fixture: str, design: str, out_dir: str) -> str:
    """Genera el PPTX de un diseño a partir de una fixture."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BASE, ".env"))   # LOGO_URL_<CLIENTE> para la portada
    from generate_pptx import generate_pptx
    from generate_pptx_v2 import generate_pptx_v2
    with open(fixture, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    os.environ["OUTPUT_DIR"] = out_dir
    gen = generate_pptx_v2 if design == "inpulsia2" else generate_pptx
    path = gen(analysis_from(data), data["client"], sections=set(ALL_SECTIONS), include_notes=True)
    base = os.path.splitext(os.path.basename(fixture))[0]
    final = os.path.join(out_dir, f"{base}_{design}.pptx")
    os.replace(path, final)
    return final


# ── Exportar con Keynote y montar hojas de contacto ──────────

def export_slides(pptx: str, out_dir: str) -> list:
    """Abre el PPTX con Keynote y exporta cada diapositiva a JPEG."""
    pptx = os.path.abspath(pptx)
    img_dir = os.path.join(os.path.abspath(out_dir), os.path.splitext(os.path.basename(pptx))[0])
    shutil.rmtree(img_dir, ignore_errors=True)
    os.makedirs(img_dir)
    script = f'''
    tell application "Keynote"
        set doc to open POSIX file "{pptx}"
        export doc to POSIX file "{img_dir}" as slide images with properties {{image format:JPEG, skipped slides:false}}
        close doc saving no
    end tell
    '''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
    if r.returncode:
        sys.exit(f"❌ Keynote no pudo exportar {os.path.basename(pptx)}: {r.stderr.strip()}")
    files = sorted(glob.glob(os.path.join(img_dir, "**", "*.jp*g"), recursive=True))
    if not files:
        sys.exit(f"❌ Keynote no exportó imágenes en {img_dir}")
    return files


def contact_sheets(images: list, out_prefix: str, per_sheet: int = 9, cols: int = 3) -> list:
    """Monta hojas de contacto de `per_sheet` diapositivas numeradas."""
    from PIL import Image, ImageDraw, ImageFont
    thumb_w = 640
    pad, label_h = 16, 30
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except OSError:
        font = ImageFont.load_default()
    sheets = []
    for start in range(0, len(images), per_sheet):
        batch = images[start:start + per_sheet]
        thumbs = []
        for p in batch:
            with Image.open(p) as im:
                im = im.convert("RGB")
                h = int(im.height * thumb_w / im.width)
                thumbs.append(im.resize((thumb_w, h)))
        th = max(t.height for t in thumbs)
        rows = -(-len(thumbs) // cols)
        sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (th + label_h + pad) + pad), "#3A3A3A")
        draw = ImageDraw.Draw(sheet)
        for i, t in enumerate(thumbs):
            x = pad + (i % cols) * (thumb_w + pad)
            y = pad + (i // cols) * (th + label_h + pad)
            draw.text((x, y + 4), f"{start + i + 1}", fill="#FFFFFF", font=font)
            sheet.paste(t, (x, y + label_h))
        path = f"{out_prefix}_{start // per_sheet + 1}.jpg"
        sheet.save(path, quality=85)
        sheets.append(path)
    return sheets


def preview(pptx: str, out_dir: str) -> list:
    images = export_slides(pptx, out_dir)
    prefix = os.path.join(out_dir, os.path.splitext(os.path.basename(pptx))[0] + "_hoja")
    sheets = contact_sheets(images, prefix)
    print(f"  🖼  {os.path.basename(pptx)}: {len(images)} diapositivas → {len(sheets)} hojas")
    for s in sheets:
        print(f"     {s}")
    return sheets


def main():
    ap = argparse.ArgumentParser(description="Hojas de contacto de los informes (desarrollo)")
    ap.add_argument("source", nargs="?", help="PPTX a revisar o fixture .json a generar")
    ap.add_argument("--capture", nargs=3, metavar=("CLIENTE", "MES", "AÑO"),
                    help="Guardar los datos reales de un cliente y mes como fixture")
    ap.add_argument("--no-ia", action="store_true", help="Con --capture: sin llamada de IA")
    ap.add_argument("--design", choices=["inpulsia1", "inpulsia2", "ambos"], default="ambos")
    ap.add_argument("--tag", default="actual", help="Subcarpeta de salida (p. ej. antes / despues)")
    args = ap.parse_args()

    if args.capture:
        client, month, year = args.capture
        capture(client, int(month), int(year), use_ia=not args.no_ia)
        return 0
    if not args.source:
        ap.error("indica un PPTX, una fixture .json o --capture")

    out_dir = os.path.join(_PREVIEW, args.tag)
    os.makedirs(out_dir, exist_ok=True)
    if args.source.endswith(".json"):
        designs = ["inpulsia1", "inpulsia2"] if args.design == "ambos" else [args.design]
        for d in designs:
            preview(render(args.source, d, out_dir), out_dir)
    else:
        preview(os.path.expanduser(args.source), out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
