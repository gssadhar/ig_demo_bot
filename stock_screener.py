import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import yfinance as yf

# Environment Variables from GitHub Secrets
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "g_lally@yahoo.co.uk")

# Diversified Universe across US, UK, Global Large/Mid/Small Caps & Sectors
SCREEN_UNIVERSE = [
    # US Tech & Growth
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AMD", "AVGO",
    # UK / European Large Caps
    "RR.L", "GLEN.L", "AZN.L", "SHEL.L", "GSK.L", "HSBC.L", "ULVR.L", "BP.L",
    # Global Industrials, Financials & Consumer
    "JPM", "BAC", "CAT", "GE", "PG", "KO", "COST", "TSLA",
    # Mid & Small Caps / Emerging Growth
    "CROX", "DUOL", "ELF", "CELH", "WING", "BOOT", "NIO", "ALTR"
]


def calculate_atr(df, period=14):
    """Calculates Average True Range (14-day) for volatility-adjusted stop losses."""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return float(tr.rolling(window=period).mean().iloc[-1])


def screen_stock_in_depth(symbol):
    try:
        ticker_obj = yf.Ticker(symbol)
        df = ticker_obj.history(period="1y", interval="1d")

        if len(df) < 200:
            return None

        # Calculate 14-day ATR for dynamic stop-loss distance
        atr_val = calculate_atr(df, period=14)
        
        # Convert ATR to points (handles London GBp vs USD pricing)
        curr_price = float(df["Close"].iloc[-1])
        if ".L" in symbol:
            # London stocks in yfinance are pence; convert to point distance
            atr_pts = round(atr_val, 1)
        else:
            atr_pts = round(atr_val, 2)
            
        # Guarantee a safe minimum stop distance floor
        final_atr_pts = max(atr_pts, 15.0)

        # Fetch Fundamentals safely
        try:
            info = ticker_obj.info
            pe_ratio = info.get("forwardPE", info.get("trailingPE", None))
            peg_ratio = info.get("pegRatio", None)
            sector = info.get("sector", "N/A")
            roe = info.get("returnOnEquity", None)
            debt_to_equity = info.get("debtToEquity", None)
            target_price = info.get("targetMeanPrice", None)
        except Exception:
            pe_ratio, peg_ratio, sector, roe, debt_to_equity, target_price = None, None, "N/A", None, None, None

        # Technical Indicators
        df["SMA_20"] = df["Close"].rolling(20).mean()
        df["SMA_50"] = df["Close"].rolling(50).mean()
        df["SMA_200"] = df["Close"].rolling(200).mean()

        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

        latest = df.iloc[-1]

        uptrend = bool(curr_price > latest["SMA_200"])
        golden_cross = bool(latest["SMA_50"] > latest["SMA_200"])
        macd_bull = bool(latest["MACD"] > latest["Signal"])
        rsi_val = float(latest["RSI"])

        # Conviction Score Engine (0 to 100 scale)
        conviction_score = 40  # Base line
        if uptrend: conviction_score += 15
        if golden_cross: conviction_score += 15
        if macd_bull: conviction_score += 10
        if 40 <= rsi_val <= 65: conviction_score += 10
        if roe and roe > 0.15: conviction_score += 10
        if peg_ratio and 0.5 <= peg_ratio <= 1.5: conviction_score += 10

        # Analyst Upside Calculation
        upside_str = "N/A"
        if target_price and curr_price > 0:
            upside_pct = ((target_price - curr_price) / curr_price) * 100
            upside_str = f"{upside_pct:+.1f}%"

        # Signal Classification based on Conviction Score
        if conviction_score >= 80:
            signal = "STRONG BUY"
            badge_color = "#10B981"
            rationale = f"Score {conviction_score}/100: Strong Trend + High ROE/Fair Valuation"
        elif conviction_score >= 65:
            signal = "BUY"
            badge_color = "#3B82F6"
            rationale = f"Score {conviction_score}/100: Bullish Trend & Positive Momentum"
        elif conviction_score <= 40:
            signal = "SELL / AVOID"
            badge_color = "#EF4444"
            rationale = f"Score {conviction_score}/100: Weak Structure / Downtrend Momentum"
        else:
            signal = "HOLD"
            badge_color = "#F59E0B"
            rationale = f"Score {conviction_score}/100: Neutral / Consolidation Phase"

        return {
            "Ticker": symbol,
            "Sector": sector,
            "Price": f"{curr_price:.2f}",
            "Signal": signal,
            "ConvictionScore": conviction_score,
            "BadgeColor": badge_color,
            "Rationale": rationale,
            "Analyst Upside": upside_str,
            "RSI": round(rsi_val, 1),
            "ROE": f"{roe*100:.1f}%" if roe else "N/A",
            "ATR_Points": final_atr_pts,
            "TradingView": f"https://www.tradingview.com/symbols/{symbol}/",
            "YahooFinance": f"https://finance.yahoo.com/quote/{symbol}/key-statistics"
        }
    except Exception as e:
        print(f"Skipping {symbol} due to processing error: {e}")
        return None


