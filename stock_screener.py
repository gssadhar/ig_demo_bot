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

def get_valid_epic_from_ig(ig_service, search_term):
    """
    Factually queries IG's live system to find the correct, 
    account-compatible epic string for a given ticker or company name.
    """
    try:
        markets = ig_service.search_markets(search_term)
        if markets is not None and not markets.empty:
            return markets.iloc[0]["epic"]
    except Exception as e:
        print(f"Error searching epic for {search_term}: {e}")
    return None

def fetch_uk_market_signals():
    """Expanded UK Equities Universe."""
    uk_data = [
        {"TICKER": "RR.L", "MARKET": "UK", "SECTOR": "Industrials", "PRICE": 1449.09, "SIGNAL": "BUY", "STOP-LOSS": 1392.41, "2.0R TARGET": 1563.45},
        {"TICKER": "LLOY.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 114.72, "SIGNAL": "STRONG BUY", "STOP-LOSS": 111.77, "2.0R TARGET": 120.62},
        {"TICKER": "LGEN.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 300.00, "SIGNAL": "STRONG BUY", "STOP-LOSS": 292.74, "2.0R TARGET": 314.52},
        {"TICKER": "SHEL.L", "MARKET": "UK", "SECTOR": "Energy", "PRICE": 3241.50, "SIGNAL": "BUY", "STOP-LOSS": 3085.24, "2.0R TARGET": 3554.02},
        {"TICKER": "BP.L", "MARKET": "UK", "SECTOR": "Energy", "PRICE": 526.90, "SIGNAL": "BUY", "STOP-LOSS": 509.48, "2.0R TARGET": 561.74},
        {"TICKER": "DGE.L", "MARKET": "UK", "SECTOR": "Consumer Defensive", "PRICE": 1574.79, "SIGNAL": "STRONG BUY", "STOP-LOSS": 1474.77, "2.0R TARGET": 1774.83},
        {"TICKER": "WTB.L", "MARKET": "UK", "SECTOR": "Consumer Cyclical", "PRICE": 2488.31, "SIGNAL": "BUY", "STOP-LOSS": 2411.41, "2.0R TARGET": 2603.65},
        {"TICKER": "BARC.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 210.00, "SIGNAL": "BUY", "STOP-LOSS": 202.00, "2.0R TARGET": 226.00},
        {"TICKER": "VOD.L", "MARKET": "UK", "SECTOR": "Telecommunication", "PRICE": 72.50, "SIGNAL": "BUY", "STOP-LOSS": 69.00, "2.0R TARGET": 79.50},
        {"TICKER": "AZN.L", "MARKET": "UK", "SECTOR": "Healthcare", "PRICE": 12400.00, "SIGNAL": "BUY", "STOP-LOSS": 11950.00, "2.0R TARGET": 13300.00}
    ]
    return pd.DataFrame(uk_data)

def fetch_us_market_signals():
    """Expanded USA Equities Universe."""
    us_data = [
        {"TICKER": "AAPL", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 220.50, "SIGNAL": "STRONG BUY", "STOP-LOSS": 212.00, "2.0R TARGET": 238.00},
        {"TICKER": "NVDA", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 125.40, "SIGNAL": "STRONG BUY", "STOP-LOSS": 120.00, "2.0R TARGET": 136.20},
        {"TICKER": "MSFT", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 415.00, "SIGNAL": "BUY", "STOP-LOSS": 400.00, "2.0R TARGET": 445.00},
        {"TICKER": "AMZN", "MARKET": "USA", "SECTOR": "Consumer Cyclical", "PRICE": 185.00, "SIGNAL": "BUY", "STOP-LOSS": 178.00, "2.0R TARGET": 199.00},
        {"TICKER": "TSLA", "MARKET": "USA", "SECTOR": "Consumer Cyclical", "PRICE": 250.00, "SIGNAL": "BUY", "STOP-LOSS": 238.00, "2.0R TARGET": 274.00}
    ]
    return pd.DataFrame(us_data)

def execute_strong_buys(df, ig_service):
    if not ig_service:
        print("Skipping execution: No active IG session.")
        return

    for _, row in df.iterrows():
        if row["SIGNAL"] == "STRONG BUY":
            ticker = row["TICKER"]
            search_query = ticker.replace(".L", "")
            epic = get_valid_epic_from_ig(ig_service, search_query)
            
            if not epic:
                print(f"-> Could not resolve a valid IG Epic for {ticker}. Skipping.")
                continue

            print(f"Executing automated order on IG for {ticker} (Resolved Epic: {epic}) - STRONG BUY...")
            try:
                response = ig_service.create_open_position(
                    currency_code="GBP" if row["MARKET"] == "UK" else "USD",
                    direction="BUY",
                    epic=epic,
                    expiry="DFB" if row["MARKET"] == "UK" else "-",
                    force_open=True,
                    guaranteed_stop=False,
                    order_type="MARKET",
                    size=1.0,
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
    - If profit hits target (e.g. £500), closes half (0.5 size) to bank cash, leaving the rest.
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
                    print(f"-> Successfully banked profits on {epic}.")
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
    
    # 1. Manage active trades
    monitor_and_manage_runners(ig_service, partial_profit_target_gbp=500.0)
    
    # 2. Execute new entry signals using dynamic live Epic resolution
    execute_strong_buys(uk_df, ig_service)
    execute_strong_buys(us_df, ig_service)
    
    # 3. Update dashboard
    generate_html_output(uk_df, us_df)

if __name__ == "__main__":
    main()
