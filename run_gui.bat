@echo off
title TKS Engine 3.0 - Central de Operacoes & Escritorio 3D
cd /d "%~dp0"

echo ========================================================
echo   TKS ENGINE 3.0 - INICIANDO SISTEMA INTEGRADO
echo ========================================================
echo.

:: 1. Verificar se o Escritorio 3D (porta 3005) esta ativo
netstat -ano | findstr ":3005" >nul
if errorlevel 1 (
    echo [1/3] Iniciando TKS Virtual Office em segundo plano na porta 3005...
    start /min "TKS Virtual Office 3D" cmd /c "cd /d \"E:\youtube\APPS CURSOR\TKS-Virtual-Office\" && npx.cmd next start -p 3005 -H 0.0.0.0"
    timeout /t 3 /nobreak >nul
) else (
    echo [1/3] TKS Virtual Office 3D ja esta ativo na porta 3005.
)

:: 2. Abrir o Escritorio 3D automaticamente no navegador padrao
echo [2/3] Abrindo Escritorio 3D no navegador: http://localhost:3005/
start http://localhost:3005/

:: 3. Iniciar a interface grafica do TKS Engine 3.0
echo [3/3] Iniciando Central de Automacao de Pastas & Agendamento...
"C:\Python315\python.exe" main.py
if errorlevel 1 pause
