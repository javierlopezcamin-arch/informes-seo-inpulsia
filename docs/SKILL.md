---
name: seo-monthly-reports
description: Genera automáticamente informes SEO mensuales en Google Slides extrayendo datos de Google Analytics 4 y Google Search Console. Proporciona URL del cliente + mes, y la skill extrae datos, analiza métricas y crea una presentación profesional con 4 secciones (Tráfico Web, Google Search Console, SEO Off-Page, Apariciones en IA). Úsalo cada vez que necesites un informe SEO completo para un cliente.
---

# SEO Monthly Reports - Skill

Automatiza 100% la generación de informes SEO mensuales profesionales en Google Slides usando datos en tiempo real de Google Analytics 4 y Google Search Console.

## Cómo Funciona

### Entrada
Proporciona al usuario:
1. **URL/dominio del cliente** (ej: somosierra.es, ejemplo.com)
2. **Mes** (enero, febrero, etc. o número 01, 02...)
3. **Año** (opcional, por defecto año actual)

**Ejemplo de uso:**
```
"Crea el informe SEO para somosierra.es, marzo 2026"
"Genera informe SEO de ejemplo.com enero 2026"
```

### Proceso Automático
1. ✅ Conecta a Google Analytics 4 usando credenciales almacenadas
2. ✅ Extrae datos de tráfico, usuarios, páginas top para el período
3. ✅ Conecta a Google Search Console
4. ✅ Extrae impresiones, clics, CTR, posiciones, keywords
5. ✅ Analiza e interpreta todos los datos
6. ✅ Redacta explicaciones profesionales y claras
7. ✅ Genera presentación en Google Slides con diseño profesional
8. ✅ Guarda en Google Drive (carpeta organizada por mes/cliente)
9. ✅ Retorna enlace a la presentación creada

### Salida
**Presentación en Google Slides** con estructura fija:

- **Portada:** Título "INFORME SEO" + mes/año
- **Sección 1 (2-3 diapositivas):** Tráfico Web
  - Narrativa de usuarios, tiempo interacción, cualificación del tráfico
  - Gráfico de top 10 páginas visitadas
  
- **Sección 2 (3 diapositivas):** Google Search Console
  - Métricas: impresiones, clics, CTR, posición media
  - Tabla con top 10 keywords (posición, impresiones, clics)
  - Tabla con top 10 páginas (rendimiento en Google)
  - Análisis narrativo
  
- **Sección 3 (2 diapositivas):** SEO Off-Page
  - Backlinks activos
  - Dominios de referencia
  - Análisis narrativo
  
- **Sección 4 (2 diapositivas):** Apariciones en IA
  - Plataformas donde aparece (ChatGPT, Gemini, Perplexity, etc.)
  - Análisis de nuevas apariciones

**Total:** 10 diapositivas (idéntico al modelo actual)

---

## Antes de Usar: Configuración Inicial

La skill requiere acceso a Google Analytics 4 y Google Search Console a través de OAuth. Necesitas completar estos pasos **una sola vez**:

### Paso 1: Crear Google Cloud Project
1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Crea un nuevo proyecto llamado "SEO Monthly Reports"
3. Anota el Project ID

### Paso 2: Habilitar APIs
En Google Cloud Console, habilita estas APIs:
- Google Analytics Data API v1
- Google Search Console API
- Google Slides API
- Google Drive API

### Paso 3: Crear Service Account
1. Ve a "Service Accounts" en Google Cloud Console
2. Crea una nueva service account con nombre "seo-reports"
3. Crea una clave JSON
4. Descarga el JSON y guárdalo en lugar seguro

### Paso 4: Otorgar Permisos
En Google Analytics y Search Console (para cada cliente):
1. Agrega el email de la service account como usuario
2. Dales permisos de "Editor" o "Lector" (mínimo necesario)

### Paso 5: Guardar Credenciales
Guarda el JSON en variables de entorno:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/ruta/al/archivo.json"
```

O crea un `.env`:
```
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
GOOGLE_DRIVE_FOLDER_ID=tu_folder_id_aqui
```

**Nota:** No compartas nunca las credenciales JSON. Mantenlas seguras como una contraseña.

---

## Parámetros y Configuración

### Variables Requeridas
- `client_domain`: Dominio del cliente (ej: somosierra.es)
- `month`: Mes en número (01-12) o nombre (enero, febrero, etc.)
- `year`: Año (ej: 2026)
- `ga4_property_id`: ID de propiedad en Google Analytics 4
- `search_console_url`: URL en Search Console (debe coincidir con ga4_property_id)

### Carpetas en Google Drive
La skill organiza automáticamente los informes así:
```
Mi Drive/
└── Informes SEO/
    ├── Enero 2026/
    │   ├── somosierra.es/
    │   │   └── INFORME_SEO_SOMOSIERRA_ENERO_2026.pptx
    │   └── ejemplo.com/
    │       └── INFORME_SEO_EJEMPLO_ENERO_2026.pptx
    ├── Febrero 2026/
    │   └── ...
    └── ...
