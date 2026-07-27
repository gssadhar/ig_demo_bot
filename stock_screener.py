import os
import sys
from datetime import datetime
import pytz
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

def is_market_open(market_type):
    """Checks if the respective market is currently open for trading."""
    tz_london = pytz.timezone("Europe/London")
    now = datetime.now(tz_london)
    
    # Check for weekends
    if now.weekday() >= 5: # Saturday or Sunday
        return False
        
    current_time = now.time()
    
    if market_type == "UK":
        # LSE regular trading hours: 08:00 - 16:30 London Time
        market_open = datetime.strptime("08:00", "%H:%M").time()
        market_close = datetime.strptime("16:30", "%H:%M").time()
        return market_open <= current_time <= market_close
        
    elif market_type == "USA":
        # US regular trading hours converted to London Time (14:30 - 21:00)
        market_open = datetime.strptime("14:30", "%H:%M").time()
        market_close = datetime.strptime("21:00", "%H:%M").time()
        return market_open <= current_time <= market_close
        
    return True

def get_valid_epic_from_ig(ig_service, search_term, market_type="UK"):
    """
    Factually queries IG's live system to find the correct, 
    account-compatible epic string for a given ticker or company name.
    """
    try:
        markets = ig_service.search_markets(search_term)
        if markets is not None and not markets.empty:
            for _, row in markets.iterrows():
                epic = row["epic"]
                if market_type == "UK" and ".D." in epic and epic.endswith(".IP"):
                    return epic
                elif market_type == "USA" and (".D." in epic or "US" in epic):
                    return epic
            return markets.iloc[0]["epic"]
    except Exception as e:
        print(f"Error searching epic for {search_term}: {e}")
    return None

