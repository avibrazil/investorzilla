import logging
import concurrent.futures
import pandas
import yaml

from .             import DataCache, MarketIndex, CurrencyExchange, PortfolioAggregator
from .currency     import brasil_banco_central     as currency_bcb
from .currency     import cryptocompare            as currency_cryptocompare
from .marketindex  import brasil_banco_central     as mktidx_bcb
from .marketindex  import federal_reserve          as mktidx_fred
from .marketindex  import yahoo_finance            as mktidx_yahoo
from .portfolios   import google_sheets            as google_sheets
from .portfolios   import uri                      as uri







class Investor(object):
    domains={'portfolio','currency_converters','benchmarks'}



    def __init__(self,file,refreshMap=dict(zip(domains,len(domains)*[False]))):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        defaultRefreshMap=dict(zip(self.domains,len(self.domains)*[False]))

        refresh=defaultRefreshMap
        refresh.update(refreshMap)

        with open(file, 'r', encoding="utf8") as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)

        self.currency=self.config['currency']

        self._cache               = None
        self.portfolio            = None
        self.currency_converters  = None
        self.benchmarks           = None
        self.exchange             = CurrencyExchange(self.currency)

        # Load all time series data from cache or web and compute derived data
        self.loadDomains(refresh)



    def loadDomains(self,refreshMap=dict(zip(domains,len(domains)*[False]))):
        """
        Load from cache or internet data for Portfolio, Currency Converters and
        Benchmarks.

        refreshMap is a dict that controls wether to load from cache or update
        domain from internet (and update cache). It looks like:

        dict(
            portfolio           = False,
            benchmarks          = False,
            currency_converters = False,
        )
        """

        defaultRefreshMap=dict(zip(self.domains,len(self.domains)*[False]))

        refresh=defaultRefreshMap
        refresh.update(refreshMap)

        # Decide wether we need to update extra benchmarks based on CurrencyConverters
        augmentDomains=False
        for dom in ['benchmarks','currency_converters']:
            augmentDomains=augmentDomains or refresh[dom] or not getattr(self,dom)

        # Decide wether we need to update CurrencyExchange object
        updateCurrencyExchange=False
        for dom in ['currency_converters']:
            updateCurrencyExchange=updateCurrencyExchange or refresh[dom] or not getattr(self,dom)

        with concurrent.futures.ThreadPoolExecutor(thread_name_prefix='load_domains') as executor:
            tasks={}

            for domain in self.domains:
                if refresh[domain] or getattr(self,domain) is None:
                    # Load if a refresh was requested or domain has nothing yet
                    setattr(self,domain,[])
                    for part in self.config[domain]:
                        if 'type' in part:
#                             self.logger.info(f"processing {part['type']}")
#                             self.logger.info(f"{part['params'].copy()}")
                            # If it contains a class that needs activation or loading

                            # Prepare parameters
                            theparams=part['params'].copy()
                            theparams.update(
                                dict(
                                    cache   = self.cache,
                                    refresh = refresh[domain]
                                )
                            )


                            task=executor.submit(
                                # The class
                                part['type'],

                                # The parameters for class’ __init__()
                                **theparams
                            )
                            tasks[task]=(domain,part)

            for task in concurrent.futures.as_completed(tasks):
                # Unpack what we’ve set previously
                (domain,part)=tasks[task]

                # Put resulting object under its config
                part['obj']=task.result()

                # Add to internal inventory
                getattr(self,domain).append(part)

        # Add more benchmarks as per config file
        if augmentDomains:
            self.augmentDomains()

        # Rearrange Portfolio
        if len(self.portfolio)>1:
            agg=PortfolioAggregator()
            agg.append([p['obj'] for p in self.portfolio])
            self.portfolio=agg
        else:
            self.portfolio=self.portfolio[0]['obj']

        if updateCurrencyExchange:
            # Setup a multiple currency exchange machine
            self.exchange=CurrencyExchange(self.currency)

            # Put all CurrencyConverters in a single useful CurrencyExchange machine
            for curr in self.currency_converters:
                self.exchange.addCurrency(curr['obj'])


    def augmentDomains(self):
        """
        Fabricate more benchmarks from currency converters, as specified by
        YAML config file.

        Entries such as the following from the YAML file will be engineered:

        benchmarks:
            - kind: from_currency_converter
              from_to: BRLUSD
        """

        for item in self.config['benchmarks']:
            if 'kind' in item and item['kind'] == 'from_currency_converter':
                curFrom = item['from_to'][:3]
                curTo   = item['from_to'][3:]

                benchmark_signature = '[{currency}] {name}'.format(
                    name=item['from_to'],
                    currency=curTo
                )

                # Delete old MarketIndex previously created by a CurrencyConverter
                self.benchmarks = [b for b in self.benchmarks if b['obj'].id!=curFrom+curTo]

                # Scan all currency converters we have to find a match
                for cc in self.currency_converters:
                    if curFrom == cc['obj'].currencyFrom and curTo == cc['obj'].currencyTo:
                        item['obj']=MarketIndex().fromCurrencyConverter(cc['obj'])
                        break
                    elif curTo == cc['obj'].currencyFrom and curFrom == cc['obj'].currencyTo:
                        item['obj']=MarketIndex().fromCurrencyConverter(cc['obj'].invert())
                        break

                if 'obj' in item:
                    self.benchmarks.append(item)
                else:
                    raise Exception(f'Can’t find "{item.kind}" CurrencyConverter to make a MarketIndex from.')

        # Sort benchmarks
        benchs={str(b['obj']): b for b in self.benchmarks}
        self.benchmarks=[benchs[k] for k in sorted(benchs)]



    @property
    def cache(self):
        if self._cache is None:
            self._cache=DataCache(self.config['cache_database'])
            self.logger.debug(f"Using cache: {self._cache}")

        return self._cache



    @property
    def currency(self):
        return self._currency



    @currency.setter
    def currency(self,name):
        self._currency=name

        if hasattr(self,'exchange'):
            self.exchange.currency=name



    def __repr__(self):
        return yaml.dump(
            {
                'Portfolio': self.portfolio.__repr__(),
                'Exchange': self.exchange.__repr__(),
                'Benchmarks': [x.__repr__() for x in self.benchmarks],
                'Currency converters': [x.__repr__() for x in self.currency_converters],
            },
            indent=6,
            canonical=False,
            default_flow_style=False
        )
