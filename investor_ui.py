import copy
import logging
import threading
import datetime
import concurrent.futures
import numpy as np
import streamlit as st
import pandas as pd
# import st_aggrid


logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

from investor_ui_config import context

import investor
import investor.currency.brasil_banco_central        as currency_bcb
import investor.currency.cryptocompare               as currency_cryptocompare
import investor.marketindex.brasil_banco_central     as mktidx_bcb
import investor.marketindex.federal_reserve          as mktidx_fred
import investor.marketindex.yahoo_finance            as mktidx_yahoo

#  import (
#     DataCache,
#     Fund,
#     GoogleSheetsBalanceAndLedger,
#     MarketIndex,
#     CurrencyConverter,
#     CurrencyExchange
# )




class StreamlitInvestorApp:
    def __init__(self, refresh=False):

        # Private var is needed instead of streamlit.session_state due to parallelism
        self._state={}

        st.session_state['cache_file']              = context['cache_file']
        st.session_state['crypto_compare_apiKey']   = context['crypto_compare_apiKey']
        st.session_state['google_credentials_file'] = context['google_credentials_file']
        st.session_state['finance_sheet_structure'] = context['finance_sheet_structure']



#         st.session_state['refresh']=refresh

        with st.sidebar:
            self.interact_refresh()
#             st.session_state['refresh']=st.session_state['interact_refresh']

        if (
                    st.session_state.interact_refresh_portfolio or
                    st.session_state.interact_refresh_market or
                    st.session_state.interact_refresh_both or
                    ('cache' not in st.session_state)
            ):
            # Data needs refresh or App running from scratch
#             self.make_state(refresh=st.session_state['refresh'])
            self.make_state(refresh=refresh)


        with st.sidebar:
            self.interact_funds()
            self.interact_no_funds()
            self.interact_currencies()
            self.interact_benchmarks()
            self.interact_periods()


        self.update_content()




    def update_content_fund(self):
        fundset=None
        if 'interact_funds' in st.session_state:
            fundset=st.session_state.interact_funds

            if 'ALL' in fundset:
                fundset.remove('ALL')

        if fundset is None or len(fundset)==0:
            fundset=st.session_state.portfolio[0].funds()
            fundset=[f[0] for f in fundset]

        if 'interact_no_funds' in st.session_state:
            fundset=list(
                set(fundset) -
                set(st.session_state.interact_no_funds)
            )

        st.session_state['fund']=st.session_state.portfolio[0].getFund(
            subset           = fundset,
            currencyExchange = st.session_state.exchange
        )



    def update_content(self):
        st.session_state['exchange'].setTarget(
            st.session_state['interact_currencies']
        )

        self.update_content_fund()

        st.title(st.session_state['fund'].name)


        self.interact_start_end()

        st.markdown('Data good for **{}**'.format(st.session_state.portfolio[0].asof))

        st.markdown('Graph data between **{}** and **{}**'.format(
            st.session_state.interact_start_end[0],
            st.session_state.interact_start_end[1]
        ))


        st.header('Main Metrics')
        for p in st.session_state['fund'].periodPairs:
            if p['period']==st.session_state.interact_periods:
                break

        metricsPeriod=st.session_state['fund'].periodicReport(
            period=p['period'],
            start=st.session_state.interact_start_end[0],
            end=st.session_state.interact_start_end[1],
        )

        metricsMacroPeriod=st.session_state['fund'].periodicReport(
            period=p['macroPeriod'],
            start=st.session_state.interact_start_end[0],
            end=st.session_state.interact_start_end[1],
        )

        if st.session_state.interact_benchmarks.currency!=st.session_state.fund.currency:
            st.warning('Fund and Benchmark have different currencies. Benchamrk comparisons won’t make sense.')

        col1, col2, col3 = st.columns(3)

        label='{kpi}: current {p[periodLabel]} and {p[macroPeriodLabel]}'

        col1.metric(
            label=label.format(p=p,kpi=investor.KPI.RATE_RETURN),
            value='{:6.2f}%'.format(100*metricsPeriod.iloc[-1][investor.KPI.RATE_RETURN]),
            delta='{:6.2f}%'.format(100*metricsMacroPeriod.iloc[-1][investor.KPI.RATE_RETURN]),
        )

        col2.metric(
            label=label.format(p=p,kpi=investor.KPI.PERIOD_GAIN),
            value='${:0,.2f}'.format(metricsPeriod.iloc[-1][investor.KPI.PERIOD_GAIN]),
            delta='${:0,.2f}'.format(metricsMacroPeriod.iloc[-1][investor.KPI.PERIOD_GAIN]),
        )

        col3.metric(
            label='current {} & {}'.format(investor.KPI.BALANCE,investor.KPI.SAVINGS),
            value='${:0,.2f}'.format(metricsPeriod.iloc[-1][investor.KPI.BALANCE]),
            delta='${:0,.2f}'.format(metricsMacroPeriod.iloc[-1][investor.KPI.SAVINGS]),
        )



        col1, col2 = st.columns(2)

        with col1:
            st.header('Performance')
            st.line_chart(
                st.session_state['fund'].performancePlot(
                    benchmark=st.session_state.interact_benchmarks,
                    start=st.session_state.interact_start_end[0],
                    end=st.session_state.interact_start_end[1],
                    type='raw'
                )
            )

            st.pyplot(
                st.session_state['fund'].rateOfReturnPlot(
                    period=st.session_state.interact_periods,
                    start=st.session_state.interact_start_end[0],
                    end=st.session_state.interact_start_end[1],
                    type='pyplot'
                )
            )

        with col2:
            st.header('Gains')
            st.altair_chart(
                use_container_width=True,
                altair_chart=st.session_state['fund'].incomePlot(
                    period=st.session_state.interact_periods,
                    start=st.session_state.interact_start_end[0],
                    end=st.session_state.interact_start_end[1],
                    type='altair'
                )
            )

            wealthPlotData=st.session_state['fund'].wealthPlot(
                benchmark=st.session_state.interact_benchmarks,
                start=st.session_state.interact_start_end[0],
                end=st.session_state.interact_start_end[1],
                type='raw'
            ) #[['balance','savings','cumulative income']]

