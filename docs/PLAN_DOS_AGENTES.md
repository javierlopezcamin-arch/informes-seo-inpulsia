# Plan: dos archivos, dos agentes (Diseño web → Marketing)

Estado: **Fases 1-3 implementadas** (2026-10-29); pendientes la Fase 0 (pruebas reales con el Elementor), la 4 y la 5. v2: el cliente revisa **Word**, no un enlace. Sustituye al reparto de
«un archivo para todo» de `PLAN_ADS_PROPUESTAS.md` y de `INSTRUCCIONES_MAESTRAS.md`.

## Idea

Un solo archivo con todas las tareas obliga a un chat con demasiados conectores y mezcla trabajo web y de
Google. Se divide en dos agentes, en este orden:

1. **Diseño web** (Elementor MCP): crea los posts **en borrador con toda la configuración SEO**, genera un
   **Word por post para que Javi lo envíe al cliente** y hace todos los cambios y revisiones de la web.
   **Va primero.**
2. **Marketing** (GA4, Search Console, Ads): trabaja con los datos y, **al final**, deja pedidos concretos
   para diseño web si hacen falta.

Cada agente carga solo sus conectores (menos contexto, menos errores).

## Hechos verificados

| Hecho | Consecuencia |
|---|---|
| `create-page` del Elementor MCP acepta `post_type` y crea la entrada **en borrador** | Se pueden crear posts. Hay que comprobar que «Entradas» esté activado en Elementor en cada web |
| **Todos los clientes usan Rank Math** (Javi; comprobado en Piscinas Riviera, DTC Oral, 10DECO y Armonicar) | Una sola vía SEO que resolver y un único criterio de «verde» |
| Piscinas Riviera ya tiene el plugin del Elementor MCP (`elementor-mcp-composer`, `mcp`, `wp-abilities`) | Solo falta añadir el conector en Claude. En Armonicar y 10DECO no se ve el plugin del MCP de Elementor |
| Las herramientas del Elementor MCP no incluyen ninguna para **slug, título/meta SEO, palabra clave, categorías, etiquetas ni imagen destacada** (solo ajustes de documento, contenido, estilos y publicar) | **Riesgo principal.** Hay que probar cómo escribir esos campos (Fase 0). Mientras no se sepa, el Word lleva una «Ficha SEO» y el borrador queda con una lista de lo que falta por rellenar a mano |
| `python-docx` no está instalado en este Mac | Hay que instalarlo (Fase 3) |
| El enlace de vista previa del Elementor MCP caduca y es una foto fija | **Ya no se necesita**: se sustituye por el Word. Queda como extra opcional |

## Qué lleva cada archivo

| Contenido actual | Archivo **Web** | Archivo **Marketing** |
|---|---|---|
| 1. Resumen de datos | Versión corta | Completa |
| 2. Propuestas de post | **Brief completo de cada post** (Fase 2) | — |
| 3. Palabras clave | Las de cada post | Tabla completa |
| 3b. Páginas que pierden clics | **Sí** (actualizar / comprobar redirección) | — |
| 3b. Llegan desde Google y no convierten | **Sí** (CTA, formulario, contenido) | Resumen |
| 3b. Tráfico desde asistentes de IA | — | Sí |
| URLs con y sin barra final | Diagnóstico (la acción es una redirección en hosting o plugin: Elementor no la hace) | — |
| Etiquetas detectadas (GA4, Ads, GTM, consentimiento) | Lo que hay en la web | Qué falta para medir bien |
| 4. Google Ads | Solo landings y URLs finales | **Todo** |
| 5. Seguimiento de conversiones | — | **Sí**, con los pedidos a diseño web que necesite |
| 6. Tareas | Las de web | Las de Google + **«Pedidos a diseño web»** al final |

Regla: lo que toca el sitio lo ejecuta Diseño web; lo que toca GA4, Search Console o Ads lo decide
Marketing. Si Marketing necesita algo en la web, lo pide (no lo hace).

## Flujo

