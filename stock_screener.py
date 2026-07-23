import os
import json
import smtplib
import pandas as pd
import yfinance as yf
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Environment Variables
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Cleaned Watchlist (Valid Active Yahoo Tickers)
WATCHLIST = [
    {"ticker": "AAPL", "sector": "Technology"},
    {"ticker": "MSFT", "sector": "Technology"},
    {"ticker": "GOOGL", "sector": "Communication Services"},
    {"ticker": "AMZN", "sector": "Consumer Cyclical"},
    {"ticker": "NVDA", "sector": "Technology"},
    {"ticker": "META", "sector": "Communication Services"},
    {"ticker": "AMD", "sector": "Technology"},
    {"ticker": "AVGO", "sector": "Technology"},
    {"ticker": "JPM", "sector": "Financial Services"},
    {"ticker": "BAC", "sector": "Financial Services"},
    {"ticker": "CAT", "sector": "Industrials"},
    {"ticker": "GE", "sector": "Industrials"},
    {"ticker": "KO", "sector": "Consumer Defensive"},
    {"ticker": "COST", "sector": "Consumer Defensive"},
    {"ticker": "CROX", "sector": "Consumer Cyclical"},
    {"ticker": "RR.L", "sector": "Industrials"},
    {"ticker": "GLEN.L", "sector": "Basic Materials"},
    {"ticker": "SHEL.L", "sector": "Energy"},
    {"ticker": "GSK.L", "sector": "Healthcare"},
    {"ticker": "BP.L", "sector": "Energy"},
    {"ticker": "HSBA.L", "sector": "Financial Services"}
]


def calculate_technical_signal(ticker_symbol):
    try:
        df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        sma_20 = close.rolling(20).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        current_price = close.iloc[-1]

        # Calculate ATR
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_value = tr.rolling(14).mean().iloc[-1]

        atr_points = max(int(round(atr_value * 100)), 15) if ticker_symbol.endswith(".L") else max(int(round(atr_value)), 15)

        signal = "HOLD"
        if current_price > sma_20 and sma_20 > sma_50:
            signal = "STRONG BUY"
        elif current_price > sma_20:
            signal = "BUY"
        elif current_price < sma_20 and sma_20 < sma_50:
            signal = "SELL"

        return {
            "Price": round(float(current_price), 2),
            "Signal": signal,
            "ATR_Points": atr_points
        }
    except Exception as e:
        print(f"⏩ Skipping {ticker_symbol}: {e}")
        return None


def build_html_report(candidates):
    rows = ""
    for c in candidates:
        badge_color = "#28a745" if c["Signal"] == "STRONG BUY" else "#17a2b8"
        rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;"><b>{c['Ticker']}</b></td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{c['Sector']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">${c['Price']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;"><span style="background-color: {badge_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">{c['Signal']}</span></td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{c['ATR_Points']} pts</td>
        </tr>
        """
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f9; padding: 20px;">
        <div style="max-width: 700px; margin: auto; background: white; padding: 20px; border-radius: 8px;">
            <h2 style="color: #333;">📈 Daily Market Screener Candidates</h2>
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 10px; border-bottom: 2px solid #ddd;">Ticker</th>
                        <th style="padding: 10px; border-bottom: 2px solid #ddd;">Sector</th>
                        <th style="padding: 10px; border-bottom: 2px solid #ddd;">Price</th>
                        <th style="padding: 10px; border-bottom: 2px solid #ddd;">Signal</th>
                        <th style="padding: 10px; border-bottom: 2px solid #ddd;">Stop Distance</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """


def send_email(html_content):
    if not all([SENDER_EMAIL, RECEIVER_EMAIL, SMTP_PASSWORD]):
        print("ℹ️ Email credentials missing. Skipping email dispatch.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚀 Daily Market Screener - Candidates"
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"-> Email successfully sent to {RECEIVER_EMAIL}!")
    except Exception as e:
        print(f"⚠️ Email dispatch error: {e}")


def run_screener():
    print("=== RUNNING GLOBAL HYBRID STOCK SCREENER ===")
    candidates = []

    for item in WATCHLIST:
        ticker = item["ticker"]
        sector = item["sector"]

        metrics = calculate_technical_signal(ticker)
        if not metrics:
            continue

        if metrics["Signal"] in ["BUY", "STRONG BUY"]:
            candidates.append({
                "Ticker": ticker,
                "Sector": sector,
                "Price": metrics["Price"],
                "Signal": metrics["Signal"],
                "ATR_Points": metrics["ATR_Points"]
            })

    with open("top_candidates.json", "w") as f:
        json.dump(candidates, f, indent=4)
    print(f"-> Saved {len(candidates)} top buy setup candidates to top_candidates.json!")

    html_report = build_html_report(candidates)
    with open("index.html", "w") as f:
        f.write(html_report)
    print("-> Successfully generated index.html!")

    send_email(html_report)


if __name__ == "__main__":
    run_screener()
