# Plan: Servidor MCP local para consultar GA4 / Search Console / AdSense desde Claude Desktop

## Objetivo
Poder preguntar en Claude Desktop cosas como "¿cómo va el tráfico de armonicar este mes?"
o "dame recomendaciones de SEO para 10deco", con datos en vivo, sin generar un informe PPTX.
Es un complemento al generador de informes existente (`seo-monthly-reports-skill/`), no un
sustituto: el PPTX sigue siendo el entregable periódico para clientes; esto es para consulta
interna rápida.

## Decisión de arquitectura
- **Local, no remoto.** Se descartó exponer un servidor MCP en un VPS con HTTPS/dominio/token
  bearer para conectarlo como "custom connector" en claude.ai. En su lugar: servidor MCP por
  **stdio**, registrado en `claude_desktop_config.json`, que Claude Desktop lanza como proceso
  local. Sin hosting, sin TLS, sin exponer nada a internet.
- Funciona en cualquier plan (el conector remoto en claude.ai requiere Pro/Max/Team/Enterprise;
  el local no).
- Patrón ya validado en esta máquina: el conector `"pencil"` en
  `~/Library/Application Support/Claude/claude_desktop_config.json` usa exactamente este mecanismo
  (`command` + `args` lanzando un binario/script local).

## Qué se reutiliza del proyecto existente
Ubicación: `seo-monthly-reports-skill/scripts/`
- `extract_ga4.py` — extracción de Google Analytics 4 (mismo service account)
- `extract_search_console.py` — extracción de Search Console
- `analyze.py` — lógica de recomendaciones e insights con IA (Gemini → Claude fallback)
- Credenciales ya existentes en `seo-monthly-reports-skill/credenciales/cappuccino-key.json`
  y variables en `seo-monthly-reports-skill/.env` (property IDs y URLs por cliente)

No hace falta tocar estos archivos; el servidor MCP los importa y los envuelve.

## Qué es nuevo
1. **`seo-monthly-reports-skill/scripts/mcp_server.py`** — servidor MCP nuevo, usando el SDK
   oficial `mcp` (`pip install mcp`). Expone herramientas de solo lectura:
   - `get_ga4_overview(cliente, rango)`
   - `get_search_console_status(cliente)`
   - `get_recommendations(cliente)` (reusa `analyze.py`)
   - `get_adsense_earnings(cuenta)` — fase 2, ver más abajo

2. **Registro en `claude_desktop_config.json`** (añadir junto al bloque `"pencil"` existente):
   ```json
   "seo-inpulsia": {
     "command": "/opt/homebrew/bin/python3",
     "args": ["/Users/javicamin/Desktop/Claude proyectos local/INFORMES SEO INPULSIA/seo-monthly-reports-skill/scripts/mcp_server.py"],
     "env": {}
   }
   ```
   Tras editarlo, reiniciar Claude Desktop para que cargue el conector.

## Punto delicado: AdSense (fase 2, aparte)
- La AdSense Management API **no admite service account** en ningún escenario (local o remoto):
  requiere **OAuth de usuario** con consentimiento explícito.
- El flujo OAuth y el refresh token se gestionan igual que `drive_token.json` en
  `upload_drive.py` (mismo patrón ya usado en este proyecto para Google Drive).
- Al ser local, el token vive en disco de esta máquina (ej. `~/.cache/seo-reports/adsense_token.json`),
  lo cual es más seguro que si el servidor estuviera expuesto en un VPS público.
- Se deja para una segunda fase, una vez validado el flujo de GA4 + Search Console.

## Procedimiento para continuar en una sesión nueva
1. Abrir Claude Code en este directorio (`INFORMES SEO INPULSIA`).
2. Pedir: *"lee docs/MCP_SERVER_PLAN.md y continúa con la implementación de mcp_server.py"*.
3. No hace falta reexplicar el contexto — este documento + la memoria de proyecto ya lo cubren.

## Estado actual
- [x] `mcp_server.py` — creado en `seo-monthly-reports-skill/scripts/mcp_server.py`.
  Usa `mcp.server.fastmcp.FastMCP`. Herramientas: `list_clientes`, `get_ga4_overview`,
  `get_search_console_status`, `get_recommendations`. Probado en CLI directamente
  (sin Claude Desktop) contra el cliente real `10deco` — funciona end to end.
- [x] Registro en `claude_desktop_config.json` — añadido el bloque `"seo-inpulsia"`
  junto a `"pencil"`. **Falta reiniciar Claude Desktop** para que cargue el conector.
- [ ] AdSense OAuth — no iniciado (fase 2)

## Notas de implementación
- El paquete `mcp` no estaba instalado; se instaló con
  `/opt/homebrew/bin/python3 -m pip install --break-system-packages mcp` (mismo
  intérprete que ya tenía instalados google-analytics-data, googleapiclient y
  python-dotenv para este proyecto).
- `GOOGLE_APPLICATION_CREDENTIALS` en `.env` es una ruta relativa
  (`credenciales/cappuccino-key.json`), pensada para cuando los scripts se ejecutan
  desde `seo-monthly-reports-skill/`. Como Claude Desktop lanza el proceso MCP con
  un `cwd` desconocido, `mcp_server.py` la resuelve a absoluta contra `SKILL_DIR`
  antes de importar `extract_ga4`/`extract_search_console`.
- Los clientes se descubren dinámicamente leyendo `GA4_PROPERTY_ID_*` y
  `SEARCH_CONSOLE_URL_*` de `.env` (no hay lista hardcodeada); usar
  `list_clientes` para ver los nombres exactos.

## Siguiente paso
Reiniciar Claude Desktop (Cmd+Q y reabrir) y probar en una conversación nueva:
"¿cómo va el tráfico de armonicar este mes?" — debería usar la tool `get_ga4_overview`
del conector `seo-inpulsia` automáticamente.