```
Web de informes ─► ARCHIVO WEB ─► Agente Diseño web ─┬─► Borradores en Elementor (con SEO)
                                                      ├─► WORD por post  ──► Javi lo envía al cliente
                                                      └─► HOJA DE ENTREGA ─┐
                └─► ARCHIVO MARKETING ───────────────────────────────────┤
                                                                          ▼
                                      Agente Marketing (lee la entrega) ─► PEDIDOS A DISEÑO WEB
                                                                          └─► siguiente ciclo de Diseño web
```

Ciclo de cada post: `borrador` → `Word enviado al cliente` → `cambios pedidos` / `aprobado` → `publicado`
(**lo publica Javi**, nunca el agente). Si el cliente pide cambios, Javi se los pasa al agente, que actualiza
el borrador y genera el Word v2.

## Rank Math en verde

**Criterio de aceptación:** cada post queda con la puntuación **verde** de Rank Math (80 o más) y los tests en
verde. Lo que no pueda quedar verde se explica en la hoja de entrega. Los requisitos siguientes salen de los
tests habituales de Rank Math; los umbrales exactos se **calibran en la Fase 0** contra el panel real de cada web.

| Bloque | Requisito en cada post |
|---|---|
| **Snippet de resultado** | **Título SEO** ≤ 60 caracteres, con la palabra clave al principio y, si encaja, un número o un gancho · **Meta descripción** de 120 a 155 caracteres con la palabra clave y una llamada a la acción · **Slug** corto (< 75 caracteres) con la palabra clave |
| **Palabras clave** | Una principal **no usada antes** en otro contenido de la web (se comprueba contra la web) y 2-4 secundarias · La principal en el primer párrafo, en el H1, en al menos un H2, en el alt de una imagen y con densidad ≈ 1 % |
| **Estructura** | **Un solo H1** (el título; comprobar que el tema o Elementor no pinta otro) · H2 por sección y H3 dentro de cada H2, sin saltar niveles · Mínimo 600 palabras (guías: 1.000-1.500) · Párrafos de 120 palabras o menos, listas, tabla de contenidos desde 4 H2 y al menos una imagen o vídeo |
| **Enlaces internos** | 3-5 a páginas y posts existentes (URL validada contra la web, texto ancla descriptivo y sin repetir) · Además, **2 páginas existentes enlazan al nuevo post** (queda como tarea de editar una copia en borrador) |
| **Enlaces externos** | 1-3 a fuentes fiables (instituciones, normativa, fabricantes, estudios), nunca competidores · La URL se comprueba (responde 200) antes de usarla · Enlace normal y en pestaña nueva |
| **Schema** (pestaña Schema de Rank Math) | **Article/BlogPosting** siempre, con autor, fecha e imagen · **FAQPage** si el post lleva 3-5 preguntas frecuentes visibles · **HowTo** si es una guía paso a paso · Nunca schema de contenido que no se vea en la página |
| **Snippets destacados** (posición cero) | Bajo los H2 redactados como pregunta, una **respuesta directa de 40-60 palabras** y luego el desarrollo · Listas numeradas para pasos y tablas para comparativas · Bloque de preguntas frecuentes al final |
| **Imágenes** | Imagen destacada, texto alternativo descriptivo en todas (una con la palabra clave), nombre de archivo limpio y peso ligero (WebP) |
| **Otros campos** | Categoría, etiquetas y extracto |

**Cómo se escribe en WordPress.** Vías a probar en este orden (Fase 0): **(a)** herramientas o `abilities` del
Elementor MCP; **(b)** API REST de Rank Math o campos meta mediante una herramienta local; **(c)** manual con la
«Ficha SEO» (unos 2 minutos por post). El agente informa de **qué campos aplicó y cuáles faltan**.
Seguridad: no se guardan contraseñas de aplicación de WordPress en el `.env` de la web sin decisión expresa de Javi.

**Cómo se comprueba el verde.** El agente no puede leer la puntuación de Rank Math (se calcula en el navegador),
así que se hace en tres pasos:
1. **Antes de crear el borrador:** `validar_seo_post` (herramienta local, Fase 3) aplica estos requisitos al post
   estructurado y devuelve un **semáforo por test**. Si algo está en rojo, el agente lo corrige antes de seguir.
2. **Tras crear el borrador:** Javi abre el post en WordPress y mira la puntuación real. Si difiere del semáforo,
   se anota y se ajusta la herramienta (calibración de la Fase 0).
