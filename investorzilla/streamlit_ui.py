import datetime
import logging
import copy

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

        if True in self.refreshMap.values():
            streamlit.cache_resource.clear()

        # Load domains from Investor internal cache, the Internet or reuse
        # Streamlit memory-cached object
        self.investor()

        with streamlit.sidebar:
            # Put controls in the sidebar
            self.interact_assets()
            self.interact_exclude_assets()
            self.interact_start_end()
            self.interact_currencies()
            self.interact_benchmarks()
            self.interact_periods()

        # Render main content with plots and tables
        self.update_content()



    @streamlit.cache_resource(show_spinner="Loading portfolio, currency exchanges and benchmarks...")
    def investor(_self):
        """
        Read config file investorzilla.yaml and load its described portfolio
        resources from cache or from the Internet. Investor's internal cache
        is controled by self.refreshMap, which is a dict that looks like:

        dict(
            portfolio=False,
            currency_converters=False,
            benchmarks=False
        )

        Each entry (caled domain) defines if content should be reloaded from
        its (slow) source (the Internet) (True) or from cache (False). If cache
        is empty or doesn't exist, content is loaded from its original source.

        The Investor object returned by this method is cached by Streamlit and
        will be used as a singleton across all sessions. If one session updates
        the Investor object, all other sessions will benefit from it.

        Returns the (cached) Investor object, which includes data of all entries
        defined in the investorzilla.yaml config file: asset data, currency
        convertion tables, benchmark data.
        """

        investor = investorzilla.Investor(
            'investorzilla.yaml',
            _self.refreshMap
        )

        # Make a preliminary internal fund from the portfolio for display purposes
        investor.portfolio.makeInternalFund(
            currencyExchange=investor.exchange
        )

        return investor



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
            assets=self.investor().portfolio.assets()
            assets=[f[0] for f in assets]

        if 'interact_no_assets' in streamlit.session_state:
            assets=list(
                set(assets) -
                set(streamlit.session_state.interact_no_assets)
            )

        # Make a virtual fund (shares and share value) from selected assets
        streamlit.session_state.fund=self.investor().portfolio.getFund(
            subset           = assets,
            currencyExchange = streamlit.session_state.exchange
        )

        streamlit.session_state.fund.setName(top=4)

        p=investorzilla.Fund.periodPairs[streamlit.session_state.interact_periods]

        self.start = (
            streamlit.session_state.interact_start_end[0]
            if len(streamlit.session_state.interact_start_end)>0
            else self.investor().portfolio.fund.start
        )
        self.end   = (
            streamlit.session_state.interact_start_end[1]
            if len(streamlit.session_state.interact_start_end)>1
            else self.investor().portfolio.fund.end
        )

        # Now that we have a fund, create periodic reports
        self.reportRagged=streamlit.session_state.fund.periodicReport(
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = self.start,
            end        = self.end,
        )

        self.reportPeriodic=streamlit.session_state.fund.periodicReport(
            period     = p['period'],
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = self.start,
            end        = self.end,
        )

        self.reportMacroPeriodic=streamlit.session_state.fund.periodicReport(
            period     = p['macroPeriod'],
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = self.start,
            end        = self.end,
        )

        self.report=streamlit.session_state.fund.report(
            precomputedPeriodicReport      = self.reportPeriodic,
            precomputedMacroPeriodicReport = self.reportMacroPeriodic,
            period     = streamlit.session_state.interact_periods,
            benchmark  = streamlit.session_state.interact_benchmarks['obj'],
            start      = self.start,
            end        = self.end,
        )



    def update_content(self):
        """
        Render the report
        """

        # Sessions use a copy of the global currency exchange machine
        streamlit.session_state.exchange=copy.deepcopy(self.investor().exchange)
        streamlit.session_state.exchange.currency=streamlit.session_state.interact_currencies

        self.prepare_fund()

        (
            tab_performance,
            tab_wealth,
            tab_contributions,
            tab_summary,
            tab_shares,
            tab_currencies,
            tab_portfolio
        ) = streamlit.tabs(
            [
                "📈 Performance",
                "📈 Wealth",
                "📶 Per Asset Contributions",
                "💼 Portfolio Summary",
                "📶 Fund Shares inspector",
                "🔁 Currencies inspector",
                "💼 Portfolio Components and Information",
            ]
        )

        with tab_performance:
            self.render_performance_page()

        with tab_wealth:
            self.render_wealth_page()

        with tab_contributions:
            self.render_contributions_page()

        with tab_summary:
            self.render_summary_page()

        with tab_shares:
            self.render_shares_page()

        with tab_currencies:
            self.render_currencies_page()

        with tab_portfolio:
            self.render_portfolio_page()

        streamlit.divider()
        streamlit.caption(f'Report by **[Investorzilla](https://github.com/avibrazil/investorzilla) {investorzilla.__version__}**.')



    def render_summary_page(self):
        # Render title
        streamlit.title(streamlit.session_state.fund.name)

        streamlit.dataframe(
            data                = streamlit.session_state.fund.describe(),
            use_container_width = True,
        )



    def render_contributions_page(self):
        # Render title
        streamlit.title(streamlit.session_state.fund.name)

        kpis=[
            investorzilla.KPI.PERIOD_GAIN,
            investorzilla.KPI.GAINS,
            investorzilla.KPI.BALANCE,
            investorzilla.KPI.SAVINGS,
            investorzilla.KPI.MOVEMENTS
        ]

        col1, col2 = streamlit.columns(2)

        col1.radio(
            "Select KPI to show the contribution of each Asset",
            kpis,
            key='kpi_contributions',
            horizontal=True,
        )

        col2.selectbox(
           "Select point in time",
            self.reportPeriodic.index.sort_values(ascending=False),
            key="pointintime_contributions"
        )

        streamlit.altair_chart(
            use_container_width=True,
            altair_chart=streamlit.session_state.fund.assetContributionPlot(
                pointInTime=streamlit.session_state.pointintime_contributions,
                kpi=streamlit.session_state.kpi_contributions,
                period=investorzilla.Fund.periodPairs[streamlit.session_state.interact_periods]['period'],
            ).interactive()
        )



    def render_wealth_page(self):
        p=investorzilla.Fund.periodPairs[streamlit.session_state.interact_periods]

        # Render title
        streamlit.title(streamlit.session_state.fund.name)

        # Render main metrics
        # streamlit.header('Main Metrics')

        if streamlit.session_state.interact_benchmarks['obj'].currency!=streamlit.session_state.fund.currency:
            streamlit.warning('Fund and Benchmark have different currencies. Benchmark comparisons won’t make sense.')

        col1, col2, col3, col4 = streamlit.columns(4)

        label='{kpi}: current {p[periodLabel]} and {p[macroPeriodLabel]}'

        # Balance
        col1.metric(
            label='current {} & {}'.format(investorzilla.KPI.BALANCE,investorzilla.KPI.SAVINGS),
            value='${:0,.2f}'.format(self.reportPeriodic.iloc[-1][investorzilla.KPI.BALANCE]),
            delta='{sign}${value:0,.2f}'.format(
                value=abs(self.reportMacroPeriodic.iloc[-1][investorzilla.KPI.SAVINGS]),
                sign=('-' if self.reportMacroPeriodic.iloc[-1][investorzilla.KPI.SAVINGS]<0 else '')
            ),
            help='Current balance compared to all your savings'
        )

        col2.metric(
            label=investorzilla.KPI.GAINS,
            value='${:0,.2f}'.format(self.reportPeriodic.iloc[-1][investorzilla.KPI.GAINS]),
            help='Overall sum of all gains and losses so far'
        )

        col3.metric(
            label=investorzilla.KPI.BALANCE_OVER_SAVINGS,
            value='{:6.2f}%'.format(100*self.reportPeriodic[investorzilla.KPI.BALANCE_OVER_SAVINGS].iloc[-1]),
            help='How many times your balance is bigger than your savings'
        )

        # Latest average movements (power of saving)
        col4.metric(
            label=f"{investorzilla.KPI.MOVEMENTS}: last {p['macroPeriodLabel']} median and mean for a {p['periodLabel']}",
            value='${:0,.2f}'.format(
                self.reportPeriodic[investorzilla.KPI.MOVEMENTS]
                .tail(investorzilla.Fund.div_offsets(p['macroPeriod'],p['period']))
                .median()
            ),
            delta='${:0,.2f}'.format(
                self.reportPeriodic[investorzilla.KPI.MOVEMENTS]
                .tail(investorzilla.Fund.div_offsets(p['macroPeriod'],p['period']))
                .mean()
            ),
            help='Long term tendency of saving money'
        )

        col1, col2 = streamlit.columns(2)

        with col1:
            streamlit.line_chart(
                use_container_width=True,
                data=streamlit.session_state.fund.wealthPlot(
                    benchmark=streamlit.session_state.interact_benchmarks['obj'],
                    precomputedReport=self.reportRagged,
                    type='raw'
                )
            )

            streamlit.line_chart(
                use_container_width=True,
                data=self.reportRagged,
                y=investorzilla.KPI.BALANCE_OVER_SAVINGS
            )

        with col2:
            streamlit.altair_chart(
                use_container_width=True,
                altair_chart=streamlit.session_state.fund.genericPeriodicPlot(
                    kpi=investorzilla.KPI.MOVEMENTS,
                    periodPair=streamlit.session_state.interact_periods,
                    type='altair',
                    precomputedReport=self.reportPeriodic
                ).interactive()
            )

        table_styles=[
            dict(selector="td", props="font-size: 0.8em; text-align: right"),
            dict(selector="th", props="font-size: 0.8em; "),
            dict(selector='tr:hover', props='background-color: yellow')
        ]

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
                    self.report,
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
                self.investor().portfolio.asof.strftime('%Y-%m-%d %X %z')
            )
        )

        streamlit.markdown(
            'Graph data between **{}** and **{}**'.format(self.start,self.end)
        )



    def render_performance_page(self):
        p=investorzilla.Fund.periodPairs[streamlit.session_state.interact_periods]

        # Render title
        streamlit.title(streamlit.session_state.fund.name)

        # Render period slider
        # self.interact_start_end()

        # Render main metrics
        # streamlit.header('Main Metrics')

        if streamlit.session_state.interact_benchmarks['obj'].currency!=streamlit.session_state.fund.currency:
            streamlit.warning('Fund and Benchmark have different currencies. Benchmark comparisons won’t make sense.')

        col1, col2, col3, col4 = streamlit.columns(4)

        label='{kpi}: current {p[periodLabel]} and {p[macroPeriodLabel]}'

        # Rate of return
        col1.metric(
            label=label.format(p=p,kpi=investorzilla.KPI.RATE_RETURN),
            value='{:6.2f}%'.format(100*self.reportPeriodic.iloc[-1][investorzilla.KPI.RATE_RETURN]),
            delta='{:6.2f}%'.format(100*self.reportMacroPeriodic.iloc[-1][investorzilla.KPI.RATE_RETURN]),
        )

        # Latest average rate of return
        col2.metric(
            label=f"{investorzilla.KPI.RATE_RETURN}: {p['periodLabel']} median and mean over last {p['macroPeriodLabel']}",
            value='{:6.2f}%'.format(100 * (
                    self.reportPeriodic[investorzilla.KPI.RATE_RETURN]
                    .tail(investorzilla.Fund.div_offsets(p['macroPeriod'],p['period']))
                    .median()
                )
            ),
            delta='{:6.2f}%'.format(100 * (
                    self.reportPeriodic[investorzilla.KPI.RATE_RETURN]
                    .tail(investorzilla.Fund.div_offsets(p['macroPeriod'],p['period']))
                    .mean()
                )
            ),
        )

        # Gain
        col3.metric(
            label=label.format(p=p,kpi=investorzilla.KPI.PERIOD_GAIN),
            value='${:0,.2f}'.format(self.reportPeriodic.iloc[-1][investorzilla.KPI.PERIOD_GAIN]),
            delta='{sign}${value:0,.2f}'.format(
                value=abs(self.reportMacroPeriodic.iloc[-1][investorzilla.KPI.PERIOD_GAIN]),
                sign=('-' if self.reportMacroPeriodic.iloc[-1][investorzilla.KPI.PERIOD_GAIN]<0 else '')
            )
        )

        # Average Gain
        col4.metric(
            label=f"{investorzilla.KPI.PERIOD_GAIN}: {p['periodLabel']} median and mean over last {p['macroPeriodLabel']}",
            value='${:0,.2f}'.format(
                self.reportPeriodic[investorzilla.KPI.PERIOD_GAIN]
                .tail(investorzilla.Fund.div_offsets(p['macroPeriod'],p['period']))
                .median()
            ),
            delta='${:0,.2f}'.format(
                self.reportPeriodic[investorzilla.KPI.PERIOD_GAIN]
                .tail(investorzilla.Fund.div_offsets(p['macroPeriod'],p['period']))
                .mean()
            ),
        )


        col1, col2 = streamlit.columns(2)

        with col1:
            streamlit.header('Performance', divider='red')
            streamlit.line_chart(
                streamlit.session_state.fund.performancePlot(
                    benchmark=streamlit.session_state.interact_benchmarks['obj'],
                    precomputedReport=self.reportRagged,
                    type='raw'
                )
            )

            streamlit.altair_chart(
                use_container_width=True,
                altair_chart=streamlit.session_state.fund.rateOfReturnPlot(
                    precomputedReport=self.reportPeriodic,
                    type='altair'
                ).interactive()
            )

        with col2:
            streamlit.header('Gains', divider='red')
            streamlit.altair_chart(
                use_container_width=True,
                altair_chart=streamlit.session_state.fund.genericPeriodicPlot(
                    kpi=investorzilla.KPI.PERIOD_GAIN,
                    periodPair=streamlit.session_state.interact_periods,
                    type='altair',
                    precomputedReport=self.reportPeriodic
                ).interactive()
            )

            streamlit.altair_chart(
                use_container_width=True,
                altair_chart=streamlit.session_state.fund.genericPeriodicPlot(
                    kpi=investorzilla.KPI.RATE_RETURN,
                    periodPair=streamlit.session_state.interact_periods,
                    type='altair',
                    precomputedReport=self.reportPeriodic
                ).interactive()
            )

        table_styles=[
            dict(selector="td", props="font-size: 0.8em; text-align: right"),
            dict(selector="th", props="font-size: 0.8em; "),
            dict(selector='tr:hover', props='background-color: yellow')
        ]

        streamlit.header('Performance')
        streamlit.markdown(
            "Benchmark is **{}**."
            .format(streamlit.session_state.interact_benchmarks['obj'])
        )

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
            investorzilla.Fund.format(
                investorzilla.Fund.filter(
                    self.report,
                    kpi=streamlit.session_state.kpi_performance
                )
            )
            .set_table_styles(table_styles)

            .to_html(),
            unsafe_allow_html=True
        )

        # Render footer stats
        streamlit.markdown(
            'Most recent porfolio data is **{}**'.format(
                self.investor().portfolio.asof
            )
        )

        streamlit.markdown(
            'Graph data between **{}** and **{}**'.format(self.start,self.end)
        )



    def render_currencies_page(self):
        streamlit.title(f"1 {streamlit.session_state.exchange.currency} in other currencies")
        streamlit.dataframe(
            (
                (1/streamlit.session_state.exchange.data)
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
                for c in self.investor().exchange.data.columns
            }
        )



    def render_shares_page(self):
        streamlit.title(streamlit.session_state.fund.name)
        streamlit.dataframe(
            (
                streamlit.session_state.fund.shares
                .assign(
                    **{
                        'time': lambda table: table.index.tz_convert(datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo),
                        investorzilla.KPI.BALANCE: lambda table: (
                            table[investorzilla.KPI.SHARES] *
                            table[investorzilla.KPI.SHARE_VALUE]
                        )
                    }
                )
                .set_index('time')
                [
                    [
                        investorzilla.KPI.SHARES,
                        investorzilla.KPI.SHARE_VALUE,
                        investorzilla.KPI.BALANCE,
                        'asset',
                        'comment'
                    ]
                ]
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
                ),
                'asset': streamlit.column_config.TextColumn(
                    help="Asset making changes in number of shares (ledger)"
                )
            }
        )



    def render_portfolio_page(self):
        with streamlit.expander('Personal Portfolio'):
            streamlit.markdown(self.investor().portfolio.to_markdown(title_prefix='##'))

        with streamlit.expander('Currency Converters'):
            for c in self.investor().currency_converters:
                streamlit.markdown(c['obj'].to_markdown(title_prefix='###'))

        with streamlit.expander('Market Indexes'):
            for b in self.investor().benchmarks:
                streamlit.markdown(b['obj'].to_markdown(title_prefix='###'))



    # All the interact_* methods manage widgets in the Streamlit UI

    def interact_assets(self):
        streamlit.multiselect(
            label     = 'Select assets to make a fund',
            options   = (
                ['ALL']+
                [
                    x[0]
                    for x in self.investor().portfolio.assets()
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
                for x in self.investor().portfolio.assets()
            ],
            help      = 'Exclude assets selected here',
            key       = 'interact_no_assets'
        )



    def interact_currencies(self):
        currencies=self.investor().exchange.currencies()

        # Find the index of default currency
        for i in range(len(currencies)):
            if currencies[i]==self.investor().config['currency']:
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
            options     = self.investor().benchmarks,
            format_func = lambda bench: str(bench['obj']),
            help        = 'Funds will be compared to the selected benchmark',
            key         = 'interact_benchmarks'
        )



    def interact_start_end(self):
        inv=self.investor()

        key='relevant period'
        defaults = dict(
            start = (
                inv.config[key]['start']
                if key in inv.config and 'start' in inv.config[key]
                else inv.portfolio.fund.start.to_pydatetime()
            ),
            end = (
                inv.config[key]['end']
                if key in inv.config and 'end' in inv.config[key]
                else inv.portfolio.fund.end.to_pydatetime()
            )
        )

        streamlit.date_input(
            label       = 'Report Period Range',
            help        = 'Report starting on date',
            min_value   = inv.portfolio.fund.start.to_pydatetime(),
            max_value   = inv.portfolio.fund.end.to_pydatetime(),
            value       = (defaults['start'],defaults['end']),
            format      = 'YYYY-MM-DD',
            key         = 'interact_start_end'
        )



    def interact_periods(self):
        streamlit.radio(
            label       = 'How to divide time',
            options     = investorzilla.Fund.getPeriodPairs(),
            # format_func = investorzilla.Fund.getPeriodPairLabel,
            index       = investorzilla.Fund.getPeriodPairs().index('month & year'), # the starting default
            help        = 'Pairs of period (as month) and macro period (as year)',
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
