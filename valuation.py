import yfinance as yf # work around https://github.com/ranaroussi/yfinance/issues/1172
import pandas_datareader.data as web
from sec_edgar_downloader import Downloader
import glob
import numpy as np
import plotly.graph_objs as go
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import shutil
from sec_cik_mapper import StockMapper
import scipy


# valuation methods
def expect_eps(price, growth, year):
    price_growth = price * (1 + growth)
    # print(price, price_growth, year)
    year -= 1

    if year < 2:
        return price_growth

    else:
        result = expect_eps(price_growth, growth, year)

    return result


def intrinsic_eps(terminal_price, minimum_rate_return, year):
    price_discount = terminal_price / (1 + minimum_rate_return)
    # print(terminal_price, price_discount, year)
    year -= 1

    if year < 2:
        return price_discount

    else:
        result = intrinsic_eps(price_discount, minimum_rate_return, year)

    return result


def stock_price_target(ticker='ALV.DE', CAPE=True, SEC_13F=True):

    # NPV variables
    year = 10
    minimum_rate_return = 0.15
    Margin_Safety = 0.8

    # parsing basic income statement on the yahoo finance
    firm = yf.Ticker(ticker)
    df = firm.earnings_dates.reset_index()
    now_year = int(datetime.now().year)
    eps = df[(df['Earnings Date'] > str(now_year-1)) & (df['Earnings Date'] < str(now_year))]['Reported EPS'].sum()
    eps_prev = df[(df['Earnings Date'] > str(now_year-2)) & (df['Earnings Date'] < str(now_year-1))]['Reported EPS'].sum()

    # growth = firm.analysis.Growth['+5Y']
    # growth =  firm.get_earnings_trend().loc['+5Y']['Growth']
    last_year_growth = (eps - eps_prev) / eps_prev
    capm_return, beta = CAPM([ticker, 'SPY']) # return of expected value based on CAPM model for 1 year
    growth = 0.15

    # PE
    if CAPE:
        PE = cape(firm)
        Shiller = 'Shiller PE'
    else:
        try:
            PE = firm.fast_info['lastPrice'] / eps
            Shiller = 'PE'
        except Exception as e:
            print(e)
            PE = firm.info['forwardPE']
            Shiller = 'Forward PE'

    # compute nvp value
    terminal_price = expect_eps(eps, growth, year)
    intr_eps = intrinsic_eps(terminal_price, minimum_rate_return, year)
    intrinsic_value = PE * intr_eps
    safety_intrinsic_value = intrinsic_value * Margin_Safety

    # compute nvp value for last year grwoth
    terminal_price = expect_eps(eps, last_year_growth, year)
    intr_eps = intrinsic_eps(terminal_price, minimum_rate_return, year)
    intrinsic_value = PE * intr_eps
    last_year_safety_intrinsic_value = intrinsic_value * Margin_Safety

    if SEC_13F:

        filing13f = Filing13F()
        df_13f = filing13f.value_by_13F()
        df_13f = df_13f[df_13f['ticker'] == ticker]
        if df_13f.empty:
            Berkshire = None
        else:
            Berkshire = df_13f.reset_index(drop=True)['price_per_share'][0]

        npv_reply = f"{ticker} safety PV = {round(safety_intrinsic_value, 2)}\n" \
                    f"{ticker} current price = {firm.info['currentPrice']}\n" \
                    f"{ticker} Cash Per Share = {round(firm.info['totalCashPerShare'], 2)}\n" \
                    f"{ticker} EPS = {round(eps, 2)}\n" \
                    f"{ticker} last year growth = {round(growth, 2)}\n" \
                    f"{ticker} last year safety PV = {round(last_year_safety_intrinsic_value, 2)}\n" \
                    f"{ticker} {Shiller} = {round(PE, 2)}\n" \
                    f"{ticker} Berkshire Buy Price = {Berkshire}"
    else:
        npv_reply = f"{ticker} safety PV = {round(safety_intrinsic_value, 2)}\n" \
                    f"{ticker} current price = {round(firm.fast_info['last_price'], 2)}\n" \
                    f"{ticker} EPS = {round(eps, 2)}\n" \
                    f"{ticker} BETA = {round(beta, 2)}\n" \
                    f"{ticker} CAPM Return = {round(capm_return, 2)}\n" \
                    f"{ticker} fixed growth for PV = {round(growth, 2)}\n" \
                    f"{ticker} last year growth = {round(last_year_growth, 2)}\n" \
                    f"{ticker} {Shiller} = {round(PE, 2)}"
                    # f"{ticker} last year safety PV = {round(last_year_safety_intrinsic_value, 2)}\n" \

    if safety_intrinsic_value - firm.fast_info['last_price'] >= 0:
        decision = f"!!! Good Bargain: {ticker} !!!\n"
    else:
        decision = "Please be patient for the right bargain value\n"

    return decision + npv_reply


