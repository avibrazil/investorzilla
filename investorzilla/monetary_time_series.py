import copy
import pandas
import logging
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
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.data        = None
        self.id          = id
        self.kind        = kind
        self.nextRefresh = refresh
        self.cache       = cache

        self.getData()



    def __eq__(self, other):
        # Make Streamlit happy
        return str(self) == str(other)



    def __lt__(self, other):
        # Make Streamlit happy
        return str(self) < str(other)



    def __gt__(self, other):
        # Make Streamlit happy
        return str(self) > str(other)



    def tryCacheData(self, kind, id, cache=None):
        if cache is not None:
            (self.data,age)=cache.get(kind=kind, id=id)
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

            if (
                    self.data is None or
                    (self.data is not None and self.data.shape[0]==0) or
                    (self.cache is not None and self.nextRefresh)
                ):
                # Call a child-implemented method to refresh data from Internet APIs
                self.refreshData()

                # Write APIs-retrieved data to cache database
                self.cacheUpdate(self.kind,self.id,self.cache)

            # Data cleanup and feature engineering
            self.processData()

            self.nextRefresh=False

        return self.data



    def refreshData(self):
        """
        Pure virtual method, needs to be implemented in derived classes.

        Will be called when MonetaryTimeSeries feels the need to update its data.
        """
        pass



    def processData(self):
        """
        Pure virtual method, needs to be implemented in derived classes.

        Will be called right after raw data is loaded from cache or from its original
        source (API) to clean it up.
        """
        pass






class CurrencyConverter(MonetaryTimeSeries):
    """
    Holds a time series which value is:

    currencyFrom × value = currencyTo

    So if currencyFrom is 'USD', currencyTo is 'BRL' and 5 is the value for a certain
    date, 3 USD can be converted to 15 BRL because 3 × 5 = 15

    Example of CurrencyConverter would be USDBRL, for BRL to USD conversion, or USDBTC,
    for BTC to USD conversion.
    """
    def __init__(self, currencyFrom, currencyTo, kind, id, cache=None, refresh=False):
        self.currencyFrom=currencyFrom
        self.currencyTo=currencyTo

        super().__init__(kind, id, cache, refresh)



    def invert(self):
        """
        Return a new object with switched currencies.

        So if data is ready to convert from BRL to USD (USD=BRL×data), new object, with
        converted data, works from USD to BRL (BRL=USD×data).
        """

        inverted = CurrencyConverter(
            currencyFrom    = self.currencyTo,
            currencyTo      = self.currencyFrom,
            kind            = self.kind,
            id              = self.currencyTo
        )

        inverted.data = 1/self.getData()

        return inverted



    def __repr__(self):
        return '{klass}(from={cfrom},to={cto},start={start},end={end},len={length})'.format(
            cfrom           = self.currencyFrom,
            cto             = self.currencyTo,
            start           = self.data.index.min(),
            end             = self.data.index.max(),
            length          = self.data.shape[0],
            klass           = type(self).__name__
        )



    def to_markdown(self, title_prefix=None):
        title=f"{self.id} ({self.currencyFrom}→{self.currencyTo}) ({type(self).__name__})"

        body=[
            # ("- home: " + self.home).format(ticker=self.id),
            f"- `{self.data.index.min()}` to `{self.data.index.max()}`"
        ]

        body='\n'.join(body)

        if title_prefix is None:
            return (title,body)
        else:
            return f"{title_prefix} {title}\n{body}"






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
        self.home=cc.__repr__()

        return self



    def refreshData(self):
        if hasattr(self, 'currencyConverter'):
            self.data=self.currencyConverter.getData().copy()
            self.data['rate']=self.data['value'].pct_change()



    def __str__(self):
        return '[{currency}] {name}'.format(name=self.id, currency=self.currency)



    def __repr__(self):
        if self.data is not None and self.data.shape[0]>0:
            return '{klass}({id},currency={curr},start={start},end={end},len={length})'.format(
                id              = self.id,
                curr            = self.currency,
                start           = self.data.index.min(),
                end             = self.data.index.max(),
                length          = self.data.shape[0],
                klass           = type(self).__name__
            )
        else:
            return '{klass}({id},currency={curr})'.format(
                id              = self.id,
                curr            = self.currency,
                klass           = type(self).__name__
            )



    def to_markdown(self, title_prefix=None):
        title=f"{self.id} ({self.currency}) ({type(self).__name__})"

        # Point to correct DataFrame
        if hasattr(self,'currencyConverter'):
            data=self.currencyConverter.data
        else:
            data=self.data

        body=[
            ("- home: " + self.home).format(ticker=self.id),
            f"- `{data.index.min()}` to `{data.index.max()}`"
        ]

        body='\n'.join(body)

        if title_prefix is None:
            return (title,body)
        else:
            return f"{title_prefix} {title}\n{body}"






class CurrencyExchange(object):
    """
    Holds the name of a target currency, as 'USD', along with data of daily conversion
    rates of multiple other currencies, as 'BRL', 'EUR', 'BTC' etc.
    """

    def __init__(self, target):
        self.data=None
        self.currency=target



    def addCurrencies(self, currencies: list):
        # Backward compatibility
        if type(currencies)==CurrencyConverter:
            currencies=[currencies]

        for currency in currencies:
            if self.data is None:
                # We have no previous data yet.
                # Initialize the self.data with currency or 1/currency
                if currency.currencyTo==self.target:
                    self.data=(
                        currency.getData()
                        .rename(columns={'value':currency.currencyFrom})
                    )
                elif currency.currencyFrom==self.target:
                    self.data=(
                        (1/currency.getData())
                        .rename(columns={'value':currency.currencyTo})
                    )
                else:
                    currency.logger.warning(f"Can’t add {currency} to {self}")
            else:
                # We already had data.
                # Add currency (or 1/currency) to our data
                if currency.currencyTo==self.target:
                    self.data=pandas.merge(
                        left        = self.data,
                        right       = (
                            currency.getData()
                            .rename(columns=dict(value=currency.currencyFrom))
                        ),
                        how         = 'outer',
                        left_index  = True,
                        right_index = True,
                    )
                elif currency.currencyFrom==self.target:
                    self.data=pandas.merge(
                        left        = self.data,
                        right       = (
                            (1/currency.getData())
                            .rename(columns=dict(value=currency.currencyTo))
                        ),
                        how         = 'outer',
                        left_index  = True,
                        right_index = True,
                    )
                else:
                    currency.logger.warning(f"Can’t add {currency} to {self}")

        if self.data is not None:
            self.data = (
                self.data

                # Drop completely empty lines
                .dropna(how='all')

                # Sort as a time series should be
                .sort_index()

                # Fill empty cells with the currency’s previous value
                .ffill()
            )

        return self


    @property
    def currency(self):
        return self.target



    @currency.setter
    def currency(self, currency: str):
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



    def __repr__(self):
        return '{klass}({target},currencies={currlist})'.format(
            target          = self.target,
            currlist        = self.currencies(),
            klass           = type(self).__name__
        )

