@echo off
rem ===================================================================
rem  Conectar a sua conta Claude (em vez de usar uma chave de API).
rem  Duplo clique. Abre o navegador para o login e, se houver um
rem  chave-api.txt na pasta, oferece desativa-lo -- a chave tem
rem  precedencia sobre a conta e impediria o login de ter efeito.
rem ===================================================================
call "%~dp0iniciar.bat" --conectar-conta
