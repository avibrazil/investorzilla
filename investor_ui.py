import streamlit as st
import numpy as np
import pandas as pd
import copy
import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

from investor_ui_config import context

import investor
import investor.currency.brasil_banco_central        as currency_bcb
import investor.currency.cryptocompare               as currency_cryptocompare
import investor.marketindex.brasil_banco_central     as mktidx_bcb
import investor.marketindex.federal_reserve          as mktidx_fred

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

        st.session_state['cache_file']=context['cache_file']
        st.session_state['crypto_compare_apiKey']=context['crypto_compare_apiKey']
        st.session_state['google_credentials_file']=context['google_credentials_file']
        st.session_state['finance_sheet_structure']=context['finance_sheet_structure']



        self.refresh=refresh

        with st.sidebar:
            self.interact_refresh()
            self.refresh=st.session_state['interact_refresh']

        if self.refresh or ('cache' not in st.session_state):
            # Data needs refresh or App running from scratch
            self.make_state(self.refresh)


        with st.sidebar:
            self.interact_funds()
            self.interact_currencies()
            self.interact_benchmarks()
            self.interact_periods()


        self.update_content()








    def update_content(self):
        st.session_state['exchange'].setTarget(
            st.session_state['interact_currencies']
        )

        fundset=st.session_state['interact_funds']
        if 'ALL' in fundset:
            fundset.remove('ALL')

        fund=st.session_state['portfolio'].getFund(
            subset           = fundset,
            currencyExchange = st.session_state['exchange']
        )

        st.title(fund.name)

        st.write('Data good for {}'.format(st.session_state['portfolio'].asof))

        st.header('Performance')
        st.write(f"Benchmark is {st.session_state['interact_benchmarks'].id}.")
        st.dataframe(
            fund.report(
                period=st.session_state.interact_periods,
                benchmark=st.session_state['interact_benchmarks'],
                kpi=['rate of return','benchmark rate of return','excess return','income'],
                output='flat'
            )
        )

        st.header('Wealth Evolution')
        st.dataframe(
            fund.report(
                period=st.session_state.interact_periods,
                benchmark=st.session_state['interact_benchmarks'],
                kpi=['balance','balance÷savings','savings','movements'],
                output='flat'
            )
        )


#         st.vega_lite_chart(data=fund.report('M',display=True), use_container_width=True)








    def interact_funds(self):
        st.session_state['interact_funds']=st.multiselect(
            'Select funds',
            ['ALL']+
            [x[0] for x in st.session_state.portfolio.funds()]
        )



    def interact_currencies(self):
        st.session_state['interact_currencies']=st.radio(
            label     = 'Convert all to currency',
            options   = st.session_state.exchange.currencies(),
            help      = 'Everything will be converted to this currency'
        )



    def interact_benchmarks(self):
        st.session_state['interact_benchmarks']=st.radio(
            label     = 'Select a benchmark to compare with',
            options   = st.session_state['benchmarks'],
            help      = 'Funds will be compared to the selected benchmark'
        )



    def interact_periods(self):
        st.session_state['interact_periods']=st.radio(
            label     = 'How to divide time',
            options   = investor.Fund.getPeriodPairs(),
            format_func = investor.Fund.getPeriodPairLabel,
            help      = 'Funds will be compared to the selected benchmark'
        )



    def interact_refresh(self):
        st.session_state['interact_refresh']=st.button(
            label     = 'Refresh Data',
            help      = 'Refresh all data from the Internet'
        )







    def make_state(self,refresh=False):
        st.session_state['cache']=investor.DataCache(st.session_state['cache_file'])


        st.session_state['portfolio']=investor.GoogleSheetsBalanceAndLedger(
            sheetStructure    = st.session_state.finance_sheet_structure,
            credentialsFile   = st.session_state.google_credentials_file,
            cache             = st.session_state.cache,
            refresh           = refresh
        )



        st.session_state['currency_converters']=dict(
            usdbrl=currency_bcb.BCBCurrencyConverter(
                currencyFrom='USD',
                cache=st.session_state.cache,
                refresh=refresh
            ),

            eurbrl=currency_bcb.BCBCurrencyConverter(
                currencyFrom='EUR',
                cache=st.session_state.cache,
                refresh=refresh
            ),

            btcusd=currency_cryptocompare.CryptoCompareCurrencyConverter(
                currencyFrom='BTC',
                apiKey=st.session_state['crypto_compare_apiKey'],
                cache=st.session_state.cache,
                refresh=refresh
            ),

            ethusd=currency_cryptocompare.CryptoCompareCurrencyConverter(
                currencyFrom='ETH',
                apiKey=st.session_state['crypto_compare_apiKey'],
                cache=st.session_state.cache,
                refresh=refresh
            ),
        )

        brlusd=copy.deepcopy(st.session_state.currency_converters['usdbrl'])
        brlusd.invert()

        curr=st.session_state['currency_converters']

        st.session_state['exchange']=investor.CurrencyExchange('BRL').addCurrency(curr['usdbrl'])

        for c in curr:
            if curr[c].currencyFrom not in st.session_state['exchange'].currencies():
                # If converter still not added to exchange...
                st.session_state['exchange']=st.session_state['exchange'].setTarget(curr[c].currencyTo)
                st.session_state['exchange']=st.session_state['exchange'].addCurrency(curr[c])



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
                refresh=refresh
            ),
            mktidx_bcb.BCBMarketIndex(
                name='CDI',
                cache=st.session_state.cache,
                refresh=refresh
            ),
            mktidx_bcb.BCBMarketIndex(
                name='SELIC',
                cache=st.session_state.cache,
                refresh=refresh
            ),
            mktidx_bcb.BCBMarketIndex(
                name='IGPM',
                cache=st.session_state.cache,
                refresh=refresh
            ),
            mktidx_bcb.BCBMarketIndex(
                name='INPC',
                cache=st.session_state.cache,
                refresh=refresh
            ),
            mktidx_fred.FREDMarketIndex(
                name='SP500',
                cache=st.session_state.cache,
                refresh=refresh
            ),
            mktidx_fred.FREDMarketIndex(
                name='DJCA',
                cache=st.session_state.cache,
                refresh=refresh
            ),
            mktidx_fred.FREDMarketIndex(
                name='NASDAQCOM',
                cache=st.session_state.cache,
                refresh=refresh
            ),
        ]



StreamlitInvestorApp(refresh=False)

# if 'app' not in st.session_state:
#     st.session_state['app']=StreamlitInvestorApp()
