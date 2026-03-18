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

# On vérifie si un code arrive par l'URL (méthode de secours)
params = st.query_params
code_url = params.get("barcode", "")

if "code_recherche" not in st.session_state:
    st.session_state.code_recherche = code_url
elif code_url:
    st.session_state.code_recherche = code_url

st.title("🍎 Assistant NutriGuide - V6")

# --- 3. INTERFACE SCANNER ---

st.subheader("📷 Scanner un produit")

# On utilise une méthode de redirection plus "brute" pour forcer le navigateur
scanner_html = """
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div id="ui-box" style="background-color: #e8f0fe; padding: 15px; border-radius: 10px; border: 1px solid #1a73e8; text-align: center;">
    <span id="status" style="font-family: sans-serif; font-weight: bold; color: #1a2336;">Scannez un code-barres...</span>
    <div id="result_box" style="display:none; margin-top:10px;">
        <div style="font-size: 1.4rem; font-weight: bold; color: #1a73e8; margin-bottom:10px;" id="code_val"></div>
        <button id="send_btn" style="width: 100%; padding: 15px; background-color: #1a73e8; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">
            🚀 ENVOYER AU SERVEUR
        </button>
    </div>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    let detectedCode = "";
    const status = document.getElementById('status');
    const resultBox = document.getElementById('result_box');
    const codeVal = document.getElementById('code_val');
    const btn = document.getElementById('send_btn');

    function onScanSuccess(decodedText) {
        detectedCode = decodedText;
        status.innerText = "Produit détecté !";
        codeVal.innerText = decodedText;
        resultBox.style.display = "block";
        // On stoppe le scanner proprement
        html5QrcodeScanner.clear();
    }

    btn.onclick = function() {
        btn.innerText = "⏳ Transfert...";
        btn.style.backgroundColor = "#555";
        
        // Méthode la plus compatible smartphone : top.location
        try {
            const currentUrl = window.top.location.href.split('?')[0];
            window.top.location.href = currentUrl + "?barcode=" + detectedCode;
        } catch (e) {
            // Repli si window.top est bloqué
            const currentUrl = window.parent.location.href.split('?')[0];
            window.parent.location.href = currentUrl + "?barcode=" + detectedCode;
        }
    };

    let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 20, qrbox: 250 }, false);
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=550)

# --- 4. RÉCUPÉRATION ET ANALYSE ---

code_manuel = st.text_input("Code détecté par le serveur :", value=st.session_state.code_recherche)

if st.button("🔍 ANALYSER LE PRODUIT") or (code_url and st.session_state.code_recherche == code_url):
    st.session_state.code_recherche = code_manuel.strip()
    
    if client and st.session_state.code_recherche:
        try:
            TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v6"
            query = f"SELECT Product_name, Famille, Secret_Score, Url_image_small FROM `{TABLE_ID}` WHERE CAST(Code_barre AS STRING) = '{st.session_state.code_recherche}' LIMIT 1"
            df = client.query(query).to_dataframe()

            if not df.empty:
                p = df.iloc[0]
                st.success(f"Produit trouvé : {p['Product_name']}")
                st.image(p['Url_image_small'], width=200)
            else:
                st.warning("Code inconnu dans la base.")
        except Exception as e:
            st.error(f"Erreur : {e}")

if st.button("🔄 EFFACER / RE-SCANNER"):
    st.query_params.clear()
    st.session_state.code_recherche = ""
    st.rerun()