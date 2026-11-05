@echo off
rem ===================================================================
rem  Japones incremental - atualizar para a versao mais recente
rem  Duplo clique: baixa a versao atual, substitui os arquivos do
rem  aplicativo e abre o app. O progresso (data\progresso.db) e a
rem  chave (chave-api.txt) NAO sao tocados.
rem
rem  O script roda a partir de uma copia no TEMP: o cmd.exe le o .bat
rem  enquanto executa, entao substituir este arquivo durante a propria
rem  atualizacao corromperia o resto da execucao.
rem ===================================================================
setlocal
if /i "%~1"=="--interno" goto principal

set "ORIGEM=%~dp0"
if "%ORIGEM:~-1%"=="\" set "ORIGEM=%ORIGEM:~0,-1%"
set "COPIA=%TEMP%\japones-atualizador.bat"
copy /y "%~f0" "%COPIA%"
if errorlevel 1 goto erro_temp
cmd /c ""%COPIA%" --interno "%ORIGEM%""
exit /b

:principal
set "DESTINO=%~2"
cd /d "%DESTINO%"
chcp 65001
cls
title Atualizar - Japones incremental

rem Endereco do projeto (troque aqui se o repositorio ou o branch mudar).
set "BRANCH=ccr-32e85758-6zpgck"
set "URL=https://codeload.github.com/miaohara2-creator/Claude-jap/zip/refs/heads/%BRANCH%"
set "PASTA_NO_ZIP=Claude-jap-%BRANCH%"
set "TMPZIP=%TEMP%\japones-incremental.zip"
set "TMPDIR=%TEMP%\japones-incremental-novo"

echo.
echo   Atualizando o aplicativo
echo   ------------------------
echo   pasta: %DESTINO%
echo.

if not exist "%DESTINO%\app.py" goto pasta_errada

echo   1/3  Baixando a versao mais recente...
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri %URL% -OutFile %TMPZIP% } catch { exit 1 }"
if errorlevel 1 goto erro_download

echo   2/3  Abrindo o pacote...
if exist "%TMPDIR%" rd /s /q "%TMPDIR%"
powershell -NoProfile -Command "try { Expand-Archive -LiteralPath %TMPZIP% -DestinationPath %TMPDIR% -Force } catch { exit 1 }"
if errorlevel 1 goto erro_extrair
if not exist "%TMPDIR%\%PASTA_NO_ZIP%\app.py" goto erro_conteudo

echo   3/3  Substituindo os arquivos do aplicativo...
xcopy "%TMPDIR%\%PASTA_NO_ZIP%\*" "%DESTINO%\" /E /I /Y /Q
if errorlevel 1 goto erro_copia

del /q "%TMPZIP%"
rd /s /q "%TMPDIR%"

echo.
echo   Pronto. Progresso e chave da API foram mantidos.
echo.
call "%DESTINO%\iniciar.bat"
goto fim

:erro_temp
echo   Nao consegui preparar o atualizador na pasta temporaria.
echo.
pause
goto fim

:pasta_errada
echo   Nao achei o app.py em: %DESTINO%
echo   O atualizar.bat precisa ficar na mesma pasta do aplicativo.
echo.
pause
goto fim

:erro_download
echo.
echo   Nao consegui baixar a atualizacao. Verifique a conexao e tente de
echo   novo. O aplicativo instalado continua funcionando: use o iniciar.bat.
echo.
pause
goto fim

:erro_extrair
echo.
echo   O arquivo baixado veio corrompido. Tente de novo em alguns minutos.
echo.
pause
goto fim

:erro_conteudo
echo.
echo   O pacote baixado nao tem o formato esperado - talvez o endereco do
echo   projeto tenha mudado. O aplicativo instalado continua funcionando.
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
