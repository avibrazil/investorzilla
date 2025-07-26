import os
import pathlib
import datetime
import pickle
import logging
import concurrent.futures
import numpy
import pandas


from . import Fund
from . import DataCache


class PortfolioColumn(object):
    """
    A single class to hold portfolio dataframe column names.
    """

    ASSET    = 'asset'
    TIME     = 'time'
    COMMENT  = 'comment'

    LEDGER   = 'ledger'
    BALANCE  = 'balance'

    nonMonetary          = (TIME, ASSET, COMMENT)
    nonMonetaryNoComment = (TIME, ASSET)
    monetary             = (LEDGER, BALANCE)



class Portfolio(object):
    """
    Interface and standards for portfolio data loading, cleaning and caching.

    A Portfolio object contains a single URL for CSV data, a single sheet in a
    Google Sheets document, or a single sheet in an Excel spreadsheet. The
    derived PortfolioAggregator class integrates multiple Portfolio objects for
    an integrated and complete portfolio.

    A Portfolio-derived class must contain logic to load this data. Then, the
    Portfolio generic class will handle column name normalization, save to cache
    (as pure as it came from storage) and data cleanup, for example as
    converting text to numbers, adjusting timezone, wealth masquerading etc.
    Derived classes might have the chance to reimplement these actions, but
    shouldn't be needed.

    The dataframe loaded from these sources may contain ledger or balance data,
    or both. Portfolio objects have the balance() and ledger() methods, which
    return only the requested part from source as a standard DataFrame.

    Portfolio objects can load its data from DataCache or force a refresh from
    original source.

    Since data of a Portfolio may contain multiple assets, Portfolio may create
    an internal Fund object for easier calculations of some Portfolio features,
    such as the biggest asset.




    A Portfolio is the keeper of raw balance and ledger of multiple
    investment instruments, assets etc. Members of a Portfolio can be
    aggregated to generate one Fund which in turns has a time series for
    number of shares and a time series for share value.

    Derived classes must set self.ledger and self.balance in order for the
    Fund creation logic to work.
    """

    # A true pseudo-random number generator in the space of 2 seconds used
    # to add random milliseconds to entries that have same time. This is
    # why we exclude Zero.
    twoSeconds=(
        pandas.Series(range(-999,1000))

        # Exclude 0
        .pipe(lambda s: s[s!=0])

        # Randomize in a deterministic way
        .sample(frac=1,random_state=42)
        .reset_index(drop=True)
    )



    def __init__(self, name, sheetStructure=None, cache=None, refresh=False, **kwargs):
        # Setup logging
        self.logger = logging.getLogger(
            "{program}.{cls}({name})".format(
                program = __name__,
                cls     = self.__class__.__name__,
                name    = name
            )
        )

        self.URI=None
        if 'URI' in kwargs:
            URI=kwargs['URI']
            if '://' in URI:
                self.URI=URI
            else:
                self.URI=pathlib.Path(URI).expanduser()

                # Now handle URIs that are not absolute paths
                if not self.URI.is_absolute() and 'base' in kwargs:
                    base=kwargs['base']
                    self.URI=(
                        (pathlib.Path(base).parent.resolve() / self.URI)
                        .resolve()
                        .as_uri()
                    )

        self.name = name
        self.sheetStructure = sheetStructure

        # Last updated at
        # self.asof = None

        # Internal protfolio-as-a-fund uninitialized. Initialize with
        # makeInternalFund() passing a currencyExchange object.
        self.fund=None

        self.cache=cache
        self.nextRefresh=refresh

        # Force data load
        self._df=None
        # self.balance
        # self.ledger



    def getFund(self, subset=None, name=None, currencyExchange=None):
        """
        Given one or more asset names, passed in the subset
        attribute, return a Fund object which allows handling it as shares
        with share value and currency.
        """

        if subset is None or (isinstance(subset,list) and len(subset)==0):
            # Make a fund of all assets
            return Fund(
                name             = name,
                ledger           = self.ledger,
                balance          = self.balance,
                currencyExchange = currencyExchange,
            )
        else:
            # We have a specific list of assets requested to form a fund

            if isinstance(subset, str):
                # If only 1 fund passed, turn it into a list
                subset=[subset]


            # And return only this subset of funds
            return Fund(
                name             = name,
                ledger           = self.ledger[self.ledger.asset.isin(subset)],
                balance          = self.balance[self.balance.asset.isin(subset)],
                currencyExchange = currencyExchange,
            )



    def makeInternalFund(self,currencyExchange):
        """
        For easier computations later, make an internal fund out of the assets
        overlooked by this portfolio.
        """
        self.fund=self.getFund(currencyExchange=currencyExchange)



    def assets(self):
        """
        Get list of assets featured in this Portfolio object, including their
        detected currencies. Returned data structure is list of tuples as:
        [
            ('asset1',['currency1']),
            ('asset2',['currency1', 'currency2']),
            ('asset3',['currency2'])
        ]

        Which is the list of assets, each with the currencies they present data.

        If self has an internal fund (created with makeInternalFund()), assets
        will be orderd by current balance, with biggest balance as the first
        one. Otherwise they'll be ordered alphabetically -- less useful.
        """
        order=None
        if self.fund is not None:
            order=(
                self.fund.balance

                ## Put balance of each fund in a different column,
                ## repeat value for empty times and fillna(0) for first empty
                ## values
                .dropna()
                .unstack(level=0)
                # .ffill()

                .sort_index()

                .ffill()

                # Get last balance
                .iloc[[-1]]

                .T

                # Get rid of useless index levels
                .pipe(
                    lambda table: table.set_index(table.index.droplevel().droplevel())
                )

                # The first column, no matter its name
                .iloc[:,0]

                # Order by balance of each asset
                .sort_values(ascending=False)

                # Get only the index
                .index
            )

        return list(
            self._df[
                [PortfolioColumn.ASSET] +

                # Get only currency names
                [
                    c for c in self._df.columns
                    if PortfolioColumn.LEDGER in c or PortfolioColumn.BALANCE in c
                ]
            ]

            .set_index(PortfolioColumn.ASSET)


            # Get rid of completely empty rows
            .dropna(how='all')


            # replace by True where there is NaN
            .isnull()

            # Convert a False (has value) to currency name
            .apply(
                lambda x: x.index[x==False][0].replace('ledger_','').replace('balance_',''),
                axis=1
            )


            # make asset name a regular column
            .reset_index()


            .drop_duplicates()


            .set_index(PortfolioColumn.ASSET)


            # Group by asset and make list of currencies
            .groupby(by=PortfolioColumn.ASSET, observed=True).agg(list)


            # Order by bigger current balance
            .reindex(order)


            # make asset name a regular column
            .reset_index()


            # convert to tuples
            .itertuples(index=False, name=None)
        )



    @property
    def data(self):
        multi=[]

        for c in self._df.columns:
            if any(p in c for p in PortfolioColumn.monetary):
                multi.append(c.split('_'))
            else:
                multi.append((c,None))

        d=self._df.copy()
        d.columns=pandas.MultiIndex.from_tuples(multi)

        return d[
            [
                c for c in (PortfolioColumn.nonMonetary + PortfolioColumn.monetary)
                if c in d.columns.get_level_values(0)
            ]
        ]



    @property
    def balance(self):
        """
        Returns a dataframe with shape

        | (index) | asset | time | currency 1 | currency 2 | ... |

        """

        return self.getProperty('balance')



    @property
    def ledger(self):
        """
        Returns a dataframe with shape

        | (index) | asset | time | comment | currency 1 | currency 2 | ... |

        """

        return self.getProperty('ledger')



    @property
    def asof(self,tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo):
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
        ).tz_convert(tz)



    def getProperty(self,prop):
        if getattr(self,f'has_{prop}') is False:
            return None

        self.logger.debug(f"Requested data for {prop}")

        metadata = "asset time comment".split()

        if self.nextRefresh:
            self.callRefreshData()
            self.nextRefresh=False
        elif getattr(self,f'_{prop}') is None:
            if self.tryCacheData() is False:
                self.callRefreshData()
        else:
            df = getattr(self,f'_{prop}')
            if hasattr(self,'wealth_mask_factor') and self.wealth_mask_factor!=1:
                # Obfuscate wealth by multiplying by wealth_mask_factor
                return pandas.concat(
                    [
                        df[df.columns.intersection(metadata)],
                        (
                            df.drop(df.columns.intersection(metadata), axis=1) *
                            self.wealth_mask_factor
                        )
                    ],
                    axis=1
                )
            else:
                return df

        # At this point we have raw data from cache or original source (internet)

        # Data cleanup and feature engineering
        self.processData()

        df = getattr(self,f'_{prop}')
        if hasattr(self,'wealth_mask_factor') and self.wealth_mask_factor!=1:
            # Obfuscate wealth by multiplying by wealth_mask_factor
            return pandas.concat(
                [
                    df[df.columns.intersection(metadata)],
                    (
                        df.drop(df.columns.intersection(metadata), axis=1) *
                        self.wealth_mask_factor
                    )
                ],
                axis=1
            )
        else:
            return df



    def tryCacheData(self):
        """
        Try to get data from cache, return True in case of success.

        If success, self._df is set and ready to be processed by
        self.processData()
        """
        if self.cache is not None:
            (self._df, age) = self.cache.get(
                kind=f'portfolio_{self.name}',
                id=self.name
            )

        return True if age else False



    def cacheUpdate(self):
        """
        Set new data to DataCache
        """
        if self.cache is not None:
            if self._df is not None:
                self.cache.set(
                    kind=f'portfolio_{self.name}',
                    id=self.name,
                    data=self._df
                )



    def callRefreshData(self):
        self.logger.info("Start retrieving data from original source")
        # Calls derived class' refreshData() method
        self.refreshData()
        self.logger.info("Finished retrieving data from original source and writting cache with almost-raw refreshed data")
        self.cacheUpdate()



    def columnSchema(self):
        """
        Returns a dict ready to be passed to pandas.DataFrame.rename() that will
        rename column names as they come from storage into a standard suitable
        for caching and further manipulation.
        """

        # Objective here is to normalize column names. So a user sheet with
        # column names such as:
        #
        # - Date
        # - My Asset
        # - Movement BRL
        # - Movement USD
        # - Balance BRL
        # - Balance USD
        # - Description
        #
        # becomes:
        #
        # - time
        # - asset
        # - ledger_BRL
        # - ledger_USD
        # - balance_BRL
        # - balance_USD
        # - comment


        columns=dict()
        for prop in self.sheetStructure.keys():
            if prop == 'separator':
                continue
            colStructure=self.sheetStructure[prop]['columns']
            for k in colStructure.keys():
                if k=='monetary':
                    for m in colStructure[k]:
                        columns[m['name']]=prop + '_' + m['currency']
                else:
                    columns[colStructure[k]]=k

        if len(columns.keys())==0:
            raise Error("Sheet structure is mandatory at least to define currencies being used")

        return columns



    def refreshData(self):
        """
        Force data refresh from source URL and return a DataFrame which columns
        where already renamed and filtered, ready to be cached. But data still
        needs to be processed by self.processData().

        Data loaded is set in self._df and also returned by this method.
        """

        renamer=self.columnSchema()

        self._df=(
            pandas.read_csv(
                filepath_or_buffer = self.URI,
                sep = (
                    self.sheetStructure['separator']
                    if 'separator' in self.sheetStructure
                    else ','
                )
            )
            .rename(columns=renamer)
            .pipe(
                lambda table: table.drop(
                    # Drop all columns that doesn't matter
                    columns=list(
                        set(table.columns) -
                        set(list(renamer.values()))
                    )
                )
            )
        )

        return self._df



    def processData(self):
        """
        Called right after raw data is loaded from cache or from its original
        source (API, Internet, storage) to clean it up.
        """
        def ddebug(table):
            self.logger.debug(table)
            return table

        columnsProfile=self.sheetStructure[prop]['columns']
        monetaryColumns=[c for c in self._df if 'balance_' in c or 'ledger_' in c]
        # sheet=getattr(self,f'_{prop}')
        # monetaryColumns=[c['currency'] for c in columnsProfile['monetary']]

        # Timestamps whose time part is 0 will be shifted with naiveTimeShift
        # Shift ledger data to noon, shift balance data to 3 minutes later (12:03)
        naiveTimeShift=12*3600
        # if prop=='balance':
        #     naiveTimeShift+=3*60

        sheet=(
            self._df

            # Normalize NaNs
            .fillna(pandas.NA)
            .replace('#N/A',pandas.NA)

            # Remove rows that don't have asset names or monetary values
            .dropna(subset=monetaryColumns, how='all')
            .dropna(subset=[PortfolioColumn.ASSET])

            # Optimize and be gentle with storage
            .astype(
                dict(
                    asset = 'category'
                )
            )

            .assign(
                # Convert Date/Time to proper type
                time=lambda table: Portfolio.normalizeTime(
                    pandas.to_datetime(
                        table[PortfolioColumn.TIME],
                        format='mixed',
                        yearfirst=True,
                        utc=False
                    ),
                    naiveTimeShift
                )
            )
        )

        # Handle monetary columns, remove currency symbols and make them numbers
        remove=['R$ ','$','€','£','¥','₪','₨',',']
        for c in columnsProfile['monetary']:
            col=c['currency']
            if self._df[col].dtype==numpy.dtype('O'):
                ## Remove currency symbols and junk
                for r in remove:
                    self._df[col]=self._df[col].str.replace(r, '', regex=False)

                ## Make NaNs of empty ('') cells
                self._df[col]=self._df[col].str.replace(r'^\s*$','', regex=True)

                ## Convert to number
                self._df[col]=pandas.to_numeric(self._df[col]) #.astype(float)



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
    """
    Same concept as Portfolio, but can keep multiple sources of data.
    When data needs to be refreshed, this class will submit refresh signals to
    all its members.
    """
    def __init__(self, cache=None, refresh=False):
        self.members=[]

        super().__init__(
            name       = 'aggregator',
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
    ## Operations that will be dispatched to contained assets.
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
    def data(self):
        return (
            pandas.concat(
                [m.data for m in self.members]
            )
            .reset_index(drop=True)

            # Reorder columns based on what columns we actually have
            .pipe(
                lambda table:
                table[[
                    c for c in (PortfolioColumn.nonMonetary + PortfolioColumn.monetary)
                    if c in table.columns.get_level_values(0)
                ]]
            )
        )



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
    def asof(self,tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo):
        return numpy.max([p.asof for p in self.members]).tz_convert(tz)



    def tryCacheData(self):
        self.submitToMembers('tryCacheData')



    def submitToMembers(self, method: str):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            tasks={}
            for p in self.members:
                m = getattr(p,method)
                tasks[executor.submit(m)] = p

            for task in concurrent.futures.as_completed(tasks):
                self.logger.debug(f'Done {tasks[task]}')

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


