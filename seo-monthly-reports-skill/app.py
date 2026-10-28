#!/usr/bin/env python3
import os, re, sys, subprocess
from datetime import datetime
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
MAIN_PY  = os.path.join(BASE_DIR, "main.py")
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
import json, html
from concurrent.futures import ThreadPoolExecutor
from utils import GEMINI_DAILY_LIMIT, gemini_usage, _CACHE_DIR, write_env
import access_check as ac

PREFS_PATH = os.path.join(_CACHE_DIR, "ui_prefs.json")
# Google Ads no es una sección elegible: la activa la marca de cada cliente (ADS_EN_INFORME_<CLIENTE>)
ALL_SECTIONS = ["resumen","trafico","canales","search","keywords","pagespeed","recomendaciones","conclusiones","glosario"]
DEFAULT_SECTIONS = list(ALL_SECTIONS)
SECTION_LABELS = {"resumen":"Resumen Ejecutivo","trafico":"Tráfico Web","canales":"Canales y Audiencia","search":"Rendimiento en Google","keywords":"Keywords y Páginas","ads":"Google Ads (opcional)","pagespeed":"SEO Técnico","recomendaciones":"Análisis y Recomendaciones","conclusiones":"Conclusiones","glosario":"Glosario"}
# El ajuste de datos (boost) no se recuerda a propósito: debe partir siempre de "Datos reales".
PREF_DEFAULTS = {"design": "Inpulsia 2", "sections": DEFAULT_SECTIONS, "include_notes": True,
                 "notes_level": "Analítico", "upload_drive": False}


def load_prefs():
    try:
        with open(PREFS_PATH, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    prefs = {k: data.get(k, v) for k, v in PREF_DEFAULTS.items()}
    prefs["sections"] = [s for s in prefs["sections"] if s in ALL_SECTIONS] or DEFAULT_SECTIONS
    if prefs["design"] not in ("Inpulsia 1", "Inpulsia 2"): prefs["design"] = PREF_DEFAULTS["design"]
    if prefs["notes_level"] not in ("Analítico", "Positivo"): prefs["notes_level"] = PREF_DEFAULTS["notes_level"]
    return prefs


def save_prefs(prefs):
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        tmp = f"{PREFS_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(prefs, f)
        os.replace(tmp, PREFS_PATH)
    except OSError:
        pass


def main_cmd(client, month, year, *extra):
    # -u: sin buffer, para que el log llegue línea a línea en vivo
    return [sys.executable, "-u", MAIN_PY, "--client", client.lower(),
            "--month", str(month), "--year", str(year), *extra]


def run_report(cmd, log_box, tail=16, env=None):
    """Ejecuta main.py mostrando su salida en vivo.
    Devuelve (returncode, pptx_path, drive_url, propuestas_path, avisos)."""
    lines, filepath, drive_url, prop_path, warns = [], None, None, None, []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=BASE_DIR, env=env)
    for line in proc.stdout:
        lines.append(line.rstrip())
        log_box.code("\n".join(lines[-tail:]), language=None)
        if "PPTX:" in line:
            filepath = line.split("PPTX:", 1)[1].strip()
        if "PROPUESTAS:" in line:
            prop_path = line.split("PROPUESTAS:", 1)[1].strip()
        # Avisos de main.py (⚠️ parcial, ❌ error): se muestran en el resultado, no solo en el registro
        w = line.strip()
        if w.startswith(("⚠️", "❌")) and w not in warns:
            warns.append(w)
        m = re.search(r"(https://drive\.google\.com/\S+)", line)
        if m and "Propuestas" not in line:
            drive_url = m.group(1)
    proc.wait()
    return proc.returncode, filepath, drive_url, prop_path, warns

MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
         7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@400;500;600&display=swap');
:root{--bg:#171A2E;--bg2:#21263F;--bg3:#2B3150;--line:rgba(255,255,255,0.06);--line2:rgba(255,255,255,0.12);--orange:#C6FF2A;--orange2:#D4FF5C;--text:#F0F4FF;--muted:#8A94B0;--green:#00E5A0;--shadow:0 16px 40px -12px rgba(0,0,0,.55);}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--text)!important;font-family:'DM Sans',sans-serif!important;}
[data-testid="stAppViewContainer"]>section>div{max-width:1080px!important;margin:0 auto!important;padding-top:1.25rem!important;}
*::selection{background:rgba(198,255,42,.25);}
::-webkit-scrollbar{width:9px;height:9px;}::-webkit-scrollbar-thumb{background:var(--bg3);border-radius:8px;}

/* Header */
.hdr{display:flex;align-items:center;gap:10px;padding:0 0 14px;border-bottom:1px solid var(--line);margin-bottom:16px;}
.hdr img{height:25px;filter:brightness(0) invert(1);}
.hdr .badge{margin-left:auto;}
.badge{font-family:'Syne',sans-serif;font-size:9px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--orange);background:rgba(198,255,42,.1);border:1px solid rgba(198,255,42,.28);padding:4px 11px;border-radius:30px;}

/* Title + stats */
.toprow{display:flex;align-items:center;gap:18px;margin-bottom:18px;}
.toprow-title{font-family:'Syne',sans-serif;font-size:23px;font-weight:800;line-height:1.15;letter-spacing:-.5px;margin:0;white-space:nowrap;}
.toprow-title span{color:var(--orange);}
.stats{display:flex;gap:10px;flex:1;}
.stat{flex:1;background:var(--bg2);border:1px solid var(--line);border-radius:14px;padding:11px 8px;text-align:center;transition:border-color .2s,transform .2s;}
.stat:hover{border-color:var(--line2);transform:translateY(-2px);}
.stat-n{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;color:var(--orange);display:block;line-height:1.1;}
.stat-l{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;}

/* Cards */
.card{background:var(--bg2);border:1px solid var(--line);border-radius:18px;padding:26px 28px;margin-bottom:18px;box-shadow:var(--shadow);}
.card-t{font-family:'Syne',sans-serif;font-size:11px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--muted);margin:0 0 18px;display:flex;align-items:center;gap:9px;}
.card-t::before{content:"";width:18px;height:2px;background:var(--orange);border-radius:2px;}

/* Inputs */
[data-testid="stSelectbox"]>div>div,[data-testid="stTextInput"]>div>div{background:var(--bg3)!important;border:1px solid var(--line)!important;border-radius:12px!important;color:var(--text)!important;transition:border-color .18s,box-shadow .18s!important;}
[data-testid="stSelectbox"]>div>div:hover,[data-testid="stTextInput"]>div>div:hover{border-color:var(--line2)!important;}
[data-testid="stTextInput"] input:focus,[data-baseweb="select"]:focus-within{outline:none!important;}
[data-testid="stTextInput"]>div>div:focus-within{border-color:var(--orange)!important;box-shadow:0 0 0 3px rgba(198,255,42,.14)!important;}
[data-testid="stSelectbox"] label,[data-testid="stTextInput"] label,[data-testid="stRadio"] label[data-testid="stWidgetLabel"],.stRadio>label{color:var(--muted)!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase!important;letter-spacing:1px!important;}
[data-testid="stTextInput"] input,[data-baseweb="select"] *{color:var(--text)!important;}
/* Dropdown popover */
[data-baseweb="popover"] [role="listbox"],[data-baseweb="menu"]{background:var(--bg3)!important;border:1px solid var(--line2)!important;border-radius:12px!important;box-shadow:var(--shadow)!important;}
[data-baseweb="popover"] [role="option"]:hover,li[role="option"]:hover{background:rgba(198,255,42,.12)!important;}

