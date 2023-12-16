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
        # Format for start in BCB API parameters is MM-DD-YYYY.
        tomorrow=(datetime.date.today()+datetime.timedelta(days=1)).strftime('%m-%d-%Y')

        start='01-01-1970'
        if self.currencyFrom=='USD':
            # Date of birth of BRLUSD. Before this date fiat was another thing
            # and values can't be mixed
            start='07-01-1994' # MM-DD-YYYY

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

        self.data=pandas.DataFrame(response.json()['value'])

        self.data.rename(columns={'dataHoraCotacao': 'time'}, inplace=True)



    def processData(self):
        self.data = (
            self.data

            .assign(
                value = lambda table: (table.cotacaoCompra+table.cotacaoVenda)/2,
                std   = lambda table: abs(table.cotacaoCompra/table.cotacaoVenda-1)
            )

            # Remove impossible values
            .query("cotacaoCompra!=0 and cotacaoVenda!=0 and std<0.2")

            .drop('cotacaoCompra cotacaoVenda std'.split(),axis=1)

            .assign(
                time = lambda table: (
                    pandas.to_datetime(table.time)

                    # Data source time is delivered as Brasilia local time
                    .dt.tz_localize('Brazil/East')

                    # Keep it as UTC internally because this is our standard
                    .dt.tz_convert('UTC')
                )
            )

            .drop_duplicates()

            .set_index('time')

            .sort_index()
        )
