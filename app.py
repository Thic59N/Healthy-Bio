import streamlit as st
from google.cloud import bigquery
import json
import os
import requests
from PIL import Image
import io

# --- 1. CONNEXION BIGQUERY (Local + Web) ---
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

st.markdown("""
    <style>
    div[data-testid="stCameraInput"] { width: 420px !important; margin: auto; }
    </style>
    """, unsafe_allow_html=True)

st.title("🍎 Assistant Healthy Bio - V2")

if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

# --- 3. FONCTIONS DE SCAN (QUADRUPLE SÉCURITÉ) ---
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

# --- 4. INTERFACE SCANNER ---
st.subheader("📷 Scanner un produit")
activer_scan = st.toggle("Activer la caméra pour scanner", value=False)

if activer_scan:
    img_file = st.camera_input("Visez le code-barres")
    if img_file:
        with st.spinner("Analyse par les serveurs (Quadruple vérification)..."):
            img = Image.open(img_file)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            img_bytes = buffer.getvalue()

            code = scan_zxing(img_bytes)
            
            if not code:
                st.info("Serveur 1 occupé... Tentative Serveur 2")
                code = scan_off(img_bytes)
                
            if not code:
                st.info("Serveur 2 occupé... Tentative Serveur 3")
                code = scan_barcodelookup(img_bytes)
                
            if not code:
                st.info("Serveur 3 occupé... Tentative finale (Serveur 4)")
                code = scan_inlite(img_bytes)
            
            if code:
                st.session_state.code_detecte = code
                st.success(f"✅ Code détecté : {code}")
            else:
                st.error("❌ Aucun serveur n'a pu lire le code. Essayez de stabiliser l'image ou de changer l'éclairage.")
else:
    st.info("Activez l'interrupteur pour allumer la caméra.")

# --- 5. RÉSULTATS BIGQUERY (Mis à jour vers V2) ---
st.divider()
final_code = st.text_input("Code détecté (modifiable manuellement) :", value=st.session_state.code_detecte).strip()

if final_code:
    try:
        # MISE À JOUR ICI : Pointage vers la table _v4
        TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit_v4"
        
        query_p = f"""
            SELECT Product_name, Famille, Secret_Score, Url_image_small, Url 
            FROM `{TABLE_ID}` 
            WHERE CAST(Code_barre AS STRING) = '{final_code}' 
            LIMIT 1
        """
        df_p = client.query(query_p).to_dataframe()

        if not df_p.empty:
            p = df_p.iloc[0]
            c1, c2 = st.columns([1, 4])
            with c1:
                if p['Url_image_small']: st.image(p['Url_image_small'], width=150)
            with c2:
                st.markdown(f"## [{p['Product_name']}]({p['Url']})")
                st.info(f"Famille : {p['Famille']}")

            st.write(f"### 📊 Comparaison : {p['Famille']}")
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
                    st.success("🏆 TOP 3")
                    st.dataframe(df_alt.head(3), column_config=config, hide_index=True, use_container_width=True)
                with col_flop:
                    st.error("📉 FLOP 3")
                    st.dataframe(df_alt.tail(3).sort_values("Secret_Score"), column_config=config, hide_index=True, use_container_width=True)
        else:
            st.warning("Produit non trouvé dans la base.")
    except Exception as e:
        st.error(f"Erreur BigQuery : {e}")

if st.button("🔄 RÉINITIALISER"):
    st.session_state.code_detecte = ""
    st.rerun()
# Mémos codes test : 
# 3560071051181
# 8852018101147
