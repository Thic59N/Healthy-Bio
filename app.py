import streamlit as st
from google.cloud import bigquery
import os

# 1. Connexion sécurisée - On force le chemin vers le dossier actuel
current_dir = os.path.dirname(os.path.abspath(__file__))
path_to_key = os.path.join(current_dir, "bases-sql-485411-c96fe54fc8c7.json")

if os.path.exists(path_to_key):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path_to_key
    client = bigquery.Client()
else:
    st.error(f"Clé JSON introuvable à l'adresse : {path_to_key}")
    st.stop() # Arrête l'exécution si la clé n'est pas là

# 2. Configuration de la page
st.set_page_config(page_title="Healthy Bio v2 - Secret Sauce", layout="wide", page_icon="🥗")

st.title("🍎 Assistant Healthy Bio - V2")
st.subheader("Analyse des alternatives par Famille")

# 3. Barre de saisie
code_saisi = st.text_input("Entrez le code barre du produit :", placeholder="Ex: 8852018101147")

# Ta nouvelle table native BigQuery (plus simple !)
TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit"

if code_saisi:
    # REQUÊTE 1 : Infos du produit saisi
    query_prod = f"SELECT Product_name, Famille FROM `{TABLE_ID}` WHERE Code_barre = {code_saisi} LIMIT 1"
    
    try:
        res_prod = client.query(query_prod).to_dataframe()

        if not res_prod.empty:
            nom_produit = res_prod['Product_name'].iloc[0]
            famille_trouvee = res_prod['Famille'].iloc[0]
            
            # --- AFFICHAGE DU PRODUIT PRINCIPAL ---
            col1, col2 = st.columns([1, 3])
            with col1:
                query_img = f"SELECT Url_image_small, Url FROM `{TABLE_ID}` WHERE Code_barre = {code_saisi} LIMIT 1"
                res_img = client.query(query_img).to_dataframe()
                
                if not res_img.empty and res_img['Url_image_small'].iloc[0]:
                    # On rend l'image principale cliquable vers le site
                    st.markdown(f'''
                        <a href="{res_img['Url'].iloc[0]}" target="_blank">
                            <img src="{res_img['Url_image_small'].iloc[0]}" width="180" style="border-radius: 10px;">
                        </a>
                    ''', unsafe_allow_html=True)
                else:
                    st.warning("📸 Image non disponible")
            
            with col2:
                st.success(f"✅ Produit : **{nom_produit}**")
                st.info(f"Famille : **{famille_trouvee}**")

            # --- TABLEAU DES ALTERNATIVES ---
            query_alternatives = f"""
                SELECT Url_image_small, Product_name, Marque, nutriscore_grade, Secret_Score, Nb_Additifs, Url
                FROM `{TABLE_ID}` 
                WHERE Famille = "{famille_trouvee}" AND Code_barre != {code_saisi}
                ORDER BY Secret_Score DESC, nutriscore_grade ASC LIMIT 10
            """
            alternatives = client.query(query_alternatives).to_dataframe()
            
            st.write(f"### 🥗 Meilleures alternatives en '{famille_trouvee}' :")

            # --- LA SOLUTION POUR LE LIEN SUR LE NOM ---
            # On crée une nouvelle colonne "Produit" qui fusionne le nom et l'URL en format Markdown
            # Note : On utilise st.column_config.LinkColumn plus bas pour l'interpréter
            
            st.dataframe(
                alternatives,
                column_config={
                    "Url_image_small": st.column_config.ImageColumn("Visuel", width="medium"),
                    "Url": st.column_config.LinkColumn(
                        "Produit", 
                        display_text=r"([^/]+)$", # Cette astuce va afficher le nom du produit extrait de l'URL
                        help="Cliquez pour ouvrir la fiche"
                    ),
                    "Product_name": None, # On cache l'ancien nom car il est maintenant dans le lien
                    "Marque": "Marque",
                    "nutriscore_grade": "Nutriscore", 
                    "Secret_Score": "Score", 
                    "Nb_Additifs": "Additifs"
                },
                # On définit l'ordre des colonnes ici pour placer le Produit après le Visuel
                column_order=("Url_image_small", "Url", "Marque", "nutriscore_grade", "Secret_Score", "Nb_Additifs"),
                hide_index=True, 
                use_container_width=True
            )
        else:
            st.error(f"❌ Le code {code_saisi} est introuvable.")
    except Exception as e:
        st.error(f"Erreur : {e}") # Une seule parenthèse ici !

# Tes commentaires/pense-bête en dessous sont parfaits
# 3560071051181
# 8852018101147
