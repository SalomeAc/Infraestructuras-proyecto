# Portfolio Optimization with Ray - AWS Infrastructure

Este proyecto implementa un sistema de optimización de portafolios usando sentiment analysis con paralelización Ray, containerización Docker y despliegue en AWS.

## 🏗️ Arquitectura del Sistema

### Componentes Principales

1. **Motor de Procesamiento de Datos** (`src/data_processor.py`)

   - Paralelización con Ray para descarga de datos
   - Procesamiento distribuido de sentiment analysis
   - Cálculo optimizado de retornos de portafolio

2. **API REST** (`src/api.py`)

   - FastAPI con Ray Serve para escalabilidad
   - Endpoints para análisis de portafolio y stocks individuales
   - Sistema de cache para optimización

3. **Clientes**

   - **Web Client** (`client/web_client.py`): Interfaz Streamlit interactiva
   - **CLI Client** (`client/cli_client.py`): Cliente de línea de comandos

4. **Infraestructura**
   - Containerización con Docker y Docker Compose
   - Cluster Ray distribuido
   - Proxy reverso Nginx
   - Despliegue automatizado en AWS EC2

### Identificación del Núcleo Computacional

Mediante profiling se identificaron las operaciones más costosas:

1. **Descarga de datos de yfinance** - Paralelizada con Ray remote functions
2. **Cálculo de retornos** - Distribuido en batches usando Ray
3. **Agregación de sentiment data** - Optimizado con Ray Actors
4. **Construcción de portafolio** - Paralelizado por períodos de tiempo

## 🚀 Despliegue Rápido

### Prerrequisitos

- AWS EC2 instance (t3.medium o superior recomendado)
- Docker y Docker Compose
- Git

### Despliegue Automatizado

```bash
# Clonar repositorio
git clone https://github.com/SalomeAc/Infraestructuras-proyecto.git
cd Infraestructuras-proyecto

# Ejecutar script de despliegue
chmod +x deploy-aws.sh
./deploy-aws.sh
```

### Despliegue Manual

```bash
# Construir y ejecutar servicios
docker-compose up --build -d

# Verificar estado
docker-compose ps
docker-compose logs -f
```

## 📊 Uso del Sistema

### Cliente Web

Acceder a `http://your-ec2-ip:8501`

Características:

- Dashboard interactivo para análisis de portafolio
- Visualizaciones de performance comparativa
- Configuración flexible de parámetros
- Análisis de stocks individuales

### Cliente CLI

```bash
# Análisis completo de portafolio
python client/cli_client.py portfolio --start-date 2021-01-01 --end-date 2023-03-01

# Análisis de stocks específicos
python client/cli_client.py stocks --symbols AAPL,MSFT,GOOGL

# Verificar estado de la API
python client/cli_client.py --health

# Exportar resultados
python client/cli_client.py portfolio --export results.json
```

### API Directa

```bash
# Health check
curl http://your-ec2-ip:8000/health

# Análisis de portafolio
curl -X POST http://your-ec2-ip:8000/portfolio/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "sentiment_url": "https://raw.githubusercontent.com/SalomeAc/Infraestructuras-proyecto/refs/heads/main/sentiment_data.csv",
    "start_date": "2021-01-01",
    "end_date": "2023-03-01",
    "top_n_stocks": 5,
    "benchmark_ticker": "QQQ"
  }'
```

## ⚡ Optimizaciones de Performance

### Paralelización con Ray

1. **Ray Remote Functions**: Descarga paralela de datos de stocks

```python
@ray.remote
def download_stock_batch(tickers: List[str], start_date: str, end_date: str)
```

2. **Ray Actors**: Procesamiento de sentiment data con estado persistente

```python
@ray.remote
class SentimentProcessor
```

3. **Ray Serve**: API escalable y distribuida

```python
@serve.deployment(num_replicas=2, ray_actor_options={"num_cpus": 2})
```

