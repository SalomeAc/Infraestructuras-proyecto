"""
API principal usando FastAPI con Ray Serve para servir el modelo de portafolio
"""
import ray
from ray import serve
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
import asyncio
import json
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import sys

# Agregar el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from data_processor import ParallelPortfolioEngine

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modelos Pydantic para requests
class PortfolioRequest(BaseModel):
    sentiment_url: str = "https://raw.githubusercontent.com/SalomeAc/Infraestructuras-proyecto/refs/heads/main/sentiment_data.csv"
    start_date: str = "2021-01-01"
    end_date: str = "2023-03-01"
    top_n_stocks: int = 5
    benchmark_ticker: str = "QQQ"

class StockAnalysisRequest(BaseModel):
    symbols: List[str]
    start_date: str = "2021-01-01"
    end_date: str = "2023-03-01"

# Crear aplicación FastAPI
app = FastAPI(
    title="Portfolio Optimization API with Ray",
    description="API para optimización de portafolios usando sentiment analysis y Ray",
    version="2.0.0-ray"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@serve.deployment(num_replicas=1, ray_actor_options={"num_cpus": 2})
@serve.ingress(app)
class PortfolioAPI:
    """Deployment principal de la API usando Ray Serve"""
    
    def __init__(self):
        self.engine = ParallelPortfolioEngine(batch_size=15)
        self.cache = {}
        logger.info("PortfolioAPI con Ray inicializada")
    
    @app.get("/")
    def root(self):
        """Endpoint raíz"""
        return {
            "message": "Portfolio Optimization API with Ray",
            "version": "2.0.0-ray",
            "engine": "Ray Serve",
            "endpoints": {
                "portfolio": "/portfolio/analyze",
                "stocks": "/stocks/analyze", 
                "health": "/health",
                "status": "/status"
            }
        }
    
    @app.get("/health")
    def health_check(self):
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "ray-enabled",
            "ray_initialized": ray.is_initialized(),
            "cache_size": len(self.cache)
        }
    
    @app.get("/status")
    def get_status(self):
        """Obtener estado del sistema"""
        ray_status = {}
        if ray.is_initialized():
            try:
                ray_status = {
                    "nodes": len(ray.nodes()),
                    "available_resources": ray.available_resources(),
                    "cluster_resources": ray.cluster_resources()
                }
            except Exception as e:
                ray_status = {"error": str(e)}
        
        return {
            "ray_initialized": ray.is_initialized(),
            "ray_status": ray_status,
            "cache_entries": len(self.cache),
            "timestamp": datetime.now().isoformat()
        }
    
    @app.post("/portfolio/analyze")
    def analyze_portfolio(self, request: PortfolioRequest):
        """Analizar portafolio basado en sentiment analysis"""
        try:
            logger.info(f"Iniciando análisis de portafolio: {request.dict()}")
            
            # Crear clave de cache
            cache_key = f"portfolio_{hash(str(request.dict()))}"
            
            # Verificar cache
            if cache_key in self.cache:
                logger.info("Resultado obtenido del cache")
                return self.cache[cache_key]
            
            start_time = datetime.now()
            
            # Procesar datos de sentimiento (sin async)
            portfolio_dates = self.engine.process_sentiment_data_sync(request.sentiment_url)
            
            if not portfolio_dates:
                raise HTTPException(status_code=400, detail="No se pudieron procesar datos de sentimiento")
            
            # Obtener lista de stocks únicos
            all_stocks = []
            for stocks in portfolio_dates.values():
                all_stocks.extend(stocks)
            unique_stocks = list(set(all_stocks))
            
            logger.info(f"Analizando {len(unique_stocks)} stocks únicos")
            
            # Descargar datos de acciones en paralelo
            prices_df = self.engine.download_stock_data_parallel(
                unique_stocks, request.start_date, request.end_date
            )
            
            if prices_df.empty:
                raise HTTPException(status_code=500, detail="No se pudieron descargar datos de acciones")
            
            # Calcular performance del portafolio
            portfolio_performance = self.engine.calculate_portfolio_performance(
                prices_df, portfolio_dates
            )
            
            # Obtener datos de benchmark
            benchmark_data = self.engine.get_benchmark_data(
                request.benchmark_ticker, request.start_date, request.end_date
            )
            
            # Combinar con benchmark
            combined_performance = portfolio_performance.merge(
                benchmark_data, left_index=True, right_index=True, how='left'
            )
            
            # Calcular métricas de performance
            portfolio_returns = combined_performance['portfolio_return'].dropna()
            benchmark_returns = combined_performance[f'{request.benchmark_ticker.lower()}_return'].dropna()
            
            # Retornos acumulativos
            portfolio_cumulative = np.exp(np.log1p(portfolio_returns).cumsum()).sub(1)
            benchmark_cumulative = np.exp(np.log1p(benchmark_returns).cumsum()).sub(1)
            
            # Métricas
            total_portfolio_return = portfolio_cumulative.iloc[-1] if len(portfolio_cumulative) > 0 else 0
            total_benchmark_return = benchmark_cumulative.iloc[-1] if len(benchmark_cumulative) > 0 else 0
            
            portfolio_volatility = portfolio_returns.std() * np.sqrt(252)
            benchmark_volatility = benchmark_returns.std() * np.sqrt(252)
            
            sharpe_ratio = (portfolio_returns.mean() * 252) / portfolio_volatility if portfolio_volatility > 0 else 0
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "status": "success",
                "processing_time_seconds": processing_time,
                "analysis": {
                    "total_portfolio_return": float(total_portfolio_return),
                    "total_benchmark_return": float(total_benchmark_return),
                    "excess_return": float(total_portfolio_return - total_benchmark_return),
                    "portfolio_volatility": float(portfolio_volatility),
                    "benchmark_volatility": float(benchmark_volatility),
                    "sharpe_ratio": float(sharpe_ratio),
                    "number_of_periods": len(portfolio_dates),
                    "unique_stocks_analyzed": len(unique_stocks)
                },
                "performance_data": {
                    "dates": portfolio_cumulative.index.strftime('%Y-%m-%d').tolist(),
                    "portfolio_cumulative_returns": portfolio_cumulative.values.tolist(),
                    "benchmark_cumulative_returns": benchmark_cumulative.values.tolist()
                },
                "portfolio_composition": portfolio_dates,
                "metadata": {
                    "request_params": request.dict(),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Guardar en cache
            self.cache[cache_key] = result
            
            logger.info(f"Análisis completado en {processing_time:.2f} segundos")
            return result
            
        except Exception as e:
            logger.error(f"Error en análisis de portafolio: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
    @app.post("/stocks/analyze")
    def analyze_stocks(self, request: StockAnalysisRequest):
        """Analizar stocks individuales"""
        try:
            logger.info(f"Analizando stocks: {request.symbols}")
            
            # Descargar datos
            prices_df = self.engine.download_stock_data_parallel(
                request.symbols, request.start_date, request.end_date
            )
            
            if prices_df.empty:
                raise HTTPException(status_code=500, detail="No se pudieron descargar datos")
            
            # Procesar retornos
            if isinstance(prices_df.columns, pd.MultiIndex):
                if 'Adj Close' in prices_df.columns.get_level_values(0):
                    adj_close = prices_df.xs('Adj Close', axis=1, level=0)
                else:
                    adj_close = prices_df.xs('Adj Close', axis=1, level=1)
            else:
                adj_close = prices_df['Adj Close'] if 'Adj Close' in prices_df.columns else prices_df
            
            returns = np.log(adj_close).diff().dropna()
            
            # Calcular métricas por stock
            stock_metrics = {}
            for symbol in returns.columns:
                stock_returns = returns[symbol].dropna()
                if len(stock_returns) > 0:
                    total_return = np.exp(stock_returns.sum()) - 1
                    volatility = stock_returns.std() * np.sqrt(252)
                    sharpe = (stock_returns.mean() * 252) / volatility if volatility > 0 else 0
                    
                    stock_metrics[symbol] = {
                        "total_return": float(total_return),
                        "volatility": float(volatility),
                        "sharpe_ratio": float(sharpe),
                        "data_points": len(stock_returns)
                    }
            
            return {
                "status": "success",
                "stocks_analyzed": len(stock_metrics),
                "metrics": stock_metrics,
                "period": f"{request.start_date} to {request.end_date}",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en análisis de stocks: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
    @app.delete("/cache/clear")
    async def clear_cache(self):
        """Limpiar cache"""
        cache_size = len(self.cache)
        self.cache.clear()
        return {
            "status": "success",
            "message": f"Cache limpiado. {cache_size} entradas eliminadas.",
            "timestamp": datetime.now().isoformat()
        }

# Deployment de la aplicación
portfolio_deployment = PortfolioAPI.bind()

# Función para inicializar Ray Serve
def start_serve():
    """Inicializar Ray Serve"""
    if not ray.is_initialized():
        ray.init()
    
    serve.start(detached=True)
    serve.run(portfolio_deployment, name="portfolio_api", route_prefix="/")
    logger.info("Ray Serve iniciado exitosamente")

if __name__ == "__main__":
    import uvicorn
    
    try:
        # Inicializar Ray
        if not ray.is_initialized():
            ray.init()
            logger.info("Ray inicializado correctamente")
        
        # Iniciar Ray Serve
        serve.start(detached=True)
        logger.info("Ray Serve iniciado")
        
        # Deployar la aplicación
        serve.run(portfolio_deployment, name="portfolio_api", route_prefix="/")
        logger.info("API desplegada en Ray Serve en http://localhost:8000")
        
        # Mantener el servidor corriendo
        import signal
        import time
        
        def signal_handler(sig, frame):
            logger.info("Deteniendo Ray Serve...")
            serve.shutdown()
            ray.shutdown()
            exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("Servidor corriendo. Presiona Ctrl+C para detener.")
        while True:
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error al inicializar la API: {e}")
        if ray.is_initialized():
            ray.shutdown()
        raise
