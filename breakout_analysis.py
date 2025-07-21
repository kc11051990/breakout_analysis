import pandas as pd
import yfinance as yf
import numpy as np
import ta
from datetime import datetime

# === CONFIGURATION ===
LENGTH = 14
MULTIPLIER = 1.0
START_DATE = "2020-01-01"
END_DATE = datetime.today().strftime('%Y-%m-%d')
SYMBOLS_FILE = "nifty500.xlsx"

# === PERSISTENT STORAGE ===
breakout_signals = []
computed_data = []
all_trading_dates = set()
resistance_levels = []
support_levels = []


# === Helper Functions ===
def is_pivot_high(highs, idx, length):
    if idx < length or idx + length >= len(highs):
        return False
    return highs[idx] == max(highs[idx - length: idx + length + 1])


def is_pivot_low(lows, idx, length):
    if idx < length or idx + length >= len(lows):
        return False
    return lows[idx] == min(lows[idx - length: idx + length + 1])


def process_symbol(symbol):
    global resistance_levels, support_levels
    try:
        df = yf.download(symbol, start=START_DATE, end=END_DATE, progress=False, auto_adjust=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            return

        df['SMA_Volume'] = df['Volume'].rolling(window=20).mean()
        df['Volume_%_of_SMA'] = ((df['Volume'] - df['SMA_Volume']) / df['SMA_Volume']) * 100

        df['Date'] = pd.to_datetime(df.index)
        df.reset_index(drop=True, inplace=True)
        all_trading_dates.update(df['Date'].dt.strftime('%d-%b-%Y'))

        # === Compute True Range (TR) and ATR ===
        df['TR'] = np.nan
        for i in range(len(df)):
            if i == 0:
                df.at[i, 'TR'] = df['High'][i] - df['Low'][i]
            else:
                hl = df['High'][i] - df['Low'][i]
                hc = abs(df['High'][i] - df['Close'][i - 1])
                lc = abs(df['Low'][i] - df['Close'][i - 1])
                df.at[i, 'TR'] = max(hl, hc, lc)

        df['ATR'] = df['TR'].rolling(window=LENGTH).mean()
        df['Slope'] = df['ATR'] / LENGTH * MULTIPLIER

        upper = lower = np.nan
        slope_ph = slope_pl = 0
        ph_row = pl_row = None

        for i in range(len(df)):
            if is_pivot_high(df['High'], i, LENGTH):
                upper = df['High'][i]
                slope_ph = df['Slope'][i]
                ph_row = i
            if is_pivot_low(df['Low'], i, LENGTH):
                lower = df['Low'][i]
                slope_pl = df['Slope'][i]
                pl_row = i

            df.at[i, 'UpperTrend'] = upper - slope_ph * (i - ph_row) if pd.notna(upper) and ph_row is not None else np.nan
            df.at[i, 'LowerTrend'] = lower + slope_pl * (i - pl_row) if pd.notna(lower) and pl_row is not None else np.nan

            breakout_type = price_breakout_type = breakout_strength = None
            open_price = df['Open'][i]
            high = df['High'][i]
            low = df['Low'][i]
            close = df['Close'][i]
            date_str = df['Date'].iloc[i].strftime('%d-%b-%Y')
            uptrend = df['UpperTrend'][i] * (1 + 0.005)
            downtrend = df['LowerTrend'][i] * (1 - 0.005)
            volume_pct = df['Volume_%_of_SMA'][i]

            if i > 0:
                prev_upper = df['UpperTrend'][i - 1] * (1 + 0.005)
                prev_lower = df['LowerTrend'][i - 1] * (1 - 0.005)
                prev_close = df['Close'][i - 1]
            else:
                prev_upper = uptrend
                prev_lower = downtrend
                prev_close = close

            if is_pivot_high(df['High'], i, LENGTH):
                level = df['High'][i]
                if not any(abs(level - r) < 0.01 * r for r in resistance_levels):
                    resistance_levels.append(level)

            if is_pivot_low(df['Low'], i, LENGTH):
                level = df['Low'][i]
                if not any(abs(level - s) < 0.01 * s for s in support_levels):
                    support_levels.append(level)

            if pd.notna(volume_pct) and volume_pct > 50:
                for r in resistance_levels:
                    if close > r:
                        price_breakout_type = "Bullish Price Breakout"
                        break
                for s in support_levels:
                    if close < s:
                        price_breakout_type = "Bearish Price Breakdown"
                        break

                if pd.notna(uptrend) and pd.notna(prev_upper) and close > uptrend and prev_close < prev_upper and i - ph_row > LENGTH:
                    breakout_type = "Bullish Breakout"
                    breakout_strength = ((close - uptrend) / uptrend) * 100 if uptrend != 0 else np.nan
                elif pd.notna(downtrend) and pd.notna(prev_lower) and close < downtrend and prev_close > prev_lower and i - pl_row > LENGTH:
                    breakout_type = "Bearish Breakout"
                    breakout_strength = ((downtrend - close) / downtrend) * 100 if downtrend != 0 else np.nan

                if breakout_type or price_breakout_type:
                    breakout_signals.append({
                        'Symbol': symbol,
                        'Date': date_str,
                        'Open': round(open_price, 5),
                        'Close': round(close, 5),
                        'Trendline': round(uptrend, 5) if pd.notna(uptrend) else "",
                        'Trend_Breakout': breakout_type if breakout_type else "",
                        'Price_Breakout': price_breakout_type if price_breakout_type else "",
                        'Breakout Strength': round(breakout_strength, 2) if breakout_strength else "",
                        'Volume % of SMA': round(volume_pct, 2) if not pd.isna(volume_pct) else np.nan
                    })

            computed_data.append({
                'Symbol': symbol,
                'Date': date_str,
                'Open': round(open_price, 5),
                'High': round(high, 5),
                'Low': round(low, 5),
                'Close': round(close, 5),
                'TR': round(df['TR'][i], 5),
                'ATR': round(df['ATR'][i], 5) if not pd.isna(df['ATR'][i]) else np.nan,
                'Slope': round(df['Slope'][i], 8) if not pd.isna(df['Slope'][i]) else np.nan,
                'Pivot High': is_pivot_high(df['High'], i, LENGTH),
                'Pivot Low': is_pivot_low(df['Low'], i, LENGTH),
                'Upper Trend': round(uptrend, 5) if pd.notna(uptrend) else np.nan,
                'Lower Trend': round(downtrend, 5) if pd.notna(downtrend) else np.nan,
                'Trend_Breakout': breakout_type if breakout_type else "",
                'Price_Breakout': price_breakout_type if price_breakout_type else "",
                'Breakout Strength (%)': round(breakout_strength, 2) if breakout_strength else "",
                'Volume % of SMA': round(volume_pct, 2) if not pd.isna(volume_pct) else np.nan
            })

    except Exception as e:
        print(f"❌ Error processing {symbol}: {e}")


# === Entry Point ===
def run():
    symbols_df = pd.read_excel(SYMBOLS_FILE)
    symbols = symbols_df['Symbol'].dropna().unique().tolist()

    for symbol in symbols:
        process_symbol(symbol)

    recent_dates = sorted(list(all_trading_dates), key=lambda d: datetime.strptime(d, '%d-%b-%Y'))[-10:]
    recent_signals = [s for s in breakout_signals if s['Date'] in recent_dates]

    df_breakouts = pd.DataFrame(recent_signals)
    df_computed = pd.DataFrame(computed_data)

    df_breakouts.to_excel("Breakout_Signals.xlsx", index=False)
    df_computed.to_excel("Breakout_Computed_Data.xlsx", index=False)

    return "Breakout_Signals.xlsx"