def intrinsic_value(ticker='ALV.DE'):
    # get financial info
    firm = yf.Ticker(ticker)

    # compute ROIC
    # capital = firm.balance_sheet.loc['Short Long Term Debt'].mean() + firm.balance_sheet.loc[
    #     'Long Term Investments'].mean() + firm.balance_sheet.loc['Total Stockholder Equity'].mean()
    # ROIC = round(firm.financials.loc['Net Income'].mean() / capital, 2)

    capital = firm.balance_sheet.loc['InvestedCapital'].mean()
    ROIC = round(firm.get_income_stmt().loc['NetIncome'].mean() / capital, 2)

    # get book value
    firm.info['bookValue'], firm.info['priceToBook']

    # get the change of book value
    book_value_equity = firm.balance_sheet.loc['StockholdersEquity']
    book_value_equity_change = []
    for i in range(len(book_value_equity) - 1):
        book_value_equity_change.append(
            round((book_value_equity[i] - book_value_equity[i + 1]) / book_value_equity[i], 2))

    date = firm.balance_sheet.columns
    book_value_change_reply = [f"{date[i].year}~{date[i+1].year}: {int(book_value_equity_change[i]*100)}%" for i in range(len(date)-1)]

    bookValue = round(firm.info['bookValue'], 2)
    priceToBook = round(firm.info['priceToBook'], 2)
    # summary of intrinsic value
    intrinsic_value_reply = f"{ticker} ROIC = {ROIC}\n" \
                            f"{ticker} Book Value = {bookValue}\n" \
                            f"{ticker} Price To Book = {priceToBook}\n" \
                            f"{ticker} Annual Change of Book Value = {', '.join(book_value_change_reply)}\n" \
                            f"{ticker} Short Ratio = {round(firm.info['shortRatio'], 2)}"

    if min(book_value_equity_change) > 0 and ROIC > 0.1:
        intrinsic_value_reply = f"--- Intrinsic Value Pass: {ticker} ---\n{intrinsic_value_reply}"
    else:
        intrinsic_value_reply = f"--- Intrinsic Value: {ticker} ---\n{intrinsic_value_reply}"

    return intrinsic_value_reply


def intrinsic_value_quarterly(ticker='ALV.DE'):
    # get financial info
    firm = yf.Ticker(ticker)

    # compute ROIC
    # capital = firm.quarterly_balance_sheet.loc['Short Long Term Debt'].mean() + firm.quarterly_balance_sheet.loc[
    #     'Long Term Investments'].mean() + firm.quarterly_balance_sheet.loc['Total Stockholder Equity'].mean()
    capital = firm.quarterly_balance_sheet.loc['InvestedCapital'].mean()
    ROIC = round(firm.quarterly_income_stmt.loc['NetIncome'].mean() / capital, 2)

    # get book value
    firm.info['bookValue'], firm.info['priceToBook']

    # get the change of book value
    book_value_equity = firm.quarterly_balance_sheet.loc['StockholdersEquity']
    book_value_equity_change = []
    for i in range(len(book_value_equity) - 1):
        book_value_equity_change.append(
            round((book_value_equity[i] - book_value_equity[i + 1]) / book_value_equity[i], 2))

    date = firm.quarterly_balance_sheet.columns
    book_value_change_reply = [f"{date[i].year}-{date[i].month}~{date[i+1].year}-{date[i+1].month}: {int(book_value_equity_change[i]*100)}%" for i in range(len(date)-1)]

    bookValue = round(firm.info['bookValue'], 2)
    priceToBook = round(firm.info['priceToBook'], 2)
    # summary of intrinsic value
    intrinsic_value_reply = f"{ticker} Quarterly ROIC = {ROIC}\n" \
                            f"{ticker} Book Value = {bookValue}\n" \
                            f"{ticker} Price To Book = {priceToBook}\n" \
                            f"{ticker} Quarterly Change of Book Value = {', '.join(book_value_change_reply)}"

    if min(book_value_equity_change) > 0 and ROIC > 0.1:
        intrinsic_value_reply = f"--- Quarterly Intrinsic Value Pass: {ticker} ---\n{intrinsic_value_reply}"
    else:
        intrinsic_value_reply = f"--- Quarterly Intrinsic Value: {ticker} ---\n{intrinsic_value_reply}"

    return intrinsic_value_reply


