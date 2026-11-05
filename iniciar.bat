@echo off
rem ===================================================================
rem  Japones incremental - atalho de inicio para Windows
rem  Duplo clique. Na primeira vez prepara o ambiente (~1 min).
rem
rem  Evita de proposito "where" e redirecionamento para NUL: em alguns
rem  ambientes o ">nul" falha com "O sistema nao pode encontrar o caminho
rem  especificado" e o comando nem chega a rodar. A saida indesejada vai
rem  para um arquivo no TEMP.
rem ===================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001
cls
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "ERRFILE=%TEMP%\japones-python.err"
set "LISTA=%TEMP%\japones-pythons.txt"
set "VAZIO=%TEMP%\japones-vazio.txt"
if exist "%LISTA%" del /q "%LISTA%"
>"%VAZIO%" echo.

echo.
echo   Japones incremental - uma palavra nova por frase
echo   -----------------------------------------------
echo.

rem --- 1. procura um Python 3.9 ou mais novo ---------------------------
set "PY_EXE="
set "PY_ARGS="

rem 1a. lancador py.exe, da versao mais nova para a mais antiga
if exist "%SystemRoot%\py.exe" for %%V in (3.18 3.17 3.16 3.15 3.14 3.13 3.12 3.11 3.10 3.9) do call :testar_py %%V

rem 1b. PATH (a busca %%~$PATH: e interna do cmd, sem comando externo)
for %%I in (python.exe) do call :testar "%%~$PATH:I"
for %%I in (python3.exe) do call :testar "%%~$PATH:I"

rem 1c. pastas de instalacao mais comuns
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :testar "%%D\python.exe"
for /d %%D in ("%ProgramFiles%\Python3*") do call :testar "%%D\python.exe"
for /d %%D in ("%ProgramFiles(x86)%\Python3*") do call :testar "%%D\python.exe"
for /d %%D in ("C:\Python3*") do call :testar "%%D\python.exe"

rem 1d. Anaconda / Miniconda
call :testar "%USERPROFILE%\anaconda3\python.exe"
call :testar "%USERPROFILE%\miniconda3\python.exe"
call :testar "%ProgramData%\anaconda3\python.exe"
call :testar "%ProgramData%\miniconda3\python.exe"

rem 1e. registro do Windows (instalacoes registradas)
call :do_registro HKCU
call :do_registro HKLM

if not defined PY_EXE goto sem_python
echo   Python: !PY_EXE! !PY_ARGS!
"!PY_EXE!" !PY_ARGS! -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" <"%VAZIO%" 2>"%ERRFILE%"
if errorlevel 1 (
    echo   [nota] O app roda neste Python, mas o pacote da Claude exige 3.10
    echo          ou mais novo: as frases virao do gerador local. Instalar um
    echo          Python atual em https://www.python.org/downloads/ resolve.
)

rem --- 2. credencial da Claude, perguntada uma unica vez ----------------
rem Vem antes da parte lenta: o bloco do .venv consome a entrada padrao,
rem alem de ser melhor decidir tudo de uma vez.
rem Tres caminhos: conta Claude (perfil OAuth em %APPDATA%\Anthropic),
rem chave de API em arquivo, ou nenhum (gerador local).
rem saida para uso nao-interativo (automacao): nao pergunta nada
if not "%NIHONGO_SEM_PERGUNTAS%"=="" goto preparar_ambiente
if exist "%APPDATA%\Anthropic\credentials\*.json" goto preparar_ambiente
if exist "chave-api.txt" goto preparar_ambiente
if not "%ANTHROPIC_API_KEY%"=="" goto preparar_ambiente
echo   Como a Claude vai escrever as frases?
echo.
echo     [1] Entrar com a minha conta Claude  ^(recomendado^)
echo     [2] Colar uma chave de API
echo     [3] Agora nao - usar o gerador local de frases
echo.
set "OPCAO="
set /p "OPCAO=  escolha [1]: "
if "!OPCAO!"=="" set "OPCAO=1"
if "!OPCAO!"=="1" call :entrar_na_conta
if "!OPCAO!"=="2" call :pedir_chave
echo.

:preparar_ambiente
rem --- 3. ambiente proprio, criado uma unica vez ------------------------
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

:rodar
"!VENV_PY!" app.py %*
if errorlevel 1 (
    echo.
    echo   O aplicativo terminou com erro. A mensagem acima explica o motivo.
    pause
)
goto fim

rem --- subrotinas -------------------------------------------------------

:testar_py
if defined PY_EXE goto :eof
"%SystemRoot%\py.exe" -%1 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" <"%VAZIO%" 2>"%ERRFILE%"
if errorlevel 1 goto :eof
set "PY_EXE=%SystemRoot%\py.exe"
set "PY_ARGS=-%1"
goto :eof

:testar
if defined PY_EXE goto :eof
if "%~1"=="" goto :eof
if not exist "%~1" goto :eof
>>"%LISTA%" echo %~1
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" <"%VAZIO%" 2>"%ERRFILE%"
if errorlevel 1 goto :eof
set "PY_EXE=%~1"
set "PY_ARGS="
goto :eof

:do_registro
for /f "tokens=*" %%K in ('reg query "%1\Software\Python\PythonCore" 2^>"%ERRFILE%" ^<"%VAZIO%"') do call :do_registro_versao "%%K"
goto :eof

