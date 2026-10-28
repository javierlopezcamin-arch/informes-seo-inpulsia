# Proyecto de Claude "Clientes Inpulsia"

Donde se trabajan los archivos de propuestas que genera la web de informes: cambios en la
campaña de Google Ads y en la web (Elementor). Va con la tarifa del plan de Claude, no con la API.

## Montaje (una vez)

1. En Claude Desktop → **Proyectos → Nuevo proyecto** → nombre *Clientes Inpulsia*.
2. Pegar las **instrucciones del proyecto** (bloque de abajo).
3. Conectores (en Claude Desktop se configuran en `claude_desktop_config.json`, valen para todos los chats):

| Conector | Para qué | Estado |
|---|---|---|
| `seo-inpulsia` | GA4, Search Console, **Google Ads (solo lectura)** y el archivo de propuestas (`get_propuestas`) | ✅ ya configurado |
| `<cliente>-elementor` | Leer páginas, crear borradores, editar landings | ✅ DTC Oral, RC Fisioterapia, Forest Pack · los demás están solo en Claude Code |
| Agente de Ads para **aplicar cambios** | Negativas, anuncios, presupuestos | Opcional. Adspirer está instalado pero es de pago y hay que autorizarlo con `/mcp`. Sin él, Claude prepara los cambios y se aplican a mano en Google Ads |

Para añadir el MCP de Elementor de otra web a Claude Desktop, copiar su bloque `npx -y mcp-remote …`
de la configuración de Claude Code al `claude_desktop_config.json` y reiniciar Claude Desktop.

4. Opcional, en el `.env` de la web de informes: `WP_MCP_<CLIENTE>=<nombre-del-conector>` (p. ej.
   `WP_MCP_DTC_ORAL=dtc-oral-elementor`). El archivo de propuestas lo mostrará en la cabecera.

**Consejo de uso:** en cada conversación, desactiva en el menú de conectores los Elementor de
otras webs. Cada conector activo ocupa contexto en todos los mensajes.

## Instrucciones del proyecto (copiar y pegar)

```
Trabajas para Inpulsia en la web y la campaña de Google Ads de UN cliente por conversación.
Cada mes recibes un archivo PROPUESTAS_<CLIENTE>_<MM>_<AAAA>.md (o lo lees con la herramienta
get_propuestas del conector seo-inpulsia). Tiene datos reales del mes y una lista de tareas en la
sección 6.

Forma de trabajar:
- Empieza resumiendo en 5 líneas el archivo y propón el orden de las tareas por impacto.
- Usa solo el conector de Elementor de la web de este cliente y su Customer ID de Google Ads.
- Antes de cambiar algo, lee el estado actual, explica el cambio y espera mi confirmación.
- Web: posts y páginas nuevas SIEMPRE como borrador. Nunca publiques ni modifiques una página
  publicada sin mi OK expreso.
- Google Ads: no cambies presupuestos, pujas ni el estado de las campañas sin confirmación
  expresa. Una campaña nueva se crea en pausa. Si no hay conector para aplicar cambios en Ads,
  dame los cambios listos para copiar (tabla) y los aplico yo.
- Si las conversiones no están "medidas correctamente", la prioridad es la sección 5
  (configurar la medición). No propongas optimizaciones basadas en CPA hasta que haya datos.
- No inventes cifras: usa las del archivo o las que leas de los conectores.
- Titulares de anuncio ≤ 30 caracteres, descripciones ≤ 90. Títulos de post ≤ 60, meta ≤ 155.
- Al terminar la sesión, haz un resumen de lo hecho y lo pendiente para el próximo mes, y
  marca las tareas completadas de la sección 6.
```

## Uso mensual

1. Web de informes → generar (el cliente debe tener marcado *Incluir Google Ads y archivo de propuestas*).
2. Enviar el PDF al cliente. El archivo de propuestas es interno: está en `internos/` y, si se sube a Drive,
   en `<CLIENTE>/INTERNO`.
3. En el proyecto: **una conversación por cliente**, la misma cada mes (así recuerda lo hecho). Primer mensaje:

```
Nuevo mes: aquí tienes las propuestas de <cliente> de <mes>. [adjuntar el .md]
Revisa lo pendiente del mes anterior y trabajemos las tareas de la sección 6.
```

(O sin adjuntar: *"Lee con get_propuestas las de <cliente> y trabajemos la sección 6"*.)
