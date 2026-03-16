@echo off
title Lancement Assistant Healthy Bio
echo [1/2] Verification des dependances...
:: Cette ligne installe silencieusement ce qui pourrait manquer
python -m pip install -r requirements.txt --quiet

echo [2/2] Demarrage du serveur Streamlit...
:: On lance Streamlit. L'onglet s'ouvrira tout seul une seule fois.
streamlit run app.py

pause