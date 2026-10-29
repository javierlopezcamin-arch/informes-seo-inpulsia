# Plan: Google Ads por cliente + archivo de propuestas

Fecha: 2026-10-23 (v3) · Estado: **implementado el 2026-10-28** (ver "Estado de la implementación" al final)

## Enfoque: separar "generar" de "trabajar"

| | **Web de informes** (`app.py`) | **Proyecto de Claude "Clientes Inpulsia"** |
|---|---|---|
| Qué hace | Genera el **PDF del cliente** y el **archivo de propuestas** | Revisa y aplica cambios en la campaña de Ads y en la web |
| Cómo | Python + datos de APIs; IA mínima | Una conversación por cliente, con MCP de Google Ads y de Elementor |
| Coste | Tokens de API → se reduce al mínimo (Gemini gratis, sin Claude de pago) | Va con la tarifa de Claude (plan), no con la API |
| Cambia cosas | Nunca | Sí, siempre con confirmación |

Flujo mensual:
1. En la web: generar informes. Para los clientes marcados con Ads salen el PDF y `PROPUESTAS_<CLIENTE>_<MM>_<AAAA>.md`.
2. Enviar el PDF al cliente.
3. En el proyecto de Claude: abrir (o continuar) la conversación del cliente, adjuntar el archivo de propuestas y trabajar los cambios.

## Lo que ya existe (no se rehace)
| Pieza | Dónde | Estado |
|---|---|---|
| Credenciales Ads (developer token, OAuth, MCC) | `.env` + `generate_ads_refresh_token.py` | ✅ |
| Extractor Ads: totales + top 8 campañas | `scripts/extract_google_ads.py` | ✅ básico |
| Customer ID por cliente | `.env`, fichas de `app.py` | ✅ solo Piscinas Riviera |
| Sección Google Ads en el PPTX | `generate_pptx.py` / `_v2.py` | ✅ siempre muestra conversiones (hay que cambiarlo) |
| Servidores MCP de Elementor por web | Claude | ✅ varios clientes |

---

# Parte A — Web de informes

## A1. Marca por cliente
- `ADS_EN_INFORME_<CLIENTE>=true` en `.env` (solo tiene efecto con Customer ID).
- Checkbox *"Incluir Google Ads y archivo de propuestas"* en *Añadir* / *Editar cliente* y pill "ADS" en la lista.
- Se quita `ads` del multiselect de secciones: manda la marca. "Generar todos" lo aplica solo a los marcados.
- `main.py`: si está marcado, añade `ads` a las secciones y genera el archivo. Flag `--no-propuestas`.

## A2. Extractor de Google Ads ampliado (`extract_google_ads.py`, caché `_v2`)
| Dato | Recurso GAQL |
|---|---|
| Acciones de conversión (nombre, tipo, estado, principal) | `conversion_action` |
| Conversiones por acción en el mes | `campaign` + `segments.conversion_action_name` |
| CPA / coste por conversión por campaña | calculado |
| Top 25 términos de búsqueda (coste, clics, conv.) | `search_term_view` |
| Keywords con Quality Score bajo (≤ 5) | `keyword_view` + `quality_info` |
| URL final de los anuncios | `ad_group_ad.ad.final_urls` |
| Cuota de impresiones perdida (presupuesto / ranking) | `search_budget_lost_impression_share`, `search_rank_lost_impression_share` |

**Estado de conversiones:** `sin_configurar` (sin acciones activas) · `sin_datos` (acciones pero 0 en 90 días) ·
`sin_conversiones_mes` · `ok`.

## A3. PDF del cliente
- Estado `ok`: sección Ads con conversiones por acción y CPA.
- Cualquier otro estado: solo *Inversión · Impresiones · Clics · CTR/CPC*. Sin KPI, columna ni
  menciones a conversiones (la nota IA recibe los datos sin ellas).

## A4. Fuentes para las propuestas (sin coste de tokens)
- **Contenido publicado** (`extract_wp_content.py`): REST pública de WordPress (`/wp-json/wp/v2/posts`, `/pages`)
  o sitemaps si está cerrada. Para no repetir posts y proponer enlaces internos reales.
- **Etiquetas instaladas** (`check_tracking.py`): HTML de la home y de la landing de Ads → GA4 (`G-`),
  Ads (`AW-`), GTM, Consent Mode, tipo de formulario.