#             wealthPlotData['balance÷savings'] *= 0.5 * (
#                 wealthPlotData['balance'] -
#                 wealthPlotData['savings']
#             ).mean()

            st.line_chart(wealthPlotData)

#             st.bar_chart(
#                 st.session_state['fund'].incomePlot(
#                     period=st.session_state.interact_periods,
#                     start=st.session_state.interact_start_end[0],
#                     end=st.session_state.interact_start_end[1],
#                     type='raw'
#                 )['income']
#             )
#
#             rolling_income=st.session_state['fund'].incomePlot(
#                 period=st.session_state.interact_periods,
#                 start=st.session_state.interact_start_end[0],
#                 end=st.session_state.interact_start_end[1],
#                 type='raw'
#             )
#
#             rolling_columns=list(rolling_income.columns)
#             rolling_columns.remove('income')
#
#             st.line_chart(rolling_income[rolling_columns])


        st.header('Performance')
        st.markdown("Benchmark is **{benchmark}**.".format(benchmark=st.session_state['interact_benchmarks']))

        st.dataframe(
#         st_aggrid.AgGrid(
            st.session_state['fund'].report(
                period=st.session_state.interact_periods,
                benchmark=st.session_state.interact_benchmarks,
                start=st.session_state.interact_start_end[0],
                end=st.session_state.interact_start_end[1],
                kpi=[
                    investor.KPI.RATE_RETURN,
                    investor.KPI.BENCHMARK_RATE_RETURN,
                    investor.KPI.BENCHMARK_EXCESS_RETURN,
                    investor.KPI.PERIOD_GAIN
                ],
                output='flat'
            )
        )

        st.header('Wealth Evolution')

        st.dataframe(
#         st_aggrid.AgGrid(
            st.session_state['fund'].report(
                period=st.session_state.interact_periods,
                benchmark=st.session_state.interact_benchmarks,
                start=st.session_state.interact_start_end[0],
                end=st.session_state.interact_start_end[1],
                kpi=[
                    investor.KPI.BALANCE,
                    investor.KPI.BALANCE_OVER_SAVINGS,
                    investor.KPI.GAINS,
                    investor.KPI.SAVINGS,
                    investor.KPI.MOVEMENTS
                ],
                output='flat'
            )
        )



#         st.vega_lite_chart(data=fund.report('M',display=True), use_container_width=True)








    def interact_funds(self):
        st.session_state['interact_funds']=st.multiselect(
            'Select funds',
            ['ALL']+
            [x[0] for x in st.session_state.portfolio[0].funds()]
        )



    def interact_no_funds(self):
        st.session_state['interact_no_funds']=st.multiselect(
            'Except funds',
            [x[0] for x in st.session_state.portfolio[0].funds()]
        )



    def interact_currencies(self):
        st.session_state['interact_currencies']=st.radio(
            label     = 'Convert all to currency',
            options   = st.session_state.exchange.currencies(),
            help      = 'Everything will be converted to this currency'
        )



    def interact_benchmarks(self):
        st.session_state['interact_benchmarks']=st.radio(
            label       = 'Select a benchmark to compare with',
            options     = st.session_state.benchmarks,
            format_func = str,
            help        = 'Funds will be compared to the selected benchmark'
        )



    def interact_start_end(self):