/* Buttons */
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button{border-radius:12px!important;font-family:'Syne',sans-serif!important;font-weight:700!important;letter-spacing:.5px!important;transition:transform .15s,box-shadow .2s,background .2s!important;}
[data-testid="stButton"] button[kind="primary"]{background:var(--orange)!important;color:#171A2E!important;border:none!important;box-shadow:0 6px 18px rgba(198,255,42,.22)!important;}
[data-testid="stButton"] button[kind="primary"]:hover{background:var(--orange2)!important;transform:translateY(-2px);box-shadow:0 12px 30px rgba(198,255,42,.4)!important;}
[data-testid="stButton"] button[kind="primary"]:active{transform:translateY(0) scale(.98);}
[data-testid="stButton"] button:not([kind="primary"]),[data-testid="stDownloadButton"] button{background:var(--bg3)!important;color:var(--text)!important;border:1px solid var(--line2)!important;}
[data-testid="stButton"] button:not([kind="primary"]):hover,[data-testid="stDownloadButton"] button:hover{border-color:var(--orange)!important;color:var(--orange)!important;transform:translateY(-1px);}
[data-testid="stButton"] button:active,[data-testid="stDownloadButton"] button:active{transform:scale(.98);}

/* Tabs */
[data-testid="stTabs"] [role="tablist"]{background:var(--bg2)!important;border:1px solid var(--line)!important;border-radius:14px!important;padding:5px!important;gap:5px!important;border-bottom:none!important;}
[data-testid="stTabs"] [role="tab"]{background:transparent!important;color:var(--muted)!important;border-radius:10px!important;font-family:'Syne',sans-serif!important;font-size:13px!important;font-weight:600!important;border:none!important;padding:9px 20px!important;transition:color .2s,background .2s!important;}
[data-testid="stTabs"] [role="tab"]:hover{color:var(--text)!important;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{background:var(--orange)!important;color:#171A2E!important;box-shadow:0 4px 14px rgba(198,255,42,.25)!important;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],[data-testid="stTabs"] [data-baseweb="tab-border"]{display:none!important;}

/* Radio pills */
[data-testid="stRadio"] [role="radiogroup"]{gap:5px!important;}
[data-testid="stRadio"] [role="radiogroup"] label{background:var(--bg3)!important;border:1px solid var(--line)!important;border-radius:10px!important;padding:5px 12px!important;transition:all .18s!important;}
[data-testid="stRadio"] [role="radiogroup"] label:hover{border-color:var(--line2)!important;}
[data-testid="stRadio"] [role="radiogroup"] label p{color:var(--text)!important;font-size:13px!important;}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){background:rgba(198,255,42,.12)!important;border-color:var(--orange)!important;}
[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) p{color:var(--orange)!important;font-weight:600!important;}
[data-testid="stRadio"] [role="radiogroup"] label>div:first-child{display:none!important;}

/* Multiselect tags compact — chips de marca: lima translúcido, texto lima, borde fino */
[data-testid="stMultiSelect"] span[data-baseweb="tag"]{font-size:11px!important;padding:2px 6px!important;height:auto!important;background:rgba(198,255,42,.1)!important;border:1px solid rgba(198,255,42,.32)!important;border-radius:8px!important;}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span{color:var(--orange)!important;font-weight:600!important;}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg{fill:var(--orange)!important;opacity:.65;}
[data-testid="stMultiSelect"] span[data-baseweb="tag"]:hover svg{opacity:1;}
[data-testid="stMultiSelect"] [data-baseweb="select"] input{font-size:12px!important;}

/* Checkbox */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] label *,
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] label div{color:var(--text)!important;opacity:1!important;font-size:13px!important;}

/* File uploader */
[data-testid="stFileUploaderDropzone"],[data-testid="stFileUploader"] section{background:var(--bg3)!important;border:1.5px dashed var(--line2)!important;border-radius:14px!important;transition:border-color .2s!important;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--orange)!important;}
[data-testid="stFileUploader"] *{color:var(--text)!important;}
[data-testid="stFileUploader"] small{color:var(--muted)!important;}

/* Alerts */
[data-testid="stAlert"]{border-radius:14px!important;border:1px solid var(--line2)!important;background:var(--bg2)!important;}

/* Status / expander */
[data-testid="stExpander"]{background:var(--bg2)!important;border:1px solid var(--line)!important;border-radius:14px!important;}
[data-testid="stExpander"] summary{color:var(--text)!important;}

/* Progress */
[data-testid="stProgress"] div[role="progressbar"]>div{background:var(--orange)!important;}
[data-testid="stProgress"] div[role="progressbar"]{background:var(--bg3)!important;}

/* Result banner */
.result{background:linear-gradient(135deg,rgba(0,229,160,.1),rgba(0,229,160,.02));border:1px solid rgba(0,229,160,.28);border-radius:18px;padding:22px 26px;margin:22px 0 6px;display:flex;align-items:center;gap:14px;box-shadow:var(--shadow);}
.result::before{content:"";flex:none;width:10px;height:10px;border-radius:50%;background:var(--green);box-shadow:0 0 14px var(--green);}
.result-tx{flex:1;}
.result-t{font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--green);margin:0 0 3px;}
.result-s{font-size:13px;color:var(--muted);margin:0;}

