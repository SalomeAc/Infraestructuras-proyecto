"""
Cliente web para la API de optimización de portafolios
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
import json
import time

# Configuración de la página
st.set_page_config(
    page_title="Portfolio Optimizer", 
    page_icon="📈",
    layout="wide"
)

# Variables de configuración
try:
    API_BASE_URL = st.secrets.get("API_URL", "http://localhost:8000")
except Exception:
    # Si no hay archivo de secretos, usar valor por defecto
    API_BASE_URL = "http://localhost:8000"

def make_api_request(endpoint: str, method: str = "GET", data: dict = None):
    """Realizar petición a la API"""
    url = f"{API_BASE_URL}{endpoint}"
    
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
        st.error("⏱️ Timeout: La petición tardó demasiado tiempo")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"🔌 Error de conexión: No se puede conectar a {API_BASE_URL}")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error HTTP {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"🚫 Error inesperado: {str(e)}")
        return None

def plot_performance_comparison(data):
    """Graficar comparación de performance"""
    dates = pd.to_datetime(data['dates'])
    portfolio_returns = data['portfolio_cumulative_returns']
    benchmark_returns = data['benchmark_cumulative_returns']
    
    fig = go.Figure()
    
    # Línea del portafolio
    fig.add_trace(go.Scatter(
        x=dates,
        y=[r * 100 for r in portfolio_returns],
        mode='lines',
        name='Portafolio (Sentiment Strategy)',
        line=dict(color='#1f77b4', width=3)
    ))
    
    # Línea del benchmark
    fig.add_trace(go.Scatter(
        x=dates,
        y=[r * 100 for r in benchmark_returns],
        mode='lines',
        name='Benchmark (QQQ)',
        line=dict(color='#ff7f0e', width=2)
    ))
    
    fig.update_layout(
        title="Comparación de Performance: Portafolio vs Benchmark",
        xaxis_title="Fecha",
        yaxis_title="Retorno Acumulativo (%)",
        hovermode='x unified',
        template="plotly_white",
        height=500
    )
    
    return fig

def show_portfolio_composition(composition_data):
    """Mostrar composición del portafolio"""
    if not composition_data:
        st.warning("No hay datos de composición disponibles")
        return
    
    # Crear DataFrame para análisis
    comp_list = []
    for date, stocks in composition_data.items():
        for stock in stocks:
            comp_list.append({"Fecha": date, "Stock": stock})
    
    if comp_list:
        comp_df = pd.DataFrame(comp_list)
        
        # Contar frecuencia de stocks
        stock_counts = comp_df['Stock'].value_counts()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Stocks más frecuentes")
            for i, (stock, count) in enumerate(stock_counts.head(10).items()):
                st.write(f"{i+1}. **{stock}**: {count} meses")
        
        with col2:
            st.subheader("📅 Composición por fecha")
            for date in sorted(composition_data.keys())[-5:]:  # Últimas 5 fechas
                stocks = composition_data[date]
                st.write(f"**{date}**: {', '.join(stocks[:3])}{'...' if len(stocks) > 3 else ''}")

def main():
    """Función principal de la aplicación"""
    st.title("📈 Portfolio Optimization Dashboard")
    st.markdown("### ⚡ Análisis de portafolio con **Ray** para paralelización")
    st.markdown("---")
    
    # Sidebar para configuración
    st.sidebar.header("⚙️ Configuración")
    
    # Verificar estado de la API
    with st.sidebar:
        st.subheader("🔧 Estado del Sistema")
        if st.button("Verificar Estado API"):
            with st.spinner("Verificando..."):
                health_data = make_api_request("/health")
                if health_data:
                    st.success("✅ API en línea")
                    st.json(health_data)
                else:
                    st.error("❌ API no disponible")
        
        if st.button("Estado Detallado"):
            status_data = make_api_request("/status")
            if status_data:
                st.json(status_data)
        
        if st.button("Limpiar Cache"):
            result = make_api_request("/cache/clear", method="DELETE")
            if result:
                st.success(result.get("message", "Cache limpiado"))
    
    # Tabs principales
    tab1, tab2, tab3 = st.tabs(["🎯 Análisis de Portafolio", "📊 Análisis de Stocks", "📋 Información"])
    
    with tab1:
        st.header("Optimización de Portafolio con Sentiment Analysis")
        
        # Formulario de configuración
        with st.form("portfolio_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                sentiment_url = st.text_input(
                    "URL de datos de sentiment",
                    value="https://raw.githubusercontent.com/SalomeAc/Infraestructuras-proyecto/refs/heads/main/sentiment_data.csv"
                )
                start_date = st.date_input("Fecha inicio", value=date(2021, 1, 1))
                top_n_stocks = st.slider("Top N stocks por mes", 3, 10, 5)
            
            with col2:
                end_date = st.date_input("Fecha fin", value=date(2023, 3, 1))
                benchmark_ticker = st.selectbox("Benchmark", ["QQQ", "SPY", "IWM"], index=0)
            
            submitted = st.form_submit_button("🚀 Ejecutar Análisis", type="primary")
        
        if submitted:
            # Preparar datos de la petición
            request_data = {
                "sentiment_url": sentiment_url,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "top_n_stocks": top_n_stocks,
                "benchmark_ticker": benchmark_ticker
            }
            
            # Mostrar progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("Enviando petición a la API...")
            progress_bar.progress(10)
            
            # Realizar petición
            with st.spinner("Procesando análisis (esto puede tomar varios minutos)..."):
                start_time = time.time()
                result = make_api_request("/portfolio/analyze", method="POST", data=request_data)
                end_time = time.time()
                
                progress_bar.progress(100)
                status_text.text(f"Completado en {end_time - start_time:.2f} segundos")
            
            if result and result.get("status") == "success":
                st.success("✅ Análisis completado exitosamente!")
                
                # Mostrar métricas principales
                analysis = result["analysis"]
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(
                        "Retorno Total Portafolio",
                        f"{analysis['total_portfolio_return']:.2%}",
                        delta=f"{analysis['excess_return']:.2%}"
                    )
                with col2:
                    st.metric(
                        "Retorno Benchmark",
                        f"{analysis['total_benchmark_return']:.2%}"
                    )
                with col3:
                    st.metric(
                        "Volatilidad Portafolio",
                        f"{analysis['portfolio_volatility']:.2%}"
                    )
                with col4:
                    st.metric(
                        "Sharpe Ratio",
                        f"{analysis['sharpe_ratio']:.3f}"
                    )
                
                # Gráfico de performance
                st.subheader("📈 Performance Comparativa")
                fig = plot_performance_comparison(result["performance_data"])
                st.plotly_chart(fig, use_container_width=True)
                
                # Composición del portafolio
                st.subheader("📋 Composición del Portafolio")
                show_portfolio_composition(result["portfolio_composition"])
                
                # Detalles técnicos
                with st.expander("🔍 Detalles Técnicos"):
                    st.json(result["metadata"])
            
            elif result:
                st.error(f"❌ Error en el análisis: {result}")
    
    with tab2:
        st.header("Análisis Individual de Stocks")
        
        with st.form("stocks_form"):
            symbols_input = st.text_area(
                "Símbolos de stocks (separados por comas)",
                value="AAPL, MSFT, GOOGL, AMZN, TSLA",
                help="Ingrese los símbolos separados por comas"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                stock_start_date = st.date_input("Fecha inicio", value=date(2021, 1, 1), key="stock_start")
            with col2:
                stock_end_date = st.date_input("Fecha fin", value=date(2023, 3, 1), key="stock_end")
            
            analyze_stocks = st.form_submit_button("📊 Analizar Stocks")
        
        if analyze_stocks:
            symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]
            
            if symbols:
                request_data = {
                    "symbols": symbols,
                    "start_date": stock_start_date.strftime("%Y-%m-%d"),
                    "end_date": stock_end_date.strftime("%Y-%m-%d")
                }
                
                with st.spinner("Analizando stocks..."):
                    result = make_api_request("/stocks/analyze", method="POST", data=request_data)
                
                if result and result.get("status") == "success":
                    st.success(f"✅ Análisis completado para {result['stocks_analyzed']} stocks")
                    
                    # Crear DataFrame con métricas
                    metrics_data = []
                    for symbol, metrics in result["metrics"].items():
                        metrics_data.append({
                            "Stock": symbol,
                            "Retorno Total": f"{metrics['total_return']:.2%}",
                            "Volatilidad": f"{metrics['volatility']:.2%}",
                            "Sharpe Ratio": f"{metrics['sharpe_ratio']:.3f}",
                            "Datos": metrics['data_points']
                        })
                    
                    df = pd.DataFrame(metrics_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Gráfico de retorno vs volatilidad
                    if len(result["metrics"]) > 1:
                        fig = px.scatter(
                            x=[m['volatility'] for m in result["metrics"].values()],
                            y=[m['total_return'] for m in result["metrics"].values()],
                            text=list(result["metrics"].keys()),
                            labels={"x": "Volatilidad", "y": "Retorno Total"},
                            title="Retorno vs Volatilidad"
                        )
                        fig.update_traces(textposition="top center")
                        st.plotly_chart(fig, use_container_width=True)
                
                else:
                    st.error("❌ Error en el análisis de stocks")
            else:
                st.warning("⚠️ Por favor ingrese al menos un símbolo de stock")
    
    with tab3:
        st.header("📋 Información del Sistema")
        
        st.markdown("""
        ### 🎯 Características de la Aplicación
        
        Esta aplicación implementa un sistema de optimización de portafolios que utiliza:
        
        - **🔄 Ray**: Para paralelización de cálculos intensivos
        - **🚀 FastAPI**: API REST de alto rendimiento  
        - **📊 Streamlit**: Interfaz web interactiva
        - **🐳 Docker**: Containerización para despliegue
        - **☁️ AWS EC2**: Infraestructura en la nube
        
        ### ⚡ Optimizaciones de Performance
        
        1. **Descarga paralela de datos**: Los datos de stocks se descargan en lotes paralelos
        2. **Procesamiento distribuido**: Los cálculos se distribuyen usando Ray
        3. **Cache inteligente**: Resultados cached para evitar recálculos
        4. **Ray Serve**: Deployment escalable de la API
        
        ### 🔧 Endpoints de la API
        
        - `GET /`: Información general
        - `GET /health`: Health check
        - `GET /status`: Estado detallado del sistema
        - `POST /portfolio/analyze`: Análisis de portafolio
        - `POST /stocks/analyze`: Análisis de stocks individuales
        - `DELETE /cache/clear`: Limpiar cache
        """)
        
        # Información de conexión
        st.subheader("🔗 Información de Conexión")
        st.code(f"API Base URL: {API_BASE_URL}")
        
        # Test de conectividad
        if st.button("🧪 Test de Conectividad"):
            with st.spinner("Probando conexión..."):
                root_data = make_api_request("/")
                if root_data:
                    st.success("✅ Conexión exitosa")
                    st.json(root_data)
                else:
                    st.error("❌ Error de conexión")

if __name__ == "__main__":
    main()
