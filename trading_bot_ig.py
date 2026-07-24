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

# Quantitative Risk Settings
MAX_RISK_PER_TRADE_GBP = 75.0  
MAX_POSITIONS_PER_SECTOR = 2
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


def get_volatility_regime_adjustments(ig_service, epic):
    """
    Volatility Regime Filtering: Determines market state based on recent high-low spread 
    vs historical range, adapting trailing steps and target multipliers dynamically.
    """
    try:
        hist = ig_service.fetch_historical_prices_by_epic_and_num_points(epic=epic, resolution="D", num_points=10)
        prices_df = hist.get("prices")
        if prices_df is not None and not prices_df.empty:
            highs = prices_df["highPrice"]["ask"].astype(float)
            lows = prices_df["lowPrice"]["ask"].astype(float)
            recent_range = (highs - lows).mean()
            baseline_range = (highs - lows).median()
            
            if recent_range > (baseline_range * 1.25):
                return {"regime": "EXPANDED_TREND", "target_mult": 2.0, "trailing_increment": 8}
            elif recent_range < (baseline_range * 0.8):
                return {"regime": "COMPRESSED_RANGE", "target_mult": 1.2, "trailing_increment": 3}
    except Exception:
        pass
    
    return {"regime": "NORMAL", "target_mult": 1.5, "trailing_increment": 5}


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

    print("\n=== EXECUTING NOISE-PROTECTED REGIME TRADES ===")
    for c in candidates:
        ticker = c["Ticker"]
        sector = c["Sector"]
        atr_points = c["ATR_Points"]

        if sector_counts.get(sector, 0) >= MAX_POSITIONS_PER_SECTOR:
            print(f"🛡️ Sector Limit Reached: {sector} already active. Skipping {ticker}.")
            continue

        epic = resolve_ig_epic(ig_service, ticker)
        if not epic:
            print(f"❌ Skipped {ticker}: Could not resolve IG Epic.")
            continue

        regime_data = get_volatility_regime_adjustments(ig_service, epic)
        regime = regime_data["regime"]
        target_mult = regime_data["target_mult"]
        trailing_inc = regime_data["trailing_increment"]

        # AMELIORATION: Increased stop buffer from 1.0 to 1.5 ATR to avoid noise stop-outs
        stop_distance = round(atr_points * 1.5, 1)
        target_distance = round(atr_points * target_mult, 1)

        try:
            market_details = ig_service.fetch_market_by_epic(epic)
            snapshot = market_details.get("snapshot", {})
            current_spread = float(snapshot.get("offer", 0)) - float(snapshot.get("bid", 0))
            max_allowed_spread = stop_distance * 0.12  
            
            if current_spread > max_allowed_spread:
                print(f"⚠️ Skipped {ticker}: Spread ({current_spread} pts) exceeds 12% limit of ATR stop ({stop_distance} pts).")
                continue
        except Exception as e:
            print(f"⚠️ Spread check warning for {ticker}: {e}")

        calculated_size = round(MAX_RISK_PER_TRADE_GBP / stop_distance, 2)
        is_uk = ticker.endswith(".L")
        min_size = 0.1 if is_uk else 0.5
        total_stake = max(calculated_size, min_size)

        safe_split_threshold = min_size * 2

        if total_stake < safe_split_threshold:
            print(f"🚀 Executing Safeguarded Single-Lot Order on {ticker} [{epic}] | Wide Stop: {stop_distance} pts")
            try:
                response = ig_service.create_open_position(
                    currency_code="GBP", direction="BUY", epic=epic, expiry="-", force_open=True,
                    guaranteed_stop=False, order_type="MARKET", size=total_stake, level=None,
                    limit_distance=None, limit_level=None, quote_id=None,
                    stop_distance=stop_distance, stop_level=None,
                    # AMELIORATION: Disabled immediate trailing stop to let the trade breathe
                    trailing_stop=False, trailing_stop_increment=None
                )
                deal_ref = response.get("dealReference", "N/A")
                print(f"✅ Order Accepted (Static Stop Buffer Active) | Ref: {deal_ref}")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                
                log_trade({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ticker": ticker, "epic": epic, "sector": sector,
                    "regime": regime, "strategy": "Static Buffer Stop (Noise Protected)", 
                    "stake": total_stake, "stop_distance": stop_distance, "deal_reference": deal_ref
                })
            except Exception as e:
                print(f"❌ Execution failed for {ticker}: {e}")
        else:
            tranche_size = round(total_stake / 2, 2)
            print(f"🚀 Executing Split-Lot Hybrid Strategy on {ticker} [{epic}] | Regime: {regime}")
            
            ref1, ref2 = None, None
            try:
                resp1 = ig_service.create_open_position(
                    currency_code="GBP", direction="BUY", epic=epic, expiry="-", force_open=True,
                    guaranteed_stop=False, order_type="MARKET", size=tranche_size, level=None,
                    limit_distance=target_distance, limit_level=None, quote_id=None,
                    stop_distance=stop_distance, stop_level=None,
                    trailing_stop=False, trailing_stop_increment=None
                )
                ref1 = resp1.get("dealReference", "N/A")
                print(f"   └─ Leg 1 (Target @ {target_distance} pts) Ref: {ref1}")
            except Exception as e:
                print(f"   ❌ Leg 1 failed: {e}")

            try:
                resp2 = ig_service.create_open_position(
                    currency_code="GBP", direction="BUY", epic=epic, expiry="-", force_open=True,
                    guaranteed_stop=False, order_type="MARKET", size=tranche_size, level=None,
                    limit_distance=None, limit_level=None, quote_id=None,
                    stop_distance=stop_distance, stop_level=None,
                    trailing_stop=False, trailing_stop_increment=None
                )
                ref2 = resp2.get("dealReference", "N/A")
                print(f"   └─ Leg 2 (Static Buffer Protection) Ref: {ref2}")
                
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                
                log_trade({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ticker": ticker, "epic": epic, "sector": sector,
                    "regime": regime, "strategy": "Split-Lot Hybrid (Noise Protected)", 
                    "tranche_stake": tranche_size, "deal_references": [ref1, ref2]
                })
            except Exception as e:
                print(f"   ❌ Leg 2 failed: {e}")

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    execute_trades()
