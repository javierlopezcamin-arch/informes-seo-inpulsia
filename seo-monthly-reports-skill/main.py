#!/usr/bin/env python3
"""
SEO Monthly Reports — Orquestador principal
Extrae datos → Analiza → Genera PPTX profesional

Uso:
    python3 main.py                              # Mes actual, cliente 10deco
    python3 main.py --client 10deco --month 2 --year 2026
"""

import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv

# Cargar .env desde la carpeta del proyecto
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, '.env'))

# La ruta de credenciales del .env es relativa a la carpeta del proyecto;
# se hace absoluta para que los extractores funcionen desde cualquier cwd.
_creds = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
if _creds and not os.path.isabs(_creds):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(_BASE_DIR, _creds)

# Importar módulos del proyecto
sys.path.insert(0, os.path.join(_BASE_DIR, 'scripts'))
from extract_ga4 import extract_ga4_data
from extract_search_console import extract_search_console_data
from extract_pagespeed import extract_pagespeed
from extract_google_ads import extract_google_ads_data, customer_id_for, credentials_configured, friendly_error, ads_enabled_for
from analyze import analyze_seo_data
from seo_insights import build_insights
from generate_pptx import generate_pptx, convert_to_pdf
from generate_pptx_v2 import generate_pptx_v2
from generate_propuestas import generate_propuestas, web_enabled_for
from upload_drive import upload_report, upload_internal_doc
from utils import MESES, prev_month
import copy


def validate_config(client_name: str) -> bool:
    """Verifica que la configuración esté completa"""
    client_upper = client_name.upper()
    creds_path = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))

    checks = [
        (os.path.exists(creds_path), f"Credenciales: {os.path.basename(creds_path)}"),
        (bool(os.getenv(f'GA4_PROPERTY_ID_{client_upper}')), f"GA4_PROPERTY_ID_{client_upper}"),
        (bool(os.getenv(f'SEARCH_CONSOLE_URL_{client_upper}')), f"SEARCH_CONSOLE_URL_{client_upper}"),
    ]

    all_ok = True
    for ok, label in checks:
        print(f"  {'✅' if ok else '❌'} {label}")
        if not ok:
            all_ok = False
    return all_ok


