# Plan: dos archivos, dos agentes (Diseño web → Marketing)

Estado: **planificado** (2026-10-29). Sustituye al reparto de «un archivo para todo» de
`PLAN_ADS_PROPUESTAS.md` y de `INSTRUCCIONES_MAESTRAS.md`.

## Idea

Un solo archivo con todas las tareas obliga a un chat con demasiados conectores y a mezclar trabajo
web con trabajo de Google. Se divide en dos agentes, en este orden:

1. **Diseño web** (Elementor MCP): crea los posts en borrador, los deja revisables por el cliente y
   hace todos los cambios y revisiones de la web. **Va primero.**
2. **Marketing** (herramientas de Google: GA4, Search Console, Ads): trabaja con los datos y, **al
   final**, deja pedidos concretos para diseño web si hacen falta.

Cada agente solo carga sus conectores (menos contexto, menos errores).

## Hechos verificados sobre el Elementor MCP (condicionan el diseño)

| Hecho | Consecuencia |
|---|---|
| `create-page` acepta `post_type` y crea la entrada **en borrador** | Se pueden crear posts del blog. Hay que comprobar que `post` esté activado en Elementor en cada web |
| `create-preview-link` devuelve una URL **anónima, firmada, con caducidad y congelada** (foto del contenido en ese momento) | Sirve para que el cliente vea el borrador sin cuenta, pero **caduca y no refleja cambios posteriores**: hay que regenerarla tras cada cambio |
| La propia herramienta dice que esa URL es para que el agente se autovalide y que al usuario se le dé `edit_url` (requiere login de WordPress) | Compartirla con el cliente es una decisión de Javi, no el uso previsto: se prueba antes (Fase 0) y se deja una alternativa |
| En DTC Oral avisa de que requiere el «editor atómico», desactivado en ese sitio | Puede **no funcionar en algunas webs**. Hay que probarlo por cliente |

## Qué lleva cada archivo

Se reparte lo que ya genera `generate_propuestas.py`:

| Contenido actual | Archivo **Web** | Archivo **Marketing** |
|---|---|---|
| 1. Resumen de datos | Versión corta | Completa |
| 2. Propuestas de post | **Brief completo de cada post** (ver Fase 2) | — |
| 3. Palabras clave | Solo las de cada post | Tabla completa |
| 3b. Páginas que pierden clics | **Sí** (actualizar / comprobar redirección) | — |
| 3b. Llegan desde Google y no convierten | **Sí** (CTA, formulario, contenido) | Resumen |
| 3b. Tráfico desde asistentes de IA | — | Sí |
| URLs con y sin barra final | Diagnóstico (la acción es redirección en hosting o plugin: Elementor no la hace) | — |
| Etiquetas detectadas (GA4, Ads, GTM, consentimiento) | Lo que hay en la web | Qué falta para medir bien |
| 4. Google Ads | Solo landings y URLs finales | **Todo** |
| 5. Seguimiento de conversiones | — | **Sí**, con los pedidos a diseño web que necesite |
| 6. Tareas | Las de web | Las de Google + **«Pedidos a diseño web»** al final |

Regla para repartir tareas: lo que toca el sitio lo ejecuta Diseño web; lo que toca GA4, Search
Console o Ads lo decide Marketing. Si Marketing necesita algo en la web, lo pide (no lo hace).

## Flujo y entregables

```
Web de informes ──► ARCHIVO WEB ──► Agente Diseño web ──► HOJA DE ENTREGA ──┐
                └─► ARCHIVO MARKETING ───────────────────────────────────────┤
                                                                              ▼
                                         Agente Marketing (lee la entrega) ──► PEDIDOS A DISEÑO WEB
                                                                              │
                                                  siguiente ciclo del agente Diseño web ◄┘
```

**Hoja de entrega** (la escribe Diseño web al terminar), una fila por pieza:

| Pieza | Tipo | ID | Estado | Enlace interno (`edit_url`) | Enlace para el cliente | Caduca | Notas |
|---|---|---|---|---|---|---|---|
| Post 1 | entrada | 123 | borrador | … | … | … | … |

Estados: `borrador` → `enviado al cliente` → `cambios pedidos` / `aprobado` → `publicado` (**lo publica
Javi**, nunca el agente).

