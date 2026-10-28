# SEO Monthly Reports Skill

Skill para Claude que automatiza 100% la generación de informes SEO mensuales en Google Slides extrayendo datos de Google Analytics 4 y Google Search Console.

## 🎯 Objetivo

Convertir un proceso manual repetitivo (extraer datos, redactar análisis, crear presentación) en una automatización completa:

```
URL + Mes → [Skill] → Presentación profesional en Google Slides
```

## ⚡ Características

- ✅ **Automatización completa:** Solo proporciona URL + mes
- ✅ **Extracción de datos en tiempo real:** GA4 + Search Console
- ✅ **Análisis profesional:** Redacción de explicaciones SEO
- ✅ **Google Slides:** Presentación con diseño profesional
- ✅ **Google Drive:** Organización automática por mes/cliente
- ✅ **Seguro:** OAuth + credenciales en variables de entorno

## 📋 Contenido del Proyecto

```
seo-monthly-reports-skill/
├── SKILL.md                     # Documentación oficial de la skill
├── claude.md                    # Contexto del proyecto
├── README.md                    # Este archivo
│
├── references/
│   ├── setup-guide.md          # Guía paso a paso de configuración
│   ├── ga4-metrics.md          # Referencia de métricas GA4
│   └── search-console-api.md   # Referencia de Search Console
│
├── scripts/
│   ├── main.py                 # Orquestador principal
│   ├── extract_ga4.py          # Extrae datos de GA4
│   ├── extract_search_console.py # Extrae datos de Search Console
│   ├── generate_slides.py      # Crea presentación en Slides
│   ├── analyze.py              # Análisis e interpretación
│   └── config.py               # Configuración centralizada
│
└── assets/
    ├── template.json           # Template de diapositivas
    └── colors.json             # Paleta de colores estándar
```

## 🚀 Inicio Rápido

### 1. Leer la Documentación
Comienza con estos documentos en este orden:
1. **SKILL.md** - Entender qué hace la skill
2. **references/setup-guide.md** - Configuración técnica (20-30 min)
3. **references/ga4-metrics.md** y **search-console-api.md** - Referencia técnica

### 2. Configuración Inicial (Una sola vez)
Sigue la **guía paso a paso en `references/setup-guide.md`**:
- Crear Google Cloud Project
- Habilitar APIs
- Crear Service Account
- Otorgar permisos en Analytics y Search Console
- Configurar variables de entorno

### 3. Usar la Skill
Una vez configurado, usa la skill así:
```
"Crea informe SEO para ejemplo.com, febrero 2026"
```

La skill se encargará del resto automáticamente.

## 📖 Documentación

| Archivo | Propósito |
|---------|-----------|
| **SKILL.md** | Documentación oficial - qué hace, cómo funciona, parámetros |
| **claude.md** | Contexto interno del proyecto para Claude |
| **setup-guide.md** | Guía paso a paso para configuración de Google Cloud |
| **ga4-metrics.md** | Referencia de métricas y dimensiones de Google Analytics |
| **search-console-api.md** | Referencia de datos disponibles en Search Console |

## 🔧 Requisitos Técnicos

### Antes de configurar
- Cuenta Google con acceso a Google Analytics 4
- Acceso a Google Search Console del sitio
- Acceso a Google Drive

### Dependencias Python
```bash
pip install \
  google-auth \
  google-auth-oauthlib \
  google-auth-httplib2 \
  google-analytics-data \
  google-api-python-client \
  python-dotenv
```

### Variables de Entorno Requeridas
```
GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/credentials.json
GA4_PROPERTY_ID=tu_property_id
SEARCH_CONSOLE_SITE_URL=sc-domain:ejemplo.com
GOOGLE_DRIVE_FOLDER_ID=tu_folder_id
```

## 📊 Estructura de Informe

Cada presentación generada tiene 10 diapositivas:

1. **Portada** - Título "INFORME SEO" + mes/año
2-3. **Tráfico Web** - Usuarios, tiempo interacción, top páginas
4-6. **Google Search Console** - Impresiones, clics, keywords, posiciones
7-8. **SEO Off-Page** - Backlinks, dominios de referencia
9-10. **Apariciones en IA** - Plataformas donde aparece el sitio

## 🔒 Seguridad

- **OAuth 2.0:** Autenticación segura sin contraseñas
- **Service Account:** Credenciales separadas, no tu cuenta personal
- **Variables de entorno:** Credenciales no en código
- **.gitignore:** Protege archivos sensibles

**IMPORTANTE:** No compartas el archivo `credentials.json` ni el `.env`

## 🐛 Troubleshooting

### Problema: "Error: Authentication failed"
→ Revisa que el JSON esté en la ruta correcta
→ Verifica permisos del Service Account

### Problema: "Property not found"
→ Confirma el GA4 Property ID es correcto
→ Verifica que el Service Account tiene acceso

### Problema: "No data available"
→ El período podría no tener datos
→ Verifica que GA4 y Search Console están activos

Para más solución de problemas, ve a **SKILL.md** sección "Solución de Problemas".

## 📈 Roadmap

- [ ] Comparativas mes anterior
- [ ] Detectar apariciones en IA automáticamente
- [ ] Exportar a PDF
- [ ] Dashboard interactivo
- [ ] Alertas de cambios significativos
- [ ] Soporte multiidioma

## 📝 Licencia y Uso

Este proyecto es para uso personal. Todos los datos extraídos son privados y no se comparten.

## 📧 Contacto

Preguntas o sugerencias: Crear issue o contactar a Javi (propietario del proyecto)

---

**Última actualización:** Enero 2026  
**Versión:** 1.0
