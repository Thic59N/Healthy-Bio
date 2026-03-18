import streamlit as st
import json
import requests
import time
import streamlit.components.v1 as components

# --- CONFIGURATION ---
st.set_page_config(page_title="NutriGuide V7 Bridge", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(int(time.time()))
if "code_detecte" not in st.session_state:
    st.session_state.code_detecte = ""

# Identifiant unique pour ton "pont" serveur
topic_bridge = f"nutriguide_{st.session_state.session_id}"
bridge_url = f"https://ntfy.sh/{topic_bridge}"

st.title("🍎 Assistant NutriGuide - V7 Bridge")

# --- 1. LE SCANNER (JAVA -> SERVEUR) ---
st.subheader("📷 Scanner un produit")

scanner_html = f"""
<div id="reader" style="width:100%; border: 2px solid #1a2336; border-radius: 15px; overflow: hidden; margin-bottom:10px;"></div>
<div id="ui-box" style="background-color: #e8f0fe; padding: 15px; border-radius: 10px; border: 1px solid #1a73e8; text-align: center;">
    <div id="code_display" style="font-size: 1.4rem; font-weight: bold; color: #1a73e8; margin-bottom:10px;">Scannez un code...</div>
    <button id="send_btn" style="display:none; width: 100%; padding: 15px; background-color: #1a73e8; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">
        🚀 ENVOYER AU SERVEUR PYTHON
    </button>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
    let detectedCode = "";
    const btn = document.getElementById('send_btn');
    const display = document.getElementById('code_display');

    function onScanSuccess(decodedText) {{
        detectedCode = decodedText;
        display.innerText = "Code détecté : " + decodedText;
        btn.style.display = "block";
        
        // --- ARRET DU SCAN IMMEDIAT ---
        if (window.html5QrcodeScanner) {{
            window.html5QrcodeScanner.clear().then(() => {{
                console.log("Scanner arrêté.");
            }}).catch(err => console.error("Erreur arrêt scanner", err));
        }}
    }}

    btn.onclick = function() {{
        btn.innerText = "⏳ Envoi en cours...";
        fetch('{bridge_url}', {{
            method: 'POST',
            body: detectedCode
        }}).then(response => {{
            if(response.ok) {{
                btn.innerText = "✅ Transmis au serveur !";
                btn.style.backgroundColor = "#28a745";
            }}
        }});
    }};

    // On stocke le scanner dans window pour y accéder partout
    window.html5QrcodeScanner = new Html5QrcodeScanner("reader", {{ fps: 20, qrbox: 250 }}, false);
    window.html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(scanner_html, height=550)

# --- 2. RÉCUPÉRATION SERVEUR (PYTHON) ---

st.write("### 📬 Réception par le Serveur Python")
if st.button("📥 RÉCUPÉRER LE CODE DU SERVEUR"):
    try:
        # On demande au serveur le dernier message
        resp = requests.get(f"{bridge_url}/json?poll=1", timeout=10)
        
        if resp.status_code == 200 and resp.text.strip():
            # On nettoie la réponse car ntfy peut envoyer plusieurs lignes JSON
            last_line = resp.text.strip().split('\n')[-1]
            data = json.loads(last_line)
            
            if "message" in data:
                st.session_state.code_detecte = data["message"]
                st.success(f"✅ Code {st.session_state.code_detecte} récupéré !")
            else:
                st.warning("⚠️ Le serveur n'a pas encore reçu de message.")
        else:
            st.info("ℹ️ Aucun scan en attente sur le serveur.")
            
    except Exception as e:
        st.error(f"Erreur de récupération : {e}")

# --- 3. ANALYSE FINALE ---
st.divider()
final_code = st.text_input("Code prêt pour analyse :", value=st.session_state.code_detecte)

if st.button("🔍 LANCER L'ANALYSE NUTRI"):
    # Ton code BigQuery ici...
    st.write(f"Recherche de {final_code} dans la base V7...")

if st.button("🔄 RESET"):
    st.session_state.code_detecte = ""
    st.rerun()