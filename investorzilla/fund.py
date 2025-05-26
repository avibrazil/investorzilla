import datetime
import logging
import numpy
import pandas





class KPI(object):
    """
    A single class to hold KPI names.
    """

    # Source of all information
    BALANCE                 =  'balance'
    BALANCE_PREV            =  'balance_prev' # of previous period
    MOVEMENTS               =  'movements'
    DEPOSITS                =  'deposits'
    WITHDRAWALS             =  'withdrawals'
    LEDGER                  =  'ledger'

    # Cumulative movements
    SAVINGS                 =  'cumulative savings'

    # Rate of accumulated gains
    BALANCE_OVER_SAVINGS    =  'balance∶savings'

    # Pure gain, on the period or accumulated
    PERIOD_GAIN             =  'gain'   # on each period
    GAINS                   =  'cumulative gains'

    # Gain compared to withdrawal per period
    GAIN_MINUS_WITHDRAWAL   =  'gain excess after withdrawal' # gain-withdrawal
    GAIN_OVER_WITHDRAWAL    =  'gain consumption by withdrawal' # withdrawal/gain

    # Normalization features
    SHARE_VALUE             =  'share price'
    SHARES                  =  'shares'

    # Performance feature, wich is percentage change of share value
    RATE_RETURN             =  'rate of return'  # on each period

    # KPIs related to extenral sources as market indexes and benchmarks
    BENCHMARK               =  'benchmark index'
    BENCHMARK_RATE_RETURN   =  'benchmark rate of return'  # on each period
    BENCHMARK_EXCESS_RETURN =  'excess return'  # relation between RATE_RETURN and BENCHMARK_RATE_RETURN, on each period







