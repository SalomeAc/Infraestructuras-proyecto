"""
Módulo de procesamiento de datos con paralelización Ray
Identifica y paraleliza las operaciones más costosas computacionalmente.
"""
import ray
import pandas as pd
import numpy as np
import yfinance as yf
import time
from typing import List, Dict, Tuple
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar Ray si no está inicializado
if not ray.is_initialized():
    ray.init()

@ray.remote
class SentimentProcessor:
    """Procesador de datos de sentimiento como Actor Ray para mantener estado"""
    
    def __init__(self):
        self.sentiment_df = None
        self.aggregated_df = None
        self.filtered_df = None
        
    def load_sentiment_data(self, url: str):
        """Cargar y procesar datos de sentimiento"""
        logger.info("Cargando datos de sentimiento...")
        self.sentiment_df = pd.read_csv(url)
        self.sentiment_df['date'] = pd.to_datetime(self.sentiment_df['date'])
        self.sentiment_df = self.sentiment_df.set_index(['date', 'symbol'])
        self.sentiment_df['engagement_ratio'] = (
            self.sentiment_df['twitterComments'] / self.sentiment_df['twitterLikes']
        )
        # Filtrar datos con suficiente engagement
        self.sentiment_df = self.sentiment_df[
            (self.sentiment_df['twitterLikes'] > 20) & 
            (self.sentiment_df['twitterComments'] > 10)
        ]
        return True
        
    def aggregate_sentiment(self):
        """Agregar datos por mes y símbolo"""
        logger.info("Agregando datos de sentimiento...")
        self.aggregated_df = (
            self.sentiment_df.reset_index('symbol')
            .groupby([pd.Grouper(freq='M'), 'symbol'])
            [['engagement_ratio']].mean()
        )
        # Ranking por mes
        self.aggregated_df['rank'] = (
            self.aggregated_df.groupby(level=0)['engagement_ratio']
            .transform(lambda x: x.rank(ascending=False))
        )
        return True
        
    def filter_top_stocks(self, top_n: int = 5):
        """Filtrar top N stocks por mes"""
        logger.info(f"Filtrando top {top_n} stocks...")
        self.filtered_df = self.aggregated_df[self.aggregated_df['rank'] < (top_n + 1)].copy()
        self.filtered_df = self.filtered_df.reset_index(level=1)
        self.filtered_df.index = self.filtered_df.index + pd.DateOffset(1)
        self.filtered_df = self.filtered_df.reset_index().set_index(['date', 'symbol'])
        return True
        
    def get_portfolio_dates(self) -> Dict[str, List[str]]:
        """Obtener fechas del portafolio"""
        dates = self.filtered_df.index.get_level_values('date').unique().tolist()
        fixed_dates = {}
        for d in dates:
            fixed_dates[d.strftime('%Y-%m-%d')] = (
                self.filtered_df.xs(d, level=0).index.tolist()
            )
        return fixed_dates

@ray.remote
def download_stock_batch(tickers: List[str], start_date: str, end_date: str, 
                        auto_adjust: bool = False) -> pd.DataFrame:
    """Función remota para descargar un lote de acciones"""
    try:
        logger.info(f"Descargando lote: {tickers[:3]}... ({len(tickers)} tickers)")
        data = yf.download(
            tickers=tickers, 
            start=start_date, 
            end=end_date,
            auto_adjust=auto_adjust, 
            progress=False
        )
        return data
    except Exception as e:
        logger.error(f"Error descargando lote {tickers}: {str(e)}")
        return pd.DataFrame()

@ray.remote
def calculate_returns_batch(prices_batch: pd.DataFrame) -> pd.DataFrame:
    """Calcular retornos para un lote de datos"""
    try:
        if isinstance(prices_batch.columns, pd.MultiIndex):
            if 'Adj Close' in prices_batch.columns.get_level_values(0):
                adj_close = prices_batch.xs('Adj Close', axis=1, level=0)
            else:
                adj_close = prices_batch.xs('Adj Close', axis=1, level=1)
        else:
            adj_close = prices_batch['Adj Close'] if 'Adj Close' in prices_batch.columns else prices_batch
            
        returns = np.log(adj_close).diff().dropna()
        return returns
    except Exception as e:
        logger.error(f"Error calculando retornos: {str(e)}")
        return pd.DataFrame()

@ray.remote
def calculate_portfolio_returns_batch(returns_df: pd.DataFrame, 
                                    portfolio_dates: Dict[str, List[str]],
                                    date_batch: List[str]) -> pd.DataFrame:
    """Calcular retornos del portafolio para un lote de fechas"""
    portfolio_batch = pd.DataFrame()
    
    for start_date in date_batch:
        if start_date not in portfolio_dates:
            continue
            
        end_date = (pd.to_datetime(start_date) + pd.offsets.MonthEnd()).strftime('%Y-%m-%d')
        cols = portfolio_dates[start_date]
        valid_cols = [c for c in cols if c in returns_df.columns]
        
        if valid_cols:
            temp_df = (returns_df.loc[start_date:end_date, valid_cols]
                      .mean(axis=1).to_frame('portfolio_return'))
            portfolio_batch = pd.concat([portfolio_batch, temp_df])
            
    return portfolio_batch