3. **Hoja de entrega:** semáforo por post con los tests que no pasan y el motivo.

## El Word para el cliente

- **Un Word por post**, con formato Inpulsia, hecho por una herramienta local (`crear_word_post`, Fase 3), no
  por el chat: sale siempre igual y es el mismo contenido que el borrador.
- Contiene: título, texto completo con H2/H3, preguntas frecuentes, llamada a la acción, sugerencias de imágenes con su
  texto alternativo, lista de enlaces (internos y externos) y **«Ficha SEO»** (título SEO, meta, slug, palabra clave,
  categoría, tipo de schema). **Nada interno**: ni cifras de Ads, ni volúmenes, ni IDs, ni el semáforo.
- Carpeta aparte de los archivos internos: `<OUTPUT_DIR>/para_cliente/<CLIENTE>/POST_<MM>_<AAAA>_<n>_<slug>.docx`.
- La web lo lista para descargar o abrir la carpeta (Fase 4). Javi lo envía; la web no envía nada.

## Hoja de entrega (la escribe Diseño web al terminar)

| Pieza | Tipo | ID | Estado | `edit_url` | Word | SEO aplicado | Semáforo | Falta a mano |
|---|---|---|---|---|---|---|---|---|
| Post 1 | entrada | 123 | borrador | … | ruta | título, meta, slug, kw, schema | 11 verdes, 1 naranja (palabras: 560) | imagen destacada |

## Pedidos a diseño web (los deja Marketing al final)

`#n · Qué · Dónde (URL) · Por qué (dato del archivo) · Criterio de aceptación`.

## Fases

**Fase 0 · Probar el Elementor y Rank Math (necesita a Javi).** Conectar `piscinas-riviera-elementor` y poner
`WP_MCP_PISCINAS_RIVIERA` en el `.env`. Comprobar: (a) crea un post en borrador (`post_type=post`); (b) cómo se
escriben slug, título SEO, meta, palabra clave, categoría, etiquetas, imagen destacada y **schema** (vías a, b, c);
(c) que el contenido se construye bien, con un solo H1, y respeta los estilos de la web; (d) **calibración:** crear un
post de prueba, mirar la puntuación real de Rank Math y compararla con el semáforo. Resultado: qué parte del SEO es
automática y cuál manual.

**Fase 1 · Dividir el generador** (`scripts/generate_propuestas.py`). Mantener el cálculo de señales y separar
`build_markdown` en `build_web_markdown` y `build_marketing_markdown`. Nombres
`PROPUESTAS_WEB_<C>_<MM>_<AAAA>.md` y `PROPUESTAS_MARKETING_<C>_<MM>_<AAAA>.md`. Ajustar `main.py` (líneas
`PROPUESTAS:`), el análisis de la salida en `app.py` y la subida a Drive. Tareas etiquetadas por agente.

**Fase 2 · Brief completo de cada post** (misma llamada a Gemini, sin coste extra): título (≤ 60), slug, palabra clave
principal y secundarias, título SEO, meta (120-155), H1, esquema H2/H3 (con H2 en forma de pregunta y su respuesta
directa de 40-60 palabras), preguntas frecuentes, tipo de schema, categoría y etiquetas, **enlaces internos validados**
contra la web, **enlaces externos validados** (el generador comprueba que la URL responde 200 y descarta las que no; si
la IA no propone ninguna fiable, queda el tipo de fuente para que el agente la busque), llamada a la acción, idioma,
longitud e ideas de imagen con alt. Además, 2 páginas existentes que deben enlazar al post. Sin IA queda como tarea
para el agente.

**Fase 3 · Herramientas del MCP local** (`scripts/mcp_server.py`): `get_propuestas(cliente, tipo="web"|"marketing")`,
`guardar_entrega` / `get_entrega` (solo escriben en `internos/`), **`validar_seo_post`** (semáforo Rank Math sobre el
post estructurado, antes de crear el borrador) y **`crear_word_post`** (genera el .docx en `para_cliente/`). Instalar
`python-docx`.

**Fase 4 · Web de informes.** Descargas del archivo Web y del de Marketing, lista de Word listos por cliente, recuento
en la tanda y subida a `<CLIENTE>/INTERNO` (los Word, a una carpeta aparte del cliente, sin enviarlos).

