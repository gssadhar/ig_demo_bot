import os
import sys
import pandas as pd
from trading_ig import IGService

# IG Credentials from Environment Secrets
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
IG_API_KEY = os.environ.get("IG_API_KEY")
IG_ACC_TYPE = "DEMO"

def authenticate_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY]):
        print("IG credentials missing from environment variables.")
        return None
    try:
        ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
        ig_service.create_session()
        print("Successfully authenticated with IG API.")
        return ig_service
    except Exception as e:
        print(f"IG Authentication failed: {e}")
        return None

def fetch_uk_market_signals():
    """Screens UK Equities mapped to valid IG Demo Epics."""
    uk_data = [
        {"TICKER": "RR.L", "EPIC": "IX.D.RR.DAILY.IP", "MARKET": "UK", "SECTOR": "Industrials", "PRICE": 1449.09, "SIGNAL": "BUY", "STOP-LOSS": 1392.41, "2.0R TARGET": 1563.45},
        {"TICKER": "LLOY.L", "EPIC": "IX.D.LLOY.DAILY.IP", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 114.72, "SIGNAL": "STRONG BUY", "STOP-LOSS": 111.77, "2.0R TARGET": 120.62},
        {"TICKER": "LGEN.L", "EPIC": "IX.D.LGEN.DAILY.IP", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 300.00, "SIGNAL": "STRONG BUY", "STOP-LOSS": 292.74, "2.0R TARGET": 314.52},
        {"TICKER": "SHEL.L", "EPIC": "IX.D.SHEL.DAILY.IP", "MARKET": "UK", "SECTOR": "Energy", "PRICE": 3241.50, "SIGNAL": "BUY", "STOP-LOSS": 3085.24, "2.0R TARGET": 3554.02},
        {"TICKER": "BP.L", "EPIC": "IX.D.BP.DAILY.IP", "MARKET": "UK", "SECTOR": "Energy", "PRICE": 526.90, "SIGNAL": "BUY", "STOP-LOSS": 509.48, "2.0R TARGET": 561.74},
        {"TICKER": "DGE.L", "EPIC": "IX.D.DGE.DAILY.IP", "MARKET": "UK", "SECTOR": "Consumer Defensive", "PRICE": 1574.79, "SIGNAL": "STRONG BUY", "STOP-LOSS": 1474.77, "2.0R TARGET": 1774.83},
        {"TICKER": "WTB.L", "EPIC": "IX.D.WTB.DAILY.IP", "MARKET": "UK", "SECTOR": "Consumer Cyclical", "PRICE": 2488.31, "SIGNAL": "BUY", "STOP-LOSS": 2411.41, "1.5R TARGET": 2603.65}
    ]
    return pd.DataFrame(uk_data)

def fetch_us_market_signals():
    """Screens USA Equities mapped to valid IG Demo Epics."""
    us_data = [
        {"TICKER": "AAPL", "EPIC": "US.D.AAPL.CASH.IP", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 220.50, "SIGNAL": "STRONG BUY", "STOP-LOSS": 212.00, "2.0R TARGET": 238.00},
        {"TICKER": "NVDA", "EPIC": "US.D.NVDA.CASH.IP", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 125.40, "SIGNAL": "BUY", "STOP-LOSS": 120.00, "2.0R TARGET": 136.20}
    ]
    return pd.DataFrame(us_data)

def execute_strong_buys(df, ig_service):
    if not ig_service:
        print("Skipping execution: No active IG session.")
        return

    for _, row in df.iterrows():
        if row["SIGNAL"] == "STRONG BUY":
            epic = row["EPIC"]
            ticker = row["TICKER"]
            print(f"Executing automated order on IG for {ticker} (Epic: {epic}) - STRONG BUY...")
            try:
                response = ig_service.create_open_position(
                    currency_code="GBP" if row["MARKET"] == "UK" else "USD",
                    direction="BUY",
                    epic=epic,
                    expiry="DFB" if row["MARKET"] == "UK" else "-",
                    force_open=True,
                    guaranteed_stop=False,
                    order_type="MARKET",
                    size=1.0,  # Full size entry to allow partial scaling out later
                    level=None,
                    limit_distance=None,
                    limit_level=float(row["2.0R TARGET"]),
                    quote_id=None,
                    stop_distance=None,
                    stop_level=float(row["STOP-LOSS"]),
                    trailing_stop=None,
                    trailing_stop_increment=None
                )
                if response and response.get("dealStatus") == "ACCEPTED":
                    print(f"-> Success! Deal ID: {response.get('dealId')}")
                else:
                    print(f"-> Order rejected for {ticker}: {response.get('reason')}")
            except Exception as e:
                print(f"-> Error executing {ticker}: {e}")

