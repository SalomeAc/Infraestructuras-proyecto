"""
API simplificada sin Ray para compatibilidad con Windows/Python 3.13
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List
from pydantic import BaseModel
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
import time

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
    title="Portfolio Optimization API (Sin Ray)",
    description="API para optimización de portafolios usando sentiment analysis",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache simple
cache = {}

def download_stock_batch_simple(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Función para descargar un lote de acciones (versión sin Ray)"""
    try:
        logger.info(f"Descargando lote: {tickers[:3]}... ({len(tickers)} tickers)")
        data = yf.download(
            tickers=tickers, 
            start=start_date, 
            end=end_date,
            auto_adjust=False, 
            progress=False
        )
        return data
    except Exception as e:
        logger.error(f"Error descargando lote {tickers}: {str(e)}")
        return pd.DataFrame()

def parallel_stock_download_simple(stocks_list: List[str], start_date: str, end_date: str, batch_size: int = 15) -> pd.DataFrame:
    """Descarga datos de acciones en paralelo usando ThreadPoolExecutor"""
    
    # Dividir la lista en lotes
    batches = [stocks_list[i:i + batch_size] for i in range(0, len(stocks_list), batch_size)]
    
    # Crear pool de threads para paralelización
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download_stock_batch_simple, batch, start_date, end_date): batch 
                  for batch in batches}
        
        results = []
        for future in futures:
            try:
                result = future.result()
                if not result.empty:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error en lote: {e}")
    
    # Combinar resultados válidos
    if results:
        combined_df = pd.concat(results, axis=1)
        logger.info(f"Descarga completada. Forma final: {combined_df.shape}")
        return combined_df
    else:
        return pd.DataFrame()

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Portfolio Optimization API (Versión Simplificada)",
        "version": "1.0.0",
        "note": "Versión sin Ray para compatibilidad",
        "endpoints": {
            "portfolio": "/portfolio/analyze",
            "stocks": "/stocks/analyze", 
            "health": "/health",
            "status": "/status"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "simplified",
        "cache_size": len(cache)
    }

@app.get("/status")
async def get_status():
    """Obtener estado del sistema"""
    return {
        "api_version": "simplified_no_ray",
        "cache_entries": len(cache),
        "timestamp": datetime.now().isoformat(),
        "parallelization": "ThreadPoolExecutor"
    }

