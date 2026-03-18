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

# --- 2. CONFIGURATION & STYLE ---
st.set_page_config(page_title="NutriGuide", layout="wide")

if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

st.markdown("""
    <style>
    div[data-testid="stCameraInput"] { width: 350px !important; margin: auto; }
    #btn-scan-gauche {
        width: 100%; height: 38px; background-color: #1a2336; color: white;
        border: 1px solid rgba(250, 250, 250, 0.2); border-radius: 4px;
        font-family: system-ui, sans-serif; font-size: 16px; cursor: pointer;
        transition: background-color 0.2s;
    }
    #btn-scan-gauche:hover { background-color: #2b3a56; }
    </style>
    """, unsafe_allow_html=True)

components.html("""
    <script>
    function setupBridge() {
        const windowParent = window.parent.document;
        const customBtn = windowParent.querySelector('#btn-scan-gauche');
        if (customBtn) {
            customBtn.onclick = function() {
                const allButtons = windowParent.querySelectorAll('button');
                const originalBtn = Array.from(allButtons).find(b => 
                    b.innerText.includes("Take Photo") && b.id !== "btn-scan-gauche"
                );
                if (originalBtn) originalBtn.click();
            };
        }
    }
    setInterval(setupBridge, 500);
    </script>
""", height=0)

st.title("🍎 Assistant NutriGuide - V7")

# --- 3. FONCTIONS DE SCAN ---
def scan_zxing(img_bytes):
    try:
        resp = requests.post('https://zxing.org/w/decode', files={'f': img_bytes}, timeout=5)
        if resp.status_code == 200 and "Raw text" in resp.text:
            start = resp.text.find("<td><pre>") + 9
            end = resp.text.find("</pre></td>", start)
            return resp.text[start:end].strip()
    except: return None

def scan_off(img_bytes):
    try:
        files = {'barcode_image': ('image.jpg', img_bytes, 'image/jpeg')}
        resp = requests.post('https://world.openfoodfacts.org/cgi/barcode.pl', files=files, timeout=5)
        if resp.status_code == 200 and resp.text.strip().isdigit(): return resp.text.strip()
    except: return None

def scan_barcodelookup(img_bytes):
    try:
        files = {'file': ('image.jpg', img_bytes, 'image/jpeg')}
        resp = requests.post('https://www.barcodelookup.com/scripts/id.php', files=files, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'): return str(data['barcode']).strip()
    except: return None

def scan_inlite(img_bytes):
    try:
        files = {'file': ('image.jpg', img_bytes, 'image/jpeg')}
        resp = requests.post('https://online-barcode-reader.inliteresearch.com/api/decode', files=files, data={'types': 'EAN13,Code128'}, timeout=7)
        if resp.status_code == 200:
            data = resp.json()
            if data: return data[0].get('Text').strip()
    except: return None

# --- 4. INTERFACE SCANNER ---
st.subheader("📷 Scanner un produit")
activer_scan = st.toggle("Activer la caméra pour scanner", value=False)

if activer_scan:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("<br>" * 8, unsafe_allow_html=True)
        st.markdown('<button id="btn-scan-gauche">Take Photo</button>', unsafe_allow_html=True)
    with col2:
        img_file = st.camera_input("Visez le code-barres")

    if img_file:
        with st.spinner("Analyse en cours..."):
            img = Image.open(img_file)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            img_bytes = buffer.getvalue()
            code = scan_zxing(img_bytes) or scan_off(img_bytes) or scan_barcodelookup(img_bytes) or scan_inlite(img_bytes)
            if code:
                st.session_state.code_detecte = code
                st.success(f"✅ Code détecté : {code}")
            else:
                st.error("❌ Impossible de lire le code.")

st.divider()
final_code = st.text_input("Code détecté (modifiable manuellement) :", value=st.session_state.code_detecte).strip()

# --- 5. RECHERCHE BIGQUERY (VUE V7) ---
if final_code:
    try:
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v7"
        
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
            st.warning(f"Produit {final_code} inconnu dans la base V7.")
    except Exception as e:
        st.error(f"Erreur lors de la recherche : {e}")

if st.button("🔄 RÉINITIALISER"):
    st.session_state.code_detecte = ""
    st.rerun()