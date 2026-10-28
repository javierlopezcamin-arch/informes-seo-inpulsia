# Plan de mejoras de diseño: PPT y web

Estado: **planificado** (2026-10-28). Base: revisión del informe de prueba de 10DECO (sept. 2026),
exportado a imágenes con Keynote, y capturas de la web. El punto 5 (traducir canales y países)
queda fuera por decisión de Javi.

Principio: cada fase se puede usar sola; un commit por punto; nada cambia los datos, solo cómo se ven.

## Fase 0 · Herramienta de revisión visual (antes de tocar nada)

`scripts/dev_preview.py <pptx>`: abre el PPTX con Keynote, exporta las diapositivas a JPEG y
monta hojas de contacto (9 por imagen) en el scratchpad o en `scratch/`. Así se compara antes/después
de cada cambio en los dos diseños. Solo para desarrollo; no lo usa la web.

Fixture de prueba fija: 10DECO sept. 2026 (tiene de todo: tablas largas, páginas que caen, visitas
desde IA) + Piscinas Riviera (web pequeña, tablas cortas).

## Fase 1 · Errores visibles en las plantillas (1, 2, 3, 4, 6)

| # | Problema | Dónde | Cambio |
|---|---|---|---|
| 1 | Círculo blanco tapa el logo del cliente en la portada | `generate_pptx.py` · `add_cover_slide` (líneas ~225-240) | Quitar el óvalo blanco detrás del logo; si el logo es oscuro sobre fondo navy, ponerlo en una tarjeta blanca redondeada del tamaño del logo (no un círculo encima) |
| 2 | Continuaciones con 1-2 filas o 2 viñetas | v2: `add_table` (`cap`, línea ~436) y `add_text` (`CAP`); v1: `add_table_slide` y `add_text_slide` | Si tras partir quedan ≤ 2 filas (o ≤ 3 líneas de texto), meterlas en la diapositiva anterior reduciendo el alto de fila; si no caben, repartir a partes iguales entre las dos |
| 3 | El círculo "›" pisa la última fila de las tablas | v2: `_circle_arrow` (9.02, 4.78) frente a `bottom = 5.35` en `add_table` | Bajar el límite de la tabla a 4.6 cuando la diapositiva lleva la flecha, o en diapositivas con tabla usar una flecha más pequeña en la esquina del pie |
| 4 | Miles con coma ("1,330") | ~15 usos de `:,` en cada generador, `analyze.py` (5) y `charts.py` (3) | Función única `fmt_int()` / `fmt_dec()` en `utils.py` con punto de miles y coma decimal (1.330 · 1,45 %) y sustituir todos los usos; las narrativas de `analyze.py` también |
| 6 | Índice y numeración de secciones no cuadran ("6. Recomendaciones" sin estar en el índice; Conclusiones también 6) | v2 líneas ~826-836 y v1 ~1370-1377 | La sección «Análisis y Recomendaciones» entra en el índice si hay recomendaciones, anomalías **o** páginas que pierden visitas; quitar los números por defecto ("05", "06") de `sec_nums.get(...)` y sacarlos siempre del índice |

Verificación: hojas de contacto antes/después de los dos diseños con los dos clientes de prueba.

## Fase 2 · Diseño de las plantillas (7, 8, 9, 10, 11)

| # | Cambio | Dónde | Detalle |
|---|---|---|---|
| 7 | «Comparativa mensual» legible | `charts.py` · `mom_grouped_bars` | Sustituir las barras absolutas (escalas incompatibles) por **barras horizontales de % de cambio** por métrica (Usuarios, Sesiones, Impresiones, Clics), verde si sube y rojo si baja, con el valor actual y el del mes anterior en la etiqueta |
| 8 | Menos vacío y letra más grande | ambos generadores | Tablas: cuerpo 11→12-13 pt, cabecera 9→10 pt, alto de fila mayor; narrativas 11→13 pt; tablas de ≤ 4 filas centradas verticalmente; gráficas: aumentar el área de imagen y el DPI/tamaño de fuente en `charts.py`. Revisar que las tablas largas siguen partiendo bien (punto 2) |
| 9 | Variación en todas las tarjetas | v1 líneas ~1408 y ~1472; v2 `add_kpi` y sus llamadas | Añadir delta de Tasa de rebote y Posición media frente al mes anterior; en ambas **bajar es mejorar** (verde con flecha hacia abajo). Requiere calcular `d_bounce` y `d_position` en `analyze.py` |
| 10 | Top keywords sin ruido | `analyze.py` · `analyze_keywords` | Excluir keywords con < 10 impresiones y posición > 50; ordenar por clics y luego impresiones. Mismo filtro en «Oportunidades» |
| 11 | Diapositiva «Lo más destacado del mes» | nueva en v1 y v2, justo después del índice | 3 logros + 1 punto a mejorar en tarjetas grandes. Sin llamada extra de IA: usa `executive_summary` si existe; si no, reglas (las 3 métricas que más suben, la que más baja, y la página que más visitas pierde). Se puede desactivar como una sección más (`destacados`) |

Verificación: hojas de contacto; comprobar que el número de diapositivas no crece salvo la nueva.

## Fase 3 · Web (12, 13, 14, 15, 16)

| # | Cambio | Dónde | Detalle |
|---|---|---|---|
| 12 | Chips de marca, no rojos | `app.py` · bloque `CSS` | Estilo para `[data-baseweb="tag"]`: fondo lima translúcido, texto lima, borde fino; en «Opciones del informe» y en el selector de clientes |
| 13 | Selector de clientes oscuro | `app.py` · `CSS` | Fondo `--bg2`, borde `--line2`, texto claro para el `multiselect` y su desplegable (`[data-baseweb="select"]`, `[data-baseweb="popover"]`) |
| 14 | Formulario en 3 pasos | `app.py` · pestaña «Generar informe» | Tarjetas «1 · Clientes», «2 · Periodo y diseño», «3 · Opciones», cada una con su título; encima del botón, un resumen en una línea: «3 informes · Septiembre 2026 · Inpulsia 2 · 3 llamadas de IA (quedan 13) · 1 con Ads» |
| 15 | Lista de clientes más clara | `app.py` · pestaña «Clientes» | Nombre legible (`10DECO` → «10DECO», `ANA_ISABEL_BONITO_PSICLOGA` → «Ana Isabel Bonito Psicloga») y la web del cliente en gris debajo; filas más compactas; «Borrar» pasa a un botón discreto (icono 🗑 o texto gris) — la confirmación «¿Borrar…?» ya existe y se mantiene |
| 16 | Ajuste de datos en una línea | `app.py` · `st.radio(... "boost")` (línea ~669) | `st.segmented_control` (Streamlit 1.58 lo tiene) con las 5 opciones en una fila; «Datos reales» por defecto y resaltado distinto si se elige un ajuste |

Verificación: navegador interno (escritorio y 1280 px), comprobando que generar, tandas, filtros,
editar y borrar siguen funcionando.

## Orden y tamaño

1. Fase 0 (pequeña) → 2. Fase 1 (pequeña-media) → 3. Fase 3 (media) → 4. Fase 2 (la más grande).
La web va antes que la fase 2 porque es independiente y rápida; la fase 2 toca tamaños y puede
mover la paginación, así que se hace con la fase 1 ya cerrada.

## Decisiones tomadas por defecto (cambiables)

- Punto 7: barras de % de cambio (mantiene una gráfica) en vez de solo tarjetas.
- Punto 11: sin llamada extra de IA; sección desactivable.
- Punto 15: los nombres internos (`NOMBRE_CLIENTE` en el `.env`) no cambian; solo cómo se muestran.