- **Google Trends** (`extract_trends.py`): `pytrends` con caché de 7 días; si falla, se omite.
- **GA4 y Search Console**: lo que ya extrae el informe.

## A5. Archivo de propuestas (`generate_propuestas.py`)
Pensado para **leerlo Claude en el proyecto**: compacto, con datos concretos y tareas claras.

**IA mínima:** las señales y tablas salen de reglas en Python. Solo los 2 títulos y la estructura de
los posts usan **1 llamada a Gemini (gratis)**. **Sin fallback a Claude de pago:** si no hay cupo, el
archivo sale con las señales y una tarea *"proponer 2 posts"* para hacerla en el proyecto.

Siempre con **datos reales** (copia anterior al ajuste +10%…+50%). Se guarda en `OUTPUT_DIR/internos/`
(separado de los PDF) y, si se sube a Drive, en la subcarpeta `INTERNO` del cliente.

### Estructura
```
# Propuestas — <Cliente> — <Mes Año>   (INTERNO)
Web · Customer ID de Ads · servidor MCP de Elementor (si se conoce)

## 1. Resumen de datos           ← 6-8 líneas con cifras: Ads, SC, GA4, Trends
## 2. Propuestas de post para el blog (2)
   Título (≤60) + variante · keyword principal y secundarias (con fuente y cifra)
   intención · slug · meta description · H1 + 5-7 H2 · 2-3 enlaces internos reales · CTA
   por qué ahora · "actualizar en vez de crear" si ya hay un post parecido
## 3. Palabras clave priorizadas (máx. 20)
   | Keyword | Fuente | Impr./clics | Pos. orgánica | Conv. Ads | Uso: post / Ads / negativa |
## 4. Google Ads: datos del mes
   Campañas · términos de búsqueda · QS bajo · cuota perdida · landing y su rebote en GA4
## 5. Seguimiento de conversiones   ← solo si el estado no es "ok"
   Diagnóstico + qué hay instalado en la web + pasos recomendados
## 6. Tareas para la conversación de Claude
   - [ ] Revisar la landing <URL> frente a los titulares del anuncio (MCP Elementor)
   - [ ] Proponer negativas a partir de la tabla de términos (MCP Ads)
   - [ ] Configurar la conversión <tipo> según la sección 5
   - [ ] Crear como borrador el post 1 / post 2
   - [ ] Proponer 15 titulares (≤30) y 4 descripciones (≤90) para los RSA
```

Reglas de las señales:
| Señal | Regla |
|---|---|
| Tema de post con demanda probada | Término de Ads con clics que no tiene post/página posicionando en SC |
| Hueco informacional | Query de SC con intención informativa en posición > 10 |
| Tendencia | Consulta "en subida" en Trends o pico estacional en 2-3 meses |
| Ya existe | Título o slug de post publicado muy parecido |
| Negativa | Coste > umbral y 0 conversiones (solo con estado `ok`) |
| Ads paga lo que el orgánico ya gana | Término de Ads con posición orgánica ≤ 3 |
| Landing que no retiene | Landing de *Paid Search* con rebote alto en GA4 |

## A6. Web
- Botón **"Archivo de propuestas"** en "Informe listo", separado de PDF/PPTX.
- En "Generar todos", aviso de cuántos archivos se generan y cuántas llamadas de Gemini consumen.

---

# Parte B — Proyecto de Claude "Clientes Inpulsia"

## B1. Montaje (una vez)
- **Proyecto** en Claude con unas instrucciones fijas (borrador en B3).
- **Conectores:**
  - **Google Ads**: un MCP con acceso a la MCC. Opciones: el MCP oficial de Google Ads (código abierto)
    con las mismas credenciales del `.env`, o el agente de Ads ya instalado (Adspirer, de pago, que hay que autorizar).
    Elegir según si hace falta solo leer o también aplicar cambios.
  - **Elementor**: los servidores MCP por web que ya tienes.
- Con muchos servidores de Elementor cargados a la vez, cada conversación gasta más contexto: **activar
  solo el conector de la web de ese cliente** en su conversación.

## B2. Uso mensual
- **Una conversación por cliente**, que se reutiliza mes a mes (así recuerda lo hecho antes).
- Al empezar el mes: adjuntar el `PROPUESTAS_…md` nuevo y pedir *"trabajemos las tareas de la sección 6"*.

