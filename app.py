import streamlit as st
import json
import requests
import time
import os
import subprocess
import sys
import streamlit.components.v1 as components
from google.oauth2 import service_account

# --- 0. CONNEXION BIGQUERY ---
try:
    from google.cloud import bigquery
except (ImportError, ModuleNotFoundError):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-cloud-bigquery", "db-dtypes", "google-auth"])
    from google.cloud import bigquery

# --- 1. CONFIGURATION & IDENTIFIANTS ---
st.set_page_config(page_title="NutriGuide V7 Bridge", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(int(time.time()))
if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

topic_bridge = f"nutriguide_{st.session_state.session_id}"
bridge_url = f"https://ntfy.sh/{topic_bridge}"

# --- 2. FONCTIONS DE CONNEXION ---
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

st.title("🍎 Assistant NutriGuide - V7 (Full Auto)")

# --- 3. LE SCANNER (ENVOI AUTO + DECLENCHEMENT RECUPERATION) ---
st.subheader("📷 Scanner un produit")

scanner_html = f"""
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div id="status_box" style="background-color: #e8f0fe; padding: 15px; border-radius: 10px; border: 1px solid #1a73e8; text-align: center;">
    <div id="code_display" style="font-size: 1.4rem; font-weight: bold; color: #1a73e8;">Visez un code-barres...</div>
    <div id="loading_msg" style="display:none; margin-top:10px; color: #28a745; font-weight: bold;">🚀 Analyse automatique en cours...</div>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    function onScanSuccess(decodedText) {{
        document.getElementById('code_display').innerText = "Code détecté : " + decodedText;
        document.getElementById('loading_msg').style.display = "block";
        
        if (window.html5QrcodeScanner) {{ window.html5QrcodeScanner.clear(); }}

        // 1. Envoi au serveur bridge
        fetch('{bridge_url}', {{ method: 'POST', body: decodedText }})
        .then(() => {{
            // 2. Délai de 30ms avant de demander à Streamlit de récupérer le code
            setTimeout(() => {{
                // On cherche le bouton "RÉCUPÉRER LE SCAN" dans l'interface parente et on clique dessus
                const btnRecup = window.parent.document.querySelector('button[kind="secondaryFormSubmit"], button[data-testid="baseButton-secondary"]');
                // Alternative : on utilise une astuce de clic sur tous les boutons contenant le texte
                const buttons = window.parent.document.querySelectorAll('button');
                buttons.forEach(btn => {{
                    if(btn.innerText.includes("RÉCUPÉRER LE SCAN")) {{
                        btn.click();
                    }}
                }});
            }}, 30);
        }});
    }}

    window.html5QrcodeScanner = new Html5QrcodeScanner("reader", {{ fps: 20, qrbox: 250 }}, false);
    window.html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=500)

# --- 4. RÉCUPÉRATION ET RECHERCHE ---

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    # Ce bouton est maintenant cliqué automatiquement par le JavaScript ci-dessus
    if st.button("📥 RÉCUPÉRER LE SCAN", use_container_width=True):
        try:
            resp = requests.get(f"{bridge_url}/json?poll=1", timeout=5)
            if resp.status_code == 200 and resp.text.strip():
                lines = resp.text.strip().split('\n')
                found = False
                for line in reversed(lines):
                    data = json.loads(line)
                    if "message" in data and data["message"]:
                        st.session_state.code_detecte = str(data["message"]).strip()
                        found = True
                        break
                if found:
                    st.rerun()
        except:
            pass

with col_btn2:
    if st.button("🔄 NOUVEAU SCAN", use_container_width=True):
        st.session_state.code_detecte = ""
        st.session_state.session_id = str(int(time.time()))
        st.rerun()

st.divider()

# --- 5. CHAMP DE SAISIE & ANALYSE ---
final_code = st.text_input("Code produit à analyser :", value=st.session_state.code_detecte).strip()

if final_code and client:
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

            st.write(f"### 📊 Comparaison : {p['Famille']}")
            
            query_alt = f"SELECT Url_image_small, Product_name, Secret_Score, Url FROM `{TABLE_ID}` WHERE Famille = '{famille_clean}' ORDER BY Secret_Score DESC"
            df_alt = client.query(query_alt).to_dataframe()

            if not df_alt.empty:
                col_top, col_flop = st.columns(2)
                config = {"Url_image_small": st.column_config.ImageColumn("Photo"), "Secret_Score": "Score", "Url": st.column_config.LinkColumn("Lien", display_text="🌐")}
                with col_top:
                    st.success("🏆 TOP 3")
                    st.dataframe(df_alt.head(3), column_config=config, hide_index=True, use_container_width=True)
                with col_flop:
                    st.error("📉 FLOP 3")
                    st.dataframe(df_alt.tail(3).sort_values("Secret_Score"), column_config=config, hide_index=True, use_container_width=True)
        else:
            st.warning(f"Le produit {final_code} est inconnu dans la base V7.")
    except Exception as e:
        st.error(f"Erreur BigQuery : {e}")