import datetime
import logging
import urllib
import requests
import numpy
import pandas

from .. import CurrencyConverter


class BCBCurrencyConverter(CurrencyConverter):
    """
    CurrencyConverter with data from Banco Central do Brasil.
    currencyFrom supports 'USD' and 'EUR'.

    https://dadosabertos.bcb.gov.br/dataset/dolar-americano-usd-todos-os-boletins-diarios

    https://dadosabertos.bcb.gov.br/dataset/taxas-de-cambio-todos-os-boletins-diarios
    """
    def __init__(self, currencyFrom, cache=None, refresh=False):
        super().__init__(
            currencyFrom  = currencyFrom,
            currencyTo    = 'BRL',

            kind          = 'BCBCurrencyConverter',
            id            = currencyFrom,

            cache         = cache,
            refresh       = refresh
        )



    def refreshData(self):
        tomorrow=(datetime.date.today()+datetime.timedelta(days=1)).strftime('%m-%d-%Y')
        if self.currencyFrom=='USD':
            start='07-01-1994'
        else:
            start='01-01-1970'
        ptax="https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"

        ptaxParams={
            '@moeda':                f"'{self.currencyFrom}'",
            '@dataInicial':          f"'{start}'",
            '@dataFinalCotacao':     f"'{tomorrow}'",
            '$select':               'dataHoraCotacao,cotacaoCompra,cotacaoVenda',
            '$format':               'json',
        }

        ptaxParamsStr = urllib.parse.urlencode(ptaxParams, safe="@$', ")

        response=requests.get(ptax,params=ptaxParamsStr)

#         logging.debug(response.content[:700])

        self.data=pandas.DataFrame(response.json()['value'])

        self.data.rename(columns={'dataHoraCotacao': 'time'}, inplace=True)

#         print(self.data.head())




    def processData(self):
        self.data = (
            self.data
            
            .assign(
                value = lambda table: (table.cotacaoCompra+table.cotacaoVenda)/2,
            )
            .drop('cotacaoCompra cotacaoVenda'.split(),axis=1)

            .assign(
                time  = lambda table: (
                    (
                        pandas.to_datetime(table.time,utc=True)
                        
                        # convert index to number of nanoseconds since
                        # 1970-01-01T00:00:00
                        .astype(numpy.int64)
                        
                        # Add some seconds of entropy to the index to eliminate repeated values
                        + numpy.random.randint(
                            low  = -10*(10**9),
                            high =  10*(10**9),
                            size =  len(table.time),
                            dtype=  numpy.int64
                        )
                    )
                    .pipe(pandas.to_datetime)
                    
                    .dt
                    
                    # Set timezone to Brasilia
                    .tz_localize('Brazil/East')
        
                    .dt
        
                    # Keep it as UTC as module´s internal standard and to improve
                    # precision of joins.
                    .tz_convert('UTC')
                    
                )
            )
            
            .set_index('time')

            .sort_index()
        )