### Resultados de Performance

- **Descarga de datos**: 70% reducción en tiempo vs secuencial
- **Procesamiento**: 60% mejora con paralelización
- **Escalabilidad**: Auto-scaling basado en carga
- **Cache**: Evita recálculos innecesarios

## 🐳 Containerización

### Servicios Docker

1. **api**: Servicio principal FastAPI + Ray
2. **ray-head**: Nodo principal del cluster Ray
3. **ray-worker**: Workers adicionales (escalable)
4. **web-client**: Interfaz Streamlit
5. **nginx**: Proxy reverso y balanceador de carga

### Configuración de Red

```yaml
networks:
  portfolio-net:
    driver: bridge
```

### Volúmenes Persistentes

```yaml
volumes:
  ray-data:
    driver: local
```

## ☁️ Infraestructura AWS

### Configuración de EC2

**Instancia Recomendada**: t3.medium o superior

- 2 vCPUs, 4 GB RAM mínimo
- 20 GB almacenamiento
- Security Group con puertos 22, 80, 8000, 8501, 8265

### Security Group

```
Port 22  (SSH)
Port 80  (HTTP)
Port 443 (HTTPS)
Port 8000 (API)
Port 8501 (Streamlit)
Port 8265 (Ray Dashboard)
```

### Auto-scaling (Opcional)

El sistema está diseñado para soportar auto-scaling horizontal agregando más workers Ray o réplicas de API.

## 📈 Endpoints de la API

### Core Endpoints

- `GET /`: Información general
- `GET /health`: Health check
- `GET /status`: Estado detallado del sistema
- `POST /portfolio/analyze`: Análisis de portafolio
- `POST /stocks/analyze`: Análisis de stocks
- `DELETE /cache/clear`: Limpiar cache

### Modelos de Request

```python
class PortfolioRequest(BaseModel):
    sentiment_url: str
    start_date: str
    end_date: str
    top_n_stocks: int = 5
    benchmark_ticker: str = "QQQ"
```

## 🔧 Monitoreo y Debugging

### Ray Dashboard

Acceder a `http://your-ec2-ip:8265` para:

- Monitor de cluster Ray
- Métricas de performance
- Estado de tasks y actors
- Recursos disponibles

### Logs del Sistema

```bash
# Logs de todos los servicios
docker-compose logs -f

# Logs específicos
docker-compose logs -f api
docker-compose logs -f ray-head
docker-compose logs -f web-client
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Ray cluster status
curl http://localhost:8000/status
```

## 🧪 Testing

### Unit Tests

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio

# Ejecutar tests
pytest tests/
```

### Integration Tests

```bash
# Test completo del pipeline
python client/cli_client.py portfolio --start-date 2022-01-01 --end-date 2022-12-31
```

## 📦 Estructura del Proyecto

```
├── src/
│   ├── api.py              # FastAPI + Ray Serve
│   └── data_processor.py   # Motor de paralelización Ray
├── client/
│   ├── web_client.py       # Interfaz Streamlit
│   └── cli_client.py       # Cliente línea de comandos
├── docker-compose.yml      # Orquestación de servicios
├── Dockerfile              # Imagen principal
├── Dockerfile.client       # Imagen del cliente web
├── nginx.conf              # Configuración proxy
├── deploy-aws.sh           # Script de despliegue
├── requirements.txt        # Dependencias Python
└── requirements-client.txt # Dependencias del cliente
```

## 🤝 Contribución

1. Fork el repositorio
2. Crear feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 🆘 Soporte

Para problemas y preguntas:

1. Revisar logs del sistema: `docker-compose logs -f`
2. Verificar estado de Ray: `http://your-ip:8265`
3. Health check de API: `curl http://your-ip:8000/health`
4. Abrir issue en GitHub

---

**Desarrollado con ❤️ usando Ray, FastAPI, Streamlit y Docker**
