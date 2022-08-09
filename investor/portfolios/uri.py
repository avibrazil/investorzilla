import pandas as pd

from .. import Portfolio


class URIBalanceOrLedger(Portfolio):
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

    def __init__(self, URI, kind, sheetStructure, cache=None, refresh=False):
        self.URI = URI
        self.kind = kind
        self.sheetStructure = sheetStructure

        self._balance = None
        self._ledger = None

        super().__init__(
            kind       = f'uri•{kind}',
            id         = self.URI,
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
        df=pd.read_csv(
            filepath_or_buffer = self.URI,
            sep = self.sheetStructure['separator'] if 'separator' in self.sheetStructure else ','
        )
        
        if self.has_balance:
            prop='balance'
        elif self.has_ledger:
            prop='ledger'
        else:
            raise NameError('Either balance or ledger sheet structure must be defined.')

        columnsProfile=self.sheetStructure[prop]['columns']

        # Normalize all columns names
        renamer={m['name']: m['currency'] for m in columnsProfile['monetary']}        
        renamer.update(
            {
                columnsProfile[k]: k
                for k in columnsProfile.keys() if k!='monetary'
            }
        )
        
        setattr(self,f'_{prop}',df.rename(columns=renamer))
        
        return getattr(self,f'_{prop}')



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

        # Set the naiveTimeShift for ledger and balance
        naiveTimeShift=12*3600
        if prop=='balance':
            naiveTimeShift+=3*60
        
        sheet=(
            sheet
            .replace('#N/A',pd.NA)

            # Remove rows that don't have fund names
            .dropna(subset=['fund'])
            
            # Optimize and be gentle with storage
            .astype(
                dict(
                    fund = 'category'
                )
            )
            
            .assign(
                # Convert Date/Time to proper type
                time=Portfolio.normalizeTime(
                    pd.to_datetime(sheet.time),
                    naiveTimeShift
                )
            )
        )

        setattr(self,f'_{prop}',sheet)



    def __repr__(self):
        return '{klass}({URI})'.format(
            URI             = self.URI,
            klass           = type(self).__name__
        )

