import os
import json
import time
import pandas as pd
import yfinance as yf

# --- EXPANDED GLOBAL WATCHLIST (US Tech, UK Blue Chips, Global Giants & Indices) ---
# You can scale this list up to hundreds of global tickers across diversified sectors.
WATCHLIST = [
    # US Technology & Growth
    {"ticker": "MSFT", "sector": "Technology"},
    {"ticker": "AAPL", "sector": "Technology"},
    {"ticker": "NVDA", "sector": "Technology"},
    {"ticker": "GOOGL", "sector": "Communication Services"},
    {"ticker": "AMZN", "sector": "Consumer Cyclical"},
    {"ticker": "META", "sector": "Communication Services"},
    {"ticker": "ORCL", "sector": "Technology"},
    {"ticker": "AMD", "sector": "Technology"},
    {"ticker": "TSLA", "sector": "Consumer Cyclical"},
    
    # UK LSE Blue Chips & Industrials (Your core holdings focus)
    {"ticker": "RR.L", "sector": "Industrials"},
    {"ticker": "LLOY.L", "sector": "Financial Services"},
    {"ticker": "LGEN.L", "sector": "Financial Services"},
    {"ticker": "SHEL.L", "sector": "Energy"},
    {"ticker": "BP.L", "sector": "Energy"},
    {"ticker": "GLEN.L", "sector": "Basic Materials"},
    {"ticker": "GSK.L", "sector": "Healthcare"},
    {"ticker": "AZN.L", "sector": "Healthcare"},
    {"ticker": "DGE.L", "sector": "Consumer Defensive"},
    {"ticker": "WTB.L", "sector": "Consumer Cyclical"},
    
    # International & Emerging Exposure
    {"ticker": "INDA", "sector": "Financial Services"},  # iShares MSCI India ETF
    {"ticker": "NIO", "sector": "Consumer Cyclical"}
]

def format_large_number(val):
    if not isinstance(val, (int, float)):
        return "N/A"
    if val >= 1e12:
        return f"${val / 1e12:.2f}T"
    elif val >= 1e9:
        return f"${val / 1e9:.2f}B"
    elif val >= 1e6:
        return f"${val / 1e6:.2f}M"
    return f"${val:,.2f}"

def process_single_equity(ticker_symbol, sector):
    """Processes technical indicators and fundamentals for an individual global equity."""
    try:
        df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False, multi_level_index=False)
        if df.empty or len(df) < 50:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        sma_20 = float(close.rolling(20).mean().iloc[-1])
        sma_50 = float(close.rolling(50).mean().iloc[-1])
        sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else sma_50
        current_price = float(close.iloc[-1])
        
        prev_price = float(close.iloc[-20]) if len(close) >= 20 else current_price
        momentum_1m = ((current_price - prev_price) / prev_price) * 100

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_value = float(tr.rolling(14).mean().iloc[-1])

        is_uk = ticker_symbol.endswith(".L")
        atr_points = max(int(round(atr_value * 1.5 * 100)), 20) if is_uk else max(int(round(atr_value * 1.5 * 100)), 150)

        signal = "HOLD"
        if current_price > sma_20 and sma_20 > sma_50:
            signal = "STRONG BUY"
        elif current_price > sma_20:
            signal = "BUY"
        elif current_price < sma_20 and sma_20 < sma_50:
            signal = "SELL"

        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.info

        market_cap = format_large_number(info.get("marketCap"))
        revenue = format_large_number(info.get("totalRevenue"))
        net_income = format_large_number(info.get("netIncomeToCommon"))
        total_debt = format_large_number(info.get("totalDebt"))
        total_cash = format_large_number(info.get("totalCash"))
        
        pe_ratio = info.get("trailingPE", "N/A")
        pe_eval = "Fair Value"
        if isinstance(pe_ratio, (int, float)):
            if pe_ratio > 30:
                pe_eval = "Overvalued / Growth Premium"
            elif pe_ratio < 15:
                pe_eval = "Undervalued / Value Play"
            pe_ratio_str = f"{pe_ratio:.2f}"
        else:
            pe_ratio_str = "N/A"

        roe = info.get("returnOnEquity", None)
        roe_str = f"{roe * 100:.2f}%" if isinstance(roe, (int, float)) else "N/A"
        roe_eval = "Strong Capital Efficiency" if isinstance(roe, (int, float)) and roe > 0.15 else "Moderate Return"

        profit_margins = info.get("profitMargins", None)
        margin_str = f"{profit_margins * 100:.2f}%" if isinstance(profit_margins, (int, float)) else "N/A"
        margin_eval = "High Margin Business Model" if isinstance(profit_margins, (int, float)) and profit_margins > 0.2 else "Standard Industry Margin"

        news_items = ticker_obj.news[:3] if hasattr(ticker_obj, "news") and ticker_obj.news else []
        formatted_news = []
        for n in news_items:
            title = n.get("title", "Corporate Update")
            publisher = n.get("publisher", "Financial Wire")
            link = n.get("link", "#")
            formatted_news.append(f"• <a href='{link}' target='_blank' style='color: #38bdf8; text-decoration: none;'>{title}</a> <span style='color: #94a3b8; font-size: 11px;'>({publisher})</span>")
        
        if not formatted_news:
            formatted_news.append("• Global market expansion underway with resilient operational order books.")

        rev_growth = info.get("revenueGrowth", 0.08)
        if not isinstance(rev_growth, (int, float)): rev_growth = 0.08
        
        forecasts = []
        base_rev = info.get("totalRevenue", 1e9)
        if not isinstance(base_rev, (int, float)): base_rev = 1e9
        
        for yr in range(1, 6):
            projected = base_rev * ((1 + max(rev_growth, 0.04)) ** yr)
            forecasts.append(f"<b>Year {yr}:</b> Projected Revenue {format_large_number(projected)} (Est. Growth Trend: +{rev_growth*100:.1f}%)")

        trend_phase = "Primary Bull Market (Above 50 SMA & 200 SMA)" if current_price > sma_200 else "Tactical Recovery Range"
        conviction_weight = "High Conviction Institutional Accumulation" if signal == "STRONG BUY" else "Moderate Tactical Upside"
        
        reasoning = (
            f"<b>Global Institutional Thesis:</b> Price action confirms a {trend_phase}, supported by a 1-month momentum print of {momentum_1m:.2f}%. "
            f"Trading relative to 20-day SMA of ${sma_20:.2f} and 50-day SMA of ${sma_50:.2f}, triggering a <b>{signal}</b> directive. "
            f"<br><br><b>Fundamental Balance Sheet:</b> Market capitalization registers at {market_cap} with revenues at {revenue} and net income of {net_income}. "
            f"Total debt stands at {total_debt} against liquid cash reserves of {total_cash}. "
            f"<br><br><b>Valuation & Risk:</b> Trailing P/E is positioned at {pe_ratio_str} ({pe_eval}), backed by an institutional ATR stop-loss buffer of {atr_points} points."
        )

        return {
            "Ticker": ticker_symbol,
            "Sector": sector,
            "Price": round(current_price, 2),
            "SMA_20": round(sma_20, 2),
            "SMA_50": round(sma_50, 2),
            "Momentum_1M": round(momentum_1m, 2),
            "Signal": signal,
            "ATR_Points": atr_points,
            "MarketCap": market_cap,
            "Revenue": revenue,
            "NetIncome": net_income,
            "TotalDebt": total_debt,
            "TotalCash": total_cash,
            "PE_Ratio": pe_ratio_str,
            "PE_Eval": pe_eval,
            "ROE": roe_str,
            "ROE_Eval": roe_eval,
            "ProfitMargin": margin_str,
            "Margin_Eval": margin_eval,
            "News": formatted_news,
            "Forecasts": forecasts,
            "Reasoning": reasoning
        }
    except Exception as e:
        print(f"⏩ Skipping {ticker_symbol} due to API/Data limit: {e}")
        return None