class Fund(object):
    initialShareValue=100



    periodPairs={
        # Period formatters are documented here:
        # https://pandas.pydata.org/docs/reference/api/pandas.Period.strftime.html#pandas.Period.strftime

        # Pandas period strings are documented here:
        # https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#dateoffset-objects

        'hour of the day': dict(
            period                     = 'h',
            periodLabel                = 'hour of day',
            periodFormatter            = '{end:%H}',

            macroPeriod                = 'D',
            macroPeriodLabel           = 'day',
            macroPeriodFormatter       = '{end:%Y-%m-%d}'
        ),


        'part of the day': dict(
            period                     = '12h',
            periodLabel                = 'part of day',
            periodFormatter            = '{end:%p}',

            macroPeriod                = 'D',
            macroPeriodLabel           = 'day',
            macroPeriodFormatter       = '{end:%Y-%m-%d}'
        ),


        'day & week': dict(
            period                     = 'D',
            periodLabel                = 'day',
            periodFormatter            = '{end:%u·%a}',

            macroPeriod                = 'W',
            macroPeriodLabel           = 'week',
            macroPeriodFormatter       = '{start:%Y-%m-%d}/{end:%Y-%m-%d}'
        ),


        # Adjust to end
        'week & 4 weeks': dict(
            period                     = 'W',
            periodLabel                = 'week',

            macroPeriod                = '4W',
            macroPeriodLabel           = '4 week',
            macroPeriodFormatter       = '{start:%Y-%m-%d}/{end:%Y-%m-%d}'
        ),


        'month & year': dict(
            period                     = 'ME',
            periodLabel                = 'month',
            periodFormatter            = '{end:%m·%b}',

            macroPeriod                = 'YE',
            macroPeriodLabel           = 'year',
            macroPeriodFormatter       = '{end:%Y}'
        ),


        # Removing those two out of scene because of Pandas limitations
       # 'quarter & year': dict(
       #      period                     = 'Q',
       #      periodLabel                = 'quarter',
       #      periodFormatter            = 'Q{period:%q}',

       #      macroPeriod                = 'Y',
       #      macroPeriodLabel           = 'year',
       #      macroPeriodFormatter       = '{end:%Y}'
       #  ),


       #  'half month & month': dict(
       #      period                     = 'SM',
       #      periodLabel                = 'month half',
       #      # periodFormatter            = '%d',

       #      macroPeriod                = 'M',
       #      macroPeriodLabel           = 'month',
       #      macroPeriodFormatter       = '{end:%m}'
       #  ),


        # Adjust to end
        'year & 5 years': dict(
            period                     = 'YE',
            periodLabel                = 'year',
            # periodFormatter            = '%Y',

            macroPeriod                = '5Y',
            macroPeriodLabel           = '5 years',
            macroPeriodFormatter       = '{start:%Y}/{end:%Y}'
        ),


        # Adjust to end
        'year & decade': dict(
            period                     = 'YE',
            periodLabel                = 'year',
            # periodFormatter            = '%Y',

            macroPeriod                = '10Y',
            macroPeriodLabel           = 'decade',
            macroPeriodFormatter       = '{start:%Y}/{end:%Y}'
        )
    }



    formatters={
        'DEFAULT': dict(
            format="{:,.2f}"
        ),

        KPI.PERIOD_GAIN: dict(
            format="${:,.2f}",
            # summaryFormat='{}'
        ),

        KPI.GAINS: dict(
            format="${:,.2f}",
        ),

        KPI.BALANCE: dict(
            format="${:,.2f}",
        ),

        KPI.SAVINGS: dict(
            format="${:,.2f}",
        ),

        KPI.MOVEMENTS: dict(
            format="${:,.2f}",
        ),

        KPI.DEPOSITS: dict(
            format="${:,.2f}",
        ),

        KPI.WITHDRAWALS: dict(
            format="${:,.2f}",
        ),

        KPI.SHARE_VALUE: dict(
            format="${:,.2f}",
        ),

        KPI.RATE_RETURN: dict(
            format="{:,.2%}"
        ),

        KPI.GAIN_MINUS_WITHDRAWAL: dict(
            format="${:,.2f}",
        ),

        KPI.GAIN_OVER_WITHDRAWAL: dict(
            format="{:,.2%}"
        ),

        KPI.BENCHMARK_EXCESS_RETURN: dict(
            format="{:,.2%}"
        ),

        KPI.BENCHMARK_RATE_RETURN: dict(
            format="{:,.2%}"
        ),

        KPI.BALANCE_OVER_SAVINGS: dict(
            format="{:,.2%}"
        )
    }



    benchmarkFeatures=[
        KPI.BENCHMARK_EXCESS_RETURN,
        KPI.BENCHMARK_RATE_RETURN,
        KPI.BENCHMARK,
    ]



    ############################################################################
    ##
    ## Initialization and data standadization methods
    ##
    ############################################################################

    def __init__(
                self, ledger, balance, currencyExchange=None,
                needCurrencyConversion=True, name=None
        ):
        """
        Creates a virtual fund consolidating assets that appear on balance and
        ledger. Before consolidation, assets will be converted to currency
        from currencyExchange.

        Funds are usually created by Portfolio.getFund(). But a Fund can also
        be created by internal calls of Fund objects, such as
        Fund.makeAssetsFunds(). In this situation, ledger and balance will be
        already initialized and currency-converted, so a currencyExchange won't
        be passed. Initialized ledger and balance have columns with multiindex,
        so that is why we test nlevels==1.
        """
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        self.ledger=ledger
        if self.ledger.columns.nlevels==1:
            # Group all columns under a ‘ledger’ multi-index
            self.ledger = pandas.concat(
                [self.ledger.set_index(['asset','time']).sort_index()],
                axis=1,
                keys=[KPI.LEDGER]
            )

        self.balance=balance
        if self.balance.columns.nlevels==1:
            # Group all columns under a ‘balance’ multi-index
            self.balance = pandas.concat(
                [self.balance.set_index(['asset','time']).sort_index()],
                axis=1,
                keys=[KPI.BALANCE]
            )

        if currencyExchange is not None:
            # Configure a multi-currency converter engine
            self.exchange=currencyExchange
            self.currency=currencyExchange.target

            if needCurrencyConversion:
                # Homogenize all to same currency
                self.ledger  = self.convertCurrency(self.ledger)
                self.balance = self.convertCurrency(self.balance)

        # Compute number of shares and share value over time
        self.computeShares()

        # Date and time the fund begins and ends
        self.start=((self.shares[KPI.SHARES] != 0) | (self.shares[KPI.SHARE_VALUE] != 0)).idxmax()
        self.end=self.shares.tail(1).index.item()

        # Set a nice fund name based on its assets
        self.setName()



    def getAssetList(self):
        return list(self.balance.index.get_level_values(0).unique())



    def makeAssetsFunds(self):
        """
        For easier later computations, make a fund out of each asset overlooked
        by this fund and store them in self.asFund[{asset_name}]
        """
        self.asFund=dict()
        for asset in self.getAssetList():
            self.asFund[asset]=Fund(
                self.ledger[ self.ledger.index.get_level_values('asset') ==asset],
                self.balance[self.balance.index.get_level_values('asset')==asset],
                currencyExchange=self.exchange,
                needCurrencyConversion=False
            )



    def setName(self, name=None, top=3) -> str:
        """
        Set fund name and return it.

        If 0 < top < 1, set name based on instruments that contribute to the
        top% of the fund.

        If top is integer N, set name based on top N instruments.
        """

        # Set name based on instruments ordered by balance
        currentBalance=self.balance.groupby(level=0, observed=True).last()
        currentBalance.columns=currentBalance.columns.droplevel()
        currentBalance.sort_values(
            self.exchange.target,
            ascending=False,
            inplace=True
        )

        if name:
            self.name=name
            return self.name
        else:
            if top:
                if isinstance(top,float) and top < 1:
                    fundset=list(
                        currentBalance
                        .assign(
                            cum=currentBalance[self.exchange.target].cumsum()
                        )
                        .query("cum<{}".format(currentBalance[self.exchange.target].sum()*top))
                        .index
                    )
                elif (isinstance(top,float) or isinstance(top,int)) and top > 1:
                    fundset=list(
                        currentBalance
                        .head(top)
                        .index
                    )
            else:
                fundset=list(currentBalance.index)

            if len(fundset)<len(currentBalance.index):
                fundset.append('…')

            self.name=' ⋃ '.join(fundset) + ' @ ' + self.exchange.target

        return self.name



    def convertCurrency(self, df):
        # Working on KPI.LEDGER or KPI.BALANCE ?
        part=df.columns.get_level_values(0)[0]

        # Get list of currencies that need conversion
        toConvert=list(set(list(df.columns.get_level_values(1)))-{'comment'})

        ## Do not convert values already in target currency, will sum() them later
        sumCurrent=[]
        if self.exchange.target in toConvert:
            toConvert.remove(self.exchange.target)
            sumCurrent.append((part,self.exchange.target))

        # Create a working dataframe with our input df simply joined with
        # currency exchange data, using super powerful merge_asof()
        monetary=(
            # Join values with time-equivalent exchange rates
            pandas.merge_asof(
                # Remove fund level from index and sort by time
                df.reset_index('asset').sort_index(),

                # Add 'exchange' column level to exchange columns
                pandas.concat(
                    [self.exchange.data],
                    axis=1,
                    keys=['exchange']
                ),
                left_index=True, right_index=True
            )
            # Restore fund as an index in the original order
            .set_index('asset', append=True)
            .reorder_levels(['asset','time'])

            # Sort index by fund and time
            .sort_index()
        )

        # Result at this point is same ledger or balance with additional columns for
        # exchange rates. Now make currency conversion calculations...

        # Sum all converted and non-converted columns in one target column
        return (
            monetary.join(
                pandas.DataFrame(
                    columns=pandas.MultiIndex.from_tuples(
                        [('converted',self.exchange.target)]
                    ),
                    data=(
                        monetary.join(
                            # Result of concat is currency-converted columns from
                            # original values
                            pandas.concat(
                                [
                                    # Multiply values on each currency with its
                                    # converter in the exchange object
                                    monetary[[ (part,col) for col in toConvert ]]
                                    .droplevel(0, axis=1)
                                    .mul(
                                        monetary[[ ('exchange',col) for col in toConvert ]]
                                        .droplevel(0, axis=1)
                                    )
                                ],
                                axis=1,
                                keys=['converted from']
                            ),
                            how='inner'
                        )
                        [
                            # Select all converted columns
                            [ ('converted from',col) for col in toConvert ] +

                            # Add the might-not-exist column that already was in target
                            # currency and won't need conversion
                            sumCurrent
                        ]
                        .sum(axis=1)
                    )
                ),
                how='inner'
            )

            # Remove columns we won't need anymore
            .drop(
                columns=(
                    # list of converted currencies
                    [ (part,col) for col in toConvert ] +

                    # list of exchange currencies
                    [ ('exchange',col) for col in self.exchange.data.columns ] +

                    # currency that was incorporated without being converted because is
                    # the same as the target currency
                    sumCurrent
                )
            )

            # Rename 'converted' to 'ledger' or 'balance
            .rename(columns={'converted': part})
        )



    def computeShares(self, initialShareValue=initialShareValue):
        """
        Compute internal self.shares DataFrame which is a time series with
        number of shares and share value.

        Number of shares change when there is ledger activity, meaning there was
        money manually added or removed from fund.

        Value of the share changes when balance changes because of interest.
        """
        self.initialShareValue=initialShareValue

        shares=0
        share_value=0

        shares_evolution=[]

        assets=self.ledger.index.get_level_values(0).unique()

        # Handle Balance by combining/summing all balances
        combinedBalance=None
        if len(assets)>1:
            combinedBalance=(
                self.balance

                ## Put balance of each asset in a different column,
                ## repeat value for empty times and fillna(0) for first empty
                ## values
                .dropna()
                .unstack(level=0)
                .ffill()

                ## Combined balance is the sum() of balances of all assets at
                ## each point in time
                .sum(axis=1)
                .where(lambda s: s!=0)
                .dropna()
                # .sort_index()
            )

            ## Eliminate all consecutive repeated values
            # combinedBalance=combinedBalance.loc[combinedBalance.shift()!=combinedBalance]

            ## Make it a compatible DataFrame
            combinedBalance=pandas.DataFrame(combinedBalance)
            combinedBalance.columns=pandas.MultiIndex.from_tuples([(KPI.BALANCE,self.exchange.target)])

        else:
            combinedBalance=self.balance.droplevel(0)

        # Handle Ledger by simply sorting by time the movements of all assets
        theShares=(
            self.ledger

            # Flatten and rearrange comment column
            .assign(comment=lambda table: table[(KPI.LEDGER,'comment')])
            .drop(columns=(KPI.LEDGER,'comment'))

            # Move asset name from index into a regular column
            .reset_index(0)

            # Get rid or NaNs
            .dropna(how='all')

            # Join the cleaned ledger with the cleaned balance
            .join(
                combinedBalance,
                how='outer',
                sort=True
            )

            # Get rid of currency column name
            .droplevel(1, axis=1)
        )

        # self.logger.debug(theShares.head().to_markdown())

        # Convert movements and balances into shares and share value
        for time,row in theShares.iterrows():

            # First adjust NUMBER OF SHARES if there was any movement
            if not pandas.isna(row[KPI.LEDGER]):
                if share_value!=0:
                    # If fund was already initialized
                    shares += row[KPI.LEDGER]/share_value
                    shares = round(shares,12)
                elif shares==0:
                    # If fund was not initialized yet
                    share_value = initialShareValue
                    shares = row[KPI.LEDGER]/share_value


            # Second, adjust the VALUE OF A SHARE based on new balance
            if not pandas.isna(row[KPI.BALANCE]):
                if shares==0:
                    if len(shares_evolution)==0:
                        # The rare situation where we have balance before any
                        # movement
                        share_value = initialShareValue
                        shares = row[KPI.BALANCE]/share_value
                    elif row[KPI.BALANCE]!=0:
                        # The even more rare situation where interest arrives
                        # after an existing balance became zero. So we have
                        # a share_value but no shares. Interests affect
                        # share_value while ledger movements affect number of
                        # shares. But here we'll have to fabricate shares to
                        # be able to express some balance. Result will be an
                        # artificially huge increase in share_value.
                        shares = 0.01
                        share_value = row[KPI.BALANCE]/shares
                else:
                    share_value = row[KPI.BALANCE]/shares

            shares_evolution.append(
                (time,shares,share_value,row.asset,row.comment)
            )

        self.shares=(
            pandas.DataFrame.from_records(
                shares_evolution,
                columns=('time',KPI.SHARES,KPI.SHARE_VALUE,'asset','comment')
            )
            .set_index('time')
        )



    ############################################################################
    ##
    ## Reporting methods
    ##
    ############################################################################

    def filter(
                report: pandas.DataFrame,
                timeSortAscending=False,
                kpi=benchmarkFeatures + [
                    KPI.RATE_RETURN,   KPI.PERIOD_GAIN,   KPI.BALANCE,
                    KPI.SAVINGS,       KPI.MOVEMENTS,     KPI.SHARES,
                    KPI.SHARE_VALUE
                ],
        ):
        """
        Filter the report (as returned by report()) and returns only the KPIs
        in the list.
        """
        return (
            report.loc[
                # All time segments (slice(None)) but only desired KPIs, all columns
                (slice(None),pandas.Index(kpi, name='KPI')), :
            ]

            # KPIs came in correct order but time is a mess, so reorder the
            # time axis
            .sort_index(
                level='time',
                ascending=timeSortAscending,
                sort_remaining=False
            )
        )



    def format(report: pandas.DataFrame, output='styled', flatPeriodFirst=True):
        """
        Makes the output of report() more readable.

        Output can be:
        - styled (default): returns a pandas.styler object with nice number
            formatting, red negative numbers and multi-index structure.

        - plain: returns a plain pandas.DataFrame ready for further data
            analysis.

        - flat_unformatted: as plain but all values are converted to text.

        - flat: returns a pandas.DataFrame with hard number formatting (all is
            converter to text after formatting) and flattened multi-indexes for
            limited displays as Streamlit.
        """
        if output=='plain':
            ## Just return the Dataframe with raw numeric values
            return report

        if output=='flat' or output=='flat_unformatted':
            ## Convert all to object to attain more flexibility per cell
            out=report.astype(object)

            if output=='flat_unformatted':
                return out

        if output=='styled':
            ## Lets work with a styled DataFrame. Best and default output type.
            out=(
                report.style
                .apply(lambda cell: numpy.where(cell<0,"color: red",None), axis=1)
            )

        # Since we want results styled or pre-formatted (to overcome Streamlit bugs) and
        # not plain (just the data), we'll have to apply formatting, either as style or
        # hardcoded (in case of flat).


        defaultFormat=None
        if 'DEFAULT' in Fund.formatters:
            defaultFormat=Fund.formatters['DEFAULT']

        # Work only in available KPIs
        for i in report.index.get_level_values('KPI').unique():
            for g in ['periods', 'summary of periods']:
                # Select formatter for KPI

                f=defaultFormat['format']
                if g=='summary of periods' and 'summaryFormat' in defaultFormat:
                    f=defaultFormat['summaryFormat']

                if i in Fund.formatters:
                    if g=='summary of periods' and 'summaryFormat' in Fund.formatters[i]:
                        f=Fund.formatters[i]['summaryFormat']
                    else:
                        f=Fund.formatters[i]['format']


                selector=pandas.IndexSlice[
                    # Apply format in KPI row
                    pandas.IndexSlice[:,i],

                    # Apply style in «periods» or «summary of periods»
                    pandas.IndexSlice[g,:]
                ]

                if output=='flat':
                    out.loc[selector]=out.loc[selector].apply(
                        lambda s: [f.format(x) for x in s]
                    )
                    out.loc[selector]=out.loc[selector].replace('$nan','')
                elif output=='styled':
                    # Styler advanced slicing only works in Pandas>=1.3
                    out=out.format(formatter=f, subset=selector, na_rep='')

        if output=='styled':
            # Styled report is ready to go
            return out

        # Final cleanup for flat
        out.replace(['nan','nan%'],'', inplace=True)
        if flatPeriodFirst:
            out.index=['·'.join((p,k)).strip() for (p,k) in out.index.values]
        else:
            out.index=['·'.join((k,p)).strip() for (p,k) in out.index.values]
        level=out.loc[:,pandas.IndexSlice['summary of periods',:]].columns.values[0][1]
        out.rename(columns={level:'summary of periods'},inplace=True)
        out.columns=out.columns.droplevel(0)

        return out



    def report(self,
                period='month & year',
                benchmark=None,
                start=None,
                end=None,
                tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo,
                precomputedPeriodicReport=None,
                precomputedMacroPeriodicReport=None,
        ):
        """
        Joins 2 periodicReports() to get a complete report with periods
        and summary of periods. For example, period='month & year'
        computes KPIs for each month aligned with the summary of 12
        months (an year).

        If precomputed* are passed, they'll be used and there must be full
        compatibility between them and the other parameters.

        Result is a structured and readable report organized as financial
        institutions use to show mutual funds performance reports.

        The output of report() can be improved for readability by format() and
        KPIs filtered by filter(), so same report() output can be reused without
        recomputing.
        """

        def ddebug(table):
            display(table)
            return table

        # Find period structure
        try:
            p = self.periodPairs[period]
        except KeyError:
            raise KeyError(
                "Period pair must be one of: {}".format(
                    str(Fund.getPeriodPairs())
                )
            )


        # How many periods fit in a macroPeriod ?
        periodsInSummary = Fund.div_offsets(p['macroPeriod'],p['period'])

        # Get detailed part of report with period data
        periodOffset = pandas.tseries.frequencies.to_offset(p['period'])
        if precomputedPeriodicReport is not None:
            period = precomputedPeriodicReport
        else:
            period = self.periodicReport(
                period     = p['period'],
                benchmark  = benchmark,
                start      = start,
                end        = end,
                tz         = tz
            )

        # Get summary part report with summary of a period set
        macroPeriodOffset = pandas.tseries.frequencies.to_offset(p['macroPeriod'])
        if precomputedMacroPeriodicReport is not None:
            macroPeriod = precomputedMacroPeriodicReport
        else:
            macroPeriod = self.periodicReport(
                period     = p['macroPeriod'],
                benchmark  = benchmark,
                start      = start,
                end        = end,
                tz         = tz
            )


        report=None

        # KPI income has a special formatter
        if KPI.PERIOD_GAIN in self.formatters:
            incomeFormatter=self.formatters[KPI.PERIOD_GAIN]['format']
        else:
            incomeFormatter=self.formatters['DEFAULT']['format']

        # Break the periodic report in chunks equivalent to the summary report
        for i in range(len(macroPeriod.index)):
            macroPeriodPrev=macroPeriod.index[i] - macroPeriodOffset
            macroPeriodCurr=macroPeriod.index[i]

            if i==0:
                # Process first line, usually prepending NaNs
                line=period[:macroPeriodCurr.end_time]
                nPeriods=line.shape[0]

                completeMe = int(periodsInSummary - nPeriods)

                if completeMe > 0:
                    # First line in report use to need leading empty
                    # periods if they start in the middle of macro period
                    line=(
                        pandas.concat(
                            [
                                # Preppend empty lines from a DataFrame that has
                                # only a useful index
                                pandas.DataFrame(
                                    index=pandas.period_range(
                                        start=line.index[0]-completeMe,
                                        periods=completeMe
                                    )
                                ),
                                line
                            ]
                        )
                        # .pipe(
                        #     lambda table: table[
                        #         (table.index > macroPeriodPrev.end_time) &
                        #         (table.index <= macroPeriodCurr.end_time)
                        #     ]
                        # )
                    )

                    nPeriods=line.shape[0]
            else:
                # Process lines that are not the first
                # currentRange=(
                #     (period.index.start_time >= macroPeriodCurr.start_time) &
                #     (period.index.end_time   <= macroPeriodCurr.end_time)
                # )
                line=period[macroPeriodCurr.start_time:macroPeriodCurr.end_time]
                nPeriods=line.shape[0]

            # Add a row label, as '2020' or '4·Thu' or '2022-w25'
            line=(
                ## Add the time index of the summary report as an additional
                ## index level to columns
                pandas.concat([line], axis=1, keys=[macroPeriod.index[i]])

                ## Rename the title for labels so we can join latter
                .rename_axis(['time','KPI'], axis='columns')

                ## Convert index from full PeriodIndex to something that can
                ## be matched across macro-periods, as just '08·Aug'
                .assign(
                    **{
                        p['periodLabel']: lambda table: (
                            # Fill with a reformatted index or a plain range
                            (
                                pandas.Series(table.index, index=table.index)
                                .apply(
                                    lambda cell: (
                                        p['periodFormatter']
                                        .format(
                                            start    = cell.start_time,
                                            end      = cell.end_time,
                                            period   = cell
                                        )
                                    )
                                )
                                # .pipe(ddebug)
                            ) if 'periodFormatter' in p
                            else range(1,nPeriods+1,1)
                        ),
                        '': 'periods',
                    }
                )
                .set_index(['',p['periodLabel']])
            )

            # Add to main report transposing it into a true row (we were
            # columns until now)
            report=(
                pandas.concat([report, line.T]) #, sort=True)
                if report is not None
                else line.T
            )

            # Make the 'income' value of summary report the average multiplied
            # by number of periods
        #             if KPI.PERIOD_GAIN in kpi:
        #                 macroPeriod.loc[macroPeriod.index[i],'new ' + KPI.PERIOD_GAIN]='{n} × {inc}'.format(
        #                     n=nPeriods,
        #                     inc=incomeFormatter.format(
        #                         macroPeriod.loc[macroPeriod.index[i],KPI.PERIOD_GAIN]/nPeriods
        #                     )
        #                 )

        #         if KPI.PERIOD_GAIN in kpi:
        #             macroPeriod[KPI.PERIOD_GAIN]=macroPeriod['new ' + KPI.PERIOD_GAIN]

        # Turn summary report into a column, sort and name labels for perfect join
        report[('summary of periods',p['macroPeriodLabel'])] = (
            macroPeriod
            .rename_axis(columns='KPI')
            .T
            .stack()
            .reorder_levels(['time','KPI'])
            .sort_index()
        )

        return (
            report

            # Reformat line index from a full PeriodIndex into something more
            # readable
            .pipe(
                lambda table:
                    table.set_index(
                        pandas.MultiIndex.from_tuples(
                            [
                                (
                                    (
                                        p['macroPeriodFormatter']
                                        .format(
                                            start=x[0].start_time,
                                            end=x[0].end_time,
                                            period=x[0]
                                        )
                                    ),
                                    x[1]
                                )
                                for x in report.index
                            ],
                            name=['time','KPI']
                        )
                    )
            )
        )



    def periodicReport(self, period=None, benchmark=None, start=None, end=None,
            tz=datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo):
        """
        This is the most important summarization and reporting method of the
        class. Returns a DataFrame with features as rate of return, income,
        balance, shares, share_value, benchmark rate of return, excess return
        compared to benchmark.

        period: Either 'M' (monthly), 'Y' (yearly), 'W' (weekly) to aggregate
        data for these periods. If not passed, returned dataframe will be a
        ragged time series as granular and precise as the amount of data
        available.

        benchmark: A MarketIndex object to use a performance indicator used to
        compute benchmark rate of return and excess return. Features are
        omitted and not computed if this objected is not passed.

        start: A starting date for the report. Makes benchmark rate of return
        start at value 1 on this date. Starts at beginning of data if this is
        None.

        end: Cut data up to this time

        tz: A time zone to convert all data. Uses local time zone if omited.
        """

        errorMsg=(
            '{par} parameter must be of type Pandas Timestamp, or a string '
            'compatible with pandas.Timestamp.fromisoformat(), but got '
            '"{value}" of type {type}.'
        )

        # Chronological index where data begins to be non-zero
        startOfReport=self.start.tz_convert(tz)

        if (start is not None) or (end is not None):
            params=dict(
                start=start,
                end=end
            )

            for p in params:
                if params[p] is not None:
                    # Check if text was passed then convert it to datetime
                    if isinstance(params[p],str):
                        params[p]=pandas.Timestamp.fromisoformat(params[p])
                    elif isinstance(params[p],datetime.date):
                        params[p]=pandas.Timestamp(params[p])

                    # Check if usable object
                    if not isinstance(params[p],pandas.Timestamp):
                        raise TypeError(
                            errorMsg.format(
                                par=p,
                                value=params[p],
                                type=type(params[p])
                            )
                        )

                    # End date is actually last nanosecond of that date
                    if p=='end':
                        params[p]=params[p].to_period('D').to_timestamp(how="end")

                    # Make it timezone-aware
                    if params[p].tzinfo is None:
                        params[p]=params[p].tz_localize(tz)

            start=params['start']
            end=params['end']

            # Now see if start time is more recent than the beginning of
            # our data, and use it
            if start and start > startOfReport:
                startOfReport=start

        self.logger.debug(f'Report period: {start} → {end}')
        self.logger.debug(f'Fund period: {self.start} → {self.end}')

        report=(
            # Start fresh
            self.shares

            # Add ledger to get movements for period
            .join(
                self.ledger

                # Remove columns that we already have in shares DF

                # Remove asset name
                .droplevel(0)

                # Remove user comment
                .drop(('ledger','comment'),axis=1)

                # Remove column names
                .droplevel(1, axis=1)

                # Rename remaining column to what it really is
                .rename(columns=dict(ledger=KPI.MOVEMENTS))

                # Sort by time
                .sort_index(), #[startOfReport:end]
                how='left'
            )

            .assign(
                **{
                    KPI.MOVEMENTS: lambda table: table[KPI.MOVEMENTS].fillna(0),

                    KPI.DEPOSITS: lambda table: (
                        table[KPI.MOVEMENTS]
                        .where(table[KPI.MOVEMENTS]>0)
                        .fillna(0)
                    ),

                    KPI.WITHDRAWALS: lambda table: (
                        table[KPI.MOVEMENTS]
                        .where(table[KPI.MOVEMENTS]<0)
                        .fillna(0)
                    ),

                    # Add balance as a function of shares
                    KPI.BALANCE: lambda table: (
                        table[KPI.SHARES] *
                        table[KPI.SHARE_VALUE].ffill()
                    ),

                    # Add cumulated savings (cumulated movements)
                    KPI.SAVINGS: lambda table: (
                        table[KPI.MOVEMENTS]
                        .cumsum()
                        .ffill()
                    ),

                    # Add balance over savings
                    KPI.BALANCE_OVER_SAVINGS: lambda table: (
                        table[KPI.BALANCE] /
                        table[KPI.SAVINGS]
                    ),

                    # Add cumulative income
                    KPI.GAINS: lambda table: table[KPI.BALANCE]-table[KPI.SAVINGS]
                }
            )

            # Convert all to desired timezone which is probably local timezone
            .pipe(lambda table: table.set_index(table.index.tz_convert(tz)))

            # Cut the report just before period-aggregation operation
            [startOfReport:end]
        )

        # On a downsample scenario (e.g. period=Y), we'll have more fund
        # data than final report.
        # On an upsample scenario (e.g. period=D), we'll have more report
        # lines than fund data.
        # If period=None, number of report lines will match the amount of
        # fund data we have.
        # These 3 situations affect how benchmark needs to be handled.

        # Add 3 benchmark-related features
        benchmarkFeatures=[]
        benchmarkAggregation=dict()
        if benchmark is not None:
            # Pair with Benchmark
            report=pandas.merge_asof(
                report,
                (
                    benchmark
                    .getData()
                    .pipe(lambda table: table.set_index(table.index.tz_convert(tz)))
                    [['value']]
                    .rename(columns={'value': KPI.BENCHMARK})
                ),
                left_index=True,
                right_index=True
            )

            benchmarkFeatures=self.benchmarkFeatures
            benchmarkAggregation={KPI.BENCHMARK: 'last'}


        if period is not None:
            # Make it a regular time series (D, M, Y etc), each column
            # aggregated by different strategy

            # Day 0 for Pandas is Monday, while it is Sunday for Python.
            # Make Pandas handle day 0 as Sunday.
            # dateOffset=(
            #     pandas.tseries.offsets.Week(weekday=5)
            #     if period=='W'
            #     else period
            # )
            dateOffset = period

            # End of period is the last nanosecond of that period, not the
            # beginning of the last day
            # periodShift=(
            #     pandas.tseries.frequencies.to_offset(period).nanos-1
            #     if Fund.div_offsets(period,'D') < 1
            #     else pandas.tseries.frequencies.to_offset('D').nanos-1
            # )

            report=(
                report

                .resample(
                    rule=dateOffset,
                    kind='period',
                    label='right'
                )

                # Compute summarizations for each KPI
                .agg(
                    dict(
                        **{
                            # KPIs that prevail last value on aggregations
                            kpi: 'last'
                            for kpi in [
                                KPI.SHARES,
                                KPI.SHARE_VALUE,
                                KPI.BALANCE,
                                KPI.SAVINGS,
                                KPI.BALANCE_OVER_SAVINGS,
                                KPI.GAINS,
                            ]
                        },

                        **{
                            # KPIs which aggregations should be summed
                            kpi: 'sum'
                            for kpi in [
                                KPI.MOVEMENTS,
                                KPI.DEPOSITS,
                                KPI.WITHDRAWALS,
                            ]
                        },

                        **benchmarkAggregation
                    )
                )

                # .to_period()

                # We want timestamps on end of each period, not in the
                # begining as Pandas defaults
                # .reset_index()
                # .assign(
                #     time=lambda table: (
                #         table.time +
                #         pandas.Timedelta(nanoseconds=periodShift)
                #     )
                # )
                # .set_index('time')

                # Fill the gaps after aggregation
                .ffill()
            )

            ledgerColumns=[]
        else:
            # Lack of aggregation will not get rid of these columns, so
            # handle them nicely in the output
            ledgerColumns=['asset','comment']

        # Compute rate of return (pure gain excluding movements)
        report[KPI.RATE_RETURN]=report[KPI.SHARE_VALUE].pct_change().fillna(0)

        # The pct_change() above yields ∞ or NaN at the first line, so fix
        # it manually
        report.loc[report.index[0],KPI.RATE_RETURN]=(
            (
                report.loc[report.index[0],KPI.SHARE_VALUE] /
                self.shares[KPI.SHARE_VALUE].asof(startOfReport)
            ) - 1
        )

        # Compute gain per period comparing consecutive Balance and excluding
        # Movements
        report=report.join(
            report[KPI.BALANCE].shift(),
            rsuffix='_prev',
            sort=True
        )

        # shift() yields NaN for first position, so fix it
        if startOfReport==self.start:
            # Balance is always Zero before the fund ever existed
            report.loc[report.index[0],KPI.BALANCE_PREV]=0
        else:
            # Compute Balance based on immediate previous data

            wayBefore=startOfReport-pandas.Timedelta(seconds=1)
            report.loc[report.index[0],KPI.BALANCE_PREV]=(
                self.shares[KPI.SHARE_VALUE].asof(wayBefore) *
                self.shares[KPI.SHARES].asof(wayBefore)
            )

        # report[KPI.PERIOD_GAIN]=report.apply(
        #     lambda x: (
        #         # Balance of current period
        #         x[KPI.BALANCE]

        #         # Balance of previous period
        #         -x[KPI.BALANCE_PREV]

        #         # Movements of current period
        #         -x[KPI.MOVEMENTS]
        #     ),
        #     axis=1
        # )

        report=report.assign(**{
            # Compute income as the difference of Balance between consecutive
            # periods, minus Movements of period
            KPI.PERIOD_GAIN: lambda table:
                table.apply(
                    lambda row: (
                        # Balance of current period
                        row[KPI.BALANCE]

                        # Balance of previous period
                        -row[KPI.BALANCE_PREV]

                        # Movements of current period
                        -row[KPI.MOVEMENTS]
                    ),
                    axis=1
                ),

            # Gain excess over withdrawal
            KPI.GAIN_MINUS_WITHDRAWAL: lambda table: table.apply(
                lambda row: (
                    row[KPI.PERIOD_GAIN]+row[KPI.MOVEMENTS]
                    if row[KPI.MOVEMENTS]<0
                    else None
                ),
                axis=1
            ),

            # Withdrawals consumption of gains
            KPI.GAIN_OVER_WITHDRAWAL: lambda table: table.apply(
                lambda row: (
                    abs(row[KPI.MOVEMENTS])/row[KPI.PERIOD_GAIN]
                    if row[KPI.MOVEMENTS]<0 and row[KPI.PERIOD_GAIN]!=0
                    else None
                ),
                axis=1
            ),
        })

        # Compute features that depend on Benchmark
        if benchmark is not None:
            # Compute benchmark growth
            report[KPI.BENCHMARK_RATE_RETURN]=report[KPI.BENCHMARK].pct_change()

            # The pct_change() above yields ∞ at the first line, so fix it manually
            report.loc[report.index[0],KPI.BENCHMARK_RATE_RETURN]=(
                (
                    report.loc[report.index[0],KPI.BENCHMARK] /
                    benchmark.getData()['value'].asof(startOfReport)
                ) - 1
            )

            # Compute fund excess growth over benchmark
            report[KPI.BENCHMARK_EXCESS_RETURN]=(
                report[KPI.RATE_RETURN] -
                report[KPI.BENCHMARK_RATE_RETURN]
            )

            # Normalize benchmark making it start with value 1
            report[KPI.BENCHMARK] /= report.loc[report.index[0]][KPI.BENCHMARK]
        
        return report[
            benchmarkFeatures + [
                KPI.RATE_RETURN,
                KPI.PERIOD_GAIN,
                KPI.BALANCE,
                KPI.SAVINGS,
                KPI.BALANCE_OVER_SAVINGS,
                KPI.GAINS,
                KPI.MOVEMENTS,
                KPI.DEPOSITS,
                KPI.WITHDRAWALS,
                KPI.GAIN_MINUS_WITHDRAWAL,
                KPI.GAIN_OVER_WITHDRAWAL,
                KPI.SHARES,
                KPI.SHARE_VALUE
            ] +
            ledgerColumns
        ]



    ############################################################################
    ##
    ## Data visualization
    ##
    ############################################################################

    def performancePlot(self,
                benchmark=None,
                start=None,
                end=None,
                type='pyplot',
                precomputedReport=None
            ):
        """
        A line plot with acumulated return rate compared with a benchmark
        """
        if benchmark.currency!=self.currency:
            self.logger.warning(f"Benchmark {benchmark.id} has a different currency; comparison won't make sense")

        if precomputedReport is not None:
            report=precomputedReport
        else:
            report=self.periodicReport(
                benchmark=benchmark,
                start=start,
                end=end
            )

        return (
            report

            # Normalize share_value to make it start on value 1
            .assign(
                **{
                    KPI.SHARE_VALUE: lambda table: (
                        table[KPI.SHARE_VALUE]/table[KPI.SHARE_VALUE].iloc[0]
                    )
                }
            )
            [[KPI.SHARE_VALUE, KPI.BENCHMARK]]

            # Rename columns for plotting
            .rename(
                columns={
                    KPI.SHARE_VALUE: str(self),
                    KPI.BENCHMARK: str(benchmark)
                }
            )

            # Decide what to return
            .pipe(
                lambda table: (
                    table.plot(kind='line')
                    if type=='pyplot'
                    else table
                )
            )
        )



    def wealthPlot(self,
                benchmark,
                start=None,
                end=None,
                type='pyplot',
                precomputedReport=None
            ):
        """
        A plot with 3 lines: balance, savings and the difference between them
        (the cumulated gains).
        """
        if precomputedReport is not None:
            report=precomputedReport
        else:
            report=self.periodicReport(
                benchmark=benchmark,
                start=start,
                end=end
            )

        return (
            report

            [[KPI.BALANCE,KPI.SAVINGS,KPI.GAINS]]

            # Decide what to return
            .pipe(
                lambda table: (
                    table.plot(kind='line')
                    if type=='pyplot'
                    else table
                )
            )
        )



    def rateOfReturnPlot(self,
                period='M',
                start=None,
                end=None,
                type='pyplot',
                precomputedReport=None,
            ):
        """
        The distribution (histogram) of rate of returns as a plot.

        Parameters
        ----------
        period : str, optional
            The name of the period, such as 'M', '12H', 'W', to pass to
            periodicReport()
        start : optional
            Time when data starts, to pass to periodicReport()
        end : optional
            Time when data ends, to pass to periodicReport()
        type : str, optional
            Type of output. Can be raw (a plain DataFrame), pyplot or altair
        precomputedReport: pandas.DataFrame, optional
            Pass the output of a previously computed periodicReport() here. The
            periodic report will be computed by this method otherwise.
        """

        value_name='rate of return %, frequency per period'

        if precomputedReport is not None:
            data=precomputedReport
        else:
            data=self.periodicReport(
                period=period,
                start=start,
                end=end
            )

        data=(
            data
            [[KPI.SHARE_VALUE]]
            .pct_change()
            .replace([numpy.inf, -numpy.inf], numpy.nan)
            .dropna()
            .rename(
                columns={
                    KPI.SHARE_VALUE: value_name
                }
            )
        )

        if type=='raw':
            return data

        # Doesn´t make sense to compute this chart if not enough data, but
        # UI will break otherwise, so let it pass anyway.
        # if data.shape[0]<=1:
        #     return None

        data=data*100
        bins=int(data.shape[0]/10)

        # Handle rate of return as a gaussian distribution
        μ=data.mean().iloc[0]
        σ=data.std().iloc[0]

        if type=='pyplot':
            return data.plot(
                kind='hist',
                bins=bins,
                xlim=(μ-2*σ,μ+2*σ)
            ).get_figure()

        if type=='altair':
            import altair

            hist = (
                altair.Chart(data)
                .mark_bar()
                .encode(
                    x = altair.X(
                        value_name,
                        bin = altair.BinParams(maxbins = max(2,bins))
                    ),
                    y = 'count()'
                )
            )

            return hist



    def genericPeriodicPlot(self,
                kpi=KPI.RATE_RETURN,
                periodPair='month & year',
                start=None,
                end=None,
                type='pyplot',
                precomputedReport=None,
            ):
        """
        Put the KPI per period in a bar chart with time on X axis. Add moving
        average and moving median on the macro period.
        """
        p=self.periodPairs[periodPair]

        periodCountInMacroPeriod = Fund.div_offsets(p['macroPeriod'],p['period'])


        # Now compute moving averages

        if precomputedReport is None:
            data=self.periodicReport(period=p['period'], start=start, end=end)
        else:
            data=precomputedReport


        label_moving_average = '{} {}s MA'.format(
            periodCountInMacroPeriod,
            p['periodLabel']
        )

        label_moving_median = '{} {}s MM'.format(
            periodCountInMacroPeriod,
            p['periodLabel']
        )

        report=(
            data
            [[kpi]]
            .assign(
                **{
                    label_moving_average: lambda table: (
                        table[kpi]
                        .rolling(periodCountInMacroPeriod, min_periods=1)
                        .mean()
                    ),
                    label_moving_median: lambda table: (
                        table[kpi]
                        .rolling(periodCountInMacroPeriod, min_periods=1)
                        .median()
                    )
                }
            )
        )

        if type=='raw':
            return report

        if type=='pyplot':
            gains=(
                report
                .reset_index()
                .assign(
                    time=lambda table: table.time.astype(str)
                )
                .set_index('time')
            )
            ax=gains[[kpi]].plot.bar(color='blue',figsize=(20,10))
            ax=gains[[label_moving_average]].plot.line(color='red',ax=ax)
            ax=gains[[label_moving_median]].plot.line(color='green',ax=ax)

            return ax.get_figure()

        if type=='altair':
            import altair

            colors=['blue', 'red', 'green', 'cyan', 'yellow', 'brown']
            color=0

            rollingAggregations=list(report.columns)
            rollingAggregations.remove(kpi)

            base = (
                altair.Chart(
                    report

                    # Altair won't handle Period objects correctly, thus convert
                    # our index into regular Timestamps.
                    .to_timestamp(how='end')
                    .reset_index()
                )
                .encode(
                    x='time',
                )
            )
            bar = base.mark_bar(color=colors[color]).encode(y=kpi)
            color+=1

            for r in rollingAggregations:
                bar += base.mark_line(color=colors[color]).encode(y=r)
                color+=1

            shades = (
                pandas.DataFrame(
                    report

                    # Make Pandas stop complaining about Period resampling
                    .to_timestamp(how='end')

                    # The bigger blocks of our report
                    .resample(p['macroPeriod'])

                    # Aggregate by whatever just to get a real DataFrame
                    .last()

                    # Get only the index
                    .index

                    # Back to the convenient Period object
                    .to_period()

                    # Every other period
                    [::2]
                )
                .assign(
                    start=lambda table: table.time.apply(lambda cell: cell.start_time),
                    end=lambda table: table.time.apply(lambda cell: cell.end_time),
                )
                .drop(columns='time')
            )

            # Add shades for every other macro-period (eg. Y, 4W) for better
            # visualization of group of periods (eg. M, W)
            bar += (
                altair.Chart(shades)
                .mark_rect(opacity=0.05)
                .encode(
                    x=altair.X('start', title=''),
                    x2=altair.X2('end', title=''),
                    color=altair.ColorValue('black')
                )
            )

            return bar



    def assetContributionPlot(self,
                pointInTime,
                kpi=KPI.PERIOD_GAIN,
                period='M',
                type='altair',
                top=5,
                precomputedReport=None
            ):
        """
        A waterfall bar plot showing contribution of each asset to the final
        result in that specific pointInTime.

        pointInTime must be a string compatible with period.

        So if period='M' (monthly periods), a compatible pointInTime can be
        '2023-12'.
        """

        if not hasattr(self,'asFund'):
            self.makeAssetsFunds()

        # Make one giant report joining all reports from all internal assets
        report = pandas.concat(
            [
                # This concat is just to add an axis level to the periodicReport
                pandas.concat(
                    [
                        self.asFund[f].periodicReport(period)
                    ],
                    axis=1,
                    keys=[f]
                )
                for f in list(self.asFund.keys())
            ],
            axis=1
        )

        # Now select and organize the contribution of each asset to the final
        # TOTAL. Only top (argument) number of assets will be showed, all other
        # assets will be aggregated into MINOR ASSETS. Final result is a table
        # like:
        # |    | Asset        |      {kpi} |
        # |---:|:-------------|-----------:|
        # |  0 | MINOR ASSETS |    9608.54 |
        # |  4 | Asset 1      |  -56136    |
        # |  3 | Asset 2      |   81159.8  |
        # |  2 | Asset 3      |  124309    |
        # |  1 | Asset 4      | -138660    |
        # |  0 | Asset 5      | -148350    |
        # |  0 | TOTAL        | -128068    |

        contributions = (
            report
            .swaplevel(0, 1, 1)
            .sort_index()
            .sort_index(axis=1)

            # Fill the blanks according to each KPI semantic
            .assign(
                **{
                    # Dict comprehension didn't work because of variable into lambda
                    KPI.BALANCE:              lambda table: table[KPI.BALANCE].ffill(),
                    KPI.BALANCE_OVER_SAVINGS: lambda table: table[KPI.BALANCE_OVER_SAVINGS].ffill(),
                    KPI.SAVINGS:              lambda table: table[KPI.SAVINGS].ffill(),
                    KPI.GAINS:                lambda table: table[KPI.GAINS].ffill(),
                    KPI.SHARE_VALUE:          lambda table: table[KPI.SHARE_VALUE].ffill(),
                    KPI.SHARES:               lambda table: table[KPI.SHARES].ffill(),
                }
            )
            # .fillna(0)

            # Get only the desired KPI
            [[kpi]]

            # Reorg
            .T

            # Get only the desired period
            [[pointInTime]]

            # Rename columns and make others
            .assign(
                **{
                    kpi: lambda table: table[pointInTime],
                    "abs": lambda table: table[kpi].abs()
                }
            )

            # Drop old column because of undesired name
            .pipe(
                lambda table: table.drop(columns=table.columns[0])
            )

            # Remove old columns spirit
            .rename_axis(columns=None)

            # Drop index level not used anymore
            .droplevel(0)

            # Assets column with correct name
            .rename_axis("Asset")
            .reset_index()

            # Eliminate useless values
            .dropna()
            .query(f"`{kpi}`.abs() > 0")

            # Order by KPI relevance
            .sort_values('abs',ascending=False)
            .reset_index(drop=True)

            # Mark less relevant assets to be aggregated
            .reset_index(names='rankk')
            .assign(
                agg=lambda table: table.apply(
                    lambda row: True if row.rankk>=top else False,
                    axis=1
                )
            )

            .pipe(
                lambda table: pandas.concat(
                    [
                        # Aggregate less relevant assets into a virtual MINOR ASSETS
                        pandas.DataFrame(table.query('agg == True').sum())
                        .T
                        .assign(
                            Asset='AGGREGATED MINOR ASSETS'
                        ),

                        # Invert assets order from less relevant up
                        table.query('agg == False').iloc[::-1],
                    ]
                ) if table.shape[0]>(top+1) else table.iloc[::-1]
            )

            # Remove auxiliary columns
            .drop(columns=['rankk','agg','abs'])

            # Append the TOTAL row
            .pipe(
                lambda table: pandas.concat(
                    [
                        table,
                        pandas.DataFrame([{
                            'Asset': 'TOTAL',
                            kpi: table.cumsum().iloc[-1].values[1],
                            # kpi: 0,
                        }]),
                    ]
                )
            )

            # Tidy up the index
            .reset_index(drop=True)
        )

        if type=='raw':
            return contributions

        if type=='altair':
            import altair

            # Make TOTAL=0; Altair will compute TOTAL for display purposes
            contributions.iloc[-1,1]=0

            bar_size=85

            base = (
                altair.Chart(contributions, mark='line')
                .transform_window(
                    window_sum_amount=f"sum({kpi})",
                    window_lead_asset="lead(Asset)",
                )
                .transform_calculate(
                    calc_lead="datum.window_lead_asset === null ? datum.Asset : datum.window_lead_asset",
                    calc_prev_sum=f"datum.Asset === 'TOTAL' ? 0 : datum.window_sum_amount - datum.{kpi}",
                    calc_amount=f"datum.Asset === 'TOTAL' ? datum.window_sum_amount : datum.{kpi}",
                    calc_text_amount="(datum.Asset !== 'TOTAL' && datum.calc_amount > 0 ? '+' : '') + datum.calc_amount",
                    calc_center="(datum.window_sum_amount + datum.calc_prev_sum) / 2",
                    calc_sum_dec="datum.window_sum_amount < datum.calc_prev_sum ? datum.window_sum_amount : 'NONE'",
                    calc_sum_inc="datum.window_sum_amount > datum.calc_prev_sum ? datum.window_sum_amount : 'NONE'",
                )
                .encode(
                    x=altair.X(
                        "Asset:N",
                        axis=altair.Axis(
                            title='Assets',
                            labelAngle=-45,
                            labelExpr='split(datum.label," ")',
                            labelBaseline='middle'
                        ),
                        sort=None,
                    )
                )
            )

            # More visible grid line at zero
            zero = (
                altair.Chart()
                .mark_rule(size=5, color='#990000')
                .encode(y=altair.datum(0))
            )

            bars = (
                base
                .mark_bar(size=bar_size)
                .encode(
                    y=altair.Y("calc_prev_sum:Q", title=f"{kpi}"),
                    y2=altair.Y2("window_sum_amount:Q"),
                    color=dict(
                        condition=[
                            dict(
                                test="datum.Asset === 'TOTAL'",
                                value="magenta"
                            ),
                            dict(
                                test="datum.calc_amount < 0",
                                value="#fa4d56"
                            )
                        ],
                        value="#24a148",
                    ),
                )
            )

            # Connect result of previous bar to the next bar
            connectors = (
                base
                .mark_rule(
                    xOffset=-(bar_size/2),
                    x2Offset=(bar_size/2),
                ).encode(
                    y="window_sum_amount:Q",
                    x2="calc_lead",
                )
            )

            # Add values as text
            text_pos_values_top_of_bar = (
                base
                .mark_text(
                    baseline="bottom",
                    dy=-4
                ).encode(
                    text=altair.Text("calc_sum_inc:N",format=',.2f'),
                    y="calc_sum_inc:Q"
                )
            )

            text_neg_values_bot_of_bar = (
                base
                .mark_text(
                    baseline="top",
                    dy=4
                ).encode(
                    text=altair.Text("calc_sum_dec:N",format=',.2f'),
                    y="calc_sum_dec:Q"
                )
            )

            text_bar_values_mid_of_bar = (
                base
                .mark_text(baseline="middle")
                .encode(
                    text=altair.Text("calc_text_amount:N",format=',.2f'),
                    y="calc_center:Q",
                    color=altair.value("white"),
                )
            )

            return altair.layer(
                bars,
                zero,
                connectors,
                text_pos_values_top_of_bar,
                text_neg_values_bot_of_bar,
                text_bar_values_mid_of_bar
            ).properties(
                height=600
            )


    def describe(self,asof=None,tz=datetime.datetime.now().astimezone().tzinfo,output='styled'):
        """
        Short report of state (balance) of each asset in fund.

        asof:   Balance at that point of time. Or last value found.
        tz:     The timezone to display all time information
        output: Returns a pandas.styler object if 'styled'. Returns a plain
                dataframe otherwise
        """

        if asof is None:
            asof=pandas.Timestamp.max
        if not isinstance(asof,pandas.Timestamp):
            # Since this is a very precise filter, make it the end of the day
            # so it won't cut data from today
            asof=(
                # Time passed
                pandas.Timestamp(asof) +
                # 00:00:00 of next day
                pandas.Timedelta(days=1) +
                # Last microssecond of previous day, which is on asof date
                pandas.Timedelta(microseconds=1)
            )

        if asof.tz is None:
            asof=asof.tz_localize(0)

        totalBalance=(
            self.balance
            .query("time<=@asof")
            .groupby(level=0)
            .last()
            .droplevel(1,axis=1)
            # .loc[pandas.IndexSlice[:, :asof], :]
            .sum()
            .values[0]
        )

        desc = (
            self.balance
            .query("time<=@asof")
            .groupby(level=0)
            .last()
            .droplevel(1,axis=1)
            # .loc[pandas.IndexSlice[:, :asof], :]
            .query(f"{KPI.BALANCE}>0")
            .join(
                self.ledger
                .query("time<=@asof")
                .droplevel(0,axis=1)
                .reset_index(1)
                .groupby(level=0)
                .last()
                # .loc[pandas.IndexSlice[:, :asof], :]
                .rename(
                    columns={
                        'time': 'last movement',
                        'comment': 'comment of last movement',
                        self.exchange.currency: 'movement'
                    }
                ),
                how='inner'
            )
            .sort_values(KPI.BALANCE, ascending=False)
            .assign(
                **{
                    '% of portfolio': lambda table: table[KPI.BALANCE]/totalBalance,
                    'last movement': lambda table: table['last movement'].dt.tz_convert(tz)
                }
            )
            [[
                KPI.BALANCE,'% of portfolio','last movement',
                'movement','comment of last movement'
            ]]
        )

        if output=='styled':
            return (
                desc
                .style
                .format(
                    {
                        KPI.BALANCE: Fund.formatters[KPI.BALANCE]['format'],
                        'movement': Fund.formatters[KPI.MOVEMENTS]['format'],
                        '% of portfolio': '{:,.2%}',
                        'last movement': '{:%Y-%m-%d %X %z}',
                    }
                )
            )
        else:
            return desc



    ############################################################################
    ##
    ## Internal and operational methods
    ##
    ############################################################################

    def pseudoRandomUniqueMilliseconds(self):
        """
        Cycle over self.twoSeconds which has 1998 entries (0 to 1997) with
        random milliseconds in the range [-999..-1, 1..999]
        """

        twoSecondsLength=len(self.twoSeconds)

        i=0
        while i<twoSecondsLength:
            # print('generating')
            yield pandas.to_timedelta(self.twoSeconds[i],unit='ms')
            i+=1
            if (i==twoSecondsLength):
                i=0



    def getPeriodPairs():
        return list(Fund.periodPairs.keys())



    def div_offsets(a, b, date=pandas.Timestamp(0)):
        '''
        Computes how many b-periods are contained into an a-period. Exemple:

        a=5Y, b=Y, returns 5.
        a=4W, b=W, returns 4.
        a=Y, b=M, returns 12.
        a=W, b=D, return 7.

        Use Pandas standard periods to represent a and b, from:
        https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-period-aliases

        Technique from:
        https://stackoverflow.com/a/68285031/367824
        '''
        isNatural = lambda number: number%1==0

        a=pandas.tseries.frequencies.to_offset(a)
        b=pandas.tseries.frequencies.to_offset(b)

        try:
            result = a.nanos / b.nanos
            return result if not isNatural(result) else int(result)
        except ValueError:
            pass

        prev = (date + a) - a
        ans  = ((prev + a) - prev).total_seconds()*1e9

        prev = (date + b) - b
        bns  = ((prev + b) - prev).total_seconds()*1e9

        if ans > bns:
            result = round(ans / bns)
            # assert date + ratio * b == date + a
            return result if not isNatural(result) else int(result)
        else:
            result = round(1/(bns/ans))
            # assert date + b == date + ratio * a
            return result if not isNatural(result) else int(result)



    def __repr__(self):
        return '{self.__class__.__name__}(name={self.name}, currency={self.exchange.target})'.format(self=self)



    def __str__(self):
        return self.name



