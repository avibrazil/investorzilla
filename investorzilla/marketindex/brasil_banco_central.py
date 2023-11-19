import pandas

from .. import MarketIndex

class BCBMarketIndex(MarketIndex):
    # Tabela (dita obsoleta) com o código dos índices:
    # https://www.bcb.gov.br/estatisticas/indecoreestruturacao

    series={
        'CDI': dict(
            url="https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json",
            home=''
        ),
        'IPCA': dict(
            # IPCA Serviços. Outros IPCAs: https://dadosabertos.bcb.gov.br/dataset?q=ipca
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json",
            home = 'https://dadosabertos.bcb.gov.br/dataset/10844-indice-de-precos-ao-consumidor-amplo-ipca---servicos'
        ),
        'SELIC': dict(
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json",
            home = 'https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic'
        ),
        'IGPM': dict(
            # url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4175/dados?formato=json",
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json",
            home = 'https://dadosabertos.bcb.gov.br/dataset/4175-divida-mobiliaria---participacao-por-indexador---posicao-em-carteira---igp-m'
        ),
        'INPC': dict(
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.188/dados?formato=json",
            home = ''
        ),
    }



    def __init__(self, name, isRate=True, cache=None, refresh=False):
        if name in self.series:
            s=self.series[name]
        else:
            raise Exception(f'BCBMarketIndex: market index not found: {name}')

        super().__init__(kind='BCBMarketIndex', id=name, currency='BRL', isRate=isRate, cache=cache, refresh=refresh)



    @property
    def home(self):
        return self.series[self.id]['home']



    def refreshData(self):
        try:
            self.data=pandas.read_json(self.series[self.id]['url'])
        except BaseException as err:
            self.logger.warning(f"URL was: {self.series[self.id]['url']}")
            raise



    def processData(self):
        self.data=(
            self.data

            # Create columns
            .assign(
                time=lambda table: (
                    (
                        # Convert to datetime
                        pandas.to_datetime(table.data,dayfirst=True) +

                        # This is date-only information but we know this is the
                        # end of the day
                        pandas.Timedelta(hours=22, minutes=59)
                    )
                    # Set timezone to Brasilia
                    .dt
                    .tz_localize('Brazil/East')

                    # Keep it as UTC as module´s internal standard and to
                    # improve precision of joins.
                    .dt
                    .tz_convert('UTC')
                ),

                # Convert rate to our standards
                rate=lambda table: table.valor/100,

                # Init a column for value
                value=None
            )

            # Remove unused
            .drop(columns=['data', 'valor'])

            # Time as index
            .set_index('time')
            .sort_index()

            # Export only these columns (and time in the index)
            [['rate','value']]
        )

        # Now compute value like this:
        #
        #          {  n=0: 1 + rateₙ
        # valueₙ = {
        #          {  n≠0: valueₙ₋₁ ✕ (1 + rateₙ)
        #

        # At this point we have a dataframe indexed by time with 2 columns:
        # - rate (index 0)
        # - value (index 1, with no data yet)

        for n in range(self.data.shape[0]):
            self.data.iat[n,1] = (
                1+self.data.iat[n,0]
                if n==0
                else self.data.iat[n-1,1]*(1+self.data.iat[n,0])
            )
