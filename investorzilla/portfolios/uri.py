import pathlib
import numpy
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
            # The URI can be a local file or even a remote http(s):// URL.
            # Anything supported by Pandas.read_csv()
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

                        # Name of assets on each row is under this column
                        asset: my asset

                        # Column called 'Saldo USD' contains values in 'USD' and so on.
                        monetary:
                            - currency:     USD
                              name:         Saldo USD
    """

    def __init__(self, URI, kind, sheetStructure, base='.', cache=None, refresh=False):

        if '://' in URI:
            self.URI=URI
        else:
            self.URI=pathlib.Path(URI).expanduser()
            if not self.URI.is_absolute():
                self.URI=(
                    (pathlib.Path(base).parent.resolve() / self.URI)
                    .resolve()
                    .as_uri()
                )

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
    ## Portfolio interface methods.
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
        """
        Force data refresh from source URL and return a DataFrame which columns
        where already renamed and filtered, ready to be cached. But data still
        needs to be processed by self.processData().

        The internal variables _balance or _ledger will be updated.
        """
        if self.has_balance:
            prop='balance'
        elif self.has_ledger:
            prop='ledger'
        else:
            raise NameError('Either balance or ledger sheet structure must be defined.')

        columnsProfile=self.sheetStructure[prop]['columns']

        # Normalize all column names
        renamer={m['name']: m['currency'] for m in columnsProfile['monetary']}
        renamer.update(
            {
                columnsProfile[k]: k
                for k in columnsProfile.keys() if k!='monetary'
            }
        )

        df=(
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

        setattr(self,f'_{prop}',df)

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
        def ddebug(table):
            self.logger.debug(table)
            return table

        sheet=getattr(self,f'_{prop}')
        columnsProfile=self.sheetStructure[prop]['columns']
        monetaryColumns=[c['currency'] for c in columnsProfile['monetary']]

        # Timestamps whose time part is 0 will be shifted with naiveTimeShift
        naiveTimeShift=12*3600
        if prop=='balance':
            naiveTimeShift+=3*60

        sheet=(
            sheet

            # Normalize NaNs
            .fillna(pandas.NA)
            .replace('#N/A',pandas.NA)

            # Remove rows that don't have asset names or monetary values
            .dropna(subset=monetaryColumns, how='all')
            .dropna(subset=['asset'])

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
                        table.time,
                        format='mixed',
                        yearfirst=True,
                        utc=False
                    ),
                    naiveTimeShift
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
                sheet[c['currency']]=pandas.to_numeric(sheet[c['currency']]) #.astype(float)

        setattr(self,f'_{prop}',sheet)



    def __repr__(self):
        return '{klass}<{kind}>({balance_or_ledger}={URI})'.format(
            URI               = self.URI,
            balance_or_ledger = 'balance' if self.has_balance else 'ledger',
            klass             = type(self).__name__,
            kind              = self.kind
        )



    def to_markdown(self, title_prefix=None):
        """
        Provides a markdown representation of this object to be used in the
        "Portfolio Components and Information" tab of Investorzilla's UI.
        """
        title="{klass}({kind})".format(klass=type(self).__name__,kind=self.kind)

        if '://' in str(self.URI):
            URI = f"[remote URL]({self.URI})"
        else:
            URI = f"`{self.URI}`"

        nonMonetary=set(['time','asset','comment'])

        if self.has_balance:
            data=self.balance
        else:
            data=self.ledger

        body=[
            "- {balance_or_ledger} from {URI}".format(
                balance_or_ledger = 'balance' if self.has_balance else 'ledger',
                URI=URI
            ),
            "- assets: `{}`".format('` · `'.join(data.asset.unique())),
            "- currencies: `{}`".format('` · `'.join(set(data.columns)-nonMonetary)),
            f"- from `{data.time.min()}` to `{data.time.max()}`"
        ]

        body='\n'.join(body)

        if title_prefix is None:
            return (title,body)
        else:
            return f"{title_prefix} {title}\n{body}"



