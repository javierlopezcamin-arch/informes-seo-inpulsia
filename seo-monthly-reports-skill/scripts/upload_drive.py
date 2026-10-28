#!/usr/bin/env python3
"""
Subida de informes a Google Drive — carpeta por cliente.

Autenticación por OAuth de usuario (cuenta Gmail normal):
  - credenciales/credentials.json  → cliente OAuth (App de escritorio)
  - credenciales/drive_token.json  → token de usuario (se crea al autorizar)

Respaldo: domain-wide delegation con Service Account si GOOGLE_DRIVE_DELEGATE
está definido en .env (solo para cuentas Google Workspace).
"""

import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRET_PATH = os.path.join(_BASE, "credenciales", "credentials.json")
TOKEN_PATH = os.path.join(_BASE, "credenciales", "drive_token.json")


def _user_creds():
    """Carga (y refresca) las credenciales OAuth de usuario. None si falta autorizar."""
    from google.oauth2.credentials import Credentials as UserCreds
    from google.auth.transport.requests import Request
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        creds = UserCreds.from_authorized_user_file(TOKEN_PATH, SCOPES)
    except Exception:
        return None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception:
            return None
    return None


def _save_token(creds):
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())


def authorize() -> bool:
    """Lanza el flujo OAuth en el navegador y guarda el token. True si tiene éxito.

    Fuerza el selector de cuenta de Google ('select_account') para poder elegir
    con qué cuenta autorizar aunque haya otra sesión activa en el navegador.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not os.path.exists(CLIENT_SECRET_PATH):
        return False
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="select_account consent",
    )
    _save_token(creds)
    return True


def is_connected() -> bool:
    """True si hay un token de usuario válido (o refrescable)."""
    return _user_creds() is not None


def _get_service():
    # 1) OAuth de usuario (Gmail normal)
    creds = _user_creds()
    if creds:
        return build("drive", "v3", credentials=creds)
    # 2) Respaldo: Service Account con delegación (solo Workspace)
    delegate_email = os.getenv("GOOGLE_DRIVE_DELEGATE", "").strip()
    creds_path = os.path.expanduser(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""))
    if delegate_email and os.path.exists(creds_path):
        from google.oauth2.service_account import Credentials
        sa = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        return build("drive", "v3", credentials=sa.with_subject(delegate_email))
    return None


def _find_or_create_folder(service, parent_id: str, name: str) -> str:
    safe = name.replace('"', '')
    parent_q = f'"{parent_id}" in parents and ' if parent_id else "'root' in parents and "
    q = f'{parent_q}mimeType="application/vnd.google-apps.folder" and name="{safe}" and trashed=false'
    results = service.files().list(q=q, fields="files(id)").execute().get("files", [])
    if results:
        return results[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id] if parent_id else []}
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def _resolve_root(service) -> str:
    """Carpeta raíz: usa GOOGLE_DRIVE_FOLDER_ID si es accesible; si no, crea 'INFORMES SEO INPULSIA'."""
    root_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if root_id:
        try:
            service.files().get(fileId=root_id, fields="id").execute()
            return root_id
        except Exception:
            print("  ℹ️  Drive: carpeta raíz del .env no accesible, usando 'INFORMES SEO INPULSIA'")
    return _find_or_create_folder(service, "", "INFORMES SEO INPULSIA")


def upload_report(file_path: str, client_name: str) -> str | None:
    try:
        service = _get_service()
    except Exception as e:
        print(f"  ⚠️  Drive: error de autenticación — {e}")
        return None

    if not service:
        print("  ⚠️  Drive: no conectado. Pulsa 'Conectar Drive' en el panel (Config).")
        return None

    try:
        root_id = _resolve_root(service)
        client_folder_id = _find_or_create_folder(service, root_id, client_name.upper())
    except Exception as e:
        print(f"  ⚠️  Drive: error creando carpeta — {e}")
        return None

    filename = os.path.basename(file_path)
    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if file_path.endswith(".pdf"):
        mime = "application/pdf"

    try:
        q = f'"{client_folder_id}" in parents and name="{filename}" and trashed=false'
        existing = service.files().list(q=q, fields="files(id)").execute().get("files", [])
        media = MediaFileUpload(file_path, mimetype=mime)
        if existing:
            service.files().update(fileId=existing[0]["id"], media_body=media).execute()
            file_id = existing[0]["id"]
        else:
            meta = {"name": filename, "parents": [client_folder_id]}
            result = service.files().create(body=meta, media_body=media, fields="id").execute()
            file_id = result["id"]
    except Exception as e:
        print(f"  ⚠️  Drive: error subiendo archivo — {e}")
        return None

    url = f"https://drive.google.com/file/d/{file_id}/view"
    print(f"  ✅ Drive: subido a {client_name.upper()}/{filename}")
    return url


def upload_internal_doc(md_path: str, client_name: str) -> str | None:
    """Sube el archivo de propuestas (.md) a <CLIENTE>/INTERNO como Google Doc.
    Si Drive no acepta la conversión desde Markdown, lo sube como .md tal cual."""
    try:
        service = _get_service()
        if not service:
            print("  ⚠️  Drive: no conectado; el archivo de propuestas queda solo en local")
            return None
        root_id = _resolve_root(service)
        client_id = _find_or_create_folder(service, root_id, client_name.upper())
        folder_id = _find_or_create_folder(service, client_id, "INTERNO")
    except Exception as e:
        print(f"  ⚠️  Drive: error preparando carpeta INTERNO — {e}")
        return None

    name = os.path.splitext(os.path.basename(md_path))[0]
    for target_mime, label in (("application/vnd.google-apps.document", "Google Doc"), (None, ".md")):
        try:
            title = name if target_mime else os.path.basename(md_path)
            q = f'"{folder_id}" in parents and name="{title}" and trashed=false'
            existing = service.files().list(q=q, fields="files(id)").execute().get("files", [])
            media = MediaFileUpload(md_path, mimetype="text/markdown")
            if existing:
                service.files().update(fileId=existing[0]["id"], media_body=media).execute()
                file_id = existing[0]["id"]
            else:
                meta = {"name": title, "parents": [folder_id]}
                if target_mime:
                    meta["mimeType"] = target_mime
                file_id = service.files().create(body=meta, media_body=media, fields="id").execute()["id"]
            url = (f"https://docs.google.com/document/d/{file_id}/edit" if target_mime
                   else f"https://drive.google.com/file/d/{file_id}/view")
            print(f"  ✅ Drive: propuestas subidas a {client_name.upper()}/INTERNO ({label})")
            return url
        except Exception as e:
            print(f"  ⚠️  Drive: no se pudo subir como {label} — {str(e)[:120]}")
    return None
