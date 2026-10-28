#!/usr/bin/env python3
"""
Extractor de datos Google Search Console
Usa Service Account para autenticación
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from utils import cache_read, cache_write, month_ttl_hours

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']


class SearchConsoleExtractor:
    """Extrae datos de Google Search Console"""

    def __init__(self, credentials_path: str, site_url: str):
        self.credentials = Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self.service = build('webmasters', 'v3', credentials=self.credentials)
        self.site_url = site_url

    def _date_range(self, month: int, year: int) -> tuple:
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_obj = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_obj = datetime(year, month + 1, 1) - timedelta(days=1)
        end_date = end_obj.strftime("%Y-%m-%d")
        return start_date, end_date

    def get_monthly_summary(self, month: int, year: int) -> dict:
        """Resumen del mes: impresiones, clics, CTR, posición"""
        start_date, end_date = self._date_range(month, year)
        print(f"  🔍 Search Console: {start_date} → {end_date}")

        response = self.service.searchanalytics().query(
            siteUrl=self.site_url,
            body={'startDate': start_date, 'endDate': end_date}
        ).execute()

        data = {'impressions': 0, 'clicks': 0, 'ctr': 0.0, 'position': 0.0}
        if response.get('rows'):
            row = response['rows'][0]
            data['impressions'] = int(row.get('impressions', 0))
            data['clicks'] = int(row.get('clicks', 0))
            data['ctr'] = round(float(row.get('ctr', 0)) * 100, 2)
            data['position'] = round(float(row.get('position', 0)), 1)

        print(f"  ✅ Impresiones: {data['impressions']} | Clics: {data['clicks']}")
        return data

    def get_top_keywords(self, month: int, year: int, limit: int = 10) -> list:
        """Top keywords por impresiones"""
        start_date, end_date = self._date_range(month, year)

        response = self.service.searchanalytics().query(
            siteUrl=self.site_url,
            body={
                'startDate': start_date, 'endDate': end_date,
                'dimensions': ['query'], 'rowLimit': limit,
            }
        ).execute()

        keywords = []
        for row in response.get('rows', []):
            keywords.append({
                'query': row['keys'][0],
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'ctr': round(float(row.get('ctr', 0)) * 100, 2),
                'position': round(float(row.get('position', 0)), 1),
            })

        print(f"  ✅ Keywords encontrados: {len(keywords)}")
        return keywords

    def get_top_pages(self, month: int, year: int, limit: int = 10) -> list:
        """Top páginas por impresiones"""
        start_date, end_date = self._date_range(month, year)

        response = self.service.searchanalytics().query(
            siteUrl=self.site_url,
            body={
                'startDate': start_date, 'endDate': end_date,
                'dimensions': ['page'], 'rowLimit': limit,
            }
        ).execute()

        pages = []
        for row in response.get('rows', []):
            pages.append({
                'url': row['keys'][0],
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'ctr': round(float(row.get('ctr', 0)) * 100, 2),
            })

        print(f"  ✅ Páginas encontradas: {len(pages)}")
        return pages

    def get_daily_performance(self, month: int, year: int) -> list:
        """Obtiene el rendimiento diario de clics e impresiones durante el mes"""
        start_date, end_date = self._date_range(month, year)

        response = self.service.searchanalytics().query(
            siteUrl=self.site_url,
            body={
                'startDate': start_date, 'endDate': end_date,
                'dimensions': ['date'],
                'rowLimit': 31,
            }
        ).execute()

        daily_data = []
        for row in response.get('rows', []):
            daily_data.append({
                'date': row['keys'][0],
                'clicks': int(row.get('clicks', 0)),
                'impressions': int(row.get('impressions', 0)),
            })
        
        # Ordenar por fecha
        daily_data.sort(key=lambda x: x['date'])

        print(f"  ✅ Rendimiento diario obtenido: {len(daily_data)} días")
        return daily_data


    def get_device_breakdown(self, month: int, year: int) -> list:
        """Clics e impresiones por dispositivo"""
        start_date, end_date = self._date_range(month, year)

        response = self.service.searchanalytics().query(
            siteUrl=self.site_url,
            body={
                'startDate': start_date, 'endDate': end_date,
                'dimensions': ['device'],
            }
        ).execute()

        devices = []
        for row in response.get('rows', []):
            devices.append({
                'device': row['keys'][0],
                'clicks': int(row.get('clicks', 0)),
                'impressions': int(row.get('impressions', 0)),
            })

        print(f"  ✅ Dispositivos SC: {len(devices)}")
        return devices


def extract_search_console_data(site_url: str, month: int, year: int) -> dict:
    """Función principal — extrae todos los datos de Search Console"""
    import hashlib
    cache_key = f"sc_{hashlib.md5(site_url.encode()).hexdigest()[:8]}_{year}_{month:02d}_v3"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        print("  ⚡ Search Console: datos desde caché")
        return cached

    creds_path = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
    if not creds_path or not os.path.exists(creds_path):
        print("  ❌ No se encontró cappuccino-key.json")
        return {}

    extractor = SearchConsoleExtractor(creds_path, site_url)
    data = {
        'month': month,
        'year': year,
        'summary': extractor.get_monthly_summary(month, year),
        'top_keywords': extractor.get_top_keywords(month, year),
        'top_pages': extractor.get_top_pages(month, year),
        'daily_performance': extractor.get_daily_performance(month, year),
        'devices': extractor.get_device_breakdown(month, year),
    }
    cache_write(cache_key, data)
    return data


def extract_sc_queries(site_url: str, month: int, year: int) -> dict:
    """Detalle para el archivo de propuestas: 250 queries y 500 pares query+página."""
    import hashlib
    cache_key = f"scq_{hashlib.md5(site_url.encode()).hexdigest()[:8]}_{year}_{month:02d}_v1"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        return cached

    creds_path = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
    ext = SearchConsoleExtractor(creds_path, site_url)
    start, end = ext._date_range(month, year)

    def q(dims, limit):
        return ext.service.searchanalytics().query(siteUrl=site_url, body={
            'startDate': start, 'endDate': end, 'dimensions': dims, 'rowLimit': limit,
        }).execute().get('rows', [])

    def row(r):
        return {'impressions': int(r.get('impressions', 0)), 'clicks': int(r.get('clicks', 0)),
                'ctr': round(float(r.get('ctr', 0)) * 100, 2), 'position': round(float(r.get('position', 0)), 1)}

    data = {
        'queries': [{'query': r['keys'][0], **row(r)} for r in q(['query'], 250)],
        'query_pages': [{'query': r['keys'][0], 'page': r['keys'][1], **row(r)} for r in q(['query', 'page'], 500)],
    }
    cache_write(cache_key, data)
    return data


if __name__ == "__main__":
    site_url = os.getenv('SEARCH_CONSOLE_URL_10DECO')
    if not site_url:
        print("❌ SEARCH_CONSOLE_URL_10DECO no configurado en .env")
        exit(1)
    data = extract_search_console_data(site_url, month=2, year=2026)
    if data:
        s = data['summary']
        print(f"\n✅ Impresiones: {s['impressions']} | Clics: {s['clicks']} | CTR: {s['ctr']}%")
