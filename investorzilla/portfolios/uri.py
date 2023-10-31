import pathlib
import pandas

from .. import Portfolio


class URIBalanceOrLedger(Portfolio):
    """
    Use this Portfolio class if you keep your balance and ledger in CSV files,
    local or remote -- on any URL supported by pandas.read_csv().

    The UI passes a sheet structure dict to this class constructor so it knows
    which tabs and columns contains the information it needs. The UI get this
    information from investor_ui_config.yaml file, under
    portfolio.params.sheetStructure, which in turns define where in the
    spreadsheet are balance and ledger information. Here is an example
    for a investor_ui_config.yaml:

    portfolio:
        - type: !!python/name:investor.portfolios.uri.URIBalanceOrLedger ''
          params:
            # The URI can be a local file or even a remote http(s):// URL. Anything supported
            # by Pandas.read_csv()
            URI: balances.txt
            kind: traderbot_balance
            sheetStructure:
                separator: "|"
                # In here you describe how the BALANCE and LEDGER data is
                # organized in sheets and columns
                balance:
                    columns:
                        # Time is in column called 'time'
                        time: time

                        # Name of funds on each row is under this column
                        fund: fund

                        # Column called 'Saldo USD' contains values in 'USD' and so on.
                        monetary:
                            - currency:     USD
                              name:         Saldo USD
    """

    def __init__(self, URI, kind, sheetStructure, cache=None, refresh=False):
        self.URI = pathlib.Path(URI).expanduser()
        self.kind = kind
        self.sheetStructure = sheetStructure

        self._balance = None
        self._ledger = None

        super().__init__(
            kind       = f'uri•{kind}',
            id         = str(self.URI),   # extract just full name from Path object
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
        df=pandas.read_csv(
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
            .replace('#N/A',pandas.NA)

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
                    pandas.to_datetime(sheet.time),
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

