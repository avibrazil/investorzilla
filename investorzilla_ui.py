import copy
import logging
import threading
import datetime
import concurrent.futures
import yaml
import numpy as np
import streamlit as st
import pandas as pd
# import st_aggrid

# Dependencies available via OS packages:
# pip3 install pandas pyyaml sqlalchemy pandas_datareader

# Other dependencies:
# pip3 install streamlit google-api-python-client

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

import investorzilla


class StreamlitInvestorzillaApp:
    defaultRefreshMap=dict(
        zip(
            investorzilla.Investor.domains,
            len(investorzilla.Investor.domains)*[False]
        )
    )

    def prepare_logging(self,level=logging.INFO):
        # Switch between INFO/DEBUG while running in production/developping:

        # Configure logging for Investor

        FORMATTER = logging.Formatter("%(asctime)s|%(levelname)s|%(name)s|%(message)s")
        HANDLER = logging.StreamHandler()
        HANDLER.setFormatter(FORMATTER)

        loggers=[
            logging.getLogger('__main__'),
            logging.getLogger('investorzilla'),
            logging.getLogger('sqlite')
        ]

        for logger in loggers:
            logger.addHandler(HANDLER)
            logger.setLevel(level)

        return loggers[0]



    def __init__(self, refresh=False):
        self.prepare_logging(level=logging.INFO)

        st.set_page_config(layout="wide")
        with st.sidebar:
            # Get the kind of refresh user wants, if any
            self.refreshMap=self.interact_refresh()

        # investor    refresh
        #   None         X.     => load
        #     X          True.  => load
        #     X.         False. => reuse
        #     None.      False. => load


        if ('investor' not in st.session_state) or (True in self.refreshMap.values()):
            st.session_state['investor']=investorzilla.Investor('investorzilla.yaml',self.refreshMap)
        # else:
        #     # Simply reuse what you have
        #     st.session_state['investor']

        with st.sidebar:
            # Put controls in the sidebar
            self.interact_funds()
            self.interact_exclude_funds()
            self.interact_currencies()
            self.interact_benchmarks()
            self.interact_periods()

        # Render main content with plots and tables
        self.update_content()



    def update_content_fund(self):
        """
        Generate a virtual fund (shares and share value) based on portfolio items selected in sidebar.
        """

        fundset=None
        if 'interact_funds' in st.session_state:
            fundset=st.session_state.interact_funds

            if 'ALL' in fundset:
                fundset.remove('ALL')

        if fundset is None or len(fundset)==0:
            fundset=st.session_state.investor.portfolio.funds()
            fundset=[f[0] for f in fundset]

        if 'interact_no_funds' in st.session_state:
            fundset=list(
                set(fundset) -
                set(st.session_state.interact_no_funds)
            )

        st.session_state['fund']=st.session_state.investor.portfolio.getFund(
            subset           = fundset,
            currencyExchange = st.session_state.investor.exchange
        )

        st.session_state['fund'].setName(top=4)



    def update_content(self):
        """
        Render the report
        """

        st.session_state['investor'].currency=st.session_state['interact_currencies']

        self.update_content_fund()

        # Render title
        st.title(st.session_state['fund'].name)

        # Render period slider
        self.interact_start_end()

        # Render main metrics
        st.header('Main Metrics')
        p=st.session_state['fund'].periodPairs[st.session_state.interact_periods]
        # for p in st.session_state['fund'].periodPairs:
        #     if p['period']==st.session_state.interact_periods:
        #         break

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

        if st.session_state.interact_benchmarks['obj'].currency!=st.session_state.fund.currency:
            st.warning('Fund and Benchmark have different currencies. Benchamrk comparisons won’t make sense.')

        col1, col2, col3 = st.columns(3)

        label='{kpi}: current {p[periodLabel]} and {p[macroPeriodLabel]}'

        col1.metric(
            label=label.format(p=p,kpi=investorzilla.KPI.RATE_RETURN),
            value='{:6.2f}%'.format(100*metricsPeriod.iloc[-1][investorzilla.KPI.RATE_RETURN]),
            delta='{:6.2f}%'.format(100*metricsMacroPeriod.iloc[-1][investorzilla.KPI.RATE_RETURN]),
        )

        col2.metric(
            label=label.format(p=p,kpi=investorzilla.KPI.PERIOD_GAIN),
            value='${:0,.2f}'.format(metricsPeriod.iloc[-1][investorzilla.KPI.PERIOD_GAIN]),
            delta='{sign}${value:0,.2f}'.format(
                value=abs(metricsMacroPeriod.iloc[-1][investorzilla.KPI.PERIOD_GAIN]),
                sign=('-' if metricsMacroPeriod.iloc[-1][investorzilla.KPI.PERIOD_GAIN]<0 else '')
            )
        )

        col3.metric(
            label='current {} & {}'.format(investorzilla.KPI.BALANCE,investorzilla.KPI.SAVINGS),
            value='${:0,.2f}'.format(metricsPeriod.iloc[-1][investorzilla.KPI.BALANCE]),
            delta='{sign}${value:0,.2f}'.format(
                value=abs(metricsMacroPeriod.iloc[-1][investorzilla.KPI.SAVINGS]),
                sign=('-' if metricsMacroPeriod.iloc[-1][investorzilla.KPI.SAVINGS]<0 else '')
            )
        )



        col1, col2 = st.columns(2)

        with col1:
            st.header('Performance')
            st.line_chart(
                st.session_state['fund'].performancePlot(
                    benchmark=st.session_state.interact_benchmarks['obj'],
                    start=st.session_state.interact_start_end[0],
                    end=st.session_state.interact_start_end[1],
                    type='raw'
                )
            )

            st.pyplot(
                st.session_state['fund'].rateOfReturnPlot(
                    period=p['period'],
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
                    periodPair=st.session_state.interact_periods,
                    start=st.session_state.interact_start_end[0],
                    end=st.session_state.interact_start_end[1],
                    type='altair'
                )
            )

            wealthPlotData=st.session_state['fund'].wealthPlot(
                benchmark=st.session_state.interact_benchmarks['obj'],
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


        table_styles=[
            dict(selector="td", props="font-size: 0.8em; text-align: right"),
            dict(selector="th", props="font-size: 0.8em; "),
            dict(selector='tr:hover', props='background-color: yellow')
        ]

        st.header('Performance')
        st.markdown("Benchmark is **{benchmark}**.".format(benchmark=st.session_state.interact_benchmarks['obj']))

        performance_benchmarks=[
            investorzilla.KPI.RATE_RETURN,
            investorzilla.KPI.BENCHMARK_RATE_RETURN,
            investorzilla.KPI.BENCHMARK_EXCESS_RETURN,
            investorzilla.KPI.PERIOD_GAIN
        ]

        st.session_state['kpi_performance']=st.multiselect(
            '',
            options=performance_benchmarks,
            default=performance_benchmarks
        )

        st.markdown(
        # st.dataframe(
            st.session_state['fund'].report(
                period     = st.session_state.interact_periods,
                benchmark  = st.session_state.interact_benchmarks['obj'],
                start      = st.session_state.interact_start_end[0],
                end        = st.session_state.interact_start_end[1],
                kpi        = st.session_state['kpi_performance'],
                # output     = 'flat'
            )
            .set_table_styles(table_styles)

            .to_html(),
            unsafe_allow_html=True
        )

        st.header('Wealth Evolution')

        wealth_benchmarks=[
            investorzilla.KPI.BALANCE,
            investorzilla.KPI.BALANCE_OVER_SAVINGS,
            investorzilla.KPI.GAINS,
            investorzilla.KPI.SAVINGS,
            investorzilla.KPI.MOVEMENTS
        ]

        st.session_state['kpi_wealth']=st.multiselect(
            '',
            options=wealth_benchmarks,
            default=wealth_benchmarks
        )

        st.markdown(
            st.session_state['fund'].report(
                period=st.session_state.interact_periods,
                benchmark=st.session_state.interact_benchmarks['obj'],
                start=st.session_state.interact_start_end[0],
                end=st.session_state.interact_start_end[1],
                kpi=st.session_state['kpi_wealth'],
                # output='flat'
            )
            .set_table_styles(table_styles)

            .to_html(),
            unsafe_allow_html=True
        )

        # Render footer
        st.markdown('Most recent porfolio data is **{}**'.format(st.session_state.investor.portfolio.asof))

        st.markdown('Graph data between **{}** and **{}**'.format(
            st.session_state.interact_start_end[0],
            st.session_state.interact_start_end[1]
        ))

        st.markdown('Report by [investorzilla](https://github.com/avibrazil/investorzilla).')



    def work_on_task(self, part, thetype, params):
        """
        Instantiate an object of the class specified in the YAML file 'type'
        entry with instrumented parameters from the 'param' entry.
        """

        # Set thread context to make Streamlit happy
        # https://stackoverflow.com/a/69363860/367824
#         self.thread_context.add_report_ctx(threading.currentThread(), self.thread_context)
#         st.ReportThread.add_report_ctx(None,self.thread_context)
        st.scriptrunner.add_script_run_ctx(threading.currentThread(),self.thread_context)

        params.update(
            dict(
                cache             = st.session_state.cache,
                refresh           = (
                    st.session_state.refresh_portfolio
                    if part == 'portfolio'
                    else st.session_state.refresh_market
                )
            )
        )

        return thetype(**params)



    def get_investor_data(self, part, executor):
        """
        Iterate over each portfolio|currency_converters|benchmarks/type of the
        pre-loaded YAML file. Call work_on_task() for each.

        Returns a dict of Future tasks being executed in parallel.
        Requires post-processing by concurrent.futures.as_completed()
        """

        tasks={}

        for desc in self.context[part]:
            if 'type' in desc:
                task=executor.submit(
                    self.work_on_task,
                    part,
                    desc['type'],
                    desc['params']
                )
                tasks[task]=(part,desc)

        return tasks



    def augment_investor_data(self):
        """
        Make benchmarks from currency converters.

        Entries such as the following from the investor_ui_config.yaml file will be
        converted:

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

                # Check if this CurrencyConvert-derived benchmark is already in
                for bi in range(len(st.session_state.benchmarks)):
                    if str(st.session_state.benchmarks[bi]) == benchmark_signature:
                        if st.session_state.refresh_market:
                            del st.session_state.benchmarks[bi]
                            break

                cc_as_mi=None

                # Scan all currency converters we have to find a match
                for cc in st.session_state.currency_converters:
                    if curFrom == cc.currencyFrom and curTo == cc.currencyTo:
                        cc_as_mi=investorzilla.MarketIndex().fromCurrencyConverter(cc)
                        break
                    elif curTo == cc.currencyFrom and curFrom == cc.currencyTo:
                        cc_as_mi=investorzilla.MarketIndex().fromCurrencyConverter(cc.invert())
                        break

                if cc_as_mi:
                    st.session_state.benchmarks.append(cc_as_mi)
                else:
                    raise Exception(f'Can’t find "{item.kind}" CurrencyConverter to make a MarketIndex from.')

        st.session_state.benchmarks.sort()



    def load_portfolio(self):
        portfolio="investor_ui_config.yaml"

        with open(portfolio, 'r') as file:
            self.context = yaml.load(file, Loader=yaml.FullLoader)



    def make_state(self, refresh=False):
        self.load_portfolio()

        if 'cache' not in st.session_state:
            st.session_state['cache']=investorzilla.DataCache(self.context['cache_database'])

        # Collect some flags about what to load from cache, reafresh from Internet etc
        st.session_state['refresh_portfolio'] = st.session_state.interact_refresh_both or st.session_state.interact_refresh_portfolio
        st.session_state['refresh_market']    = st.session_state.interact_refresh_both or st.session_state.interact_refresh_market
        self.thread_context                   = st.scriptrunner.script_run_context.get_script_run_ctx()

        with concurrent.futures.ThreadPoolExecutor(thread_name_prefix='load_portfolio') as executor:
            tasks = dict()

            refresh_map = [
                ('portfolio',              st.session_state.refresh_portfolio),
                ('currency_converters',    st.session_state.refresh_market),
                ('benchmarks',             st.session_state.refresh_market),
            ]

            # Trigger all portfolio/benchmark/currency data load tasks in parallel
            for ref in refresh_map:
                if ref[1] or ref[0] not in st.session_state:
                    if ref[0] in st.session_state:
                        del st.session_state[ref[0]]
                    tasks.update(self.get_investor_data(ref[0], executor))

            # Wait for all parallel data loading to complete
            for task in concurrent.futures.as_completed(tasks):
                if tasks[task][0] in st.session_state:
                    st.session_state[tasks[task][0]].append(task.result())
                else:
                    st.session_state[tasks[task][0]]=[task.result()]

        if st.session_state.refresh_market or 'exchange' not in st.session_state:
            st.session_state['exchange']=investorzilla.CurrencyExchange('USD')

            # Put all CurrencyConverters in a single useful CurrencyExchange machine
            for curr in st.session_state['currency_converters']:
                st.session_state.exchange.addCurrency(curr)

        #
        # At this point we have all that is required for the app:
        # - st.session_state.portfolio containing balance and ledger
        # - st.session_state.exchange with flexible currency converters
        # - st.session_state.benchmarks with market indexes etc
        #
        # Now construct some derivate objects such as:
        # - Market indexes from currency converters
        # - An actual composite fund from a UI-selected part of the portfolio
        #

        # Scan and do whatever else is required
        self.augment_investor_data()

#         self.update_content_fund()



    def interact_funds(self):
        st.session_state['interact_funds']=st.multiselect(
            'Select funds',
            ['ALL']+
            [x[0] for x in st.session_state.investor.portfolio.funds()]
        )



    def interact_exclude_funds(self):
        st.session_state['interact_no_funds']=st.multiselect(
            'Except funds',
            [x[0] for x in st.session_state.investor.portfolio.funds()]
        )



    def interact_currencies(self):
        st.session_state['interact_currencies']=st.radio(
            label     = 'Convert all to currency',
            options   = st.session_state.investor.exchange.currencies(),
            help      = 'Everything will be converted to this currency'
        )



    def interact_benchmarks(self):
        st.session_state['interact_benchmarks']=st.radio(
            label       = 'Select a benchmark to compare with',
            options     = st.session_state.investor.benchmarks,
            format_func = lambda bench: str(bench['obj']),
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
            options     = investorzilla.Fund.getPeriodPairs(),
            format_func = investorzilla.Fund.getPeriodPairLabel,
            index       = investorzilla.Fund.getPeriodPairs().index('month & year'), # the starting default
            help        = 'Refine observation periods and set relation with summary of periods'
        )



    def interact_refresh(self):
        self.refreshMap=self.defaultRefreshMap.copy()

        st.subheader('Refresh data')

        col1, col2, col3 = st.columns(3)

        if col1.button(
            label       = 'Portfolio',
            help        = 'Invalidate cache and update your Portfolio data from the Internet'
        ):
            self.refreshMap['portfolio']=True

        if col2.button(
            label       = 'Market',
            help        = 'Invalidate cache and update Market Indexes and Currency Converters data from the Internet'
        ):
            self.refreshMap['currency_converters']=True
            self.refreshMap['benchmarks']=True

        if col3.button(
            label       = 'Both',
            help        = 'Invalidate cache and update all data from the Internet'
        ):
            self.refreshMap['currency_converters']=True
            self.refreshMap['benchmarks']=True
            self.refreshMap['portfolio']=True

        return self.refreshMap



def main():
    import os
    import subprocess
    import sys
    import time
    import webbrowser



    # Getting path to python executable (full path of deployed python on Windows)
    executable = sys.executable

    # Running streamlit server in a subprocess and writing to log file
    proc = subprocess.Popen(
        [
            executable,
            "-m",
            "streamlit",
            "run",
            __file__,
            # The following option appears to be necessary to correctly start the streamlit server,
            # but it should start without it. More investigations should be carried out.
            "--server.headless=true",
            "--global.developmentMode=false",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    proc.stdin.close()

    # Force the opening (does not open automatically) of the browser tab after a brief delay to let
    # the streamlit server start.
    time.sleep(3)
    webbrowser.open("http://localhost:8501")

    while True:
        s = proc.stdout.read()
        if not s:
            break
        print(s, end="")

    proc.wait()


if __name__ == "__main__":
    main()
else:
    StreamlitInvestorzillaApp(refresh=False)
