import pandas
import pandas_datareader

from .. import MarketIndex


class FREDMarketIndex(MarketIndex):
    """
    Any market index from https://fred.stlouisfed.org/categories/32255

    Use the tag in the URL in the `name` parameter. For example, in the page above,
    the `S&P 500` has URL https://fred.stlouisfed.org/series/SP500, so use name=SP500.

    """
    def __init__(self, name, isRate=False, cache=None, refresh=False):
        super().__init__(kind='DataReaderFRED', id=name, currency='USD', isRate=isRate, cache=cache, refresh=refresh)


    def refreshData(self):
        self.data = pandas_datareader.data.DataReader([self.id], 'fred','1900-01-01')

        # Put a standard column name
        self.data.rename(columns={self.id: 'value'}, inplace=True)

#         # Rename index to our standard
#         self.data.index.name='time'

        # Make the index a regular column for caching purposes
        self.data.reset_index(inplace=True)



    def processData(self):
        # Convert time to a new column
        self.data['time']=pandas.to_datetime(self.data.DATE)

        # Set it as the index
        self.data.set_index('time', inplace=True)
        self.data.sort_index(inplace=True)

        # Drop old column
        self.data.drop('DATE', axis=1)

        self.data.fillna(method='ffill', axis=0, inplace=True)

        # Compute rate from daily values
        self.data['rate']=self.data['value']/self.data.shift()['value']-1


