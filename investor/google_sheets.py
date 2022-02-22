import os
import datetime
import pickle
import logging
import concurrent.futures
import pandas as pd

# python3 -m pip install -U google-api-python-client google-auth-httplib2 google-auth-oauthlib pandas_datareader --user

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


from . import Fund
from . import DataCache


class GoogleSheetsBalanceAndLedger(object):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    def getGoogleSheetRange(self, SPREADSHEET_ID, DATA_TO_PULL):
        service = build('sheets', 'v4', credentials=self.creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=DATA_TO_PULL
        ).execute()
        values = result.get('values', [])

        if not values:
            return None

        rows = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=DATA_TO_PULL
        ).execute()

        data = rows.get('values')

        df = pd.DataFrame(data=data[1:],columns=data[0])

        return df



    def getMonetarySheet(self, sheetID, sheetRange, columnsProfile):

        sheet=self.getGoogleSheetRange(sheetID,sheetRange)

        sheet.replace('#N/A',pd.NA, inplace=True)

        # Handle monetary columns, remove currency symbols and make them numbers
        remove=['R$ ','$','€',',']
        for c in columnsProfile['monetary']:

            ## Remove currency symbols and junk
            for r in remove:
                sheet[c['name']]=sheet[c['name']].str.replace(r, '', regex=False)

            ## Make NaNs of empty ('') cells
            sheet[c['name']]=sheet[c['name']].str.replace(r'^\s*$','nan', regex=True)

            ## Convert to number
            sheet[c['name']]=sheet[c['name']].astype(float)

            ## Rename column to its currency name (BRL, USD, BTC etc)
            sheet.rename(columns={c['name']: c['currency']}, inplace=True)


        # Rename fund name column to 'fund'
        sheet.rename(columns={columnsProfile['fund']: 'fund'}, inplace=True)

        # Rename comment column, if any, to 'comment'
        if 'comment' in columnsProfile and columnsProfile['comment'] in sheet.columns:
            sheet.rename(columns={columnsProfile['comment']: 'comment'}, inplace=True)


        # Convert Date/Time to proper types and name column as 'time'
        sheet[columnsProfile['time']]=pd.to_datetime(sheet[columnsProfile['time']])
        sheet.rename(columns={columnsProfile['time']: 'time'}, inplace=True)


        # Remove rows that don't have fund names
        return sheet.dropna(subset=['fund'])



    def __init__(self, sheetStructure=None, credentialsFile='credentials.json', cache=None, refresh=False):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)


        self.sheetStructure = sheetStructure

        self.creds = None

        self.ledger = None
        self.balance = None

        if cache is not None:
#             self.logger.debug(cache)
            self.ledger  = cache.get(kind='ledger',  id=self.sheetStructure['sheet'])
            self.balance = cache.get(kind='balance', id=self.sheetStructure['sheet'])
            self.asof    = cache.last(kind='balance', id=self.sheetStructure['sheet'])

        if refresh or self.ledger is None or self.balance is None:
            if os.path.exists('token.pickle'):
                # Get credentials from pickle file
                with open('token.pickle', 'rb') as token:
                    self.creds = pickle.load(token)

            if not self.creds or not self.creds.valid:
                # No pickle yet
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    # Get credentials from Google JSON file
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentialsFile, self.SCOPES)

                    self.creds = flow.run_local_server(port=0)

                # Cache credentials in a pickle file for later use
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)


            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                ledgerThread=executor.submit(
                    self.getMonetarySheet,
                    **dict(
                        sheetID            = self.sheetStructure['sheet'],
                        sheetRange         = self.sheetStructure['ledger']['sheetRange'],
                        columnsProfile     = self.sheetStructure['ledger']['columns']
                    )
                )

                balanceThread=executor.submit(
                    self.getMonetarySheet,
                    **dict(
                        sheetID            = self.sheetStructure['sheet'],
                        sheetRange         = self.sheetStructure['balance']['sheetRange'],
                        columnsProfile     = self.sheetStructure['balance']['columns']
                    )
                )

            self.ledger=ledgerThread.result()
            self.balance=balanceThread.result()

#             self.ledger=self.getMonetarySheet(
#                 sheetID            = self.sheetStructure['sheet'],
#                 sheetRange         = self.sheetStructure['ledger']['sheetRange'],
#                 columnsProfile     = self.sheetStructure['ledger']['columns']
#             )
#
#
#             self.balance=self.getMonetarySheet(
#                 sheetID            = self.sheetStructure['sheet'],
#                 sheetRange         = self.sheetStructure['balance']['sheetRange'],
#                 columnsProfile     = self.sheetStructure['balance']['columns']
#             )

            self.asof=pd.Timestamp.utcnow()

            if cache:
                cache.set(kind='ledger',  id=self.sheetStructure['sheet'], data=self.ledger)
                cache.set(kind='balance', id=self.sheetStructure['sheet'], data=self.balance)

        self.ledger['time']  = pd.to_datetime(self.ledger['time'])
        self.balance['time'] = pd.to_datetime(self.balance['time'])

        # asof has UTC time, convert to TZ-aware localtime
        utcoffset=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        self.asof=self.asof.tz_convert(utcoffset)



    def getFund(self, subset=None, name=None, currencyExchange=None):
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
