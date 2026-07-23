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

# Hybrid Quantitative Risk Settings
MAX_RISK_PER_TRADE_GBP = 75.0  
MAX_POSITIONS_PER_SECTOR = 2
INITIAL_STOP_ATR_MULT = 1.0    
PARTIAL_TARGET_ATR_MULT = 1.5  
TRAILING_STOP_INCREMENT = 5    
LOG_FILE = "trade_log.json"


def connect_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Missing IG Environment Variables!")
        return None
    try:
        ig_service = IGService(
            username=IG_USERNAME, password=IG_PASSWORD,
            api_key=IG_API_KEY, acc_type=IG_ACC_TYPE.upper(),
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
    print(f"📜 Hybrid trade logged to {LOG_FILE}")


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

    print("\n=== EXECUTING AMELIORATED HYBRID QUANTITATIVE TRADES ===")
    for c in candidates:
        ticker = c["Ticker"]
        sector = c["Sector"]
        atr_points = c["ATR_Points"]

        if sector_counts.get(sector, 0) >= MAX_POSITIONS_PER_SECTOR:
            print(f"🛡️ Sector Limit Reached: {sector} already has active limit. Skipping {ticker}.")
            continue

        epic = resolve_ig_epic(ig_service, ticker)
        if not epic:
            print(f"❌ Skipped {ticker}: Could not resolve IG Epic.")
            continue

        stop_distance = round(atr_points * INITIAL_STOP_ATR_MULT, 1)
        target_distance = round(atr_points * PARTIAL_TARGET_ATR_MULT, 1)

        calculated_size = round(MAX_RISK_PER_TRADE_GBP / stop_distance, 2)
        is_uk = ticker.endswith(".L")
        min_size = 0.1 if is_uk else 0.5
        total_stake = max(calculated_size, min_size)

        # Ameliorated Safeguard: Only split if total stake is at least DOUBLE the broker minimum
        # This completely prevents broker rejections from sub-minimum fractional splits.
        safe_split_threshold = min_size * 2

        if total_stake < safe_split_threshold:
            print(f"🚀 Executing Safe Single-Lot Trailing Order on {ticker} [{epic}] (Stake: £{total_stake}/pt matches minimum floor)")
            try:
                response = ig_service.create_open_position(
                    currency_code="GBP", direction="BUY", epic=epic, expiry="-", force_open=True,
                    guaranteed_stop=False, order_type="MARKET", size=total_stake, level=None,
                    limit_distance=None, limit_level=None, quote_id=None,
                    stop_distance=stop_distance, stop_level=None,
                    trailing_stop=True, trailing_stop_increment=TRAILING_STOP_INCREMENT
                )
                deal_ref = response.get("dealReference", "N/A")
                print(f"✅ Order Accepted | Ref: {deal_ref}")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                log_trade({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ticker": ticker, "epic": epic, "sector": sector,
                    "strategy": "Single-Lot Trailing (Safeguarded)", "stake": total_stake,
                    "stop_distance": stop_distance, "deal_reference": deal_ref
                })
            except Exception as e:
                print(f"❌ Execution failed for {ticker}: {e}")
        else:
            tranche_size = round(total_stake / 2, 2)
            print(f"🚀 Executing True Split-Lot Hybrid Strategy on {ticker} [{epic}] (Total Stake: £{total_stake}/pt)")
            
            try:
                resp1 = ig_service.create_open_position(
                    currency_code="GBP", direction="BUY", epic=epic, expiry="-", force_open=True,
                    guaranteed_stop=False, order_type="MARKET", size=tranche_size, level=None,
                    limit_distance=target_distance, limit_level=None, quote_id=None,
                    stop_distance=stop_distance, stop_level=None,
                    trailing_stop=False, trailing_stop_increment=None
                )
                ref1 = resp1.get("dealReference", "N/A")
                print(f"   └─ Leg 1 (Fixed Target @ {target_distance} pts) Ref: {ref1}")
            except Exception as e:
                print(f"   ❌ Leg 1 failed: {e}")
                ref1 = None

            try:
                resp2 = ig_service.create_open_position(
                    currency_code="GBP", direction="BUY", epic=epic, expiry="-", force_open=True,
                    guaranteed_stop=False, order_type="MARKET", size=tranche_size, level=None,
                    limit_distance=None, limit_level=None, quote_id=None,
                    stop_distance=stop_distance, stop_level=None,
                    trailing_stop=True, trailing_stop_increment=TRAILING_STOP_INCREMENT
                )
                ref2 = resp2.get("dealReference", "N/A")
                print(f"   └─ Leg 2 (Trailing Stop Rider) Ref: {ref2}")
                
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                
                log_trade({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ticker": ticker, "epic": epic, "sector": sector,
                    "strategy": "Split-Lot Hybrid (Fixed + Trailing)", "tranche_stake": tranche_size,
                    "stop_distance": stop_distance, "target_distance": target_distance,
                    "deal_references": [ref1, ref2]
                })
            except Exception as e:
                print(f"   ❌ Leg 2 failed: {e}")

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    execute_trades()
