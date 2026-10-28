# Guía Completa de Configuración: SEO Monthly Reports

Esta guía te lleva paso a paso por la configuración de Google Cloud Console, obtención de credenciales y configuración de variables de entorno.

## Tiempo estimado: 20-30 minutos

---

## PARTE 1: Crear Google Cloud Project

### Paso 1.1: Acceder a Google Cloud Console
1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Inicia sesión con tu cuenta Google (la que tiene acceso a Analytics y Search Console)
3. Si es tu primera vez, acepta los términos

### Paso 1.2: Crear Nuevo Proyecto
1. En la parte superior, haz clic en el selector de proyecto (donde dice "Select a project")
2. Haz clic en **"NEW PROJECT"**
3. Completa:
   - **Project name:** `SEO Monthly Reports` (o el nombre que prefieras)
   - **Organization:** Déjalo en blanco si no tienes organización
4. Haz clic en **CREATE**
5. Espera 1-2 minutos a que se cree el proyecto
6. **Anota el Project ID** (aparecerá en la página, es importante)

### Paso 1.3: Seleccionar el Proyecto
1. Vuelve al selector de proyecto (arriba a la izquierda)
2. Selecciona el proyecto que acabas de crear
3. Ahora estás dentro del proyecto

---

## PARTE 2: Habilitar APIs Necesarias

### Paso 2.1: Ir a APIs & Services
1. En el menú izquierdo, busca **"APIs & Services"**
2. Haz clic en **"APIs & Services"** → **"Library"**

### Paso 2.2: Habilitar Google Analytics Data API
1. En la caja de búsqueda, escribe: `Google Analytics Data API`
2. Haz clic en el resultado
3. Haz clic en **ENABLE**
4. Espera a que se habilite (unos segundos)

### Paso 2.3: Habilitar Google Search Console API
1. Vuelve a la biblioteca de APIs
2. En la caja de búsqueda, escribe: `Google Search Console API`
3. Haz clic en el resultado
4. Haz clic en **ENABLE**

### Paso 2.4: Habilitar Google Slides API
1. Vuelve a la biblioteca de APIs
2. En la caja de búsqueda, escribe: `Google Slides API`
3. Haz clic en el resultado
4. Haz clic en **ENABLE**

### Paso 2.5: Habilitar Google Drive API
1. Vuelve a la biblioteca de APIs
2. En la caja de búsqueda, escribe: `Google Drive API`
3. Haz clic en el resultado
4. Haz clic en **ENABLE**

**Listo:** Ahora tienes todas las APIs habilitadas. Deberías ver las 4 APIs en "Enabled APIs & Services".

---

## PARTE 3: Crear Service Account

### Paso 3.1: Ir a Service Accounts
1. En el menú izquierdo, ve a **APIs & Services** → **Credentials**
2. En la parte superior, haz clic en **+ CREATE CREDENTIALS**
3. Selecciona **Service Account**

### Paso 3.2: Rellenar Detalles del Service Account
En el formulario que aparece:
- **Service account name:** `seo-reports` (o el nombre que prefieras)
- **Service account ID:** Se auto-completa (seo-reports@[proyecto].iam.gserviceaccount.com)
- **Description:** `Service account para extraer datos SEO` (opcional)

Haz clic en **CREATE AND CONTINUE**

### Paso 3.3: Asignar Permisos (Basic)
En la siguiente pantalla **"Grant this service account access to project"**:
- Haz clic en el selector de rol (donde dice "Select a role")
- Busca y selecciona: **Editor** (permisos amplios, necesarios para acceder a todas las APIs)
  - O más restrictivo: **Viewer** + **Roles/analyticsreporting.service** (opcional, más seguro)
- Haz clic en **CONTINUE**

### Paso 3.4: Crear Clave JSON
En la siguiente pantalla **"Create key"**:
1. Haz clic en **CREATE KEY**
2. Selecciona **JSON**
3. Haz clic en **CREATE**
4. **Se descargará automáticamente un archivo JSON** (guárdalo en un lugar seguro)
   - Nombre típico: `[proyecto]-[identificador].json`
   - **NO compartas este archivo. Mantén seguro como una contraseña.**

Haz clic en **DONE**

**Has completado la creación del Service Account. Tienes el JSON descargado.**

---

## PARTE 4: Otorgar Acceso a Google Analytics

El Service Account necesita acceso a tu Google Analytics 4.