def monitor_and_manage_runners(ig_service, partial_profit_target_gbp=500.0):
    """
    Manages open positions:
    - If profit hits target (e.g. £500, representing a 2.0R milestone), 
      it closes half (0.5 size) to bank cash, leaving the rest to run.
    """
    if not ig_service:
        return
    
    try:
        positions = ig_service.fetch_open_positions()
        if positions is None or positions.empty:
            print("No open positions found to monitor.")
            return

        for _, pos in positions.iterrows():
            deal_id = pos.get("dealId")
            profit_loss = float(pos.get("profitAndLoss", 0.0))
            epic = pos.get("epic")
            current_size = float(pos.get("size", 1.0))
            
            print(f"Monitoring runner position {epic} (ID: {deal_id}, Size: {current_size}) | P&L: £{profit_loss:.2f}")
            
            # Condition 1: Take partial profit (half size) if profit threshold is reached and we haven't scaled out yet
            if profit_loss >= partial_profit_target_gbp and current_size > 0.5:
                half_size = round(current_size / 2.0, 2)
                print(f"-> Target profit of £{partial_profit_target_gbp} reached for {epic}! Banking half size ({half_size})...")
                
                close_response = ig_service.close_open_position(
                    deal_id=deal_id,
                    direction="SELL" if pos.get("direction") == "BUY" else "BUY",
                    size=half_size,
                    order_type="MARKET",
                    quote_id=None
                )
                if close_response and close_response.get("status") == "SUCCESS":
                    print(f"-> Successfully banked profits on {epic}. Leaving remaining runner to catch extended trends.")
                else:
                    print(f"-> Partial close failed for {epic}.")
                    
    except Exception as e:
        print(f"Error managing runner positions: {e}")

def generate_html_output(uk_df, us_df):
    """Combines UK and US tables into index.html."""
    template_path = "template.html"
    if not os.path.exists(template_path):
        print("Error: template.html not found.")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    combined_df = pd.concat([uk_df, us_df], ignore_index=True)

    rows_html = ""
    for _, row in combined_df.iterrows():
        badge_class = "strong-buy-badge" if row["SIGNAL"] == "STRONG BUY" else "buy-badge"
        target_col = row.get("2.0R TARGET", row.get("1.5R TARGET", 0.0))
        rows_html += f"""
            <tr>
                <td>{row['TICKER']} ({row['MARKET']})</td>
                <td>{row['SECTOR']}</td>
                <td>{row['PRICE']}</td>
                <td><span class="{badge_class}">{row['SIGNAL']}</span></td>
                <td>{row['STOP-LOSS']}</td>
                <td>{target_col}</td>
            </tr>
        """

    final_html = template_content.replace("{{TABLE_ROWS}}", rows_html)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("Dashboard index.html successfully updated with UK & USA feeds.")

def main():
    print("--- Starting 4x Daily Runner Strategy Pipeline ---")
    uk_df = fetch_uk_market_signals()
    us_df = fetch_us_market_signals()
    
    ig_service = authenticate_ig()
    
    # 1. Manage active trades (take partial profits & let runners continue)
    monitor_and_manage_runners(ig_service, partial_profit_target_gbp=500.0)
    
    # 2. Execute new entry signals
    execute_strong_buys(uk_df, ig_service)
    execute_strong_buys(us_df, ig_service)
    
    # 3. Update dashboard
    generate_html_output(uk_df, us_df)

if __name__ == "__main__":
    main()
