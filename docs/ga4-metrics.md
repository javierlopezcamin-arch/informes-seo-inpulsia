# Referencia: Google Analytics 4 Data API

## Métricas Disponibles en GA4

Esta es la referencia de qué datos la skill extrae de Google Analytics 4.

### Métricas de Usuario
| Métrica | Descripción | Uso en Informe |
|---------|-------------|-----------------|
| `activeUsers` | Usuarios activos en el período | Total de usuarios (sección Tráfico) |
| `newUsers` | Usuarios nuevos | Crecimiento de audiencia |
| `totalUsers` | Total de usuarios únicos | Total de usuarios (sección Tráfico) |
| `sessions` | Sesiones totales | Volumen de sesiones |

### Métricas de Engagement
| Métrica | Descripción | Uso en Informe |
|---------|-------------|-----------------|
| `engagementRate` | Porcentaje de sesiones con interacción | Calidad del tráfico |
| `sessionDuration` | Duración promedio de sesión | Calidad del tráfico |
| `averageSessionDuration` | Duración media en segundos | Tiempo de interacción (sección Tráfico) |
| `bounceRate` | Porcentaje de rebote | Calidad de contenido |
| `screenPageViews` | Vistas de página/pantalla | Tráfico total |

### Métricas de Conversión
| Métrica | Descripción | Uso en Informe |
|---------|-------------|-----------------|
| `conversions` | Conversiones totales | Si está configurado |
| `conversionRate` | Tasa de conversión | Rendimiento |
| `totalRevenue` | Ingresos totales | Si está configurado e-commerce |

---

## Dimensiones Disponibles

Las dimensiones permiten segmentar datos por:

| Dimensión | Descripción | Uso |
|-----------|-------------|-----|
| `pagePath` | Ruta de la página (ej: /blog/articulo) | Top 10 páginas |
| `pageTitle` | Título de la página | Tabla de páginas |
| `country` | País del usuario | Segmentación geográfica |
| `deviceCategory` | Desktop / Mobile / Tablet | Segmentación por dispositivo |
| `source` | Fuente del tráfico (organic, google, etc.) | Tráfico por canal |
| `medium` | Medio del tráfico (organic, referral, etc.) | Análisis de canal |
| `date` | Fecha en formato YYYYMMDD | Filtrado temporal |

---

## Período de Datos

Para extraer datos de un mes específico:

```python
# Ejemplo: Enero 2026
fecha_inicio = "20260101"
fecha_fin = "20260131"

# Ejemplo: Febrero 2026
fecha_inicio = "20260201"
fecha_fin = "20260228"
```

---

## Límites de API

- **Requests por día:** 25,000 (suficiente)
- **Rows por request:** Máximo 100,000
- **Rate limit:** Sin límite estricto

---

## Ejemplo de Extracción

```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    DateRange,
)

client = BetaAnalyticsDataClient()
request = RunReportRequest(
    property=f"properties/{property_id}",
    dimensions=[Dimension(name="pagePath")],
    metrics=[
        Metric(name="screenPageViews"),
        Metric(name="averageSessionDuration"),
    ],
    date_ranges=[DateRange(start_date="20260101", end_date="20260131")],
    limit=10,
)
response = client.run_report(request)

for row in response.rows:
    dimension_values = [header.name for header in response.dimension_headers]
    metric_values = [header.name for header in response.metric_headers]
    print(f"Página: {row.dimension_values[0].value}")
    print(f"Vistas: {row.metric_values[0].value}")
```

---

## Notas

- Las métricas están siempre disponibles (no requieren configuración especial)
- Los datos tienen latencia de 24-48 horas
- Los datos históricos están disponibles
- La skill usa la API Data API v1 (la más nueva y recomendada)
