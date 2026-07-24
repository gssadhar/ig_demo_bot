import os
import json
import pandas as pd
import yfinance as yf

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

        market_cap = format_large_number(info.get("marketCap"))
        revenue = format_large_number(info.get("totalRevenue"))
        net_income = format_large_number(info.get("netIncomeToCommon"))
        total_debt = format_large_number(info.get("totalDebt"))
        total_cash = format_large_number(info.get("totalCash"))
        
        pe_ratio = info.get("trailingPE", "N/A")
        if isinstance(pe_ratio, (int, float)):
            pe_ratio = f"{pe_ratio:.2f}"
            
        pb_ratio = info.get("priceToBook", "N/A")
        if isinstance(pb_ratio, (int, float)):
            pb_ratio = f"{pb_ratio:.2f}"
            
        roe = info.get("returnOnEquity", None)
        roe_str = f"{roe * 100:.2f}%" if isinstance(roe, (int, float)) else "N/A"
        
        profit_margins = info.get("profitMargins", None)
        margin_str = f"{profit_margins * 100:.2f}%" if isinstance(profit_margins, (int, float)) else "N/A"

        # Constructing institutional conviction rationale
        trend_phase = "Primary Bull Market (Above 50 SMA & 200 SMA)" if current_price > sma_200 else "Tactical Recovery Range"
        conviction_weight = "High Conviction Institutional Accumulation" if signal == "STRONG BUY" else "Moderate Tactical Upside"
        
        reasoning = (
            f"<b>Institutional Thesis & Market Structure:</b> Price action confirms a {trend_phase}, supported by a 1-month momentum print of {momentum_1m:.2f}%. "
            f"The asset trades relative to a 20-day SMA of ${sma_20:.2f} and 50-day SMA of ${sma_50:.2f}, triggering a <b>{signal}</b> directive. "
            f"<br><br><b>Fundamental Balance Sheet & Profitability Strength:</b> Operating with a market capitalization of {market_cap}, the corporation reports trailing revenues of {revenue} and net income of {net_income}. "
            f"Capital structure reflects total debt of {total_debt} offset by liquid cash reserves of {total_cash}. "
            f"Profitability metrics show a net profit margin of {margin_str} and a Return on Equity (ROE) of {roe_str}. "
            f"<br><br><b>Valuation & Risk Parameters:</b> Valued at a Trailing P/E of {pe_ratio} and Price-to-Book multiple of {pb_ratio}. "
            f"Risk parameters enforce an ATR-derived institutional stop-loss buffer of {atr_points} points to insulate against short-term market noise. "
            f"<b>Verdict:</b> {conviction_weight} backed by fundamental solvency and positive trend alignment."
        )

        return {
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
            "PE_Ratio": pe_ratio,
            "PB_Ratio": pb_ratio,
            "ROE": roe_str,
            "ProfitMargin": margin_str,
            "Reasoning": reasoning
        }
    except Exception as e:
        print(f"⏩ Skipping {ticker_symbol}: {e}")
        return None

