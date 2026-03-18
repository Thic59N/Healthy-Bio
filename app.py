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

# --- 2. LOGIQUE SERVEUR (PYTHON) ---
st.set_page_config(page_title="NutriGuide", layout="wide")

# ÉTAPE A : Python regarde dans l'URL s'il y a un code
params = st.query_params
code_depuis_url = params.get("barcode", "")

# ÉTAPE B : Python initialise la session avec ce qu'il a trouvé dans l'URL
if "code_recherche" not in st.session_state:
    st.session_state.code_recherche = code_depuis_url
elif code_depuis_url and code_depuis_url != st.session_state.code_recherche:
    st.session_state.code_recherche = code_depuis_url

st.title("🍎 Assistant NutriGuide - V6")

# --- 3. INTERFACE SCANNER ---

st.subheader("📷 Scanner un produit")

scanner_html = f"""
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div style="background-color: #e8f0fe; padding: 15px; border-radius: 10px; border: 1px solid #1a73e8; text-align: center;">
    <span id="status" style="font-family: sans-serif; font-weight: bold; color: #1a2336;">Scannez un code-barres...</span>
    <div id="result_box" style="display:none; margin-top:10px;">
        <div style="font-size: 1.4rem; font-weight: bold; color: #1a73e8; margin-bottom:10px;" id="code_val"></div>
        <button onclick="sendToServer()" style="width: 100%; padding: 15px; background-color: #1a73e8; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">
            🚀 ENVOYER AU SERVEUR PYTHON
        </button>
    </div>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    let detectedCode = "";
    function onScanSuccess(decodedText) {{
        detectedCode = decodedText;
        document.getElementById('status').innerText = "Produit détecté !";
        document.getElementById('code_val').innerText = decodedText;
        document.getElementById('result_box').style.display = "block";
        // On arrête le scan pour économiser la batterie
        html5QrcodeScanner.clear();
    }}

    function sendToServer() {{
        // On modifie l'URL parente : Python va intercepter le changement
        const url = new URL(window.parent.location.href);
        url.searchParams.set('barcode', detectedCode);
        window.parent.location.href = url.href;
    }}

    let html5QrcodeScanner = new Html5QrcodeScanner("reader", {{ fps: 20, qrbox: 250 }}, false);
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=550)

# --- 4. TRAITEMENT PYTHON ---

# Ici, Python affiche la valeur qu'IL a récupérée de l'URL
code_final = st.text_input("Code manuel (reçu par le serveur) :", value=st.session_state.code_recherche)

if st.button("🔍 ANALYSER LE PRODUIT"):
    st.session_state.code_recherche = code_final.strip()
    # On nettoie l'URL pour éviter les boucles au prochain refresh
    st.query_params.clear()
    st.rerun()

st.divider()

# --- 5. RECHERCHE BIGQUERY ---
if st.session_state.code_recherche and client:
    try:
        code_a_chercher = st.session_state.code_recherche
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v6"
        
        query_p = f"SELECT Product_name, Famille, Secret_Score, Url_image_small, Url FROM `{TABLE_ID}` WHERE CAST(Code_barre AS STRING) = '{code_a_chercher}' OR SAFE_CAST(Code_barre AS INT64) = SAFE_CAST('{code_a_chercher}' AS INT64) LIMIT 1"
        df_p = client.query(query_p).to_dataframe()

        if not df_p.empty:
            p = df_p.iloc[0]
            famille_clean = p['Famille'].replace("'", "''")
            
            c_img, c_txt = st.columns([1, 4])
            with c_img:
                if p['Url_image_small']: st.image(p['Url_image_small'], width=150)
            with c_txt:
                st.markdown(f"## [{p['Product_name']}]({p['Url']})")
                st.info(f"Famille : {p['Famille']} | Score : {p['Secret_Score']}")
            
            # (Affichage du Top/Flop simplifié pour la démo)
            st.success(f"Analyse terminée pour le code {code_a_chercher}")
        else:
            st.warning(f"Le code {code_a_chercher} n'existe pas dans BigQuery.")
    except Exception as e:
        st.error(f"Erreur BigQuery : {e}")

if st.button("🔄 REFAIRE UN SCAN"):
    st.query_params.clear()
    st.session_state.code_recherche = ""
    st.rerun()