import streamlit as st
import json
import os
import requests
from PIL import Image
import io
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

if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    #reader { border: 2px solid #1a2336 !important; border-radius: 15px !important; overflow: hidden; }
    .stTextInput > div > div > input { font-size: 20px !important; font-weight: bold; color: #FF4B4B; }
    </style>
    """, unsafe_allow_html=True)

st.title("🍎 Assistant NutriGuide - V6")

# --- 3. SCANNER AVEC TRANSFERT FORCE ---
st.subheader("📷 Scanner un produit")

scanner_html = """
<div id="reader" style="width:100%;"></div>
<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    function onScanSuccess(decodedText, decodedResult) {
        // 1. Chercher le champ de texte dans la page parente
        const inputs = window.parent.document.querySelectorAll('input');
        for (let input of inputs) {
            if (input.ariaLabel && input.ariaLabel.includes("Code détecté")) {
                input.value = decodedText;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                input.dispatchEvent(new Event('blur', { bubbles: true }));
                
                // 2. Faire vibrer le téléphone pour confirmer le scan
                if (navigator.vibrate) navigator.vibrate(200);
                
                // 3. Arrêter le scanner
                html5QrcodeScanner.clear();
                break;
            }
        }
    }
    let html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", { fps: 20, qrbox: {width: 250, height: 150}, aspectRatio: 1.0 }, false
    );
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""

if st.toggle("Activer la caméra", value=not st.session_state.code_detecte):
    components.html(scanner_html, height=400)

# Champ texte qui reçoit la valeur
final_code = st.text_input("Code détecté (modifiable manuellement) :", value=st.session_state.code_detecte).strip()

# --- BOUTON DE VALIDATION (Obligatoire si le scan ne déclenche pas le rerun) ---
if final_code:
    if st.button("🔍 ANALYSER CE PRODUIT", type="primary"):
        st.session_state.code_detecte = final_code
else:
    st.info("Visez un code-barres avec la caméra ou saisissez-le manuellement.")

st.divider()

# --- 4. RECHERCHE BIGQUERY (TA LOGIQUE ORIGINALE) ---
if final_code and client:
    try:
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v6"
        query_p = f"""
            SELECT Product_name, Famille, Secret_Score, Url_image_small, Url 
            FROM `{TABLE_ID}` 
            WHERE CAST(Code_barre AS STRING) = '{final_code}'
                OR SAFE_CAST(Code_barre AS INT64) = SAFE_CAST('{final_code}' AS INT64)
            LIMIT 1
        """
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

            st.write(f"### 📊 Comparaison dans la catégorie : {p['Famille']}")
            
            query_alt = f"""
                SELECT Url_image_small, Product_name, Secret_Score, Url 
                FROM `{TABLE_ID}` 
                WHERE Famille = '{famille_clean}' 
                ORDER BY Secret_Score DESC
            """
            df_alt = client.query(query_alt).to_dataframe()

            if not df_alt.empty:
                col_top, col_flop = st.columns(2)
                config = {
                    "Url_image_small": st.column_config.ImageColumn("Photo"), 
                    "Secret_Score": "Score", 
                    "Url": st.column_config.LinkColumn("Lien", display_text="🌐")
                }
                with col_top:
                    st.success("🏆 TOP 3")
                    st.dataframe(df_alt.head(3), column_config=config, hide_index=True, use_container_width=True)
                with col_flop:
                    st.error("📉 FLOP 3")
                    st.dataframe(df_alt.tail(3).sort_values("Secret_Score"), column_config=config, hide_index=True, use_container_width=True)
        else:
            st.warning(f"Produit {final_code} inconnu.")
    except Exception as e:
        st.error(f"Erreur : {e}")

if st.button("🔄 RÉINITIALISER"):
    st.session_state.code_detecte = ""
    st.rerun()