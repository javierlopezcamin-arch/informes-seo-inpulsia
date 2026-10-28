#!/usr/bin/env python3
"""
Extractor de datos Google Analytics 4
Usa Service Account para autenticación
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from utils import cache_read, cache_write, month_ttl_hours
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    DateRange,
    OrderBy,
)

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']


class GA4Extractor:
    """Extrae datos de Google Analytics 4"""

    def __init__(self, credentials_path: str, property_id: str):
        self.credentials = Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self.client = BetaAnalyticsDataClient(credentials=self.credentials)
        self.property_id = property_id

    def _date_range(self, month: int, year: int) -> tuple:
        """Calcula start_date y end_date para un mes"""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_obj = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_obj = datetime(year, month + 1, 1) - timedelta(days=1)
        end_date = end_obj.strftime("%Y-%m-%d")
        return start_date, end_date

    def get_monthly_data(self, month: int, year: int) -> dict:
        """Extrae métricas principales del mes"""
        start_date, end_date = self._date_range(month, year)
        print(f"  📊 GA4: {start_date} → {end_date}")

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="totalUsers"),
                Metric(name="sessions"),
                Metric(name="averageSessionDuration"),
                Metric(name="engagementRate"),
                Metric(name="bounceRate"),
                Metric(name="screenPageViews"),
            ],
        )

        response = self.client.run_report(request)

        data = {
            'active_users': 0, 'total_users': 0, 'sessions': 0,
            'avg_session_duration': 0, 'engagement_rate': 0,
            'bounce_rate': 0, 'pageviews': 0,
        }

        if response.rows:
            row = response.rows[0]
            data['active_users'] = int(row.metric_values[0].value)
            data['total_users'] = int(row.metric_values[1].value)
            data['sessions'] = int(row.metric_values[2].value)
            data['avg_session_duration'] = float(row.metric_values[3].value)
            data['engagement_rate'] = float(row.metric_values[4].value) * 100
            data['bounce_rate'] = float(row.metric_values[5].value) * 100
            data['pageviews'] = int(row.metric_values[6].value)

        print(f"  ✅ Usuarios: {data['total_users']} | Sesiones: {data['sessions']}")
        return data

    def get_top_pages(self, month: int, year: int, limit: int = 10) -> list:
        """Obtiene las páginas más visitadas"""
        start_date, end_date = self._date_range(month, year)

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
        )

        response = self.client.run_report(request)

        pages = []
        for row in response.rows:
            pages.append({
                'path': row.dimension_values[0].value,
                'views': int(row.metric_values[0].value),
            })

        total_views = sum(p['views'] for p in pages) or 1
        for page in pages:
            page['percentage'] = round(page['views'] / total_views * 100, 1)

        print(f"  ✅ Top páginas: {len(pages)}")
        return pages

    def get_traffic_channels(self, month: int, year: int, limit: int = 10) -> list:
        """Obtiene el tráfico por canales de adquisición"""
        start_date, end_date = self._date_range(month, year)

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        )

        response = self.client.run_report(request)

        channels = []
        for row in response.rows:
            channels.append({
                'channel': row.dimension_values[0].value,
                'sessions': int(row.metric_values[0].value),
            })

        total_sessions = sum(c['sessions'] for c in channels) or 1
        for channel in channels:
            channel['percentage'] = round(channel['sessions'] / total_sessions * 100, 1)

        print(f"  ✅ Canales de tráfico encontrados: {len(channels)}")
        return channels

    def get_daily_users(self, month: int, year: int) -> list:
        """Serie diaria de usuarios y sesiones del mes"""
        start_date, end_date = self._date_range(month, year)

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="totalUsers"), Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
        )

        response = self.client.run_report(request)

        daily = []
        for row in response.rows:
            daily.append({
                'date': row.dimension_values[0].value,
                'users': int(row.metric_values[0].value),
                'sessions': int(row.metric_values[1].value),
            })

        print(f"  ✅ Serie diaria GA4: {len(daily)} días")
        return daily

    def get_top_countries(self, month: int, year: int, limit: int = 5) -> list:
        """Top países por usuarios"""
        start_date, end_date = self._date_range(month, year)

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name="country")],
            metrics=[Metric(name="totalUsers")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit,
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="totalUsers"), desc=True)],
        )

        response = self.client.run_report(request)

        countries = []
        for row in response.rows:
            countries.append({
                'country': row.dimension_values[0].value,
                'users': int(row.metric_values[0].value),
            })

        print(f"  ✅ Top países: {len(countries)}")
        return countries

    def get_device_metrics(self, month: int, year: int) -> dict:
        """Obtiene la distribución por tipo de dispositivo"""
        start_date, end_date = self._date_range(month, year)

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name="deviceCategory")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        )

        response = self.client.run_report(request)

        devices = {}
        for row in response.rows:
            devices[row.dimension_values[0].value] = int(row.metric_values[0].value)

        print(f"  ✅ Datos de dispositivos obtenidos: {list(devices.keys())}")
        return devices


def extract_ga4_data(property_id: str, month: int, year: int) -> dict:
    """Función principal — extrae todos los datos GA4"""
    cache_key = f"ga4_{property_id}_{year}_{month:02d}_v3"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        print("  ⚡ GA4: datos desde caché")
        return cached

    creds_path = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
    if not creds_path or not os.path.exists(creds_path):
        print("  ❌ No se encontró cappuccino-key.json")
        return {}

    extractor = GA4Extractor(creds_path, property_id)
    data = {
        'month': month,
        'year': year,
        'metrics': extractor.get_monthly_data(month, year),
        'top_pages': extractor.get_top_pages(month, year),
        'traffic_channels': extractor.get_traffic_channels(month, year),
        'devices': extractor.get_device_metrics(month, year),
        'daily_users': extractor.get_daily_users(month, year),
        'top_countries': extractor.get_top_countries(month, year),
    }
    cache_write(cache_key, data)
    return data


def extract_paid_landings(property_id: str, month: int, year: int) -> list:
    """Landings del canal Paid Search (sesiones, rebote, eventos clave) para el archivo de propuestas."""
    from google.analytics.data_v1beta.types import Filter, FilterExpression
    cache_key = f"ga4_paid_{property_id}_{year}_{month:02d}_v1"
    cached = cache_read(cache_key, month_ttl_hours(month, year))
    if cached:
        return cached.get('rows', [])

    creds_path = os.path.expanduser(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
    ext = GA4Extractor(creds_path, property_id)
    start, end = ext._date_range(month, year)
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="landingPage")],
        metrics=[Metric(name="sessions"), Metric(name="bounceRate"), Metric(name="keyEvents")],
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimension_filter=FilterExpression(filter=Filter(
            field_name="sessionDefaultChannelGroup",
            string_filter=Filter.StringFilter(value="Paid Search"))),
        limit=10,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    )
    rows = [{
        'landing': r.dimension_values[0].value,
        'sessions': int(r.metric_values[0].value),
        'bounce_rate': round(float(r.metric_values[1].value) * 100, 1),
        'key_events': round(float(r.metric_values[2].value), 1),
    } for r in ext.client.run_report(request).rows]
    cache_write(cache_key, {'rows': rows})
    return rows


if __name__ == "__main__":
    property_id = os.getenv('GA4_PROPERTY_ID_10DECO')
    if not property_id:
        print("❌ GA4_PROPERTY_ID_10DECO no configurado en .env")
        exit(1)
    data = extract_ga4_data(property_id, month=2, year=2026)
    if data:
        m = data['metrics']
        print(f"\n✅ Usuarios: {m['total_users']} | Sesiones: {m['sessions']} | Páginas: {m['pageviews']}")
