@echo off
title TKS Engine 3.0 - Central de Operacoes
cd /d "%~dp0"

echo ========================================================
echo   TKS ENGINE 3.0 - CENTRAL DE OPERACOES
echo ========================================================
echo.

python main.py
if errorlevel 1 pause
