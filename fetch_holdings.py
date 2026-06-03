import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf

def download_top_20(ticker_symbol):
    print(f"Initializing data pull for {ticker_symbol}...")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    })
    
    # 1. Fetch current top holdings
    try:
        ticker = yf.Ticker(ticker_symbol, session=session)
        holdings_df = ticker.funds_data.holdings
        if holdings_df is None or holdings_df.empty:
            raise ValueError("Yahoo Finance returned an empty dataset.")
    except Exception as e:
        print(f"Primary fetch bypassed ({e}). Trying alternative layout extraction...")
        url = f"https://stockanalysis.com{ticker_symbol.lower()}/holdings/"
        try:
            response = session.get(url, timeout=15)
            tables = pd.read_html(response.text)
            holdings_df = tables[0]
        except Exception as fallback_err:
            print(f"Critical Failure: All data streams blocked. {fallback_err}")
            return

    holdings_df = holdings_df.head(20)
    symbol_col = 'Symbol' if 'Symbol' in holdings_df.columns else holdings_df.columns[0]
    
    # 2. Extract historical anchor data safely
    print("Gathering reference price data matrix...")
    try:
        benchmark_hist = yf.download(ticker_symbol, period="1y", interval="1wk", session=session)
        if isinstance(benchmark_hist.columns, pd.MultiIndex):
            benchmark_hist = benchmark_hist['Close'][ticker_symbol]
        else:
            benchmark_hist = benchmark_hist['Close']
    except Exception as b_err:
        print(f"Could not load historical baseline: {b_err}")
        return
        
    relative_strength_list = []
    rel_momentum_list = []
    change_of_mom_list = []
    
    for comp in holdings_df[symbol_col]:
        symbol_str = str(comp).strip()
        try:
            asset_hist = yf.download(symbol_str, period="1y", interval="1wk", session=session)
            if isinstance(asset_hist.columns, pd.MultiIndex):
                asset_hist = asset_hist['Close'][symbol_str]
            else:
                asset_hist = asset_hist['Close']
                
            merged = pd.DataFrame({'Asset': asset_hist, 'Benchmark': benchmark_hist}).dropna()
            
            if len(merged) >= 27:
                merged['RS'] = merged['Asset'] / merged['Benchmark']
                merged['RM'] = 10 * (merged['RS'] - merged['RS'].shift(26))
                merged['CM'] = 100 * (merged['RM'] - merged['RM'].shift(1))
                
                relative_strength_list.append(round(float(merged['RS'].iloc[-1]), 4))
                rel_momentum_list.append(round(float(merged['RM'].iloc[-1]), 4))
                change_of_mom_list.append(round(float(merged['CM'].iloc[-1]), 4))
            else:
                relative_strength_list.append(np.nan)
                rel_momentum_list.append(np.nan)
                change_of_mom_list.append(np.nan)
        except Exception:
            relative_strength_list.append(np.nan)
            rel_momentum_list.append(np.nan)
            change_of_mom_list.append(np.nan)

    # Attach structural data arrays
    holdings_df['relative_strength'] = relative_strength_list
    holdings_df['rel_Momntum'] = rel_momentum_list
    holdings_df['Change_of_Mom'] = change_of_mom_list

    runtime_str = datetime.now().strftime("%Y-%m-%d")
    holdings_df['Snapshot_Date'] = runtime_str
    
    os.makedirs("holdings_history", exist_ok=True)
    holdings_df.to_csv(f"holdings_history/{ticker_symbol}_top20_{runtime_str}.csv", index=False)
    holdings_df.to_csv(f"{ticker_symbol}_top20_latest.csv", index=False)
    print("Process complete. Saved files generated successfully.")

if __name__ == "__main__":
    download_top_20("SPMO")
