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

# --- 0. BLOC DE SÉCURITÉ ANTI-ERREUR ---
try:
    from google.cloud import bigquery
except (ImportError, ModuleNotFoundError):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-cloud-bigquery", "db-dtypes", "google-auth"])
    from google.cloud import bigquery

# --- 1. CONNEXION BIGQUERY (Local + Web) ---
NOM_FICHIER_JSON = "bases-sql-485411-c96fe54fc8c7.json"
current_dir = os.path.dirname(os.path.abspath(__file__))
path_to_key = os.path.join(current_dir, NOM_FICHIER_JSON)

def get_bigquery_client():
    scopes = [
        "https://www.googleapis.com/auth/bigquery",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    try:
        if os.path.exists(path_to_key):
            creds = service_account.Credentials.from_service_account_info(
                json.load(open(path_to_key)), 
                scopes=scopes
            )
            return bigquery.Client(credentials=creds, project=creds.project_id)
        
        if "gcp_service_account" in st.secrets:
            info = json.loads(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(
                info, 
                scopes=scopes
            )
            return bigquery.Client(credentials=creds, project=creds.project_id)
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
    return None

client = get_bigquery_client()

if client is None:
    st.error("❌ Connexion BigQuery impossible. Vérifie ton fichier JSON.")
    st.stop()

# --- 2. CONFIGURATION & STYLE (OPTIMISÉ SMARTPHONE) ---
st.set_page_config(page_title="NutriGuide", layout="wide")

st.markdown("""
    <style>
    /* Optimisation pour petits écrans */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
    }
    
    /* Boutons larges pour usage tactile */
    .stButton > button {
        width: 100%;
        height: 3.5rem;
        border-radius: 12px;
        font-weight: bold;
    }

    /* Style du conteneur de scan */
    #reader {
        border: 2px solid #1a2336 !important;
        border-radius: 15px !important;
        overflow: hidden;
    }

    /* Masquer les éléments inutiles sur mobile */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

st.title("🍎 NutriGuide - Mobile Scan")

# --- 3. INTERFACE SCANNER AUTOMATIQUE (JS) ---
st.subheader("📷 Scanner un produit")

# Le composant HTML5-QRCode permet de scanner en flux continu
scanner_js = """
<script src="https://unpkg.com/html5-qrcode"></script>
<div id="reader" style="width:100%;"></div>
<script>
    function onScanSuccess(decodedText, decodedResult) {
        // Envoie le résultat à Streamlit via l'API interne
        const result = decodedText;
        window.parent.postMessage({
            type: 'streamlit:set_widget_value',
            data: result,
            widgetId: 'js_code_input'
        }, '*');
    }

    let html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", 
        { fps: 10, qrbox: {width: 280, height: 180}, aspectRatio: 1.0 }, 
        /* verbose= */ false
    );
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""

activer_scan = st.toggle("Activer le scanner en direct", value=True)

if activer_scan:
    # On affiche le scanner dans un composant HTML
    components.html(scanner_js, height=380)

# Champ caché/récupérateur pour le JS (et modifiable manuellement)
final_code = st.text_input(
    "Code détecté :", 
    value=st.session_state.code_detecte, 
    key="js_code_input"
).strip()

st.divider()

# --- 4. RECHERCHE BIGQUERY (VUE V6) ---
if final_code:
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
            
            c_img, c_txt = st.columns([1, 2])
            with c_img:
                if p['Url_image_small']: st.image(p['Url_image_small'], use_container_width=True)
            with c_txt:
                st.markdown(f"### [{p['Product_name']}]({p['Url']})")
                st.info(f"Famille : {p['Famille']} | Score : {p['Secret_Score']}")

            st.write(f"### 📊 Comparaison : {p['Famille']}")
            
            query_alt = f"""
                SELECT Url_image_small, Product_name, Secret_Score, Url 
                FROM `{TABLE_ID}` 
                WHERE Famille = '{famille_clean}' 
                ORDER BY Secret_Score DESC
            """
            df_alt = client.query(query_alt).to_dataframe()

            if not df_alt.empty:
                # Sur mobile, on empile les sections pour la lisibilité
                st.success("🏆 TOP 3 PRODUITS")
                config = {
                    "Url_image_small": st.column_config.ImageColumn("Photo"), 
                    "Secret_Score": "Score", 
                    "Url": st.column_config.LinkColumn("Lien", display_text="🌐")
                }
                st.dataframe(df_alt.head(3), column_config=config, hide_index=True, use_container_width=True)
                
                st.error("📉 FLOP 3 PRODUITS")
                st.dataframe(df_alt.tail(3).sort_values("Secret_Score"), column_config=config, hide_index=True, use_container_width=True)
        else:
            st.warning(f"Produit {final_code} inconnu.")
    except Exception as e:
        st.error(f"Erreur lors de la recherche : {e}")

if st.button("🔄 RÉINITIALISER"):
    st.session_state.code_detecte = ""
    st.rerun()