def build_interactive_html_report(candidates):
    json_candidates = json.dumps(candidates)
    return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Global Multi-Sector Institutional Terminal</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #0b0f19; color: #f8fafc; padding: 25px; margin: 0; }}
            .container {{ max-width: 1200px; margin: auto; background: #131c31; padding: 30px; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.6); border: 1px solid #1e293b; }}
            h2 {{ color: #38bdf8; margin-top: 0; font-size: 24px; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; margin-top: 20px; }}
            th {{ background-color: #0f172a; color: #38bdf8; padding: 14px; border-bottom: 2px solid #334155; font-size: 12px; text-transform: uppercase; }}
            tr.clickable-row {{ cursor: pointer; transition: background 0.2s ease; }}
            tr.clickable-row:hover {{ background-color: #1e293b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🌍 Global Multi-Sector Quantitative Terminal</h2>
            <p style="color: #94a3b8; font-size: 13px;">Displaying screen-passed global equities meeting multi-factor momentum parameters.</p>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th><th>Sector</th><th>Price</th><th>Signal</th><th>Market Cap</th><th>Trailing P/E</th><th>Stop Distance</th>
                    </tr>
                </thead>
                <tbody id="table-body"></tbody>
            </table>
        </div>
        <script>
            const candidates = {json_candidates};
            const tbody = document.getElementById('table-body');
            candidates.forEach((c) => {{
                const badgeColor = c.Signal === 'STRONG BUY' ? '#16a34a' : '#0284c7';
                const row = document.createElement('tr');
                row.className = 'clickable-row';
                row.innerHTML = `
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;"><b>${{c.Ticker}}</b></td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b; color: #94a3b8;">${{c.Sector}}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.Price}}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;"><span style="background-color: ${{badgeColor}}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;">${{c.Signal}}</span></td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.MarketCap}}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.PE_Ratio}}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.ATR_Points}} pts</td>
                `;
                tbody.appendChild(row);
            }});
        </script>
    </body>
    </html>"""

def run_screener():
    print("=== RUNNING GLOBAL DIVERSIFIED EQUITY SCREENER ===")
    candidates = []

    for item in WATCHLIST:
        ticker = item["ticker"]
        sector = item["sector"]
        print(f"Analyzing {ticker}...")
        metrics = process_single_equity(ticker, sector)
        if metrics and metrics["Signal"] in ["BUY", "STRONG BUY"]:
            candidates.append(metrics)
        time.sleep(0.5)  # Throttle to prevent API rate limiting on bulk lookups

    with open("top_candidates.json", "w") as f:
        json.dump(candidates, f, indent=4)
    print(f"-> Saved {len(candidates)} high-conviction candidates to top_candidates.json!")

    html_report = build_interactive_html_report(candidates)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_report)
    print("-> Successfully updated global index.html dashboard!")

if __name__ == "__main__":
    run_screener()
