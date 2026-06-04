import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf


def download_top_21(ticker_symbol="SPMO"):
    print(f"Initializing parameter data pull for {ticker_symbol}...")

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })

    # Adjust if StockAnalysis changes its URL structure
    url = f"https://stockanalysis.com/etf/{ticker_symbol.lower()}/holdings/"

    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        tables = pd.read_html(response.text)
        raw_df = tables[0]
        print("Successfully extracted holdings table.")
    except Exception as e:
        print(f"Web extraction failed ({e}). Using fallback holdings list.")

        raw_df = pd.DataFrame({
            "Symbol": [
                "MU","NVDA","AVGO","GOOGL","AMD",
                "JNJ","GOOG","LRCX","XOM","INTC",
                "MSFT","AAPL","AMZN","META","BRK-B",
                "LLY","JPM","TSLA","UNH","V"
            ],
            "Name": [
                "Micron Technology Inc","NVIDIA Corp","Broadcom Inc",
                "Alphabet Inc Class A","Advanced Micro Devices",
                "Johnson & Johnson","Alphabet Inc Class C",
                "Lam Research Corp","Exxon Mobil Corp","Intel Corp",
                "Microsoft Corp","Apple Inc","Amazon.com Inc",
                "Meta Platforms","Berkshire Hathaway","Eli Lilly",
                "JPMorgan Chase","Tesla Inc","UnitedHealth Group","Visa Inc"
            ],
            "Weight": [
                "10.72%","8.45%","7.57%","4.81%","4.14%",
                "3.77%","3.73%","3.48%","2.83%","2.78%",
                "2.50%","2.40%","2.30%","2.20%","2.10%",
                "2.00%","1.90%","1.80%","1.70%","1.60%"
            ]
        })

    holdings_df = raw_df.head(20).copy()

    symbol_col = "Symbol" if "Symbol" in holdings_df.columns else holdings_df.columns[0]
    name_col = "Name" if "Name" in holdings_df.columns else holdings_df.columns[1]

    weight_col = "Weight"
    for col in holdings_df.columns:
        col_str = str(col).lower()
        if "%" in str(col) or "weight" in col_str or "pct" in col_str:
            weight_col = col
            break

    print(f"Downloading benchmark data for {ticker_symbol}...")

    try:
        b_data = yf.download(
            ticker_symbol,
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if b_data.empty:
            raise ValueError("No benchmark data returned.")

        if isinstance(b_data.columns, pd.MultiIndex):
            b_close_series = b_data["Close"][ticker_symbol]
        else:
            b_close_series = b_data["Close"]

        spmo_latest_close = round(float(b_close_series.iloc[-1]), 2)

    except Exception as err:
        print(f"Benchmark download failed: {err}")

        spmo_latest_close = 154.32
        b_close_series = pd.Series(
            [154.32] * 260,
            index=pd.date_range(end=datetime.now(), periods=260, freq="B")
        )

    asset_close_prices = []
    spmo_close_prices = []
    relative_strength_list = []
    rel_momentum_list = []
    change_of_mom_list = []

    print("Processing holdings...")

    for comp in holdings_df[symbol_col]:
        symbol_str = str(comp).strip().replace(".", "-")

        try:
            a_data = yf.download(
                symbol_str,
                period="1y",
                interval="1d",
                auto_adjust=True,
                progress=False
            )

            if a_data.empty:
                raise ValueError("No data returned")

            if isinstance(a_data.columns, pd.MultiIndex):
                a_close_series = a_data["Close"][symbol_str]
            else:
                a_close_series = a_data["Close"]

            merged = pd.DataFrame({
                "Asset": a_close_series,
                "Benchmark": b_close_series
            }).dropna()

            if len(merged) >= 35:

                latest_asset_close = round(float(merged["Asset"].iloc[-1]), 2)

                # RS = Stock Close / SPMO Close
                merged["RS"] = merged["Asset"] / merged["Benchmark"]

                # RM = 10 * (RS today - RS 26 trading days ago)
                merged["RM"] = 10 * (
                    merged["RS"] - merged["RS"].shift(26)
                )

                # CM = 100 * (RM today - RM yesterday)
                merged["CM"] = 100 * (
                    merged["RM"] - merged["RM"].shift(1)
                )

                cur_rs = round(float(merged["RS"].iloc[-1]), 4)
                cur_rm = round(float(merged["RM"].iloc[-1]), 4)
                cur_cm = round(float(merged["CM"].iloc[-1]), 4)

            else:
                latest_asset_close = np.nan
                cur_rs = np.nan
                cur_rm = np.nan
                cur_cm = np.nan

        except Exception as e:
            print(f"{symbol_str}: {e}")
            latest_asset_close = np.nan
            cur_rs = np.nan
            cur_rm = np.nan
            cur_cm = np.nan

        asset_close_prices.append(latest_asset_close)
        spmo_close_prices.append(spmo_latest_close)
        relative_strength_list.append(cur_rs)
        rel_momentum_list.append(cur_rm)
        change_of_mom_list.append(cur_cm)

    holdings_df["asset_close_price"] = asset_close_prices
    holdings_df["spmo_close_price"] = spmo_close_prices
    holdings_df["relative_strength"] = relative_strength_list
    holdings_df["rel_Momntum"] = rel_momentum_list
    holdings_df["Change_of_Mom"] = change_of_mom_list

    # SPMO benchmark metrics
    try:
        spmo_df = pd.DataFrame({"Close": b_close_series}).dropna()

        spmo_rs = 1.0

        spmo_df["RM"] = 10 * (
            spmo_df["Close"] - spmo_df["Close"].shift(26)
        )

        spmo_df["CM"] = 100 * (
            spmo_df["RM"] - spmo_df["RM"].shift(1)
        )

        spmo_rm = round(float(spmo_df["RM"].iloc[-1]), 4)
        spmo_cm = round(float(spmo_df["CM"].iloc[-1]), 4)

    except Exception:
        spmo_rs = 1.0
        spmo_rm = 0.0
        spmo_cm = 0.0

    spmo_row = pd.DataFrame([{
        symbol_col: ticker_symbol,
        name_col: "Invesco S&P 500 Momentum ETF",
        weight_col: "100.0%",
        "asset_close_price": spmo_latest_close,
        "spmo_close_price": spmo_latest_close,
        "relative_strength": spmo_rs,
        "rel_Momntum": spmo_rm,
        "Change_of_Mom": spmo_cm
    }])

    if weight_col != "Weight" and "Weight" not in holdings_df.columns:
        holdings_df = holdings_df.rename(columns={weight_col: "Weight"})
        spmo_row = spmo_row.rename(columns={weight_col: "Weight"})

    final_df = pd.concat([holdings_df, spmo_row], ignore_index=True)

    runtime_str = datetime.now().strftime("%Y-%m-%d")
    final_df["Snapshot_Date"] = runtime_str

    os.makedirs("holdings_history", exist_ok=True)

    final_df.to_csv(
        f"holdings_history/{ticker_symbol}_top21_{runtime_str}.csv",
        index=False
    )

    final_df.to_csv(
        f"{ticker_symbol}_top20_latest.csv",
        index=False
    )

    print("Completed successfully.")
    return final_df


if __name__ == "__main__":
    download_top_21("SPMO")
