@echo off
setlocal
set ALLOW_LOCAL_DEV=1
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8501
