# Referencia: Google Search Console API

## Datos Disponibles en Search Console

Esta es la referencia de qué datos la skill extrae de Google Search Console.

### Métricas Principales
| Métrica | Descripción | Uso en Informe |
|---------|-------------|-----------------|
| `impressions` | Número de veces que aparece en resultados | Sección 2: Google Search Console |
| `clicks` | Número de clics en resultados | Sección 2: Google Search Console |
| `ctr` | Click-Through Rate (clics/impresiones) | Sección 2: Google Search Console |
| `position` | Posición media en resultados | Sección 2: Google Search Console |

---

## Dimensiones de Análisis

Se pueden segmentar datos por:

| Dimensión | Descripción | Uso |
|-----------|-------------|-----|
| `query` | Palabra clave de búsqueda | Top 10 keywords (sección 2) |
| `page` | URL de la página | Top 10 páginas (sección 2) |
| `country` | País del buscador | Segmentación geográfica |
| `device` | Desktop / Mobile / Tablet | Segmentación por dispositivo |
| `searchType` | Web / Image / Video | Tipo de búsqueda |
| `date` | Fecha YYYY-MM-DD | Filtrado temporal |

---

## Período de Datos

Para extraer datos de un mes específico:

```
Enero 2026: 2026-01-01 to 2026-01-31
Febrero 2026: 2026-02-01 to 2026-02-28
```

---

## Data Freshness

- **Latencia:** 2-3 días (los datos de hoy se ven hasta en 2-3 días)
- **Historial:** Disponible desde que la propiedad fue añadida a Search Console
- **Precisión:** Datos agregados, puede haber pequeñas variaciones

---

## Límites de API

- **Requests:** 40,000 por día (amplio)
- **Rows por request:** Máximo 25,000
- **Rate limit:** 500 requests por minuto

---

## Ejemplo de Extracción

```python
from google.auth.transport.requests import Request
from webmasters_v3 import build

service = build('webmasters', 'v3', credentials=credentials)

request_body = {
    'startDate': '2026-01-01',
    'endDate': '2026-01-31',
    'dimensions': ['query', 'page'],
    'rowLimit': 10,
}

response = service.searchanalytics().query(
    siteUrl='sc-domain:ejemplo.com',
    body=request_body
).execute()

for row in response.get('rows', []):
    print(f"Keyword: {row['keys'][0]}")
    print(f"Página: {row['keys'][1]}")
    print(f"Impresiones: {row['impressions']}")
    print(f"Clics: {row['clicks']}")
    print(f"CTR: {row['ctr']:.2%}")
    print(f"Posición: {row['position']:.1f}")
```

---

## Estructura de Respuesta

```python
{
    'rows': [
        {
            'keys': ['keyword1', '/pagina1'],  # Dimensiones
            'clicks': 15,
            'impressions': 100,
            'ctr': 0.15,
            'position': 8.5
        },
        # ... más filas
    ]
}
```

---

## Notas Importantes

1. **CTR es fraccional:** 0.15 = 15%, se debe convertir para mostrar
2. **Posición es promedio:** 8.5 significa posición media entre 8 y 9
3. **Query vs Page:** Se puede pedir por keyword O por página, no juntos
4. **Datos combinados:** Para keyword + página, hacer 2 requests separados
5. **Filtros:** Search Console permite filtros pero la API es más limitada

---

## Casos de Uso en la Skill

### Top 10 Keywords
```
Dimensión: 'query'
Métricas: impressions, clicks, ctr, position
Ordenado por: impressions DESC
Límite: 10 filas
```

### Top 10 Páginas
```
Dimensión: 'page'
Métricas: impressions, clicks, ctr
Ordenado por: clicks DESC
Límite: 10 filas
```

### Métricas Globales
```
Sin dimensión
Métricas: impressions, clicks, ctr, position
Período: Mes completo
```

---

## URLs de Sitio en Search Console

### Formato correcto
- Propiedad de dominio: `sc-domain:ejemplo.com`
- Propiedad de URL: `https://ejemplo.com/`
- Con subdominio: `sc-domain:blog.ejemplo.com`

**La skill acepta ambos formatos, pero se prefiere `sc-domain:` para comodidad.**
