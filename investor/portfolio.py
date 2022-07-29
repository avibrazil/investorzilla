import os
import datetime
import pickle
import logging
import concurrent.futures
import numpy
import pandas as pd


from . import Fund
from . import DataCache


class Portfolio(object):
    """
    A simple interface for a generic Portfolio.

    A Portfolio is the keeper of raw balance and ledger of multiple investment
    instruments, funds etc. Members of a Portfolio can be aggregated to generate one Fund
    which in turns has a time series for number of shares and a time series for share
    value.

    Derived classes must set self.ledger and self.balance in order for the Fund creation
    logic to work.
    """
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
        
        # Force data load
        self.balance
        self.ledger



    def getFund(self, subset=None, name=None, currencyExchange=None):
        """
        Given one or more investment items names, passed in the subset
        attribute, return a Fund object which allows handling it as share,
        share value and currency.
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
            .groupby(by='fund').agg(list)



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
        if self.cache is not None:
            (self._ledger,ledger_age)  = self.cache.get(kind=f'{self.kind}__ledger', id=self.id)
            (self._balance,balance_age) = self.cache.get(kind=f'{self.kind}__balance', id=self.id)

            if self._ledger is not None or self._balance is not None:
                self.asof=ledger_age if ledger_age else balance_age
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
        
        # Time zone aware current time
        self.asof=(
            pd.Timestamp.utcnow()
            .tz_convert(
                datetime.datetime.now(
                    datetime.timezone.utc
                )
                .astimezone()
                .tzinfo
            )
        )
        
        
        
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
            pd.concat(
                [p._balance for p in self.members if p.has_balance]
            )
            .reset_index(drop=True)
        )



    @property
    def _ledger(self):
        return (
            pd.concat(
                [p._ledger for p in self.members if p.has_ledger]
            )
            .reset_index(drop=True)
        )



    @property
    def asof(self):
        return numpy.max([p.asof for p in self.members])



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
