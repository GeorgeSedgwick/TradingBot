############# TRADING BOT #############
"""
This bot trades off of the following features:
 - RSI calculated using weighted EMA and Wilder's smoothing: Y
 - Volume
 - Time-weighted momentum: Y
 - Added ML feature as final filter for execution decision
 

It needs to:
 - Calculate feature for a list of stocks
 - Assign a score based on said features.
 - Execute trades with trailing stops.
 - Sell partial quantities at different price levels.


This has been scaled for greater amounts of capital in paper trading, however as I intend to live trade using this program, I must abide by PDT rules, and
therefore sadly NO shorting of stocks.

"""


import pandas as pd
import yfinance as yf
import numpy as np
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, TrailingStopOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, PositionSide, OrderType, OrderStatus
import time



client = TradingClient("API-key", "secret-API", paper=True)
account = client.get_account()

url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
sp500_df = pd.read_csv(url)
stocks = sp500_df['Symbol'].str.replace('.', '-', regex=False).tolist()
#print(stocks)


data = yf.download(
    stocks,
    start="2025-04-01",
    end="2025-09-04",
    interval="1d",
    group_by="ticker",
    auto_adjust=True,
    progress=True,
    threads=True
)

#print(data)
stock_data = {}


#functions i need:
"""
i need a buy function, a sell function, a function to calculate quantity of  purchase

"""
def get_stock_data(stocks):
    for ticker in stocks:
        if data[ticker].empty:
            print(f"No stock data for {ticker} was found.")
            continue
        else:
            try:
                stock_data[ticker] = data[ticker][['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                #print("next stock")
            except Exception as e:
                print(f"No stock data for {ticker} was found.")
    return stock_data

def calc_position_size(ticker, stock_data, risk=0.02):
    account = client.get_account()
    capital = float(account.cash)
    #print(f"Capital: {capital}")
    #print(f"Risk: {risk}")
    atr = stock_data[ticker]['ATR'].iloc[-1]
    risk_amount = capital * risk
    stop_loss_dollars = atr * 2
    #print(f"Risk amount: {risk_amount}")
    quantity = int(risk_amount / stop_loss_dollars)
    stock = yf.Ticker(ticker)
    current_price = stock.fast_info['last_price']
    buy_price_limit = round(current_price + (atr * 0.2), 2)
    
    return quantity, buy_price_limit



def buy(ticker, quantity, buy_price_limit):
    quantity = int(quantity)
    if quantity <= 0:
        return False
    try:
        limit_order = LimitOrderRequest(
            symbol=ticker,
            qty=quantity,
            side=OrderSide.BUY,
            limit_price=buy_price_limit,
            time_in_force=TimeInForce.DAY

            )
        order = client.submit_order(order_data=limit_order)
        print(f"Executed long trade for {ticker}. Quantity: {quantity}")
        return True
    except Exception as e:
        print(f"Error executing trade for {ticker}: {e}")
        return False




def sell(ticker, quantity):
    try:
        market_order = MarketOrderRequest(
            symbol=ticker,
            qty=quantity,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
            )
        order = client.submit_order(order_data=market_order)
        print(f"Sold all shares of {ticker}.")
    except Exception as e:
        print(f"Error selling shares of {ticker}: {e}")



def check_and_buy(stock_data):
    total_bought = 0
    positions = {pos.symbol for pos in client.get_all_positions()}

    for ticker in stock_data:
        if ticker in positions:
            continue
        #print(f"Trying to buy {ticker}")
        if stock_data[ticker]['Momentum Signal'].iloc[-1] == "strong_buy" and stock_data[ticker]['RSI Signal'].iloc[-1] == "strong_buy":
            #print(f"Decided to buy {ticker}")
            quantity, buy_price_limit = calc_position_size(ticker, stock_data, risk=0.02)
            if buy(ticker, quantity, buy_price_limit):
                total_bought += 1 
        elif stock_data[ticker]['Momentum Signal'].iloc[-1] == "strong_buy" and stock_data[ticker]['RSI Signal'].iloc[-1] == "medium_buy":
            quantity, buy_price_limit = calc_position_size(ticker, stock_data, risk=0.02)
            if buy(ticker, quantity, buy_price_limit):
                total_bought += 1
        elif stock_data[ticker]['Momentum Signal'].iloc[-1] == "medium_buy" and stock_data[ticker]['RSI Signal'].iloc[-1] == "medium_buy":
            quantity, buy_price_limit = calc_position_size(ticker, stock_data, risk=0.02)
            if buy(ticker, quantity, buy_price_limit):
                total_bought += 1
        else:
            print("Error: Signals not met")


    return total_bought

def check_and_sell(stock_data):
        positions = client.get_all_positions()
        for position in positions:
            ticker = position.symbol
            quantity = int(float(position.qty))
            if stock_data[ticker]['Momentum Signal'].iloc[-1] == "strong_sell":
                sell(ticker, quantity)
            elif "sell" in stock_data[ticker]['Momentum Signal'].iloc[-1] and "sell" in stock_data[ticker]['RSI Signal']:
                sell(ticker, quantity)
            else:
                print(f"Holding: {ticker}")


def check_and_set_trails(trail_percent=3.00):
    positions = client.get_all_positions()
    open_orders = client.get_orders()
    existing_trails = []

    for order in open_orders:
        if (order.order_type == OrderType.TRAILING_STOP and order.status in [OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PENDING_NEW]):
            existing_trails.append(order.symbol)

    for position in positions:
        ticker = position.symbol
        quantity = abs(int(position.qty))
        if ticker in existing_trails:
            continue

        elif position.side == PositionSide.LONG:

            trail_order = TrailingStopOrderRequest(
                symbol=ticker,
                qty=quantity,
                side=OrderSide.SELL,
                trail_percent=trail_percent,
                time_in_force=TimeInForce.GTC
            )
            order = client.submit_order(order_data=trail_order)
            print(f"Set 3% trailing stop for {ticker} long position.")
        else:
            print(f"Error setting trail for {ticker}")
            time.sleep(1)


def calc_tw_momentum(stock_data):
    for ticker in stock_data:
        if stock_data[ticker].empty:
            continue
        stock_data[ticker]['Signal'] = 0
        stock_data[ticker]['tw_momentum'] = (
                    stock_data[ticker]['Close'].shift(10) * 0.5 +
                    stock_data[ticker]['Close'].shift(30) * 0.3 +
                    stock_data[ticker]['Close'].shift(60) * 0.2)
        #print(f"Time-weighted momentum score for {ticker}: {stock_data[ticker]['tw_momentum']}")
        stock_data[ticker]['pct_change'] = stock_data[ticker]['tw_momentum'].diff()
        stock_data[ticker]['momentum_z_score'] = (stock_data[ticker]['tw_momentum'] - stock_data[ticker]['tw_momentum'].mean()) / stock_data[ticker]['tw_momentum'].std()
        last_pct_change = stock_data[ticker]['pct_change'].iloc[-1]
        last_z_score = stock_data[ticker]['momentum_z_score'].iloc[-1]

        stock_data[ticker]['Momentum Signal'] = ""
        if last_z_score > 0.5 and last_pct_change > 3:
            stock_data[ticker]['Momentum Signal'] = "strong_buy"
        elif last_z_score > 0.5 and last_pct_change > 0:
            stock_data[ticker]['Momentum Signal'] = "medium_buy"
        elif last_z_score < -0.5 and last_pct_change < 0:
            stock_data[ticker]['Momentum Signal'] = "medium_sell"
        elif last_z_score < 0.5 and last_pct_change < -3:
            stock_data[ticker]['Momentum Signal'] = "strong_sell"
        
        else:
            continue
    return stock_data
            

"""
pretty smooth calculation for atr that i can confirm is accurate. Now i have my position sizing tool.
"""
def calc_atr(stock_data):
    for ticker in stock_data:
        if stock_data[ticker].empty:
            continue
        
        high_low = stock_data[ticker]['High'] - stock_data[ticker]['Low']
        high_close = abs(stock_data[ticker]['High'] - stock_data[ticker]['Close'].shift(1))
        low_close = abs(stock_data[ticker]['Low'] - stock_data[ticker]['Close'].shift(1))

        stock_data[ticker]['TR'] = pd.concat([high_close, high_low, low_close], axis=1).max(axis=1)
        stock_data[ticker]['ATR'] = stock_data[ticker]['TR'].rolling(window=14).mean()
        #print(stock_data[ticker]['ATR'])
    return stock_data


"""
I originally created a strung-out and loop-heavy rsi calculation, but I didn't know about Pandas' ewm function at that time.
"""
def calc_rsi(stock_data):
    for ticker in stock_data:
        #if ticker in possible_buys or ticker in possible_sells
        price_change = stock_data[ticker]['Close'].diff()
        gains = price_change.where(price_change > 0, 0)
        losses = (-price_change).where(price_change < 0, 0)


        avg_gains = gains.ewm(alpha=1/14, adjust=False).mean()
        avg_losses = losses.ewm(alpha=1/14, adjust=False).mean()

        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        stock_data[ticker]["RSI Signal"] = ""
        stock_data[ticker]['RSI'] = rsi
        if stock_data[ticker]['RSI'].iloc[-1] < 30:
            stock_data[ticker]['RSI Signal'] = "strong_buy"
        elif stock_data[ticker]['RSI'].iloc[-1] >= 30 and stock_data[ticker]['RSI'].iloc[-1] < 50:
            stock_data[ticker]['RSI Signal'] = "medium_buy"
        elif stock_data[ticker]['RSI'].iloc[-1] >= 50 and stock_data[ticker]['RSI'].iloc[-1] < 70:
            stock_data[ticker]['RSI Signal'] = "medium_sell"
        elif stock_data[ticker]['RSI'].iloc[-1] > 70:
            stock_data[ticker]['RSI Signal'] = "strong_sell"
        else:
            stock_data[ticker]['RSI Signal'] = "NaN"
        #print(stock_data[ticker]['RSI'])
        #print(f"Latest rsi for {ticker}: {stock_data[ticker]['RSI'].iloc[-1]}")
    return stock_data


#TODO: add same for tw


def P_L():
    account = client.get_account()
    balance_change = float(account.equity) - float(account.last_equity)
    return balance_change




print("What would you like to do today, George?\n")
print("""
      1.) View  Portfolio Overview
      2.) Execute trade
      3.) Set stops for existing positions
      4.) Use bot\n""")
choice = input("> ")

if "1" in choice:
    account = client.get_account()
    balance_change = P_L()
    print(f"Available cash: {account.cash}")
    print(f"Daily P/L: {balance_change}")
elif "2" in choice:
    symbol = input("Which position would you like to execute a trade for:\n> ")
    quantity, buy_price_limit = calc_position_size(symbol, stock_data, risk=0.02)
    quantity = float(input("How many shares?\n> "))
    buy(symbol, quantity, buy_price_limit)
elif "3" in choice:
    print("Which position would you like to set trailing stop for?\n")
    ticker = input("> ")
    print("How many shares are you setting the stop for?")
    quantity = int(input("> "))

    try:
        trail_order = TrailingStopOrderRequest(
                symbol=ticker,
                qty=quantity,
                side=OrderSide.SELL,
                trail_percent=3.00,
                time_in_force=TimeInForce.GTC
                )
        order = client.submit_order(order_data=trail_order)
        print(f"Set 3% trailing stop for {ticker} long position.")
    except Exception as e:
        print(f"Error executing trailing stop: {e}")
elif "4" in choice:
    account = client.get_account()
    print(account.cash)



    print("Calculating features...")
    print("Getting stock data...")
    stock_data = get_stock_data(stocks)

    print("Calculating ATR...")
    stock_data = calc_atr(stock_data)

    print("Ranking top moveers...")
    stock_data = calc_tw_momentum(stock_data)


    print("Calculating RSI...")
    stock_data = calc_rsi(stock_data)


    print("Checking if current positions should be sold...")
    check_and_sell(stock_data)

    print("Checking for new positions to buy...")
    total_bought = check_and_buy(stock_data)
    if total_bought == 0:
        print("No trades were executed.")
        #for ticker in stock_data:
            #print(stock_data[ticker][['RSI Signal', 'Momentum Signal']])
    elif total_bought != 0:
        print("Completed trades, preparing to add 3% trailing stops to positions...")
        check_and_set_trails(trail_percent=3.00)







     
























            
        










    











    

        




    


    
