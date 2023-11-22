import datetime
import urllib
import requests
import pandas

from .. import CurrencyConverter


class CryptoCompareCurrencyConverter(CurrencyConverter):
    """
    Crypto currency converter to USD with data from
    https://min-api.cryptocompare.com/documentation?key=Historical&cat=dataSymbolHistoday

    Pass to currencyFrom crypto names such as `BTC`, `ETH` etc.
    """

    api='https://min-api.cryptocompare.com/data/v2/histoday?fsym={cfrom}&tsym={cto}&limit=2000&toTs={maxTime}&api_key={key}'


    def __init__(self, currencyFrom, currencyTo='USD', apiKey=None, cache=None, refresh=False):
        self.apiKey=apiKey

        super().__init__(
            currencyFrom  = currencyFrom,
            currencyTo    = currencyTo,

            kind          = 'CryptoCompareCurrencyConverter',
            id            = currencyFrom,

            cache         = cache,
            refresh       = refresh
        )



    def refreshData(self):
        self.data=None

        maxTime=datetime.datetime.utcnow().timestamp()+(24*3600)

        for t in range(10):
            # Go back in time until closing price equals zero
            data=requests.get(
                self.api.format(
                    cfrom=self.currencyFrom,
                    cto=self.currencyTo,
                    key=self.apiKey,
                    maxTime=round(maxTime)
                )
            ).json()

            table=pandas.DataFrame(data['Data']['Data'])

            if self.data is None:
                self.data=table
            else:
                self.data=pandas.concat([self.data,table])

            if table[table['time']==data['Data']['TimeFrom']]['close'][0]==0:
                # First datapoint of iteration presents no closing price.
                # Stop going back in time.
                break
            else:
                maxTime=data['Data']['TimeFrom']

        self.data = self.data[self.data.close != 0]



    def processData(self):
        self.data = (
            self.data

            .rename(columns={'time': 'ts', 'close': 'value'})

            .assign(
                time = lambda table: pandas.to_datetime(table.ts,unit='s',utc=True)
            )

            .set_index('time')
            .sort_index()

            .drop(columns="high low open volumefrom volumeto conversionType conversionSymbol ts".split())
        )