def cape(firm):
    # get current year
    now = datetime.now()
    start = datetime(now.year - 4, 1, 1)
    end = datetime(now.year - 1, 12, 31)

    # cpi query
    cpi_annual = web.DataReader('FPCPITOTLZGUSA', 'fred', start, end)

    # compute the CAPE
    # get yearly eps
    yearly_eps = firm.earnings['Earnings'] / firm.get_shares().BasicShares

    # set the same index of cpi for computation afterwards
    cpi_annual = cpi_annual.set_index(yearly_eps.index)

    # adjust eps by cpi, then taking average
    adj_yearly_eps = yearly_eps * (1 - cpi_annual['FPCPITOTLZGUSA'] / 100)
    CAPE = firm.info['currentPrice'] / adj_yearly_eps.mean()

    return CAPE


class Filing13F:
    """
        Class containing common stock portfolio information from an institutional investor.
        1. Parsed from 13F-HR filing from SEC Edgar database.
    """

    # If True prints out results in console
    debug = False

    def __init__(self, filepath=''):
        """ Initialize object """
        self.filepath = filepath  # Path of file

        # Directly call parse_file() when filepath is provided with __init__
        if self.filepath:
            self.parse_file(self.filepath)

    def parse_file(self, filepath=''):
        """ Parses relevant information from 13F-HR text file """
        self.filepath = filepath  # Path of file

        if self.debug:
            print(self.filepath)

        # Opens document and passes to BeautifulSoup object.
        doc = open(filepath)
        soup = BeautifulSoup(doc, 'html.parser')  # OBS! XML parser will not work with SEC txt format

        # Print document structure and tags in console
        if self.debug:
            print(soup.prettify())

            for tag in soup.find_all(True):
                print(tag.name)

        ## --- Parse content using tag strings from txt document: <tag> content </tag>
        # OBS html.parser uses tags in lowercase

        # Name of filing company
        self.company = soup.find('filingmanager').find('name').string
        # Company identifier: Central Index Key
        self.CIK = soup.find('cik').string
        # Form type: 13F-HR
        self.formtype = soup.find('type').string
        # 13F-HR file number
        self.fileNumber = soup.find('form13ffilenumber').string
        # Reporting date (e.g. 03-31-2020)
        self.period_of_report_date = datetime.strptime(soup.find('periodofreport').string, '%m-%d-%Y').date()
        # Filing date (up to 45 days after reporting date)
        self.filing_date = datetime.strptime(soup.find('signaturedate').string, '%m-%d-%Y').date()

        ## --- Parse stock list: Each stock is marked with an infoTable parent tag
        stocklist = soup.find_all('infotable')  # List of parent tag objects

        # Initialize lists
        name = []  # Company name
        cusip = []  # CUSIP identifier
        value = []  # Total value of holdings
        amount = []  # Amount of stocks
        price_per_share = []  # Share price on reporting day != purchase price
        poc = []  # Put/Call options
        symbol = []  # Trading symbol

        # Fill lists with each stock
        for s in stocklist:
            # Company name & Title of class (e.g. COM, Class A, etc)
            n = s.find("nameofissuer").string
            n = n.replace('.', '')  # Remove dots

            c = s.find("titleofclass").string
            if c != "COM":
                name.append(n + " (" + c + ")")
            else:
                name.append(n)

            # CUSIP identifier
            cusip.append(s.find("cusip").string)
            # Total value of holdings
            v = int(s.find("value").string)
            value.append(v)
            # Amount of stocks
            ssh = int(s.find("shrsorprnamt").find("sshprnamt").string)
            amount.append(ssh)
            # Share price on reporting day (OBS! != purchase price)
            if ssh == 0:
                price_per_share.append(round(0, 2))
            else:
                price_per_share.append(round(v * 1000 / ssh, 2))

                # Put/Call options
            put_or_call = s.find("putcall")
            if put_or_call:
                poc.append(put_or_call.string)
            else:
                poc.append('No')

        # Create dictionary
        stock_dict = {"filed name": name, "cusip": cusip, "value": value, "amount": amount,
                      "price_per_share": price_per_share, "put_or_call": poc}
        # Store in dataframe
        data = pd.DataFrame(stock_dict)

        # Drop rows with put/call option
        indexes = data[data['put_or_call'] != 'No'].index
        data.drop(indexes, inplace=True)
        # data.set_index('symbol', inplace=True)
        data.set_index('filed name', inplace=True)

        self.data = data
        print(self.period_of_report_date, self.filing_date)

        return data, self.period_of_report_date, self.filing_date

    def status_report(self, institution_id='0001067983'):
        # Initialize a downloader instance. If no argument is passed
        # to the constructor, the package will download filings to
        # the current working directory.
        dl = Downloader(".")

        # Get all 13F-HR filings
        dl.get("13F-HR", institution_id, amount=2)

        # path search
        current_13f = []
        print('Named explicitly:')
        for name in glob.glob(f'sec-edgar-filings/{institution_id}/13F-HR/*'):
            print(name)
            current_13f.append(name)

        df_1, period_of_report_date_1, filing_date_1 = self.parse_file(filepath=f"{current_13f[0]}/full-submission.txt")
        df_1 = df_1.groupby("filed name").agg(Sum_amount=('amount', np.sum), Sum_value=('value', np.sum),
                                              price_per_share=('price_per_share', np.mean))

        df_2, period_of_report_date_2, filing_date_2 = self.parse_file(filepath=f"{current_13f[1]}/full-submission.txt")
        df_2 = df_2.groupby("filed name").agg(Sum_amount=('amount', np.sum), Sum_value=('value', np.sum),
                                              price_per_share=('price_per_share', np.mean))

        # compute share change
        if filing_date_1 > filing_date_2:
            df = df_1.merge(df_2, on='filed name', how='outer')
            file_date = f'{filing_date_2}~{filing_date_1}'
        else:
            df = df_2.merge(df_1, on='filed name', how='outer')
            file_date = f'{filing_date_1}~{filing_date_2}'

        df = df.fillna(0)
        df['amount_change'] = (df.Sum_amount_x - df.Sum_amount_y) / df.Sum_amount_y
        df['amount_change'].replace([np.inf, -np.inf], 99.99, inplace=True)
        df['amount_change'] = df['amount_change'] * 100
        # Convert single column to int dtype.
        df = df.fillna(0)
        df['amount_change'] = df['amount_change'].astype('int')

        df = df[df['amount_change'] != 0]
        df = df.sort_values(by='amount_change', ascending=False)

        df["Color"] = np.where(df["amount_change"] < 0, 'red', 'green')

        # plot
        y = 'amount_change'

        fig = go.Figure()

        fig.add_trace(go.Bar(x=df.index,
                             y=df[y],
                             name=y,
                             text=df[y],
                             marker_color=df['Color'],
                             textposition='auto'))

        fig.update_layout(
            title_text=f"{institution_id} {file_date} %Change of Shares",
            legend=dict(orientation="h")
        )

        fig.write_image("share_%change.jpeg")
        shutil.rmtree('sec-edgar-filings')

    def cusip_2_ticker(self, cusip='00507V109'):

        mapper = StockMapper()

        cik_cusip = pd.read_csv("config/cik-cusip-maps.csv")

        try:
          cik = f"{int(cik_cusip[cik_cusip['cusip8']==cusip[:-1]]['cik'].reset_index(drop=True)[0])}"
          head = '0' * (10-len(cik))
          cik = f"{head}{cik}"
          ticker = list(mapper.cik_to_tickers[cik])[0]
        except:
          ticker = None

        return ticker

    def value_by_13F(self, institution_id='0001067983'):
        # Initialize a downloader instance. If no argument is passed
        # to the constructor, the package will download filings to
        # the current working directory.
        dl = Downloader(".")

        # Get all 13F-HR filings for the Vanguard Group
        dl.get("13F-HR", institution_id, amount=1)

        # path search
        current_13f = []
        print('Named explicitly:')
        for name in glob.glob(f'sec-edgar-filings/{institution_id}/13F-HR/*'):
            print(name)
            current_13f.append(name)

        df, period_of_report_date, filing_date = self.parse_file(filepath=f"{current_13f[0]}/full-submission.txt")
        df = df.groupby(["filed name", "cusip"]).agg(Sum_amount=('amount', np.sum), Sum_value=('value', np.sum), price_per_share=('price_per_share', np.mean)).reset_index()
        df['ticker'] = df.cusip.apply(self.cusip_2_ticker)

        shutil.rmtree('sec-edgar-filings')

        return df

    def value_plot(self):

        df = self.value_by_13F()

        def current_price(ticker):
            try:
                firm = yf.Ticker(ticker)
                currentPrice = firm.info['currentPrice']
            except:
                currentPrice = None

            return currentPrice

        df['currentPrice'] = df.ticker.apply(current_price)
        df['delta'] = df['price_per_share'] - df['currentPrice']
        df['delta'] = df['delta'].round(1)
        df = df.sort_values(by='delta')
        # plot
        x = 'filed name'
        y = 'delta'

        fig = go.Figure()

        df["Color"] = np.where(df["delta"] < 0, 'red', 'green')

        fig.add_trace(go.Bar(x=df[x],
                             y=df[y],
                             name=y,
                             text=df[y],
                             marker_color=df['Color'],
                             textposition='auto'))

        fig.update_layout(
            title_text=f"13F Share Price - Current Price",
            legend=dict(orientation="h")
        )

        fig.write_image("13f_price_delta.jpeg")


