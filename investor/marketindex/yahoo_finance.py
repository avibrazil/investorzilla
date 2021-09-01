import datetime
import pandas as pd
# import pandas_datareader.data as pdr

from .. import MarketIndex


class YahooMarketIndex(MarketIndex):
    """
    Any market index from Yahoo Finance
    """

    url='https://query1.finance.yahoo.com/v7/finance/download/{ticker}?period1={start}&period2={now}&interval=1d&events=history&includeAdjustedClose=true'

    def __init__(self, name, friendlyName=None, currency='USD', isRate=False, cache=None, refresh=False):
        super().__init__(
            type='YahooMarketIndex',
            id=name,
            currency=currency,
            isRate=isRate,
            cache=cache,
            refresh=refresh
        )

        self.friendlyName=friendlyName


    def refreshData(self):
#         self.data = pdr.DataReader([self.id], data_source='yahoo')


        print(self.url.format(
                ticker=self.id,
                start=round(datetime.datetime(1900,1,1).timestamp()),
                now=round(datetime.datetime.utcnow().timestamp()+3600*24)
            ))

        self.data=pd.read_csv(
            self.url.format(
                ticker=self.id,
                start=round(datetime.datetime(1900,1,1).timestamp()),
                now=round(datetime.datetime.utcnow().timestamp()+3600*24)
            )
        )



    def processData(self):
        # Convert time to a new column
        self.data['time']=pd.to_datetime(self.data.Date)

        # Set it as the index
        self.data.set_index('time', inplace=True)
        self.data.sort_index(inplace=True)

        # Drop old column
        self.data.drop('Date', axis=1)

        # Make the 'value' column
        self.data.rename(columns={'Close': 'value'}, inplace=True)
        toRemove=list(self.data.columns)
        toRemove.remove('value')
        self.data.drop(columns=toRemove, inplace=True)

        self.data.fillna(method='ffill', axis=0, inplace=True)

        # Compute rate from daily values
        self.data['rate']=self.data['value']/self.data.shift()['value']-1


    def __str__(self):
        if self.friendlyName is not None:
            return '[{currency}] {name}'.format(name=self.friendlyName, currency=self.currency)
        else:
            return super().__str__()