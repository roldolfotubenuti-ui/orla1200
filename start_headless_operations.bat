@echo off
title TKS Engine 3.0 - Headless Operations Daemon
cd /d "%~dp0"
echo ===================================================
echo TKS ENGINE 3.0 - CENTRAL DE OPERACOES EM SEGUNDO PLANO
echo Porta API: http://127.0.0.1:5050
echo Monitorando: E:\ORLA1200\1..6
echo ===================================================
python run_engine_headless.py
pause
