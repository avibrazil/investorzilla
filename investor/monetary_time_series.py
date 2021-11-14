import pandas as pd
from . import DataCache


class MonetaryTimeSeries(object):
    """
    A super abstract class to make concrete CurrencyConverts and MarketIndexes that
    efficiently and transparently work with DataCache class, in multi-threading context,
    with lazy data loading.

    Child class just need to really implement refreshData(), to load data from its
    original source, and processData(), to make data usable right after it was loaded
    from original source or the cache.
    """

    def __init__(self, kind, id, cache=None, refresh=False):
        self.data=None
        self.id=id
        self.kind=kind
        self.nextRefresh=refresh
        self.cache=cache



    def __eq__(self, other):
        # Make Streamlit happy
        return str(self) == str(other)



    def tryCacheData(self, kind, id, cache=None):
        if cache is not None:
            self.data=cache.get(kind=kind, id=id)
            if self.data is not None:
                return True
        return False



    def cacheUpdate(self, kind, id, cache):
        if cache is not None and self.data is not None:
            cache.set(kind=kind, id=id, data=self.data)



    def getData(self):
        if self.data is None:
            if self.nextRefresh is False:
                # Don't want to get new data from the Internet, so try cache first.
                self.tryCacheData(self.kind,self.id,self.cache)

            if self.data is None or (self.data is not None and self.data.shape[0]==0) or (self.cache is not None and self.nextRefresh):
                # Call a child-implemented method to refresh data from Internet APIs
                self.refreshData()

                # Write APIs-retrieved data to cache database
                self.cacheUpdate(self.kind,self.id,self.cache)


            # Data cleanup and feature engineering
            self.processData()

            self.nextRefresh=False

        return self.data



    def refreshData(self):
        # Pure virtual method, needs to be implemented in derived classes
        pass



    def processData(self):
        # Pure virtual method, needs to be implemented in derived classes
        pass






class CurrencyConverter(MonetaryTimeSeries):
    """
    Holds a time series which value is:

    currencyFrom × value = currencyTo

    So if currencyFrom is 'USD', currencyTo is 'BRL' and 5 is the value for a certain date, 3 USD can be converted to 15 BRL because:

    3 × 5 = 15

    Example of CurrencyConverter would be USDBRL, for BRL to USD conversion, or USDBTC,
    for BTC to USD conversion.
    """
    def __init__(self, currencyFrom, currencyTo, kind, id, cache=None, refresh=False):
        self.currencyFrom=currencyFrom
        self.currencyTo=currencyTo

        super().__init__(kind, id, cache, refresh)



    def invert(self):
        self.getData()
        self.data['value']=1/self.data['value']
        to=self.currencyTo
        self.currencyTo=self.currencyFrom
        self.currencyFrom=to

        return self



    def __repr__(self):
        return '{klass}(from={cfrom},to={cto},start={start},end={end},len={length})'.format(
            cfrom=self.currencyFrom,
            cto=self.currencyTo,
            start=self.data.index.min(),
            end=self.data.index.max(),
            length=self.data.shape[0],
            klass=type(self).__name__
        )








class MarketIndex(MonetaryTimeSeries):
    """
    self.data holds a time-indexed DataFrame with 2 columns:
    - value: market index value at that point of time
    - rate: percentage change between this and the chronologically previous value

    Example of market indexes are IBOV, SP500 and NASDAQ.
    See implementations in marketindex folder.
    """
    def __init__(self, kind='MarketIndex', id=None, currency=None, isRate=True, cache=None, refresh=False):
        super().__init__(kind=kind, id=id, cache=cache, refresh=refresh)

        self.currency=currency
        self.isRate=isRate



    def fromCurrencyConverter(self, cc: CurrencyConverter):
        """
        Make a MarketIndex from a CurrencyConverter
        """
        self.currencyConverter=cc
        self.currency=cc.currencyTo
        self.id=cc.currencyFrom+cc.currencyTo

        return self



    def refreshData(self):
        if hasattr(self, 'currencyConverter'):
            self.data=self.currencyConverter.getData().copy()
            self.data['rate']=self.data['value'].pct_change()



    def __str__(self):
        return '[{currency}] {name}'.format(name=self.id, currency=self.currency)







class CurrencyExchange(object):
    """
    Holds the name of a target currency, as 'USD', along with data of daily conversion
    rates of multiple other currencies, as 'BRL', 'EUR', 'BTC' etc.
    """

    def __init__(self, target):
        self.data=None
        self.setTarget(target)



    def addCurrency(self, currency: CurrencyConverter):
        if self.data is None:
            # We have no previous data yet.
            # Initialize the self.data with currency or 1/currency
            if currency.currencyTo==self.target:
                self.data=currency.getData().rename(columns={'value':currency.currencyFrom})
            elif currency.currencyFrom==self.target:
                self.data=(1/currency.getData()).rename(columns={'value':currency.currencyTo})
        else:
            # We already had data.
            # Add currency (or 1/currency) to our data
            if currency.currencyTo==self.target:
                self.data=pd.merge_asof(
                    self.data,
                    currency.getData().rename(columns={'value':currency.currencyFrom}),
                    left_index=True, right_index=True,
                )
            elif currency.currencyFrom==self.target:
                self.data=pd.merge_asof(
                    self.data,
                    (1/currency.getData()).rename(columns={'value':currency.currencyTo}),
                    left_index=True, right_index=True,
                )

        return self



    def setTarget(self, currency: str):
        """
        Make this CurrencyExchange now convert to another currency.
        For example, target was 'USD' and we had data for 'BRL' and 'EUR' (to USD conversion).
        Use setTarget('BRL') to then turn it into a to-BRL machine, converting
        internal data conveniently. So updated object is now capable of converting
        USD➔BRL, EUR➔BRL etc.
        """
        if self.data is not None:
            if currency in self.data.columns:
                for c in self.data.columns:
                    if c!=currency:
                        self.data[c]/=self.data[currency]

                self.data[currency]=1/self.data[currency]
                self.data.rename(columns={currency:self.target}, inplace=True)
            elif currency == self.target:
                pass
            else:
                raise IOError

        self.target=currency

        return self



    def currencies(self):
        # Get list of currencies supported by this CurrencyExchange
        c=[self.target]
        if self.data is not None:
            c+=list(self.data.columns)

        c.sort()

        return c