#         current = st.session_state['fund'].start.to_pydatetime()
#         if 'interact_start_end' in st.session_state and current < st.session_state['interact_start_end'][0]:
#             current = st.session_state['interact_start_end'][0]

        st.session_state['interact_start_end']=st.slider(
            label       = 'Report Period Range',
            help        = 'Report starting on date',
            min_value   = st.session_state.fund.start.to_pydatetime(),
            max_value   = st.session_state.fund.end.to_pydatetime(),
            value       = (
                st.session_state.fund.start.to_pydatetime(),
                st.session_state.fund.end.to_pydatetime()
            )
        )



    def interact_periods(self):
        st.session_state['interact_periods']=st.radio(
            label       = 'How to divide time',
            options     = investor.Fund.getPeriodPairs(),
            format_func = investor.Fund.getPeriodPairLabel,
            index       = investor.Fund.getPeriodPairs().index('M'), # the starting default
            help        = 'Refine observation periods and set relation with summary of periods'
        )



    def interact_refresh(self):

        st.subheader('Refresh data')

        col1, col2, col3 = st.columns(3)

        st.session_state['interact_refresh_portfolio']=col1.button(
            label       = 'Portfolio',
            help        = 'Invalidate cache and update your Portfolio data from the Internet'
        )

        st.session_state['interact_refresh_market']=col2.button(
            label       = 'Market',
            help        = 'Invalidate cache and update Market Indexes and Currency Converters data from the Internet'
        )

        st.session_state['interact_refresh_both']=col3.button(
            label       = 'Both',
            help        = 'Invalidate cache and update all data from the Internet'
        )



    def work_on_task(self, stItem, task, params, thread_context):
        st.report_thread.add_report_ctx(threading.currentThread(), thread_context)

        params.update(
            dict(
                cache             = st.session_state.cache,
                refresh           = (
                    st.session_state.refresh_portfolio
                    if stItem=='portfolio'
                    else st.session_state.refresh_market
                )
            )
        )

        if stItem in st.session_state:
            st.session_state[stItem].append(task(**params))
        else:
            st.session_state[stItem]=[task(**params)]



    work_description = [
        dict(
            stItem='portfolio',
            task=investor.GoogleSheetsBalanceAndLedger,
            params=dict(
                sheetStructure    = context['finance_sheet_structure'],
                credentialsFile   = context['google_credentials_file']
            )
        ),

        dict(
            stItem='currency_converters',
            task=currency_bcb.BCBCurrencyConverter,
            params=dict(
                currencyFrom='USD',
            )
        ),

        dict(
            stItem='currency_converters',
            task=currency_bcb.BCBCurrencyConverter,
            params=dict(
                currencyFrom='EUR',
            )
        ),

        dict(
            stItem='currency_converters',
            task=currency_cryptocompare.CryptoCompareCurrencyConverter,
            params=dict(
                currencyFrom='BTC',
                apiKey=context['crypto_compare_apiKey']
            )
        ),

        dict(
            stItem='currency_converters',
            task=currency_cryptocompare.CryptoCompareCurrencyConverter,
            params=dict(
                currencyFrom='ETH',
                apiKey=context['crypto_compare_apiKey']
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='IPCA',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='CDI',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='SELIC',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='IGPM',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='INPC',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^BVSP',
                friendlyName='Índice BoVESPa (^BVSP)',
                currency='BRL',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^GSPC',
                friendlyName='S&P 500 (^GSPC)',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^DJI',
                friendlyName='Dow Jones (^DJI)',
            )
        ),

        dict(
            stItem='benchmarks',
            task=mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^IXIC',
                friendlyName='NASDAQ (^IXIC)',
            )
        )
    ]



    def make_state(self,refresh=False):
        if 'cache' not in st.session_state:
            st.session_state['cache']=investor.DataCache(st.session_state.cache_file)
#         self.cache=investor.DataCache(st.session_state['cache_file'])

#         self.refresh=refresh
        st.session_state['refresh_portfolio'] = st.session_state.interact_refresh_both or st.session_state.interact_refresh_portfolio
        st.session_state['refresh_market']    = st.session_state.interact_refresh_both or st.session_state.interact_refresh_market


