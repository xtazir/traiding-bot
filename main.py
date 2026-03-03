import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import warnings
import time
import requests
from datetime import datetime

warnings.filterwarnings('ignore')

# ---------------- KONFIGURACJA BOTA ----------------
SYMBOL = 'PAXG/USDT'
TIMEFRAME = '1m'
REFRESH_RATE = 5

# --- TELEGRAM KONFIGURACJA (UZUPEŁNIJ!) ---
TELEGRAM_TOKEN = '8561391555:AAF9hik7Wz0L6GwDyzNoGGnRT-SW-dUfhoc'
TELEGRAM_CHAT_ID = '-1003750371593'
# ---------------------------------------------------

exchange = ccxt.binance({'enableRateLimit': True})
last_telegram_signal = "CZEKAJ"


def send_telegram_message(text):
    if TELEGRAM_TOKEN == 'TWÓJ_TOKEN_BOTA' or TELEGRAM_CHAT_ID == 'TWÓJ_CHAT_ID':
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print(f"Błąd komunikacji z Telegramem: {e}")


def compute_indicators(df):
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_300'] = df['close'].ewm(span=300, adjust=False).mean()
    df['Dist_EMA300'] = (df['close'] - df['EMA_300']) / df['close'] * 100
    df['Dist_EMA20'] = (df['close'] - df['EMA_20']) / df['close'] * 100

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['tr1'] = df['high'] - df['low']
    df['tr2'] = np.abs(df['high'] - df['close'].shift(1))
    df['tr3'] = np.abs(df['low'] - df['close'].shift(1))
    df['ATR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1).rolling(window=14).mean()
    return df


def fetch_and_evaluate():
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=1000)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df = compute_indicators(df)
        df.dropna(inplace=True)

        df['Target'] = (df['close'].shift(-3) > df['close']).astype(int)
        train_df = df[:-3].copy()
        current_candle = df.iloc[-1:].copy()

        features = ['Dist_EMA20', 'RSI', 'ATR', 'Dist_EMA300']
        model = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', n_jobs=-1,
                                       random_state=42)
        model.fit(train_df[features], train_df['Target'])

        prediction_probs = model.predict_proba(current_candle[features])[0]
        prob_up = round(prediction_probs[1] * 100, 1)
        prob_down = round(prediction_probs[0] * 100, 1)
        macro_trend = "WZROSTOWY" if current_candle['Dist_EMA300'].iloc[0] > 0 else "SPADKOWY"
        atr_val = current_candle['ATR'].iloc[0]

        return prob_up, prob_down, macro_trend, atr_val
    except Exception as e:
        print(f"Błąd pobierania danych: {e}")
        return 50, 50, "BRAK", 0


def main():
    global last_telegram_signal
    print("🦅 ZŁOTY ORZEŁ v21.0 (SILNIK W TLE) URUCHOMIONY!")
    print("Sygnały są wysyłane bezpośrednio na Telegram.")
    print("Nie musisz otwierać przeglądarki. Możesz zminimalizować to okno.")
    print("-" * 50)

    send_telegram_message("🦅 <b>Złoty Orzeł v21.0 pomyślnie uruchomiony w tle!</b>\nNasłuchuję rynku...")

    while True:
        prob_up, prob_down, macro_trend, atr_val = fetch_and_evaluate()

        main_action = "CZEKAJ"
        CONFIDENCE_THRESHOLD = 65.0

        if prob_up >= CONFIDENCE_THRESHOLD and macro_trend == "WZROSTOWY":
            main_action = "KUP"
        elif prob_down >= CONFIDENCE_THRESHOLD and macro_trend == "SPADKOWY":
            main_action = "SPRZEDAJ"

        if main_action in ["KUP", "SPRZEDAJ"] and main_action != last_telegram_signal:
            sl_dist = atr_val * 1.5
            tp_dist = atr_val * 2.5

            sl_str = f"-{sl_dist:.2f}" if main_action == "KUP" else f"+{sl_dist:.2f}"
            tp_str = f"+{tp_dist:.2f}" if main_action == "KUP" else f"-{tp_dist:.2f}"
            kolor = "🟢" if main_action == "KUP" else "🔴"
            akcja_xtb = "Odejmij SL, Dodaj TP" if main_action == "KUP" else "Dodaj SL, Odejmij TP"

            wiadomosc = f"{kolor} <b>SYGNAŁ ZŁOTO: {main_action}</b>\n\n" \
                        f"🛡️ <b>Zasięg SL:</b> {sl_str} USD\n" \
                        f"💰 <b>Zasięg TP:</b> {tp_str} USD\n" \
                        f"〰️ Zmienność (ATR): {atr_val:.2f} USD\n\n" \
                        f"👉 XTB: {akcja_xtb}"

            send_telegram_message(wiadomosc)
            last_telegram_signal = main_action
            print(f"[{datetime.now().strftime('%H:%M:%S')}] WYSŁANO SYGNAŁ: {main_action}")

        elif main_action == "CZEKAJ":
            if last_telegram_signal != "CZEKAJ":
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Oczekiwanie na sygnał...")
            last_telegram_signal = "CZEKAJ"

        # Czekamy 5 sekund przed kolejnym skanowaniem rynku
        time.sleep(REFRESH_RATE)


if __name__ == '__main__':
    main()