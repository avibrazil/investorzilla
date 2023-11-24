import logging

# Dependencies available via OS packages:
# pip3 install pandas pyyaml sqlalchemy pandas_datareader

# Other dependencies:
# pip3 install streamlit google-api-python-client

import streamlit
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

        loggers=[
            logging.getLogger('__main__'),
            logging.getLogger('investorzilla'),
            # logging.getLogger('sqlite')
        ]

        if loggers[0].handlers:  # logger is already setup, don't setup again
            return loggers[0]

        FORMATTER = logging.Formatter("%(asctime)s|%(levelname)s|%(name)s|%(message)s")
        HANDLER = logging.StreamHandler()
        HANDLER.setFormatter(FORMATTER)

        for logger in loggers:
            logger.addHandler(HANDLER)
            logger.setLevel(level)

        streamlit.session_state.logger=loggers[0]
        return streamlit.session_state.logger



    def __init__(self, refresh=False):
        self.prepare_logging(level=logging.INFO)

        streamlit.set_page_config(
            layout="wide",
            page_title='Investorzilla',
            menu_items={
                "Report a Bug": 'https://github.com/avibrazil/investorzilla/issues',
                "About": '\n'.join([
                    '# [Investorzilla](https://github.com/avibrazil/investorzilla)',
                    'Brought to you by **[Avi Alkalay](https://Avi.Alkalay.NET/)**'
                ])
            }
        )
        with streamlit.sidebar:
            # Get the kind of refresh user wants, if any
            self.refreshMap=self.interact_refresh()

        # investor    refresh
        #   None         X.     => load
        #     X          True.  => load
        #     X.         False. => reuse
        #     None.      False. => load


        if ('investor' not in streamlit.session_state) or (True in self.refreshMap.values()):
            streamlit.session_state.investor=investorzilla.Investor(
                'investorzilla.yaml',
                self.refreshMap
            )

        with streamlit.sidebar:
            # Put controls in the sidebar
            self.interact_funds()
            self.interact_exclude_funds()
            self.interact_currencies()
            self.interact_benchmarks()
            self.interact_periods()

        # Render main content with plots and tables
        self.update_content()



    def prepare_fund(self):
        """
        Generate a virtual fund (shares and share value) based on portfolio
        items selected in sidebar.
        """

        fundset=None
        if 'interact_funds' in streamlit.session_state:
            fundset=streamlit.session_state.interact_funds

            if 'ALL' in fundset:
                fundset.remove('ALL')

        if fundset is None or len(fundset)==0:
            fundset=streamlit.session_state.investor.portfolio.funds()
            fundset=[f[0] for f in fundset]

        if 'interact_no_funds' in streamlit.session_state:
            fundset=list(
                set(fundset) -
                set(streamlit.session_state.interact_no_funds)
            )

        streamlit.session_state.fund=streamlit.session_state.investor.portfolio.getFund(
            subset           = fundset,
            currencyExchange = streamlit.session_state.investor.exchange
        )

        streamlit.session_state.fund.setName(top=4)



    def update_content(self):
        """
        Render the report
        """

        streamlit.session_state.investor.currency=streamlit.session_state.interact_currencies

        self.prepare_fund()

        (tab_performance, tab_portfolio) = streamlit.tabs(["📈 Performance", "💼 Portfolio Components and Information"])

        with tab_performance:
            self.render_performance_page()

        with tab_portfolio:
            self.render_portfolio_page()

        streamlit.caption('Report by [investorzilla](https://github.com/avibrazil/investorzilla).')



    def render_portfolio_page(self):
        with streamlit.expander('Personal Portfolio'):
            streamlit.markdown(streamlit.session_state.investor.portfolio.to_markdown(title_prefix='##'))

        with streamlit.expander('Market Indexes'):
            for b in streamlit.session_state.investor.benchmarks:
                streamlit.markdown(b['obj'].to_markdown(title_prefix='###'))

        with streamlit.expander('Currency Converters'):
            for c in streamlit.session_state.investor.currency_converters:
                streamlit.markdown(c['obj'].to_markdown(title_prefix='###'))



    def render_performance_page(self):
        # Render title
        streamlit.title(streamlit.session_state.fund.name)

        # Render period slider
        self.interact_start_end()

        # Render main metrics
        streamlit.header('Main Metrics', divider='rainbow')
        p=streamlit.session_state.fund.periodPairs[streamlit.session_state.interact_periods]
        # for p in streamlit.session_state['fund'].periodPairs:
        #     if p['period']==streamlit.session_state.interact_periods:
        #         break

        metricsPeriod=streamlit.session_state.fund.periodicReport(
            period=p['period'],
            start=streamlit.session_state.interact_start_end[0],
            end=streamlit.session_state.interact_start_end[1],
        )

        metricsMacroPeriod=streamlit.session_state.fund.periodicReport(
            period=p['macroPeriod'],
            start=streamlit.session_state.interact_start_end[0],
            end=streamlit.session_state.interact_start_end[1],
        )

        if streamlit.session_state.interact_benchmarks['obj'].currency!=streamlit.session_state.fund.currency:
            streamlit.warning('Fund and Benchmark have different currencies. Benchamrk comparisons won’t make sense.')

        col1, col2, col3 = streamlit.columns(3)

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



        col1, col2 = streamlit.columns(2)

        with col1:
            streamlit.header('Performance', divider='red')
            streamlit.line_chart(
                streamlit.session_state.fund.performancePlot(
                    benchmark=streamlit.session_state.interact_benchmarks['obj'],
                    start=streamlit.session_state.interact_start_end[0],
                    end=streamlit.session_state.interact_start_end[1],
                    type='raw'
                )
            )

            streamlit.pyplot(
                streamlit.session_state.fund.rateOfReturnPlot(
                    period=p['period'],
                    start=streamlit.session_state.interact_start_end[0],
                    end=streamlit.session_state.interact_start_end[1],
                    type='pyplot'
                )
            )

        with col2:
            streamlit.header('Gains', divider='red')
            streamlit.altair_chart(
                use_container_width=True,
                altair_chart=streamlit.session_state.fund.incomePlot(
                    periodPair=streamlit.session_state.interact_periods,
                    start=streamlit.session_state.interact_start_end[0],
                    end=streamlit.session_state.interact_start_end[1],
                    type='altair'
                )
            )

            wealthPlotData=streamlit.session_state.fund.wealthPlot(
                benchmark=streamlit.session_state.interact_benchmarks['obj'],
                start=streamlit.session_state.interact_start_end[0],
                end=streamlit.session_state.interact_start_end[1],
                type='raw'
            ) #[['balance','savings','cumulative income']]

