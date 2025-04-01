import logging
import concurrent.futures
import pandas
import yaml

from .             import DataCache, MarketIndex, CurrencyExchange, PortfolioAggregator
from .currency     import brasil_banco_central     as currency_bcb
from .currency     import cryptocompare            as currency_cryptocompare
from .marketindex  import brasil_banco_central     as mktidx_bcb
from .marketindex  import federal_reserve          as mktidx_fred
from .marketindex  import alphavantage             as mktidx_alphavantage
# from .marketindex  import yahoo_finance            as mktidx_yahoo
from .portfolios   import google_sheets            as google_sheets
from .portfolios   import uri                      as uri







class Investor(object):
    """
    Class that encapsulates everything needed to provide a useful report:

    - Portfolio with assets
    - Currency converters
    - Market benchmarks such as S&P500, Índice BoVeSPa etc
    - Other UI-related metadata such as assets grouping, relevant period,
      default currency
    - Other operational details such as cache DB URL

    Organizes use of cache database.
    Can be configured from a YAML file and then trigger data loading for all
    these domain, either from cache or the Internet.
    """
    domains={'portfolio','currency_converters','benchmarks'}



    def __init__(self,file,refreshMap=dict(zip(domains,len(domains)*[False])),load=True):
        """
        Reads the YAML file which contains domains 'portfolio',
        'currency_converters' and 'benchmarks', and then load their data from
        cache or their original sources.
        """
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

        if load:
            # Load all time series data from cache or web and compute derived
            # data
            self.loadDomains(refresh)



    def loadDomains(self,refreshMap=dict(zip(domains,len(domains)*[False]))):
        """
        Load from cache or original data source (the Internet?) data for
        Portfolio, Currency Converters and Benchmarks.

        refreshMap is a dict that controls wether to load from cache or update
        domain from internet (and update cache). It looks like:

        dict(
            portfolio           = False,
            benchmarks          = False,
            currency_converters = False,
        )
        """

        refresh=dict(zip(self.domains,len(self.domains)*[False]))
        refresh.update(refreshMap)

        # Decide wether we need to update extra benchmarks based on
        # CurrencyConverters
        augmentDomains=False
        for dom in ['benchmarks','currency_converters']:
            augmentDomains=augmentDomains or refresh[dom] or not getattr(self,dom)

        # Decide wether we need to update CurrencyExchange object
        updateCurrencyExchange=False
        for dom in ['currency_converters']:
            updateCurrencyExchange=(
                updateCurrencyExchange or
                refresh[dom] or not
                getattr(self,dom)
            )

        with concurrent.futures.ThreadPoolExecutor(thread_name_prefix='load_domains') as executor:
            tasks={}

            for domain in self.domains:
                if refresh[domain] or getattr(self,domain) is None:
                    # Load if a refresh was requested or domain has nothing yet
                    setattr(self,domain,[])
                    for part in self.config[domain]:
                        archived = 'archived' in part and part['archived']
                        if 'type' in part:
                            # If it contains a class that needs activation or loading

                            # Prepare parameters
                            theparams=part['params'].copy()
                            theparams.update(
                                dict(
                                    cache   = self.cache,

                                    # Reload data from original source only if
                                    # an explicit refresh was requested by the
                                    # UI button AND if asset not marked as
                                    # archived AND (decided later) asset has no
                                    # entries in cache.
                                    refresh = refresh[domain] and not archived
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

        if 'wealth_mask_factor' in self.config:
            self.portfolio.wealth_mask_factor=self.config['wealth_mask_factor']
        else:
            self.portfolio.wealth_mask_factor=1

        if updateCurrencyExchange:
            # Setup a multiple currency exchange machine
            self.exchange=CurrencyExchange(self.currency)

            # Put all CurrencyConverters in a single useful CurrencyExchange machine
            self.exchange.addCurrencies(
                [
                    curr['obj']
                    for curr in self.currency_converters
                ]
            )



    def augmentDomains(self):
        """
        Fabricate more benchmarks from currency converters, as specified by
        YAML config file.

        Entries such as the following from the YAML file will be handled:

        benchmarks:
            - kind: from_currency_converter
              from_to: BRLUSD

        For the config entry above, result is two benchmarks:
        - [BRL] USDBRL: expressed in BRL, or how USD performed in comparison to BRL
        - [USD] BRLUSD: expressed in USD, or how BRL performed in comparison to USD

        As the “[USD] S&P500” bechmark conveys what would happen if I converted
        my USD into assets of the S&P500 set, the fabricated “[BRL] USDBRL”
        benchmark shows what would happen if I converted my BRL in USD.
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
                    current_cc=cc['obj']
                    if curFrom == current_cc.currencyFrom and curTo == current_cc.currencyTo:
                        item['obj']=MarketIndex().fromCurrencyConverter(current_cc)
                        break
                    elif curTo == current_cc.currencyFrom and curFrom == current_cc.currencyTo:
                        item['obj']=MarketIndex().fromCurrencyConverter(current_cc.invert())
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
            self._cache=DataCache(self.config['cache_database'],recycle=2)
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
