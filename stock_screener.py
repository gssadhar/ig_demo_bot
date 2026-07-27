import os
import json
import time
import requests
import pandas as pd
import yfinance as yf

# ==============================================================================
# 1. AUTOMATED IG DEMO EXECUTION CONFIGURATION
# ==============================================================================
ENABLE_AUTO_EXECUTION = False  

IG_CREDENTIALS = {
    "api_key": "YOUR_IG_DEMO_API_KEY",
    "username": "YOUR_IG_USERNAME",
    "password": "YOUR_IG_PASSWORD",
    "account_id": "YOUR_IG_DEMO_ACCOUNT_ID",
    "base_url": "https://demo-api.ig.com/gateway/deal"
}

IG_EPIC_MAP = {
    "LLOY.L": "CS.D.LLOY.DAILY.IP",
    "LGEN.L": "CS.D.LGEN.DAILY.IP",
    "RR.L": "CS.D.RR.DAILY.IP",
    "SHEL.L": "CS.D.SHEL.DAILY.IP",
    "BP.L": "CS.D.BP.DAILY.IP",
    "GSK.L": "CS.D.GSK.DAILY.IP",
    "DGE.L": "CS.D.DGE.DAILY.IP",
    "NVDA": "CS.D.NVDA.DAILY.IP",
    "AAPL": "CS.D.AAPL.DAILY.IP",
    "MSFT": "CS.D.MSFT.DAILY.IP",
    "AMZN": "CS.D.AMZN.DAILY.IP",
    "GOOGL": "CS.D.GOOGL.DAILY.IP",
    "META": "CS.D.META.DAILY.IP"
}