/* Client list rows */
.cli{display:flex;align-items:center;justify-content:space-between;padding:12px 2px;border-bottom:1px solid var(--line);font-size:13px;}
.cli:last-child{border-bottom:none;}
.cli-n{font-weight:500;color:var(--text);}
.tag{font-size:10px;font-weight:700;letter-spacing:.5px;background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.25);padding:3px 10px;border-radius:30px;}
.cli{flex-wrap:wrap;gap:6px 12px;}
.cli-meta{display:flex;align-items:center;gap:6px;}
.pill{font-size:10px;font-weight:700;letter-spacing:.5px;padding:3px 9px;border-radius:30px;border:1px solid;}
.pill.ok{background:rgba(0,229,160,.12);color:var(--green);border-color:rgba(0,229,160,.25);}
.pill.bad{background:rgba(255,107,107,.12);color:#FF8F8F;border-color:rgba(255,107,107,.3);}
.pill.unk{background:var(--bg3);color:var(--muted);border-color:var(--line2);}
.cli-age{font-size:10px;color:var(--muted);margin-left:4px;}
.cli-err{flex-basis:100%;font-size:11px;color:#FF8F8F;line-height:1.4;}
.stat-n.bad{color:#FF8F8F;}.stat-n.mut{color:var(--muted);}
[data-testid="stTextInput"] input::placeholder{color:var(--muted)!important;opacity:1!important;}
[data-testid="stExpander"] summary{font-family:'Syne',sans-serif;font-weight:700;font-size:13px;}

hr{border-color:var(--line)!important;margin:26px 0!important;}
.footer{text-align:center;font-size:10px;color:var(--muted);padding:24px 0 10px;letter-spacing:2px;text-transform:uppercase;}
[data-testid="stCode"]{background:#0E1020!important;border:1px solid var(--line)!important;border-radius:12px!important;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{color:var(--muted)!important;}
#MainMenu,footer,header{visibility:hidden;}
[data-testid="stToolbar"]{display:none;}
</style>"""

def pick_folder():
    """Abre el selector de carpetas nativo de macOS (Finder) y devuelve la ruta elegida."""
    script = 'POSIX path of (choose folder with prompt "Elige la carpeta de salida")'
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=180)
        path = r.stdout.strip().rstrip("/")
        return path or None
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def credentials_status(ads_cid):
    """Estado de lo que necesita una tanda, para verlo antes de lanzarla.
    Se cachea 10 min: Drive y Ads hacen una llamada de red. Devuelve [(etiqueta, estado, detalle)]."""
    ac.load_env()
    out = []
    sa = ac._creds_path()
    out.append(("Google", "ok" if sa and os.path.exists(sa) else "bad",
                "" if sa and os.path.exists(sa) else "No se encuentra la clave de la cuenta de servicio (GA4 y Search Console)"))
    try:
        from upload_drive import is_connected
        drive_ok = is_connected()
    except Exception as e:
        drive_ok = False
    out.append(("Drive", "ok" if drive_ok else "unk", "" if drive_ok else "Drive sin conectar o token caducado: reconéctalo en ⚙ Config"))
    if ads_cid:
        import extract_google_ads as eg
        r = eg.check_access(ads_cid)
        out.append(("Google Ads", "ok" if r["ok"] else "bad", "" if r["ok"] else r.get("error", "error")))
    return out


def gemini_usage_today():
    return gemini_usage(), GEMINI_DAILY_LIMIT


def load_clients():
    clients = []
    if not os.path.exists(ENV_PATH): return clients
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*GA4_PROPERTY_ID_([A-Z0-9_]+)\s*=\s*(\S+)", line)
            if m and m.group(2): clients.append(m.group(1))
    return sorted(set(clients))

def get_output_dir():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH,"r",encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*OUTPUT_DIR\s*=\s*(\S.*)", line)
                if m: return m.group(1).strip()
    return "~/Desktop"

def set_output_dir(path):
    path = path.strip()
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        content = f.read()
    if re.search(r"(?m)^\s*OUTPUT_DIR\s*=.*$", content):
        content = re.sub(r"(?m)^\s*OUTPUT_DIR\s*=.*$", f"OUTPUT_DIR={path}", content)
    else:
        content += f"\nOUTPUT_DIR={path}\n"
    write_env(ENV_PATH, content)

def get_api_key():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH,"r",encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*ANTHROPIC_API_KEY\s*=\s*(\S.*)", line)
                if m: return m.group(1).strip()
    return ""

def set_api_key(key):
    key = key.strip()
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        content = f.read()
    if re.search(r"(?m)^\s*ANTHROPIC_API_KEY\s*=.*$", content):
        content = re.sub(r"(?m)^\s*ANTHROPIC_API_KEY\s*=.*$", f"ANTHROPIC_API_KEY={key}", content)
    else:
        content += f"\nANTHROPIC_API_KEY={key}\n"
    write_env(ENV_PATH, content)

def get_ia_enabled():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH,"r",encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*IA_ENABLED\s*=\s*(\S+)", line)
                if m: return m.group(1).strip().lower() != "false"
    return True

def set_ia_enabled(val: bool):
    v = "true" if val else "false"
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        content = f.read()
    if re.search(r"(?m)^\s*IA_ENABLED\s*=.*$", content):
        content = re.sub(r"(?m)^\s*IA_ENABLED\s*=.*$", f"IA_ENABLED={v}", content)
    else:
        content += f"\nIA_ENABLED={v}\n"
    write_env(ENV_PATH, content)

def get_gemini_key():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH,"r",encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*GOOGLE_GEMINI_API_KEY\s*=\s*(\S.*)", line)
                if m: return m.group(1).strip()
    return ""

def set_gemini_key(key):
    key = key.strip()
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        content = f.read()
    if re.search(r"(?m)^\s*GOOGLE_GEMINI_API_KEY\s*=.*$", content):
        content = re.sub(r"(?m)^\s*GOOGLE_GEMINI_API_KEY\s*=.*$", f"GOOGLE_GEMINI_API_KEY={key}", content)
    else:
        content += f"\nGOOGLE_GEMINI_API_KEY={key}\n"
    write_env(ENV_PATH, content)

def get_logo_url(name):
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH,"r",encoding="utf-8") as f:
            for line in f:
                m = re.match(rf"\s*LOGO_URL_{name}\s*=\s*(\S.*)", line)
                if m: return m.group(1).strip()
    return ""

def add_client_to_env(name, ga4_id, sc_url, logo_url=""):
    block = f"\n# --- Cliente: {name} ---\nGA4_PROPERTY_ID_{name}={ga4_id}\nSEARCH_CONSOLE_URL_{name}={sc_url}\n"
    if logo_url:
        block += f"LOGO_URL_{name}={logo_url}\n"
    with open(ENV_PATH,"r",encoding="utf-8") as f: content = f.read()
    write_env(ENV_PATH, content + block)

def get_ads_id(name):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(rf"\s*GOOGLE_ADS_CUSTOMER_ID_{name}\s*=\s*(\S+)", line)
            if m: return m.group(1)
    return ""

def set_ads_id(name, ads_id):
    """Fija (o borra si va vacío) el Customer ID de Google Ads del cliente."""
    ads_id = re.sub(r"\D", "", ads_id or "")
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    pat = rf"(?m)^\s*GOOGLE_ADS_CUSTOMER_ID_{name}\s*=.*\n?"
    if re.search(pat, content):
        content = re.sub(pat, f"GOOGLE_ADS_CUSTOMER_ID_{name}={ads_id}\n" if ads_id else "", content)
    elif ads_id:
        content = re.sub(rf"(SEARCH_CONSOLE_URL_{name}\s*=\s*\S+)", rf"\1\nGOOGLE_ADS_CUSTOMER_ID_{name}={ads_id}", content, count=1)
    write_env(ENV_PATH, content)

def get_ads_flag(name):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(rf"\s*ADS_EN_INFORME_{name}\s*=\s*(\S+)", line)
            if m: return m.group(1).strip().lower() in ("true", "1", "si", "sí")
    return False

def set_ads_flag(name, on):
    """Marca (o desmarca) el cliente para incluir Google Ads + archivo de propuestas."""
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    pat = rf"(?m)^\s*ADS_EN_INFORME_{name}\s*=.*\n?"
    content = re.sub(pat, "", content)
    if on:
        anchor = rf"((?:GOOGLE_ADS_CUSTOMER_ID|SEARCH_CONSOLE_URL)_{name}\s*=\s*\S+)"
        m = list(re.finditer(anchor, content))
        if m:
            content = content[:m[-1].end()] + f"\nADS_EN_INFORME_{name}=true" + content[m[-1].end():]
    write_env(ENV_PATH, content)

def get_client_data(name):
    ga4_id, sc_url = "", ""
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        for line in f:
            m1 = re.match(rf"\s*GA4_PROPERTY_ID_{name}\s*=\s*(\S+)", line)
            m2 = re.match(rf"\s*SEARCH_CONSOLE_URL_{name}\s*=\s*(\S+)", line)
            if m1: ga4_id = m1.group(1)
            if m2: sc_url = m2.group(1)
    return ga4_id, sc_url

def delete_client(name):
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        lines = f.readlines()
    new_lines, skip = [], False
    for line in lines:
        if re.match(rf"\s*#\s*---\s*Cliente:\s*{name}", line):
            skip = True; continue
        if re.match(rf"\s*GA4_PROPERTY_ID_{name}\s*=", line): continue
        if re.match(rf"\s*SEARCH_CONSOLE_URL_{name}\s*=", line): continue
        if re.match(rf"\s*LOGO_URL_{name}\s*=", line): continue
        if re.match(rf"\s*GOOGLE_ADS_CUSTOMER_ID_{name}\s*=", line): continue
        if re.match(rf"\s*ADS_EN_INFORME_{name}\s*=", line): continue
        if re.match(rf"\s*WP_MCP_{name}\s*=", line): continue
        if skip and line.strip() == "": skip = False; continue
        if not skip: new_lines.append(line)
    write_env(ENV_PATH, "".join(new_lines))

def update_client(old_name, new_ga4, new_sc, new_logo=""):
    with open(ENV_PATH,"r",encoding="utf-8") as f:
        content = f.read()
    content = re.sub(rf"(GA4_PROPERTY_ID_{old_name}\s*=\s*)\S+", r"\g<1>" + new_ga4, content)
    content = re.sub(rf"(SEARCH_CONSOLE_URL_{old_name}\s*=\s*)\S+", r"\g<1>" + new_sc, content)
    if new_logo:
        if re.search(rf"(?m)^\s*LOGO_URL_{old_name}\s*=.*$", content):
            content = re.sub(rf"(?m)^\s*LOGO_URL_{old_name}\s*=.*$", f"LOGO_URL_{old_name}={new_logo}", content)
        else:
            content = re.sub(rf"(SEARCH_CONSOLE_URL_{old_name}\s*=\s*\S+)",
                             r"\1" + f"\nLOGO_URL_{old_name}={new_logo}", content)
    write_env(ENV_PATH, content)

st.set_page_config(page_title="SEO Reports - Inpulsia", page_icon="https://inpulsia.es/wp-content/uploads/2025/12/favicon-inpulsia.png", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
st.markdown('''<div class="hdr"><img src="https://inpulsia.es/wp-content/uploads/2025/12/inpulsia-logo-2.png" alt="Inpulsia"><span class="badge">SEO Reports</span></div>''', unsafe_allow_html=True)

now = datetime.now()
prev_month = now.month-1 if now.month>1 else 12
prev_year  = now.year if now.month>1 else now.year-1
clients = load_clients()

status_all = ac.load_status()
_states = [ac.state_of(status_all.get(c)) for c in clients]
n_ok, n_bad, n_unk = _states.count("ok"), _states.count("error"), _states.count("unknown")
_ia_used, _ia_limit = gemini_usage_today()
_ia_left = max(0, _ia_limit - _ia_used)
_ia_cls = "bad" if _ia_left == 0 else ""
st.markdown(f'''<div class="toprow"><p class="toprow-title">Informes SEO · <span>{MESES[prev_month]} {prev_year}</span></p><div class="stats">
<div class="stat"><span class="stat-n">{n_ok}<small style="font-size:12px;color:var(--muted)">/{len(clients)}</small></span><span class="stat-l">Con acceso</span></div>
<div class="stat"><span class="stat-n {'bad' if n_bad else 'mut'}">{n_bad}</span><span class="stat-l">Con error</span></div>
<div class="stat"><span class="stat-n {'mut' if n_unk == 0 else ''}">{n_unk}</span><span class="stat-l">Sin verificar</span></div>
<div class="stat"><span class="stat-n {_ia_cls}">{_ia_left}<small style="font-size:12px;color:var(--muted)">/{_ia_limit}</small></span><span class="stat-l">Gemini hoy</span></div>
</div></div>''', unsafe_allow_html=True)

# Estado de credenciales: se prueba Ads con el primer cliente marcado (o con Customer ID)
_ads_ids = [get_ads_id(c) for c in sorted(clients, key=lambda c: not get_ads_flag(c))]
_cred = credentials_status(next((x for x in _ads_ids if x), ""))
st.markdown('<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:-6px 0 10px;">'
            '<span style="font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;margin-right:4px;">Estado</span>'
            + "".join(f'<span class="pill {st_}" title="{html.escape(d)}">{"✓" if st_ == "ok" else "!"} {lbl}</span>' for lbl, st_, d in _cred)
            + '</div>', unsafe_allow_html=True)
for _lbl, _st, _d in _cred:
    if _st == "bad":
        st.caption(f"⚠️ {_lbl}: {_d}")

_s, _cfg_col = st.columns([5, 1])
with _cfg_col:
    if st.button("⚙ Config", use_container_width=True, key="toggle_config"):
        st.session_state["show_config"] = not st.session_state.get("show_config", False)

if st.session_state.get("show_config"):
    st.markdown('<div class="card"><p class="card-t">Configuración</p>', unsafe_allow_html=True)
    st.markdown("**Carpeta de salida**")
    _dc1, _dc2, _dc3 = st.columns([3, 1, 1])
    with _dc1:
        _out_dir = st.text_input("Carpeta", value=get_output_dir(), label_visibility="collapsed")
    with _dc2:
        if st.button("Examinar", key="cfg_pick_dir", use_container_width=True):
            _picked = pick_folder()
            if _picked:
                set_output_dir(_picked)
                st.rerun()
            else:
                st.caption("Selección cancelada.")
    with _dc3:
        if st.button("Guardar", key="cfg_save_dir", use_container_width=True):
            set_output_dir(_out_dir)
            st.success(f"Guardado: {_out_dir}")
    st.divider()
    st.markdown("**Insights con IA**")
    _cur_ia = get_ia_enabled()
    _ia_on = st.checkbox("Usar IA en conclusiones", value=_cur_ia, key="cfg_ia_toggle")
    if _ia_on != _cur_ia:
        set_ia_enabled(_ia_on)
    if _ia_on:
        st.markdown("**Gemini (gratis)**")
        _gc1, _gc2 = st.columns([3, 1])
        with _gc1:
            _gemini_key = st.text_input("Clave Gemini", value=get_gemini_key(), type="password",
                                         placeholder="AIzaSy...", key="cfg_gemini_key", label_visibility="collapsed")
        with _gc2:
            if st.button("Guardar", key="cfg_save_gemini", use_container_width=True):
                set_gemini_key(_gemini_key)
                st.rerun()
        if get_gemini_key():
            st.caption(f"Gemini: {get_gemini_key()[:12]}…  ·  Motor principal (gratis)")
            _used, _limit = gemini_usage_today()
            _left = _limit - _used
            if _left <= 0:
                if get_api_key():
                    st.info("Sin cuota de Gemini hoy: los informes usarán Claude Haiku como respaldo.")
                else:
                    st.error("⛔ Sin cuota de Gemini hoy (429). Las notas IA, conclusiones y resumen saldrán como texto genérico hasta el reinicio diario.")
            elif _left <= 3:
                st.warning(f"Gemini hoy: {_used}/{_limit} usadas · quedan {_left}")
            else:
                st.caption(f"Gemini hoy: {_used}/{_limit} usadas · quedan {_left}")
        else:
            st.caption("Obtén una clave gratis en aistudio.google.com → API Keys")
        st.markdown("**Claude Haiku (respaldo automático cuando Gemini se agota)**")
        _kc1, _kc2 = st.columns([3, 1])
        with _kc1:
            _api_key = st.text_input("Clave Anthropic", value=get_api_key(), type="password",
                                      placeholder="sk-ant-...", key="cfg_api_key", label_visibility="collapsed")
        with _kc2:
            if st.button("Guardar", key="cfg_save_key", use_container_width=True):
                set_api_key(_api_key)
                st.rerun()
        if get_api_key():
            st.caption(f"Claude: {get_api_key()[:12]}…  ·  Fallback si Gemini falla")
    else:
        st.caption("IA desactivada — se usarán conclusiones genéricas.")
    st.divider()
    st.markdown("**Google Drive**")
    try:
        from upload_drive import is_connected as _drive_connected, authorize as _drive_authorize
        _conn = _drive_connected()
    except Exception as _e:
        _drive_connected = _drive_authorize = None
        _conn = False
        st.caption(f"Drive no disponible: {_e}")
    if _drive_authorize is not None:
        if _conn:
            st.caption("✅ Conectado · los informes se subirán a tu Drive")
            if st.button("Reconectar Drive", key="cfg_drive_reconnect"):
                with st.spinner("Abriendo navegador para autorizar…"):
                    ok = _drive_authorize()
                credentials_status.clear()
                st.success("Drive reconectado.") if ok else st.error("No se pudo autorizar.")
                st.rerun()
        else:
            st.caption("No conectado. Autoriza una vez para subir informes a tu Drive.")
            if st.button("Conectar Drive", type="primary", key="cfg_drive_connect"):
                with st.spinner("Abriendo navegador para autorizar…"):
                    ok = _drive_authorize()
                credentials_status.clear()
                st.success("Drive conectado.") if ok else st.error("Falta credenciales/credentials.json o se canceló.")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ── Preferencias recordadas entre sesiones ──
_prefs = load_prefs()
for _k, _v in _prefs.items():
    st.session_state.setdefault(_k, _v)

tab1, tab2 = st.tabs(["Generar informe", "Clientes"])


def status_icon(c):
    return {"ok": "✅", "error": "❌", "unknown": "⚪"}[ac.state_of(status_all.get(c))]


def preflight(sel, month, year):
    """Revisa acceso y datos de cada cliente antes de generar. Devuelve {cliente: [(nivel, texto)]}."""
    ac.load_env()
    issues = {}
    prog = st.progress(0.0, text="Comprobando datos...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {c: pool.submit(ac.sanity_check, c, month, year) for c in sel}
        for i, (c, f) in enumerate(futs.items(), 1):
            prog.progress(i / len(futs), text=f"Comprobando datos · {c} ({i}/{len(futs)})")
            try:
                issues[c] = f.result()
            except Exception as e:
                issues[c] = [("error", str(e)[:120])]
    prog.empty()
    return issues


def show_warns(warns):
    """Avisos del informe (secciones que salieron incompletas) en un desplegable."""
    if warns:
        with st.expander(f"⚠️ {len(warns)} aviso(s): revisa antes de enviar", expanded=False):
            st.markdown("\n".join(f"- {html.escape(w.lstrip('⚠️❌ ').strip())}" for w in warns))


def execute_batch(sel, params):
    month, year, opts, budget = params["month"], params["year"], params["opts"], params["ai_budget"]
    n = len(sel)
    st.session_state.pop("last_report", None)

    def env_for(i):
        # Sin cuota de Gemini: IA_ENABLED=false evita la llamada (main.py no pisa variables ya definidas)
        return dict(os.environ, IA_ENABLED="false") if budget is not None and i >= budget else None

    if n == 1:
        c = sel[0]
        with st.status(f"Procesando {c} - {MESES[month]} {year}...", expanded=True) as status:
            rc, filepath, drive_url, prop_path, warns = run_report(main_cmd(c, month, year, *opts), st.empty(), env=env_for(0))
            if rc == 0:
                status.update(label="Informe generado", state="complete")
                st.session_state["last_report"] = {"client": c, "month": MESES[month], "year": year, "filepath": filepath,
                                                   "drive_url": drive_url, "propuestas": prop_path, "warns": warns}
            else:
                status.update(label="Error al generar", state="error")
                st.error("Revisa el registro.")
        return

    prog = st.progress(0.0, text="Iniciando...")
    results, props = [], []
    for i, c in enumerate(sel):
        prog.progress(i / n, text=f"Generando {c} ({i+1}/{n})...")
        with st.status(f"{c}", expanded=False) as status:
            rc, filepath, drive_url, prop_path, warns = run_report(main_cmd(c, month, year, *opts), st.empty(), tail=8, env=env_for(i))
            status.update(label=f"{c} · {'listo' if rc == 0 else 'error'}", state="complete" if rc == 0 else "error")
        results.append((c, rc == 0, filepath, drive_url, warns))
        if prop_path:
            props.append(prop_path)
    prog.progress(1.0, text="Completado")
    ok = sum(1 for _, r, _, _, _ in results if r)
    drive_msg = " y subidos a Drive" if params["upload_drive"] else ""
    (st.success if ok == n else st.warning)(f"{ok}/{n} informes generados{drive_msg}.")
    for c, r, fp, du, ws in results:
        link = f" · [Abrir en Drive]({du})" if du else ""
        fname = f" · `{os.path.basename(fp)}`" if fp else ""
        icon = "❌" if not r else ("⚠️" if ws else "✅")
        st.markdown(f"{icon} **{c}**{fname}{link}")
        show_warns(ws)
    _dirs = {os.path.dirname(fp) for _, r, fp, _, _ in results if r and fp}
    if len(_dirs) == 1 and st.button("Abrir carpeta de informes", use_container_width=True, key="open_batch_dir"):
        subprocess.run(["open", _dirs.pop()])
    if props:
        st.caption(f"📝 {len(props)} archivo(s) de propuestas internos en `{os.path.dirname(props[0])}`")
        if st.button("Abrir carpeta de propuestas", use_container_width=True, key="open_props_dir"):
            subprocess.run(["open", os.path.dirname(props[0])])


with tab1:
    if not clients:
        st.warning("No hay clientes configurados.")
    else:
        # ── selector de clientes (tanda) ──
        if "sel_clients" not in st.session_state:
            st.session_state["sel_clients"] = clients[:1]
        else:  # descarta clientes borrados/renombrados desde la última selección
            st.session_state["sel_clients"] = [c for c in st.session_state["sel_clients"] if c in clients]
        _sa1, _sa2, _sa4, _sa3 = st.columns(4)
        with _sa1:
            if st.button("Seleccionar todos", use_container_width=True, key="sel_all"):
                st.session_state["sel_clients"] = clients
        with _sa2:
            if st.button("Solo con acceso OK", use_container_width=True, key="sel_ok"):
                st.session_state["sel_clients"] = [c for c in clients if ac.state_of(status_all.get(c)) == "ok"]
        with _sa4:
            if st.button("Solo con Ads", use_container_width=True, key="sel_ads"):
                st.session_state["sel_clients"] = [c for c in clients if get_ads_flag(c)]
        with _sa3:
            if st.button("Ninguno", use_container_width=True, key="sel_none"):
                st.session_state["sel_clients"] = []
        sel_clients = st.multiselect("Clientes", clients, key="sel_clients",
                                     format_func=lambda c: f"{status_icon(c)} {c}", label_visibility="collapsed")
        if n_bad or n_unk:
            st.caption(f"❌ {n_bad} con error de acceso · ⚪ {n_unk} sin verificar — usa «Verificar todos» en la pestaña Clientes.")

        col1, col2, col3 = st.columns(3)
        with col1:
            month = st.selectbox("Mes", list(MESES.keys()), index=prev_month-1, format_func=lambda m:MESES[m])
        with col2:
            years = list(range(now.year,now.year-4,-1))
            year  = st.selectbox("Año", years, index=years.index(prev_year))
        with col3:
            design_opt = st.selectbox("Diseño", ["Inpulsia 2", "Inpulsia 1"], key="design")
            design_val = {"Inpulsia 1": "inpulsia1", "Inpulsia 2": "inpulsia2"}[design_opt]
        col_boost, col_sec = st.columns([35, 65])
        with col_boost:
            boost_opt = st.radio("Ajuste de datos", ["Datos reales", "+10%", "+20%", "+30%", "+50%"], horizontal=True, key="boost")
            boost_val = {"Datos reales": "1.0", "+10%": "1.10", "+20%": "1.20", "+30%": "1.30", "+50%": "1.50"}[boost_opt]
        with col_sec:
            st.markdown('<p style="font-size:0.85rem;color:rgba(255,255,255,.55);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">Opciones del informe</p>', unsafe_allow_html=True)
            sections_sel = st.multiselect("Secciones", ALL_SECTIONS, format_func=lambda s:SECTION_LABELS[s], key="sections", label_visibility="collapsed")
            _nc1, _nc2 = st.columns([1, 1])
            with _nc1:
                include_notes = st.checkbox("Incluir notas IA", key="include_notes")
            with _nc2:
                notes_level_opt = st.selectbox("Nivel de notas", ["Analítico", "Positivo"], key="notes_level", label_visibility="collapsed")
                notes_level = {"Analítico": "analitico", "Positivo": "positivo"}[notes_level_opt]
        upload_drive = st.checkbox("Subir a Google Drive", key="upload_drive")
        _marked = [c for c in sel_clients if get_ads_flag(c) and get_ads_id(c)]
        if _marked:
            st.caption(f"📣 Google Ads + archivo de propuestas en {len(_marked)} de {len(sel_clients)} cliente(s) "
                       f"({', '.join(_marked[:5])}{'…' if len(_marked) > 5 else ''}) · +{len(_marked)} llamada(s) de Gemini, sin respaldo de pago")

        # ── cuota de IA: estimación y reparto ──
        _n_sel = len(sel_clients)
        _claude_backup = bool(get_api_key())
        ia_active = get_ia_enabled() and (bool(get_gemini_key()) or _claude_backup)
        ai_budget = None
        _over = max(0, _n_sel - _ia_left)
        if ia_active and _over:
            if _claude_backup:
                st.info(f"Gemini cubre {min(_n_sel, _ia_left)} informe(s) hoy; los {_over} restantes usarán Claude Haiku como respaldo (unos céntimos en total).")
            else:
                st.warning(f"⛔ Quedan {_ia_left} llamadas de Gemini hoy y esta tanda necesita {_n_sel} (1 por informe). "
                           f"{_over} informe(s) saldrían con texto genérico.")
                if st.checkbox("Generar sin IA los que superen la cuota", value=True, key="skip_ai_over_quota"):
                    ai_budget = _ia_left
        if _n_sel:
            if not ia_active:
                _ia_txt = "IA desactivada"
            elif _claude_backup and _over:
                _ia_txt = f"IA: {min(_n_sel, _ia_left)} con Gemini + {_over} con Claude"
            elif ai_budget is not None:
                _ia_txt = f"IA en {min(_n_sel, _ia_left)} de {_n_sel} (quedan {_ia_left} llamadas hoy)"
            else:
                _ia_txt = f"IA en {_n_sel} (quedan {_ia_left} llamadas hoy)"
            st.caption(f"{_n_sel} informe(s) · {MESES[month]} {year} · {design_opt} · {_ia_txt}")

        _cur_prefs = {k: st.session_state.get(k, v) for k, v in PREF_DEFAULTS.items()}
        if _cur_prefs != _prefs:
            save_prefs(_cur_prefs)

        _btn_label = "Generar informe" if _n_sel == 1 else f"Generar {_n_sel} informes" if _n_sel > 1 else "Selecciona al menos un cliente"
        _gen = st.button(_btn_label, type="primary", use_container_width=True, disabled=_n_sel == 0)
        _opts = ["--boost", boost_val, "--sections", ",".join(sections_sel), "--design", design_val, "--notes-level", notes_level]
        if not include_notes:
            _opts.append("--no-notes")
        if upload_drive:
            _opts.append("--upload-drive")
        params = {"month": month, "year": year, "opts": _opts, "ai_budget": ai_budget, "upload_drive": upload_drive}

        if _gen:
            st.session_state.pop("pending", None)
            issues = preflight(sel_clients, month, year)
            flagged = {c: v for c, v in issues.items() if any(l in ("warn", "error") for l, _ in v)}
            if flagged:
                st.session_state["pending"] = {"clients": list(sel_clients), "issues": flagged, "params": params}
            else:
                for t in sorted({t for v in issues.values() for l, t in v if l == "info"}):
                    st.info(t)
                execute_batch(sel_clients, params)

        pending = st.session_state.get("pending")
        pend_box = st.empty()
        if pending:
            fl = pending["issues"]
            keep = [c for c in pending["clients"] if c not in fl]
            with pend_box.container():
                st.warning(f"{len(fl)} de {len(pending['clients'])} cliente(s) con datos sospechosos o sin acceso. Revisa antes de generar:")
                for c, v in fl.items():
                    lines = "".join(f"<div class='cli-err'>{'❌' if l == 'error' else '⚠️'} {html.escape(t)}</div>" for l, t in v if l != "info")
                    st.markdown(f"<div class='cli'><span class='cli-n'>{c}</span>{lines}</div>", unsafe_allow_html=True)
                _pb1, _pb2, _pb3 = st.columns(3)
                with _pb1:
                    go_all = st.button("Generar todos igualmente", use_container_width=True, key="pend_all")
                with _pb2:
                    go_ok = st.button(f"Omitir los marcados ({len(keep)})", use_container_width=True, key="pend_skip", disabled=not keep)
                with _pb3:
                    cancel = st.button("Cancelar", use_container_width=True, key="pend_cancel")
            if go_all or go_ok or cancel:
                st.session_state.pop("pending", None)
                pend_box.empty()
                if not cancel:
                    execute_batch(pending["clients"] if go_all else keep, pending["params"])

    report = st.session_state.get("last_report")
    if report:
        fname = os.path.basename(report["filepath"]) if report["filepath"] else ""
        drive_html = f' · <a href="{report["drive_url"]}" target="_blank" style="color:var(--green);text-decoration:none;">Abrir en Drive</a>' if report.get("drive_url") else ""
        st.markdown(f'''<div class="result"><div class="result-tx"><p class="result-t">Informe listo · {report["client"]}</p><p class="result-s">{report["month"]} {report["year"]} · {fname}{drive_html}</p></div></div>''', unsafe_allow_html=True)
        show_warns(report.get("warns"))
        if report["filepath"] and os.path.exists(report["filepath"]):
            pdf_path = report["filepath"].rsplit(".", 1)[0] + ".pdf"
            has_pdf = os.path.exists(pdf_path)
            cols = st.columns(3 if has_pdf else 2)
            with cols[0]:
                with open(report["filepath"],"rb") as f:
                    st.download_button("Descargar PPTX", f.read(), file_name=fname,
                                       mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                       use_container_width=True)
            if has_pdf:
                with cols[1]:
                    pdf_fname = os.path.basename(pdf_path)
                    with open(pdf_path,"rb") as f:
                        st.download_button("Descargar PDF", f.read(), file_name=pdf_fname,
                                           mime="application/pdf", use_container_width=True)
            with cols[-1]:
                if st.button("Abrir carpeta",use_container_width=True): subprocess.run(["open",os.path.dirname(report["filepath"])])
        _prop = report.get("propuestas")
        if _prop and os.path.exists(_prop):
            with open(_prop, "rb") as f:
                st.download_button("📝 Archivo de propuestas (interno)", f.read(), file_name=os.path.basename(_prop),
                                   mime="text/markdown", use_container_width=True)
            st.caption("Para trabajarlo en el proyecto de Claude del cliente. No enviar al cliente.")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _pill(label, ok):
    return f'<span class="pill {"ok" if ok else "bad"}">{label}</span>'


def _verify_flash(c, entry):
    if ac.state_of(entry) == "ok":
        return ("success", f"{c}: acceso correcto a GA4 y Search Console.")
    return ("error", f"{c} — {ac.error_text(entry)}")


with tab2:
    _flash = st.session_state.pop("flash", None)
    if _flash:
        getattr(st, _flash[0])(_flash[1])

    tb1, tb2, tb3 = st.columns([3, 2, 2], vertical_alignment="center")
    with tb1:
        q = st.text_input("Buscar", placeholder="Buscar cliente…", key="cli_q", label_visibility="collapsed")
    with tb2:
        flt = st.selectbox("Estado", ["Todos", "Con error", "Sin verificar", "Con acceso", "Con Ads marcado", "Con Customer ID", "Sin Customer ID", "Error en Ads"], key="cli_f", label_visibility="collapsed")
    with tb3:
        verify_all = st.button("Verificar todos", type="primary", use_container_width=True, key="verify_all", disabled=not clients)
    if verify_all:
        credentials_status.clear()
        prog = st.progress(0.0, text="Verificando accesos…")
        res = ac.check_and_store(clients, lambda i, n, c: prog.progress(i / n, text=f"Verificando {c} ({i}/{n})"))
        bad = [c for c in clients if ac.state_of(res[c]) == "error"]
        st.session_state["flash"] = (
            ("success", f"Verificados {len(clients)} clientes: todos con acceso.") if not bad else
            ("warning", f"Verificados {len(clients)} clientes: {len(bad)} con error de acceso ({', '.join(bad[:6])}{'…' if len(bad) > 6 else ''})."))
        st.rerun()

    with st.expander("＋ Añadir cliente"):
        _an = st.session_state.setdefault("add_n", 0)
        name_raw = st.text_input("Nombre", placeholder="MITIENDA", key=f"add_name_{_an}")
        c1, c2 = st.columns(2)
        with c1:
            ga4_id = st.text_input("GA4 Property ID", placeholder="510058187", key=f"add_ga4_{_an}")
        with c2:
            sc_url = st.text_input("URL Search Console", placeholder="https://mitienda.com/  o  sc-domain:mitienda.com", key=f"add_sc_{_an}")
        logo_url = st.text_input("Logo (opcional)", placeholder="https://mitienda.com/logo.png", key=f"add_logo_{_an}")
        ads_new = st.text_input("Google Ads Customer ID (opcional)", placeholder="123-456-7890", key=f"add_ads_{_an}")
        ads_flag_new = st.checkbox("Incluir Google Ads y archivo de propuestas en el informe", key=f"add_adsflag_{_an}")
        st.caption("Comparte GA4 y Search Console con **seo-reports@cappuccino.iam.gserviceaccount.com** — GA4: rol Lector · SC: permiso Completo")
        if st.button("Guardar cliente", type="primary", use_container_width=True, key=f"add_save_{_an}"):
            name = re.sub(r"[^A-Z0-9_]","",name_raw.upper().replace(" ","_"))
            errors=[]
            if not name: errors.append("El nombre no puede estar vacio.")
            if name in load_clients(): errors.append(f"El cliente {name} ya existe.")
            if not ga4_id.strip().isdigit(): errors.append("El GA4 Property ID debe ser solo numeros.")
            if not sc_url.strip().startswith(("http://","https://","sc-domain:")): errors.append("La URL debe empezar por https://, http:// o sc-domain:")
            if ads_new.strip() and len(re.sub(r"\D", "", ads_new)) != 10: errors.append("El Customer ID de Google Ads debe tener 10 dígitos.")
            if ads_flag_new and not ads_new.strip(): errors.append("Para incluir Google Ads hace falta el Customer ID.")
            if errors:
                for e in errors: st.error(e)
            else:
                add_client_to_env(name,ga4_id.strip(),sc_url.strip(),logo_url.strip())
                if ads_new.strip(): set_ads_id(name, ads_new)
                if ads_flag_new: set_ads_flag(name, True)
                with st.spinner("Validando acceso..."):
                    entry = ac.check_and_store([name])[name]
                if ac.state_of(entry) == "ok":
                    st.session_state["flash"] = ("success", f"{name} añadido con acceso a GA4 y Search Console.")
                else:
                    st.session_state["flash"] = ("warning", f"{name} guardado, pero sin acceso — {ac.error_text(entry)}")
                st.session_state["add_n"] = _an + 1
                st.rerun()

    if not clients:
        st.caption("No hay clientes todavía.")
    else:
        _states_by = {"Con error": "error", "Sin verificar": "unknown", "Con acceso": "ok"}

        def _match(c):
            if flt == "Todos": return True
            if flt in _states_by: return ac.state_of(status_all.get(c)) == _states_by[flt]
            if flt == "Con Ads marcado": return get_ads_flag(c)
            if flt == "Con Customer ID": return bool(get_ads_id(c))
            if flt == "Sin Customer ID": return not get_ads_id(c)
            if flt == "Error en Ads": return bool(ac.ads_error_text(status_all.get(c)))
            return True
        shown = [c for c in clients if (not q.strip() or _norm(q) in _norm(c)) and _match(c)]
        st.caption(f"Mostrando {len(shown)} de {len(clients)}")
        for c in shown:
            entry = status_all.get(c)
            if entry:
                pills = _pill("GA4", entry["ga4"]["ok"]) + _pill("SC", entry["sc"]["ok"])
                if entry.get("ads") and get_ads_flag(c):
                    pills += _pill("ADS", entry["ads"]["ok"])
                pills += f'<span class="cli-age">{ac.age_label(entry)}</span>'
            else:
                pills = '<span class="pill unk">Sin verificar</span>'
            err = "".join(f'<div class="cli-err">{html.escape(t)}</div>'
                          for t in (ac.error_text(entry) if ac.state_of(entry) == "error" else "", ac.ads_error_text(entry)) if t)
            rc1, rc2, rc3, rc4 = st.columns([6, 1, 1, 1], vertical_alignment="center")
            with rc1:
                st.markdown(f'<div class="cli"><span class="cli-n">{c}</span><span class="cli-meta">{pills}</span>{err}</div>', unsafe_allow_html=True)
            with rc2:
                if st.button("Verificar", key=f"chk_{c}", use_container_width=True):
                    with st.spinner(f"Verificando {c}…"):
                        st.session_state["flash"] = _verify_flash(c, ac.check_and_store([c])[c])
                    st.rerun()
            with rc3:
                if st.button("Editar", key=f"edit_{c}", use_container_width=True):
                    st.session_state["editing"] = c
                    st.session_state.pop("confirm_del", None)
            with rc4:
                if st.button("Borrar", key=f"del_{c}", use_container_width=True):
                    st.session_state["confirm_del"] = c
                    st.session_state.pop("editing", None)

            if st.session_state.get("editing") == c:
                ga4_val, sc_val = get_client_data(c)
                new_ga4  = st.text_input("GA4 Property ID", value=ga4_val, key=f"edit_ga4_{c}")
                new_sc   = st.text_input("URL Search Console", value=sc_val, key=f"edit_sc_{c}")
                new_logo = st.text_input("Logo (opcional)", value=get_logo_url(c), key=f"edit_logo_{c}", placeholder="https://cliente.com/logo.png")
                new_ads  = st.text_input("Google Ads Customer ID (opcional)", value=get_ads_id(c), key=f"edit_ads_{c}", placeholder="123-456-7890")
                new_ads_flag = st.checkbox("Incluir Google Ads y archivo de propuestas en el informe", value=get_ads_flag(c), key=f"edit_adsflag_{c}")
                cap_dir = os.path.join(BASE_DIR, "capturas", c)
                st.caption("Capturas de paneles")
                uploads = st.file_uploader("Capturas PNG/JPG", type=["png","jpg","jpeg"], accept_multiple_files=True, key=f"caps_{c}")
                if uploads:
                    os.makedirs(cap_dir, exist_ok=True)
                    for up in uploads:
                        with open(os.path.join(cap_dir, up.name), "wb") as f:
                            f.write(up.getbuffer())
                    st.success(f"{len(uploads)} captura(s) guardada(s).")
                existing = sorted(os.listdir(cap_dir)) if os.path.isdir(cap_dir) else []
                existing = [e for e in existing if e.lower().endswith((".png",".jpg",".jpeg"))]
                if existing:
                    for img in existing:
                        ic1, ic2 = st.columns([4,1])
                        with ic1: st.markdown(f'<div class="cli"><span class="cli-n">{img}</span></div>', unsafe_allow_html=True)
                        with ic2:
                            if st.button("Quitar", key=f"rm_{c}_{img}", use_container_width=True):
                                os.remove(os.path.join(cap_dir, img))
                                st.rerun()

                def _edit_errors():
                    errs = []
                    if not new_ga4.strip().isdigit(): errs.append("GA4 Property ID debe ser numeros.")
                    if not new_sc.strip().startswith(("http://","https://","sc-domain:")): errs.append("La URL debe empezar por https://, http:// o sc-domain:")
                    if new_ads.strip() and len(re.sub(r"\D", "", new_ads)) != 10: errs.append("El Customer ID de Google Ads debe tener 10 dígitos.")
                    if new_ads_flag and not new_ads.strip(): errs.append("Para incluir Google Ads hace falta el Customer ID.")
                    return errs

                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    _do_save = st.button("Guardar cambios", type="primary", use_container_width=True, key=f"save_{c}")
                with ec2:
                    _do_validate = st.button("Verificar acceso", use_container_width=True, key=f"validate_{c}")
                with ec3:
                    if st.button("Cancelar", use_container_width=True, key=f"cancel_{c}"):
                        st.session_state.pop("editing", None)
                        st.rerun()
                if _do_save or _do_validate:
                    errors = _edit_errors()
                    if errors:
                        for e in errors: st.error(e)
                    else:
                        update_client(c, new_ga4.strip(), new_sc.strip(), new_logo.strip())
                        set_ads_id(c, new_ads)
                        set_ads_flag(c, new_ads_flag)
                        if _do_save:
                            ac.forget_client(c)  # los datos cambiaron: el estado anterior ya no vale
                            st.session_state.pop("editing", None)
                            st.session_state["flash"] = ("success", f"{c} actualizado. Pulsa «Verificar» para comprobar el acceso.")
                        else:
                            with st.spinner("Verificando acceso..."):
                                st.session_state["flash"] = _verify_flash(c, ac.check_and_store([c])[c])
                        st.rerun()

            if st.session_state.get("confirm_del") == c:
                st.warning(f"¿Borrar {c}?")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("Si, borrar", type="primary", use_container_width=True, key=f"confirm_del_{c}"):
                        delete_client(c)
                        ac.forget_client(c)
                        st.session_state.pop("confirm_del", None)
                        st.rerun()
                with dc2:
                    if st.button("Cancelar", use_container_width=True, key=f"cancel_del_{c}"):
                        st.session_state.pop("confirm_del", None)
                        st.rerun()

st.markdown('<hr><p class="footer">INPULSIA - SISTEMA DE INFORMES SEO AUTOMATIZADOS</p>', unsafe_allow_html=True)
