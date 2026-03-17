import streamlit as st
import json
import os
import requests
from PIL import Image
import io
import subprocess
import sys
import streamlit.components.v1 as components

# --- 0. BLOC DE SÉCURITÉ ANTI-ERREUR ---
try:
    from google.cloud import bigquery
except (ImportError, ModuleNotFoundError):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-cloud-bigquery", "db-dtypes"])
    from google.cloud import bigquery

# --- 1. CONNEXION BIGQUERY ---
NOM_FICHIER_JSON = "bases-sql-485411-c96fe54fc8c7.json"
current_dir = os.path.dirname(os.path.abspath(__file__))
path_to_key = os.path.join(current_dir, NOM_FICHIER_JSON)

def get_bigquery_client():
    if os.path.exists(path_to_key):
        return bigquery.Client.from_service_account_info(json.load(open(path_to_key)))
    try:
        if "gcp_service_account" in st.secrets:
            info = json.loads(st.secrets["gcp_service_account"])
            return bigquery.Client.from_service_account_info(info)
    except: pass
    return None

client = get_bigquery_client()

if client is None:
    st.error("❌ Connexion BigQuery impossible. Vérifie ton fichier JSON.")
    st.stop()

# --- 2. CONFIGURATION & STYLE ---
st.set_page_config(page_title="NutriGuide", layout="wide")

# Initialisation impérative du session_state pour éviter l'AttributeError
if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

# Injection CSS : Taille caméra et style bouton
st.markdown("""
    <style>
    /* Réduction de la taille du bloc caméra */
    div[data-testid="stCameraInput"] { 
        width: 350px !important; 
        margin: auto; 
    }
    
    /* Bouton de gauche identique à l'original Streamlit */
    #btn-scan-gauche {
        width: 100%;
        height: 38px;
        background-color: #1a2336;
        color: white;
        border: 1px solid rgba(250, 250, 250, 0.2);
        border-radius: 4px;
        font-family: system-ui, -apple-system, sans-serif;
        font-size: 16px;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    #btn-scan-gauche:hover {
        background-color: #2b3a56;
    }
    </style>
    """, unsafe_allow_html=True)

# Pont JavaScript pour lier les deux boutons
components.html("""
    <script>
    function setupBridge() {
        const windowParent = window.parent.document;
        const customBtn = windowParent.querySelector('#btn-scan-gauche');
        if (customBtn) {
            customBtn.onclick = function() {
                const allButtons = windowParent.querySelectorAll('button');
                // On cherche le bouton original qui contient "Take Photo"
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

st.title("🍎 Assistant NutriGuide - V2")

# --- 3. FONCTIONS DE SCAN (LES 4 SERVEURS) ---
def scan_zxing(img_bytes):
    try:
        url_zxing = 'https://zxing.org/w/decode' 
        files = {'f': img_bytes}
        resp = requests.post(url_zxing, files=files, timeout=5)
        if resp.status_code == 200 and "Raw text" in resp.text:
            start = resp.text.find("<td><pre>") + 9
            end = resp.text.find("</pre></td>", start)
            return resp.text[start:end].strip()
    except: return None

def scan_off(img_bytes):
    try:
        files = {'barcode_image': ('image.jpg', img_bytes, 'image/jpeg')}
        resp = requests.post('https://world.openfoodfacts.org/cgi/barcode.pl', files=files, timeout=5)
        if resp.status_code == 200 and resp.text.strip().isdigit():
            return resp.text.strip()
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
        url_inlite = 'https://online-barcode-reader.inliteresearch.com/api/decode'
        files = {'file': ('image.jpg', img_bytes, 'image/jpeg')}
        params = {'types': 'EAN13,Code128'} 
        resp = requests.post(url_inlite, files=files, data=params, timeout=7)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                return data[0].get('Text').strip()
    except: return None

# --- 4. INTERFACE ---
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
            
            # Tentative sur les 4 serveurs
            code = scan_zxing(img_bytes)
            if not code: code = scan_off(img_bytes)
            if not code: code = scan_barcodelookup(img_bytes)
            if not code: code = scan_inlite(img_bytes)
            
            if code:
                st.session_state.code_detecte = code
                st.success(f"✅ Code détecté : {code}")
            else:
                st.error("❌ Impossible de lire le code. Essayez de mieux l'éclairer.")
else:
    st.info("Activez l'interrupteur pour utiliser le scanner.")

st.divider()

# Champ de saisie lié au session_state
final_code = st.text_input("Code détecté (modifiable manuellement) :", value=st.session_state.code_detecte).strip()

# --- 5. RECHERCHE BIGQUERY ET AFFICHAGE ---
if final_code:
    try:
<<<<<<< HEAD
        # MISE À JOUR ICI : Pointage vers la table _v4
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v4"
=======
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v2"
>>>>>>> e11f45ec51490ac8cc12a0383239e98786edeb0e
        
        # Requête produit principal
        query_p = f"""
            SELECT Product_name, Famille, Secret_Score, Url_image_small, Url 
            FROM `{TABLE_ID}` 
            WHERE CAST(Code_barre AS STRING) = '{final_code}' 
            LIMIT 1
        """
        df_p = client.query(query_p).to_dataframe()

        if not df_p.empty:
            p = df_p.iloc[0]
            c_img, c_txt = st.columns([1, 4])
            with c_img:
                if p['Url_image_small']: st.image(p['Url_image_small'], width=150)
            with c_txt:
                st.markdown(f"## [{p['Product_name']}]({p['Url']})")
                st.info(f"Famille : {p['Famille']} | Score : {p['Secret_Score']}")

            st.write(f"### 📊 Comparaison dans la catégorie : {p['Famille']}")
            
            # Requête pour les alternatives (TOP/FLOP)
            query_alt = f"""
                SELECT Url_image_small, Product_name, Secret_Score, Url 
                FROM `{TABLE_ID}` 
                WHERE Famille = "{p['Famille']}" 
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
                    st.success("🏆 TOP 3 (Meilleurs scores)")
                    st.dataframe(df_alt.head(3), column_config=config, hide_index=True, use_container_width=True)
                with col_flop:
                    st.error("📉 FLOP 3 (Moins bons scores)")
                    # On prend les 3 derniers et on les trie pour voir le pire en haut
                    st.dataframe(df_alt.tail(3).sort_values("Secret_Score"), column_config=config, hide_index=True, use_container_width=True)
        else:
            st.warning("Produit inconnu dans notre base v2.")
    except Exception as e:
        st.error(f"Erreur lors de la recherche : {e}")

if st.button("🔄 RÉINITIALISER"):
    st.session_state.code_detecte = ""
    st.rerun()