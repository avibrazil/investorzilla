import os
import datetime
import pickle
import logging
import concurrent.futures
import pandas as pd
import numpy

# python3 -m pip install -U google-api-python-client google-auth-httplib2 google-auth-oauthlib pandas_datareader --user

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


from .. import Portfolio


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



    def __init__(self, sheetStructure=None, credentialsFile='credentials.json', cache=None, refresh=False):
        self.sheetStructure = sheetStructure

        self._balance = None
        self._ledger = None

        super().__init__(
            kind       = 'gsheet',
            id         = self.sheetStructure['sheet'],
            cache      = cache,
            refresh    = refresh
        )



    ############################################################################
    ##
    ## Portfolio interface mathods.
    ##
    ## Concrete implementation of abstract virtual methods from Portfolio class
    ##
    ############################################################################
    

    @property
    def has_balance(self):
        return 'balance' in self.sheetStructure



    @property
    def has_ledger(self):
        return 'ledger' in self.sheetStructure



    def refreshData(self):
        self.creds = None

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
                    credentialsFile,
                    self.SCOPES
                )

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

            self._ledger=ledgerThread.result()
            self._balance=balanceThread.result()



    def processData(self):
        if self.has_balance:
            self.processSheetData('balance')
        if self.has_ledger:
            self.processSheetData('ledger')



    ############################################################################
    ##
    ## Internal methods
    ##
    ############################################################################
    
    def processSheetData(self, prop):
        sheet=getattr(self,f'_{prop}')
        columnsProfile=self.sheetStructure[prop]['columns']

        sheet=(
            sheet
            .replace('#N/A',pd.NA)
            .assign(
                # Convert Date/Time to proper types and name column as 'time'
                time=pd.to_datetime(sheet.time)
            )
            # Remove rows that don't have fund names
            .dropna(subset=['fund'])
            
            # Optimize and be gentle with storage
            .astype(
                dict(
                    fund = 'category'
                )
            )
        )

        # Handle monetary columns, remove currency symbols and make them numbers
        remove=['R$ ','$','€',',']
        for c in columnsProfile['monetary']:
            if sheet[c['currency']].dtype==numpy.dtype('O'):
                ## Remove currency symbols and junk
                for r in remove:
                    sheet[c['currency']]=sheet[c['currency']].str.replace(r, '', regex=False)

                ## Make NaNs of empty ('') cells
                sheet[c['currency']]=sheet[c['currency']].str.replace(r'^\s*$','', regex=True)

                ## Convert to number
                sheet[c['currency']]=pd.to_numeric(sheet[c['currency']]) #.astype(float)
            
        setattr(self,f'_{prop}',sheet)



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
        
        # Normalize all columns names
        renamer={m['name']: m['currency'] for m in columnsProfile['monetary']}        
        renamer.update(
            {
                columnsProfile[k]: k
                for k in columnsProfile.keys() if k!='monetary'
            }
        )
        
        return sheet.rename(columns=renamer)
                            


    def __repr__(self):
        return '{klass}({sheetid},balance={balance},ledger={ledger})'.format(
            sheetid         = self.sheetStructure['sheet'],
            balance         = self.sheetStructure['balance']['sheetRange'],
            ledger          = self.sheetStructure['ledger']['sheetRange'],
            klass           = type(self).__name__
        )