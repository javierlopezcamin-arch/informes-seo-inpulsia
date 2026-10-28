#!/bin/bash
/opt/homebrew/bin/python3 -m streamlit run "/Users/javicamin/Desktop/Claude proyectos local/INFORMES SEO INPULSIA/seo-monthly-reports-skill/app.py" --server.headless true --server.port 8501 --browser.gatherUsageStats false &
sleep 3
open http://localhost:8501
wait
