## Trading Bot

#Takes data from DataCollector and passes to strategy

#Takes strategy's buy/sell signals and tells portfolio to execute

## Strategies
#-Pairs Trading

## Assets
#-Stocks
#-Bonds
#-Crypto

## Portfolio
#-Balance
#-Buying, Selling
#-P/L


## DataCollector
#-CurrentPrice
#-HistoricalData


#TradingBot has a Portfolio, has a datacollector, and has a strategy
#Portfolio has-many assets
#It will keep all assets, quantities, values

#ORDER OF WORK:
#ASSET: Define what each asset needs
#PORTFOLIO: Portfolio can store multiple assets, return their current
#           state and update them after trades
#STRATEGY: Given an asset/its performance, output a decision
#DATACOLLECTOR: Feeds real data into the assets.
#TRADIGNBOT: Connect everything: The bot loops through portfolio assets,
#            asks strategy what to do, and updates portfolio.






import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit as st
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import TimeInForce, OrderSide
import math
import os



class TradingBot(object):
    def __init__(self, strategy_class, initial_cash):
        self.portfolio = Portfolio(initial_cash)
        self.data_collector = DataCollector()
        self.strategy = strategy_class(self.portfolio, self.data_collector)
        self.risk_manager = RiskManager(self.portfolio, self.data_collector)
        self.trade_executor = TradeExecutor(self.portfolio)

    def run(self):
        price_history = self.data_collector.get_price_history()
        
        signals = self.strategy.generate_z_signals()
        position_sizes = self.risk_manager.calculate_position_sizes(signals, price_history)
        self.trade_executor.execute_trades(signals, position_sizes)
        
        self.portfolio.list_assets()
        
        









class TradeExecutor():
    def __init__(self, portfolio):
        self.portfolio = portfolio
        self.client = TradingClient(os.getenv("API-KEY"), "os.getenv("SECRET-API-KEY")", paper=True)

    def execute_trades(self, signals, position_sizes):

        for ticker in signals:
            if signals[ticker] == "Buy":
                print(f"{ticker}: Buying {position_sizes[ticker]['shares']}...")
                #print(f"Shares inside trade method: {position_sizes[ticker]['shares']}")
                #print(f"PRINTING {ticker} position size: {position_sizes[ticker]}") ##ERROR HERE NOT GETTING ANY SHARES
                try:
                    limit_order = LimitOrderRequest(
                        symbol=ticker,
                        qty = position_sizes[ticker]['shares'],
                        side=OrderSide.BUY,
                        limit_price=position_sizes[ticker]['buy_limit_price'],
                        time_in_force=TimeInForce.DAY

                    )
                    order = self.client.submit_order(order_data=limit_order)
                    print(f"Executed long trade for: {ticker}")
                    self.portfolio.add_asset(Asset(ticker, position_sizes[ticker]['buy_limit_price'], position_sizes[ticker]['shares']))

                except Exception as e:
                    print(f"Error executing trade for {ticker}: {e}")
            else:
                #print(f"Signal for {ticker}: {signals[ticker]}")
                continue




class RiskManager():
    def __init__(self, portfolio, data_collector):
        self.portfolio = portfolio
        self.data_collector = data_collector
             
    def calculate_position_sizes(self, signals, price_history):
        position_sizes = {}
        available_cash = self.portfolio.get_cash_balance()
        risk_per_trade = available_cash * 0.02
        stop_loss_multiplier = 2.0

        for ticker in signals:
            if signals[ticker] == "Buy": #this can technically go when i want to go long and short

                atr = price_history[ticker]['ATR'].iloc[-1]

                if pd.isna(atr) or atr <= 0:
                    continue

                #print(f"Risk per trade: {risk_per_trade}")
                #print(f"ATR: {atr}")


                shares = risk_per_trade // (atr * stop_loss_multiplier)

                #print(f"Shares: {shares}")
                close = price_history[ticker]['Close'].iloc[-1]
                buy_limit_price = round(float(close + 0.5 * atr), 2)


                print(f"shares: {shares}")
                if shares > 0:
                    print(f"This works, and passes {shares} for {ticker}")
                    position_sizes[ticker] = {
                        "shares": shares,
                        "buy_limit_price": buy_limit_price
                    }
                   # print(position_sizes[ticker])


        max_portfolio_risk = 0.10
        total_risk = sum(
            position_sizes[ticker]['shares'] * (price_history[ticker]['ATR'].iloc[-1] * stop_loss_multiplier)
            for  ticker in position_sizes
        )
        if total_risk > available_cash * max_portfolio_risk:
            scaling_factor = (available_cash * max_portfolio_risk) / total_risk
            for ticker in position_sizes:
                position_sizes[ticker]['shares'] = math.floor(position_sizes[ticker]['shares'] * scaling_factor)


        return position_sizes


