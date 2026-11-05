@echo off
rem ===================================================================
rem  Japones incremental - atalho de inicio para Windows
rem  Duplo clique. Na primeira vez prepara o ambiente (~1 min).
rem
rem  Este script evita de proposito "where" e redirecionamento para NUL:
rem  em alguns ambientes o ">nul" falha com "O sistema nao pode encontrar
rem  o caminho especificado" e o comando nem chega a rodar.
rem ===================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001
cls
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo   Japones incremental - uma palavra nova por frase
echo   -----------------------------------------------
echo.

rem --- 1. procura o Python --------------------------------------------
set "PY_EXE="
set "PY_ARGS="

rem 1a. o lancador oficial py.exe, instalado junto com o Python
if exist "%SystemRoot%\py.exe" (
    set "PY_EXE=%SystemRoot%\py.exe"
    set "PY_ARGS=-3"
)

rem 1b. procura no PATH sem comando externo ^(%%~$PATH: faz a busca^)
if not defined PY_EXE for %%I in (python.exe) do if not defined PY_EXE set "PY_EXE=%%~$PATH:I"
if not defined PY_EXE for %%I in (python3.exe) do if not defined PY_EXE set "PY_EXE=%%~$PATH:I"

rem 1c. pastas de instalacao mais comuns
if not defined PY_EXE for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY_EXE=%%D\python.exe"
if not defined PY_EXE for /d %%D in ("%ProgramFiles%\Python3*") do if exist "%%D\python.exe" set "PY_EXE=%%D\python.exe"
if not defined PY_EXE for /d %%D in ("%ProgramFiles(x86)%\Python3*") do if exist "%%D\python.exe" set "PY_EXE=%%D\python.exe"

if not defined PY_EXE goto sem_python

rem o atalho da Microsoft Store nao e o Python de verdade
set "SEM_LOJA=!PY_EXE:WindowsApps=!"
if not "!SEM_LOJA!"=="!PY_EXE!" set "DA_LOJA=1"

"!PY_EXE!" !PY_ARGS! -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_ruim

rem --- 2. ambiente proprio, criado uma unica vez ------------------------
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "!VENV_PY!" (
    echo   Preparando o ambiente pela primeira vez. Leva cerca de um minuto...
    "!PY_EXE!" !PY_ARGS! -m venv ".venv"
    if errorlevel 1 goto erro_venv
    echo   Instalando a biblioteca da Claude...
    "!VENV_PY!" -m pip install --quiet --upgrade pip
    "!VENV_PY!" -m pip install --quiet anthropic
    if errorlevel 1 (
        echo   [aviso] Nao consegui instalar o pacote anthropic.
        echo           O app funciona assim mesmo, com o gerador local de frases.
    )
    echo.
)

rem --- 3. chave da API, perguntada uma unica vez ------------------------
if exist "chave-api.txt" goto rodar
if not "%ANTHROPIC_API_KEY%"=="" goto rodar
echo   Para a Claude escrever as frases, cole abaixo a sua chave da API.
echo   ^(Enter em branco usa o gerador local; da para configurar depois
echo    criando o arquivo chave-api.txt nesta pasta.^)
echo.
set "CHAVE="
set /p "CHAVE=  chave: "
if not "!CHAVE!"=="" (
    >chave-api.txt echo !CHAVE!
    echo   Chave salva em chave-api.txt ^(nao vai para o repositorio^).
)
echo.

:rodar
"!VENV_PY!" app.py %*
if errorlevel 1 (
    echo.
    echo   O aplicativo terminou com erro. A mensagem acima explica o motivo.
    pause
)
goto fim

:sem_python
echo   Nao encontrei o Python neste computador.
echo.
echo   Procurei em:
echo     %SystemRoot%\py.exe
echo     no PATH ^(python.exe e python3.exe^)
echo     %LOCALAPPDATA%\Programs\Python\Python3*
echo     %ProgramFiles%\Python3*
echo.
echo   Baixe em https://www.python.org/downloads/ e, na tela de instalacao,
echo   marque "Add python.exe to PATH" antes de clicar em Install.
echo   Depois feche esta janela e de outro duplo clique aqui.
echo.
echo   Se voce TEM Python instalado, rode o diagnostico.bat desta pasta e
echo   mande o resultado - ele mostra o que o script esta enxergando.
echo.
pause
goto fim

:python_ruim
if defined DA_LOJA (
    echo   O que encontrei foi o atalho da Microsoft Store, nao o Python.
    echo   Instale o Python de verdade em https://www.python.org/downloads/
    echo   e marque "Add python.exe to PATH" na instalacao.
) else (
    echo   O Python encontrado e antigo demais ^(precisa ser 3.11 ou mais novo^):
    echo     !PY_EXE!
    echo   Baixe a versao atual em https://www.python.org/downloads/
)
echo.
pause
goto fim

:erro_venv
echo   Nao consegui criar o ambiente virtual ^(.venv^).
echo   Tente rodar nesta pasta:  "!PY_EXE!" !PY_ARGS! -m venv .venv
echo.
pause

:fim
endlocal
