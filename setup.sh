#!/bin/bash

echo "============================================"
echo "Portfolio Optimization - Setup Script"
echo "============================================"

# Función para logging con colores
log() {
    echo -e "\033[32m[$(date '+%H:%M:%S')]\033[0m $1"
}

error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

# Verificar Python
log "🔍 Verificando Python..."
if ! command -v python3 &> /dev/null; then
    error "❌ Python3 no encontrado. Instale Python 3.9 o superior"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log "✅ Python $PYTHON_VERSION encontrado"

# Crear entorno virtual
log "📦 Creando entorno virtual..."
python3 -m venv portfolio_env

# Activar entorno virtual
log "⚡ Activando entorno virtual..."
source portfolio_env/bin/activate

# Actualizar pip
log "🔄 Actualizando pip..."
python -m pip install --upgrade pip

# Instalar dependencias principales
log "📚 Instalando dependencias principales..."
pip install -r requirements.txt

# Instalar dependencias del cliente
log "📱 Instalando dependencias del cliente..."
pip install -r requirements-client.txt

# Verificar instalación de Ray
log "🧪 Verificando instalación de Ray..."
python -c "import ray; print('✅ Ray instalado correctamente:', ray.__version__)"

# Crear archivo de activación rápida
cat > activate_env.sh << 'EOF'
#!/bin/bash
source portfolio_env/bin/activate
echo "✅ Entorno activado"
echo "🚀 Comandos disponibles:"
echo "  - python main.py                    # Ejecutar análisis completo"
echo "  - python src/api.py                 # Ejecutar API"
echo "  - streamlit run client/web_client.py # Cliente web"
echo "  - python client/cli_client.py --help # Cliente CLI"
EOF

chmod +x activate_env.sh

echo ""
echo "============================================"
echo "✅ ¡Setup completado exitosamente!"
echo "============================================"
echo ""
echo "🚀 Para activar el entorno:"
echo "   source activate_env.sh"
echo ""
echo "🎯 Para ejecutar el análisis:"
echo "   python main.py"
echo ""
echo "🌐 Para ejecutar la API:"
echo "   python src/api.py"
echo ""
echo "💻 Para el cliente web:"
echo "   streamlit run client/web_client.py"
echo ""
echo "📋 Para el cliente CLI:"
echo "   python client/cli_client.py --help"
echo ""
