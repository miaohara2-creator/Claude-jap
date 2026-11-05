@echo off
rem ===================================================================
rem  Japones incremental - atalho de inicio para Windows
rem  De um duplo clique neste arquivo. Na primeira vez ele prepara o
rem  ambiente (demora ~1 min); depois disso abre em poucos segundos.
rem ===================================================================
setlocal enabledelayedexpansion
chcp 65001 >/dev/null 2>&1
title Japones incremental
cd /d "%~dp0"

rem Python precisa falar UTF-8: a tela mostra japones o tempo todo.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo   Japones incremental - uma palavra nova por frase
echo   ------------------------------------------
echo.

rem --- 1. procura o Python -------------------------------------------
set "PY="
where py >/dev/null 2>&1 && set "PY=py -3"
if not defined PY (where python >/dev/null 2>&1 && set "PY=python")
if not defined PY goto sem_python

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1
if errorlevel 1 goto python_antigo

rem --- 2. ambiente proprio, criado uma unica vez ----------------------
set "VENV_PY=.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo   Preparando o ambiente pela primeira vez. Isso leva cerca de um minuto...
    %PY% -m venv .venv
    if errorlevel 1 goto erro_venv
    "%VENV_PY%" -m pip install --quiet --upgrade pip
    echo   Instalando a biblioteca da Claude...
    "%VENV_PY%" -m pip install --quiet anthropic
    if errorlevel 1 echo   [aviso] Nao consegui instalar o pacote anthropic: o app vai
    if errorlevel 1 echo           funcionar com o gerador local de frases.
    echo.
)

rem --- 3. chave da API, perguntada uma unica vez ----------------------
if not exist "chave-api.txt" if "%ANTHROPIC_API_KEY%"=="" (
    echo   Para a Claude escrever as frases, cole abaixo sua chave da API.
    echo   ^(Enter em branco usa o gerador local; da para configurar depois
    echo    criando o arquivo chave-api.txt nesta pasta.^)
    echo.
    set "CHAVE="
    set /p "CHAVE=  chave: "
    if not "!CHAVE!"=="" (
        >chave-api.txt echo !CHAVE!
        echo   Chave salva em chave-api.txt ^(esse arquivo nao vai para o Git^).
    )
    echo.
)

rem --- 4. sobe o app e abre o navegador -------------------------------
"%VENV_PY%" app.py %*
if errorlevel 1 (
    echo.
    echo   O aplicativo terminou com erro. A mensagem acima explica o motivo.
    pause
)
goto fim

:sem_python
echo   Nao encontrei o Python neste computador.
echo.
echo   Baixe em https://www.python.org/downloads/ e, na tela de instalacao,
echo   marque a caixa "Add python.exe to PATH" antes de clicar em Install.
echo   Depois feche esta janela e de outro duplo clique aqui.
echo.
pause
goto fim

:python_antigo
echo   O Python encontrado e antigo demais. Este app precisa da versao 3.11
echo   ou mais nova. Baixe a atual em https://www.python.org/downloads/
echo.
pause
goto fim

:erro_venv
echo   Nao consegui criar o ambiente virtual (.venv).
echo   Tente rodar nesta pasta:  py -3 -m venv .venv
echo.
pause

:fim
endlocal