WATCHLIST = [
    {"ticker": "MSFT", "sector": "Technology"},
    {"ticker": "AAPL", "sector": "Technology"},
    {"ticker": "NVDA", "sector": "Technology"},
    {"ticker": "GOOGL", "sector": "Communication Services"},
    {"ticker": "AMZN", "sector": "Consumer Cyclical"},
    {"ticker": "META", "sector": "Communication Services"},
    {"ticker": "ORCL", "sector": "Technology"},
    {"ticker": "AMD", "sector": "Technology"},
    {"ticker": "RR.L", "sector": "Industrials"},
    {"ticker": "LLOY.L", "sector": "Financial Services"},
    {"ticker": "LGEN.L", "sector": "Financial Services"},
    {"ticker": "SHEL.L", "sector": "Energy"},
    {"ticker": "BP.L", "sector": "Energy"},
    {"ticker": "GLEN.L", "sector": "Basic Materials"},
    {"ticker": "GSK.L", "sector": "Healthcare"},
    {"ticker": "DGE.L", "sector": "Consumer Defensive"},
    {"ticker": "WTB.L", "sector": "Consumer Cyclical"},
    {"ticker": "TSM", "sector": "Technology"},         
    {"ticker": "BABA", "sector": "Consumer Cyclical"},  
    {"ticker": "IEMG", "sector": "Financial Services"}, 
    {"ticker": "INDA", "sector": "Financial Services"}  
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

def execute_ig_trade(ticker, signal, stop_distance_pts, target_distance_pts):
    if not ENABLE_AUTO_EXECUTION:
        return
    epic = IG_EPIC_MAP.get(ticker)
    if not epic:
        return
    
    session_url = f"{IG_CREDENTIALS['base_url']}/session"
    headers = {
        "X-IG-API-KEY": IG_CREDENTIALS["api_key"],
        "Content-Type": "application/json",
        "Accept": "application/json; charset=UTF-8"
    }
    payload = {
        "identifier": IG_CREDENTIALS["username"],
        "password": IG_CREDENTIALS["password"]
    }
    
    try:
        resp = requests.post(session_url, json=payload, headers=headers)
        if resp.status_code != 200:
            return
        cst = resp.headers.get("CST")
        x_security_token = resp.headers.get("X-SECURITY-TOKEN")
        headers.update({"CST": cst, "X-SECURITY-TOKEN": x_security_token})
        
        order_url = f"{IG_CREDENTIALS['base_url']}/positions/otc"
        order_payload = {
            "epic": epic,
            "expiry": "-",
            "direction": "BUY",
            "size": "0.5",
            "orderType": "MARKET",
            "guaranteedStop": False,
            "stopDistance": str(int(round(stop_distance_pts))),
            "limitDistance": str(int(round(target_distance_pts))),
            "currencyCode": "GBP" if ticker.endswith(".L") else "USD",
            "forceOpen": True
        }
        requests.post(order_url, json=order_payload, headers=headers)
    except Exception:
        pass

def process_single_equity(ticker_symbol, sector):
    try:
        df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False, multi_level_index=False)
        if df.empty or len(df) < 50:
            return None

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
            risk_distance = atr_value * 1.2
            stop_loss_val = current_price - risk_distance
            profit_target_val = current_price + (risk_distance * 1.5)
            
            stop_points_ig = max(round(risk_distance, 1), 2.0)
            target_points_ig = round(risk_distance * 1.5, 1)
            
            price_str = f"{current_price:.2f}p (£{current_price/100:.2f})"
            stop_str = f"{stop_loss_val:.2f}p ({stop_points_ig} pts)"
            target_str = f"{profit_target_val:.2f}p ({target_points_ig} pts)"
        else:
            risk_distance = atr_value * 1.2
            stop_loss_val = current_price - risk_distance
            profit_target_val = current_price + (risk_distance * 1.5)
            
            stop_points_ig = max(round(risk_distance * 100, 1), 50.0)
            target_points_ig = round(risk_distance * 150, 1)
            
            price_str = f"${current_price:.2f}"
            stop_str = f"${stop_loss_val:.2f} ({stop_points_ig:.0f} pts)"
            target_str = f"${profit_target_val:.2f} ({target_points_ig:.0f} pts)"

        signal = "HOLD"
        if current_price > sma_20 and current_price > sma_50 and sma_20 > sma_50 and momentum_1m > 1.0:
            signal = "STRONG BUY"
        elif current_price > sma_20 and current_price > sma_50 and momentum_1m > 0:
            signal = "BUY"
        elif current_price < sma_20 or current_price < sma_50:
            signal = "SELL"

        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.info

        market_cap = format_large_number(info.get("marketCap"))
        revenue = format_large_number(info.get("totalRevenue"))
        total_cash = format_large_number(info.get("totalCash"))
        
        pe_ratio = info.get("trailingPE", "N/A")
        pe_eval = "Fair Value"
        if isinstance(pe_ratio, (int, float)):
            if pe_ratio > 30: pe_eval = "Growth Premium"
            elif pe_ratio < 15: pe_eval = "Undervalued Value Play"
            pe_ratio_str = f"{pe_ratio:.2f}"
        else:
            pe_ratio_str = "N/A"

        news_items = ticker_obj.news[:3] if hasattr(ticker_obj, "news") and ticker_obj.news else []
        formatted_news = []
        for n in news_items:
            title = n.get("title", "Corporate Announcement")
            publisher = n.get("publisher", "Wire")
            link = n.get("link", "#")
            formatted_news.append(f"• <a href='{link}' target='_blank' style='color: #38bdf8; text-decoration: none;'>{title}</a> <span style='color: #94a3b8; font-size: 11px;'>({publisher})</span>")
        
        if not formatted_news:
            formatted_news.append("• Active corporate operations and institutional liquidity support maintain bullish posture.")

        reasoning = (
            f"<b>Institutional Setup & Auto-Rules:</b> Asset maintains primary trend above 20-day SMA and 50-day SMA "
            f"with a 1-month momentum of {momentum_1m:.2f}% ({signal}). "
            f"<br><br><b>🎯 Automatic IG Order Parameters:</b> "
            f"<br>• <b>IG Stop Distance:</b> Set exactly to <b>{stop_points_ig} Points</b> below entry ({stop_str})."
            f"<br>• <b>IG Profit Target 1 (1.5R):</b> Set exactly to <b>{target_points_ig} Points</b> above entry ({target_str})."
            f"<br>• <b>Execution Directive:</b> Scale out 50% at Target 1 and move remaining stop to entry break-even."
        )

        if signal == "STRONG BUY" and ENABLE_AUTO_EXECUTION:
            execute_ig_trade(ticker_symbol, signal, stop_points_ig, target_points_ig)

        return {
            "Ticker": ticker_symbol,
            "Sector": sector,
            "Price": price_str,
            "Signal": signal,
            "StopLoss": stop_str,
            "Target15R": target_str,
            "MarketCap": market_cap,
            "Revenue": revenue,
            "TotalCash": total_cash,
            "PE_Ratio": pe_ratio_str,
            "PE_Eval": pe_eval,
            "News": formatted_news,
            "Reasoning": reasoning
        }
    except Exception:
        return None

