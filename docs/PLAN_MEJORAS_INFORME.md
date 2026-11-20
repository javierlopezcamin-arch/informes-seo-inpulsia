# Plan de mejoras del informe (nov 2026)

Objetivo: un informe más positivo y orientado al crecimiento, con seguimiento de las palabras que le importan al cliente.

## 1. Quitar «palabras que bajan»
- `generate_pptx.py:1310` `add_keyword_movements_slide`: quitar la columna «Bajaron» y la frase «… y N bajaron». La diapositiva pasa a «Keywords que suben» + «Keywords nuevas» (`new` ya se calcula en `analyze.py:462`).
- Revisar otros puntos negativos de cara al cliente: la diapositiva de páginas que pierden clics (`_decay_slide_data`) y «Posiciones perdidas» en destacados (`analyze.py:401`). Propuesta: mover el decay solo a PROPUESTAS (ya está ahí) y quitarlo del informe.
- El resumen para la IA (`analyze.py:688`, «Bajan: …») se mantiene interno o se quita para que no lo mencione.

## 2. Evolución de las palabras clave objetivo
- Lista por cliente en el `.env`: `KEYWORDS_OBJETIVO_<CLIENTE>=piscinas alicante, construcción piscinas, …` (y casilla/campo en la web más adelante).
- Search Console devuelve hasta 16 meses: por cada palabra, consulta filtrada por `query` mes a mes (posición media, clics, impresiones) de los últimos 6-12 meses. No depende de que esté en el top de la consulta general.
- Diapositiva nueva: tabla «Palabra · posición hace 6 meses · ahora · mejor posición» + gráfico de líneas (eje invertido: arriba = mejor).
- Si una palabra objetivo empeora, se muestra sin flecha roja (solo posición actual) y la tarea va a PROPUESTAS.

## 3. Palabras clave que dominamos
- Consultas en top 3 (o top 5) con impresiones mínimas: número total, evolución del número mes a mes y la lista de las principales.
- KPI positivo para portada/destacados: «Dominamos 24 búsquedas en el top 3 (+5 vs. mes anterior)».

## 4. Seguimiento de puntuación (Rank Math)
Herramientas útiles de Rank Math MCP (solo lectura):
- `get-seo-scores`: puntuación SEO de cada post → media de la web y nº de posts en verde (≥80). Evolución mes a mes = «salud SEO del contenido».
- `audit-site-seo`: auditoría de la web → nº de pruebas superadas.
- `get-top-keywords`: lo mismo que ya sacamos de Search Console (no aporta).
- `get-ai-visibility-*`: visibilidad en IA (menciones, citas), pero exige el plan Content AI.
- No hay rastreador de posiciones propio ni edición de slug/meta/categorías/imagen por post.

Problema: el informe se genera en Python desde la web, y Rank Math MCP vive dentro del WordPress de cada cliente (vía MCP adapter, el mismo plugin que el de Elementor). Opciones:
- A) Leerlo desde el agente de Diseño web (ya tiene ese conector) y que guarde una «foto mensual» de puntuaciones con el conector local → el informe la usa. Sin credenciales nuevas, pero un paso manual al mes.
- B) Llamar desde Python a la API de WordPress con una contraseña de aplicación por cliente. Automático, pero guarda credenciales en el `.env` (decisión de Javi).
- Además, como Rank Math sí tiene `fix-site-seo` y el Elementor MCP no hace meta/slug, conviene probar en la Fase 0 si el MCP adapter expone Rank Math junto a Elementor.

## 5. Fuentes gratuitas para enriquecer el informe
Ya usamos: GA4, Search Console, PageSpeed, Google Trends, Google Ads.
Candidatas (gratis o casi):
- **Google Business Profile Performance API**: llamadas, cómo llegar, clics a la web, búsquedas en Maps. Muy positivo para negocios locales. Gratis; requiere solicitar acceso a la API.
- **CrUX API** (Chrome UX Report): velocidad real de usuarios, evolución mensual. Gratis con la misma clave de PageSpeed.
- **Search Console – inspección de URL / páginas indexadas**: «X páginas indexadas (+N)». Gratis, ya tenemos acceso.
- **Bing Webmaster Tools API**: clics e impresiones en Bing (y Copilot). Gratis.
- **Open PageRank**: autoridad del dominio (0-10) mensual. Gratis con clave.
- **Ahrefs Webmaster Tools**: enlaces entrantes y autoridad de webs verificadas. Gratis, pero sin API (captura/exportación manual).
- Visitas desde asistentes de IA (ChatGPT, Perplexity…) ya salen en GA4: destacarlas como crecimiento.

## Orden propuesto
1. Quitar negativos (pequeño, rápido).
2. Palabras que dominamos (solo datos que ya tenemos).
3. Palabras objetivo con evolución (nuevo campo por cliente + consultas a GSC).
4. CrUX + páginas indexadas (gratis, mismas credenciales).
5. Rank Math (tras decidir A o B y la Fase 0).
6. Google Business Profile (requiere aprobación de Google).

## Estado (2026-11-20)
Hecho 1-5 (Rank Math por opción B: API de WordPress con contraseña de aplicación).
- Configuración por cliente en el `.env`: `KEYWORDS_OBJETIVO_<C>`, `WP_USER_<C>`, `WP_APP_PASSWORD_<C>` (y `WP_URL_<C>` opcional).
- CrUX necesita activar la API «Chrome UX Report» en el proyecto de Google Cloud de la clave de PageSpeed (hoy da 403).
- «Páginas indexadas» no existe en la API de Search Console: se calcula «páginas que aparecen en Google» (con impresiones), guardado pero aún sin diapositiva.
- Rank Math guarda una foto mensual en `seo-monthly-reports-skill/datos/rankmath/` (fuera de git).
Pendiente: Google Business Profile; campos de la web para palabras objetivo y WordPress.
