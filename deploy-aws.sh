#!/bin/bash

# Script para desplegar la aplicación en AWS EC2
# Este script debe ejecutarse en una instancia EC2 con Docker instalado

set -e

echo "🚀 Iniciando despliegue de Portfolio Optimization en AWS EC2..."

# Variables de configuración
REPO_URL="https://github.com/SalomeAc/Infraestructuras-proyecto.git"
APP_DIR="/opt/portfolio-app"
SERVICE_NAME="portfolio-optimizer"

# Función para logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Verificar si Docker está instalado
if ! command -v docker &> /dev/null; then
    log "❌ Docker no está instalado. Instalando..."
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    log "✅ Docker instalado exitosamente"
fi

# Verificar si Docker Compose está instalado
if ! command -v docker-compose &> /dev/null; then
    log "❌ Docker Compose no está instalado. Instalando..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log "✅ Docker Compose instalado exitosamente"
fi

# Crear directorio de aplicación
if [ ! -d "$APP_DIR" ]; then
    log "📁 Creando directorio de aplicación..."
    sudo mkdir -p $APP_DIR
    sudo chown -R $USER:$USER $APP_DIR
fi

# Clonar o actualizar repositorio
if [ -d "$APP_DIR/.git" ]; then
    log "🔄 Actualizando repositorio existente..."
    cd $APP_DIR
    git pull origin main
else
    log "📥 Clonando repositorio..."
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
fi

# Configurar variables de entorno para producción
log "⚙️ Configurando variables de entorno..."
cat > .env << EOF
# Configuración de producción
RAY_DISABLE_IMPORT_WARNING=1
RAY_HEAD_NODE_HOST=ray-head
RAY_ADDRESS=ray://ray-head:10001

# Configuración de la API
API_HOST=0.0.0.0
API_PORT=8000

# Configuración del cliente
CLIENT_API_URL=http://localhost:8000

# Configuración de logging
LOG_LEVEL=INFO
EOF

# Detener servicios existentes si están corriendo
log "🛑 Deteniendo servicios existentes..."
docker-compose down --remove-orphans || true

# Limpiar imágenes antiguas
log "🧹 Limpiando imágenes Docker antiguas..."
docker system prune -f

# Construir y ejecutar servicios
log "🔨 Construyendo imágenes Docker..."
docker-compose build --no-cache

log "🚀 Iniciando servicios..."
docker-compose up -d

# Verificar que los servicios estén corriendo
log "✅ Verificando estado de los servicios..."
sleep 30

# Verificar API
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    log "✅ API está funcionando correctamente"
else
    log "❌ Error: API no responde"
    docker-compose logs api
    exit 1
fi

# Verificar cliente web
if curl -f http://localhost:8501 > /dev/null 2>&1; then
    log "✅ Cliente web está funcionando correctamente"
else
    log "⚠️ Advertencia: Cliente web no responde inmediatamente (puede estar iniciando)"
fi

# Configurar firewall (UFW)
log "🔒 Configurando firewall..."
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 8000/tcp    # API
sudo ufw allow 8501/tcp    # Streamlit
sudo ufw allow 8265/tcp    # Ray Dashboard
sudo ufw --force enable

# Crear servicio systemd para auto-inicio
log "⚙️ Configurando servicio systemd..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Portfolio Optimization Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

log "🎉 Despliegue completado exitosamente!"
log ""
log "📊 Información de acceso:"
log "   API:               http://$(curl -s http://checkip.amazonaws.com):8000"
log "   Cliente Web:       http://$(curl -s http://checkip.amazonaws.com):8501"
log "   Ray Dashboard:     http://$(curl -s http://checkip.amazonaws.com):8265"
log "   Nginx (Proxy):     http://$(curl -s http://checkip.amazonaws.com)"
log ""
log "📝 Comandos útiles:"
log "   Ver logs:          docker-compose logs -f"
log "   Reiniciar:         docker-compose restart"
log "   Parar servicios:   docker-compose down"
log "   Estado:            docker-compose ps"
log ""
log "🔧 El servicio se iniciará automáticamente en el próximo reinicio"
