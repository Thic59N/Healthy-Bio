import streamlit as st
from google.cloud import bigquery
import os

# Connexion sécurisée
path_to_key = "bases-sql-485411-c96fe54fc8c7.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path_to_key

client = bigquery.Client()

# Configuration de la page
st.set_page_config(page_title="Healthy Bio - Recherche", layout="wide")

# Connexion à BigQuery (Streamlit utilise les secrets ou l'auth locale)
client = bigquery.Client()

st.title("🍎 Assistant Healthy Bio")
st.subheader("Trouvez des alternatives dans la même catégorie")

# Barre de saisie
code_saisi = st.text_input("Entrez le code barre du produit :", placeholder="Ex: 3017620422003")

if code_saisi:
    # 1. On prépare la première requête pour trouver LA catégorie
    query_cat = f"""
        SELECT Main_Category_Fr 
        FROM `bases-sql-485411.Healthy_Bio.Gold_Cat_fr` 
        WHERE CAST(code AS STRING) = '{code_saisi}'
        LIMIT 1
    """
    
    # 2. On exécute la recherche de catégorie
    res_cat = client.query(query_cat).to_dataframe()

    if not res_cat.empty:
        # On récupère le nom de la catégorie dans le résultat
        categorie_trouvee = res_cat['Main_Category_Fr'].iloc[0]
        st.success(f"Produit identifié ! Catégorie : **{categorie_trouvee}**")

        # 3. Requête simplifiée pour ne prendre que ce dont on a besoin
        query_alternatives = f"""
            SELECT 
                CAST(code AS STRING) as code, 
                image_small_url, 
                product_name
            FROM `bases-sql-485411.Healthy_Bio.Gold_Cat_fr` 
            WHERE Main_Category_Fr = "{categorie_trouvee}"
            AND CAST(code AS STRING) != '{code_saisi}'
            ORDER BY nutriscore_grade ASC
            LIMIT 10
        """
        
        # 4. Exécution et Affichage avec configuration des colonnes
        alternatives = client.query(query_alternatives).to_dataframe()
        
        st.write(f"### Produits similaires en {categorie_trouvee} :")
        
        # Configuration magique pour afficher l'image au lieu du texte
        st.dataframe(
            alternatives,
            column_config={
                "image_small_url": st.column_config.ImageColumn(
                    "Aperçu", help="Image du produit"
                ),
                "code": "Code Barre",
                "product_name": "Nom du Produit"
            },
            hide_index=True, # Pour enlever la colonne des numéros à gauche
            use_container_width=True
        )

    if not res_cat.empty:
        categorie_trouvee = res_cat['Main_Category_Fr'].iloc[0]
        st.success(f"Produit identifié ! Catégorie : **{categorie_trouvee}**")

        # 2. Requête pour trouver les produits de la même catégorie
        # On limite à 10 pour l'exemple
        query_alternatives = f"""
            SELECT code, product_name, nutriscore_grade, ecoscore_grade
            FROM `bases-sql-485411.Healthy_Bio.Gold_Cat_fr` 
            WHERE Main_Category_Fr = '{categorie_trouvee}'
            AND code != '{code_saisi}'
            ORDER BY nutriscore_grade ASC
            LIMIT 10
        """
        
        alternatives = client.query(query_alternatives).to_dataframe()

        st.write(f"### Produits similaires en {categorie_trouvee} :")
        st.dataframe(alternatives, use_container_width=True)
        
    else:
        st.error("Désolé, ce code produit est inconnu dans notre base.")


# 3560071051181