class ParallelPortfolioEngine:
    """Motor principal para el procesamiento paralelo del portafolio"""
    
    def __init__(self, batch_size: int = 20):
        self.batch_size = batch_size
        self.sentiment_processor = None
        
    async def process_sentiment_data(self, url: str):
        """Procesar datos de sentimiento de forma paralela"""
        start_time = time.time()
        
        # Crear procesador de sentimiento
        self.sentiment_processor = SentimentProcessor.remote()
        
        # Procesar en paralelo
        await self.sentiment_processor.load_sentiment_data.remote(url)
        await self.sentiment_processor.aggregate_sentiment.remote()
        await self.sentiment_processor.filter_top_stocks.remote()
        
        portfolio_dates = await self.sentiment_processor.get_portfolio_dates.remote()
        
        logger.info(f"Procesamiento de sentimiento completado en {time.time() - start_time:.2f}s")
        return portfolio_dates
    
    def process_sentiment_data_sync(self, url: str):
        """Procesar datos de sentimiento de forma paralela (versión síncrona)"""
        start_time = time.time()
        
        # Crear procesador de sentimiento
        self.sentiment_processor = SentimentProcessor.remote()
        
        # Procesar en paralelo usando ray.get()
        ray.get(self.sentiment_processor.load_sentiment_data.remote(url))
        ray.get(self.sentiment_processor.aggregate_sentiment.remote())
        ray.get(self.sentiment_processor.filter_top_stocks.remote())
        
        portfolio_dates = ray.get(self.sentiment_processor.get_portfolio_dates.remote())
        
        logger.info(f"Procesamiento de sentimiento completado en {time.time() - start_time:.2f}s")
        return portfolio_dates
        
    def download_stock_data_parallel(self, stocks_list: List[str], 
                                   start_date: str = '2021-01-01',
                                   end_date: str = '2023-03-01') -> pd.DataFrame:
        """Descargar datos de acciones en paralelo"""
        start_time = time.time()
        
        # Excluir acciones problemáticas
        excluded = ['MRO', 'ATVI']
        stocks_list = [s for s in stocks_list if s not in excluded]
        
        # Dividir en lotes
        batches = [stocks_list[i:i + self.batch_size] 
                  for i in range(0, len(stocks_list), self.batch_size)]
        
        logger.info(f"Descargando {len(stocks_list)} acciones en {len(batches)} lotes...")
        
        # Crear tareas remotas
        futures = [download_stock_batch.remote(batch, start_date, end_date, False)
                  for batch in batches]
        
        # Obtener resultados
        results = ray.get(futures)
        
        # Combinar resultados válidos
        valid_dataframes = [df for df in results if not df.empty]
        
        if valid_dataframes:
            combined_df = pd.concat(valid_dataframes, axis=1)
            logger.info(f"Descarga completada en {time.time() - start_time:.2f}s")
            return combined_df
        else:
            logger.warning("No se pudieron descargar datos de acciones")
            return pd.DataFrame()
            
    def calculate_portfolio_performance(self, prices_df: pd.DataFrame, 
                                      portfolio_dates: Dict[str, List[str]]) -> pd.DataFrame:
        """Calcular performance del portafolio en paralelo"""
        start_time = time.time()
        
        # Calcular retornos en paralelo
        returns_future = calculate_returns_batch.remote(prices_df)
        returns_df = ray.get(returns_future)
        
        # Dividir fechas en lotes para procesamiento paralelo
        date_list = list(portfolio_dates.keys())
        date_batches = [date_list[i:i + 5] for i in range(0, len(date_list), 5)]
        
        # Calcular retornos del portafolio en paralelo
        portfolio_futures = [
            calculate_portfolio_returns_batch.remote(returns_df, portfolio_dates, batch)
            for batch in date_batches
        ]
        
        portfolio_results = ray.get(portfolio_futures)
        
        # Combinar resultados
        portfolio_df = pd.concat([df for df in portfolio_results if not df.empty])
        
        logger.info(f"Cálculo de performance completado en {time.time() - start_time:.2f}s")
        return portfolio_df
        
    def get_benchmark_data(self, ticker: str = 'QQQ', 
                          start_date: str = '2021-01-01',
                          end_date: str = '2023-03-01') -> pd.DataFrame:
        """Obtener datos de benchmark"""
        benchmark_data = yf.download(
            tickers=ticker,
            start=start_date,
            end=end_date,
            auto_adjust=False
        )
        
        if isinstance(benchmark_data.columns, pd.MultiIndex):
            adj_close = benchmark_data['Adj Close']
        else:
            adj_close = benchmark_data['Adj Close']
            
        benchmark_returns = np.log(adj_close).diff()
        benchmark_returns.columns = [f'{ticker.lower()}_return']
        
        return benchmark_returns

def shutdown_ray():
    """Cerrar Ray de forma segura"""
    if ray.is_initialized():
        ray.shutdown()