```

---

## Datos Que Extrae

### De Google Analytics 4
- Usuarios totales del período
- Tiempo de interacción promedio (en segundos)
- Top 10 páginas más visitadas (con número de vistas)
- Tasa de rebote (si aplica)
- Conversiones (si está configurado)

### De Google Search Console
- Impresiones totales (cuántas veces aparece en Google)
- Clics totales (cuántas veces hace clic el usuario)
- CTR promedio (Click-Through Rate)
- Posición media en búsqueda
- Top 10 keywords/consultas (con impresiones, clics, posición)
- Top 10 páginas (con impresiones, clics, CTR)

### Análisis Añadido
- Interpretación de tendencias
- Contexto de lo que significa cada métrica
- Identificación de hitos positivos (Top 10, posiciones mejoradas, etc.)
- Recomendaciones implícitas en la redacción

---

## Tono y Estilo de Redacción

La skill redacta las explicaciones con:

- **Tono:** Profesional pero accesible
- **Formato:** Párrafos cortos (máximo 2-3 por sección)
- **Lenguaje:** Directo, sin florituras
- **Referencias:** Números específicos destacados
- **Análisis:** Qué significa cada métrica para SEO

### Ejemplo de Redacción
```
"En el mes de enero el volumen de tráfico total del sitio web se sitúa 
en los 70 usuarios. El tiempo de interacción medio aumenta hasta los 
43 segundos, lo que hace pensar que se trata de un tráfico más 
cualificado que en meses anteriores."
```

---

## Casos de Uso

### Caso 1: Informe Básico
```
Usuario: "Crea informe SEO para cliente.com, febrero 2026"
→ Skill extrae datos → Genera presentación → Guarda en Drive
→ Retorna: "Presentación guardada en: https://docs.google.com/..."
```

### Caso 2: Múltiples Clientes (mismo mes)
```
Usuario: "Necesito informes de enero 2026 para 3 clientes"
→ Skill genera 3 presentaciones (una por cliente)
→ Todas organizadas en la misma carpeta
```

### Caso 3: Cliente Nuevo (sin historial)
```
Si el cliente es nuevo sin datos históricos:
→ Skill aún genera la presentación
→ Incluye nota: "Datos limitados (primer mes)"
→ Estructura completa lista para meses futuros
```

---

## Limitaciones y Notas

- **Tiempo de procesamiento:** 2-5 minutos por informe (depende de volumen de datos)
- **Rate limiting:** Google Search Console permite ~10 solicitudes/seg (sin problemas)
- **Datos históricos:** Solo extrae del período específico (mes actual, sin comparativas)
- **Errores de autenticación:** Si las credenciales expiran, mostrará error claro
- **Apariciones en IA:** Requiere búsqueda manual o integración con servicio externo

---

## Solución de Problemas

### "Error: Authentication failed"
→ Revisa que el JSON de credenciales esté en la ruta correcta
→ Verifica que el Service Account tenga permisos en GA4 y Search Console

### "Error: Property not found"
→ Revisa que el GA4 Property ID sea correcto
→ Confirma que el Service Account tiene acceso a esa propiedad

### "Error: No data available"
→ El período podría no tener datos registrados
→ Verifica que las cuentas estén activas y correctamente vinculadas

### "La presentación se genera pero sin gráficos"
→ Algunos gráficos se generan basados en datos
→ Si no hay datos suficientes, se muestran tablas en su lugar

---

## Próximas Versiones (Roadmap)

- [ ] Agregar comparativa mes anterior (trends)
- [ ] Integración con herramientas de IA para detectar apariciones automáticamente
- [ ] Exportar a PDF además de Slides
- [ ] Dashboard interactivo de métricas
- [ ] Alertas automáticas de cambios significativos
- [ ] Soporte para múltiples idiomas

---

## Referencia Técnica

### Librerías Utilizadas
```python
google-auth
google-auth-oauthlib
google-auth-httplib2
google-analytics-data
google-api-python-client  # Para Slides API y Drive API
python-dotenv             # Para variables de entorno
```

### Instalación
```bash
pip install google-auth google-analytics-data google-api-python-client python-dotenv
```

### Estructura del Código
```
scripts/
├── main.py                    # Orquestador principal
├── extract_ga4.py            # Extrae datos de GA4
├── extract_search_console.py # Extrae datos de Search Console
├── generate_slides.py        # Crea presentación
├── analyze.py                # Análisis e interpretación
└── config.py                 # Configuración y constantes
```

---

## Soporte y Feedback

Para reportar bugs, sugerir mejoras o preguntas:
- Revisa este documento (SKILL.md)
- Consulta la guía de configuración en `references/setup-guide.md`
- Reporta errores específicos con detalles de entrada y output

---

## Versión
**v1.0** - Enero 2026
- Versión inicial
- 4 secciones básicas
- Automatización completa
- Google Slides como output