:do_registro_versao
for /f "tokens=2,*" %%A in ('reg query "%~1\InstallPath" /ve 2^>"%ERRFILE%" ^<"%VAZIO%"') do call :testar "%%B\python.exe"
goto :eof

:pedir_chave
echo.
echo   Cole a sua chave da API ^(Enter em branco cancela^):
set "CHAVE="
set /p "CHAVE=  chave: "
if "!CHAVE!"=="" goto :eof
>chave-api.txt echo !CHAVE!
echo   Chave salva em chave-api.txt ^(nao vai para o repositorio^).
goto :eof

:entrar_na_conta
rem O login usa o utilitario oficial `ant`, da Anthropic. Ele grava um
rem perfil em %APPDATA%\Anthropic que o pacote anthropic encontra sozinho.
set "ANT="
rem Preferimos a nossa copia. Atencao: o Apache Ant (ferramenta de build
rem Java) tambem se chama ant.exe, entao um ant do PATH so vale se
rem responder ao subcomando `auth`, que so o utilitario da Anthropic tem.
if exist "%~dp0.ferramentas\ant.exe" set "ANT=%~dp0.ferramentas\ant.exe"
if not defined ANT for %%I in (ant.exe) do call :validar_ant "%%~$PATH:I"
if defined ANT goto fazer_login
echo.
echo   Para entrar com a sua conta eu preciso do utilitario `ant`, da
echo   Anthropic. Posso baixa-lo agora para a pasta .ferramentas daqui.
echo   Origem: https://github.com/anthropics/anthropic-cli/releases
set "BAIXAR="
set /p "BAIXAR=  baixar agora? [S/n]: "
if /i "!BAIXAR!"=="n" goto :eof
echo   Baixando...
powershell -NoProfile -Command "try { $r = Invoke-RestMethod 'https://api.github.com/repos/anthropics/anthropic-cli/releases/latest'; $v = $r.tag_name.TrimStart('v'); $arq = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {'arm64'} else {'amd64'}; $nome = 'ant_' + $v + '_windows_' + $arq + '.zip'; $url = ($r.assets | Where-Object { $_.name -eq $nome }).browser_download_url; if (-not $url) { exit 2 }; $zip = Join-Path $env:TEMP 'ant-cli.zip'; Invoke-WebRequest -UseBasicParsing $url -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath '.ferramentas' -Force; Remove-Item $zip -ErrorAction SilentlyContinue } catch { Write-Error $_; exit 1 }" 2>"%TEMP%\japones-ant-erro.txt"
if errorlevel 1 (
    echo   Nao consegui baixar o utilitario. Motivo:
    type "%TEMP%\japones-ant-erro.txt"
    echo   Voce pode:
    echo     - baixar a mao em https://github.com/anthropics/anthropic-cli/releases
    echo       ^(ant_^<versao^>_windows_amd64.zip^), extrair o ant.exe na pasta
    echo       .ferramentas daqui, e rodar este atalho de novo; ou
    echo     - usar uma chave de API, rodando este atalho e escolhendo [2].
    goto :eof
)
if not exist "%~dp0.ferramentas\ant.exe" (
    echo   O download terminou mas nao achei o ant.exe em .ferramentas.
    goto :eof
)
set "ANT=%~dp0.ferramentas\ant.exe"
goto fazer_login

:validar_ant
if "%~1"=="" goto :eof
if not exist "%~1" goto :eof
"%~1" auth status <"%VAZIO%" >"%TEMP%\japones-ant.txt" 2>&1
findstr /i /c:"Buildfile" "%TEMP%\japones-ant.txt" >"%TEMP%\japones-ant.chk" 2>&1
if not errorlevel 1 (
    echo   ^(ignorando o Apache Ant em %~1 - nao e o utilitario da Anthropic^)
    goto :eof
)
set "ANT=%~1"
goto :eof

:fazer_login
echo.
echo   Vai abrir o navegador para voce entrar na sua conta Claude.
echo   Terminando por la, volte para esta janela.
echo.
"!ANT!" auth login
if exist "%APPDATA%\Anthropic\credentials\*.json" (
    echo.
    echo   Conta conectada. Nao precisa de chave de API.
) else (
    echo.
    echo   O login nao foi concluido. O app vai usar o gerador local por
    echo   enquanto; rode este atalho de novo para tentar outra vez.
)
goto :eof

:mostrar_versao
echo     - %~1
"%~1" --version
goto :eof

rem --- mensagens de erro -------------------------------------------------

:sem_python
echo   Nao encontrei um Python 3.9 ou mais novo neste computador.
echo.
if exist "%LISTA%" (
    echo   Pythons que eu encontrei, e a versao de cada um:
    for /f "usebackq delims=" %%P in ("%LISTA%") do call :mostrar_versao "%%P"
    echo.
)
if exist "%SystemRoot%\py.exe" (
    echo   Versoes que o lancador py.exe conhece:
    "%SystemRoot%\py.exe" -0
    echo.
)
echo   Procurei tambem em:
echo     %LOCALAPPDATA%\Programs\Python\Python3*
echo     %ProgramFiles%\Python3*
echo     C:\Python3*  ^|  anaconda3  ^|  miniconda3
echo     registro do Windows ^(HKCU e HKLM, Software\Python\PythonCore^)
echo.
echo   Baixe o Python em https://www.python.org/downloads/ e, na tela de
echo   instalacao, marque "Add python.exe to PATH" antes de clicar em
echo   Install. Depois feche esta janela e de outro duplo clique aqui.
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
