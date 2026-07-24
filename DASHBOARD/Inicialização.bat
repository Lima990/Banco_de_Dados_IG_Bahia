@echo off
cls
echo ===================================================
echo     INICIANDO DASHBOARD DO PROJETO DE MESTRADO
echo ===================================================
echo.

REM Muda para o diretorio do seu projeto.
REM As aspas sao importantes por causa dos espacos no caminho.
cd "C:\Users\User\OneDrive\Área de Trabalho\MESTRADO\Produto\DASHBOARD"

echo Diretorio atual: %cd%
echo.
echo Executando o Streamlit com o Python do sistema...
echo.

REM --- METODO 1: PYTHON NO PATH (Seu caso) ---
REM Este eh o comando que funcionou para voce. Ele assume que o Python
REM e o Streamlit estao instalados e acessiveis no sistema.
python -m streamlit run app_mapa_bahia.py


REM --- METODO 2: AMBIENTE VIRTUAL (Alternativa para o futuro) ---
REM Se voce criar um ambiente virtual chamado "venv" dentro da pasta
REM do projeto no futuro, comente a linha de cima (adicione REM no inicio)
REM e descomente a linha abaixo (remova o REM).
REM
REM call "venv\Scripts\python.exe" -m streamlit run app.py


:end
REM Mantem a janela do terminal aberta para vermos qualquer mensagem.
echo.
echo O dashboard deve ter aberto no seu navegador.
pause
