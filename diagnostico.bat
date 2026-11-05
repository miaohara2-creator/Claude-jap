@echo off
rem ===================================================================
rem  Diagnostico - mostra o que os atalhos estao enxergando.
rem  Duplo clique e mande o resultado da janela.
rem ===================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001
cls
echo ===== DIAGNOSTICO - Japones incremental =====
echo.
echo [pasta]
echo   script : %~dp0
echo   atual  : %CD%
echo.
echo [teste de redirecionamento para NUL]
echo teste>nul
if errorlevel 1 (echo   FALHOU - este e o problema) else (echo   ok)
echo.
echo [py.exe]
if exist "%SystemRoot%\py.exe" (echo   existe: %SystemRoot%\py.exe) else (echo   nao existe)
echo.
echo [python no PATH]
for %%I in (python.exe) do echo   python.exe : %%~$PATH:I
for %%I in (python3.exe) do echo   python3.exe: %%~$PATH:I
for %%I in (where.exe) do echo   where.exe  : %%~$PATH:I
echo.
echo [pastas de instalacao]
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do echo   %%D
for /d %%D in ("%ProgramFiles%\Python3*") do echo   %%D
echo.
echo [versoes]
if exist "%SystemRoot%\py.exe" "%SystemRoot%\py.exe" -3 --version
python --version
echo.
echo [arquivos do app]
if exist "app.py" (echo   app.py ok) else (echo   app.py AUSENTE)
if exist ".venv\Scripts\python.exe" (echo   .venv ok) else (echo   .venv ainda nao criado)
if exist "chave-api.txt" (echo   chave-api.txt existe) else (echo   chave-api.txt nao existe)
if exist "data\progresso.db" (echo   progresso.db existe) else (echo   progresso.db ainda nao existe)
echo.
echo ===== fim =====
echo.
pause
endlocal
