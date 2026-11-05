@echo off
rem ===================================================================
rem  Diagnostico - mostra o que os atalhos estao enxergando.
rem  Duplo clique e mande o resultado da janela.
rem ===================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001
cls
set "ERRFILE=%TEMP%\japones-diag.err"
echo ===== DIAGNOSTICO - Japones incremental =====
echo.
echo [pasta]
echo   script : %~dp0
echo   atual  : %CD%
echo.
echo [teste de redirecionamento para NUL]
echo teste>nul
if errorlevel 1 (echo   FALHOU - e por isso que o >nul foi removido dos atalhos) else (echo   ok)
echo.
echo [lancador py.exe]
if exist "%SystemRoot%\py.exe" (
    echo   existe: %SystemRoot%\py.exe
    echo   versoes que ele conhece:
    "%SystemRoot%\py.exe" -0
) else (echo   nao existe)
echo.
echo [todos os pythons encontrados]
for %%I in (python.exe) do call :ver "%%~$PATH:I" "PATH"
for %%I in (python3.exe) do call :ver "%%~$PATH:I" "PATH"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :ver "%%D\python.exe" "usuario"
for /d %%D in ("%ProgramFiles%\Python3*") do call :ver "%%D\python.exe" "Program Files"
for /d %%D in ("%ProgramFiles(x86)%\Python3*") do call :ver "%%D\python.exe" "Program Files x86"
for /d %%D in ("C:\Python3*") do call :ver "%%D\python.exe" "raiz C:"
call :ver "%USERPROFILE%\anaconda3\python.exe" "anaconda"
call :ver "%USERPROFILE%\miniconda3\python.exe" "miniconda"
call :reg HKCU
call :reg HKLM
echo.
echo [arquivos do app]
if exist "app.py" (echo   app.py ok) else (echo   app.py AUSENTE)
if exist ".venv\Scripts\python.exe" (echo   .venv ok) else (echo   .venv ainda nao criado)
if exist "chave-api.txt" (echo   chave-api.txt existe) else (echo   chave-api.txt nao existe)
if exist "data\progresso.db" (echo   progresso.db existe) else (echo   progresso.db ainda nao existe)
echo.
echo ===== fim - mande esta janela inteira =====
echo.
pause
goto :eof

:ver
if "%~1"=="" goto :eof
if not exist "%~1" goto :eof
echo   [%~2] %~1
"%~1" --version
goto :eof

:reg
for /f "tokens=*" %%K in ('reg query "%1\Software\Python\PythonCore" 2^>"%ERRFILE%"') do call :reg_ver "%%K"
goto :eof

:reg_ver
for /f "tokens=2,*" %%A in ('reg query "%~1\InstallPath" /ve 2^>"%ERRFILE%"') do call :ver "%%B\python.exe" "registro"
goto :eof
