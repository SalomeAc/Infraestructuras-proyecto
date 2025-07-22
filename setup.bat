@echo off
echo ============================================
echo Portfolio Optimization - Setup de Windows
echo ============================================

echo 🔧 Configurando entorno de desarrollo...

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado. Por favor instale Python 3.9 o superior.
    echo 📥 Descargue desde: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python encontrado

REM Crear entorno virtual
echo 📦 Creando entorno virtual...
python -m venv portfolio_env

REM Activar entorno virtual
echo ⚡ Activando entorno virtual...
call portfolio_env\Scripts\activate.bat

REM Actualizar pip
echo 🔄 Actualizando pip...
python -m pip install --upgrade pip

REM Instalar dependencias principales
echo 📚 Instalando dependencias principales...
pip install -r requirements.txt

REM Instalar dependencias del cliente (opcional)
echo 📱 Instalando dependencias del cliente web...
pip install -r requirements-client.txt

REM Verificar instalación de Ray
echo 🧪 Verificando instalación de Ray...
python -c "import ray; print('✅ Ray instalado correctamente:', ray.__version__)"

echo.
echo ============================================
echo ✅ ¡Setup completado exitosamente!
echo ============================================
echo.
echo 🚀 Para ejecutar el análisis:
echo    1. portfolio_env\Scripts\activate.bat
echo    2. python main.py
echo.
echo 🌐 Para ejecutar la API:
echo    1. portfolio_env\Scripts\activate.bat  
echo    2. python src\api.py
echo.
echo 💻 Para ejecutar el cliente web:
echo    1. portfolio_env\Scripts\activate.bat
echo    2. streamlit run client\web_client.py
echo.
echo 📋 Para el cliente CLI:
echo    1. portfolio_env\Scripts\activate.bat
echo    2. python client\cli_client.py --help
echo.
pause
