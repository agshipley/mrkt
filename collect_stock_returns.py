"""
Collect acquirer stock returns around deal announcement.
Uses Yahoo Finance (free, no API key needed).
Calculates cumulative abnormal returns vs S&P 500.
"""

import json
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path


def get_stock_return(ticker, announcement_date, window_days):
    """
    Calculate stock return over a window starting from announcement date.
    Returns the stock return and the S&P 500 return over the same period.
    """
    try:
        start = datetime.strptime(announcement_date, '%Y-%m-%d')
        # Pull a few days before for the pre-announcement price
        fetch_start = start - timedelta(days=5)
        fetch_end = start + timedelta(days=window_days + 5)

        stock = yf.download(ticker, start=fetch_start.strftime('%Y-%m-%d'),
                           end=fetch_end.strftime('%Y-%m-%d'), progress=False)
        sp500 = yf.download('^GSPC', start=fetch_start.strftime('%Y-%m-%d'),
                           end=fetch_end.strftime('%Y-%m-%d'), progress=False)

        if stock.empty or sp500.empty:
            return None, None, None

        # Find the closest trading day on or before announcement
        pre_dates = stock.index[stock.index <= start.strftime('%Y-%m-%d')]
        if len(pre_dates) == 0:
            return None, None, None
        pre_date = pre_dates[-1]

        # Find the closest trading day on or after announcement + window
        target_end = start + timedelta(days=window_days)
        post_dates = stock.index[stock.index >= target_end.strftime('%Y-%m-%d')]
        if len(post_dates) == 0:
            return None, None, None
        post_date = post_dates[0]

        # Stock return
        pre_price = float(stock.loc[pre_date]['Close'].iloc[0]) if hasattr(stock.loc[pre_date]['Close'], 'iloc') else float(stock.loc[pre_date]['Close'])
        post_price = float(stock.loc[post_date]['Close'].iloc[0]) if hasattr(stock.loc[post_date]['Close'], 'iloc') else float(stock.loc[post_date]['Close'])
        stock_return = (post_price - pre_price) / pre_price * 100

        # S&P 500 return over same period
        sp_pre = float(sp500.loc[pre_date]['Close'].iloc[0]) if hasattr(sp500.loc[pre_date]['Close'], 'iloc') else float(sp500.loc[pre_date]['Close'])
        sp_post = float(sp500.loc[post_date]['Close'].iloc[0]) if hasattr(sp500.loc[post_date]['Close'], 'iloc') else float(sp500.loc[post_date]['Close'])
        sp_return = (sp_post - sp_pre) / sp_pre * 100

        # Abnormal return = stock return - market return
        abnormal_return = stock_return - sp_return

        return stock_return, sp_return, abnormal_return

    except Exception as e:
        return None, None, None


def main():
    with open('data/deal_outcomes.json') as f:
        outcomes = json.load(f)

    with open('data/deal_metadata.json') as f:
        metadata = json.load(f)

    # Load existing results to allow resuming
    output_path = 'data/stock_returns.json'
    if Path(output_path).exists():
        with open(output_path) as f:
            returns = json.load(f)
        print(f"Resuming: {len(returns)} already collected")
    else:
        returns = {}

    remaining = {k: v for k, v in outcomes.items() if k not in returns}
    print(f"Total deals: {len(outcomes)}")
    print(f"Remaining: {len(remaining)}")
    print()

    for i, (contract_id, outcome) in enumerate(sorted(remaining.items(),
            key=lambda x: int(x[0].split('_')[1]))):

        ticker = outcome.get('acquirer_ticker')
        signing_date = metadata.get(contract_id, {}).get('signing_date')

        if not ticker or not signing_date or signing_date.startswith('<'):
            print(f"[{i+1:>3}/{len(remaining)}] {contract_id}: SKIPPED (missing ticker or date)")
            returns[contract_id] = {
                'ticker': ticker,
                'error': 'missing ticker or date'
            }
            # Save after each
            with open(output_path, 'w') as f:
                json.dump(returns, f, indent=2)
            continue

        print(f"[{i+1:>3}/{len(remaining)}] {contract_id}: {ticker} ({signing_date})...", end="", flush=True)

        result = {'ticker': ticker, 'signing_date': signing_date}

        # Calculate returns for multiple windows
        for window in [7, 30, 90]:
            stock_ret, sp_ret, abnormal_ret = get_stock_return(ticker, signing_date, window)
            result[f'stock_return_{window}d'] = round(stock_ret, 4) if stock_ret is not None else None
            result[f'sp500_return_{window}d'] = round(sp_ret, 4) if sp_ret is not None else None
            result[f'abnormal_return_{window}d'] = round(abnormal_ret, 4) if abnormal_ret is not None else None

        # Print summary
        ar30 = result.get('abnormal_return_30d')
        if ar30 is not None:
            print(f" AR(30d) = {ar30:+.2f}%")
        else:
            print(f" NO DATA")

        returns[contract_id] = result

        # Save after each deal
        with open(output_path, 'w') as f:
            json.dump(returns, f, indent=2)

    # Summary
    print(f"\nResults saved to {output_path}")
    ar30_values = [v.get('abnormal_return_30d') for v in returns.values()
                   if v.get('abnormal_return_30d') is not None]
    if ar30_values:
        import statistics
        print(f"\n30-Day Abnormal Returns:")
        print(f"  N: {len(ar30_values)}")
        print(f"  Mean: {statistics.mean(ar30_values):+.2f}%")
        print(f"  Median: {statistics.median(ar30_values):+.2f}%")
        print(f"  Min: {min(ar30_values):+.2f}%")
        print(f"  Max: {max(ar30_values):+.2f}%")


if __name__ == "__main__":
    main()