**Fase 5 · Instrucciones.** Dos bloques maestros (Diseño web y Marketing) y sus primeros mensajes, sustituyendo
`INSTRUCCIONES_MAESTRAS.md`. Dos proyectos de Claude: Diseño web = Elementor del cliente + `seo-inpulsia`;
Marketing = solo `seo-inpulsia`.

**Orden:** Fase 0 en cuanto esté conectado el Elementor (en paralelo al código) → 1 → 2 → 3 → 4 → 5.

## Decisiones por defecto (cambiables)

- **Dos interruptores por cliente:** «Archivo de diseño web» (cualquier cliente con web) y «Google Ads + archivo de
  marketing» (solo con Customer ID).
- **Gemini** solo para los posts, y solo si el archivo web está activado; el de marketing no usa IA.
- **Un Word por post**, sin datos internos, con «Ficha SEO» al final y versión v2 si hay cambios.
- **Verde = 80 o más en Rank Math** y todos los tests en verde; si uno no puede cumplirse (por ejemplo, 600 palabras en un
  post corto), se justifica en la hoja de entrega en lugar de forzarlo.
- **El agente no publica un post que tenga tests en rojo** sin avisar a Javi.
- **Publicar:** siempre Javi, tras la aprobación del cliente. El agente nunca publica ni envía nada.
- **Entrega entre agentes:** por el MCP local, con copiar y pegar como respaldo.
- **Credenciales de WordPress:** no se guardan en la web; si hace falta una herramienta local para el SEO se decide
  aparte.

## Estado de la implementación (2026-10-29)

| Fase | Estado | Dónde |
|---|---|---|
| 1 · Dividir el generador | ✅ probado con Piscinas Riviera (sept. 2026) | `generate_propuestas.py` → `PROPUESTAS_WEB_…md` y `PROPUESTAS_MARKETING_…md`; `main.py` imprime `PROPUESTAS WEB:` / `PROPUESTAS MARKETING:`; la web los reconoce y ofrece las dos descargas (la interfaz completa es la Fase 4) |
| 2 · Brief completo del post | ✅ probado con 1 llamada real a Gemini | `_ai_posts` pide snippet, H2 con respuesta directa, FAQ, schema, enlaces internos/externos y alt; los enlaces externos se descartan si no responden; avisos del brief (`brief_issues`) |
| 3 · Herramientas del conector local | ✅ probadas llamando a cada una | `mcp_server.py`: `get_propuestas(tipo)`, `guardar_entrega`/`get_entrega`, `guardar_pedidos_web`/`get_pedidos_web`, `validar_seo_post`, `crear_word_post` |
| Semáforo Rank Math y Word | ✅ 18 tests unitarios (`python3 -m unittest discover -s tests`) | `scripts/seo_posts.py`, `scripts/word_post.py` (`python-docx`) |

**Cómo se activa (hasta la Fase 4):** archivo Web con `WEB_EN_INFORME_<CLIENTE>=true` en el `.env`; archivo Marketing con la
casilla de Google Ads que ya existe (`ADS_EN_INFORME_<CLIENTE>`).

**Cambios sobre el plan:**
- Se añadieron `guardar_pedidos_web` y `get_pedidos_web` para que Marketing deje los pedidos sin copiar y pegar. Los pedidos
  pendientes se muestran al final de `get_propuestas(tipo="web")` mientras sean más recientes que la última entrega.
- `get_propuestas(tipo="marketing")` añade al final la última entrega de Diseño web.
- El contenido del post se pasa en Markdown (`## `, `### `, `> ` para la llamada a la acción, enlaces `[ancla](url)`,
  imágenes `![alt](idea)`); el mismo texto alimenta el semáforo y el Word.
- El semáforo no replica la nota numérica de Rank Math: es VERDE solo si todos los tests están en verde. Las comprobaciones de
  «palabra clave no usada» y de densidad son aproximadas hasta calibrar (Fase 0).

**Pendiente:** Fase 0 (Elementor + Rank Math reales: crear borrador, escribir los campos SEO, calibrar el semáforo), Fase 4 (web:
interruptores por cliente, lista de Word) y Fase 5 (instrucciones de los dos proyectos de Claude).
