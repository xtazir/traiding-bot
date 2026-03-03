from flask import Flask, render_template_string
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
import warnings
import time
import os
import requests
import threading

warnings.filterwarnings('ignore')

# ---------------- KONFIGURACJA ----------------
SYMBOL = 'PAXG/USDT'  # Wracamy do naszego cyfrowego Złota!
TIMEFRAME = '1m'      
REFRESH_RATE = 5      

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

app = Flask(__name__)

# SILNIK BINANCE - działa dzięki holenderskiemu IP!
exchange = ccxt.binance({'enableRateLimit': True})

last_telegram_signal = "CZEKAJ"
app_state = {
    "current_price": "0.00", "prob_up": 50, "prob_down": 50, 
    "main_action": "CZEKAJ", "sl_str": "Brak", "tp_str": "Brak", 
    "atr_val": "0.00", "top_feature": "Brak", "exec_time": 0, 
    "macro_trend": "BRAK", "chart_html": ""
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>ORZEŁ v26 - ULTIMATE (BINANCE + CLOUD)</title>
    <meta http-equiv="refresh" content="{{ refresh_rate }}">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        :root { --bg-dark: #121418; --bg-panel: #1e222d; --border: #2b3139; --text-main: #d1d4dc; --text-muted: #787b86; --buy-color: #089981; --sell-color: #f23645; --warning: #facc15; --ai-color: #8b5cf6; --macro: #3b82f6;}
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: var(--bg-dark); color: var(--text-main); font-family: 'Roboto', sans-serif; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
        .top-bar { height: 50px; background-color: #1a1e26; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; padding: 0 20px; font-size: 0.9rem; }
        .logo { font-weight: 900; color: var(--text-main); font-size: 1.2rem; letter-spacing: 1px; }
        .logo span { color: #facc15; } 
        .status-ping { display: flex; align-items: center; gap: 8px; color: var(--buy-color); font-weight: bold; }
        .dot { height: 8px; width: 8px; background-color: var(--buy-color); border-radius: 50%; box-shadow: 0 0 8px var(--buy-color); animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        .workspace { display: grid; grid-template-columns: 280px 1fr 320px; height: calc(100vh - 50px); }
        .panel { background-color: var(--bg-panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
        .panel-right { border-right: none; border-left: 1px solid var(--border); }
        .panel-header { padding: 15px; border-bottom: 1px solid var(--border); font-weight: 700; font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
        .panel-content { padding: 15px; overflow-y: auto; }
        .telemetry-item { margin-bottom: 20px; }
        .tel-label { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 5px; text-transform: uppercase; }
        .tel-value { font-size: 1.1rem; font-weight: 700; }
        .ai-bar-container { background: var(--bg-dark); height: 8px; border-radius: 4px; overflow: hidden; display: flex; margin-top: 8px; }
        .ai-up { background: var(--buy-color); height: 100%; transition: width 0.3s; }
        .ai-down { background: var(--sell-color); height: 100%; transition: width 0.3s; }
        .feature-box { background: rgba(139, 92, 246, 0.1); border-left: 3px solid var(--ai-color); padding: 10px; font-size: 0.85rem; border-radius: 0 4px 4px 0; margin-top: 20px; line-height: 1.4; }
        .chart-area { background-color: var(--bg-dark); position: relative; width: 100%; height: 100%; }
        .market-price { text-align: center; margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
        .market-symbol { font-size: 1.5rem; font-weight: 900; margin-bottom: 5px; color: #facc15; }
        .market-value { font-size: 2.5rem; font-weight: 700; color: #fff; }
        .order-action { text-align: center; margin-bottom: 20px; }
        .status-badge { display: inline-block; padding: 6px 12px; border-radius: 4px; font-weight: 900; font-size: 1.2rem; letter-spacing: 1px; }
        .badge-KUP { background: rgba(8, 153, 129, 0.2); color: var(--buy-color); border: 1px solid var(--buy-color); }
        .badge-SPRZEDAJ { background: rgba(242, 54, 69, 0.2); color: var(--sell-color); border: 1px solid var(--sell-color); }
        .badge-CZEKAJ { background: rgba(120, 123, 134, 0.2); color: var(--text-muted); border: 1px solid var(--text-muted); }
        .risk-params { background: var(--bg-dark); border-radius: 6px; padding: 15px; border: 1px solid var(--border); }
        .risk-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border); }
        .risk-row:last-child { border-bottom: none; padding-bottom: 0; }
        .risk-label { font-size: 0.85rem; color: var(--text-muted); font-weight: 700; }
        .risk-val { font-size: 1.2rem; font-weight: 900; font-family: monospace; }
        .val-sl { color: var(--sell-color); }
        .val-tp { color: var(--buy-color); }
    </style>
</head>
<body>
    <div id="content" style="height: 100%; width: 100%; display: flex; flex-direction: column;">
        <div class="top-bar">
            <div class="logo">ORZEŁ <span>v26 ULTIMATE</span></div>
            <div class="status-ping"><div class="dot"></div> Binance Feed | ML Execution: {{ exec_time }}ms</div>
        </div>
        <div class="workspace">
            <div class="panel">
                <div class="panel-header">Diagnostyka Modelu (ML)</div>
                <div class="panel-content">
                    <div class="telemetry-item">
                        <div class="tel-label">Pewność Wzrostu (UP)</div>
                        <div class="tel-value" style="color: var(--buy-color);">{{ prob_up }}%</div>
                        <div class="ai-bar-container"><div class="ai-up" style="width: {{ prob_up }}%;"></div></div>
                    </div>
                    <div class="telemetry-item">
                        <div class="tel-label">Pewność Spadku (DOWN)</div>
                        <div class="tel-value" style="color: var(--sell-color);">{{ prob_down }}%</div>
                        <div class="ai-bar-container"><div class="ai-down" style="width: {{ prob_down }}%; float: right;"></div></div>
                    </div>
                    <div class="feature-box">
                        <strong>Główny czynnik:</strong><br>
                        <span style="color: #fff;">{{ top_feature }}</span>
                    </div>
                    <div class="feature-box" style="border-left-color: var(--macro); background: rgba(59, 130, 246, 0.1);">
                        <strong>Filtr Makro (Trend 15m):</strong><br>
                        <span style="color: {{ 'var(--buy-color)' if macro_trend == 'WZROSTOWY' else 'var(--sell-color)' }};">{{ macro_trend }}</span>
                    </div>
                </div>
            </div>
            <div class="chart-area">
                {{ chart_html | safe }}
            </div>
            <div class="panel panel-right">
                <div class="panel-header">Terminal Zleceń</div>
                <div class="panel-content">
                    <div class="market-price">
                        <div class="market-symbol">PAXG/USDT (ZŁOTO)</div>
                        <div class="market-value">{{ current_price }}</div>
                    </div>
                    <div class="order-action">
                        <div class="status-badge badge-{{ main_action }}">{{ main_action }}</div>
                    </div>
                    <div class="risk-params">
                        <div class="risk-row"><span class="risk-label">ZASIĘG SL</span><span class="risk-val val-sl">{{ sl_str }} USD</span></div>
                        <div class="risk-row"><span class="risk-label">ZASIĘG TP</span><span class="risk-val val-tp">{{ tp_str }} USD</span></div>
                        <div class="risk-row"><span class="risk-label">ZMIENNOŚĆ (ATR)</span><span class="risk-val" style="color: var(--warning);">{{ atr_val }} USD</span></div>
                    </div>
                    <div style="margin-top: 15px; font-size: 0.8rem; color: var(--text-muted); text-align: center;">
                        👉 Dane: Binance | Server: EU
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

def send_telegram_photo(caption, photo_path="chart.png"):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as photo:
            payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            files = {"photo": photo}
            requests.post(url, data=payload, files=files, timeout=10)
    except Exception as e:
        print(f"Błąd wysyłania zdjęcia: {e}")

def send_telegram_message(text):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def compute_indicators(df):
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_300'] = df['close'].ewm(span=300, adjust=False).mean()
    df['Dist_EMA300'] = (df['close'] - df['EMA_300']) / df['close'] * 100
    df['Dist_EMA20'] = (df['close'] - df['EMA_20']) / df['close'] * 100
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = np.abs(df['high'] - df['close'].shift(1))
    df['tr3'] = np.abs(df['low'] - df['close'].shift(1))
    df['ATR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1).rolling(window=14).mean()
    return df

def fetch_and_train_ai():
    start_time = time.time()
    try:
        # Pobieranie danych z Binance!
        bars = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=1000)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

        df = compute_indicators(df)
        df.dropna(inplace=True)

        df['Target'] = (df['close'].shift(-3) > df['close']).astype(int)
        train_df = df[:-3].copy()
        current_candle = df.iloc[-1:].copy()

        features = ['Dist_EMA20', 'RSI', 'ATR', 'Dist_EMA300']
        feature_names = {'Dist_EMA20': 'Odchylenie (EMA20)', 'RSI': 'Siła relatywna (RSI)', 'ATR': 'Zmienność (ATR)', 'Dist_EMA300': 'Trend (EMA 300)'}
        
        X_train = train_df[features]
        y_train = train_df['Target']
        
        model = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', n_jobs=-1, random_state=42)
        model.fit(X_train, y_train)
        
        importances = model.feature_importances_
        top_feature_name = feature_names[features[np.argmax(importances)]]

        prediction_probs = model.predict_proba(current_candle[features])[0] 
        prob_down = round(prediction_probs[0] * 100, 1)
        prob_up = round(prediction_probs[1] * 100, 1)
        
        exec_time = int((time.time() - start_time) * 1000)
        macro_trend = "WZROSTOWY" if current_candle['Dist_EMA300'].iloc[0] > 0 else "SPADKOWY"
        
        return df, prob_up, prob_down, top_feature_name, exec_time, macro_trend
    except Exception as e:
        print(f"Błąd analizy danych Binance: {e}")
        return pd.DataFrame(), 50, 50, "Błąd", 0, "BRAK"

def build_figure(df):
    df_plot = df.tail(100)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.8, 0.2])
    fig.add_trace(go.Candlestick(x=df_plot['datetime'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'], increasing_line_color='#089981', decreasing_line_color='#f23645'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['datetime'], y=df_plot['EMA_20'], line=dict(color='#facc15', width=1.5), name="EMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['datetime'], y=df_plot['EMA_300'], line=dict(color='#3b82f6', width=2.5), name="Trend 15m"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_plot['datetime'], y=df_plot['RSI'], line=dict(color='#8b5cf6', width=1.5), name="RSI"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", row=2, col=1, line_color="#f23645")
    fig.add_hline(y=30, line_dash="dot", row=2, col=1, line_color="#089981")
    fig.update_layout(template='plotly_dark', paper_bgcolor='#121418', plot_bgcolor='#121418', margin=dict(l=10, r=10, t=10, b=10), autosize=True, xaxis_rangeslider_visible=False, showlegend=False)
    return fig

def background_scanner():
    global last_telegram_signal, app_state
    print("☁️ Rozpoczynam skanowanie Binance PAXG w tle...")
    send_telegram_message("☁️ <b>Złoty Orzeł v26 uruchomiony!</b>\nŹródło: Binance (Serwer EU) 🇪🇺\nWykresy zsynchronizowane. Oczekuję na wejście...")

    while True:
        df, prob_up, prob_down, top_feature, exec_time, macro_trend = fetch_and_train_ai()
        if not df.empty:
            current_price = df['close'].iloc[-1]
            atr_val = df['ATR'].iloc[-1]
            main_action = "CZEKAJ"
            sl_dist, tp_dist = 0.0, 0.0
            CONFIDENCE_THRESHOLD = 65.0 

            if prob_up >= CONFIDENCE_THRESHOLD and macro_trend == "WZROSTOWY":
                main_action = "KUP"
                sl_dist, tp_dist = atr_val * 1.5, atr_val * 2.5
            elif prob_down >= CONFIDENCE_THRESHOLD and macro_trend == "SPADKOWY":
                main_action = "SPRZEDAJ"
                sl_dist, tp_dist = atr_val * 1.5, atr_val * 2.5

            sl_str, tp_str = "Brak", "Brak"
            if main_action == "KUP": sl_str, tp_str = f"-{sl_dist:.2f}", f"+{tp_dist:.2f}"
            elif main_action == "SPRZEDAJ": sl_str, tp_str = f"+{sl_dist:.2f}", f"-{tp_dist:.2f}"

            if main_action in ["KUP", "SPRZEDAJ"] and main_action != last_telegram_signal:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Wysyłanie wykresu na Telegram...")
                fig = build_figure(df)
                fig.write_image("chart.png", width=1000, height=600, scale=1)
                
                kolor = "🟢" if main_action == "KUP" else "🔴"
                akcja_xtb = "Odejmij SL, Dodaj TP" if main_action == "KUP" else "Dodaj SL, Odejmij TP"
                wiadomosc = f"{kolor} <b>SYGNAŁ ZŁOTO: {main_action}</b>\n\n🛡️ <b>Zasięg SL:</b> {sl_str} USD\n💰 <b>Zasięg TP:</b> {tp_str} USD\n〰️ ATR: {atr_val:.2f} USD\n\n👉 XTB: {akcja_xtb}"
                
                send_telegram_photo(wiadomosc, "chart.png")
                last_telegram_signal = main_action
            
            elif main_action == "CZEKAJ":
                last_telegram_signal = "CZEKAJ"

            fig = build_figure(df)
            app_state.update({
                "current_price": f"{current_price:.2f}", "prob_up": prob_up, "prob_down": prob_down,
                "main_action": main_action, "sl_str": sl_str, "tp_str": tp_str, "atr_val": f"{atr_val:.2f}", 
                "top_feature": top_feature, "exec_time": exec_time, "macro_trend": macro_trend,
                "chart_html": pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
            })
            
        time.sleep(REFRESH_RATE)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, refresh_rate=REFRESH_RATE, **app_state)

if __name__ == '__main__':
    threading.Thread(target=background_scanner, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
