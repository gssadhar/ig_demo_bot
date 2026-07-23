import os
import sys
import json
import pandas as pd
from trading_ig import IGService

# ==========================================
# 1. LOAD CREDENTIALS FROM ENVIRONMENT
# ==========================================
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = "DEMO"

# EXPANDED EPIC Lookup Table mapped to Sector Categories
EPIC_MAP = {
    # --- TECH & GROWTH ---
    "AAPL":     {"epic": "UC.D.AAPL.DAILY.IP",  "sector": "Tech"},
    "MSFT":     {"epic": "UC.D.MSFT.DAILY.IP",  "sector": "Tech"},
    "NVDA":     {"epic": "UC.D.NVDA.DAILY.IP",  "sector": "Tech"},
    "GOOGL":    {"epic": "UC.D.GOOGL.DAILY.IP", "sector": "Tech"},
    "AMZN":     {"epic": "UC.D.AMZN.DAILY.IP",  "sector": "Tech"},
    "META":     {"epic": "UC.D.META.DAILY.IP",  "sector": "Tech"},
    "ALAW.L":   {"epic": "SE.D.ALAW.DAILY.IP",  "sector": "Tech"},      # Alphawave Semi
    "ALGM":     {"epic": "UC.D.ALGM.DAILY.IP",  "sector": "Tech"},      # Allegro Micro
    "LRCX":     {"epic": "UC.D.LRCX.DAILY.IP",  "sector": "Tech"},      # Lam Research
    
    # --- INDUSTRIALS & AEROSPACE ---
    "RR.L":     {"epic": "SE.D.RR.DAILY.IP",    "sector": "Industrials"}, # Rolls Royce
    "OXIG.L":   {"epic": "SE.D.OXIG.DAILY.IP",  "sector": "Industrials"}, # Oxford Instruments
    "CPI.L":    {"epic": "SE.D.CPI.DAILY.IP",   "sector": "Industrials"}, # Capita
    "SNA":      {"epic": "UC.D.SNA.DAILY.IP",   "sector": "Industrials"}, # Snap-on
    "PPG":      {"epic": "UC.D.PPG.DAILY.IP",   "sector": "Industrials"}, # PPG Industries
    
    # --- MATERIALS & MINING ---
    "GLEN.L":   {"epic": "SE.D.GLEN.DAILY.IP",  "sector": "Materials"},  # Glencore
    "TGA.L":    {"epic": "SE.D.TGA.DAILY.IP",   "sector": "Materials"},  # Thungela
    
    # --- HEALTHCARE & PHARMA ---
    "AZN.L":    {"epic": "SE.D.AZN.DAILY.IP",   "sector": "Healthcare"},
    "GSK.L":    {"epic": "SE.D.GSK.DAILY.IP",   "sector": "Healthcare"},
    "ROG.SW":   {"epic": "LX.D.ROG.DAILY.IP",   "sector": "Healthcare"}, # Roche
    "SPI.L":    {"epic": "SE.D.SPI.DAILY.IP",   "sector": "Healthcare"}, # Spire Healthcare
    
    # --- ENERGY ---
    "SHEL.L":   {"epic": "SE.D.SHEL.DAILY.IP",  "sector": "Energy"},
    "BP.L":     {"epic": "SE.D.BP.DAILY.IP",    "sector": "Energy"},
    "ITH.L":    {"epic": "SE.D.ITH.DAILY.IP",   "sector": "Energy"},     # Ithaca Energy
    
    # --- FINANCIALS & ADVISORY ---
    "HSBC.L":   {"epic": "SE.D.HSBC.DAILY.IP",  "sector": "Financials"},
    "LGEN.L":   {"epic": "SE.D.LGEN.DAILY.IP",  "sector": "Financials"}, # Legal & General
    "FRP.L":    {"epic": "SE.D.FRP.DAILY.IP",   "sector": "Financials"}, # FRP Advisory
    
    # --- CONSUMER & SERVICES ---
    "EZJ.L":    {"epic": "SE.D.EZJ.DAILY.IP",   "sector": "Consumer"},   # easyJet
    "JDW.L":    {"epic": "SE.D.JDW.DAILY.IP",   "sector": "Consumer"},   # JD Wetherspoon
    "DGE.L":    {"epic": "SE.D.DGE.DAILY.IP",   "sector": "Consumer"},   # Diageo
    "NIO":      {"epic": "UC.D.NIO.DAILY.IP",   "sector": "Consumer"},   # Nio Inc
    
    # --- TELECOM ---
    "BT-A.L":   {"epic": "SE.D.BT.DAILY.IP",    "sector": "Telecom"},    # BT Group
    "VOD.L":    {"epic": "SE.D.VOD.DAILY.IP",   "sector": "Telecom"}     # Vodafone
}

