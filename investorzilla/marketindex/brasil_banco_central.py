import urllib
import concurrent.futures
import pandas

from .. import MarketIndex

class BCBMarketIndex(MarketIndex):
    # Tabela (dita obsoleta) com o código dos índices:
    # https://www.bcb.gov.br/estatisticas/indecoreestruturacao

    series={
        'SELIC': dict(
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json",
            home = 'https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic',
            paged = True
        ),
        'CDI': dict(
            url="https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json",
            home='https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=12',
            paged = True
        ),
        'IPCA': dict(
            # IPCA Serviços. Outros IPCAs: https://dadosabertos.bcb.gov.br/dataset?q=ipca
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json",
            home = 'https://dadosabertos.bcb.gov.br/dataset/10844-indice-de-precos-ao-consumidor-amplo-ipca---servicos',
            paged = False
        ),
        'IGPM': dict(
            # url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4175/dados?formato=json",
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json",
            home = 'https://dadosabertos.bcb.gov.br/dataset/4175-divida-mobiliaria---participacao-por-indexador---posicao-em-carteira---igp-m',
            paged = False
        ),
        'INPC': dict(
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.188/dados?formato=json",
            home = 'https://www3.bcb.gov.br/sgspub/consultarmetadados/consultarMetadadosSeries.do?method=consultarMetadadosSeriesInternet&hdOidSerieSelecionada=188',
            paged = False
        ),
    }

    paged_period_params='&dataInicial={start:%d/%m/%Y}&dataFinal={end:%d/%m/%Y}'

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
        if self.series[self.id]['paged']:
            # Generate periods of 5 years from today until 1980
            periods = pandas.date_range(
                start=pandas.Timestamp.today() + pandas.Timedelta(days=1),
                end=pandas.Timestamp('1980-01-01'),
                freq='-60ME'
            )

            # Read URL content for multiple periods in parallel
            with concurrent.futures.ThreadPoolExecutor(thread_name_prefix='load_domains') as executor:
                tasks=dict()
                self.data=None
                for i in range(len(periods)):
                    if i+1==len(periods):
                        break
                    end=periods[i]
                    start=periods[i+1]
                    # display(url.format(start=start,end=end))
                    url=(
                        (self.series[self.id]['url']+self.paged_period_params)
                        .format(
                            start=start,
                            end=end
                        )
                    )

                    # Read URL in background
                    task=executor.submit(
                        # Method to execute in background
                        pandas.read_json,

                        # Parameters to the method: the index URL
                        url
                    )

                    tasks[task]=(self.id,start,end)

                for task in concurrent.futures.as_completed(tasks):
                    try:
                        if self.data is None:
                            self.data=task.result()
                        else:
                            self.data=pandas.concat([self.data,task.result()])
                    except urllib.error.HTTPError as e:
                        self.logger.warning(f"Failed to retrieve {tasks[task][0]} for period {tasks[task][1]} → {tasks[task][2]}. Probably data series has no data for period.")

            # Concatenate all results together and do minimum processing
            self.data=(
                self.data
                .assign(
                    time=lambda table: (
                        (
                            # Convert to datetime
                            pandas.to_datetime(table.data,dayfirst=True) +

                            # This is date-only information but we know this is the
                            # end of the day
                            pandas.Timedelta(hours=22, minutes=59)
                        )
                    ),
                )
                .sort_values('time')
                .drop('time',axis=1)
                .drop_duplicates()
            )
        else:
            try:
                self.data=pandas.read_json(self.series[self.id]['url'])
            except urllib.error.URLError as err:
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
