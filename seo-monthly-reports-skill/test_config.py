#!/usr/bin/env python3
"""
Test de configuración — Verifica que todo está listo
"""

import os
import json
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

G = '\033[92m'  # verde
R = '\033[91m'  # rojo
B = '\033[94m'  # azul
E = '\033[0m'   # reset


def test(name, condition, detail=""):
    status = f"{G}✅{E}" if condition else f"{R}❌{E}"
    print(f"  {status} {name}")
    if detail and not condition:
        print(f"      → {detail}")
    return condition


def main():
    print(f"\n{B}{'='*55}")
    print("  TEST DE CONFIGURACIÓN — SEO Monthly Reports")
    print(f"{'='*55}{E}\n")

    results = []

    # 1. Archivo .env
    env_exists = os.path.exists(os.path.join(os.path.dirname(__file__), '.env'))
    results.append(test("Archivo .env", env_exists, "Crea el archivo .env en la raíz del proyecto"))

    # 2. Credenciales JSON
    creds_path = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
    creds_exist = os.path.exists(creds_path) if creds_path else False
    results.append(test("cappuccino-key.json", creds_exist, f"No encontrado en: {creds_path}"))

    if creds_exist:
        try:
            with open(creds_path) as f:
                creds = json.load(f)
            has_fields = all(k in creds for k in ['type', 'project_id', 'private_key', 'client_email'])
            results.append(test("JSON válido (Service Account)", has_fields and creds.get('type') == 'service_account',
                                "El JSON no es un Service Account. ¿Estás usando credentials.json de OAuth?"))
            if has_fields:
                print(f"      Service Account: {creds['client_email']}")
        except Exception as e:
            results.append(test("JSON válido", False, str(e)))

    # 3. Variables de entorno
    vars_needed = {
        'GOOGLE_CLOUD_PROJECT_ID': os.getenv('GOOGLE_CLOUD_PROJECT_ID'),
        'GA4_PROPERTY_ID_10DECO': os.getenv('GA4_PROPERTY_ID_10DECO'),
        'SEARCH_CONSOLE_URL_10DECO': os.getenv('SEARCH_CONSOLE_URL_10DECO'),
    }
    for var, val in vars_needed.items():
        results.append(test(var, bool(val), "No configurado en .env"))
        if val:
            print(f"      → {val}")

    # 4. Librerías Python
    libs = {
        'google-auth': 'google.oauth2.service_account',
        'google-api-python-client': 'googleapiclient.discovery',
        'google-analytics-data': 'google.analytics.data_v1beta',
        'python-pptx': 'pptx',
        'python-dotenv': 'dotenv',
    }
    for name, module in libs.items():
        try:
            __import__(module)
            results.append(test(f"Librería: {name}", True))
        except ImportError:
            results.append(test(f"Librería: {name}", False, f"pip install {name} --break-system-packages"))

    # Resumen
    passed = sum(results)
    total = len(results)
    print(f"\n{B}{'='*55}{E}")
    if passed == total:
        print(f"  {G}🎉 {passed}/{total} tests pasados — ¡LISTO!{E}")
    else:
        print(f"  {R}⚠️  {passed}/{total} tests pasados — revisa los errores{E}")
    print(f"{B}{'='*55}{E}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