def CAPM(stocks_list):
    # getting historic stock data from yfinance
    data = yf.download(stocks_list, period='10y')['Adj Close']

    data.columns = stocks_list

    # Normalizing Stock Prices
    def normalize_prices(df):

        df_ = df.copy()

        for stock in df_.columns:
            df_[stock] = df_[stock] / df_[stock][0]

        return df_

    norm_df = normalize_prices(data)

    # Calculating Daily % change in stock prices
    daily_returns = norm_df.pct_change()

    daily_returns.iloc[0, :] = 0

    # Initializing empty dictionaries to save results
    beta, alpha, r2 = dict(), dict(), dict()

    # Loop on every daily stock return
    for idx, stock in enumerate(daily_returns.columns.values[:-1]):
        # Fit a line (regression using polyfit of degree 1)
        slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(daily_returns[stocks_list[-1]],
                                                                             daily_returns[stock])

        b_, a_ = np.polyfit(daily_returns[stocks_list[-1]], daily_returns[stock], 1)

        # save the regression coeeficient for the current stock
        beta[stock] = b_

        alpha[stock] = a_

        r2[stock] = r_value ** 2

    keys = list(beta.keys())
    beta_3 = dict()

    for k in keys:
        beta_3[k] = [daily_returns[[k, stocks_list[-1]]].cov() / daily_returns[stocks_list[-1]].var()][0].iloc[0, 1]

    # Initialize the expected return dictionary

    ER = dict()

    rf = 0.04

    # rm = rf + 0.053
    trading_days = 365

    # Estimate the expected return of the market using the daily returns
    rm = daily_returns[stocks_list[-1]].mean() * trading_days

    for k in keys:
        # Calculate return for every security using CAPM
        ER[k] = rf + beta[k] * (rm - rf)

    for k in keys:
        print(
            f"beta = {round(beta[k], 2)}, r2 = {round(r2[k], 2)}, rf = {round(rf * 100, 2)}%, rm of {trading_days} trading_days = {round(rm * 100, 2)}%")
        print("{} trading_days of Expected return based on CAPM model for {} is {}%".format(trading_days, k,
                                                                                            round(ER[k] * 100, 2)))
    # Calculating historic returns
    for k in keys:
        print('{} trading_days Return based on historical data for {} is {}%'.format(trading_days, k, round(
            daily_returns[k].mean() * 100 * trading_days, 2)))

    return ER[k], beta[k]
