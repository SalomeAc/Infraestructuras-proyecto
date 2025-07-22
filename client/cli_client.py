"""
Cliente de línea de comandos para la API de optimización de portafolios
"""
import argparse
import requests
import json
import sys
import time
from typing import Dict, List
from datetime import datetime
import pandas as pd

class PortfolioAPIClient:
    """Cliente para interactuar con la API de portafolios"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        
    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> Dict:
        """Realizar petición HTTP a la API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, timeout=300)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=300)
            elif method == "DELETE":
                response = requests.delete(url, timeout=300)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            print("❌ Error: La petición tardó demasiado tiempo")
            return {"error": "timeout"}
        except requests.exceptions.ConnectionError:
            print(f"❌ Error: No se puede conectar a {self.base_url}")
            return {"error": "connection_error"}
        except requests.exceptions.HTTPError as e:
            print(f"❌ Error HTTP {e.response.status_code}: {e.response.text}")
            return {"error": f"http_error_{e.response.status_code}"}
        except Exception as e:
            print(f"❌ Error inesperado: {str(e)}")
            return {"error": str(e)}
    
    def health_check(self) -> bool:
        """Verificar salud de la API"""
        print("🔍 Verificando estado de la API...")
        result = self._make_request("/health")
        
        if "error" in result:
            print(f"❌ API no disponible: {result['error']}")
            return False
        
        print("✅ API en línea")
        print(f"   Estado: {result.get('status', 'unknown')}")
        print(f"   Timestamp: {result.get('timestamp', 'unknown')}")
        print(f"   Ray inicializado: {result.get('ray_initialized', False)}")
        return True
    
    def get_status(self) -> Dict:
        """Obtener estado detallado del sistema"""
        print("📊 Obteniendo estado del sistema...")
        result = self._make_request("/status")
        
        if "error" not in result:
            print("✅ Estado obtenido exitosamente")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return result
    
    def analyze_portfolio(self, sentiment_url: str, start_date: str, end_date: str,
                         top_n_stocks: int = 5, benchmark_ticker: str = "QQQ") -> Dict:
        """Analizar portafolio"""
        print("🎯 Iniciando análisis de portafolio...")
        print(f"   URL sentiment: {sentiment_url}")
        print(f"   Período: {start_date} - {end_date}")
        print(f"   Top stocks: {top_n_stocks}")
        print(f"   Benchmark: {benchmark_ticker}")
        
        data = {
            "sentiment_url": sentiment_url,
            "start_date": start_date,
            "end_date": end_date,
            "top_n_stocks": top_n_stocks,
            "benchmark_ticker": benchmark_ticker
        }
        
        start_time = time.time()
        result = self._make_request("/portfolio/analyze", method="POST", data=data)
        end_time = time.time()
        
        if "error" in result:
            print(f"❌ Error en análisis: {result['error']}")
            return result
        
        print(f"✅ Análisis completado en {end_time - start_time:.2f} segundos")
        
        # Mostrar resultados principales
        if result.get("status") == "success":
            analysis = result["analysis"]
            print("\n📈 RESULTADOS DEL ANÁLISIS")
            print("=" * 50)
            print(f"Retorno Total Portafolio: {analysis['total_portfolio_return']:.2%}")
            print(f"Retorno Total Benchmark:  {analysis['total_benchmark_return']:.2%}")
            print(f"Retorno en Exceso:        {analysis['excess_return']:.2%}")
            print(f"Volatilidad Portafolio:   {analysis['portfolio_volatility']:.2%}")
            print(f"Volatilidad Benchmark:    {analysis['benchmark_volatility']:.2%}")
            print(f"Sharpe Ratio:             {analysis['sharpe_ratio']:.3f}")
            print(f"Períodos analizados:      {analysis['number_of_periods']}")
            print(f"Stocks únicos:            {analysis['unique_stocks_analyzed']}")
            
            # Tiempo de procesamiento
            proc_time = result.get("processing_time_seconds", 0)
            print(f"Tiempo de procesamiento:  {proc_time:.2f} segundos")
        
        return result
    
    def analyze_stocks(self, symbols: List[str], start_date: str, end_date: str) -> Dict:
        """Analizar stocks individuales"""
        print("📊 Iniciando análisis de stocks...")
        print(f"   Symbols: {', '.join(symbols)}")
        print(f"   Período: {start_date} - {end_date}")
        
        data = {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date
        }
        
        start_time = time.time()
        result = self._make_request("/stocks/analyze", method="POST", data=data)
        end_time = time.time()
        
        if "error" in result:
            print(f"❌ Error en análisis: {result['error']}")
            return result
        
        print(f"✅ Análisis completado en {end_time - start_time:.2f} segundos")
        
        # Mostrar resultados
        if result.get("status") == "success":
            print(f"\n📊 ANÁLISIS DE {result['stocks_analyzed']} STOCKS")
            print("=" * 70)
            print(f"{'Stock':<8} {'Retorno':<12} {'Volatilidad':<12} {'Sharpe':<8} {'Datos':<6}")
            print("-" * 70)
            
            for symbol, metrics in result["metrics"].items():
                print(f"{symbol:<8} {metrics['total_return']:>10.2%} "
                      f"{metrics['volatility']:>10.2%} {metrics['sharpe_ratio']:>6.3f} "
                      f"{metrics['data_points']:>5}")
        
        return result
    
    def clear_cache(self) -> Dict:
        """Limpiar cache del sistema"""
        print("🧹 Limpiando cache...")
        result = self._make_request("/cache/clear", method="DELETE")
        
        if "error" not in result:
            print(f"✅ {result.get('message', 'Cache limpiado')}")
        
        return result
    
    def export_results(self, result: Dict, filename: str):
        """Exportar resultados a archivo JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"📁 Resultados exportados a: {filename}")
        except Exception as e:
            print(f"❌ Error exportando resultados: {str(e)}")

def main():
    """Función principal del CLI"""
    parser = argparse.ArgumentParser(
        description="Cliente CLI para Portfolio Optimization API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Verificar estado de la API
  python cli_client.py --health

  # Análisis completo de portafolio
  python cli_client.py portfolio --start-date 2021-01-01 --end-date 2023-03-01

  # Análisis de stocks específicos
  python cli_client.py stocks --symbols AAPL,MSFT,GOOGL --start-date 2022-01-01

  # Obtener estado detallado del sistema
  python cli_client.py --status

  # Limpiar cache
  python cli_client.py --clear-cache
        """
    )
    
    # Argumentos globales
    parser.add_argument("--url", default="http://localhost:8000",
                       help="URL base de la API (default: http://localhost:8000)")
    parser.add_argument("--export", metavar="FILE",
                       help="Exportar resultados a archivo JSON")
    parser.add_argument("--health", action="store_true",
                       help="Verificar salud de la API")
    parser.add_argument("--status", action="store_true",
                       help="Obtener estado detallado del sistema")
    parser.add_argument("--clear-cache", action="store_true",
                       help="Limpiar cache del sistema")
    
    # Subcomandos
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Comando portfolio
    portfolio_parser = subparsers.add_parser("portfolio", help="Análisis de portafolio")
    portfolio_parser.add_argument("--sentiment-url", 
                                 default="https://raw.githubusercontent.com/SalomeAc/Infraestructuras-proyecto/refs/heads/main/sentiment_data.csv",
                                 help="URL de datos de sentiment")
    portfolio_parser.add_argument("--start-date", default="2021-01-01",
                                 help="Fecha de inicio (YYYY-MM-DD)")
    portfolio_parser.add_argument("--end-date", default="2023-03-01",
                                 help="Fecha de fin (YYYY-MM-DD)")
    portfolio_parser.add_argument("--top-stocks", type=int, default=5,
                                 help="Número de top stocks por mes")
    portfolio_parser.add_argument("--benchmark", default="QQQ",
                                 help="Ticker del benchmark")
    
    # Comando stocks
    stocks_parser = subparsers.add_parser("stocks", help="Análisis de stocks")
    stocks_parser.add_argument("--symbols", required=True,
                              help="Símbolos separados por comas (ej: AAPL,MSFT,GOOGL)")
    stocks_parser.add_argument("--start-date", default="2021-01-01",
                              help="Fecha de inicio (YYYY-MM-DD)")
    stocks_parser.add_argument("--end-date", default="2023-03-01",
                              help="Fecha de fin (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    # Crear cliente
    client = PortfolioAPIClient(args.url)
    
    # Verificar conectividad básica
    if not any([args.health, args.status, args.clear_cache]) and args.command:
        if not client.health_check():
            print("❌ No se puede conectar a la API. Verifique que el servidor esté ejecutándose.")
            sys.exit(1)
        print()
    
    result = None
    
    # Ejecutar comandos
    if args.health:
        client.health_check()
    
    elif args.status:
        result = client.get_status()
    
    elif args.clear_cache:
        result = client.clear_cache()
    
    elif args.command == "portfolio":
        result = client.analyze_portfolio(
            sentiment_url=args.sentiment_url,
            start_date=args.start_date,
            end_date=args.end_date,
            top_n_stocks=args.top_stocks,
            benchmark_ticker=args.benchmark
        )
    
    elif args.command == "stocks":
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        result = client.analyze_stocks(
            symbols=symbols,
            start_date=args.start_date,
            end_date=args.end_date
        )
    
    else:
        parser.print_help()
        sys.exit(1)
    
    # Exportar resultados si se solicita
    if args.export and result and "error" not in result:
        client.export_results(result, args.export)

if __name__ == "__main__":
    main()
