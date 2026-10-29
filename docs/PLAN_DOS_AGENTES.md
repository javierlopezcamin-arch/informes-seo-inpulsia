# Plan: dos archivos, dos agentes (Diseño web → Marketing)

Estado: **planificado** (2026-10-29, v2: el cliente revisa **Word**, no un enlace). Sustituye al reparto de
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
| Las 4 webs comprobadas (Piscinas Riviera, DTC Oral, 10DECO, Armonicar) usan **Rank Math** | Una sola vía SEO que resolver |
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

## Configuración SEO del borrador (Rank Math)

Campos que el agente debe dejar rellenados en cada post:

| Campo | Origen |
|---|---|
| Título del post (H1) y **slug** | Brief |
| **Título SEO** (≤ 60) y **meta descripción** (≤ 155) | Brief |
| **Palabra clave principal** (Rank Math) y secundarias | Brief |
| Categoría y etiquetas | Brief + las que ya existen en la web |
| Extracto | Brief |
| Imagen destacada y **texto alternativo** de cada imagen | Imágenes de la biblioteca (`list-assets`) o petición a Javi |
| Enlaces internos | Brief, validados contra las URLs de la web |
| Schema/OG | Valores por defecto de Rank Math |

Vías para escribirlos, a probar en este orden (Fase 0): **(a)** herramientas o `abilities` del Elementor MCP;
**(b)** API REST de Rank Math / campos meta mediante una herramienta local; **(c)** manual con la «Ficha SEO»
(2 minutos por post). El agente informa en la hoja de entrega de **qué campos aplicó y cuáles faltan**.
Seguridad: no se guardan contraseñas de aplicación de WordPress en el `.env` de la web sin decisión expresa de Javi.

## El Word para el cliente

- **Un Word por post**, con formato Inpulsia, hecho por una herramienta local (`crear_word_post`, Fase 3), no
  por el chat: sale siempre igual y es el mismo contenido que el borrador.
- Contiene: título, texto completo con H2/H3, llamada a la acción, sugerencias de imágenes y **«Ficha SEO»**
  (título SEO, meta, slug, palabra clave, categoría). **Nada interno**: ni cifras de Ads, ni volúmenes, ni IDs.
- Carpeta aparte de los archivos internos: `<OUTPUT_DIR>/para_cliente/<CLIENTE>/POST_<MM>_<AAAA>_<n>_<slug>.docx`.
- La web lo lista para descargar o abrir la carpeta (Fase 4). Javi lo envía; la web no envía nada.

## Hoja de entrega (la escribe Diseño web al terminar)

| Pieza | Tipo | ID | Estado | `edit_url` | Word | SEO aplicado | Falta a mano |
|---|---|---|---|---|---|---|---|
| Post 1 | entrada | 123 | borrador | … | ruta | título, meta, slug, kw | imagen destacada |

## Pedidos a diseño web (los deja Marketing al final)

`#n · Qué · Dónde (URL) · Por qué (dato del archivo) · Criterio de aceptación`.

## Fases

**Fase 0 · Probar el Elementor y Rank Math (necesita a Javi).** Conectar `piscinas-riviera-elementor` y poner
`WP_MCP_PISCINAS_RIVIERA` en el `.env`. Comprobar: (a) crea un post en borrador (`post_type=post`);
(b) cómo se escriben slug, título/meta SEO, palabra clave, categoría, etiquetas e imagen destacada (vías a, b, c);
(c) que el contenido del post se construye bien y respeta los estilos de la web. Resultado: qué parte del SEO
es automática y cuál manual.

**Fase 1 · Dividir el generador** (`scripts/generate_propuestas.py`). Mantener el cálculo de señales y separar
`build_markdown` en `build_web_markdown` y `build_marketing_markdown`. Nombres
`PROPUESTAS_WEB_<C>_<MM>_<AAAA>.md` y `PROPUESTAS_MARKETING_<C>_<MM>_<AAAA>.md`. Ajustar `main.py` (líneas
`PROPUESTAS:`), el análisis de la salida en `app.py` y la subida a Drive. Tareas etiquetadas por agente.

**Fase 2 · Brief completo de cada post** (misma llamada a Gemini, sin coste extra): título (≤ 60), slug, palabra
clave principal y secundarias, título SEO, meta (≤ 155), H1, esquema H2/H3, intención de búsqueda, categoría y
etiquetas, enlaces internos validados, llamada a la acción, idioma, longitud e ideas de imagen. Sin IA queda como
tarea para el agente.

**Fase 3 · Herramientas del MCP local** (`scripts/mcp_server.py`): `get_propuestas(cliente, tipo="web"|"marketing")`,
`guardar_entrega` / `get_entrega` (solo escriben en `internos/`) y **`crear_word_post`** (recibe el post
estructurado y genera el .docx en `para_cliente/`). Instalar `python-docx`.

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
- **Publicar:** siempre Javi, tras la aprobación del cliente. El agente nunca publica ni envía nada.
- **Entrega entre agentes:** por el MCP local, con copiar y pegar como respaldo.
- **Credenciales de WordPress:** no se guardan en la web; si hace falta una herramienta local para el SEO se decide
  aparte.