## B3. Borrador de instrucciones del proyecto
```
Trabajas para Inpulsia en la web y la campaña de Google Ads de un cliente por conversación.
Cada mes recibes un archivo PROPUESTAS_<cliente>_<mes>.md con datos reales y tareas.
- Usa solo el conector de Elementor de la web de este cliente y la cuenta de Ads de su Customer ID.
- Antes de cambiar algo, lee el estado actual, explica el cambio y espera mi confirmación.
- Web: los posts y páginas nuevas, siempre como borrador. Nunca publiques sin mi OK.
- Ads: no cambies presupuestos, pujas ni estados de campaña sin confirmación expresa.
  Cualquier campaña nueva se crea en pausa.
- Si no hay conversiones, la prioridad es configurar la medición antes de optimizar por CPA.
- No inventes cifras: usa las del archivo o las que leas de los conectores.
- Al terminar, haz un resumen de lo hecho y lo pendiente para el próximo mes.
```

---

## Orden de implementación
| Fase | Contenido | Prueba |
|---|---|---|
| 1 | A1 + A2 + A3 | Piscinas Riviera: PDF sin conversiones si no las tiene |
| 2 | A4 (contenido publicado, etiquetas, Trends) | Datos de Piscinas Riviera |
| 3 | A5 + A6 | `internos/PROPUESTAS_PISCINAS_RIVIERA_09_2026.md` desde la web |
| 4 | B1-B3: montar el proyecto y probarlo con un cliente | Conversación de Piscinas Riviera con el archivo |

## Coste
- **Web:** +1 llamada a Gemini (gratis) por cliente marcado. Sin Claude de pago en este paso.
- **Proyecto de Claude:** va con el plan. Para reducir uso: archivo compacto (tablas limitadas a 20-25 filas),
  un solo conector de Elementor activo y conversación por cliente en vez de una sola para todos.

## Requisitos antes de empezar
- [ ] Customer ID de cada cliente a marcar (hoy solo Piscinas Riviera).
- [x] Confirmar que las acciones de conversión se pueden leer con el developer token actual (2026-10-29, acceso Explorador).
- [x] `pip install --break-system-packages pytrends` en `/opt/homebrew/bin/python3`.
- [x] MCP de Google Ads para el proyecto: lectura con `seo-inpulsia`; cambios a mano o con un agente de Ads.

## Estado de la implementación (2026-10-28)
| Pieza | Archivo | Estado |
|---|---|---|
| Marca por cliente `ADS_EN_INFORME_<CLIENTE>` | `extract_google_ads.ads_enabled_for`, `main.py`, `app.py` | ✅ Piscinas Riviera marcado |
| Extractor Ads v2 (conversiones, términos, QS, URLs, cuota, puja) | `extract_google_ads.py` | ✅ probado con Piscinas Riviera (sept. 2026) el 2026-10-29 con acceso **Explorador** (2.880 operaciones/día en cuentas reales). El Basic queda pendiente de la verificación de marca del proyecto `cappuccino` |
| PDF sin conversiones si el estado no es `ok` | `analyze.py`, `generate_pptx.py`, `generate_pptx_v2.py` | ✅ |
| Contenido publicado / etiquetas / Trends | `extract_wp_content.py`, `check_tracking.py`, `extract_trends.py` | ✅ probado con Piscinas Riviera y DTC Oral |
| Detalle SC (250 queries) y landings Paid Search de GA4 | `extract_search_console.extract_sc_queries`, `extract_ga4.extract_paid_landings` | ✅ |
| Archivo de propuestas (señales + 1 llamada Gemini, sin Claude de pago) | `generate_propuestas.py` | ✅ probado de principio a fin |
| Subida a Drive como Google Doc en `<CLIENTE>/INTERNO` | `upload_drive.upload_internal_doc` | ⚠️ sin probar (no se ha subido nada) |
| Web: checkbox, aviso de tanda, botón de descarga | `app.py` | ✅ compila; sin probar en el navegador |
| MCP: `get_google_ads_overview`, `get_propuestas`, `list_clientes` con Ads | `mcp_server.py` | ✅ |
| Guía del proyecto de Claude | `docs/PROYECTO_CLAUDE_CLIENTES.md` | ✅ |

Las señales detectan preguntas en castellano y catalán, y no cuentan como canibalización la misma URL con otra barra
final o en otro idioma. Las URLs indexadas con y sin barra final se señalan aparte, como duplicado técnico.