class Strategy(object):
    def __init__(self, portfolio, data_collector):
        self.portfolio = portfolio
        self.data_collector = data_collector
        self.tickers_list = self.data_collector.tickers_list
        self.price_history = self.data_collector.get_price_history()
        self.close_prices = pd.concat(
            [df['Close'].rename(ticker) for ticker, df in self.price_history.items()],
            axis=1

        )


#class tw_momentum_strategy(Strategy):
#   def __init__(self, portfolio, data_collector):
#   super().__init__(portfolio, data_collector)






#   return signals{}







class z_score_strategy(Strategy):
    def __init__(self, portfolio, data_collector):
        super().__init__(portfolio, data_collector)



        
    def generate_z_signals(self):
        signals = {}

        ma_14d = self.close_prices.rolling(window=14).mean()
        std_14d = self.close_prices.rolling(window=14).std()
        z_scores = (self.close_prices - ma_14d) / std_14d

        #st.write(z_scores)
        
        
        for ticker in self.tickers_list:
            if z_scores[ticker].iloc[-1] > 2:
                signals[ticker] = "Buy"

            elif z_scores[ticker].iloc[-1] < -2:
                signals[ticker] = "Sell"
                #ADD STRONGER SIGNALS
            else:
                signals[ticker] = "Hold"

            #st.write(f"{ticker}: {z_signal[ticker]}")

        return signals



        

class Asset(object):
    def __init__(self, ticker, current_price, quantity):
        self.ticker = ticker
        self.current_price = current_price
        self.quantity = quantity

    def update_price(self, price_history):
        try:
            self.current_price = price_history[self.ticker]['Close'].iloc[-1]
        except (KeyError, TypeError):
            self.current_price = price_history['Close'].iloc[-1]




class Portfolio(object):
    def __init__(self, initial_cash):
        self.cash = initial_cash
        self.assets = []

    def get_cash_balance(self):
        return self.cash
        

    def update_cash(self, amount):
        self.cash += amount

    def can_afford(self, cost):
        return self.cash >= cost




    def add_asset(self, asset):
        self.assets.append(asset)

    def list_assets(self):
        print("LISTING ASSETS:\n")
        print(self.assets)
    
    def get_portfolio_value(self):
        print("TOTAL PORTFOLIO VALUE:\n")
        total_value = 0
        for asset in self.assets:
            total_value += asset.current_price * asset.quantity

        return total_value
        
            

class DataCollector(object):
    def __init__(self):
        print("Downloading data...")
        url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
        sp500_df = pd.read_csv(url)
        self.tickers_list = sp500_df['Symbol'].str.replace('.', '-', regex=False).tolist()
        
    def get_price_history(self):
        print("Getting current prices...")
        data = yf.download(tickers=self.tickers_list, group_by='ticker', start="2025-07-01", end="2025-09-24", auto_adjust=True)
        price_history = {}
        for ticker in self.tickers_list:
            ticker_data = data[ticker].copy()
            ticker_data['H-L'] = ticker_data['High'] - ticker_data['Low']
            ticker_data['H-C'] = (ticker_data['High'] - ticker_data['Close'].shift()).abs()
            ticker_data['L-C'] = (ticker_data['Low'] - ticker_data['Close'].shift()).abs()
            
            ticker_data['TR'] = ticker_data[['H-L', 'H-C', 'L-C']].max(axis=1)
            ticker_data['ATR'] = ticker_data['TR'].rolling(window=14).mean()

            price_history[ticker] = {}
            price_history[ticker] = data[ticker].copy()
            price_history[ticker]['ATR'] = ticker_data['ATR']




        return price_history

user_cash = int(input("Enter portfolio cash to begin trading:\n> "))

bot = TradingBot(z_score_strategy, user_cash)


bot.run()



