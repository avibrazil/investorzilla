import os
import datetime
import pickle
import logging
import concurrent.futures
import numpy
import pandas


from . import Fund
from . import DataCache


class Portfolio(object):
    """
    A simple interface for a generic Portfolio.

    A Portfolio is the keeper of raw balance and ledger of multiple
    investment instruments, funds etc. Members of a Portfolio can be
    aggregated to generate one Fund which in turns has a time series for
    number of shares and a time series for share value.

    Derived classes must set self.ledger and self.balance in order for the
    Fund creation logic to work.
    """

    # A true pseudo-random number generator in the space of 2 seconds used
    # to add random miliseconds to entries that have same time. This is
    # why we exclude Zero.
    twoSeconds=(
        pandas.Series(range(-999,1000))

        # Exclude 0
        .pipe(lambda s: s[s!=0])

        # Randomize in a deterministic way
        .sample(frac=1,random_state=42)
        .reset_index(drop=True)
    )

    # twoSecondsGen=None # to be redefined later




    def __init__(self, kind, id, cache=None, refresh=False):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        # Suffix for DataCache table
        self.kind=kind

        # ID of dataset
        self.id=id

        # Last updated at
        # self.asof = None

        self.cache=cache
        self.nextRefresh=refresh

        # self.twoSecondsGen=Portfolio.pseudoRandomUniqueMilliseconds()

        # Force data load
        self.balance
        self.ledger



    def getFund(self, subset=None, name=None, currencyExchange=None):
        """
        Given one or more investment items names, passed in the subset
        attribute, return a Fund object which allows handling it as shares
        with share value and currency.
        """

        if subset is None or (isinstance(subset,list) and len(subset)==0):
            # Return all funds
            return Fund(
                name             = name,
                ledger           = self.ledger,
                balance          = self.balance,
                currencyExchange = currencyExchange,
            )
        else:
            if isinstance(subset, str):
                # If only 1 fund passed, turn it into a list
                subset=[subset]


            # And return only this subset of funds
            return Fund(
                name             = name,
                ledger           = self.ledger[self.ledger.fund.isin(subset)],
                balance          = self.balance[self.balance.fund.isin(subset)],
                currencyExchange = currencyExchange,
            )



    def funds(self):
        """
        Return list of tuples as:
        [
            ('fund1',['currency1']),
            ('fund2',['currency1', 'currency2']),
            ('fund3',['currency2'])
        ]

        Which is the list of funds, each with the currencies they present data.
        """
        nonMonetary={'fund', 'time', 'comment'}

        return list(
            self.ledger[
                ['fund'] +
                # Get only currency names
                list(set(self.ledger.columns) - nonMonetary)
            ]

            .set_index('fund')


            # Get rid of completely empty rows
            .dropna(how='all')


            # replace by True where there is NaN
            .isnull()


            # Convert a False (has value) to currency name
            .apply(
                lambda x: x.index[x==False][0],
                axis=1
            )


            # make fund name a regular column
            .reset_index()


            .drop_duplicates()



            # Group by fund and make list of currencies
            .groupby(by='fund', observed=True).agg(list)



            # make fund name a regular column
            .reset_index()



            # convert to tuples
            .itertuples(index=False, name=None)
        )



    @property
    def balance(self):
        return self.getProperty('balance')



    @property
    def ledger(self):
        return self.getProperty('ledger')



    @property
    def asof(self):
        """
        Timestamp of most recent balance or ledger data of this portfolio asset
        """
        return numpy.max(
            [t for t in
                [
                    self.ledger.time.max()  if self.has_ledger  else None,
                    self.balance.time.max() if self.has_balance else None
                ] if t is not None
            ]
        )



    def getProperty(self,prop):
        if getattr(self,f'has_{prop}') is False:
            return None

        if self.nextRefresh:
            self.callRefreshData()
            self.nextRefresh=False
        elif getattr(self,f'_{prop}') is None:
            if self.tryCacheData() is False:
                self.callRefreshData()
        else:
            return getattr(self,f'_{prop}')

        # At this point we have raw data from cache or internet

        # Data cleanup and feature engineering
        self.processData()

        return getattr(self,f'_{prop}')



    def tryCacheData(self):
        ledger_age = None
        balance_age = None

        if self.cache is not None:
            (self._ledger,ledger_age)   = self.cache.get(
                kind=f'{self.kind}__ledger',
                id=self.id
            )

            (self._balance,balance_age) = self.cache.get(
                kind=f'{self.kind}__balance',
                id=self.id
            )

        if ledger_age or balance_age:
            return True

        return False



    def cacheUpdate(self):
        """
        Set new data to DataCache
        """
        if self.cache is not None:
            if self._ledger is not None:
                self.cache.set(kind=f'{self.kind}__ledger', id=self.id, data=self._ledger)
            if self._balance is not None:
                self.cache.set(kind=f'{self.kind}__balance', id=self.id, data=self._balance)



    def callRefreshData(self):
        self.refreshData()
        self.cacheUpdate()



    ############################################################################
    ##
    ## Virtual methods.
    ##
    ## Need to be defined in derived classes.
    ##
    ############################################################################

    def refreshData(self):
        """
        Called when Portfolio feels the need to update its data.
        Pure virtual method, needs to be implemented in derived classes.
        """
        pass



    def processData(self):
        """
        Called right after raw data is loaded from cache or from its original
        source (API) to clean it up.

        Pure virtual method, needs to be implemented in derived classes.
        """
        pass



    @property
    def has_balance(self):
        # Let derived classes define this
        return None



    @property
    def has_ledger(self):
        # Let derived classes define this
        return None



    ############################################################################
    ##
    ## Utility methods, to be used in general situations by derived classes
    ##
    ############################################################################


