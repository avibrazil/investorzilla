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


from .. import Fund, Portfolio


class GoogleSheetsBalanceAndLedger(Portfolio):
    """
    Use this Portfolio class if you keep your balance and ledger in a Google Sheet.
    An example spreadsheet is here: https://docs.google.com/spreadsheets/d/1AE0F_mzXTJJuuuQwPnSzBejRrmui01CfUUY1qyvnbkk/edit#gid=476533794

    The UI passes a sheet structure dict to this class constructor so it which tabs and
    columns contains the information it needs. The UI get this information from
    investor_ui_config.yaml file, under portfolio.params.sheetStructure, which in turns
    define where in the spreadsheet are balance and ledger information. Here is an example
    for a investor_ui_config.yaml:

    portfolio:
        - type: !!python/name:investor.google_sheets.GoogleSheetsBalanceAndLedger ''
          params:
            credentialsFile: credentials.json
            sheetStructure:
                # This Google Sheet is an example that should work out of the box
                # See it at https://docs.google.com/spreadsheets/d/1AE0F_mzXTJJuuuQwPnSzBejRrmui01CfUUY1qyvnbkk
                sheet: 1AE0F_mzXTJJuuuQwPnSzBejRrmui01CfUUY1qyvnbkk

                # In here you describe how the BALANCE and LEDGER data is
                # organized in sheets and columns
                balance:
                    # The sheet/tab range with your balances
                    sheetRange: Balances!A:D
                    columns:
                        # Time is in column called 'Data'
                        time: Date and time

                        # Name of funds on each row is under this column
                        fund: Compound fund

                        # Column called 'Saldo USD' contains values in 'USD' and so on.
                        monetary:
                            - currency:     BRL
                              name:         Balance BRL
                            - currency:     USD
                              name:         Balance USD

                ledger:
                    # The sheet/tab with all your in and out movements (ledger)
                    sheetRange: Ledger!A:E
                    columns:
                        time: Date and time
                        fund: Compound fund

                        # Name of columns with random comments
                        comment: Comment
                        monetary:
                            - currency:     BRL
                              name:         Mov BRL
                            - currency:     USD
                              name:         Mov USD
    """
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    def getGoogleSheetRange(self, SPREADSHEET_ID, DATA_TO_PULL):
        """
        Pull raw data from a Google Sheet, given the GSheets ID and the cell range.

        SPREADSHEET_ID is something like '1iBlzY...wuY_b...so'
        DATA_TO_PULL is like 'Balances!A:D'
        """
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
        """
        Pull raw data from a Google Sheet, given the GSheets ID and the cell range.
        And then clean, interpret and add semantic based on columnsProfile.

        columnsProfile is a dict with this layout:

            # Time is in column called 'Date and time'
            time: Date and time

            # Name of funds on each row is under this column
            fund: Compound fund

            # Column called 'Saldo USD' contains values in 'USD' and so on.
            monetary:
                - currency:     BRL
                  name:         Balance BRL
                - currency:     USD
                  name:         Balance USD
        """
        sheet=self.getGoogleSheetRange(sheetID,sheetRange)

        sheet.replace('#N/A',pd.NA, inplace=True)

        # Handle monetary columns, remove currency symbols and make them numbers
        remove=['R$ ','$','€',',']
        for c in columnsProfile['monetary']:

            ## Remove currency symbols and junk
            for r in remove:
                sheet[c['name']]=sheet[c['name']].str.replace(r, '', regex=False)

            ## Make NaNs of empty ('') cells
            sheet[c['name']]=sheet[c['name']].str.replace(r'^\s*$','', regex=True)

            ## Convert to number
            sheet[c['name']]=pd.to_numeric(sheet[c['name']]) #.astype(float)

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
        super().__init__(cache=cache, refresh=refresh)

        self.sheetStructure = sheetStructure
        
        self.creds = None

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




    def __repr__(self):
        return '{klass}({sheetid},balance={balance},ledger={ledger})'.format(
            sheetid         = self.sheetStructure['sheet'],
            balance         = self.sheetStructure['balance']['sheetRange'],
            ledger          = self.sheetStructure['ledger']['sheetRange'],
            klass           = type(self).__name__
        )