def main():
    parser = argparse.ArgumentParser(description='Generador de informes SEO mensuales')
    parser.add_argument('--client', type=str, default='10deco', help='Nombre del cliente')
    parser.add_argument('--month', type=int, default=datetime.now().month, help='Mes (1-12)')
    parser.add_argument('--year', type=int, default=datetime.now().year, help='Año')
    parser.add_argument('--boost', type=float, default=1.0, help='Factor de ajuste (1.0=real, 1.10=+10%%, 1.20=+20%%, 1.30=+30%%)')
    parser.add_argument('--validate-only', action='store_true', help='Solo validar acceso a APIs, sin generar informe')
    parser.add_argument('--upload-drive', action='store_true', help='Subir informe a Google Drive')
    parser.add_argument('--sections', type=str, default='resumen,destacados,trafico,canales,search,keywords,conversiones,pagespeed,conclusiones,glosario', help='Secciones a incluir')
    parser.add_argument('--no-notes', action='store_true', help='No incluir notas IA en las slides')
    parser.add_argument('--notes-level', type=str, default='analitico', choices=['positivo', 'analitico'], help='Profundidad de las notas IA')
    parser.add_argument('--design', type=str, default='inpulsia1', choices=['inpulsia1', 'inpulsia2'], help='Diseño del informe')
    parser.add_argument('--new-ai', action='store_true', help='Redactar de nuevo con IA aunque haya una respuesta guardada para estos datos')
    parser.add_argument('--no-propuestas', action='store_true', help='No generar los archivos internos de propuestas (Web y Marketing)')
    args = parser.parse_args()

    if args.month < 1 or args.month > 12:
        print("❌ Mes debe estar entre 1 y 12")
        return 1

    if args.new_ai:
        os.environ['IA_NUEVA'] = 'true'

    client = args.client
    month = args.month
    year = args.year
    month_name = MESES.get(month, 'mes')

    print("\n" + "=" * 60)
    print("  GENERADOR AUTOMÁTICO DE INFORMES SEO")
    print("=" * 60)
    print(f"  Cliente: {client.upper()}")
    print(f"  Período: {month_name.capitalize()} {year}")
    print("=" * 60)

    # ── 1. Validar configuración ────────────────────────────
    print("\n🔍 Validando configuración...")
    if not validate_config(client):
        print("\n❌ Configuración incompleta. Revisa el archivo .env")
        return 1

    client_upper = client.upper()
    ga4_id = os.getenv(f'GA4_PROPERTY_ID_{client_upper}')
    sc_url = os.getenv(f'SEARCH_CONSOLE_URL_{client_upper}')

    # ── Modo validación ─────────────────────────────────────
    if args.validate_only:
        print("\n🔍 Validando acceso a APIs...")
        ok = True
        try:
            ga4_test = extract_ga4_data(ga4_id, month, year)
            if ga4_test and ga4_test.get('metrics'):
                print("  ✅ GA4: acceso correcto")
            else:
                print("  ⚠️  GA4: sin datos (puede ser normal si el mes no tiene tráfico)")
        except Exception as e:
            print(f"  ❌ GA4: {e}")
            ok = False
        try:
            sc_test = extract_search_console_data(sc_url, month, year)
            if sc_test and sc_test.get('summary'):
                print("  ✅ Search Console: acceso correcto")
            else:
                print("  ⚠️  Search Console: sin datos")
        except Exception as e:
            print(f"  ❌ Search Console: {e}")
            ok = False
        return 0 if ok else 1

    # ── 2. Extraer datos ────────────────────────────────────
    failed = []
    print(f"\n📊 Extrayendo datos de Google Analytics 4...")
    try:
        ga4_data = extract_ga4_data(ga4_id, month, year)
    except Exception as e:
        print(f"  ❌ Error GA4: {e}")
        ga4_data, failed = {}, failed + ["GA4"]

    print(f"\n🔍 Extrayendo datos de Search Console...")
    try:
        sc_data = extract_search_console_data(sc_url, month, year)
    except Exception as e:
        print(f"  ❌ Error Search Console: {e}")
        sc_data, failed = {}, failed + ["Search Console"]

    # Si una fuente falla (permisos, API...) no se genera el informe: saldría con
    # ceros y las notas IA los interpretarían como datos reales.
    if failed:
        print(f"\n❌ Informe cancelado: sin acceso a {' y '.join(failed)}.")
        print("   Comprueba que seo-reports@cappuccino.iam.gserviceaccount.com tiene permiso")
        print("   (GA4: Lector · Search Console: Completo) y usa 'Verificar acceso' en el panel.")
        return 1
    if not ga4_data and not sc_data:
        print("\n❌ No se pudieron extraer datos de ninguna fuente.")
        print("   Verifica que las APIs estén habilitadas en Google Cloud Console:")
        print("   → Google Analytics Data API")
        print("   → Google Search Console API")
        return 1

    # Datos mínimos para que el análisis no falle
    if not ga4_data:
        ga4_data = {'month': month, 'year': year, 'metrics': {}, 'top_pages': [], 'traffic_channels': [], 'devices': {}}
    else:
        ga4_data.setdefault('traffic_channels', [])
        ga4_data.setdefault('devices', {})

    if not sc_data:
        sc_data = {'month': month, 'year': year, 'summary': {}, 'top_keywords': [], 'top_pages': [], 'daily_performance': []}
    else:
        sc_data.setdefault('daily_performance', [])

    # ── 2b. Extraer mes anterior (comparación MoM) ──────────
    pm, py = prev_month(month, year)
    print(f"\n📈 Extrayendo mes anterior ({MESES.get(pm, pm)} {py}) para comparar...")
    try:
        ga4_prev = extract_ga4_data(ga4_id, pm, py)
    except Exception as e:
        print(f"  ⚠️  GA4 mes anterior: {type(e).__name__}: {str(e)[:120]} — el informe sale sin comparativa de tráfico")
        ga4_prev = {}
    try:
        sc_prev = extract_search_console_data(sc_url, pm, py)
    except Exception as e:
        print(f"  ⚠️  Search Console mes anterior: {type(e).__name__}: {str(e)[:120]} — el informe sale sin comparativa de búsqueda")
        sc_prev = {}

    # ── 2b'. Google Ads (opcional; un fallo no cancela el informe) ──
    wanted = {x.strip() for x in args.sections.split(',') if x.strip()}
    # La marca del cliente (ADS_EN_INFORME_<CLIENTE>) activa Ads + archivo de propuestas.
    marked = ads_enabled_for(client)
    if marked:
        wanted.add('ads')
    ads_data, ads_prev, ads_error = {}, {}, ""
    if 'ads' in wanted:
        ads_id = customer_id_for(client)
        if not ads_id:
            print("\n📣 Google Ads: este cliente no tiene Customer ID; se omite la sección")
        elif not credentials_configured():
            ads_error = "No disponible: faltan credenciales de Google Ads en el .env"
            print("\n📣 Google Ads: faltan credenciales en el .env; se omite la sección")
        else:
            print("\n📣 Extrayendo Google Ads...")
            try:
                ads_data = extract_google_ads_data(ads_id, month, year)
                if not ads_data.get('impressions'):
                    print("  ℹ️  Google Ads: sin actividad este mes; se omite la sección")
                else:
                    try:
                        ads_prev = extract_google_ads_data(ads_id, pm, py)
                    except Exception as e:
                        print(f"  ⚠️  Google Ads mes anterior: {friendly_error(e)} — sin comparativa de Ads")
                        ads_prev = {}
            except Exception as e:
                ads_data = {}
                ads_error = f"No disponible: {friendly_error(e)}"
                print(f"  ⚠️  Google Ads: {friendly_error(e)} — el informe se genera sin esa sección")

    # Copia de los datos reales para el archivo interno (el boost solo afecta al informe del cliente)
    real_ga4, real_sc = copy.deepcopy(ga4_data), copy.deepcopy(sc_data)

    # ── 2c. Aplicar ajuste de datos (boost) ───────────────────
    boost = args.boost
    if boost != 1.0:
        print(f"\n📐 Aplicando ajuste de datos: x{boost:.2f}")
        m = ga4_data.get('metrics', {})
        for k in ('total_users', 'active_users', 'sessions', 'pageviews'):
            if k in m:
                m[k] = int(m[k] * boost)
        for pg in ga4_data.get('top_pages', []):
            pg['views'] = int(pg['views'] * boost)
        for ch in ga4_data.get('traffic_channels', []):
            ch['sessions'] = int(ch['sessions'] * boost)
        for d in ga4_data.get('daily_users', []):
            d['users'] = int(d['users'] * boost)
            d['sessions'] = int(d['sessions'] * boost)
        for c in ga4_data.get('top_countries', []):
            c['users'] = int(c['users'] * boost)
        dev = ga4_data.get('devices', {})
        for k in list(dev.keys()):
            dev[k] = int(dev[k] * boost)
        s = sc_data.get('summary', {})
        for k in ('impressions', 'clicks'):
            if k in s:
                s[k] = int(s[k] * boost)
        for d in sc_data.get('daily_performance', []):
            d['clicks'] = int(d['clicks'] * boost)
            d['impressions'] = int(d['impressions'] * boost)
        for kw in sc_data.get('top_keywords', []):
            kw['impressions'] = int(kw['impressions'] * boost)
            kw['clicks'] = int(kw['clicks'] * boost)

    # ── 2d. Histórico 6 meses (en paralelo) ────────────────
    print(f"\n📈 Extrayendo histórico (6 meses)...")
    months = []
    hm, hy = month, year
    for _ in range(6):
        months.append((hm, hy))
        hm, hy = prev_month(hm, hy)

    def _fetch_month(mh):
        hm, hy = mh
        h_ga4 = extract_ga4_data(ga4_id, hm, hy)
        h_sc = extract_search_console_data(sc_url, hm, hy)
        m_ga4 = (h_ga4 or {}).get('metrics', {})
        s_sc = (h_sc or {}).get('summary', {})
        return {
            'month': hm, 'year': hy,
            'label': f"{MESES.get(hm, hm)[:3]} {hy}",
            'users': m_ga4.get('total_users', 0),
            'sessions': m_ga4.get('sessions', 0),
            'impressions': s_sc.get('impressions', 0),
            'clicks': s_sc.get('clicks', 0),
        }

    # 4 workers: cada mes hace ~6 peticiones GA4 en serie, así no se supera
    # el límite de 10 peticiones concurrentes por propiedad de la API GA4.
    historical = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for mh, fut in [(mh, pool.submit(_fetch_month, mh)) for mh in months]:
            try:
                historical.append(fut.result())
            except Exception as e:
                print(f"  ⚠️  Histórico {MESES.get(mh[0], mh[0])[:3]} {mh[1]}: {type(e).__name__}: {e}")
    historical.sort(key=lambda h: (h['year'], h['month']))
    print(f"  ✅ {len(historical)} meses recopilados")

    # ── 2e. PageSpeed Insights ──────────────────────────────
    print(f"\n⚡ Extrayendo PageSpeed Insights...")
    try:
        ps_data = extract_pagespeed(sc_url)
    except Exception as e:
        print(f"  ⚠️  PageSpeed: {e}")
        ps_data = {}

    # ── 2f. Señales cruzadas: contenido que pierde clics, URL SC×GA4, tráfico desde IA ──
    print(f"\n🔎 Señales SEO (contenido, páginas, IA)...")
    insights = build_insights(ga4_id, sc_url, month, year)
    print(f"  ✅ {len((insights.get('decay') or {}).get('pages', []))} páginas pierden clics · "
          f"{(insights.get('ai') or {}).get('sessions', 0)} visitas desde IA")

    # ── 3. Analizar ─────────────────────────────────────────
    print(f"\n🔬 Analizando datos...")
    analysis = analyze_seo_data(ga4_data, sc_data, ga4_prev, sc_prev, historical, args.notes_level,
                                ads_data=ads_data, ads_prev=ads_prev, insights=insights)
    if ps_data:
        analysis['pagespeed'] = ps_data
    print("  ✅ Análisis completado")

    # ── 4. Generar PPTX ────────────────────────────────────
    print(f"\n📊 Generando presentación PPTX...")
    try:
        sections = wanted or None
        _gen = generate_pptx_v2 if args.design == 'inpulsia2' else generate_pptx
        filepath = _gen(analysis, client, sections=sections, include_notes=not args.no_notes)
        print(f"  ✅ Guardado: {filepath}")
    except Exception as e:
        print(f"  ❌ Error generando PPTX: {e}")
        return 1

    # ── 5. Convertir a PDF ─────────────────────────────────
    print(f"\n📄 Convirtiendo a PDF...")
    pdf_path = convert_to_pdf(filepath)

    # ── 5b. Archivos internos: WEB (WEB_EN_INFORME_<C>) y MARKETING (ADS_EN_INFORME_<C>) ──
    props = {}
    web_on = web_enabled_for(client)
    if (marked or web_on) and not args.no_propuestas:
        print(f"\n📝 Generando archivos de propuestas (interno)...")
        try:
            props = generate_propuestas(client, month, year, real_ga4, real_sc, ads_data, ads_error, insights,
                                        web=web_on, marketing=marked)
            for kind, path in props.items():
                if path:
                    print(f"  ✅ Guardado ({kind}): {path}")
        except Exception as e:
            print(f"  ⚠️  Propuestas: {type(e).__name__}: {e} — el informe se mantiene")

    # ── 6. Subir a Google Drive ───────────────────────────
    drive_url = None
    if args.upload_drive:
        print(f"\n☁️  Subiendo a Google Drive...")
        drive_url = upload_report(filepath, client)
        if pdf_path:
            upload_report(pdf_path, client)
        for kind, path in props.items():
            if path:
                prop_drive = upload_internal_doc(path, client)
                if prop_drive:
                    print(f"  📝 Propuestas {kind} en Drive: {prop_drive}")

    # ── Resultado ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ✅ ¡INFORME GENERADO EXITOSAMENTE!")
    print("=" * 60)
    print(f"  📊 Cliente:  {client.upper()}")
    print(f"  📅 Período:  {month_name.capitalize()} {year}")
    print(f"  📄 PPTX:     {filepath}")
    if pdf_path:
        print(f"  📄 PDF:      {pdf_path}")
    for kind, path in props.items():
        if path:
            print(f"  📝 PROPUESTAS {kind.upper()}: {path}")
    if drive_url:
        print(f"  ☁️  Drive:    {drive_url}")
    print("=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
