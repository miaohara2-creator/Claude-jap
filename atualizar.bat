@echo off
rem ===================================================================
rem  Japones incremental - atualizar para a versao mais recente
rem  Duplo clique: baixa a versao atual do GitHub, substitui os
rem  arquivos do aplicativo e abre o app. Seu progresso
rem  (data\progresso.db) e sua chave (chave-api.txt) NAO sao tocados.
rem ===================================================================
setlocal
chcp 65001 >nul 2>&1
title Atualizar - Japones incremental
cd /d "%~dp0"

rem Endereco do projeto (troque aqui se o repositorio ou o branch mudar).
set "BRANCH=ccr-32e85758-6zpgck"
set "URL=https://codeload.github.com/miaohara2-creator/Claude-jap/zip/refs/heads/%BRANCH%"
set "PASTA_NO_ZIP=Claude-jap-%BRANCH%"

set "TMPZIP=%TEMP%\japones-incremental.zip"
set "TMPDIR=%TEMP%\japones-incremental-novo"

echo.
echo   Atualizando o aplicativo
echo   ------------------------
echo.

if not exist "app.py" goto pasta_errada

echo   1/3  Baixando a versao mais recente...
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri %URL% -OutFile %TMPZIP% } catch { exit 1 }"
if errorlevel 1 goto erro_download

echo   2/3  Abrindo o pacote...
if exist "%TMPDIR%" rd /s /q "%TMPDIR%"
powershell -NoProfile -Command "try { Expand-Archive -LiteralPath %TMPZIP% -DestinationPath %TMPDIR% -Force } catch { exit 1 }"
if errorlevel 1 goto erro_extrair
if not exist "%TMPDIR%\%PASTA_NO_ZIP%\app.py" goto erro_conteudo

echo   3/3  Substituindo os arquivos do aplicativo...
xcopy "%TMPDIR%\%PASTA_NO_ZIP%\*" "%CD%\" /E /I /Y /Q >nul
if errorlevel 1 goto erro_copia

del /q "%TMPZIP%" >nul 2>&1
rd /s /q "%TMPDIR%" >nul 2>&1

echo.
echo   Pronto. Progresso e chave da API foram mantidos.
echo.
echo   Abrindo o aplicativo...
timeout /t 2 >nul
call "%~dp0iniciar.bat"
goto fim

:pasta_errada
echo   Este arquivo precisa ficar na mesma pasta do app.py.
echo   Mova o atualizar.bat para a pasta do aplicativo e tente de novo.
echo.
pause
goto fim

:erro_download
echo.
echo   Nao consegui baixar a atualizacao.
echo   Verifique a conexao com a internet e tente de novo. Se o problema
echo   continuar, o aplicativo atual segue funcionando: use o iniciar.bat.
echo.
pause
goto fim

:erro_extrair
echo.
echo   O arquivo baixado veio corrompido ou nao pode ser aberto.
echo   Tente de novo em alguns minutos.
echo.
pause
goto fim

:erro_conteudo
echo.
echo   O pacote baixado nao tem o formato esperado - talvez o endereco do
echo   projeto tenha mudado. O aplicativo atual continua funcionando.
echo.
pause
goto fim

:erro_copia
echo.
echo   Nao consegui substituir os arquivos. Feche o aplicativo (a janela
echo   preta do iniciar.bat) e rode este atualizador de novo.
echo.
pause

:fim
endlocal
