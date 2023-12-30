import datetime
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

        # Make a preliminary internal fund from the portfolio for display purposes
        streamlit.session_state.investor.portfolio.makeInternalFund(
            streamlit.session_state.investor.exchange
        )

        with streamlit.sidebar:
            # Put controls in the sidebar
            self.interact_assets()
            self.interact_exclude_assets()
            self.interact_currencies()
            self.interact_benchmarks()
            self.interact_periods()

        # Render main content with plots and tables
        self.update_content()



    def prepare_fund(self):
        """
        Generate a virtual fund (shares and share value) based on portfolio
        items (assets) selected in sidebar.
        """

        fundset=None
        if 'interact_assets' in streamlit.session_state:
            assets=streamlit.session_state.interact_assets

            if 'ALL' in assets:
                assets.remove('ALL')

        if assets is None or len(assets)==0:
            assets=streamlit.session_state.investor.portfolio.assets()
            assets=[f[0] for f in assets]

        if 'interact_no_assets' in streamlit.session_state:
            assets=list(
                set(assets) -
                set(streamlit.session_state.interact_no_assets)
            )

        # Make a virtual fund (shares and share value) from selected assets
        streamlit.session_state.fund=streamlit.session_state.investor.portfolio.getFund(
            subset           = assets,
            currencyExchange = streamlit.session_state.investor.exchange
        )

        streamlit.session_state.fund.setName(top=4)



    def update_content(self):
        """
        Render the report
        """

        streamlit.session_state.investor.currency=streamlit.session_state.interact_currencies

        self.prepare_fund()

        (tab_performance, tab_shares, tab_currencies, tab_portfolio) = streamlit.tabs(
            [
                "📈 Performance",
                "📶 Fund Shares inspector",
                "🔁 Currencies inspector",
                "💼 Portfolio Components and Information",
            ]
        )

        with tab_performance:
            self.render_performance_page()

        with tab_shares:
            self.render_shares_page()

        with tab_currencies:
            self.render_currencies_page()

        with tab_portfolio:
            self.render_portfolio_page()

        streamlit.caption('Report by [investorzilla](https://github.com/avibrazil/investorzilla).')



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

        reportRagged=streamlit.session_state.fund.periodicReport(
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = streamlit.session_state.interact_start_end[0],
            end        = streamlit.session_state.interact_start_end[1],
        )

        reportPeriodic=streamlit.session_state.fund.periodicReport(
            period     = p['period'],
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = streamlit.session_state.interact_start_end[0],
            end        = streamlit.session_state.interact_start_end[1],
        )

        reportMacroPeriodic=streamlit.session_state.fund.periodicReport(
            period     = p['macroPeriod'],
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = streamlit.session_state.interact_start_end[0],
            end        = streamlit.session_state.interact_start_end[1],
        )

        if streamlit.session_state.interact_benchmarks['obj'].currency!=streamlit.session_state.fund.currency:
            streamlit.warning('Fund and Benchmark have different currencies. Benchamrk comparisons won’t make sense.')

        col1, col2, col3 = streamlit.columns(3)

        label='{kpi}: current {p[periodLabel]} and {p[macroPeriodLabel]}'

        # Rate of return
        col1.metric(
            label=label.format(p=p,kpi=investorzilla.KPI.RATE_RETURN),
            value='{:6.2f}%'.format(100*reportPeriodic.iloc[-1][investorzilla.KPI.RATE_RETURN]),
            delta='{:6.2f}%'.format(100*reportMacroPeriodic.iloc[-1][investorzilla.KPI.RATE_RETURN]),
        )

        # Gain
        col2.metric(
            label=label.format(p=p,kpi=investorzilla.KPI.PERIOD_GAIN),
            value='${:0,.2f}'.format(reportPeriodic.iloc[-1][investorzilla.KPI.PERIOD_GAIN]),
            delta='{sign}${value:0,.2f}'.format(
                value=abs(reportMacroPeriodic.iloc[-1][investorzilla.KPI.PERIOD_GAIN]),
                sign=('-' if reportMacroPeriodic.iloc[-1][investorzilla.KPI.PERIOD_GAIN]<0 else '')
            )
        )

        # Balance
        col3.metric(
            label='current {} & {}'.format(investorzilla.KPI.BALANCE,investorzilla.KPI.SAVINGS),
            value='${:0,.2f}'.format(reportPeriodic.iloc[-1][investorzilla.KPI.BALANCE]),
            delta='{sign}${value:0,.2f}'.format(
                value=abs(reportMacroPeriodic.iloc[-1][investorzilla.KPI.SAVINGS]),
                sign=('-' if reportMacroPeriodic.iloc[-1][investorzilla.KPI.SAVINGS]<0 else '')
            )
        )



        col1, col2 = streamlit.columns(2)

        with col1:
            streamlit.header('Performance', divider='red')
            streamlit.line_chart(
                streamlit.session_state.fund.performancePlot(
                    benchmark=streamlit.session_state.interact_benchmarks['obj'],
                    precomputedReport=reportRagged,
                    type='raw'
                )
            )

            streamlit.pyplot(
                streamlit.session_state.fund.rateOfReturnPlot(
                    precomputedReport=reportPeriodic,
                    type='pyplot'
                )
            )

        with col2:
            streamlit.header('Gains', divider='red')
            streamlit.altair_chart(
                use_container_width=True,
                altair_chart=streamlit.session_state.fund.incomePlot(
                    periodPair=streamlit.session_state.interact_periods,
                    type='altair',
                    precomputedReport=reportPeriodic
                )
            )

            streamlit.line_chart(
                streamlit.session_state.fund.wealthPlot(
                    benchmark=streamlit.session_state.interact_benchmarks['obj'],
                    precomputedReport=reportRagged,
                    type='raw'
                )
            )

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

        # kpi        = streamlit.session_state['kpi_performance'],

        report=streamlit.session_state.fund.report(
                precomputedPeriodicReport      = reportPeriodic,
                precomputedMacroPeriodicReport = reportMacroPeriodic,
                period     = streamlit.session_state.interact_periods,
                benchmark  = streamlit.session_state.interact_benchmarks['obj'],
                start      = streamlit.session_state.interact_start_end[0],
                end        = streamlit.session_state.interact_start_end[1],
            )

        streamlit.markdown(
            investorzilla.Fund.format(
                investorzilla.Fund.filter(
                    report,
                    kpi=streamlit.session_state.kpi_performance
                )
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
            investorzilla.Fund.format(
                investorzilla.Fund.filter(
                    report,
                    kpi=streamlit.session_state.kpi_wealth
                )
            )
            .set_table_styles(table_styles)

            .to_html(),
            unsafe_allow_html=True
        )

        # Render footer stats
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



    def render_currencies_page(self):
        streamlit.title(f"1 {streamlit.session_state.investor.exchange.currency} in other currencies")
        streamlit.dataframe(
            (
                (1/streamlit.session_state.investor.exchange.data)
                # Deliver time information in user’s timezone
                .assign(
                    time=lambda table: (
                        table.index
                        .tz_convert(
                            datetime.datetime.now(datetime.timezone.utc)
                            .astimezone()
                            .tzinfo
                        )
                    ),
                )
                .set_index('time')
                .sort_index(ascending=False)
            ),
            use_container_width=True,
            column_config={
                c: streamlit.column_config.NumberColumn(format="%.16f")
                for c in streamlit.session_state.investor.exchange.data.columns
            }
        )



    def render_shares_page(self):
        streamlit.title(streamlit.session_state.fund.name)
        streamlit.dataframe(
            (
                streamlit.session_state.fund.shares
                .assign(
                    time=lambda table: table.index.tz_convert(datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo),
                    balance=lambda table: (
                        table[investorzilla.KPI.SHARES] *
                        table[investorzilla.KPI.SHARE_VALUE]
                    )
                )
                .set_index('time')
            ),
            use_container_width=True,
            column_config={
                investorzilla.KPI.SHARES: streamlit.column_config.NumberColumn(
                    help="Number of shares of the virtual fund formed by selected assets, in that point of time",
                ),
                investorzilla.KPI.SHARE_VALUE: streamlit.column_config.NumberColumn(
                    help=f"The value of each share, in {streamlit.session_state.fund.currency}",
                    # format=investorzilla.Fund.formatters[investorzilla.KPI.SHARE_VALUE]['format'],
                    format="$%.6f"
                ),
                investorzilla.KPI.BALANCE: streamlit.column_config.NumberColumn(
                    help=f"Balance in that point of time, in {streamlit.session_state.fund.currency}",
                    format="$%.2f"
                )
            }
        )



    def render_portfolio_page(self):
        with streamlit.expander('Personal Portfolio'):
            streamlit.markdown(streamlit.session_state.investor.portfolio.to_markdown(title_prefix='##'))

        with streamlit.expander('Currency Converters'):
            for c in streamlit.session_state.investor.currency_converters:
                streamlit.markdown(c['obj'].to_markdown(title_prefix='###'))

        with streamlit.expander('Market Indexes'):
            for b in streamlit.session_state.investor.benchmarks:
                streamlit.markdown(b['obj'].to_markdown(title_prefix='###'))



    # All the interact_* methods manager widgets in the Streamlit UI

    def interact_assets(self):
        streamlit.multiselect(
            label     = 'Select assets to make a fund',
            options   = (
                ['ALL']+
                [
                    x[0]
                    for x in streamlit.session_state.investor.portfolio.assets()
                ]
            ),
            help      = 'Shares and share value will be computed for the union of selected assets',
            key       = 'interact_assets'
        )



    def interact_exclude_assets(self):
        streamlit.multiselect(
            label     = 'Except assets',
            options   = [
                x[0]
                for x in streamlit.session_state.investor.portfolio.assets()
            ],
            help      = 'Exclude assets selected here',
            key       = 'interact_no_assets'
        )



    def interact_currencies(self):
        currencies=streamlit.session_state.investor.exchange.currencies()

        # Find the index of default currency
        for i in range(len(currencies)):
            if currencies[i]==streamlit.session_state.investor.config['currency']:
                break

        streamlit.radio(
            label     = 'Convert all to currency',
            options   = currencies,
            index     = i,
            help      = 'Everything will be converted to selected currency',
            key       = 'interact_currencies'
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
