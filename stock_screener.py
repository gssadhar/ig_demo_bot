import os
import json
import smtplib
import pandas as pd
import yfinance as yf
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Environment Variables
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Expanded Comprehensive Global Multi-Sector Watchlist
WATCHLIST = [
    {"ticker": "MSFT", "sector": "Technology"},
    {"ticker": "GOOGL", "sector": "Communication Services"},
    {"ticker": "AMZN", "sector": "Consumer Cyclical"},
    {"ticker": "NVDA", "sector": "Technology"},
    {"ticker": "META", "sector": "Communication Services"},
    {"ticker": "AAPL", "sector": "Technology"},
    {"ticker": "AMD", "sector": "Technology"},
    {"ticker": "AVGO", "sector": "Technology"},
    {"ticker": "ORCL", "sector": "Technology"},
    {"ticker": "JPM", "sector": "Financial Services"},
    {"ticker": "BAC", "sector": "Financial Services"},
    {"ticker": "HSBA.L", "sector": "Financial Services"},
    {"ticker": "LLOY.L", "sector": "Financial Services"},
    {"ticker": "LGEN.L", "sector": "Financial Services"},
    {"ticker": "RR.L", "sector": "Industrials"},
    {"ticker": "CAT", "sector": "Industrials"},
    {"ticker": "GE", "sector": "Industrials"},
    {"ticker": "BA.L", "sector": "Industrials"},
    {"ticker": "OXIG.L", "sector": "Industrials"},
    {"ticker": "SHEL.L", "sector": "Energy"},
    {"ticker": "BP.L", "sector": "Energy"},
    {"ticker": "GLEN.L", "sector": "Basic Materials"},
    {"ticker": "TGA.JO", "sector": "Basic Materials"},
    {"ticker": "ITH.L", "sector": "Energy"},
    {"ticker": "GSK.L", "sector": "Healthcare"},
    {"ticker": "AZN.L", "sector": "Healthcare"},
    {"ticker": "DGE.L", "sector": "Consumer Defensive"},
    {"ticker": "KO", "sector": "Consumer Defensive"},
    {"ticker": "COST", "sector": "Consumer Defensive"},
    {"ticker": "WINE.L", "sector": "Consumer Cyclical"},
    {"ticker": "EZJ.L", "sector": "Consumer Cyclical"},
    {"ticker": "CROX", "sector": "Consumer Cyclical"}
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

        sma_20 = float(close.rolling(20).mean().iloc[-1])
        sma_50 = float(close.rolling(50).mean().iloc[-1])
        current_price = float(close.iloc[-1])
        
        prev_price = float(close.iloc[-20]) if len(close) >= 20 else current_price
        momentum_1m = ((current_price - prev_price) / prev_price) * 100

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_value = float(tr.rolling(14).mean().iloc[-1])

        is_uk = ticker_symbol.endswith(".L")
        if is_uk:
            atr_points = max(int(round(atr_value * 1.5 * 100)), 20)
        else:
            atr_points = max(int(round(atr_value * 1.5 * 100)), 150)

        signal = "HOLD"
        if current_price > sma_20 and sma_20 > sma_50:
            signal = "STRONG BUY"
        elif current_price > sma_20:
            signal = "BUY"
        elif current_price < sma_20 and sma_20 < sma_50:
            signal = "SELL"

        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.info
        pe_ratio = info.get("trailingPE", "N/A")

        trend_desc = "bullish structural uptrend" if current_price > sma_50 else "defensive range"
        reasoning = (
            f"Technical Analysis: Price is trading relative to the 20-period SMA ({sma_20:.2f}) and 50-period SMA ({sma_50:.2f}), "
            f"classifying the market phase as a {trend_desc}. 1-month momentum is measured at {momentum_1m:.2f}%. "
            f"Risk Management: The 14-period Average True Range (ATR) computes an institutional stop distance of {atr_points} points. "
            f"Fundamental Valuation: Trailing P/E ratio registers at {pe_ratio}. "
            f"Expert Verdict: Systematic multi-factor rules assign a '{signal}' directive based on dynamic moving-average alignment and volatility thresholds."
        )

        return {
            "Price": round(current_price, 2),
            "SMA_20": round(sma_20, 2),
            "SMA_50": round(sma_50, 2),
            "Momentum_1M": round(momentum_1m, 2),
            "Signal": signal,
            "ATR_Points": atr_points,
            "PE_Ratio": pe_ratio,
            "Reasoning": reasoning
        }
    except Exception as e:
        print(f"⏩ Skipping {ticker_symbol}: {e}")
        return None


def build_interactive_html_report(candidates):
    json_data = json.dumps(candidates)
    
    rows = ""
    for c in candidates:
        badge_color = "#28a745" if c["Signal"] == "STRONG BUY" else "#17a2b8"
        # Safely serialize item to avoid quote clashes in inline onclick
        safe_json_item = json.dumps(c).replace('"', '&quot;')
        rows += f"""
        <tr onclick='openModal({safe_json_item})' style="cursor: pointer;">
            <td style="padding: 12px; border-bottom: 1px solid #334155;"><b>{c['Ticker']}</b></td>
            <td style="padding: 12px; border-bottom: 1px solid #334155;">{c['Sector']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #334155;">${c['Price']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #334155;"><span style="background-color: {badge_color}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">{c['Signal']}</span></td>
            <td style="padding: 12px; border-bottom: 1px solid #334155;">{c['ATR_Points']} pts</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Global Institutional Equity Screener</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px; margin: 0; }}
            .container {{ max-width: 1000px; margin: auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
            h2 {{ color: #38bdf8; margin-top: 0; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; margin-top: 20px; }}
            th {{ background-color: #0f172a; color: #38bdf8; padding: 14px; border-bottom: 2px solid #334155; font-size: 13px; text-transform: uppercase; }}
            tr:hover {{ background-color: #334155; }}
            .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(4px); }}
            .modal-content {{ background: #1e293b; margin: 6% auto; padding: 30px; border: 1px solid #475569; width: 80%; max-width: 650px; border-radius: 12px; color: #f8fafc; }}
            .close {{ color: #94a3b8; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }}
            .close:hover {{ color: #fff; }}
            .modal-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .metric-box {{ background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155; }}
            .metric-label {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; }}
            .metric-value {{ font-size: 16px; font-weight: bold; color: #38bdf8; margin-top: 4px; }}
            .reasoning-box {{ background: #0f172a; padding: 15px; border-radius: 6px; border-left: 4px solid #38bdf8; margin-top: 15px; font-size: 14px; line-height: 1.6; color: #cbd5e1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>📈 Global Multi-Sector Quantitative Screener</h2>
            <p style="color: #94a3b8; font-size: 14px;">Click any stock row to expand deep-dive technical indicators, valuations, and expert reasoning.</p>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Sector</th>
                        <th>Price</th>
                        <th>Signal</th>
                        <th>Stop Distance</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>

        <div id="stockModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal()">&times;</span>
                <h3 id="modalTitle" style="color: #38bdf8; margin-top:0;">Stock Analysis</h3>
                <div class="modal-grid">
                    <div class="metric-box">
                        <div class="metric-label">Current Price</div>
                        <div class="metric-value" id="mPrice"></div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Signal Directive</div>
                        <div class="metric-value" id="mSignal"></div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">20-Day SMA</div>
                        <div class="metric-value" id="mSma20"></div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">50-Day SMA</div>
                        <div class="metric-value" id="mSma50"></div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">1-Month Momentum</div>
                        <div class="metric-value" id="mMomentum"></div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Trailing P/E Ratio</div>
                        <div class="metric-value" id="mPe"></div>
                    </div>
                </div>
                <div class="metric-label">Expert Quantitative Rationale & Parameter Alignment</div>
                <div class="reasoning-box" id="mReasoning"></div>
            </div>
        </div>

        <script>
            function openModal(data) {{
                document.getElementById('modalTitle').innerText = data.Ticker + ' — Sector Deep Dive Analysis';
                document.getElementById('mPrice').innerText = '$' + data.Price;
                document.getElementById('mSignal').innerText = data.Signal;
                document.getElementById('mSma20').innerText = '$' + data.SMA_20;
                document.getElementById('mSma50').innerText = '$' + data.SMA_50;
                document.getElementById('mMomentum').innerText = data.Momentum_1M + '%';
                document.getElementById('mPe').innerText = data.PE_Ratio;
                document.getElementById('mReasoning').innerText = data.Reasoning;
                document.getElementById('stockModal').style.display = 'block';
            }}

            function closeModal() {{
                document.getElementById('stockModal').style.display = 'none';
            }}

            window.onclick = function(event) {{
                var modal = document.getElementById('stockModal');
                if (event.target == modal) {{
                    modal.style.display = 'none';
                }}
            }}
        </script>
    </body>
    </html>
    """


def run_screener():
    print("=== RUNNING EXPANDED GLOBAL HYBRID STOCK SCREENER ===")
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
                "SMA_20": metrics["SMA_20"],
                "SMA_50": metrics["SMA_50"],
                "Momentum_1M": metrics["Momentum_1M"],
                "Signal": metrics["Signal"],
                "ATR_Points": metrics["ATR_Points"],
                "PE_Ratio": metrics["PE_Ratio"],
                "Reasoning": metrics["Reasoning"]
            })

    with open("top_candidates.json", "w") as f:
        json.dump(candidates, f, indent=4)
    print(f"-> Saved {len(candidates)} qualified buy setup candidates to top_candidates.json!")

    html_report = build_interactive_html_report(candidates)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_report)
    print("-> Successfully generated interactive index.html dashboard!")


if __name__ == "__main__":
    run_screener()