### Paso 4.1: Ir a Google Analytics 4
1. Ve a [Google Analytics 4](https://analytics.google.com)
2. Selecciona la propiedad donde quieres crear informes
3. En la parte inferior izquierda, ve a **Admin** (⚙️)

### Paso 4.2: Agregar Acceso
1. Haz clic en **Account Access Management** (o "Property Access Management")
2. Haz clic en **"+"** (Invite users)
3. En el campo de email, pega: `seo-reports@[tu-proyecto].iam.gserviceaccount.com`
4. Selecciona el rol: **Editor** o **Viewer** (Viewer es más seguro)
5. Haz clic en **Invite**

**Listo:** El Service Account ahora tiene acceso a tu Google Analytics.

### Paso 4.3: Anotar Google Analytics Property ID
Mientras estés en Google Analytics Admin:
1. Ve a **Property Settings** (Configuración de propiedad)
2. Busca **Property ID** (es un número, ej: 123456789)
3. **Cópialo y guárdalo en un lugar seguro** (lo necesitarás en la configuración)

---

## PARTE 5: Otorgar Acceso a Google Search Console

### Paso 5.1: Ir a Google Search Console
1. Ve a [Google Search Console](https://search.google.com/search-console)
2. Selecciona tu propiedad (dominio)
3. En la parte izquierda, ve a **Settings** (Configuración)

### Paso 5.2: Agregar Acceso
1. Haz clic en **Users and permissions** (Usuarios y permisos)
2. Haz clic en **Add user**
3. En el campo de email, pega: `seo-reports@[tu-proyecto].iam.gserviceaccount.com`
4. Selecciona el rol: **Owner** o **Restricted** (Restricted es más seguro)
5. Haz clic en **Invite** o **Add**

**Listo:** El Service Account ahora tiene acceso a tu Search Console.

### Paso 5.3: Anotar la URL de Search Console
Mientras estés en Search Console:
1. En la parte superior, copia la URL exacta de tu propiedad
2. Ejemplo: `https://search.google.com/search-console/about?resource_id=sc-domain%3Aejemplo.com`
3. La URL de dominio es: `ejemplo.com` o `sc-domain:ejemplo.com`
4. **Guárdalo** (lo necesitarás en la configuración)

---

## PARTE 6: Configurar Variables de Entorno

### Paso 6.1: Guardar el archivo JSON
1. En tu computadora, crea una carpeta: `~/.seo-reports/`
2. Mueve el JSON descargado ahí
3. Renómbralo a: `credentials.json` (más fácil de recordar)
4. Ruta completa: `~/.seo-reports/credentials.json`

### Paso 6.2: Crear archivo .env
En la carpeta del proyecto (`seo-monthly-reports-skill/`):

1. Crea un archivo llamado `.env`
2. Complétalo con esto:

```bash
# Google Cloud Credentials
GOOGLE_APPLICATION_CREDENTIALS=/home/[tu-usuario]/.seo-reports/credentials.json

# Google Analytics
GA4_PROPERTY_ID=123456789

# Google Search Console
SEARCH_CONSOLE_SITE_URL=sc-domain:ejemplo.com

# Google Drive
GOOGLE_DRIVE_FOLDER_ID=tu_folder_id_aqui

# Configuración General
PROJECT_NAME=SEO Monthly Reports
LOG_LEVEL=INFO
```

**Reemplaza:**
- `[tu-usuario]` con tu nombre de usuario en Linux/Mac
- `123456789` con tu Google Analytics Property ID
- `sc-domain:ejemplo.com` con tu URL de Search Console
- `tu_folder_id_aqui` con el ID de tu carpeta en Google Drive

### Paso 6.3: Obtener Google Drive Folder ID
Para poder guardar los informes en Drive:

1. Ve a [Google Drive](https://drive.google.com)
2. Crea una carpeta llamada `Informes SEO`
3. Abre la carpeta
4. En la URL del navegador, copia el ID (después de `/folders/`)
   - Ejemplo URL: `https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I`
   - ID: `1A2B3C4D5E6F7G8H9I`
5. Pégalo en el `.env` como `GOOGLE_DRIVE_FOLDER_ID`

### Paso 6.4: Proteger el archivo .env
**IMPORTANTE:** El `.env` contiene credenciales sensibles.

1. Asegúrate de que `.env` está en `.gitignore` (si usas Git)
2. No lo compartas ni lo subas a repositorios
3. No lo envíes por email ni mensaje

```bash
# En .gitignore
.env
credentials.json
*.json
```

---

## PARTE 7: Verificar la Configuración

### Paso 7.1: Test de Autenticación
Ejecuta este script Python para verificar que todo está configurado:

```python
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# Cargar credenciales
credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
credentials = service_account.Credentials.from_service_account_file(
    credentials_path,
    scopes=[
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/webmasters.readonly',
        'https://www.googleapis.com/auth/drive',
    ]
)

# Refrescar token
credentials.refresh(Request())
print("✅ Autenticación exitosa")
print(f"Token válido hasta: {credentials.expiry}")
```

Si sale error, revisa:
1. ¿La ruta del JSON es correcta?
2. ¿El JSON tiene permisos correctos?
3. ¿El `.env` está en el lugar correcto?

---

## Checklist Final

Antes de usar la skill, verifica:

- [ ] Google Cloud Project creado
- [ ] 4 APIs habilitadas (Analytics, Search Console, Slides, Drive)
- [ ] Service Account creado
- [ ] JSON descargado y guardado en `~/.seo-reports/credentials.json`
- [ ] Service Account agregado a Google Analytics (con acceso)
- [ ] Service Account agregado a Google Search Console (con acceso)
- [ ] archivo `.env` creado con todas las variables
- [ ] `.env` protegido (en .gitignore, no compartido)
- [ ] Test de autenticación ejecutado exitosamente

---

## Próximos Pasos

Una vez que hayas completado esta configuración, estás listo para:
1. Usar la skill `seo-monthly-reports`
2. Proporcionar URL + mes, y la skill se encargará del resto
3. Los informes se guardarán automáticamente en tu carpeta de Google Drive

Si tienes problemas, revisa la sección "Solución de Problemas" en SKILL.md.
