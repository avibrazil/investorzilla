import os
import importlib
import datetime
import pathlib
import logging
import concurrent.futures
import yaml
import pandas
import numpy

# python3 -m pip install -U google-api-python-client google-auth-httplib2 google-auth-oauthlib pandas_datareader --user

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


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
            # A tag to differentiate from other data from same GSheet
            kind: form_entry

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

                        # Name of assets on each row is under this column
                        asset: Compound asset

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
                        asset: Compound asset

                        # Name of columns with random comments
                        comment: Comment
                        monetary:
                            - currency:     BRL
                              name:         Mov BRL
                            - currency:     USD
                              name:         Mov USD
    """

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    def showme():
        return pathlib.Path(importlib.util.find_spec('investorzilla').submodule_search_locations[0]) / pathlib.Path('portfolios/app-credentials-for-google-sheets.json')

    def __init__(self, kind='generic', sheetStructure=None, credentialsFile='credentials.json', cache=None, refresh=False):
        self.sheetStructure = sheetStructure
        self.kind = kind

        self._balance = None
        self._ledger = None
        self.gAppCredentialsFile = (
            pathlib.Path(importlib.util.find_spec('investorzilla').submodule_search_locations[0]) /
            pathlib.Path('portfolios/app-credentials-for-google-sheets.json')
        )

        super().__init__(
            kind       = f'gsheet•{kind}',
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
        gAccountCredFileName='google-account-credentials.yaml'
        self.creds = None

        if os.path.exists(gAccountCredFileName):
            # Get credentials from YAML file
            with open(gAccountCredFileName, 'r') as token:
                self.creds = yaml.load(token, Loader=yaml.Loader)

        if not self.creds:
            self.creds=dict()

        if (
            (self.sheetStructure['sheet'] not in self.creds) or (
                (self.sheetStructure['sheet'] in self.creds) and
                (self.creds[self.sheetStructure['sheet']].valid==False)
            )
        ):
            # Google token is expired, invalid or non-existent.
            # Make user authenticate and authorize access in the browser.
            # Get credentials from Google JSON file

            self.logger.info('Google authentication…')
            flow = InstalledAppFlow.from_client_secrets_file(
                self.gAppCredentialsFile,
                self.SCOPES
            )

            self.creds[self.sheetStructure['sheet']] = flow.run_local_server(port=0)

            # Cache user credentials in a YAML file for later use
            with open(gAccountCredFileName, 'w') as token:
                yaml.dump(self.creds, token)

        self.logger.debug(self.creds)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            if 'ledger' in self.sheetStructure:
                ledgerThread=executor.submit(
                    self.getMonetarySheet,
                    **dict(
                        sheetID            = self.sheetStructure['sheet'],
                        sheetRange         = self.sheetStructure['ledger']['sheetRange'],
                        columnsProfile     = self.sheetStructure['ledger']['columns']
                    )
                )

            if 'balance' in self.sheetStructure:
                balanceThread=executor.submit(
                    self.getMonetarySheet,
                    **dict(
                        sheetID            = self.sheetStructure['sheet'],
                        sheetRange         = self.sheetStructure['balance']['sheetRange'],
                        columnsProfile     = self.sheetStructure['balance']['columns']
                    )
                )

            if 'ledger' in self.sheetStructure:
                self._ledger=ledgerThread.result()

            if 'balance' in self.sheetStructure:
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
        """
        Given any balance or ledger sheet (defined by prop), clean data,
        convert data types and normalize time column.
        """
        sheet=getattr(self,f'_{prop}')
        columnsProfile=self.sheetStructure[prop]['columns']

        # Set the naiveTimeShift to 12:00 for ledger and 12:03 for balance
        naiveTimeShift=12*3600
        if prop=='balance':
            naiveTimeShift+=3*60

        sheet=(
            sheet
            .replace('#N/A',pandas.NA)

            # Remove rows that don't have asset names
            .dropna(subset=['asset'])

            # Remove rows that have no data on monetary columns
            .dropna(
                subset=[c['currency'] for c in columnsProfile['monetary']],
                how='all'
            )

            # Optimize and be gentle with storage
            .astype(
                dict(
                    asset = 'category'
                )
            )

            # Convert Date/Time to proper type
            .assign(
                time=lambda table: Portfolio.normalizeTime(
                    pandas.to_datetime(
                        table.time,
                        format='mixed',
                        yearfirst=True
                    ),
                    naiveTimeShift
                )
            )

            # Normalize NaNs
            .fillna(pandas.NA)
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
                sheet[c['currency']]=pandas.to_numeric(sheet[c['currency']]) #.astype(float)

        setattr(self,f'_{prop}',sheet)



    def getGoogleSheetRange(self, SPREADSHEET_ID, DATA_TO_PULL):
        """
        Pull raw data from a Google Sheet, given the GSheets ID and the cell range.

        SPREADSHEET_ID is something like '1iBlzY...wuY_b...so'
        DATA_TO_PULL is like 'Balances!A:D'
        """
        service = build('sheets', 'v4', credentials=self.creds[self.sheetStructure['sheet']])
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

        # The data is a list of lists, having column names in the first row.
        # Sometimes it has more column names than data, so each data row might be smaller
        # than the number of columns. So to be safe we'll have to create the DataFrame
        # in a more complex way

        return (
            # Create anonymous DataFrame, without column names
            pandas.DataFrame(data[1:])

            # Put column names on the ones that have data
            .pipe(
                lambda table: table.rename(dict(zip(table.columns,data[0])), axis=1)
            )

            # Create empty columns for remaining columns
            .pipe(
                lambda table: table.assign(
                    **{c:None for c in list(set(data[0])-set(table.columns))}
                )
            )
        )



    def getMonetarySheet(self, sheetID, sheetRange, columnsProfile):
        """
        Pull raw data from a Google Sheet, given the GSheets ID and the cell
        range. And then just rename columns following spec on columnsProfile.

        columnsProfile is a dict with this layout:

            # Time is in column called 'Date and time'
            time: Date and time

            # Name of assets on each row is under this column
            asset: Compound asset

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
        balanceOrLedger='{}={}'

        bl = [
            balanceOrLedger.format(s,self.sheetStructure[s]['sheetRange'])
            for s in ['balance','ledger'] if s in self.sheetStructure
        ]

        return '{klass}({sheetid},{bl})'.format(
            sheetid  = self.sheetStructure['sheet'],
            bl       = ','.join(bl),
            klass    = type(self).__name__
        )