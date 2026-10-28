# SEO Monthly Reports Skill - Contexto del Proyecto

## Objetivo
Crear una skill que automatiza 100% la generación de informes SEO mensuales en Google Slides extrayendo datos de Google Analytics 4 y Google Search Console.

## Propietario
Javi (usuario)

## Estado
En desarrollo - Fase 1: Crear SKILL.md

## Flujo Principal
1. Usuario pasa: URL del cliente + mes
2. Skill extrae automáticamente datos de GA4 + Search Console
3. Skill genera presentación en Google Slides
4. Skill guarda en Google Drive organizado por mes/cliente
5. Skill retorna enlace a la presentación

## Requisitos Clave
- ✅ Automatización total (sin intervención manual)
- ✅ Seguridad: OAuth + variables de entorno
- ✅ Estructura idéntica al modelo actual (INFORME_SEO_SOMOSIERRA_CLÍNICA_DENTAL_-_01_2026.pptx)
- ✅ 4 secciones: Tráfico Web, Google Search Console, SEO Off-Page, Apariciones en IA
- ✅ Tono profesional pero accesible
- ✅ Solo datos del mes actual (sin comparativas)

## APIs Necesarias
1. Google Analytics Data API v1 - Extraer tráfico, usuarios, páginas top
2. Google Search Console API - Extraer impresiones, clics, CTR, keywords, posiciones
3. Google Slides API - Crear y actualizar presentaciones

## Autenticación
- Tipo: OAuth 2.0 con Service Account
- Almacenamiento: Variables de entorno (.env)
- Plataforma: Google Cloud Console (gratuito)

## Estructura de Carpetas del Proyecto
```
seo-monthly-reports-skill/
├── SKILL.md                    # Documentación principal de la skill
├── claude.md                   # Este archivo (contexto del proyecto)
├── scripts/
│   ├── setup.py               # Setup de autenticación y configuración
│   ├── extract_ga4.py         # Extrae datos de Google Analytics
│   ├── extract_search_console.py # Extrae datos de Search Console
│   ├── generate_slides.py      # Genera presentación en Google Slides
│   └── main.py                # Orquestador principal
├── references/
│   ├── ga4-metrics.md         # Referencia de métricas GA4
│   ├── search-console-api.md  # Referencia de Search Console API
│   └── setup-guide.md         # Guía paso a paso para configuración
└── assets/
    ├── template.json          # Template de diapositivas
    └── colors.json            # Colores estándar
```

## Próximos Pasos
1. ✅ Crear SKILL.md completo con documentación
2. ⏳ Crear scripts Python para extracción de datos
3. ⏳ Crear guía de configuración para Google Cloud
4. ⏳ Testing con cliente real
5. ⏳ Optimizaciones finales

## Notas Técnicas
- Python 3.8+
- Librerías: google-auth, google-analytics-data, google-search-console, google-slides
- Sin dependencias externas complejas
- Rate limiting: Search Console permite ~10 req/seg (suficiente)

## Decisiones Tomadas
- OAuth/Service Account (máxima seguridad)
- Google Cloud Console (gratuito)
- Variables de entorno para credenciales (simple y seguro)
- Una presentación por cliente por mes
- Automatización total (sin revisión manual)
- Diseño idéntico al modelo actual

## Contacto / Preguntas
Dirigirse a: Javi (en este proyecto)
