import datetime
import pandas

from .. import MarketIndex


class YahooMarketIndex(MarketIndex):
    """
    Any market index from Yahoo Finance.

    Pass to name attribute index names such as `^DJI` (Dow Jones), `^IXIC` (NASDAQ) etc.

    """

    url='https://query1.finance.yahoo.com/v7/finance/download/{ticker}?period1={start}&period2={now}&interval=1d&events=history&includeAdjustedClose=true'

    def __init__(self, name, friendlyName=None, currency='USD', isRate=False, cache=None, refresh=False):
        super().__init__(
            kind     = 'YahooMarketIndex',
            id       = name,
            currency = currency,
            isRate   = isRate,
            cache    = cache,
            refresh  = refresh
        )

        self.friendlyName=friendlyName



    def refreshData(self):
        self.data=pandas.read_csv(
            self.url.format(
                ticker=self.id,
                start=round(datetime.datetime(1900,1,1).timestamp()),
                now=round(datetime.datetime.utcnow().timestamp()+3600*24)
            )
        )



    def processData(self):
        # Convert time to a new column
        self.data=(
            self.data

            .assign(
                time=lambda table: (
                    pandas.to_datetime(table.Date, utc=True) +

                    # This is date-only information but we know this is the
                    # end of the day
                    pandas.Timedelta(hours=23, minutes=55)
                ),

                # Make the rate column
                rate=lambda table: (table.Close/table.Close.shift())-1
            )

            .set_index('time')

            .pipe(
                # Delete all columns except time, rate and Close
                lambda table: table.drop(
                    columns=list(
                        set(table.columns) -
                        set('time Close rate'.split())
                    )
                )
            )

            .rename(columns={'Close': 'value'})

            .fillna(method='ffill', axis=0)
        )



    def __str__(self):
        if self.friendlyName is not None:
            return '[{currency}] {name}'.format(
                name=self.friendlyName,
                currency=self.currency
            )
        else:
            return super().__str__()