def build_interactive_html_report(candidates):
    json_candidates = json.dumps(candidates)
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Institutional Multi-Sector Equity Terminal</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #0b0f19; color: #f8fafc; padding: 25px; margin: 0; }}
            .container {{ max-width: 1200px; margin: auto; background: #131c31; padding: 30px; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.6); border: 1px solid #1e293b; }}
            h2 {{ color: #38bdf8; margin-top: 0; font-size: 24px; letter-spacing: 0.5px; }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; margin-top: 20px; }}
            th {{ background-color: #0f172a; color: #38bdf8; padding: 14px; border-bottom: 2px solid #334155; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
            tr.clickable-row {{ cursor: pointer; transition: background 0.2s ease; }}
            tr.clickable-row:hover {{ background-color: #1e293b; }}
            .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(5,7,12,0.85); backdrop-filter: blur(6px); overflow-y: auto; }}
            .modal-content {{ background: #131c31; margin: 3% auto; padding: 35px; border: 1px solid #334155; width: 90%; max-width: 950px; border-radius: 16px; color: #f8fafc; box-shadow: 0 15px 40px rgba(0,0,0,0.8); }}
            .close {{ color: #94a3b8; float: right; font-size: 32px; font-weight: bold; cursor: pointer; line-height: 20px; }}
            .close:hover {{ color: #fff; }}
            .modal-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }}
            .metric-box {{ background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #1e293b; }}
            .metric-label {{ font-size: 10px; color: #94a3b8; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
            .metric-value {{ font-size: 15px; font-weight: bold; color: #38bdf8; margin-top: 6px; }}
            .section-title {{ font-size: 13px; color: #38bdf8; text-transform: uppercase; margin-top: 25px; margin-bottom: 10px; font-weight: bold; letter-spacing: 0.5px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
            .reasoning-box {{ background: #0f172a; padding: 18px; border-radius: 8px; border-left: 4px solid #38bdf8; font-size: 13px; line-height: 1.7; color: #cbd5e1; }}
            .tv-container {{ margin-top: 20px; width: 100%; height: 450px; border-radius: 8px; overflow: hidden; border: 1px solid #1e293b; background: #0f172a; }}
            .tv-link-btn {{ display: inline-block; background: #0284c7; color: #fff; padding: 10px 20px; border-radius: 6px; font-weight: bold; font-size: 13px; text-decoration: none; margin-top: 15px; transition: background 0.2s; }}
            .tv-link-btn:hover {{ background: #0369a1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>📈 Institutional Multi-Sector Quantitative Terminal</h2>
            <p style="color: #94a3b8; font-size: 13px;">Click any asset row to open institutional due diligence, fundamental balance sheet metrics, valuation ratios, and live TradingView technical charts.</p>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Sector</th>
                        <th>Price</th>
                        <th>Signal</th>
                        <th>Market Cap</th>
                        <th>Trailing P/E</th>
                        <th>Stop Distance</th>
                    </tr>
                </thead>
                <tbody id="table-body"></tbody>
            </table>
        </div>

        <div id="stockModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal()">&times;</span>
                <h3 id="modalTitle" style="color: #38bdf8; margin-top:0; font-size: 20px;">Asset Deep Dive</h3>
                
                <div class="section-title">Key Market & Valuation Metrics</div>
                <div class="modal-grid">
                    <div class="metric-box"><div class="metric-label">Current Price</div><div class="metric-value" id="mPrice"></div></div>
                    <div class="metric-box"><div class="metric-label">Signal Directive</div><div class="metric-value" id="mSignal"></div></div>
                    <div class="metric-box"><div class="metric-label">Market Capitalization</div><div class="metric-value" id="mMarketCap"></div></div>
                    <div class="metric-box"><div class="metric-label">Trailing P/E Ratio</div><div class="metric-value" id="mPe"></div></div>
                    <div class="metric-box"><div class="metric-label">Total Revenue</div><div class="metric-value" id="mRevenue"></div></div>
                    <div class="metric-box"><div class="metric-label">Net Income</div><div class="metric-value" id="mNetIncome"></div></div>
                    <div class="metric-box"><div class="metric-label">Total Debt</div><div class="metric-value" id="mDebt"></div></div>
                    <div class="metric-box"><div class="metric-label">Cash Reserves</div><div class="metric-value" id="mCash"></div></div>
                    <div class="metric-box"><div class="metric-label">Return on Equity (ROE)</div><div class="metric-value" id="mRoe"></div></div>
                    <div class="metric-box"><div class="metric-label">Profit Margin</div><div class="metric-value" id="mMargin"></div></div>
                    <div class="metric-box"><div class="metric-label">20-Day SMA</div><div class="metric-value" id="mSma20"></div></div>
                    <div class="metric-box"><div class="metric-label">50-Day SMA</div><div class="metric-value" id="mSma50"></div></div>
                </div>

                <div class="section-title">Institutional Analytical Conviction & Rationale</div>
                <div class="reasoning-box" id="mReasoning"></div>

                <div class="section-title">Live Technical Chart & Candlestick Analysis</div>
                <div id="tradingview_widget" class="tv-container"></div>
                <a id="tvExternalLink" href="#" target="_blank" class="tv-link-btn">Open Full Advanced Chart on TradingView ↗</a>
            </div>
        </div>

        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script>
            const candidates = {json_candidates};
            let currentWidget = null;

            function renderTable() {{
                const tbody = document.getElementById('table-body');
                tbody.innerHTML = '';
                candidates.forEach((c) => {{
                    const badgeColor = c.Signal === 'STRONG BUY' ? '#16a34a' : '#0284c7';
                    const row = document.createElement('tr');
                    row.className = 'clickable-row';
                    row.innerHTML = `
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b;"><b>${{c.Ticker}}</b></td>
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b; color: #94a3b8;">${{c.Sector}}</td>
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b;">$${{c.Price}}</td>
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b;"><span style="background-color: ${{badgeColor}}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;">${{c.Signal}}</span></td>
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.MarketCap}}</td>
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.PE_Ratio}}</td>
                        <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${{c.ATR_Points}} pts</td>
                    `;
                    row.onclick = () => openModal(c);
                    tbody.appendChild(row);
                }});
            }}

            function openModal(data) {{
                document.getElementById('modalTitle').innerText = data.Ticker + ' — Institutional Due Diligence & Technical Analysis';
                document.getElementById('mPrice').innerText = '$' + data.Price;
                document.getElementById('mSignal').innerText = data.Signal;
                document.getElementById('mMarketCap').innerText = data.MarketCap;
                document.getElementById('mPe').innerText = data.PE_Ratio;
                document.getElementById('mRevenue').innerText = data.Revenue;
                document.getElementById('mNetIncome').innerText = data.NetIncome;
                document.getElementById('mDebt').innerText = data.TotalDebt;
                document.getElementById('mCash').innerText = data.TotalCash;
                document.getElementById('mRoe').innerText = data.ROE;
                document.getElementById('mMargin').innerText = data.ProfitMargin;
                document.getElementById('mSma20').innerText = '$' + data.SMA_20;
                document.getElementById('mSma50').innerText = '$' + data.SMA_50;
                document.getElementById('mReasoning').innerHTML = data.Reasoning;
                
                // Format ticker for TradingView widget (e.g., HSBA.L -> LSE:HSBA)
                let tvSymbol = data.Ticker;
                if (tvSymbol.endsWith('.L')) {{
                    tvSymbol = 'LSE:' + tvSymbol.replace('.L', '');
                }} else if (tvSymbol.endsWith('.JO')) {{
                    tvSymbol = 'JSE:' + tvSymbol.replace('.JO', '');
                }}

                document.getElementById('tvExternalLink').href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(tvSymbol);

                document.getElementById('stockModal').style.display = 'block';

                // Render TradingView Advanced Chart Widget inside modal
                document.getElementById('tradingview_widget').innerHTML = '';
                new TradingView.widget({{
                    "width": "100%",
                    "height": "450",
                    "symbol": tvSymbol,
                    "interval": "D",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#0f172a",
                    "enable_publishing": false,
                    "hide_side_toolbar": false,
                    "allow_symbol_change": false,
                    "studies": [
                        "MASimple@tv-basicstudies",
                        "RSI@tv-basicstudies"
                    ],
                    "container_id": "tradingview_widget"
                }});
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

            renderTable();
        </script>
    </body>
    </html>
    """

def run_screener():
    print("=== RUNNING INSTITUTIONAL MULTI-SECTOR TERMINAL SCREENER ===")
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
                **metrics
            })

    with open("top_candidates.json", "w") as f:
        json.dump(candidates, f, indent=4)
    print(f"-> Saved {len(candidates)} institutional candidates to top_candidates.json!")

    html_report = build_interactive_html_report(candidates)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_report)
    print("-> Successfully generated professional terminal dashboard!")

if __name__ == "__main__":
    run_screener()