**Pedidos a diseño web** (los deja Marketing al final), un bloque por pedido:
`#n · Qué · Dónde (URL) · Por qué (dato del archivo) · Criterio de aceptación`.

## Enlace visible para el cliente (a decidir tras la Fase 0)

| Opción | Cómo | Pros | Contras |
|---|---|---|---|
| **A (primera a probar)** | `create-preview-link` | Sin plugins, sin cuentas | Caduca; es una foto fija; puede no funcionar con el editor atómico desactivado |
| B | Plugin gratuito de vista previa pública de borradores | Enlace estable y sin login | Instalar un plugin en la web de cada cliente |
| C (respaldo) | Contenido en un documento (Google Doc/PDF) para aprobar el texto; el diseño se revisa después | No toca la web | El cliente no ve el diseño |

Se descarta publicar con contraseña: queda publicado y el título se ve en el blog.

## Fases

**Fase 0 · Probar el Elementor (necesita a Javi).** Conectar el Elementor de Piscinas Riviera
(`piscinas-riviera-elementor`, y `WP_MCP_PISCINAS_RIVIERA` en el `.env`). Comprobar: (a) `create-page`
con `post_type=post` crea un borrador; (b) `create-preview-link` funciona en esa web y cuánto caduca;
(c) la URL se abre sin login desde otro navegador. Elegir A, B o C.

**Fase 1 · Dividir el generador** (`scripts/generate_propuestas.py`). Mantener el cálculo de señales
y separar `build_markdown` en `build_web_markdown` y `build_marketing_markdown`. Nombres:
`PROPUESTAS_WEB_<C>_<MM>_<AAAA>.md` y `PROPUESTAS_MARKETING_<C>_<MM>_<AAAA>.md`. Ajustar `main.py` (las
líneas `PROPUESTAS:`), el análisis de salida de `app.py` y la subida a Drive (`upload_internal_doc`).
Tareas etiquetadas por agente.

**Fase 2 · Brief completo de los posts** (misma llamada a Gemini, sin coste extra). Cada post lleva:
título (≤ 60), slug, palabra clave principal y secundarias, título SEO y meta (≤ 155), H1, esquema
H2/H3, intención de búsqueda, enlaces internos validados contra la web, llamada a la acción, idioma y
longitud orientativa. Sin IA: queda como tarea para el agente.

**Fase 3 · Entrega y pedidos en el MCP local** (`scripts/mcp_server.py`):
`get_propuestas(cliente, tipo="web"|"marketing")`, `guardar_entrega(cliente, mes, anio, contenido)` y
`get_entrega(cliente, mes, anio)`. Así Marketing lee lo que hizo Diseño web sin copiar y pegar. Solo
escribe en la carpeta `internos/`.

**Fase 4 · Web de informes.** Dos botones de descarga (Web y Marketing), recuento en la tanda y subida de
los dos a `<CLIENTE>/INTERNO`. Un interruptor por cliente (ver decisiones).

**Fase 5 · Instrucciones.** Dos bloques maestros (Diseño web y Marketing) y los primeros mensajes de cada
uno, sustituyendo `INSTRUCCIONES_MAESTRAS.md`. Dos proyectos de Claude, cada uno con sus conectores:
Diseño web = Elementor del cliente + `seo-inpulsia`; Marketing = solo `seo-inpulsia`.

**Orden:** Fase 0 en cuanto esté conectado el Elementor (en paralelo al código) → 1 → 2 → 3 → 4 → 5.

## Decisiones por defecto (cambiables)

- **Interruptor:** hoy una casilla controla «Ads + propuestas». Propongo **dos**: «Archivo de diseño web»
  (para cualquier cliente con web: contenido que cae, posts) y «Google Ads + archivo de marketing»
  (solo clientes con Customer ID). Así los clientes sin Ads también reciben posts y revisiones.
- **Cupo de Gemini:** la llamada de los posts solo se hace si el archivo web está activado; el archivo
  de marketing no usa IA.
- **Publicar:** siempre Javi, tras la aprobación del cliente.
- **Entrega entre agentes:** por el MCP local (Fase 3), con el copia y pega como respaldo.
- **Sin cambios de código hasta confirmar la Fase 0:** no se construye nada que dependa del enlace de
  vista previa hasta saber si funciona en las webs reales.
