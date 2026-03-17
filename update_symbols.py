import requests
import json
import os

def fetch_symbols():
    print("Fetching VN symbols from TradingView Scanner...")
    symbols = set()
    
    # TradingView Scanner API is unauthenticated and usually unblocked by corporate firewalls
    url = "https://scanner.tradingview.com/vietnam/scan"
    
    payload = {
        "filter": [{"left":"type","operation":"in_range","right":["stock","dr","fund"]}],
        "options": {"lang":"en"},
        "markets": ["vietnam"],
        "symbols": {"query":{"types":[]},"tickers":[]},
        "columns": ["name"],
        "sort": {"sortBy":"market_cap_basic","sortOrder":"desc"},
        "range": [0, 2000] # Get top 2000 VN stocks
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for row in data.get("data", []):
                sym = row.get("d", [""])[0]
                if sym:
                    symbols.add(sym)
            
            print(f"Fetched {len(symbols)} unique symbols!")
        else:
            print(f"Failed to fetch. Status code: {response.status_code}")
                
        if symbols:
            with open("symbols.txt", "w") as f:
                for target_symbol in sorted(list(symbols)):
                    f.write(target_symbol + "\n")
            print(f"Successfully saved {len(symbols)} symbols to symbols.txt!")
        else:
            print("No symbols found.")
            
    except Exception as e:
        print(f"Error fetching symbols: {e}")

if __name__ == "__main__":
    fetch_symbols()
