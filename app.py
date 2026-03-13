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
            st.success(f"✅ Produit : **{nom_produit}** | Famille : **{famille_trouvee}**")

            # REQUÊTE 2 : Alternatives
            query_alternatives = f"""
                SELECT Url as image_url, Product_name, Marque, nutriscore_grade, Secret_Score, Nb_Additifs
                FROM `{TABLE_ID}` 
                WHERE Famille = "{famille_trouvee}" AND Code_barre != {code_saisi}
                ORDER BY Secret_Score DESC, nutriscore_grade ASC LIMIT 10
            """
            alternatives = client.query(query_alternatives).to_dataframe()
            
            st.write(f"### 🥗 Meilleures alternatives en '{famille_trouvee}' :")
            st.dataframe(
                alternatives,
                column_config={
                    "image_url": st.column_config.ImageColumn("Visuel"),
                    "Product_name": "Produit", "Marque": "Marque",
                    "nutriscore_grade": "Nutriscore", "Secret_Score": "Score", "Nb_Additifs": "Additifs"
                },
                hide_index=True, use_container_width=True
            )
        else:
            st.error(f"❌ Le code {code_saisi} est introuvable.")
    except Exception as e:
        st.error(f"Erreur : {e}") # Une seule parenthèse ici !

# Tes commentaires/pense-bête en dessous sont parfaits
# 3560071051181
# 8852018101147