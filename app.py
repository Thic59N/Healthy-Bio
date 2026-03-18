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
import time

# --- 1. CONNEXION BIGQUERY ---
# (Gardez votre bloc de connexion BigQuery habituel ici)
# ... [Bloc BigQuery inchangé] ...

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="NutriGuide", layout="wide")

# On génère un ID unique pour votre session pour ne pas mélanger vos scans avec d'autres
if "session_id" not in st.session_state:
    st.session_state.session_id = str(int(time.time()))
if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

st.title("🍎 Assistant NutriGuide - V7 Bridge")

# --- 3. LE SCANNER (JAVA -> SERVEUR EXTERNE) ---
st.subheader("📷 Scanner un produit")

# L'URL du "pont" (on utilise ntfy.sh qui est gratuit et sans inscription pour ce test)
topic_bridge = f"nutriguide_scan_{st.session_state.session_id}"
bridge_url = f"https://ntfy.sh/{topic_bridge}"

scanner_html = f"""
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div style="background-color: #e8f0fe; padding: 15px; border-radius: 10px; border: 1px solid #1a73e8; text-align: center;">
    <div id="code_val" style="font-size: 1.4rem; font-weight: bold; color: #1a73e8; margin-bottom:10px;">En attente de scan...</div>
    <button id="send_btn" style="display:none; width: 100%; padding: 15px; background-color: #1a73e8; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">
        🚀 ENVOYER AU SERVEUR PYTHON
    </button>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    let detectedCode = "";
    const btn = document.getElementById('send_btn');
    const codeVal = document.getElementById('code_val');

    function onScanSuccess(decodedText) {{
        detectedCode = decodedText;
        codeVal.innerText = "Code : " + decodedText;
        btn.style.display = "block";
    }}

    btn.onclick = function() {{
        btn.innerText = "⏳ Envoi au serveur...";
        // JAVA ENVOIE LE CODE AU SERVEUR EXTERNE
        fetch('{bridge_url}', {{
            method: 'POST',
            body: detectedCode
        }}).then(() => {{
            btn.innerText = "✅ Transmis !";
            btn.style.backgroundColor = "#28a745";
        }});
    }};

    let html5QrcodeScanner = new Html5QrcodeScanner("reader", {{ fps: 20, qrbox: 250 }}, false);
    html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=550)

# --- 4. PYTHON RÉCUPÈRE LE CODE SUR LE SERVEUR ---

st.write("### 📬 Réception Serveur")
if st.button("📥 RÉCUPÉRER LE SCAN"):
    with st.spinner("Vérification du serveur..."):
        try:
            # PYTHON VA CHERCHER LE DERNIER MESSAGE SUR LE PONT
            resp = requests.get(f"{bridge_url}/json?poll=1", timeout=5)
            lines = resp.text.strip().split('\n')
            if lines:
                last_msg = json.loads(lines[-1])
                code_recu = last_msg.get("message")
                if code_recu:
                    st.session_state.code_detecte = code_recu
                    st.success(f"Code récupéré du serveur : {code_recu}")
        except Exception as e:
            st.error(f"Erreur de récupération : {e}")

# --- 5. RECHERCHE BIGQUERY ---
final_code = st.text_input("Code prêt pour analyse :", value=st.session_state.code_detecte).strip()

if final_code:
    # Votre bloc de recherche BigQuery habituel...
    st.info(f"Analyse en cours pour le code {final_code}...")
    # [Insérez ici votre code SELECT FROM TABLE_ID...]

if st.button("🔄 RESET"):
    st.session_state.code_detecte = ""
    st.rerun()