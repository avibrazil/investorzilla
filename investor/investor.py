import logging
import concurrent.futures
import pandas
import yaml

from . import DataCache, MarketIndex, CurrencyExchange
from .currency     import brasil_banco_central     as currency_bcb
from .currency     import cryptocompare            as currency_cryptocompare
from .marketindex  import brasil_banco_central     as mktidx_bcb
from .marketindex  import federal_reserve          as mktidx_fred
from .marketindex  import yahoo_finance            as mktidx_yahoo
from .portfolios   import google_sheets            as google_sheets


class Investor(object):
    domains={'portfolio','currency_converters','benchmarks'}


    @property
    def cache(self):
        if self._cache is None:
            self._cache=DataCache(self.context['cache_database'])

        return self._cache


    def loadDomains(self,refreshMap=dict(zip(domains,len(domains)*[False]))):
        """
        Load from cache or internet data for Portfolio, Currency Converters and
        Benchmarks.

        refreshMap is a dict that controls wether to load from cache or update domain
        from internet (and update cache). It looks like:

        dict(
            portfolio = False,
            benchmarks = False,
            currency_converters = False,
        )
        """

        defaultRefreshMap=dict(zip(self.domains,len(self.domains)*[False]))

        refresh=defaultRefreshMap
        refresh.update(refreshMap)

        with concurrent.futures.ThreadPoolExecutor(thread_name_prefix='load_domains') as executor:
            tasks={}
            for d in self.domains:
                for p in self.context[d]:
                    if 'type' in p:
                        params=p['params'].copy()
                        params.update(
                            dict(
                                cache   = self.cache,
                                refresh = refresh[d]
                            )
                        )
                        t=executor.submit(p['type'],**params)
                        tasks[t]=(d,p)
            results={}
            for task in concurrent.futures.as_completed(tasks):
                if tasks[task][0] in results:
                    results[tasks[task][0]].append(task.result())
                else:
                    results[tasks[task][0]]=[task.result()]

            self.portfolio           = results['portfolio']
            self.currency_converters = results['currency_converters']
            self.benchmarks          = results['benchmarks']



    def augmentDomains(self):
        """
        Fabricate more benchmarks from currency converters, as specified by YAML config
        file.

        Entries such as the following from the YAML file will be converted:

        benchmarks:
            - kind: from_currency_converter
              from_to: BRLUSD
        """
        for item in self.context['benchmarks']:
            if 'kind' in item and item['kind'] == 'from_currency_converter':
                curFrom = item['from_to'][:3]
                curTo   = item['from_to'][3:]

                benchmark_signature = '[{currency}] {name}'.format(
                    name=item['from_to'],
                    currency=curTo
                )

                # Scan all currency converters we have to find a match
                for cc in self.currency_converters:
                    if curFrom == cc.currencyFrom and curTo == cc.currencyTo:
                        cc_as_mi=MarketIndex().fromCurrencyConverter(cc)
                        break
                    elif curTo == cc.currencyFrom and curFrom == cc.currencyTo:
                        cc_as_mi=MarketIndex().fromCurrencyConverter(cc.invert())
                        break

                if cc_as_mi:
                    self.benchmarks.append(cc_as_mi)
                else:
                    raise Exception(f'Can’t find "{item.kind}" CurrencyConverter to make a MarketIndex from.')

        self.benchmarks.sort()



    def __init__(self,file,refreshMap=dict(zip(domains,len(domains)*[False]))):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        defaultRefreshMap=dict(zip(self.domains,len(self.domains)*[False]))

        refresh=defaultRefreshMap
        refresh.update(refreshMap)

        self._cache=None
        self.portfolio=None
        self.currency_converters=None
        self.benchmarks=None

        with open(file, 'r') as f:
            self.context = yaml.load(f, Loader=yaml.FullLoader)

        # Load all time series data from cache or web
        self.loadDomains(refresh)

        # Setup some more benchmarks from some loaded currency converters
        self.augmentDomains()

        # Setup a multiple currency exchange machine
        self.exchange=CurrencyExchange(self.context['currency'])

        # Put all CurrencyConverters in a single useful CurrencyExchange machine
        for curr in self.currency_converters:
            self.exchange.addCurrency(curr)



    def __repr__(self):
        return yaml.dump(
            {
                'Portfolio': [x.__repr__() for x in self.portfolio],
                'Exchange': self.exchange.__repr__(),
                'Benchmarks': [x.__repr__() for x in self.benchmarks],
                'Currency converters': [x.__repr__() for x in self.currency_converters],
            },
            indent=6,
            canonical=False,
            default_flow_style=False
        )