@app.post("/portfolio/analyze")
async def analyze_portfolio(request: PortfolioRequest):
    """Analizar portafolio basado en sentiment analysis"""
    try:
        logger.info(f"Iniciando análisis de portafolio: {request.dict()}")
        
        # Crear clave de cache
        cache_key = f"portfolio_{hash(str(request.dict()))}"
        
        # Verificar cache
        if cache_key in cache:
            logger.info("Resultado obtenido del cache")
            return cache[cache_key]
        
        start_time = time.time()
        
        # Cargar datos de sentiment
        logger.info("Cargando datos de sentiment...")
        sentiment_df = pd.read_csv(request.sentiment_url)
        sentiment_df['date'] = pd.to_datetime(sentiment_df['date'])
        sentiment_df = sentiment_df.set_index(['date', 'symbol'])
        sentiment_df['engagement_ratio'] = sentiment_df['twitterComments'] / sentiment_df['twitterLikes']
        sentiment_df = sentiment_df[(sentiment_df['twitterLikes'] > 20) & (sentiment_df['twitterComments'] > 10)]
        
        # Agregar por mes
        aggregated_df = (sentiment_df.reset_index('symbol')
                        .groupby([pd.Grouper(freq='ME'), 'symbol'])  # Usar 'ME' en lugar de 'M'
                        [['engagement_ratio']].mean())
        
        aggregated_df['rank'] = (aggregated_df.groupby(level=0)['engagement_ratio']
                               .transform(lambda x: x.rank(ascending=False)))
        
        # Filtrar top N stocks
        filtered_df = aggregated_df[aggregated_df['rank'] < (request.top_n_stocks + 1)].copy()
        filtered_df = filtered_df.reset_index(level=1)
        filtered_df.index = filtered_df.index + pd.DateOffset(1)
        filtered_df = filtered_df.reset_index().set_index(['date', 'symbol'])
        
        # Crear diccionario de fechas
        dates = filtered_df.index.get_level_values('date').unique().tolist()
        portfolio_dates = {}
        for d in dates:
            portfolio_dates[d.strftime('%Y-%m-%d')] = filtered_df.xs(d, level=0).index.tolist()
        
        # Obtener stocks únicos
        all_stocks = []
        for stocks in portfolio_dates.values():
            all_stocks.extend(stocks)
        unique_stocks = list(set(all_stocks))
        
        # Excluir stocks problemáticos
        excluded = ['MRO', 'ATVI']
        unique_stocks = [s for s in unique_stocks if s not in excluded]
        
        logger.info(f"Descargando datos para {len(unique_stocks)} stocks...")
        
        # Descargar datos de stocks
        prices_df = parallel_stock_download_simple(unique_stocks, request.start_date, request.end_date)
        
        if prices_df.empty:
            raise HTTPException(status_code=500, detail="No se pudieron descargar datos de acciones")
        
        # Procesar retornos
        if isinstance(prices_df.columns, pd.MultiIndex):
            if 'Adj Close' in prices_df.columns.get_level_values(0):
                adj_close_df = prices_df.xs('Adj Close', axis=1, level=0)
            else:
                adj_close_df = prices_df.xs('Adj Close', axis=1, level=1)
        else:
            adj_close_df = prices_df['Adj Close'] if 'Adj Close' in prices_df.columns else prices_df
        
        returns_df = np.log(adj_close_df).diff().dropna()
        
        # Calcular retornos del portafolio
        portfolio_df = pd.DataFrame()
        for start_date in portfolio_dates.keys():
            end_date = (pd.to_datetime(start_date) + pd.offsets.MonthEnd()).strftime('%Y-%m-%d')
            cols = portfolio_dates[start_date]
            valid_cols = [c for c in cols if c in returns_df.columns]
            
            if valid_cols:
                temp_df = returns_df.loc[start_date:end_date, valid_cols].mean(axis=1).to_frame('portfolio_return')
                portfolio_df = pd.concat([portfolio_df, temp_df])
        
        # Obtener datos de benchmark
        benchmark_data = yf.download(
            tickers=request.benchmark_ticker,
            start=request.start_date,
            end=request.end_date,
            auto_adjust=False
        )
        
        if isinstance(benchmark_data.columns, pd.MultiIndex):
            benchmark_adj_close = benchmark_data['Adj Close']
        else:
            benchmark_adj_close = benchmark_data['Adj Close']
        
        benchmark_returns = np.log(benchmark_adj_close).diff()
        benchmark_returns.columns = [f'{request.benchmark_ticker.lower()}_return']
        
        # Combinar con benchmark
        combined_performance = portfolio_df.merge(
            benchmark_returns, left_index=True, right_index=True, how='left'
        )
        
        # Calcular métricas
        portfolio_returns = combined_performance['portfolio_return'].dropna()
        benchmark_rets = combined_performance[f'{request.benchmark_ticker.lower()}_return'].dropna()
        
        # Retornos acumulativos
        portfolio_cumulative = np.exp(np.log1p(portfolio_returns).cumsum()).sub(1)
        benchmark_cumulative = np.exp(np.log1p(benchmark_rets).cumsum()).sub(1)
        
        # Métricas
        total_portfolio_return = portfolio_cumulative.iloc[-1] if len(portfolio_cumulative) > 0 else 0
        total_benchmark_return = benchmark_cumulative.iloc[-1] if len(benchmark_cumulative) > 0 else 0
        
        portfolio_volatility = portfolio_returns.std() * np.sqrt(252)
        benchmark_volatility = benchmark_rets.std() * np.sqrt(252)
        
        sharpe_ratio = (portfolio_returns.mean() * 252) / portfolio_volatility if portfolio_volatility > 0 else 0
        
        processing_time = time.time() - start_time
        
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
                "timestamp": datetime.now().isoformat(),
                "api_version": "simplified_no_ray"
            }
        }
        
        # Guardar en cache
        cache[cache_key] = result
        
        logger.info(f"Análisis completado en {processing_time:.2f} segundos")
        return result
        
    except Exception as e:
        logger.error(f"Error en análisis de portafolio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.delete("/cache/clear")
async def clear_cache():
    """Limpiar cache"""
    global cache
    cache_size = len(cache)
    cache.clear()
    return {
        "status": "success",
        "message": f"Cache limpiado. {cache_size} entradas eliminadas.",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Iniciando API de Portfolio Optimization (Versión Simplificada)")
    print("📊 Sin Ray - Compatible con Windows/Python 3.13")
    print("🔗 API disponible en: http://localhost:8000")
    print("📚 Documentación en: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")