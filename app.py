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

if "code_recherche" not in st.session_state:
    st.session_state.code_recherche = ""

st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    div[data-testid="stTextInput"] input { background-color: #f0f2f6 !important; font-weight: bold; color: #1a2336; font-size: 1.2rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🍎 Assistant NutriGuide - V6")

# --- 3. INTERFACE ---

st.subheader("📷 Scanner un produit")

scanner_html = """
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div style="background-color: #e8f0fe; padding: 15px; border-radius: 10px; border: 1px solid #1a73e8;">
    <label style="font-family: sans-serif; font-weight: bold; color: #1a2336; display: block; margin-bottom: 5px;">Code détecté :</label>
    <input type="text" id="result_field" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #ccc; font-size: 1.3rem; font-weight: bold; box-sizing: border-box;" readonly>
    <button onclick="copyAndTransfer()" style="width: 100%; margin-top: 10px; padding: 15px; background-color: #1a73e8; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem;">
        ⚡ COLLER DANS LE CHAMP MANUEL
    </button>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    function onScanSuccess(decodedText) {
        document.getElementById('result_field').value = decodedText;
        html5QrcodeScanner.clear();
    }
    
    function copyAndTransfer() {
        var code = document.getElementById("result_field").value;
        if (!code) return;
        
        // Recherche du champ Streamlit dans la page parente
        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
        if (inputs.length > 0) {
            const targetInput = inputs[0]; 
            
            // 1. On donne le focus au champ
            targetInput.focus();
            
            // 2. On injecte la valeur
            targetInput.value = code;
            
            // 3. On déclenche les événements de saisie
            targetInput.dispatchEvent(new Event('input', { bubbles: true }));
            targetInput.dispatchEvent(new Event('change', { bubbles: true }));
            
            // 4. On enlève le focus pour valider
            targetInput.blur();
            
            console.log("Code injecté et validé : " + code);
        }
    }

    let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 20, qrbox: 250 }, false);
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=580)

# Champ Streamlit
code_manuel = st.text_input("Code manuel :", value=st.session_state.code_recherche)

if st.button("🔍 ANALYSER LE PRODUIT"):
    st.session_state.code_recherche = code_manuel.strip()
    st.rerun()

st.divider()

# --- 4. RECHERCHE BIGQUERY ---
if st.session_state.code_recherche and client:
    try:
        code_a_chercher = st.session_state.code_recherche
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v6"
        
        query_p = f"""
            SELECT Product_name, Famille, Secret_Score, Url_image_small, Url 
            FROM `{TABLE_ID}` 
            WHERE CAST(Code_barre AS STRING) = '{code_a_chercher}'
               OR SAFE_CAST(Code_barre AS INT64) = SAFE_CAST('{code_a_chercher}' AS INT64)
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
            st.warning(f"Produit '{code_a_chercher}' inconnu.")
    except Exception as e:
        st.error(f"Erreur BigQuery : {e}")

if st.button("🔄 NOUVEAU SCAN / RESET"):
    st.session_state.code_recherche = ""
    st.rerun()