#         with concurrent.futures.ThreadPoolExecutor() as executor:
#             thread_context = st.report_thread.get_report_ctx()
#
#             # Trigger all work in parallel
#             futureWorks = {
#                 executor.submit(
#                     self.work_on_task,
#                     work['stItem'],
#                     work['task'],
#                     work['params'],
#                     thread_context
#                 ): work for work in self.work_description
#             }
#
# #             print(futureWorks)
#
#             # Wait for finish and collect results
#             for future in concurrent.futures.as_completed(futureWorks):
#                 future.result()  # Raise any exception here
#                 work = futureWorks[future]
#                 print('Done {}'.format(work['task']))
#
#         # st.session_state.update(self._state)








#         self.get_portfolio()
#         self.get_currencies()
#         self.get_market()
#         ---
#         integrate()
#         fund()












        st.session_state['portfolio']=[investor.GoogleSheetsBalanceAndLedger(
            sheetStructure    = st.session_state.finance_sheet_structure,
            credentialsFile   = st.session_state.google_credentials_file,
            cache             = st.session_state.cache,
            refresh           = st.session_state.refresh_portfolio
        )]


        if 'currency_converters' not in st.session_state or st.session_state.refresh_market:
            st.session_state['currency_converters']=dict(
                usdbrl=currency_bcb.BCBCurrencyConverter(
                    currencyFrom       = 'USD',
                    cache              = st.session_state.cache,
                    refresh            = st.session_state.refresh_market
                ),

                eurbrl=currency_bcb.BCBCurrencyConverter(
                    currencyFrom       = 'EUR',
                    cache              = st.session_state.cache,
                    refresh            = st.session_state.refresh_market
                ),

                btcusd=currency_cryptocompare.CryptoCompareCurrencyConverter(
                    currencyFrom       = 'BTC',
                    apiKey             = st.session_state.crypto_compare_apiKey,
                    cache              = st.session_state.cache,
                    refresh            = st.session_state.refresh_market
                ),

                ethusd=currency_cryptocompare.CryptoCompareCurrencyConverter(
                    currencyFrom       = 'ETH',
                    apiKey             = st.session_state.crypto_compare_apiKey,
                    cache              = st.session_state.cache,
                    refresh            = st.session_state.refresh_market
                ),
            )

            brlusd=copy.deepcopy(st.session_state.currency_converters['usdbrl'])
            brlusd.invert()

            curr=st.session_state.currency_converters

            st.session_state.exchange=investor.CurrencyExchange('BRL').addCurrency(curr['usdbrl'])

            for c in curr:
                if curr[c].currencyFrom not in st.session_state['exchange'].currencies():
                    # If converter still not added to exchange...
                    st.session_state['exchange']=st.session_state['exchange'].setTarget(curr[c].currencyTo)
                    st.session_state['exchange']=st.session_state['exchange'].addCurrency(curr[c])

        if 'benchmarks' not in st.session_state or st.session_state.refresh_market:
            st.session_state['benchmarks']=[
                (
                    investor.MarketIndex()
                    .fromCurrencyConverter(st.session_state.currency_converters['usdbrl'])
                ),
                (
                    investor.MarketIndex()
                    .fromCurrencyConverter(st.session_state.currency_converters['eurbrl'])
                ),
                (
                    investor.MarketIndex()
                    .fromCurrencyConverter(brlusd)
                ),
                (
                    investor.MarketIndex()
                    .fromCurrencyConverter(st.session_state.currency_converters['btcusd'])
                ),
                (
                    investor.MarketIndex()
                    .fromCurrencyConverter(st.session_state.currency_converters['ethusd'])
                ),
                mktidx_bcb.BCBMarketIndex(
                    name='IPCA',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_bcb.BCBMarketIndex(
                    name='CDI',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_bcb.BCBMarketIndex(
                    name='SELIC',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_bcb.BCBMarketIndex(
                    name='IGPM',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_bcb.BCBMarketIndex(
                    name='INPC',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_yahoo.YahooMarketIndex(
                    name='^BVSP',
                    friendlyName='Índice BoVESPa (^BVSP)',
                    currency='BRL',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_yahoo.YahooMarketIndex(
                    name='^GSPC',
                    friendlyName='S&P 500 (^GSPC)',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_yahoo.YahooMarketIndex(
                    name='^DJI',
                    friendlyName='Dow Jones (^DJI)',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
                mktidx_yahoo.YahooMarketIndex(
                    name='^IXIC',
                    friendlyName='NASDAQ (^IXIC)',
                    cache=st.session_state.cache,
                    refresh=st.session_state.refresh_market
                ),
            ]


        self.update_content_fund()



StreamlitInvestorApp(refresh=False)


