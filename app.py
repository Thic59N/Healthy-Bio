import streamlit as st
import json
import os
import subprocess
import sys
import streamlit.components.v1 as components
from google.oauth2 import service_account

# --- 0. SÉCURITÉ BIGQUERY ---
try:
    from google.cloud import bigquery
except (ImportError, ModuleNotFoundError):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-cloud-bigquery", "db-dtypes", "google-auth"])
    from google.cloud import bigquery

# --- 1. CONNEXION BIGQUERY ---
NOM_FICHIER_JSON = "bases-sql-485411-c96fe54fc8c7.json"
current_dir = os.path.dirname(os.path.abspath(__file__))
path_to_key = os.path.join(current_dir, NOM_FICHIER_JSON)

def get_bigquery_client():
    scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
    try:
        if os.path.exists(path_to_key):
            creds = service_account.Credentials.from_service_account_info(json.load(open(path_to_key)), scopes=scopes)
            return bigquery.Client(credentials=creds, project=creds.project_id)
        if "gcp_service_account" in st.secrets:
            info = json.loads(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            return bigquery.Client(credentials=creds, project=creds.project_id)
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
    return None

client = get_bigquery_client()

# --- 2. STYLE & CONFIG ---
st.set_page_config(page_title="NutriGuide", layout="wide")

# Initialisation de la mémoire Python
if "code_scanne" not in st.session_state:
    st.session_state.code_scanne = ""

st.title("🍎 Assistant NutriGuide - V6")

# --- 3. LE SCANNER (Envoie l'info à Python via l'URL) ---

st.subheader("📷 Scanner un produit")

# Le bouton bleu ici utilise une redirection URL que Python intercepte immédiatement
scanner_html = """
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #ccc; text-align: center;">
    <b style="font-family: sans-serif;">Code détecté :</b><br>
    <span id="display_code" style="font-size: 1.5rem; font-weight: bold; color: #1a73e8;">... en attente ...</span>
    <button id="send_btn" style="display:none; width: 100%; margin-top: 10px; padding: 15px; background-color: #28a745; color: white; border: none; border-radius: 8px; font-weight: bold; font-size: 1.1rem; cursor: pointer;">
        ✅ VALIDER CE PRODUIT
    </button>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    const display = document.getElementById('display_code');
    const btn = document.getElementById('send_btn');
    let lastCode = "";

    function onScanSuccess(decodedText) {
        lastCode = decodedText;
        display.innerText = decodedText;
        btn.style.display = "block"; // On montre le bouton quand un code est trouvé
    }

    btn.onclick = function() {
        // On envoie le code à Python en rechargeant proprement l'URL parente
        const url = new URL(window.parent.location.href);
        url.searchParams.set('barcode', lastCode);
        window.parent.location.href = url.href;
    };

    let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 20, qrbox: 250 }, false);
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=550)

# --- 4. RÉCUPÉRATION PAR PYTHON ---

# Python regarde si un code est présent dans l'URL
query_params = st.query_params
if "barcode" in query_params:
    st.session_state.code_scanne = query_params["barcode"]

# Affichage du code récupéré par Python
code_final = st.text_input("Code détecté (récupéré par Python) :", value=st.session_state.code_scanne)

if st.button("🔍 ANALYSER LE PRODUIT") or (st.session_state.code_scanne and "last_analyzed" not in st.session_state):
    st.session_state.last_analyzed = st.session_state.code_scanne
    # Lancement de la recherche BigQuery...
    if client and code_final:
        try:
            TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v6"
            query = f"SELECT Product_name, Famille, Secret_Score, Url_image_small, Url FROM `{TABLE_ID}` WHERE CAST(Code_barre AS STRING) = '{code_final}' LIMIT 1"
            df = client.query(query).to_dataframe()

            if not df.empty:
                p = df.iloc[0]
                st.divider()
                c1, c2 = st.columns([1, 3])
                with c1: st.image(p['Url_image_small'])
                with c2: 
                    st.header(p['Product_name'])
                    st.info(f"Score : {p['Secret_Score']} | Catégorie : {p['Famille']}")
            else:
                st.warning("Produit inconnu.")
        except Exception as e:
            st.error(f"Erreur : {e}")

if st.button("🔄 RESET"):
    st.query_params.clear()
    st.session_state.code_scanne = ""
    st.rerun()