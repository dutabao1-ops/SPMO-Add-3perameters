import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf

def download_top_20(ticker_symbol):
    print(f"Fetching structural components for {ticker_symbol}...")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    # 1. Fetch current top holdings
    try:
        ticker = yf.Ticker(ticker_symbol, session=session)
        holdings_df = ticker.funds_data.holdings
        if holdings_df is None or holdings_df.empty:
            raise ValueError("No direct dataset returned.")
    except Exception as e:
        print(f"Primary fetch failed ({e}). Shifting to alternative web extractor...")
        url = f"https://stockanalysis.com{ticker_symbol.lower()}/holdings/"
        try:
            response = session.get(url, timeout=15)
            holdings_df = pd.read_html(response.text)[0]
        except Exception as fallback_err:
            print(f"Critical Timeout: Source un-extractable. {fallback_err}")
            return

    # Filter to top 20 lines
    holdings_df = holdings_df.head(20)
    
    # Standardize column naming based on source format (usually 'Symbol' or 'Ticker')
    symbol_col = 'Symbol' if 'Symbol' in holdings_df.columns else holdings_df.columns[0]
    
    # 2. Extract historical anchor data for calculations (27 weeks minimum needed)
    print("Downloading historical reference blocks...")
    # Fetch benchmark historical series
    benchmark_hist = yf.download(ticker_symbol, period="1y", interval="1wk", session=session)['Close']
    
    relative_strength_list = []
    rel_momentum_list = []
    change_of_mom_list = []
    
    for comp in holdings_df[symbol_col]:
        try:
            # Download asset history
            asset_hist = yf.download(str(comp).strip(), period="1y", interval="1wk", session=session)['Close']
            
            # Align time frames with benchmark via an intersection dataframe
            merged = pd.DataFrame({'Asset': asset_hist, 'Benchmark': benchmark_hist}).dropna()
            
            if len(merged) >= 27:
                # Calculate Relative Strength series
                merged['RS'] = merged['Asset'] / merged['Benchmark']
                # Calculate Relative Momentum (Shift 26 periods)
                merged['RM'] = 10 * (merged['RS'] - merged['RS'].shift(26))
                # Calculate Change of Momentum (Shift 1 period)
                merged['CM'] = 100 * (merged['RM'] - merged['RM'].shift(1))
                
                # Append the latest terminal array values
                relative_strength_list.append(round(float(merged['RS'].iloc[-1]), 4))
                rel_momentum_list.append(round(float(merged['RM'].iloc[-1]), 4))
                change_of_mom_list.append(round(float(merged['CM'].iloc[-1]), 4))
            else:
                relative_strength_list.append(np.nan)
                rel_momentum_list.append(np.nan)
                change_of_mom_list.append(np.nan)
        except Exception as err:
            print(f"Failed math matrix compilation for {comp}: {err}")
            relative_strength_list.append(np.nan)
            rel_momentum_list.append(np.nan)
            change_of_mom_list.append(np.nan)

    # Attach computed variables to CSV layout
    holdings_df['relative_strength'] = relative_strength_list
    holdings_df['rel_Momntum'] = rel_momentum_list
    holdings_df['Change_of_Mom'] = change_of_mom_list

    runtime_str = datetime.now().strftime("%Y-%m-%d")
    holdings_df['Snapshot_Date'] = runtime_str
    
    os.makedirs("holdings_history", exist_ok=True)
    file_path = f"holdings_history/{ticker_symbol}_top20_{runtime_str}.csv"
    holdings_df.to_csv(file_path, index=False)
    holdings_df.to_csv(f"{ticker_symbol}_top20_latest.csv", index=False)
    print(f"Successfully committed metrics to {file_path}")

if __name__ == "__main__":
    TARGET_TICKER = "SPMO" 
    download_top_20(TARGET_TICKER)
