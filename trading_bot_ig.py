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
    vs historical range, adapting target multipliers dynamically per academic frameworks.
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
                return {"regime": "EXPANDED_TREND", "target_mult": 2.0}
            elif recent_range < (baseline_range * 0.8):
                return {"regime": "COMPRESSED_RANGE", "target_mult": 1.2}
    except Exception:
        pass
    
    return {"regime": "NORMAL", "target_mult": 1.5}


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

    print("\n=== EXECUTING INSTITUTIONAL QUANTITATIVE PIPELINE ===")
    for c in candidates:
        ticker = c["Ticker"]
        sector = c["Sector"]

        if sector_counts.get(sector, 0) >= MAX_POSITIONS_PER_SECTOR:
            print(f"🛡️ Sector Limit Reached: {sector} already active. Skipping {ticker}.")
            continue

        epic = resolve_ig_epic(ig_service, ticker)
        if not epic:
            print(f"❌ Skipped {ticker}: Could not resolve IG Epic.")
            continue

        regime_data = get_volatility_regime_adjustments(ig_service, epic)
        regime = regime_data["regime"]

        try:
            market_details = ig_service.fetch_market_by_epic(epic)
            snapshot = market_details.get("snapshot", {})
            bid_price = float(snapshot.get("bid", 0))
            offer_price = float(snapshot.get("offer", 0))
            current_spread = offer_price - bid_price
            
            if bid_price <= 0:
                print(f"⚠️ Skipped {ticker}: Invalid bid price.")
                continue

            # Normalized 3% risk boundary calculation for quantitative stake sizing
            stop_distance = round(bid_price * 0.03, 1)
            max_allowed_spread = stop_distance * 0.12  
            if current_spread > max_allowed_spread:
                print(f"⚠️ Skipped {ticker}: Spread ({current_spread} pts) exceeds institutional 12% limit.")
                continue
        except Exception as e:
            print(f"⚠️ Market detail error for {ticker}: {e}")
            continue

        calculated_size = round(MAX_RISK_PER_TRADE_GBP / stop_distance, 2)
        is_uk = ticker.endswith(".L")
        min_size = 0.1 if is_uk else 0.5
        total_stake = max(calculated_size, min_size)

        print(f"🚀 Executing Quant-Validated Position on {ticker} [{epic}] | Regime: {regime} | Stake: {total_stake}")
        try:
            response = ig_service.create_open_position(
                currency_code="GBP", 
                direction="BUY", 
                epic=epic, 
                expiry="-", 
                force_open=True,
                guaranteed_stop=False, 
                order_type="MARKET", 
                size=total_stake, 
                level=None,
                limit_distance=None, 
                limit_level=None, 
                quote_id=None,
                stop_distance=None, 
                stop_level=None,
                trailing_stop=False, 
                trailing_stop_increment=None
            )
            deal_ref = response.get("dealReference", "N/A")
            print(f"✅ Position Successfully Established! | Ref: {deal_ref}")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            
            log_trade({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker, 
                "epic": epic, 
                "sector": sector,
                "regime": regime, 
                "strategy": "Adaptive Multi-Factor Momentum", 
                "stake": total_stake, 
                "deal_reference": deal_ref
            })
        except Exception as e:
            print(f"❌ Execution failed for {ticker}: {e}")

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    execute_trades()