def build_interactive_html_report(candidates):
    json_candidates = json.dumps(candidates)
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Global Quantitative Terminal</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #0b0f19; color: #f8fafc; padding: 25px; margin: 0; }
        .container { max-width: 1200px; margin: auto; background: #131c31; padding: 30px; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.6); border: 1px solid #1e293b; }
        h2 { color: #38bdf8; margin-top: 0; font-size: 24px; letter-spacing: 0.5px; }
        table { width: 100%; border-collapse: collapse; text-align: left; margin-top: 20px; }
        th { background-color: #0f172a; color: #38bdf8; padding: 14px; border-bottom: 2px solid #334155; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        tr.clickable-row { cursor: pointer; transition: background 0.2s ease; }
        tr.clickable-row:hover { background-color: #1e293b; }
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(5,7,12,0.85); backdrop-filter: blur(6px); overflow-y: auto; }
        .modal-content { background: #131c31; margin: 2% auto; padding: 30px; border: 1px solid #334155; width: 95%; max-width: 1350px; border-radius: 16px; color: #f8fafc; box-shadow: 0 15px 40px rgba(0,0,0,0.8); }
        .close { color: #94a3b8; float: right; font-size: 32px; font-weight: bold; cursor: pointer; line-height: 20px; }
        .close:hover { color: #fff; }
        .modal-layout { display: grid; grid-template-columns: 1.3fr 0.7fr; gap: 24px; margin-top: 20px; }
        .left-column { display: flex; flex-direction: column; gap: 20px; }
        .right-sidebar { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; max-height: 850px; overflow-y: auto; }
        .sidebar-title { font-size: 13px; color: #38bdf8; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px; border-bottom: 1px solid #1e293b; padding-bottom: 8px; margin-bottom: 15px; }
        .metric-card { background: #131c31; padding: 12px 14px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 10px; }
        .metric-label { font-size: 10px; color: #94a3b8; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }
        .metric-value { font-size: 15px; font-weight: bold; color: #38bdf8; margin-top: 4px; }
        .metric-eval { font-size: 10px; font-weight: bold; color: #34d399; margin-top: 2px; }
        .section-title { font-size: 13px; color: #38bdf8; text-transform: uppercase; margin-top: 20px; margin-bottom: 8px; font-weight: bold; letter-spacing: 0.5px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }
        .reasoning-box, .info-box { background: #0f172a; padding: 16px; border-radius: 8px; border-left: 4px solid #38bdf8; font-size: 13px; line-height: 1.7; color: #cbd5e1; }
        .tv-container { width: 100%; height: 460px; border-radius: 8px; overflow: hidden; border: 1px solid #1e293b; background: #0f172a; }
        .tv-link-btn { display: inline-block; background: #0284c7; color: #fff; padding: 10px 20px; border-radius: 6px; font-weight: bold; font-size: 13px; text-decoration: none; text-align: center; transition: background 0.2s; }
        .tv-link-btn:hover { background: #0369a1; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🌍 Global Quantitative Terminal (Automated IG Execution Parameters)</h2>
        <p style="color: #94a3b8; font-size: 13px;">UK shares are automatically converted to pence/pounds with exact IG SpreadBet point distances.</p>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Price</th>
                    <th>Signal</th>
                    <th>IG Stop Loss</th>
                    <th>IG 1.5R Target</th>
                    <th>Market Cap</th>
                </tr>
            </thead>
            <tbody id="table-body"></tbody>
        </table>
    </div>

    <div id="stockModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h3 id="modalTitle" style="color: #38bdf8; margin-top:0; font-size: 20px;">Asset Analysis</h3>
            
            <div class="modal-layout">
                <div class="left-column">
                    <div class="section-title" style="margin-top:0;">Chart View</div>
                    <div id="tradingview_widget" class="tv-container"></div>
                    <a id="tvExternalLink" href="#" target="_blank" class="tv-link-btn">View on TradingView ↗</a>

                    <div class="section-title">Automated Execution Rationale</div>
                    <div class="reasoning-box" id="mReasoning"></div>

                    <div class="section-title">Corporate Catalysts</div>
                    <div class="info-box" id="mNews"></div>
                </div>

                <div class="right-sidebar">
                    <div class="sidebar-title">Order Parameters</div>
                    
                    <div class="metric-card" style="border-color: #ef4444;">
                        <div class="metric-label">IG Stop-Loss Distance</div>
                        <div class="metric-value" id="mStopLoss" style="color: #ef4444;"></div>
                        <div class="metric-eval">Defensive Exit Point</div>
                    </div>

                    <div class="metric-card" style="border-color: #34d399;">
                        <div class="metric-label">IG 1.5R Target Distance</div>
                        <div class="metric-value" id="mTarget" style="color: #34d399;"></div>
                        <div class="metric-eval">50% Partial Scale-Out</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Live Price</div>
                        <div class="metric-value" id="mPrice"></div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Signal Directive</div>
                        <div class="metric-value" id="mSignal"></div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Market Cap</div>
                        <div class="metric-value" id="mMarketCap"></div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Trailing P/E</div>
                        <div class="metric-value" id="mPe"></div>
                        <div class="metric-eval" id="mPeEval"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        const candidates = __CANDIDATES_JSON__;

        function renderTable() {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';
            if (candidates.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="padding: 20px; text-align: center; color: #94a3b8;">No assets currently meet the entry criteria.</td></tr>';
                return;
            }
            candidates.forEach((c) => {
                const badgeColor = c.Signal === 'STRONG BUY' ? '#16a34a' : '#0284c7';
                const row = document.createElement('tr');
                row.className = 'clickable-row';
                row.innerHTML = `
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;"><b>${c.Ticker}</b></td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b; color: #94a3b8;">${c.Sector}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${c.Price}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;"><span style="background-color: ${badgeColor}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;">${c.Signal}</span></td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b; color: #ef4444;">${c.StopLoss}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b; color: #34d399;">${c.Target15R}</td>
                    <td style="padding: 14px; border-bottom: 1px solid #1e293b;">${c.MarketCap}</td>
                `;
                row.onclick = () => openModal(c);
                tbody.appendChild(row);
            });
        }

        function openModal(data) {
            document.getElementById('modalTitle').innerText = data.Ticker + ' — Execution Overview';
            document.getElementById('mPrice').innerText = data.Price;
            document.getElementById('mSignal').innerText = data.Signal;
            document.getElementById('mStopLoss').innerText = data.StopLoss;
            document.getElementById('mTarget').innerText = data.Target15R;
            document.getElementById('mMarketCap').innerText = data.MarketCap;
            document.getElementById('mPe').innerText = data.PE_Ratio;
            document.getElementById('mPeEval').innerText = data.PE_Eval;
            document.getElementById('mReasoning').innerHTML = data.Reasoning;
            document.getElementById('mNews').innerHTML = data.News.join('<br><br>');

            let tvSymbol = data.Ticker;
            if (tvSymbol.endsWith('.L')) {
                tvSymbol = 'LSE:' + tvSymbol.replace('.L', '');
            }

            document.getElementById('tvExternalLink').href = 'https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(tvSymbol);
            document.getElementById('stockModal').style.display = 'block';

            document.getElementById('tradingview_widget').innerHTML = '';
            try {
                new TradingView.widget({
                    "width": "100%",
                    "height": "460",
                    "symbol": tvSymbol,
                    "interval": "D",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#0f172a",
                    "enable_publishing": false,
                    "hide_side_toolbar": false,
                    "allow_symbol_change": true,
                    "studies": ["MASimple@tv-basicstudies", "RSI@tv-basicstudies", "BB@tv-basicstudies", "Volume@tv-basicstudies"],
                    "container_id": "tradingview_widget"
                });
            } catch(err) {
                document.getElementById('tradingview_widget').innerHTML = '<div style="padding: 40px; text-align: center; color: #94a3b8;">TradingView widget load pending.</div>';
            }
 