#     def pseudoRandomUniqueMilliseconds():
#         # Cycle over self.twoSeconds which has 1998 entries (0 to 1997) with
#         # random milliseconds in the range [-999..-1, 1..999]

#         twoSecondsLength=len(Portfolio.twoSeconds)

#         i=0
#         while i<twoSecondsLength:
#             # print('generating')
#             yield pandas.to_timedelta(Portfolio.twoSeconds[i],unit='ms')
#             i+=1
#             if (i==twoSecondsLength):
#                 i=0



    def normalizeTime(time, naiveTimeShift=12*3600) -> pandas.DataFrame:
        """
        Get a pandas.Series in ‘time’ and normalize it:

        1. Add naiveTimeShift (in seconds) to time-naive entries
        2. Add current timezone to TZ-naive entries
        3. Convert all to UTC timezone
        4. De-duplicate timestamps using Portfolio.twoSeconds for small
           adjustments

        Return a normalized pandas.Series ordered and indexed identical to
        input.

        Derived classes must use this method to homogenize time handling
        across the fremework.
        """
        def randomTimedeltas(index):
            """
            Return a vector of random pandas.Timedelta indexed by `index`.
            """
            vec=(
                pandas.to_timedelta(
                    # Create a long random vector by concatenating
                    # Portfolio.twoSeconds multiple times
                    pandas.concat(
                        # How many times we need to duplicate
                        # Portfolio.twoSeconds?
                        max(2,int(
                            numpy.ceil(
                                len(index) /
                                len(Portfolio.twoSeconds)
                            )
                        )) *
                        [Portfolio.twoSeconds]
                    )

                    # Get a vector with precise size
                    .head(len(index)),

                    # This is in milliseconds
                    unit='ms'
                )
            )

            # Overwrite index
            vec.index=index

            return vec

        # Convert naiveTimeShift into something more useful
        timeShift=pandas.to_timedelta(naiveTimeShift, unit='s')

        # Get current timezone
        currtz=(
            datetime.datetime.now(datetime.timezone.utc)
            .astimezone()
            .tzinfo
        )

        instrumented=(
            time

            # Shift dates that have no time (time part is 00:00:00) to the
            # middle of the day (12:00:00) using naiveTimeShift parameter
            .apply(
                lambda cell:
                    pandas.Timestamp(cell+timeShift)
                    if cell.time()==datetime.time(0)
                    else pandas.Timestamp(cell)
            )

            # Convert all to current time zone, or simply add current time
            # zone to TZ-naive entries.
            .apply(
                lambda cell:
                    cell.tz_localize(currtz) # Set TZ on undefined cells
                    if cell.tzinfo is None
                    else cell.tz_convert(currtz) # Convert existing TZ
            )

            # Keep it internally as UTC for more precise and compatible
            # joins.
            .dt
            .tz_convert('UTC')
        )

        # Cirurgically adjust time adding a few random milliseconds only
        # on duplicate items
        dups=instrumented.duplicated()
        duplicated=instrumented[dups]

        instrumented=pandas.concat(
            [
                instrumented[~dups],
                instrumented[dups]+randomTimedeltas(instrumented[dups].index)
            ]
        )

        return instrumented






class PortfolioAggregator(Portfolio):
    def __init__(self, cache=None, refresh=False):
        self.members=[]

        super().__init__(
            kind       = 'aggregator',
            id         = None,
            cache      = cache,
            refresh    = refresh
        )


    def append(self,portfolio):
        if isinstance(portfolio, list):
            self.members += portfolio
        else:
            self.members.append(portfolio)



    ############################################################################
    ##
    ## Virtual methods.
    ##
    ## Need to be defined in derived classes.
    ##
    ############################################################################

    def refreshData(self):
        self.submitToMembers('refreshData')



    def processData(self):
        self.submitToMembers('processData')



    @property
    def has_balance(self):
        has = False
        for p in self.members:
            has = has or p.has_balance
            if has:
                break

        return has



    @property
    def has_ledger(self):
        has = False
        for p in self.members:
            has = has or p.has_ledger
            if has:
                break

        return has



    @property
    def _balance(self):
        return (
            pandas.concat(
                [p._balance for p in self.members if p.has_balance]
            )
            .reset_index(drop=True)
        )



    @property
    def _ledger(self):
        return (
            pandas.concat(
                [p._ledger for p in self.members if p.has_ledger]
            )
            .reset_index(drop=True)
        )



    @property
    def asof(self):
        return numpy.max([p.asof.tz_localize(None) for p in self.members])



    def tryCacheData(self):
        self.submitToMembers('tryCacheData')



    def submitToMembers(self, method: str):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            tasks={}
            for p in self.members:
                m = getattr(p,method)
                task[executor.submit(m)] = p

            for task in concurrent.futures.as_completed(tasks):
                self.debug(f'Done {tasks[task]}')

                # The return of submited method (processData) or the raise of error
                task.result()



    def __repr__(self):
        return '{klass}({members})'.format(
            klass   = type(self).__name__,
            members = ', '.join([m.__repr__() for m in self.members])
        )



    def to_markdown(self, title_prefix=None):
        title="{klass}({n} members)".format(
            klass=type(self).__name__,
            n=len(self.members)
        )

        body=[
            (m.to_markdown(title_prefix=title_prefix + '#' if title_prefix else None))
            for m in self.members
        ]

        if title_prefix is None:
            return (title,body)
        else:
            body='\n\n'.join(body)
            return f"{title_prefix} {title}\n{body}"


