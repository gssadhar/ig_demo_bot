import os
import sys
import pandas as pd
from trading_ig import IGService

# Read credentials from GitHub environment secrets
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
IG_API_KEY = os.environ.get("IG_API_KEY")
IG_ACC_TYPE = "DEMO"

def authenticate_ig():
    try:
        ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
        ig_service.create_session()
        print("Successfully authenticated with IG API via GitHub Actions.")
        return ig_service
    except Exception as e:
        print(f"IG Authentication failed: {e}")
        return None

def fetch_market_signals():
    # Your quantitative signal scanner logic
    data = [
        {"TICKER": "RR.L", "SECTOR": "Industrials", "PRICE": 1449.09, "SIGNAL": "BUY", "STOP-LOSS": 1392.41, "1.5R TARGET": 1534.11},
        {"TICKER": "LLOY.L", "SECTOR": "Financial Services", "PRICE": 114.72, "SIGNAL": "STRONG BUY", "STOP-LOSS": 111.77, "1.5R TARGET": 119.15},
        {"TICKER": "LGEN.L", "SECTOR": "Financial Services", "PRICE": 300.00, "SIGNAL": "STRONG BUY", "STOP-LOSS": 292.74, "1.5R TARGET": 310.90},
        {"TICKER": "SHEL.L", "SECTOR": "Energy", "PRICE": 3241.50, "SIGNAL": "BUY", "STOP-LOSS": 3085.24, "1.5R TARGET": 3475.89},
        {"TICKER": "BP.L", "SECTOR": "Energy", "PRICE": 526.90, "SIGNAL": "BUY", "STOP-LOSS": 509.48, "1.5R TARGET": 553.03},
        {"TICKER": "DGE.L", "SECTOR": "Consumer Defensive", "PRICE": 1574.79, "SIGNAL": "STRONG BUY", "STOP-LOSS": 1474.77, "1.5R TARGET": 1724.82},
        {"TICKER": "WTB.L", "SECTOR": "Consumer Cyclical", "PRICE": 2488.31, "SIGNAL": "BUY", "STOP-LOSS": 2411.41, "1.5R TARGET": 2603.65}
    ]
    return pd.DataFrame(data)

def execute_strong_buys(df, ig_service):
    if not ig_service:
        print("Skipping execution: No active IG session.")
        return

    for _, row in df.iterrows():
        if row["SIGNAL"] == "STRONG BUY":
            epic = row["TICKER"]
            print(f"Executing automated order on IG for {epic} (STRONG BUY)...")
            try:
                response = ig_service.create_open_position(
                    currency_code="GBP",
                    direction="BUY",
                    epic=epic,
                    expiry="DFB",
                    force_open="true",
                    guaranteed_stop="false",
                    order_type="MARKET",
                    size="0.5",
                    stop_level=str(row["STOP-LOSS"]),
                    limit_level=str(row["1.5R TARGET"])
                )
                if response and response.get("dealStatus") == "ACCEPTED":
                    print(f"-> Success! Deal ID: {response.get('dealId')}")
                else:
                    print(f"-> Order rejected for {epic}: {response.get('reason')}")
            except Exception as e:
                print(f"-> Error executing {epic}: {e}")

def generate_html_output(df):
    template_path = "template.html"
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        rows_html = ""
        for _, row in df.iterrows():
            badge_class = "strong-buy-badge" if row["SIGNAL"] == "STRONG BUY" else "buy-badge"
            rows_html += f"""
                <tr>
                    <td>{row['TICKER']}</td>
                    <td>{row['SECTOR']}</td>
                    <td>{row['PRICE']}</td>
                    <td><span class="{badge_class}">{row['SIGNAL']}</span></td>
                    <td>{row['STOP-LOSS']}</td>
                    <td>{row['1.5R TARGET']}</td>
                </tr>
            """
        final_html = template_content.replace("{{TABLE_ROWS}}", rows_html)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(final_html)

def main():
    df_signals = fetch_market_signals()
    ig_service = authenticate_ig()
    execute_strong_buys(df_signals, ig_service)
    generate_html_output(df_signals)

if __name__ == "__main__":
    main()
