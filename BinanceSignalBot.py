
import requests
import time
import datetime
import pytz
import numpy as np
import telegram

# --- 사용자 설정 ---
TELEGRAM_TOKEN = "8027865821:AAHsX1wOaH2MFHetZRqg65aNWv9JDqSdIvo"
TELEGRAM_CHAT_ID = "5888953708"

# --- 초기 설정 ---
binance_url = "https://api.binance.com"
session = requests.Session()
kst = pytz.timezone("Asia/Seoul")

# 텔레그램 알림 함수
def send_telegram_message(message):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# RSI 계산 함수
def calculate_rsi(closes, period=14):
    deltas = np.diff(closes)
    ups = deltas.clip(min=0)
    downs = -deltas.clip(max=0)
    ma_up = np.convolve(ups, np.ones(period), 'valid') / period
    ma_down = np.convolve(downs, np.ones(period), 'valid') / period
    rs = ma_up / (ma_down + 1e-6)
    rsi = 100 - (100 / (1 + rs))
    return np.concatenate((np.full(period, np.nan), rsi))

# 바이낸스에서 USDT 마켓 코인 리스트 가져오기
def get_usdt_symbols():
    res = session.get(f"{binance_url}/api/v3/exchangeInfo")
    symbols = []
    for s in res.json()["symbols"]:
        if s["quoteAsset"] == "USDT" and s["status"] == "TRADING" and not s["isMarginTradingAllowed"]:
            symbols.append(s["symbol"])
    return symbols

# 일봉 데이터 가져오기
def get_ohlcv(symbol):
    url = f"{binance_url}/api/v3/klines?symbol={symbol}&interval=1d&limit=21"
    res = session.get(url)
    data = res.json()
    if not data or len(data) < 15:
        return None
    return np.array(data, dtype=float)

# 조건 판단
def check_signal(symbol, data):
    closes = data[:, 4]
    opens = data[:, 1]
    highs = data[:, 2]
    lows = data[:, 3]
    volumes = data[:, 5]
    rsi = calculate_rsi(closes)

    # 전날 봉
    close = closes[-2]
    open_ = opens[-2]
    high = highs[-2]
    low = lows[-2]
    volume = volumes[-2]
    vol_avg = np.mean(volumes[-21:-1])
    rsi_val = rsi[-2]

    body = close - open_
    upper_wick = high - max(close, open_)
    lower_wick = min(close, open_) - low
    candle_range = high - low
    is_bull = close > open_
    is_bear = close < open_

    buy_cond = (
        rsi_val < 35 and
        volume > vol_avg * 1.5 and
        is_bull and
        lower_wick > candle_range * 0.3
    )

    sell_cond = (
        rsi_val > 70 and
        volume > vol_avg * 1.5 and
        is_bear and
        upper_wick > candle_range * 0.3
    )

    return buy_cond, sell_cond, rsi_val

# 메인 실행 함수
def run():
    now = datetime.datetime.now(kst)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 시그널 체크 시작")

    symbols = get_usdt_symbols()
    print(f"총 {len(symbols)}개 코인 분석 중...")

    for symbol in symbols:
        try:
            data = get_ohlcv(symbol)
            if data is None:
                continue

            buy, sell, rsi_val = check_signal(symbol, data)

            if buy:
                msg = f"[매수 시그널 발생]\n코인: {symbol}\nRSI: {rsi_val:.2f}\n조건: 거래량 급증 + RSI 저점 + 양봉 + 아래꼬리\n시간: {now.strftime('%Y-%m-%d')}"
                send_telegram_message(msg)

            if sell:
                msg = f"[매도 시그널 발생]\n코인: {symbol}\nRSI: {rsi_val:.2f}\n조건: 거래량 급증 + RSI 고점 + 음봉 + 위꼬리\n시간: {now.strftime('%Y-%m-%d')}"
                send_telegram_message(msg)

        except Exception as e:
            print(f"{symbol} 분석 중 오류 발생: {e}")
            continue

    print("시그널 체크 완료")

# 매일 오전 9시에 실행되도록 대기
def wait_until_9am():
    while True:
        now = datetime.datetime.now(kst)
        if now.hour == 9 and now.minute == 0:
            run()
            time.sleep(60)  # 1분 대기 (중복 실행 방지)
        time.sleep(10)

if __name__ == "__main__":
    wait_until_9am()