# Risk Parameters
MAX_POSITIONS_PER_SECTOR = 2
RISK_PCT_PER_TRADE = 0.01   # Risk 1% of available cash
DEFAULT_STOP_DISTANCE = 20  # 20 points stop-loss


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
        print(f"⚠️ Could not fetch live balance via API: {e}")
    return 20000.0


def calculate_stake_size(available_cash, stop_loss_points=20):
    risk_amount = available_cash * RISK_PCT_PER_TRADE
    stake = risk_amount / stop_loss_points
    max_stake = 5.0  # Cap at £5/point
    return max(min(round(stake, 2), max_stake), 0.50)


def count_sector_positions(open_positions):
    sector_counts = {}
    if isinstance(open_positions, pd.DataFrame) and not open_positions.empty and "epic" in open_positions.columns:
        active_epics = open_positions["epic"].tolist()
        for ticker, data in EPIC_MAP.items():
            if data["epic"] in active_epics:
                sec = data["sector"]
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
    return sector_counts


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
    
    print("⚠️ Warning: top_candidates.json not found or invalid. No trades executed.")
    return []


def execute_ig_trade(ig_service, ticker, epic, sector, open_positions, sector_counts, available_cash):
    # 1. Prevent duplicate position entries
    if isinstance(open_positions, pd.DataFrame) and not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Active position already exists for {ticker} ({epic}). Skipping.")
            return

    # 2. Enforce Sector Concentration Cap
    current_sector_trades = sector_counts.get(sector, 0)
    if current_sector_trades >= MAX_POSITIONS_PER_SECTOR:
        print(f"🛡️ Sector Limit Reached: {sector} already has {current_sector_trades} active trades. Skipping {ticker}.")
        return

    stake_size = calculate_stake_size(available_cash, stop_loss_points=DEFAULT_STOP_DISTANCE)
    
    print(f"🚀 Placing BUY Trade on {ticker} ({sector}) @ £{stake_size}/point...")
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
            stop_distance=DEFAULT_STOP_DISTANCE,
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
    sector_counts = count_sector_positions(open_positions)
    
    candidates = load_screener_candidates()
    if not candidates:
        print("🛑 Execution halt: No candidates passed from screener.")
        return

    print("\n=== EXECUTING IG SPREAD BET TRADES FROM SCREENER ===")
    
    for item in candidates:
        ticker = item.get("Ticker")
        signal = item.get("Signal", "HOLD")
        
        # Only execute on clear actionable buy signals from screener
        if signal not in ["BUY", "STRONG BUY"]:
            print(f"⏩ Skipping {ticker}: Signal is {signal}")
            continue

        meta = EPIC_MAP.get(ticker)
        if not meta:
            print(f"⚠️ Skipped {ticker}: Missing IG EPIC mapping. Add to EPIC_MAP.")
            continue
            
        epic = meta["epic"]
        sector = meta["sector"]
        
        execute_ig_trade(ig_service, ticker, epic, sector, open_positions, sector_counts, available_cash)

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    run_bot()