#             wealthPlotData['balance÷savings'] *= 0.5 * (
#                 wealthPlotData['balance'] -
#                 wealthPlotData['savings']
#             ).mean()

            streamlit.line_chart(wealthPlotData)

#             streamlit.bar_chart(
#                 streamlit.session_state['fund'].incomePlot(
#                     period=streamlit.session_state.interact_periods,
#                     start=streamlit.session_state.interact_start_end[0],
#                     end=streamlit.session_state.interact_start_end[1],
#                     type='raw'
#                 )['income']
#             )
#
#             rolling_income=streamlit.session_state['fund'].incomePlot(
#                 period=streamlit.session_state.interact_periods,
#                 start=streamlit.session_state.interact_start_end[0],
#                 end=streamlit.session_state.interact_start_end[1],
#                 type='raw'
#             )
#
#             rolling_columns=list(rolling_income.columns)
#             rolling_columns.remove('income')
#
#             streamlit.line_chart(rolling_income[rolling_columns])


        table_styles=[
            dict(selector="td", props="font-size: 0.8em; text-align: right"),
            dict(selector="th", props="font-size: 0.8em; "),
            dict(selector='tr:hover', props='background-color: yellow')
        ]

        streamlit.header('Performance')
        streamlit.markdown("Benchmark is **{benchmark}**.".format(benchmark=streamlit.session_state.interact_benchmarks['obj']))

        performance_benchmarks=[
            investorzilla.KPI.RATE_RETURN,
            investorzilla.KPI.BENCHMARK_RATE_RETURN,
            investorzilla.KPI.BENCHMARK_EXCESS_RETURN,
            investorzilla.KPI.PERIOD_GAIN
        ]

        streamlit.multiselect(
            '',
            options=performance_benchmarks,
            default=performance_benchmarks,
            key='kpi_performance'
        )

        streamlit.markdown(
        # streamlit.dataframe(
            streamlit.session_state['fund'].report(
                period     = streamlit.session_state.interact_periods,
                benchmark  = streamlit.session_state.interact_benchmarks['obj'],
                start      = streamlit.session_state.interact_start_end[0],
                end        = streamlit.session_state.interact_start_end[1],
                kpi        = streamlit.session_state['kpi_performance'],
                # output     = 'flat'
            )
            .set_table_styles(table_styles)

            .to_html(),
            unsafe_allow_html=True
        )

        streamlit.header('Wealth Evolution')

        wealth_benchmarks=[
            investorzilla.KPI.BALANCE,
            investorzilla.KPI.BALANCE_OVER_SAVINGS,
            investorzilla.KPI.GAINS,
            investorzilla.KPI.SAVINGS,
            investorzilla.KPI.MOVEMENTS
        ]

        streamlit.multiselect(
            '',
            options=wealth_benchmarks,
            default=wealth_benchmarks,
            key='kpi_wealth'
        )

        streamlit.markdown(
            streamlit.session_state['fund'].report(
                period=streamlit.session_state.interact_periods,
                benchmark=streamlit.session_state.interact_benchmarks['obj'],
                start=streamlit.session_state.interact_start_end[0],
                end=streamlit.session_state.interact_start_end[1],
                kpi=streamlit.session_state['kpi_wealth'],
                # output='flat'
            )
            .set_table_styles(table_styles)

            .to_html(),
            unsafe_allow_html=True
        )

        # Render footer
        streamlit.markdown(
            'Most recent porfolio data is **{}**'.format(
                streamlit.session_state.investor.portfolio.asof
            )
        )

        streamlit.markdown(
            'Graph data between **{}** and **{}**'.format(
                streamlit.session_state.interact_start_end[0],
                streamlit.session_state.interact_start_end[1]
            )
        )



    # All the interact_* methods manager widgets in the Streamlit UI

    def interact_funds(self):
        streamlit.multiselect(
            label     = 'Select assets to make a fund',
            options   = (
                ['ALL']+
                [
                    x[0]
                    for x in streamlit.session_state.investor.portfolio.funds()
                ]
            ),
            help      = 'Shares and share value will be computed for the union of selected assets',
            key       = 'interact_funds'
        )



    def interact_exclude_funds(self):
        streamlit.multiselect(
            label     = 'Except funds',
            options   = [
                x[0]
                for x in streamlit.session_state.investor.portfolio.funds()
            ],
            help      = 'Exclude assets selected here',
            key       = 'interact_no_funds'
        )



    def interact_currencies(self):
        streamlit.session_state['interact_currencies']=streamlit.radio(
            label     = 'Convert all to currency',
            options   = streamlit.session_state.investor.exchange.currencies(),
            help      = 'Everything will be converted to this currency'
        )



    def interact_benchmarks(self):
        streamlit.radio(
            label       = 'Select a benchmark to compare with',
            options     = streamlit.session_state.investor.benchmarks,
            format_func = lambda bench: str(bench['obj']),
            help        = 'Funds will be compared to the selected benchmark',
            key         = 'interact_benchmarks'
        )



    def interact_start_end(self):
        streamlit.slider(
            label       = 'Report Period Range',
            help        = 'Report starting on date',
            min_value   = streamlit.session_state.fund.start.to_pydatetime(),
            max_value   = streamlit.session_state.fund.end.to_pydatetime(),
            value       = (
                streamlit.session_state.fund.start.to_pydatetime(),
                streamlit.session_state.fund.end.to_pydatetime()
            ),
            key         = 'interact_start_end'
        )



    def interact_periods(self):
        streamlit.radio(
            label       = 'How to divide time',
            options     = investorzilla.Fund.getPeriodPairs(),
            format_func = investorzilla.Fund.getPeriodPairLabel,
            index       = investorzilla.Fund.getPeriodPairs().index('month & year'), # the starting default
            help        = 'Refine observation periods and set relation with summary of periods',
            key         = 'interact_periods'
        )



    def interact_refresh(self):
        self.refreshMap=self.defaultRefreshMap.copy()

        streamlit.subheader('Refresh data')

        col1, col2, col3 = streamlit.columns(3)

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



StreamlitInvestorzillaApp(refresh=False)
