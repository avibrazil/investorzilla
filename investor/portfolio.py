import os
import datetime
import pickle
import logging
import concurrent.futures
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
    def __init__(self, cache=None, refresh=False):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.ledger = None
        self.balance = None

        self.asof = None



    def getFund(self, subset=None, name=None, currencyExchange=None):
        """
        Given one or more investment items names, passed in the subset attribute, return
        a Fund object which allows handling it as share, share value and currency.
        """
        if subset is None or (isinstance(subset,list) and len(subset)==0):
            # Return all funds
            return Fund(
                name=name,
                ledger=self.ledger,
                balance=self.balance,
                currencyExchange=currencyExchange,
            )
        else:
            if isinstance(subset, str):
                # If only 1 fund passed, turn it into a list
                subset=[subset]


            # And return only this subset of funds
            return Fund(
                name=name,
                ledger=self.ledger[self.ledger.fund.isin(subset)],
                balance=self.balance[self.balance.fund.isin(subset)],
                currencyExchange=currencyExchange,
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
        return list(
#             self.ledger.droplevel(1)[
            self.ledger[
                ['fund'] +
                # Get only currency names
                [x['currency'] for x in self.sheetStructure['ledger']['columns']['monetary']]
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