def build_html_report(data_list):
    cards_html = ""
    if not data_list:
        cards_html = "<p style='text-align:center; color:#6b7280;'>No stocks evaluated today or market data unavailable.</p>"
    else:
        for item in data_list:
            cards_html += f"""
            <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f3f4f6; padding-bottom: 10px; margin-bottom: 12px;">
                    <div>
                        <span style="font-size: 20px; font-weight: bold; color: #111827;">{item['Ticker']}</span>
                        <span style="font-size: 12px; color: #6b7280; margin-left: 8px;">{item['Sector']}</span>
                    </div>
                    <div>
                        <span style="background-color: {item['BadgeColor']}; color: #ffffff; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px;">{item['Signal']}</span>
                    </div>
                </div>
                <div style="font-size: 14px; color: #374151; margin-bottom: 12px;">
                    <strong>Rationale:</strong> {item['Rationale']}
                </div>
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; background: #f9fafb; padding: 10px; border-radius: 6px; font-size: 12px; text-align: center;">
                    <div><span style="color: #6b7280; display: block; font-size: 10px;">PRICE</span> <strong>{item['Price']}</strong></div>
                    <div><span style="color: #6b7280; display: block; font-size: 10px;">UPSIDE</span> <strong>{item['Analyst Upside']}</strong></div>
                    <div><span style="color: #6b7280; display: block; font-size: 10px;">RSI (14)</span> <strong>{item['RSI']}</strong></div>
                    <div><span style="color: #6b7280; display: block; font-size: 10px;">ROE</span> <strong>{item['ROE']}</strong></div>
                    <div><span style="color: #6b7280; display: block; font-size: 10px;">14-ATR PTS</span> <strong>{item['ATR_Points']}</strong></div>
                </div>
                <div style="margin-top: 14px; font-size: 12px; text-align: right;">
                    <a href="{item['TradingView']}" target="_blank" style="color: #2563eb; text-decoration: none; margin-right: 12px; font-weight: bold;">📈 TradingView Chart &rarr;</a>
                    <a href="{item['YahooFinance']}" target="_blank" style="color: #4b5563; text-decoration: none; font-weight: bold;">🔍 Yahoo Financials &rarr;</a>
                </div>
            </div>
            """

    return f"""
    <!DOCTYPE html>
    <html>
      <head><meta charset="utf-8"></head>
      <body style="font-family: Arial, sans-serif; background-color: #f3f4f6; padding: 20px; margin: 0;">
        <div style="max-width: 680px; margin: 0 auto;">
            <div style="background: #1e293b; color: #ffffff; padding: 24px; border-radius: 8px 8px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 22px;">GLOBAL EQUITY BRIEFING</h1>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">Automated Quantitative Screener & Volatility Signal Report</p>
            </div>
            <div style="padding: 20px 0;">{cards_html}</div>
        </div>
      </body>
    </html>
    """


def send_email_alert(html_body, candidate_count):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("SENDER_EMAIL or SENDER_PASSWORD secret missing. Skipping email send.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 INSTITUTIONAL EQUITY BRIEFING ({candidate_count} Equities Evaluated)"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print(f"-> Email successfully sent to {RECEIVER_EMAIL}!")
    except Exception as e:
        print(f"Failed to send email: {e}")


def run_screener():
    print("=== RUNNING GLOBAL HYBRID STOCK SCREENER ===")
    results = []

    for ticker in SCREEN_UNIVERSE:
        candidate = screen_stock_in_depth(ticker)
        if candidate:
            results.append(candidate)

    # 1. Filter out candidate setup list for the IG Trading Bot
    top_buys = [item for item in results if item["Signal"] in ["STRONG BUY", "BUY"]]

    # 2. Save JSON candidate file for trading_bot_ig.py to consume
    with open("top_candidates.json", "w", encoding="utf-8") as f:
        json.dump(top_buys, f, indent=4)
    print(f"-> Saved {len(top_buys)} top buy setup candidates to top_candidates.json!")

    # 3. Build HTML Report & Save Locally for GitHub Pages
    html_content = build_html_report(results)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("-> Successfully generated index.html!")

    # 4. Send Email Briefing Alert
    send_email_alert(html_content, len(results))


if __name__ == "__main__":
    run_screener()
