import streamlit as st
import json
import os
import subprocess
import sys
import streamlit.components.v1 as components
from google.oauth2 import service_account

# --- BIGQUERY ---
try:
    from google.cloud import bigquery
except:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-cloud-bigquery", "db-dtypes", "google-auth"])
    from google.cloud import bigquery

# --- CONNEXION ---
NOM_FICHIER_JSON = "bases-sql-485411-c96fe54fc8c7.json"
current_dir = os.path.dirname(os.path.abspath(__file__))
path_to_key = os.path.join(current_dir, NOM_FICHIER_JSON)

def get_bigquery_client():
    scopes = ["https://www.googleapis.com/auth/bigquery"]
    try:
        if os.path.exists(path_to_key):
            creds = service_account.Credentials.from_service_account_info(
                json.load(open(path_to_key)), scopes=scopes
            )
            return bigquery.Client(credentials=creds, project=creds.project_id)
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
    return None

client = get_bigquery_client()

# --- CONFIG ---
st.set_page_config(page_title="NutriGuide", layout="wide")

if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

st.title("🍎 NutriGuide")

# --- SCANNER ---
st.subheader("📷 Scanner un produit")

scanner_html = """
<div id="reader" style="width:100%;"></div>
<script src="https://unpkg.com/html5-qrcode"></script>
<script>
function onScanSuccess(decodedText) {
    html5QrcodeScanner.clear();

    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
    if (inputs.length > 0) {
        inputs[0].value = decodedText;
        inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
    }
}
let html5QrcodeScanner = new Html5QrcodeScanner(
    "reader",
    { fps: 20, qrbox: {width: 250, height: 150} },
    false
);
html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=350)

# --- INPUT (IMPORTANT) ---
final_code = st.text_input("Code détecté :", key="barcode_input")

# --- BOUTONS (TOUJOURS VISIBLES) ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🔍 ANALYSER LE PRODUIT"):
        st.session_state.code_detecte = final_code

with col2:
    if st.button("🔄 NOUVEAU SCAN"):
        st.session_state.code_detecte = ""
        st.session_state.barcode_input = ""
        st.rerun()

st.divider()

# --- ANALYSE ---
if st.session_state.code_detecte and client:
    try:
        code = st.session_state.code_detecte
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v6"

        query = f"""
        SELECT Product_name, Famille, Secret_Score, Url_image_small, Url
        FROM `{TABLE_ID}`
        WHERE CAST(Code_barre AS STRING) = '{code}'
        LIMIT 1
        """

        df = client.query(query).to_dataframe()

        if not df.empty:
            p = df.iloc[0]

            st.success("Produit trouvé ✅")

            col1, col2 = st.columns([1, 3])

            with col1:
                if p["Url_image_small"]:
                    st.image(p["Url_image_small"])

            with col2:
                st.markdown(f"### [{p['Product_name']}]({p['Url']})")
                st.write(f"Famille : {p['Famille']}")
                st.write(f"Score : {p['Secret_Score']}")

        else:
            st.warning("Produit inconnu")

    except Exception as e:
        st.error(e)