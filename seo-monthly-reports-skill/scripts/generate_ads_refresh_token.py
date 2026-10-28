#!/usr/bin/env python3
"""
Genera (o renueva) el refresh token de Google Ads y lo guarda en .env.

Abre el navegador para iniciar sesión con la cuenta que tiene acceso a la MCC
(webmaster@cappuccinoestudio.com) y conceder permiso.

Uso: python3 scripts/generate_ads_refresh_token.py

Si el token vuelve a caducar a la semana, la pantalla de consentimiento OAuth del
proyecto de Google Cloud está en modo "Testing": publícala (In production).
"""

import os
import re
from google_auth_oauthlib.flow import InstalledAppFlow
from utils import write_env

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRET_PATH = os.path.join(BASE_DIR, "credenciales", "google_ads_client_secret.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def save_token(token: str) -> None:
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    line = f"GOOGLE_ADS_REFRESH_TOKEN={token}"
    pat = r"(?m)^\s*GOOGLE_ADS_REFRESH_TOKEN\s*=.*$"
    content = re.sub(pat, lambda _: line, content) if re.search(pat, content) else content + f"\n{line}\n"
    write_env(ENV_PATH, content)


def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    # prompt=consent fuerza un refresh token nuevo aunque ya se haya autorizado antes
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        raise SystemExit("Google no devolvió refresh token. Revoca el acceso en myaccount.google.com/permissions y repite.")
    save_token(creds.refresh_token)
    print("\n✅ Refresh token guardado en .env (GOOGLE_ADS_REFRESH_TOKEN).")


if __name__ == "__main__":
    main()
