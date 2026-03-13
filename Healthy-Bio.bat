@echo off
title Lancement Assistant Healthy Bio
echo Lancement de l'application Streamlit...
start http://localhost:8501
streamlit run app.py
pause