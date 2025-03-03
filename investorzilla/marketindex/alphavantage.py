import datetime
import pandas

from .. import MarketIndex


class AlphaVantageMarketIndex(MarketIndex):
    """
    Any market index from Alpha Vantage.

    Pass to name attribute the index name such as 'AAPL' or 'IBM'.
    AV doesn't provide market indexes such as NASDAQ (IXIC) or S&P500 (GSPC).
    There are ETFs that can be used to mimic these indexes. Example:

    Index                 Use this ETF
    S&P500                SPY
    S&P500                IVV
    NASDAQ                QQQ
    Índice BoVESPa        BOVA11.SAO

    List of symbols can be explored at
    https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={SOME KEYWORD}&apikey={YOUR API KEY}&datatype=json
    """

    # url='https://query1.finance.yahoo.com/v7/finance/download/{ticker}?period1={start}&period2={now}&interval=1d&events=history&includeAdjustedClose=true'
    # home='https://finance.yahoo.com/quote/{ticker}'

    url='https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={key}&datatype=csv&outputsize=full'
    home='https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={ticker}'

    def __init__(self, name, friendlyName=None, currency='USD', apiKey='demo', isRate=False, cache=None, refresh=False):
        self.friendlyName=friendlyName
        self.apiKey=apiKey

        super().__init__(
            kind     = 'AlphaVantageMarketIndex',
            id       = name,
            currency = currency,
            isRate   = isRate,
            cache    = cache,
            refresh  = refresh
        )



    def refreshData(self):
        self.data=pandas.read_csv(
            self.url.format(
                ticker=self.id,
                key=self.apiKey
            )
        )



    def processData(self):
        # Convert time to a new column
        self.data=(
            self.data

            .assign(
                time=lambda table: (
                    pandas.to_datetime(table.timestamp, utc=True) +

                    # This is date-only information but we know this is the
                    # end of the day
                    pandas.Timedelta(hours=23, minutes=55)
                ),

                # Make the rate column
                rate=lambda table: (table.close/table.close.shift())-1
            )

            .set_index('time')
            .sort_index()

            .pipe(
                # Delete all columns except time, rate and close
                lambda table: table.drop(
                    columns=list(
                        set(table.columns) -
                        set('time close rate'.split())
                    )
                )
            )

            .rename(columns={'close': 'value'})

            .ffill()
        )



    def get_name(self):
        return self.friendlyName if self.friendlyName else self.id



    def to_markdown(self, title_prefix=None):
        (title,body)=super().to_markdown()

        # Overwrite title with a specialization from this class
        title=f"{self.friendlyName} ({self.currency}) ({type(self).__name__})"

        if title_prefix is None:
            return (title,body)
        else:
            return f"{title_prefix} {title}\n{body}"