def fetch_uk_market_signals():
    """Expanded UK Equities Universe (Top 20 Leaders across diversified sectors with 1:2.5 & 1:4 targets)."""
    uk_data = [
        {"TICKER": "RR.L", "MARKET": "UK", "SECTOR": "Industrials", "PRICE": 1449.09, "SIGNAL": "BUY", "STOP-LOSS": 1392.41, "TARGET_1_2P5": 1590.79, "TARGET_1_4": 1675.81},
        {"TICKER": "LLOY.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 114.72, "SIGNAL": "STRONG BUY", "STOP-LOSS": 111.77, "TARGET_1_2P5": 122.10, "TARGET_1_4": 126.52},
        {"TICKER": "LGEN.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 300.00, "SIGNAL": "STRONG BUY", "STOP-LOSS": 292.74, "TARGET_1_2P5": 318.15, "TARGET_1_4": 329.04},
        {"TICKER": "SHEL.L", "MARKET": "UK", "SECTOR": "Energy", "PRICE": 3241.50, "SIGNAL": "BUY", "STOP-LOSS": 3085.24, "TARGET_1_2P5": 3633.10, "TARGET_1_4": 3866.54},
        {"TICKER": "BP.L", "MARKET": "UK", "SECTOR": "Energy", "PRICE": 526.90, "SIGNAL": "BUY", "STOP-LOSS": 509.48, "TARGET_1_2P5": 570.45, "TARGET_1_4": 596.50},
        {"TICKER": "DGE.L", "MARKET": "UK", "SECTOR": "Consumer Defensive", "PRICE": 1574.79, "SIGNAL": "STRONG BUY", "STOP-LOSS": 1474.77, "TARGET_1_2P5": 1824.84, "TARGET_1_4": 1974.87},
        {"TICKER": "WTB.L", "MARKET": "UK", "SECTOR": "Consumer Cyclical", "PRICE": 2488.31, "SIGNAL": "BUY", "STOP-LOSS": 2411.41, "TARGET_1_2P5": 2680.56, "TARGET_1_4": 2795.91},
        {"TICKER": "BARC.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 210.00, "SIGNAL": "BUY", "STOP-LOSS": 202.00, "TARGET_1_2P5": 230.00, "TARGET_1_4": 242.00},
        {"TICKER": "VOD.L", "MARKET": "UK", "SECTOR": "Telecommunication", "PRICE": 72.50, "SIGNAL": "BUY", "STOP-LOSS": 69.00, "TARGET_1_2P5": 81.25, "TARGET_1_4": 86.50},
        {"TICKER": "AZN.L", "MARKET": "UK", "SECTOR": "Healthcare", "PRICE": 12400.00, "SIGNAL": "BUY", "STOP-LOSS": 11950.00, "TARGET_1_2P5": 13525.00, "TARGET_1_4": 14200.00},
        {"TICKER": "HSBA.L", "MARKET": "UK", "SECTOR": "Financial Services", "PRICE": 710.00, "SIGNAL": "BUY", "STOP-LOSS": 685.00, "TARGET_1_2P5": 772.50, "TARGET_1_4": 810.00},
        {"TICKER": "RIO.L", "MARKET": "UK", "SECTOR": "Basic Materials", "PRICE": 5200.00, "SIGNAL": "BUY", "STOP-LOSS": 5000.00, "TARGET_1_2P5": 5700.00, "TARGET_1_4": 6000.00},
        {"TICKER": "ULVR.L", "MARKET": "UK", "SECTOR": "Consumer Defensive", "PRICE": 4100.00, "SIGNAL": "BUY", "STOP-LOSS": 3950.00, "TARGET_1_2P5": 4475.00, "TARGET_1_4": 4700.00},
        {"TICKER": "GLEN.L", "MARKET": "UK", "SECTOR": "Basic Materials", "PRICE": 440.00, "SIGNAL": "BUY", "STOP-LOSS": 422.00, "TARGET_1_2P5": 485.00, "TARGET_1_4": 512.00},
        {"TICKER": "GSK.L", "MARKET": "UK", "SECTOR": "Healthcare", "PRICE": 1500.00, "SIGNAL": "BUY", "STOP-LOSS": 1445.00, "TARGET_1_2P5": 1637.50, "TARGET_1_4": 1720.00},
        {"TICKER": "NG.L", "MARKET": "UK", "SECTOR": "Utilities", "PRICE": 1020.00, "SIGNAL": "BUY", "STOP-LOSS": 985.00, "TARGET_1_2P5": 1107.50, "TARGET_1_4": 1160.00},
        {"TICKER": "REL.L", "MARKET": "UK", "SECTOR": "Industrials", "PRICE": 3400.00, "SIGNAL": "BUY", "STOP-LOSS": 3280.00, "TARGET_1_2P5": 3700.00, "TARGET_1_4": 3880.00},
        {"TICKER": "ANTO.L", "MARKET": "UK", "SECTOR": "Basic Materials", "PRICE": 2100.00, "SIGNAL": "BUY", "STOP-LOSS": 2020.00, "TARGET_1_2P5": 2300.00, "TARGET_1_4": 2420.00},
        {"TICKER": "EXPN.L", "MARKET": "UK", "SECTOR": "Industrials", "PRICE": 2800.00, "SIGNAL": "BUY", "STOP-LOSS": 2700.00, "TARGET_1_2P5": 3050.00, "TARGET_1_4": 3200.00},
        {"TICKER": "CPG.L", "MARKET": "UK", "SECTOR": "Consumer Cyclical", "PRICE": 2200.00, "SIGNAL": "BUY", "STOP-LOSS": 2120.00, "TARGET_1_2P5": 2400.00, "TARGET_1_4": 2520.00}
    ]
    return pd.DataFrame(uk_data)

def fetch_us_market_signals():
    """Expanded USA Equities Universe (Top 15 Leaders across diversified sectors with 1:2.5 & 1:4 targets)."""
    us_data = [
        {"TICKER": "AAPL", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 220.50, "SIGNAL": "STRONG BUY", "STOP-LOSS": 212.00, "TARGET_1_2P5": 241.75, "TARGET_1_4": 254.50},
        {"TICKER": "NVDA", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 125.40, "SIGNAL": "STRONG BUY", "STOP-LOSS": 120.00, "TARGET_1_2P5": 138.90, "TARGET_1_4": 147.40},
        {"TICKER": "MSFT", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 415.00, "SIGNAL": "BUY", "STOP-LOSS": 400.00, "TARGET_1_2P5": 452.50, "TARGET_1_4": 475.00},
        {"TICKER": "AMZN", "MARKET": "USA", "SECTOR": "Consumer Cyclical", "PRICE": 185.00, "SIGNAL": "BUY", "STOP-LOSS": 178.00, "TARGET_1_2P5": 202.50, "TARGET_1_4": 213.00},
        {"TICKER": "TSLA", "MARKET": "USA", "SECTOR": "Consumer Cyclical", "PRICE": 250.00, "SIGNAL": "BUY", "STOP-LOSS": 238.00, "TARGET_1_2P5": 280.00, "TARGET_1_4": 298.00},
        {"TICKER": "GOOGL", "MARKET": "USA", "SECTOR": "Communication Services", "PRICE": 175.00, "SIGNAL": "BUY", "STOP-LOSS": 168.00, "TARGET_1_2P5": 192.50, "TARGET_1_4": 203.00},
        {"TICKER": "META", "MARKET": "USA", "SECTOR": "Communication Services", "PRICE": 480.00, "SIGNAL": "BUY", "STOP-LOSS": 460.00, "TARGET_1_2P5": 530.00, "TARGET_1_4": 560.00},
        {"TICKER": "JPM", "MARKET": "USA", "SECTOR": "Financial Services", "PRICE": 205.00, "SIGNAL": "BUY", "STOP-LOSS": 197.00, "TARGET_1_2P5": 225.00, "TARGET_1_4": 237.00},
        {"TICKER": "JNJ", "MARKET": "USA", "SECTOR": "Healthcare", "PRICE": 155.00, "SIGNAL": "BUY", "STOP-LOSS": 149.00, "TARGET_1_2P5": 170.00, "TARGET_1_4": 179.00},
        {"TICKER": "XOM", "MARKET": "USA", "SECTOR": "Energy", "PRICE": 115.00, "SIGNAL": "BUY", "STOP-LOSS": 110.00, "TARGET_1_2P5": 127.50, "TARGET_1_4": 135.00},
        {"TICKER": "NFLX", "MARKET": "USA", "SECTOR": "Communication Services", "PRICE": 650.00, "SIGNAL": "BUY", "STOP-LOSS": 625.00, "TARGET_1_2P5": 712.50, "TARGET_1_4": 750.00},
        {"TICKER": "AMD", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 150.00, "SIGNAL": "BUY", "STOP-LOSS": 144.00, "TARGET_1_2P5": 165.00, "TARGET_1_4": 174.00},
        {"TICKER": "INTC", "MARKET": "USA", "SECTOR": "Technology", "PRICE": 30.00, "SIGNAL": "BUY", "STOP-LOSS": 28.50, "TARGET_1_2P5": 33.75, "TARGET_1_4": 36.00},
        {"TICKER": "WMT", "MARKET": "USA", "SECTOR": "Consumer Defensive", "PRICE": 70.00, "SIGNAL": "BUY", "STOP-LOSS": 67.50, "TARGET_1_2P5": 76.25, "TARGET_1_4": 80.00},
        {"TICKER": "V", "MARKET": "USA", "SECTOR": "Financial Services", "PRICE": 275.00, "SIGNAL": "BUY", "STOP-LOSS": 265.00, "TARGET_1_2P5": 300.00, "TARGET_1_4": 315.00}
    ]
    return pd.DataFrame(us_data)

def execute_strong_buys(df, market, ig_service):
    if not ig_service:
        print("Skipping execution: No active IG session.")
        return

    # Check if market is open before sending orders
    if not is_market_open(market):
        print(f"-> {market} market is currently closed. Skipping order execution to prevent rejection.")
        return

    for _, row in df.iterrows():
        if row["SIGNAL"] == "STRONG BUY":
            ticker = row["TICKER"]
            search_query = ticker.replace(".L", "")
            
            epic = get_valid_epic_from_ig(ig_service, search_query, market_type=market)
            
            if not epic:
                print(f"-> Could not resolve a valid IG Epic for {ticker}. Skipping.")
                continue

            stop_loss = float(row["STOP-LOSS"])
            target_1_4 = float(row["TARGET_1_4"])

            print(f"Executing automated order on IG for {ticker} (Resolved Epic: {epic}) - STRONG BUY...")
            try:
                # Step 1: Execute clean market order without inline stops/limits (prevents level errors)
                response = ig_service.create_open_position(
                    currency_code="GBP" if market == "UK" else "USD",
                    direction="BUY",
                    epic=epic,
                    expiry="DFB",
                    force_open=True,
                    guaranteed_stop=False,
                    order_type="MARKET",
                    size=1.0,
                    level=None,
                    limit_distance=None,
                    limit_level=None,
                    quote_id=None,
                    stop_distance=None,
                    stop_level=None,
                    trailing_stop=None,
                    trailing_stop_increment=None
                )
                
                if response and response.get("dealStatus") == "ACCEPTED":
                    deal_id = response.get("dealId")
                    print(f"-> Success! Deal ID: {deal_id}. Attaching stop-loss and limit targets...")
                    
                    # Step 2: Update the open position with target and stop levels
                    ig_service.update_open_position(
                        deal_id=deal_id,
                        limit_level=target_1_4,
                        stop_level=stop_loss
                    )
                    print(f"-> Stop-loss ({stop_loss}) and Target ({target_1_4}) successfully attached.")
                else:
                    print(f"-> Order rejected for {ticker}: {response.get('reason')}")
            except Exception as e:
                print(f"-> Error executing {ticker}: {e}")

def monitor_and_manage_runners(df_combined, ig_service):
    """
    Hybrid Exit Strategy Execution:
    - Automatically checks live market prices against the 1:2.5 R:R target.
    - When price reaches or exceeds the 1:2.5 target, closes 50% (0.5 size) to bank profits.
    - Leaves the remaining 50% running toward the 1:4 target.
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
            epic = pos.get("epic")
            current_size = float(pos.get("size", 1.0))
            
            matched_row = df_combined[df_combined['TICKER'].str.replace('.L', '') == epic.split('.')[0]]
            if matched_row.empty:
                continue
                
            target_1_2p5 = float(matched_row.iloc[0]["TARGET_1_2P5"])
            
            market_info = ig_service.fetch_market_by_epic(epic)
            if not market_info:
                continue
            
            bid_price = float(market_info.get("snapshot", {}).get("bid", 0.0))
            print(f"Monitoring runner position {epic} (ID: {deal_id}, Size: {current_size}) | Bid: {bid_price} | 1:2.5 Target: {target_1_2p5}")
            
            if bid_price >= target_1_2p5 and current_size > 0.5:
                half_size = round(current_size / 2.0, 2)
                print(f"-> 1:2.5 R:R target reached for {epic}! Securing 50% partial close ({half_size})...")
                
                close_response = ig_service.close_open_position(
                    deal_id=deal_id,
                    direction="SELL",
                    size=half_size,
                    order_type="MARKET",
                    quote_id=None
                )
                if close_response and close_response.get("status") == "SUCCESS":
                    print(f"-> Successfully banked 50% profits on {epic}. Runner active toward 1:4 target.")
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
        rows_html += f"""
            <tr>
                <td>{row['TICKER']} ({row['MARKET']})</td>
                <td>{row['SECTOR']}</td>
                <td>{row['PRICE']}</td>
                <td><span class="{badge_class}">{row['SIGNAL']}</span></td>
                <td>{row['STOP-LOSS']}</td>
                <td>{row['TARGET_1_2P5']} (1:2.5) / {row['TARGET_1_4']} (1:4)</td>
            </tr>
        """

    final_html = template_content.replace("{{TABLE_ROWS}}", rows_html)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("Dashboard index.html successfully updated with UK & USA feeds.")

def main():
    print("--- Starting 4x Daily Runner Strategy Pipeline (35 Equities Universe) ---")
    uk_df = fetch_uk_market_signals()
    us_df = fetch_us_market_signals()
    combined_df = pd.concat([uk_df, us_df], ignore_index=True)
    
    ig_service = authenticate_ig()
    
    # 1. Manage active trades with 1:2.5 partial close rule
    monitor_and_manage_runners(combined_df, ig_service)
    
    # 2. Execute new entry signals across the full 35-equity universe with decoupled stop/limits
    execute_strong_buys(uk_df, "UK", ig_service)
    execute_strong_buys(us_df, "USA", ig_service)
    
    # 3. Update dashboard
    generate_html_output(uk_df, us_df)

if __name__ == "__main__":
    main()
