import os
import json
import logging
import time
from trading_ig import IGService

# Setup Logging
logging.basicConfig(level=logging.INFO)

# IG Credentials
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = os.getenv("IG_ACC_TYPE", "DEMO")  # Set to 'LIVE' for real account

# Risk Management Settings
MAX_RISK_PER_TRADE_GBP = 75.0  # Max £ amount to lose per trade
MAX_POSITIONS_PER_SECTOR = 2


def connect_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Missing IG Environment Variables!")
        return None
    try:
        ig_service = IGService(
            username=IG_USERNAME,
            password=IG_PASSWORD,
            api_key=IG_API_KEY,
            acc_type=IG_ACC_TYPE,
            acc_number=IG_ACC_NUMBER
        )
        ig_service.create_session()
        print("⚡ Connected to IG API successfully!")
        return ig_service
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def resolve_ig_epic(ig_service, ticker):
    """
    Dynamically searches IG API to resolve active Spread Bet Epics.
    """
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

    # Check available funds
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

        # Enforce sector diversification
        if sector_counts.get(sector, 0) >= MAX_POSITIONS_PER_SECTOR:
            print(f"🛡️ Sector Limit Reached: {sector} already has {MAX_POSITIONS_PER_SECTOR} active trades. Skipping {ticker}.")
            continue

        epic = resolve_ig_epic(ig_service, ticker)
        if not epic:
            print(f"❌ Skipped {ticker}: Could not resolve IG Epic.")
            continue

        # Dynamic Sizing Logic: Risk £75 max per trade
        calculated_size = round(MAX_RISK_PER_TRADE_GBP / stop_distance, 2)
        
        # Enforce IG minimum stake constraints
        is_uk = ticker.endswith(".L")
        min_size = 0.1 if is_uk else 0.5
        stake_size = max(calculated_size, min_size)

        print(f"🚀 Submitting BUY order on {ticker} [{epic}] | Stop: {stop_distance} pts | Stake: £{stake_size}/pt...")

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
                limit_distance=None,
                limit_level=None,
                quote_id=None,
                stop_distance=stop_distance,
                stop_level=None,
                trailing_stop=False,
                trailing_stop_increment=None
            )
            
            deal_ref = response.get("dealReference", "N/A")
            
            # Brief pause to allow IG's order engine to process
            time.sleep(1)
            
            # Fetch deal confirmation to verify execution status
            confirm = ig_service.fetch_deal_confirmation(deal_ref)
            deal_status = confirm.get("dealStatus")
            reason = confirm.get("reason", "SUCCESS")

            if deal_status == "ACCEPTED":
                print(f"✅ Position OPENED for {ticker} | Ref: {deal_ref}")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
            else:
                print(f"🚫 Order REJECTED for {ticker} | Reason: {reason}")

        except Exception as e:
            print(f"❌ Trade execution failed for {ticker}: {e}")

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    execute_trades()
