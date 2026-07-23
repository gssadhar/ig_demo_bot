import os
import json
import logging
from datetime import datetime, timezone
from trading_ig import IGService

# Setup Logging
logging.basicConfig(level=logging.INFO)

# IG Credentials
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = os.getenv("IG_ACC_TYPE") or "DEMO"

# Risk Management Settings
MAX_RISK_PER_TRADE_GBP = 75.0  # Max £ amount to lose per trade
MAX_POSITIONS_PER_SECTOR = 2
REWARD_RISK_RATIO = 2.0        # 2:1 Reward to Risk (Take-Profit = 2x ATR)
LOG_FILE = "trade_log.json"


def connect_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Missing IG Environment Variables!")
        return None
    try:
        ig_service = IGService(
            username=IG_USERNAME,
            password=IG_PASSWORD,
            api_key=IG_API_KEY,
            acc_type=IG_ACC_TYPE.upper(),
            acc_number=IG_ACC_NUMBER
        )
        ig_service.create_session()
        print(f"⚡ Connected to IG API successfully ({IG_ACC_TYPE.upper()} Mode)!")
        return ig_service
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def resolve_ig_epic(ig_service, ticker):
    clean_symbol = ticker.replace(".L", "").strip().upper()
    try:
        search_results = ig_service.search_markets(clean_symbol)
        if hasattr(search_results, "iterrows"):
            for _, row in search_results.iterrows():
                epic = str(row.get("epic", ""))
                itype = str(row.get("instrumentType", ""))
                if "SHARES" in itype and ("DAILY" in epic or "DFB" in epic):
                    return epic
            if not search_results.empty:
                return search_results.iloc[0].get("epic")
    except Exception as e:
        print(f"⚠️ Dynamic search error for {ticker}: {e}")
    return None


def log_trade(trade_data):
    """
    Appends successful trade records to trade_log.json for audit and analysis.
    """
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        except Exception:
            logs = []

    logs.append(trade_data)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)
    print(f"📜 Trade logged to {LOG_FILE}")


def execute_trades():
    if not os.path.exists("top_candidates.json"):
        print("⚠️ No top_candidates.json file found.")
        return

    with open("top_candidates.json", "r") as f:
        candidates = json.load(f)

    if not candidates:
        print("ℹ️ Candidates list is empty.")
        return

    ig_service = connect_ig()
    if not ig_service:
        return

    accounts = ig_service.fetch_accounts()
    if hasattr(accounts, "iterrows"):
        balance = accounts.iloc[0].get("available", 0)
        print(f"💰 Current Available Capital: £{balance:,.2f}")

    sector_counts = {}

    print("\n=== EXECUTING IG SPREAD BET TRADES ===")
    for c in candidates:
        ticker = c["Ticker"]
        sector = c["Sector"]
        stop_distance = c["ATR_Points"]
        
        # Calculate Take-Profit distance (2x Stop Distance)
        limit_distance = round(stop_distance * REWARD_RISK_RATIO, 1)

        # Enforce sector limits
        if sector_counts.get(sector, 0) >= MAX_POSITIONS_PER_SECTOR:
            print(f"🛡️ Sector Limit Reached: {sector} already has {MAX_POSITIONS_PER_SECTOR} active trades. Skipping {ticker}.")
            continue

        epic = resolve_ig_epic(ig_service, ticker)
        if not epic:
            print(f"❌ Skipped {ticker}: Could not resolve IG Epic.")
            continue

        # Position Sizing
        calculated_size = round(MAX_RISK_PER_TRADE_GBP / stop_distance, 2)
        is_uk = ticker.endswith(".L")
        min_size = 0.1 if is_uk else 0.5
        stake_size = max(calculated_size, min_size)

        print(f"🚀 Submitting BUY order on {ticker} [{epic}]")
        print(f"   └─ Stake: £{stake_size}/pt | Stop Loss: {stop_distance} pts | Take Profit: {limit_distance} pts")

        try:
            response = ig_service.create_open_position(
                currency_code="GBP",
                direction="BUY",
                epic=epic,
                expiry="-",
                force_open=True,
                guaranteed_stop=False,
                order_type="MARKET",
                size=stake_size,
                level=None,
                limit_distance=limit_distance,  # Sets automated Take-Profit
                limit_level=None,
                quote_id=None,
                stop_distance=stop_distance,   # Sets automated Stop-Loss
                stop_level=None,
                trailing_stop=False,
                trailing_stop_increment=None
            )
            
            deal_ref = response.get("dealReference", "N/A")
            print(f"✅ Order Submitted for {ticker} | Ref: {deal_ref}")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

            # Save to JSON log
            log_trade({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "epic": epic,
                "sector": sector,
                "stake_gbp_per_point": stake_size,
                "stop_distance_pts": stop_distance,
                "take_profit_pts": limit_distance,
                "deal_reference": deal_ref
            })

        except Exception as e:
            print(f"❌ Trade execution failed for {ticker}: {e}")

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    execute_trades()
