import os
import sys
import json
import pandas as pd
from trading_ig import IGService

# Environment Credentials
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = "DEMO"

# Risk & Execution Controls
MAX_POSITIONS_PER_SECTOR = 2
RISK_PCT_PER_TRADE = 0.01   # Risk 1% of total cash per trade
DEFAULT_STOP_DISTANCE = 20  # Default fallback stop loss


def connect_to_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials in environment variables.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    
    try:
        ig_service.switch_account(IG_ACC_NUMBER, False)
        print(f"✅ Active Account ID: {IG_ACC_NUMBER}")
    except Exception as e:
        print(f"ℹ️ Account notice: {e}")

    return ig_service


def get_account_balance(ig_service):
    try:
        accounts = ig_service.fetch_accounts()
        if isinstance(accounts, pd.DataFrame) and not accounts.empty:
            for _, acc in accounts.iterrows():
                if acc.get("accountId") == IG_ACC_NUMBER or len(accounts) == 1:
                    balance_info = acc.get("balance", {})
                    available_cash = balance_info.get("available", 0) if isinstance(balance_info, dict) else acc.get("available", 0)
                    print(f"💰 Current Available Capital: £{float(available_cash):,.2f}")
                    return float(available_cash)
    except Exception as e:
        print(f"⚠️ Could not fetch balance via API: {e}")
    return 20000.0


def resolve_ig_epic(ig_service, ticker):
    """
    Dynamically searches IG API to find the exact active Spread Bet Epic.
    """
    clean_symbol = ticker.replace(".L", "").strip().upper()
    try:
        search_results = ig_service.search_markets(clean_symbol)
        
        # Parse results DataFrame or Dict from trading_ig
        if hasattr(search_results, "iterrows"):
            for _, row in search_results.iterrows():
                epic = str(row.get("epic", ""))
                itype = str(row.get("instrumentType", ""))
                if "SHARES" in itype and ("DAILY" in epic or "DFB" in epic):
                    return epic
            return search_results.iloc[0].get("epic") if not search_results.empty else None
            
    except Exception as e:
        print(f"⚠️ Search failed for {ticker}: {e}")
    return None


def calculate_stake_size(available_cash, stop_loss_points=20):
    risk_amount = available_cash * RISK_PCT_PER_TRADE
    stake = risk_amount / stop_loss_points
    max_stake = 5.0  # Cap at £5/point
    return max(min(round(stake, 2), max_stake), 0.50)


def load_screener_candidates():
    filename = "top_candidates.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                candidates = json.load(f)
                print(f"📋 Loaded {len(candidates)} candidates from {filename}.")
                return candidates
        except Exception as e:
            print(f"⚠️ Error reading {filename}: {e}")
    
    print("⚠️ Warning: top_candidates.json not found or invalid.")
    return []


def execute_ig_trade(ig_service, item, open_positions, sector_counts, available_cash):
    ticker = item.get("Ticker")
    sector = item.get("Sector", "General")
    atr_points = item.get("ATR_Points", DEFAULT_STOP_DISTANCE)
    
    epic = resolve_ig_epic(ig_service, ticker)
    if not epic:
        print(f"❌ Skipped {ticker}: Could not resolve IG Epic.")
        return

    # Duplicate check
    if isinstance(open_positions, pd.DataFrame) and not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Active position already exists for {ticker} ({epic}). Skipping.")
            return

    # Sector Concentration check
    if sector_counts.get(sector, 0) >= MAX_POSITIONS_PER_SECTOR:
        print(f"🛡️ Sector Limit Reached: {sector} already has {sector_counts.get(sector, 0)} active trades. Skipping {ticker}.")
        return

    stop_dist = atr_points if atr_points and atr_points >= 10 else DEFAULT_STOP_DISTANCE
    stake_size = calculate_stake_size(available_cash, stop_loss_points=stop_dist)
    
    print(f"🚀 Placing BUY Trade on {ticker} ({sector}) [Epic: {epic}] @ £{stake_size}/point (Stop: {stop_dist} pts)...")
    try:
        response = ig_service.create_open_position(
            currency_code="GBP",
            direction="BUY",
            epic=epic,
            expiry="DFB",
            force_open=True,
            guaranteed_stop=False,
            level=None,
            limit_distance=None,
            limit_level=None,
            order_type="MARKET",
            quote_id=None,
            size=stake_size,
            stop_distance=int(stop_dist),
            stop_level=None,
            trailing_stop=True,
            trailing_stop_increment=1.0
        )
        deal_ref = response.get("dealReference", "Success") if isinstance(response, dict) else "Executed"
        print(f"✅ Order executed for {ticker} | Ref: {deal_ref}")
        
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    except Exception as e:
        print(f"❌ Trade execution failed for {ticker}: {e}")


def run_bot():
    ig_service = connect_to_ig()
    available_cash = get_account_balance(ig_service)
    
    open_positions = ig_service.fetch_open_positions()
    sector_counts = {}
    
    candidates = load_screener_candidates()
    if not candidates:
        print("🛑 Execution halt: No candidates passed from screener.")
        return

    print("\n=== EXECUTING IG SPREAD BET TRADES FROM SCREENER ===")
    
    for item in candidates:
        signal = item.get("Signal", "HOLD")
        if signal not in ["BUY", "STRONG BUY"]:
            print(f"⏩ Skipping {item.get('Ticker')}: Signal is {signal}")
            continue
            
        execute_ig_trade(ig_service, item, open_positions, sector_counts, available_cash)

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    run_bot()
