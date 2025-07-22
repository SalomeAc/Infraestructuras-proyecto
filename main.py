"""
Archivo principal para ejecutar el sistema de portfolio optimization
Versión optimizada con todas las mejoras de Ray implementadas
"""
import sys
import os
import asyncio
import time
import logging

# Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data_processor import ParallelPortfolioEngine, shutdown_ray
import ray

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_portfolio_analysis():
    """Ejecutar análisis completo del portafolio"""
    
    # Configuración
    sentiment_url = "https://raw.githubusercontent.com/SalomeAc/Infraestructuras-proyecto/refs/heads/main/sentiment_data.csv"
    start_date = "2021-01-01"
    end_date = "2023-03-01"
    top_n_stocks = 5
    
    try:
        logger.info("🚀 Iniciando Portfolio Optimization con Ray")
        start_time = time.time()
        
        # Crear motor de portfolio
        engine = ParallelPortfolioEngine(batch_size=15)
        
        # Procesar datos de sentiment
        logger.info("📊 Procesando datos de sentiment...")
        portfolio_dates = await engine.process_sentiment_data(sentiment_url)
        
        if not portfolio_dates:
            logger.error("❌ No se pudieron procesar datos de sentiment")
            return
        
        logger.info(f"✅ Datos de sentiment procesados. {len(portfolio_dates)} períodos encontrados")
        
        # Obtener stocks únicos
        all_stocks = []
        for stocks in portfolio_dates.values():
            all_stocks.extend(stocks)
        unique_stocks = list(set(all_stocks))
        
        logger.info(f"📈 Descargando datos para {len(unique_stocks)} stocks únicos...")
        
        # Descargar datos de stocks en paralelo
        prices_df = engine.download_stock_data_parallel(
            unique_stocks, start_date, end_date
        )
        
        if prices_df.empty:
            logger.error("❌ No se pudieron descargar datos de acciones")
            return
        
        logger.info(f"✅ Datos de stocks descargados. Forma: {prices_df.shape}")
        
        # Calcular performance del portafolio
        logger.info("⚡ Calculando performance del portafolio...")
        portfolio_performance = engine.calculate_portfolio_performance(
            prices_df, portfolio_dates
        )
        
        # Obtener datos de benchmark
        logger.info("📊 Obteniendo datos de benchmark (QQQ)...")
        benchmark_data = engine.get_benchmark_data("QQQ", start_date, end_date)
        
        # Combinar con benchmark
        combined_performance = portfolio_performance.merge(
            benchmark_data, left_index=True, right_index=True, how='left'
        )
        
        # Calcular métricas finales
        logger.info("📈 Calculando métricas de performance...")
        
        portfolio_returns = combined_performance['portfolio_return'].dropna()
        benchmark_returns = combined_performance['qqq_return'].dropna()
        
        # Retornos acumulativos
        import numpy as np
        portfolio_cumulative = np.exp(np.log1p(portfolio_returns).cumsum()).sub(1)
        benchmark_cumulative = np.exp(np.log1p(benchmark_returns).cumsum()).sub(1)
        
        # Métricas
        total_portfolio_return = portfolio_cumulative.iloc[-1] if len(portfolio_cumulative) > 0 else 0
        total_benchmark_return = benchmark_cumulative.iloc[-1] if len(benchmark_cumulative) > 0 else 0
        
        portfolio_volatility = portfolio_returns.std() * np.sqrt(252)
        benchmark_volatility = benchmark_returns.std() * np.sqrt(252)
        
        sharpe_ratio = (portfolio_returns.mean() * 252) / portfolio_volatility if portfolio_volatility > 0 else 0
        
        processing_time = time.time() - start_time
        
        # Mostrar resultados
        logger.info("🎉 ¡Análisis completado exitosamente!")
        print("\n" + "="*60)
        print("📈 RESULTADOS DEL ANÁLISIS DE PORTFOLIO")
        print("="*60)
        print(f"⏱️  Tiempo de procesamiento:     {processing_time:.2f} segundos")
        print(f"📊 Períodos analizados:         {len(portfolio_dates)}")
        print(f"🏢 Stocks únicos:               {len(unique_stocks)}")
        print(f"📈 Retorno Total Portfolio:     {total_portfolio_return:.2%}")
        print(f"📊 Retorno Total Benchmark:     {total_benchmark_return:.2%}")
        print(f"⚡ Retorno en Exceso:           {total_portfolio_return - total_benchmark_return:.2%}")
        print(f"📉 Volatilidad Portfolio:       {portfolio_volatility:.2%}")
        print(f"📉 Volatilidad Benchmark:       {benchmark_volatility:.2%}")
        print(f"⭐ Sharpe Ratio:                {sharpe_ratio:.3f}")
        print("="*60)
        
        # Mostrar algunos de los top stocks más frecuentes
        print("\n🏆 TOP STOCKS MÁS FRECUENTES:")
        stock_frequency = {}
        for stocks in portfolio_dates.values():
            for stock in stocks:
                stock_frequency[stock] = stock_frequency.get(stock, 0) + 1
        
        top_stocks = sorted(stock_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (stock, freq) in enumerate(top_stocks, 1):
            print(f"{i:2d}. {stock}: {freq} meses")
        
        # Mostrar últimas composiciones
        print(f"\n📅 ÚLTIMAS 5 COMPOSICIONES DE PORTFOLIO:")
        for date in sorted(portfolio_dates.keys())[-5:]:
            stocks = portfolio_dates[date]
            print(f"{date}: {', '.join(stocks)}")
        
        # Guardar resultados en archivo
        import json
        results = {
            "analysis": {
                "total_portfolio_return": float(total_portfolio_return),
                "total_benchmark_return": float(total_benchmark_return),
                "excess_return": float(total_portfolio_return - total_benchmark_return),
                "portfolio_volatility": float(portfolio_volatility),
                "benchmark_volatility": float(benchmark_volatility),
                "sharpe_ratio": float(sharpe_ratio),
                "processing_time_seconds": processing_time,
                "number_of_periods": len(portfolio_dates),
                "unique_stocks_analyzed": len(unique_stocks)
            },
            "portfolio_composition": portfolio_dates,
            "top_stocks": dict(top_stocks),
            "performance_data": {
                "dates": portfolio_cumulative.index.strftime('%Y-%m-%d').tolist(),
                "portfolio_cumulative_returns": portfolio_cumulative.values.tolist(),
                "benchmark_cumulative_returns": benchmark_cumulative.values.tolist()
            }
        }
        
        with open('portfolio_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("💾 Resultados guardados en 'portfolio_results.json'")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error en el análisis: {str(e)}")
        raise
    finally:
        # Limpiar Ray
        shutdown_ray()
        logger.info("🧹 Ray desconectado")

def main():
    """Función principal"""
    print("🎯 Portfolio Optimization con Ray - Infraestructuras Paralelas")
    print("=" * 60)
    
    try:
        # Ejecutar análisis
        asyncio.run(run_portfolio_analysis())
        
    except KeyboardInterrupt:
        print("\n⚠️ Análisis interrumpido por el usuario")
        shutdown_ray()
    except Exception as e:
        print(f"\n❌ Error fatal: {str(e)}")
        shutdown_ray()
        sys.exit(1)
    
    print("\n✅ Programa completado exitosamente")

if __name__ == "__main__":
    main()
