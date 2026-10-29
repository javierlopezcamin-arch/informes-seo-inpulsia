# 📊 SEO Monthly Reports

Generador automático de informes SEO mensuales.  
Extrae datos reales de GA4 y Search Console → Genera presentación PPTX profesional.

---

## 📁 Estructura del proyecto

```
seo-monthly-reports-skill/
├── main.py                          ← Ejecutar este archivo
├── test_config.py                   ← Verificar configuración
├── .env                             ← Variables de entorno
├── scripts/
│   ├── extract_ga4.py               ← Extracción Google Analytics 4
│   ├── extract_search_console.py    ← Extracción Search Console
│   ├── analyze.py                   ← Análisis y narrativas
│   └── generate_pptx.py            ← Generación de presentación
├── credenciales/
│   └── (cappuccino-key.json)        ← Service Account JSON
└── README.md
```

---

## 🚀 Uso rápido

### 1. Verificar configuración
```bash
cd ~/Desktop/Claude\ proyectos\ local/INFORMES\ SEO/seo-monthly-reports-skill
python3 test_config.py
```

### 2. Generar informe
```bash
# Mes actual
python3 main.py

# Mes específico
python3 main.py --client 10deco --month 2 --year 2026

# Solo febrero
python3 main.py --month 2
```

El PPTX se guarda automáticamente en el **Escritorio**.

---

## ⚙️ Configuración (.env)

```env
GOOGLE_CLOUD_PROJECT_ID=cappuccino
GOOGLE_APPLICATION_CREDENTIALS=~/Desktop/Claude proyectos local/INFORMES SEO/credenciales/cappuccino-key.json
GOOGLE_DRIVE_FOLDER_ID=1A_GNTeZOWo1eaBAzkgaG2InX00s8PuoA

GA4_PROPERTY_ID_10DECO=372615008
SEARCH_CONSOLE_URL_10DECO=https://10deco.com/
```

---

## ➕ Agregar nuevo cliente

1. Agrega al `.env`:
```env
GA4_PROPERTY_ID_NUEVOCLIENTE=123456789
SEARCH_CONSOLE_URL_NUEVOCLIENTE=https://nuevocliente.com/
```

2. Da permisos al Service Account en GA4 y Search Console del nuevo cliente

3. Ejecuta:
```bash
python3 main.py --client nuevocliente --month 2 --year 2026
```

---

## 📋 Requisitos

```bash
pip install google-auth google-api-python-client google-analytics-data python-pptx python-dotenv python-docx
```

---

## 🔧 Solución de problemas

| Error | Solución |
|-------|----------|
| `403 permission` en GA4 | Verificar Service Account tiene rol Lector en GA4 Admin |
| `403 permission` en Search Console | Verificar Service Account añadido en SC > Configuración > Usuarios |
| `APIs not enabled` | Habilitar "Google Analytics Data API" y "Search Console API" en GCP |
| `cappuccino-key.json not found` | Verificar ruta en .env |
