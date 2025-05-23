import datetime
import zoneinfo
import tzlocal
import random
import string
import logging
import copy
import textwrap
import pandas

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

    view_tag="🥽 view"

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

        self.currencies_container=None
        self.benchmarks_container=None

        if 'interact_currencies_value' not in streamlit.session_state:
            streamlit.session_state.interact_currencies_value=None

        if 'interact_benchmarks_value' not in streamlit.session_state:
            streamlit.session_state.interact_benchmarks_value=None

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
            if self.check_password() is False:
                return

            # Put controls in the sidebar
            self.interact_assets()
            self.interact_exclude_assets()
            self.interact_start_end()
            self.interact_currencies(streamlit.session_state.interact_currencies_value)
            self.interact_benchmarks(streamlit.session_state.interact_benchmarks_value)
            self.interact_periods()

        # Render main content with plots and tables
        self.update_content()


    def check_password(self):
        if (
                'authenticated' in streamlit.session_state and
                streamlit.session_state.authenticated
            ):
            return True

        if 'password' in self.investor().config:
            streamlit.text_input(
                label       = '',
                placeholder = 'App password',
                type        = 'password',
                key         = 'pass'
            )

            streamlit.session_state.authenticated = (
                streamlit.session_state['pass'] == self.investor().config['password']
            )
        else:
            streamlit.session_state.authenticated = True

        return streamlit.session_state.authenticated



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

        Each entry (called domain) defines if content should be reloaded from
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
        assets=self.get_interact_assets()

        if 'interact_no_assets' in streamlit.session_state:
            assets=list(
                set(assets) -
                set(
                    self.resolve_views_assets(
                        streamlit.session_state.interact_no_assets
                    )
                )
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
            benchmark  = streamlit.session_state.interact_benchmarks_value['obj'],
            start      = self.start,
            end        = self.end,
        )

        self.reportPeriodic=streamlit.session_state.fund.periodicReport(
            period     = p['period'],
            benchmark  = streamlit.session_state.interact_benchmarks_value['obj'],
            start      = self.start,
            end        = self.end,
        )

        self.reportMacroPeriodic=streamlit.session_state.fund.periodicReport(
            period     = p['macroPeriod'],
            benchmark  = streamlit.session_state.interact_benchmarks_value['obj'],
            start      = self.start,
            end        = self.end,
        )

        self.report=streamlit.session_state.fund.report(
            precomputedPeriodicReport      = self.reportPeriodic,
            precomputedMacroPeriodicReport = self.reportMacroPeriodic,
            period     = streamlit.session_state.interact_periods,
            benchmark  = streamlit.session_state.interact_benchmarks_value['obj'],
            start      = self.start,
            end        = self.end,
        )



    def update_content(self):
        """
        Render the report
        """

        # Sessions use a copy of the global currency exchange machine
        streamlit.session_state.exchange=copy.deepcopy(self.investor().exchange)
        streamlit.session_state.exchange.currency=streamlit.session_state.interact_currencies_value

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
                "💼 Report Components and Information",
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



        # Page footer stats and signature
        streamlit.divider()

        streamlit.caption(
            'Most recent porfolio data is **{}**'.format(
                self.investor().portfolio.asof
            )
        )

        now_local = datetime.datetime.now(
            zoneinfo.ZoneInfo(tzlocal.get_localzone_name())
        )

        streamlit.caption(
            textwrap.dedent(f"""\
                Reported on {now_local:%Y-%m-%d %H:%M:%S%Z} 
                by **[Investorzilla]
                (https://github.com/avibrazil/investorzilla) 
                {investorzilla.__version__}**.
            """)
            # Make it a one line string
            .replace('\n','')
        )



    def render_summary_page(self):
        # Get list of assets for each currency as dict:
        #    dict(
        #         BRL = ['Asset 1', 'Asset 3',...],
        #         USD = ['Asset 4', 'Asset 2',...],
        #         ...
        #    )
        assets_of_currencies = (
            # Get list of assets in portfolio
            self.investor().portfolio
            .balance
            .drop(columns='time')

            # Compute number of entries for each currency
            .groupby(by='asset')
            .count()

            # Get the most popular currency for each asset
            .idxmax(axis=1)

            # Data wrangling to convert it to desired dict
            .to_frame()
            .reset_index()
            .set_index(0)
            .sort_index()
            .assign(
                subindex=lambda table: table.groupby(table.index).cumcount()
            )
            .set_index('subindex', append=True)
            .pipe(
                lambda table: {currency: assets.asset.to_list() for currency, assets in table.groupby(level=0)}
            )
        )

        fund_assets=set(streamlit.session_state.fund.getAssetList())

        for currency in assets_of_currencies.keys():
            selected_assets=list(
                set(assets_of_currencies[currency]) &
                fund_assets
            )

            if len(selected_assets)<1:
                continue

            exg=copy.deepcopy(self.investor().exchange)
            exg.currency=currency
            fund=self.investor().portfolio.getFund(
                subset           = selected_assets,
                currencyExchange = exg
            )

            reportRagged=fund.periodicReport(
                start      = self.start,
                end        = self.end,
            )

            # Render title
            streamlit.title(f"Assets in {currency} as of {self.end}")

            streamlit.dataframe(
                data                = fund.describe(asof=self.end),
                use_container_width = True,
            )

            streamlit.markdown(
                'Net Liquidation Value (sum of all balances): **${nlv:0,.2f} {currency}**'.format(
                    nlv=reportRagged.iloc[-1][investorzilla.KPI.BALANCE],
                    currency=fund.exchange.target
                )
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

        if streamlit.session_state.interact_benchmarks_value['obj'].currency!=streamlit.session_state.fund.currency:
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
            label='{} & TWR'.format(investorzilla.KPI.GAINS),
            value='${:0,.2f}'.format(self.reportPeriodic.iloc[-1][investorzilla.KPI.GAINS]),
            delta='{:6.2f}%'.format(
                100 * (
                    # (share_value_end-share_value_start)/share_value_start
                    (
                        self.reportRagged[investorzilla.KPI.SHARE_VALUE].iloc[-1] -
                        self.reportRagged[investorzilla.KPI.SHARE_VALUE].iloc[0]
                    ) /
                    self.reportRagged[investorzilla.KPI.SHARE_VALUE].iloc[0]
                )
            ),
            help='Overall sum of all gains and losses in period & Time Weighted Return'
        )

        col3.metric(
            label=investorzilla.KPI.BALANCE_OVER_SAVINGS,
            value='{:6.2f}%'.format(100*self.reportPeriodic[investorzilla.KPI.BALANCE_OVER_SAVINGS].iloc[-1]),
            help='How many times your balance is bigger than your savings'
        )

        # Latest average movements (capacity of saving money)
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
            help='Long term tendency of saving or spending money'
        )

        col1, col2 = streamlit.columns(2)

        with col1:
            streamlit.line_chart(
                use_container_width=True,
                data=streamlit.session_state.fund.wealthPlot(
                    benchmark=streamlit.session_state.interact_benchmarks_value['obj'],
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

            # Render 4% Rule text
            rates=[3,4,5,6,7,8,9,10]
            streamlit.dataframe(
                use_container_width=True,
                data=(
                    pandas.DataFrame.from_dict(
                        dict(
                            balance=self.reportPeriodic.iloc[-1][investorzilla.KPI.BALANCE],
                            rates=rates
                        )
                    )
                    .assign(**{
                        'annual withdrawal': lambda table: table.balance*table.rates/100,
                        'monthly withdrawal': lambda table: table.balance*table.rates/100/12
                    })
                    .drop(columns='balance')
                    .rename(columns=dict(rates='rate %'))
                    .set_index('rate %')
                    .style
                    .format(formatter="${:,.0f}")
                )
            )

            streamlit.markdown(textwrap.dedent("""\
                [4% Rule](https://www.investopedia.com/terms/f/four-percent-rule.asp)
                allows you to withdraw only the interests from your
                portfolio, never touching the main assets. It is useful in a
                retirement scenario when you are not depositing to your assets
                anymore. Here we give you annual withdrawal rates from {start}%
                to {end}%. A conservative approach is to pick a rate lower than
                your annual rate of return.
            """).format(start=rates[0],end=rates[-1]))



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
            investorzilla.KPI.MOVEMENTS,
            investorzilla.KPI.DEPOSITS,
            investorzilla.KPI.WITHDRAWALS,
            investorzilla.KPI.GAIN_MINUS_WITHDRAWAL,
            investorzilla.KPI.GAIN_OVER_WITHDRAWAL,
        ]

        streamlit.multiselect(
            label='Select KPIs to display in table',
            label_visibility='collapsed',
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

        if streamlit.session_state.interact_benchmarks_value['obj'].currency!=streamlit.session_state.fund.currency:
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
                    benchmark=streamlit.session_state.interact_benchmarks_value['obj'],
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
            .format(streamlit.session_state.interact_benchmarks_value['obj'])
        )

        performance_benchmarks=[
            investorzilla.KPI.RATE_RETURN,
            investorzilla.KPI.BENCHMARK_RATE_RETURN,
            investorzilla.KPI.BENCHMARK_EXCESS_RETURN,
            investorzilla.KPI.PERIOD_GAIN
        ]

        streamlit.multiselect(
            label='Select KPIs to display in table',
            label_visibility='collapsed',
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
        # TODO: implement paging from https://medium.com/streamlit/paginating-dataframes-with-streamlit-2da29b080920
        streamlit.title(streamlit.session_state.fund.name)
        streamlit.dataframe(
            (
                self.reportRagged

                # Only relevant columns in a good order
                [[
                    investorzilla.KPI.BALANCE,
                    investorzilla.KPI.PERIOD_GAIN,
                    investorzilla.KPI.RATE_RETURN,
                    investorzilla.KPI.MOVEMENTS,
                    investorzilla.KPI.SAVINGS,
                    investorzilla.KPI.GAINS,
                    investorzilla.KPI.BALANCE_OVER_SAVINGS,
                    investorzilla.KPI.SHARES,
                    investorzilla.KPI.SHARE_VALUE,
                    'asset',
                    'comment'
                ]]

                # If this is a single-asset report, asset name in the table
                # is redundant; drop column then
                .pipe(
                    lambda table: (
                        table.drop(columns='asset')
                        if len(table.asset.dropna().unique())<2
                        else table
                    )
                )

                # Apply number formatting
                .pipe(
                    lambda table:
                        table.style.format(
                            {
                                c: investorzilla.Fund.formatters[c]['format'].format
                                for c in table.columns
                                if c in investorzilla.Fund.formatters
                            }
                        )
                )
            ),

            use_container_width=True,

            # Column formatting
            column_config={
                investorzilla.KPI.SHARES: streamlit.column_config.NumberColumn(
                    help="Number of shares of the virtual fund formed by selected assets, in that point of time",
                ),
                investorzilla.KPI.SHARE_VALUE: streamlit.column_config.NumberColumn(
                    help=f"The value of each share, in {streamlit.session_state.fund.currency}",
                    # format=investorzilla.Fund.formatters[investorzilla.KPI.SHARE_VALUE]['format'],
                    # format="$%.6f"
                ),
                investorzilla.KPI.BALANCE: streamlit.column_config.NumberColumn(
                    help=f"Balance in that point of time, in {streamlit.session_state.fund.currency}",
                    # format="$%.2f"
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

    def set_view(self):
        """Update visuals of currency and benchmark widgets to what is defined
        in the view"""

        view=self.get_view()

        if view:
            # streamlit.session_state.logger.info(f"View: {view}")

            for b in self.investor().benchmarks:
                if b['obj'].get_name() == view['benchmark']:
                    break

            self.interact_currencies(view['currency'])
            self.interact_benchmarks(b)



    def interact_assets(self):
        options = (
            ['ALL'] +
            [
                x[0]
                for x in self.investor().portfolio.assets()
            ]
        )

        if 'views' in self.investor().config:
            options += [
                f"{self.view_tag}: {c}"
                for c in self.investor().config['views'].keys()
            ]

        streamlit.multiselect(
            label       = 'Select assets to make a fund',
            placeholder = 'All assets selected',
            options     = options,
            help        = 'Shares and share value will be computed for the union of selected assets',
            key         = 'interact_assets',
            on_change   = self.set_view
        )



    def resolve_views_assets(self,interact):
        # Explode all views into its actual list of assets
        resolved_assets=[]
        for a in interact:
            if self.view_tag in a:
                resolved_assets += self.investor().config['views'][a.replace(f"{self.view_tag}: ","")]['assets']
            else:
                resolved_assets.append(a)

        return resolved_assets



    def get_view(self):
        """Get the view object defined in the YAML"""

        if 'interact_assets' in streamlit.session_state:
            assets=streamlit.session_state.interact_assets
            for a in assets:
                if self.view_tag in a:
                    return (
                        self.investor()
                        .config['views'][a.replace(f"{self.view_tag}: ","")]
                    )

        return None



    def get_interact_assets(self):
        if 'interact_assets' in streamlit.session_state:
            assets=streamlit.session_state.interact_assets

            if 'ALL' in assets:
                assets.remove('ALL')

        if assets is None or len(assets)==0:
            assets=self.investor().portfolio.assets()
            assets=[f[0] for f in assets]

        return self.resolve_views_assets(assets)



    def interact_exclude_assets(self):
        options = [
            x[0]
            for x in self.investor().portfolio.assets()
        ]

        if 'views' in self.investor().config:
            options += [
                f"{self.view_tag}: {c}"
                for c in self.investor().config['views'].keys()
            ]

        streamlit.multiselect(
            label       = 'Except assets',
            placeholder = 'No assets are excluded',
            options     = options,
            help        = 'Exclude assets selected here',
            key         = 'interact_no_assets'
        )



    def interact_currencies(self, currency=None):
        if self.currencies_container is None:
            self.currencies_container=streamlit.empty()
        else:
            self.currencies_container.empty()

        currencies=self.investor().exchange.currencies()

        # Set the currency we'll be initialized with
        if currency:
            desired=currency
        else:
            desired=self.investor().config['currency']

        # Find the index of desired currency
        for i in range(len(currencies)):
            if currencies[i]==desired:
                break

        streamlit.session_state.interact_currencies_value=self.currencies_container.radio(
            label     = 'Convert all to currency',
            options   = currencies,
            index     = i,
            help      = 'Everything will be converted to selected currency',
            key       = ''.join(
                random.SystemRandom().choice(
                    string.ascii_uppercase +
                    string.ascii_lowercase +
                    string.digits
                ) for _ in range(10)
            )
        )



    def interact_benchmarks(self, benchmark=None):
        if self.benchmarks_container is None:
            self.benchmarks_container=streamlit.empty()
        else:
            self.benchmarks_container.empty()

        # Set the currency we'll be initialized with
        if benchmark:
            benchmarks=self.investor().benchmarks

            # Find the index of desired currency
            for i in range(len(benchmarks)):
                # streamlit.session_state.logger.log(f"testing {benchmarks[i]} against {benchmark}")
                if benchmarks[i]==benchmark:
                    break
        else:
            i = 0

        streamlit.session_state.interact_benchmarks_value=self.benchmarks_container.radio(
            label       = 'Select a benchmark to compare with',
            options     = self.investor().benchmarks,
            index       = i,
            format_func = lambda bench: str(bench['obj']),
            help        = 'Funds will be compared to the selected benchmark',
            key         = ''.join(
                random.SystemRandom().choice(
                    string.ascii_uppercase +
                    string.ascii_lowercase +
                    string.digits
                ) for _ in range(10)
            )
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
