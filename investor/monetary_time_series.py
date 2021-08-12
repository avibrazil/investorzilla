import pandas as pd
from . import DataCache


class MonetaryTimeSeries(object):
    """
    A super abstract class to make concrete CurrencyConverts and MarketIndexes
    """

    def __init__(self, type, id, cache=None, refresh=False):
        self.data=None
        self.id=id
        self.type=type

        self.tryCacheData(type,id,cache)

        if self.data is None or (self.data is not None and self.data.shape[0]==0) or (cache is not None and refresh):
            self.refreshData()
#             print(self.data.info())
            self.cacheUpdate(type,id,cache)

        self.processData()



    def tryCacheData(self,type,id,cache=None):
        if cache is not None:
            self.data=cache.get(type=type,id=id)
            if self.data is not None:
                return True
        return False


    def cacheUpdate(self,type,id,cache):
        if cache is not None and self.data is not None:
            cache.set(type=type, id=id, data=self.data)


    def refreshData(self):
        # Pure virtual method, needs to be implemented in derived classes
        pass


    def processData(self):
        # Pure virtual method, needs to be implemented in derived classes
        pass







class MarketIndex(MonetaryTimeSeries):
    """
    self.data holds a time-indexed DataFrame with 2 columns:
    - value: index number
    - rate: percentage change between 2 periods of value
    """
    def __init__(self, type='MarketIndex', id=None, currency=None, isRate=True, cache=None, refresh=False):
        super().__init__(type=type, id=id, cache=cache, refresh=refresh)

        self.currency=currency
        self.isRate=isRate



    def fromCurrencyConverter(self,cc):
        self.currency=cc.currencyTo
        self.id=cc.currencyFrom+cc.currencyTo

        self.data=cc.data.copy()
        self.data['rate']=self.data['value'].pct_change()

        return self


    def __str__(self):
        return '[{currency}] {name}'.format(name=self.id, currency=self.currency)









class CurrencyConverter(MonetaryTimeSeries):
    """
    Holds a time series which value is:

    currencyFrom × value = currencyTo

    So if currencyFrom is 'USD', currencyTo is 'BRL' and 5 is the value for a certain date, 3 USD can be converted to 15 BRL because:

    3 × 5 = 15

    """
    def __init__(self, currencyFrom, currencyTo, type, id, cache=None, refresh=False):
        self.currencyFrom=currencyFrom
        self.currencyTo=currencyTo

        super().__init__(type, id, cache, refresh)



    def invert(self):
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






class CurrencyExchange(object):
    """
    Holds the name of a target currency, as 'USD', with data of daily conversion
    rates of multiple other currencies, as 'BRL', 'EUR', 'BTC' etc.
    """

    def __init__(self, target):
        self.data=None
        self.setTarget(target)


    def addCurrency(self,currency):
        if self.data is None:
            # We have no previous data yet.
            # Initialize the self.data with currency or 1/currency
            if currency.currencyTo==self.target:
                self.data=currency.data.rename(columns={'value':currency.currencyFrom})
            elif currency.currencyFrom==self.target:
                self.data=(1/currency.data).rename(columns={'value':currency.currencyTo})
        else:
            # We already had data.
            # Add currency (or 1/currency) to the our data
            if currency.currencyTo==self.target:
                self.data=pd.merge_asof(
                    self.data,
                    currency.data.rename(columns={'value':currency.currencyFrom}),
                    left_index=True, right_index=True,
                )
            elif currency.currencyFrom==self.target:
                self.data=pd.merge_asof(
                    self.data,
                    (1/currency.data).rename(columns={'value':currency.currencyTo}),
                    left_index=True, right_index=True,
                )

        return self


    def setTarget(self,currency):
        # Make this CurrencyExchange now convert to another currency.
        # For example, target was 'USD' and we had data for 'BRL' (to USD conversion).
        # Use setTarget to then turn it into a to-BRL machine, converting data conveniently.
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
        c=[self.target]
        if self.data is not None:
            c+=list(self.data.columns)

        c.sort()

        return c


