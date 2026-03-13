import streamlit as st
from google.cloud import bigquery
import json
import os

# 1. Connexion sécurisée
client = None

# On tente d'abord de lire les Secrets (Mode Cloud)
try:
    if "gcp_service_account" in st.secrets:
        credentials_info = json.loads(st.secrets["gcp_service_account"])
        client = bigquery.Client.from_service_account_info(credentials_info)
except Exception:
    # Si on est ici, c'est qu'on est en local ou que les secrets ne sont pas chargés
    client = None

# Si le client n'est toujours pas créé, on cherche le fichier JSON (Mode Local)
if client is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    path_to_key = os.path.join(current_dir, "bases-sql-485411-c96fe54fc8c7.json")
    
    if os.path.exists(path_to_key):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path_to_key
        client = bigquery.Client()
    else:
        st.error("Désolé, impossible de trouver une clé de connexion (Secret ou JSON).")
        st.stop()

# 2. Configuration de la page
st.set_page_config(page_title="Healthy Bio v2 - Secret Sauce", layout="wide", page_icon="🥗")

st.title("🍎 Assistant Healthy Bio - V2")
st.subheader("Analyse des alternatives par Famille")

# 3. Barre de saisie
code_saisi = st.text_input("Entrez le code barre du produit :", placeholder="Ex: 8852018101147")

# Ta table BigQuery
TABLE_ID = "bases-sql-485411.Healthy_Bio_v2.Secret_Sauce_Streamlit"

if code_saisi:
    try:
        # REQUÊTE : On récupère les infos du produit saisi
        query_prod = f"SELECT Product_name, Famille, Url, Url_image_small FROM `{TABLE_ID}` WHERE Code_barre = {code_saisi} LIMIT 1"
        res_prod = client.query(query_prod).to_dataframe()

        if not res_prod.empty:
            nom_produit = res_prod['Product_name'].iloc[0]
            famille_trouvee = res_prod['Famille'].iloc[0]
            url_fiche = res_prod['Url'].iloc[0]
            url_img = res_prod['Url_image_small'].iloc[0]

            # --- AFFICHAGE DU PRODUIT PRINCIPAL ---
            col1, col2 = st.columns([1, 4])
            with col1:
                if url_img:
                    # Image cliquable vers le site
                    st.markdown(f'''
                        <a href="{url_fiche}" target="_blank">
                            <img src="{url_img}" width="180" style="border-radius: 10px; border: 1px solid #ddd;">
                        </a>
                    ''', unsafe_allow_html=True)
                else:
                    st.warning("📸 Image non disponible")
            
            with col2:
                st.success(f"✅ Produit : **{nom_produit}**")
                st.info(f"Famille : **{famille_trouvee}**")
                st.write(f"[Voir la fiche complète sur Open Food Facts]({url_fiche})")

            st.divider()

            # --- RÉCUPÉRATION DE TOUTES LES ALTERNATIVES ---
            query_all = f"""
                SELECT Url_image_small, Product_name, Marque, nutriscore_grade, Secret_Score, Nb_Additifs, Url
                FROM `{TABLE_ID}` 
                WHERE Famille = "{famille_trouvee}" AND Code_barre != {code_saisi}
            """
            all_alternatives = client.query(query_all).to_dataframe()

            if not all_alternatives.empty:
                # Configuration commune des colonnes pour éviter la répétition
                config_table = {
                    "Url_image_small": st.column_config.ImageColumn("Visuel", width="medium"),
                    "Url": st.column_config.LinkColumn("Produit", display_text=r"([^/]+)$"),
                    "Product_name": None, # Masqué car inclus dans Url
                    "Marque": "Marque",
                    "nutriscore_grade": "Nutriscore",
                    "Secret_Score": "Score",
                    "Nb_Additifs": "Additifs"
                }
                ordre_colonnes = ("Url_image_small", "Url", "Marque", "nutriscore_grade", "Secret_Score", "Nb_Additifs")

                # --- TABLEAU 1 : LES 5 MEILLEURS ---
                st.write(f"### 🏆 Les 5 meilleures alternatives")
                top_5 = all_alternatives.sort_values(by=['Secret_Score', 'nutriscore_grade'], ascending=[False, True]).head(5)
                st.dataframe(top_5, column_config=config_table, column_order=ordre_colonnes, hide_index=True, use_container_width=True)

                st.write("") # Espace

                # --- TABLEAU 2 : LES 5 MOINS BONS ---
                st.write(f"### ⚠️ Les 5 moins bons de la catégorie")
                bottom_5 = all_alternatives.sort_values(by=['Secret_Score', 'nutriscore_grade'], ascending=[True, False]).head(5)
                st.dataframe(bottom_5, column_config=config_table, column_order=ordre_colonnes, hide_index=True, use_container_width=True)
            else:
                st.write("Aucune alternative trouvée dans cette famille.")

        else:
            st.error(f"❌ Le code {code_saisi} est introuvable dans la base.")

    except Exception as e:
        st.error(f"Erreur lors de la récupération des données : {e}")

# Mémos codes test : 
# 3560071051181
# 8852018101147