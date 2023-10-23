import datetime
import logging
import numpy as np
import pandas as pd





class KPI(object):
    """
    A single class to hold KPI names.
    """

    # Source of all information
    BALANCE                 =  'balance'
    MOVEMENTS               =  'movements'

    # Cumulative movements
    SAVINGS                 =  'savings'

    # Rate of accumulated gains
    BALANCE_OVER_SAVINGS    =  'balance ➗ savings'

    # Pure gain, on the period or accumulated
    PERIOD_GAIN             =  'gain'   # on each period
    GAINS                   =  'cumulative gains'

    # Normalization features
    SHARE_VALUE             =  'share value'
    SHARES                  =  'shares'

    # Performance feature, wich is percentage change of share value
    RATE_RETURN             =  'rate of return'  # on each period

    # KPIs related to extenral sources as market indexes and benchmarks
    BENCHMARK               =  'benchmark'
    BENCHMARK_RATE_RETURN   =  'benchmark rate of return'  # on each period
    BENCHMARK_EXCESS_RETURN =  'excess return'  # relation between RATE_RETURN and BENCHMARK_RATE_RETURN, on each period







class Fund(object):
    initial_share_value=100



    periodPairs={
        'day & week': dict(
            period                     = 'D',
            periodLabel                = 'day',
            periodFormatter            = '%w·%a',

            macroPeriod                = 'W',
            macroPeriodLabel           = 'week',
            macroPeriodFormatter       = '%Y-w%U'
        ),


        'week & 4 weeks': dict(
            period                     = 'W',
            periodLabel                = 'week',

            macroPeriod                = '4W',
            macroPeriodLabel           = '4 week',
            macroPeriodFormatter       = '%Y-w%U'
        ),


        'month & year': dict(
            period                     = 'M',
            periodLabel                = 'month',
            periodFormatter            = '%m·%b',

            macroPeriod                = 'Y',
            macroPeriodLabel           = 'year',
            macroPeriodFormatter       = '%Y'
        ),


       'quarter & year': dict(
            period                     = 'Q',
            periodLabel                = 'quarter',
            periodFormatter            = '%m',

            macroPeriod                = 'Y',
            macroPeriodLabel           = 'year',
            macroPeriodFormatter       = '%Y'
        ),


        'half month & month': dict(
            period                     = 'SM',
            periodLabel                = 'month half',
            # periodFormatter            = '%d',

            macroPeriod                = 'M',
            macroPeriodLabel           = 'month',
            macroPeriodFormatter       = '%m'
        ),


        'year & 5 years': dict(
            period                     = 'Y',
            periodLabel                = 'year',
            # periodFormatter            = '%Y',

            macroPeriod                = '5Y',
            macroPeriodLabel           = '5 years',
            macroPeriodFormatter       = '%Y'
        ),


        'year & decade': dict(
            period                     = 'Y',
            periodLabel                = 'year',
            # periodFormatter            = '%Y',

            macroPeriod                = '10Y',
            macroPeriodLabel           = 'decade',
            macroPeriodFormatter       = '%Y'
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

        KPI.SHARE_VALUE: dict(
            format="${:,.2f}",
        ),

        KPI.RATE_RETURN: dict(
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

    def __init__(self, ledger, balance, currencyExchange=None, name=None):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        # Configure a multi-currency converter engine
        self.exchange=currencyExchange
        self.currency=currencyExchange.target

        # Group all columns under a ‘ledger’ multi-index
        self.ledger = pd.concat(
            [ledger.set_index(['fund','time']).sort_index()],
            axis=1,
            keys=['ledger']
        )

        # Group all columns under a ‘balance’ multi-index
        self.balance = pd.concat(
            [balance.set_index(['fund','time']).sort_index()],
            axis=1,
            keys=[KPI.BALANCE]
        )

        # Homogenize all to same currency
        self.ledger  = self.convertCurrency(self.ledger)
        self.balance = self.convertCurrency(self.balance)


        # Compute number of shares and share value over time
        try:
            self.computeShares()

            # Date and time the fund begins and ends
            self.start=((self.shares[KPI.SHARES] != 0) | (self.shares[KPI.SHARE_VALUE] != 0)).idxmax()
            self.end=self.shares.tail(1).index.item()
        except Exception as e:
            self.logger.warning(
                f'Failed to compute shares with error "{e}". ' +
                'Returning an incomplete object for debug purposes'
            )

        self.setName()
        # self.name='aaa'


    def setName(self, name=None, top=3) -> str:
        """
        Set fund name and return it.

        If 0 < top < 1, set name based on instruments that contribute to the
        top% of the fund.

        If top is integer N, set name based on top N instruments.
        """

        # Set name based on instruments ordered by balance
        currentBalance=self.balance.groupby(level=0).last()
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

        # Working on 'ledger' or KPI.BALANCE ?
        part=df.columns.get_level_values(0)[0]

        # Get list of currencies that need conversion
        toConvert=list(df.columns.get_level_values(1))

        if 'comment' in toConvert:
            toConvert.remove('comment')

        ## Do not convert values already in target currency, will sum() them later
        sumCurrent=[]
        if self.exchange.target in toConvert:
            toConvert.remove(self.exchange.target)
            sumCurrent.append((part,self.exchange.target))




        # Create a working dataframe with our input df simply joined with
        # currency exchange data, using super powerful merge_asof()
        monetary=(
            # Join values with time-equivalent exchange rates
            pd.merge_asof(
                # Remove fund level from index and sort by time
                df.reset_index('fund').sort_index(),

                # Add 'exchange' column level to exchange columns
                pd.concat(
                    [self.exchange.data],
                    axis=1,
                    keys=['exchange']
                ),
                left_index=True, right_index=True
            )
            # Restore fund as an index in the original order
            .set_index('fund', append=True)
            .reorder_levels(['fund','time'])

            # Sort index by fund and time
            .sort_index()
        )

        # Result at this point is same ledger or balance with additional columns for
        # exchange rates. Now make currency conversion calculations...

        # Sum all converted and non-converted columns in one target column
        return (
            monetary.join(
                pd.DataFrame(
                    columns=pd.MultiIndex.from_tuples(
                        [('converted',self.exchange.target)]
                    ),
                    data=(
                        monetary.join(
                            # Result of concat is currency-converted columns from
                            # original values
                            pd.concat(
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



    def computeShares(self, initial_share_value=initial_share_value):
        self.initial_share_value=initial_share_value

        shares=0
        share_value=0

        shares_evolution=[]

        funds=self.ledger.index.get_level_values(0).unique()

        # Handle Balance by combining/summing all balances
        combinedBalance=None
        if len(funds)>1:
            ## Put balance of each fund in a different column,
            ## repeat value for empty times and fillna(0) for first empty values
            try:
                combinedBalance=self.balance.dropna().unstack(level=0).pad()
            except Exception as e:
                self.logger.debug(e)
#                 self.balance.to_csv('balance_dups.csv')
#                 iii=self.balance.index.to_frame().reset_index(drop=True) #.set_index('time')
#                 iii.to_csv('index.csv')
                raise e
#                 iii=iii.join(iii, rsuffix='_aa')
#                 self.logger.debug(iii[iii.fund!=iii.fund_aa])

            ## Combined balance is the sum() of balances of all funds at each point in time
            combinedBalance=(
                combinedBalance
                .sum(axis=1)
                .where(lambda s: s!=0)
                .dropna()
                .sort_index()
            )

            ## Eliminate all consecutive repeated values
            combinedBalance=combinedBalance.loc[combinedBalance.shift()!=combinedBalance]

            ## Make it a compatible DataFrame
            combinedBalance=pd.DataFrame(combinedBalance)
            combinedBalance.columns=pd.MultiIndex.from_tuples([(KPI.BALANCE,self.exchange.target)])

        else:
            combinedBalance=self.balance.droplevel(0)

#         self.combinedBalance=combinedBalance


        # Handle Ledger by simply sorting by time the movements of all funds

        theShares=(
            self.ledger

            # Get rid of comment column
            .drop(columns=('ledger','comment'))

            # Get rid of fund names
            .droplevel(0)

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

        for i,t in theShares.iterrows():

#             print(f'{i}: {t}')

            # First adjust number of shares if there was any movements
            if not pd.isna(t['ledger']) and t['ledger']!=0:
                if share_value!=0:
                    shares += t['ledger']/share_value
                elif shares==0:
                    share_value = initial_share_value
                    shares = t['ledger']/share_value


            # Second, adjust the share value based on balance
            if not pd.isna(t[KPI.BALANCE]) and t[KPI.BALANCE]!=0:
                if shares==0:
                    # The rare situation where we have balance before any movement
                    shares=t[KPI.BALANCE]/initial_share_value

                share_value = t[KPI.BALANCE]/shares

            shares_evolution.append(
                (i,shares,share_value)
            )

        self.shares=(
            pd.DataFrame.from_records(
                shares_evolution,
                columns=('time',KPI.SHARES,KPI.SHARE_VALUE)
            )
            .set_index('time')
        )



    ############################################################################
    ##
    ## Reporting methods
    ##
    ############################################################################

    def report(self, period='month & year', benchmark=None, output='styled',
                start=None,
                end=None,
                flatPeriodFirst=True,
                kpi=benchmarkFeatures + [
                    KPI.RATE_RETURN,   KPI.PERIOD_GAIN,   KPI.BALANCE,
                    KPI.SAVINGS,       KPI.MOVEMENTS,     KPI.SHARES,
                    KPI.SHARE_VALUE
                ]
        ):
        """
        Joins 2 periodicReports() to get a complete report with periods
        and summary of periods. For example, period='month & year'
        computes the benchmarks for each month plus the summary of 12
        months (an year).
        """


        # Find period structure
        try:
            p = self.periodPairs[period]
        except KeyError:
            raise KeyError("Period pair must be one of: {}".format(str(Fund.getPeriodPairs())))


        # How many periods fit in a macroPeriod ?
        periodsInSummary=Fund.div_offsets(p['macroPeriod'],p['period'])

        if benchmark is None:
            # Remove benchmark features because there is no benchmark
            kpi=[i for i in kpi if i not in self.benchmarkFeatures]

            # Can't use set() operations here because it messes with features
            # order, which are important to us


        # Get detailed part of report with period data
        period = self.periodicReport(
            period     = p['period'],
            benchmark  = benchmark,
            start      = start,
            end        = end
        )[kpi]

        # Get summary part report with summary of a period set
        macroPeriod = self.periodicReport(
            period     = p['macroPeriod'],
            benchmark  = benchmark,
            start      = start,
            end        = end
        )[kpi]


        report=None

        # KPI income has a special formatter
        if KPI.PERIOD_GAIN in self.formatters:
            incomeFormatter=self.formatters[KPI.PERIOD_GAIN]['format']
        else:
            incomeFormatter=self.formatters['DEFAULT']['format']

        # Break the periodic report in chunks equivalent to the summary report
        for i in range(len(macroPeriod.index)):

            macroPeriodPrev=macroPeriod.index.shift(-1)[i]
            macroPeriodCurr=macroPeriod.index[i]

            if i==0:
                # Process first line, usually prepending NaNs
                line=period[:macroPeriodCurr]
                nPeriods=line.shape[0]

                completeMe = periodsInSummary - nPeriods

                if completeMe > 0:
                    # First line in report use to need leading empty periods if they
                    # start in the middle of macro period
                    line=(
                        pd.concat(
                            [
                                # Preppend empty lines
                                pd.DataFrame(
                                    index=pd.date_range(
                                        line.index.shift(-completeMe)[0],
                                        periods=completeMe,
                                        freq=line.index.freq
                                    )
                                ),
                                line
                            ]
                        )
                        .pipe(
                            lambda table: table[
                                (table.index > macroPeriodPrev) &
                                (table.index <= macroPeriodCurr)
                            ]
                        )
                    )

                    nPeriods=line.shape[0]
            else:
                # Process lines that are not the first
                currentRange=(
                    (period.index > macroPeriodPrev) &
                    (period.index <= macroPeriodCurr)
                )
                line=period[currentRange]
                nPeriods=line.shape[0]

            somedict={
                p['periodLabel']: (
                    line.index.strftime(p['periodFormatter'])
                    if 'periodFormatter' in p
                    else range(1,nPeriods+1,1)
                ),
                '': 'periods'
            }

            # Add a row label, as '2020' or '4·Thu' or '2022-w25'
            line=(
                ## Add the time index of the summary report as an additional
                ## index level to columns
                pd.concat([line], axis=1, keys=[macroPeriod.index[i]])

                ## Rename the title for labels so we can join latter
                .rename_axis(['time','KPI'], axis='columns')

                ## Convert index from full DateTimeIndex to something that can
                ## be matched across macro-periods, as just '08·Aug'
                .assign(
                    **{
                        p['periodLabel']: (
                            line.index.strftime(p['periodFormatter'])
                            if 'periodFormatter' in p
                            else range(1,nPeriods+1,1)
                        ),
                        '': 'periods'
                    }
                )
                .set_index(['',p['periodLabel']])
            )

            # Add to main report transposing it into a true row (we were columns
            # until now)
            report=(
                pd.concat([report,line.T], sort=True)
                if report is not None
                else line.T
            )

            self.debugReport=report

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

        # Make summary report a column, sort and name labels for perfect join
        macroPeriod=(
            macroPeriod
            .rename_axis(columns='KPI')
            .T
            .stack()
            .reorder_levels(['time','KPI'])
            .sort_index()
        )

        # Join the summary report to main report
        report[('summary of periods',p['macroPeriodLabel'])]=macroPeriod

        # Reformat line index from a full DateTimeIndex to something more readable
        report.index=pd.MultiIndex.from_tuples(
            [
                (x[0].strftime(p['macroPeriodFormatter']), x[1])
                for x in report.index
            ],
            name=['time','KPI']
        )




        # output may be:
        ## - styled (default): returns a styled Dataframe
        ## - flat: hard format and simplify the dataframe for Streamlit
        ## - plain: the Dataframe without style

        if output=='plain':
            ## Just return the Dataframe
            return report

        if output=='flat' or output=='flat_unformatted':
            ## Convert all to object to attain more flexibility per cell
            out=report.astype(object)

            if output=='flat_unformatted':
                return out

        if output=='styled':
            ## Lets work with a styled DataFrame
            out=report.style


        # Since we want results styled or pre-formatted (to overcome Streamlit bugs) and
        # not plain (just the data), we'll have to apply formatting, either as style or
        # hardcoded (in case of flat).


        defaultFormat=None
        if 'DEFAULT' in self.formatters:
            defaultFormat=self.formatters['DEFAULT']

        for i in kpi:
            for g in ['periods', 'summary of periods']:
                # Select formatter for KPI

                f=defaultFormat['format']
                if g=='summary of periods' and 'summaryFormat' in defaultFormat:
                    f=defaultFormat['summaryFormat']

                if i in self.formatters:
                    if g=='summary of periods' and 'summaryFormat' in self.formatters[i]:
                        f=self.formatters[i]['summaryFormat']
                    else:
                        f=self.formatters[i]['format']


                selector=pd.IndexSlice[
                    # Apply format in KPI row
                    pd.IndexSlice[:,i],

                    # Apply style in «periods» or «summary of periods»
                    pd.IndexSlice[g,:]
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
        level=out.loc[:,pd.IndexSlice['summary of periods',:]].columns.values[0][1]
        out.rename(columns={level:'summary of periods'},inplace=True)
        out.columns=out.columns.droplevel(0)

        return out



    def periodicReport(self, period=None, benchmark=None, start=None, end=None):
        """
        This is the most important summarization and reporting method of the class.
        Returns a DataFrame with features as rate of return, income, balance, shares,
        share_value, benchmark rate of return, excess return compared to benchmark.

        period: Either 'M' (monthly), 'Y' (yearly), 'W' (weekly) to aggregate data for
        these periods. If not passed, returned dataframe will be a ragged time series as
        precise as the amount of data available.

        benchmark: A MarketIndex object to use a performance indicator used to compute
        benchmark rate of return and excess return. Features are omitted and not computed
        if this objected is not passed.

        start: A starting date for the report. Makes benchmark rate of return start at
        value 1 on this date. Starts at beginning of data if this is None.
        """

        # Chronological index where data begins to be non-zero
        startOfReport=self.start


        errorMsg='{par} parameter must be of type Pandas Timestamp or Python date or time, or a string compatible with datetime.datetime.fromisoformat(), but got "{value}"'

        if start is not None:
            # Check if we have a good start time and make appropriate type conversions.
            if isinstance(start,str):
                start=datetime.datetime.fromisoformat(start)
            if not (isinstance(start,datetime.date) or isinstance(start,datetime.time) or isinstance(start,pd.Timestamp)):
                raise TypeError(errorMsg.format(par='start',value=start))

            # Now see if start time is more recent than the beginning of our data, and
            # use it
            if start > startOfReport:
                startOfReport=start


        if end is not None:
            # Check if we have a good start time and make appropriate type conversions.
            if isinstance(end,str):
                end=datetime.datetime.fromisoformat(end)
            if not (isinstance(end,datetime.date) or isinstance(end,datetime.time) or isinstance(end,pd.Timestamp)):
                raise TypeError(errorMsg.format(par='end',value=end))

        # Start fresh
        report=self.shares.copy() #[startOfReport:end]

        # Add ledger to get movements for period
        report=report.join(
            self.ledger
            .droplevel(0)
            .drop(('ledger','comment'),axis=1)
            .droplevel(1, axis=1)
            .rename(columns=dict(ledger=KPI.MOVEMENTS))
            .sort_index(), #[startOfReport:end]
            how='left'
        )

        report[KPI.MOVEMENTS] = report[KPI.MOVEMENTS].fillna(0)

        # Add balance as a function of shares
        report[KPI.BALANCE]=report[KPI.SHARES]*report[KPI.SHARE_VALUE].ffill()

        # Add cumulated savings (cumulated movements)
        report[KPI.SAVINGS]=report[KPI.MOVEMENTS].cumsum().ffill()

        # Add balance over savings
        report[KPI.BALANCE_OVER_SAVINGS]=report[KPI.BALANCE]/report[KPI.SAVINGS]

        # Add cumulative income
        report[KPI.GAINS]=report[KPI.BALANCE]-report[KPI.SAVINGS]

        # Getting ready to aggregate on a periodic basis
        aggregationStrategy={
            kpi: 'last'
            for kpi in [
                KPI.SHARES,
                KPI.SHARE_VALUE,
                KPI.BALANCE,
                KPI.SAVINGS,
                KPI.BALANCE_OVER_SAVINGS,
                KPI.GAINS,
            ]
        }

        aggregationStrategy[KPI.MOVEMENTS]='sum'

        # On a downsample scenario (e.g. period=Y), we'll have more fund data than final report.
        # On an upsample scenario (e.g. period=D), we'll have more report lines than fund data.
        # If period=None, number of report lines will match the amount of fund data we have.
        # These 3 situations affect how benchmark has to be handled.

        # Cut the report just before period-aggregation operation
        report=report[startOfReport:end]

        if period is not None:
            # Make it a regular time series (D, M, Y etc), each column
            # aggregated by different strategy

            # Day 0 for Pandas is Monday, while it is Sunday for Python.
            # Make Pandas handle day 0 as Sunday.
            dateOffset=pd.tseries.offsets.Week(weekday=5) if period=='W' else period

            report=(
                report
                .resample(dateOffset)

                # Compute summarizations for each KPI
                .agg(aggregationStrategy)

                # Fill the gaps after aggregation
                .ffill()
            )

        # Add 3 benchmark-related features
        benchmarkFeatures=[]
        if benchmark is not None:
            # Pair with Benchmark
            report=pd.merge_asof(
                report,
                (
                    benchmark
                    .getData()[['value']]
                    .rename(columns={'value': KPI.BENCHMARK})
                ),
                left_index=True,
                right_index=True
            )

            benchmarkFeatures=self.benchmarkFeatures

        # Compute rate of return (pure gain excluding movements)
        report[KPI.RATE_RETURN]=report[KPI.SHARE_VALUE].pct_change().fillna(0)

        # The pct_change() above yields ∞ or NaN at the first line, so fix it manually
        report.loc[report.index[0],KPI.RATE_RETURN]=(
            (report.loc[report.index[0],KPI.SHARE_VALUE]/self.shares[KPI.SHARE_VALUE].asof(startOfReport))-1
        )

        # Compute gain per period comparing consecutive Balance and excluding Movements
        report=report.join(
            report[KPI.BALANCE].shift(),
            rsuffix='_prev',
            sort=True
        )

        # shift() yields NaN for first position, so fix it
        if startOfReport==self.start:
            # Balance is always Zero before the fund ever existed
            report.loc[report.index[0],KPI.BALANCE+'_prev']=0
        else:
            # Compute Balance based on immediate previous data
            report.loc[report.index[0],KPI.BALANCE+'_prev']=(
                self.shares[KPI.SHARE_VALUE].asof(startOfReport-pd.Timedelta(seconds=1)) *
                self.shares[KPI.SHARES].asof(startOfReport-pd.Timedelta(seconds=1))
            )

        # Compute income as the difference of Balance between consecutive
        # periods, minus Movements of period
        report[KPI.PERIOD_GAIN]=report.apply(
            lambda x: (
                # Balance of current period
                x[KPI.BALANCE]

                # Balance of previous period
                -x[KPI.BALANCE + '_prev']

                # Movements of current period
                -x[KPI.MOVEMENTS]
            ),
            axis=1
        )

        # Compute features that depend on Benchmark
        if benchmark is not None:
            # Compute benchmark growth
            report[KPI.BENCHMARK_RATE_RETURN]=report[KPI.BENCHMARK].pct_change()

            # The pct_change() above yields ∞ at the first line, so fix it manually
            report.loc[report.index[0],KPI.BENCHMARK_RATE_RETURN]=(
                (report.loc[report.index[0],KPI.BENCHMARK]/benchmark.getData()['value'].asof(startOfReport))-1
            )

            # Compute fund excess growth over benchmark
            report[KPI.BENCHMARK_EXCESS_RETURN]=report[KPI.RATE_RETURN]-report[KPI.BENCHMARK_RATE_RETURN]

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
                KPI.SHARES,
                KPI.SHARE_VALUE
            ]
        ]



    ############################################################################
    ##
    ## Data visualization
    ##
    ############################################################################

    def performancePlot(self, benchmark, start=None, end=None, type='pyplot'):
        if benchmark.currency!=self.currency:
            self.logger.warning(f"Benchmark {benchmark.id} has a different currency; comparison won't make sense")

        # Get prototype of data to plot
        data=self.periodicReport(
            benchmark=benchmark,
            start=start,
            end=end
        )[[KPI.SHARE_VALUE,KPI.BENCHMARK]]

        # Normalize share_value to make it start on value 1
        data[KPI.SHARE_VALUE]/=data[KPI.SHARE_VALUE][0]


        data.rename(
            columns=dict(
                share_value=str(self),
                benchmark=str(benchmark)
            ),
            inplace=True
        )



        if type=='pyplot':
            return data.plot(kind='line')
        elif type=='vegalite':
            spec=dict(
                description='Performance of {name}'.format(name=self.name,index=benchmark.id),
                mark='trail',
                encoding=dict(
                    x=dict(
                        field='date',
                        type='temporal'
                    ),
                    y=dict(
                        field='performance',
                        type='quantitative'
                    ),
                    size=dict(
                        field='performance',
                        type='quantitative'
                    ),
                    color=dict(
                        field='performance',
                        type='quantitative'
                    )
                )
            )
        elif type=='raw':
            return data



    def wealthPlot(self, benchmark, start=None, end=None, type='pyplot'):
        if benchmark.currency!=self.currency:
            self.logger.warning(f"Benchmark {benchmark.id} has a different currency; comparison won't make sense")

        # Get prototype of data to plot
        data=self.periodicReport(
            benchmark=benchmark,
            start=start,
            end=end
        )[[KPI.BALANCE,KPI.SAVINGS,KPI.GAINS]]




        if type=='pyplot':
            return data.plot(kind='line')
        elif type=='vegalite':
            spec=dict(
                description='Performance of {name}'.format(name=self.name,index=benchmark.id),
                mark='trail',
                encoding=dict(
                    x=dict(
                        field='date',
                        type='temporal'
                    ),
                    y=dict(
                        field='performance',
                        type='quantitative'
                    ),
                    size=dict(
                        field='performance',
                        type='quantitative'
                    ),
                    color=dict(
                        field='performance',
                        type='quantitative'
                    )
                )
            )
        elif type=='raw':
            return data



    def rateOfReturnPlot(self,period='M', confidence_interval=0.95, start=None, end=None, type='pyplot'):
        # Get prototype of data to plot
        data=(
            self.periodicReport(
                period=period,
                start=start,
                end=end
            )[[KPI.SHARE_VALUE]]
            .pct_change()
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .rename(
                columns={
                    KPI.SHARE_VALUE: 'rate of return %, frequency per period'
                }
            )
            *100
        )

        # Handle rate of return as a gaussian distribution
        μ=data.mean()[0]
        σ=data.std()[0]

        if type=='pyplot':
            if data.shape[0]>1:
                return data.plot(
                    kind='hist',
                    bins=200,
                    xlim=(μ-2*σ,μ+2*σ)
                ).get_figure()
            else:
                return None
        elif type=='raw':
            return data



    def incomePlot(self,periodPair='month & year', start=None, end=None, type='pyplot'):
        p=self.periodPairs[periodPair]

        # Compute how many 'period's fit in one 'macroPeriod'.
        # https://stackoverflow.com/questions/68284757
        o1 = pd.tseries.frequencies.to_offset(p['period'])
        o2 = pd.tseries.frequencies.to_offset(p['macroPeriod'])

        t0 = pd.Timestamp(0)

        o2ns = ((t0 + o2) - t0).delta
        o1ns = ((t0 + o1) - t0).delta

        periodCountInMacroPeriod=round(o2ns/o1ns)


        # Now compute moving averages

        data=self.periodicReport(period=p['period'], start=start, end=end)[[KPI.PERIOD_GAIN]]


        data['{} {}s moving average'.format(periodCountInMacroPeriod,p['periodLabel'])] = (
            data[KPI.PERIOD_GAIN]
            .rolling(periodCountInMacroPeriod, min_periods=1)
            .mean()
        )

        data['{} {}s moving median'.format(periodCountInMacroPeriod,p['periodLabel'])] = (
            data[KPI.PERIOD_GAIN]
            .rolling(periodCountInMacroPeriod, min_periods=1)
            .median()
        )

#         data=data.tail(24)

#         ax = data[['moving_average']].plot(kind='line')
#         ax = data[['moving_median']].plot(kind='line', ax=ax)
#         ax = data[['income']].plot(kind='bar', ax=ax)

        if type=='raw':
            return data

        if type=='altair':
            import altair

            colors=['blue', 'red', 'green', 'cyan', 'yellow', 'brown']
            color=0

            columns=list(data.columns)
            columns.remove(KPI.PERIOD_GAIN)


            base=altair.Chart(data.reset_index()).encode(x='time')
            bar=base.mark_bar(color=colors[color]).encode(y=KPI.PERIOD_GAIN)
            color+=1

            for column in columns:
                bar+=base.mark_line(color=colors[color]).encode(y=column)
                color+=1

            return bar.interactive()



    ############################################################################
    ##
    ## Internal and operational methods
    ##
    ############################################################################

    def pseudoRandomUniqueMilliseconds(self):
        # Cycle over self.twoSeconds which has 1998 entries (0 to 1997) with
        # random milliseconds in the range [-999..-1, 1..999]

        twoSecondsLength=len(self.twoSeconds)

        i=0
        while i<twoSecondsLength:
            # print('generating')
            yield pd.to_timedelta(self.twoSeconds[i],unit='ms')
            i+=1
            if (i==twoSecondsLength):
                i=0



    def getPeriodPairs():
        return list(Fund.periodPairs.keys())



    def getPeriodPairLabel(period):
        return period



    def div_offsets(a, b, date=pd.Timestamp(0)):
        '''
        Compute pandas dateoffset ratios using nanosecond conversion
        https://stackoverflow.com/a/68285031/367824
        '''
        a=pd.tseries.frequencies.to_offset(a)
        b=pd.tseries.frequencies.to_offset(b)

        try:
            return a.nanos / b.nanos
        except ValueError:
            pass

        prev = (date + a) - a
        ans  = ((prev + a) - prev).delta

        prev = (date + b) - b
        bns  = ((prev + b) - prev).delta

        if ans > bns:
            ratio = round(ans / bns)
            # assert date + ratio * b == date + a
            return ratio
        else:
            ratio = round(bns / ans)
            # assert date + b == date + ratio * a
            return 1 / ratio



    def __repr__(self):
        return '{self.__class__.__name__}(name={self.name}, currency={self.exchange.target})'.format(self=self)



    def __str__(self):
        return self.name



