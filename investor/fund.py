import datetime
import logging
import pandas as pd

class Fund(object):
    periodPairs=[
        dict(
            period='D',
            periodLabel='day',
            periodFormatter='%w·%a',

            macroPeriod='W',
            macroPeriodLabel='week',
            macroPeriodFormatter='%Y-w%U'
        ),
        dict(
            period='M',
            periodLabel='month',
            periodFormatter='%m·%b',

            macroPeriod='Y',
            macroPeriodLabel='year',
            macroPeriodFormatter='%Y'
        ),
        dict(
            period='Q',
            periodLabel='quarter',
            periodFormatter='%m',

            macroPeriod='Y',
            macroPeriodLabel='year',
            macroPeriodFormatter='%Y'
        ),
        dict(
            period='SM',
            periodLabel='month half',
            periodFormatter='%d',

            macroPeriod='M',
            macroPeriodLabel='month',
            macroPeriodFormatter='%m'
        )
    ]

    formatters={
        'DEFAULT': dict(
            format="{:,.2f}"
        ),

        'income': dict(
            format="{:,.2f}",
            summaryFormat='{}'
        ),

        'rate of return': dict(
            format="{:,.2%}"
        ),

        'excess return': dict(
            format="{:,.2%}"
        ),
        'benchmark rate of return': dict(
            format="{:,.2%}"
        ),
        'balance÷savings': dict(
            format="{:,.2%}"
        )
    }



    def __repr__(self):
        return '{self.__class__.__name__}(name={self.name}, currency={self.exchange.target})'.format(self=self)



    def __init__(self, ledger, balance, currencyExchange=None, name=None):
        # Setup logging
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)



        # A true pseudo-random number generator in the space of 2 minutes used to add
        # random seconds to entries at the same time. This is why we exclude Zero.
        self.twoMinutes=pd.Series(range(-59,60))
        self.twoMinutes=self.twoMinutes[self.twoMinutes!=0].sample(frac=1).reset_index(drop=True)
        self.twoMinutesGen=self.pseudoRandomUniqueSeconds()


        self.exchange=currencyExchange

        if name:
            self.name=name
        else:
            self.name=' ⋃ '.join(ledger['fund'].unique()) + ' @ ' + self.exchange.target


        self.ledger = pd.concat(
            [self.normalizeMonetarySheet(ledger)],
            axis=1,
            keys=['ledger']
        )


        # Shift naive entries in 12h3m, just to put them after ledger's default 12h0m
        self.balance = pd.concat(
            [self.normalizeMonetarySheet(balance, naiveTimeShift = 12*3600 + 3*60)],
            axis=1,
            keys=['balance']
        )


        self.ledger  = self.convertCurrency(self.ledger)
        self.balance = self.convertCurrency(self.balance)

        self.currency=currencyExchange.target

        self.computeShares()




    def normalizeMonetarySheet(self, sheet, naiveTimeShift=12*3600):
        sheet=sheet.copy()


        # Shift dates that have no time (time part is 00:00:00) to
        # the middle of the day (12:00:00) using naiveTimeShift
        sheet.loc[sheet.time.dt.time==datetime.time(0), 'time'] = (
            sheet[sheet.time.dt.time==datetime.time(0)]['time'] +
            pd.to_timedelta(naiveTimeShift, unit='s')
        )


        # Adjust duplicate datetime entries of funds adding random number of seconds
        sheet.sort_values('time', inplace=True)

        ## Get a dataframe with only the time entries of the
        ## fund in a way we can make comparisons
        adjust=(
            sheet[['time']]
            .join(
                sheet[['time']].shift(1),
                rsuffix='_next'
            )
        )

        ## Find only the duplicate entries, those that will need adjustment
        repeatedTime=(
#             (adjust['fund']==adjust['fund_next']) &
            (adjust['time']==adjust['time_next'])
        )

        ## Adjust time adding a few random seconds
        sheet.loc[repeatedTime, 'time']=(
            sheet[repeatedTime]['time']
            .apply(
                lambda x: x+pd.to_timedelta(
#                     random.randint(-60,60),
#                     secrets.randbelow(120)-60,
                    next(self.twoMinutesGen),
                    unit='s'
                )
            )
        )

        return sheet.set_index(['fund','time']).sort_index()




    def convertCurrency(self, df):

        # Working on 'ledger' or 'balance' ?
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




        # Creating a working dataframe with our input df simply joined with
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
                    data=monetary.join(
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
                        )[
                            # Select all converted columns
                            [ ('converted from',col) for col in toConvert ] +

                            # Add the might-not-exist column that already was in target
                            # currency and won't need conversion
                            sumCurrent
                        ].sum(axis=1)
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




    def computeShares(self, initial_share_value=100):
        shares=0
        share_value=0

        shares_evolution=[]

        funds=self.ledger.index.get_level_values(0).unique()

        # Handle Balance by combining/summing all balances
        combinedBalance=None
        if len(funds)>1:
            ## Put balance of each fund in a different column,
            ## repeat value for empty times and fillna(0) for first empty values
            combinedBalance=self.balance.dropna().unstack(level=0).pad()

            ## Combined balance is the sum() of balances of all funds at each point in time
            combinedBalance['sum']=combinedBalance.sum(axis=1)

            ## Get only non-zero balances in a time-sorted vector
            combinedBalance=combinedBalance['sum'].replace(0,pd.NA).dropna().sort_index()

            ## Eliminate all consecutive repeated values
            combinedBalance=combinedBalance.loc[combinedBalance.shift()!=combinedBalance]

            ## Make it a compatible DataFrame
            combinedBalance=pd.DataFrame(combinedBalance)
            combinedBalance.columns=pd.MultiIndex.from_tuples([('balance',self.exchange.target)])

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
            if not pd.isna(t['balance']) and t['balance']!=0:
                if shares==0:
                    # The rare situation where we have balance before any movement
                    shares=t['balance']/initial_share_value

                share_value = t['balance']/shares

            shares_evolution.append(
                (i,shares,share_value)
            )

        self.shares=(
            pd.DataFrame.from_records(
                shares_evolution,
                columns=('time','shares','share_value')
            )
            .set_index('time')
        )




    def periodicReport(self, period='M', benchmark=None):

        # Chronological index where data begins to be non-zero
        sharesBeginsNonZero=((self.shares['shares'] != 0) | (self.shares['share_value'] != 0)).idxmax()
#         ledgerBeginsNonZero=(self.ledger[('ledger',self.exchange.target)] != 0).idxmax()
#         balanceBeginsNonZero=(self.balance[('balance',self.exchange.target)] != 0).idxmax()


        # Start fresh
        report=self.shares[sharesBeginsNonZero:].copy()

        # Add ledger to get movements for period
        report['movements']=(
            self.ledger
                .droplevel(0)
                .drop(('ledger','comment'),axis=1)
                .droplevel(1, axis=1)
                .sort_index()
        )
        report['movements'] = report['movements'].fillna(0)



        # Make it a regular time series (M, Y etc), each column aggregated by
        # different strategy
        report=(
            report
                .resample(period)
                .agg(
                    dict(
                        shares       = 'last',
                        share_value  = 'last',
                        movements    = 'sum'
                    )
                )
        )

        report['shares'] = report['shares'].ffill()
        report['share_value'] = report['share_value'].ffill()


        if period!='D':
            # In order to have period-end rate of return for 1st period, the first
            # movement is needed, except for high resolution reports, such as Daily.
            report=(
                report
                    .append(self.shares[sharesBeginsNonZero:].head(1))
                    .sort_index()
            )



        # Now we have it all computed in a regular period (M, Y etc):
        # shares, share_value, movements


        # Compute rate of return (pure gain excluding movements)
        report['rate of return']=report['share_value'].pct_change().fillna(0)


        if period!='D':
            # Remove first row, that was included artificially just to compute
            # first pct_change()
            report=report.iloc[1:]


        # Add balance
        report['balance']=report['shares']*report['share_value'].ffill()

        # Add cumulated savings (cumulated movements)
        report['savings']=report['movements'].cumsum().ffill()

        # Add balance over savings
        report['balance÷savings']=report['balance']/report['savings']-1


        if report.shape[0]>1:
            # Pair with shares of the previous period
            report=report.join(
                report[['shares','share_value']].shift(),
                rsuffix='_prev'
            )


            # Compute income as the difference between consecutive periods, minus
            # movements of period
            report['income']=report.apply(
                lambda x: (
                    # Balance of current period
                    x['shares']*x['share_value']

                    # Balance of previous period
                    -x['shares_prev']*x['share_value_prev']

                    # Movements of current period
                    -x['movements']
                ),
                axis=1
            )
            if period!='D':
                # Adjust income of first period only
                report.loc[report.index[0],'income']+=report.loc[report.index[0],'movements']

        # Adjust income of first period only
        report.loc[report.index[0],'income']=(
            report.loc[report.index[0],'balance']-
            report.loc[report.index[0],'savings']
        )


        # Add 3 benchmark-related features
        benchmarkFeatures=[]
        if benchmark is not None:
            # Join with benchmark
            report=pd.merge_asof(
                report,
                benchmark.data[['value']].rename(columns={'value': 'benchmark'}),
                left_index=True,
                right_index=True
            )

            # Normalize benchmark making it start with value 1
            report['benchmark'] /= report.iloc[0]['benchmark']

            # Compute benchmark growth
            report['benchmark rate of return']=report['benchmark'].pct_change()

            # Compute fund excess growth over benchmark
            report['excess return']=report['rate of return']-report['benchmark rate of return']

            benchmarkFeatures=['benchmark', 'benchmark rate of return', 'excess return']

        return report[
            [
                'rate of return',
                'income',
                'balance',
                'savings',
                'balance÷savings',
                'movements',
                'shares',
                'share_value'
            ] +
            benchmarkFeatures
        ]




    def performancePlot(self, marketIndex, type='pyplot'):
        if marketIndex.currency!=self.currency:
            self.logger.warning("MarketIndex has a different currency; comparison won't make sense")

        fundBegin=((self.shares['shares'] != 0) | (self.shares['share_value'] != 0)).idxmax()

        indexx=marketIndex.data[['value']].truncate(before=fundBegin)
        indexx['value']/=indexx['value'][indexx.index[0]]


        data = pd.merge_asof(
            (self.shares[['share_value']].truncate(before=fundBegin)/self.shares['share_value'][fundBegin]),
            indexx,
            left_index=True, right_index=True
        ).rename(
            columns=dict(
                share_value=self.name,
                value=marketIndex.id
            )
        )

        if type=='pyplot':
            data.plot(kind='line')
        elif type=='vegalite':
            spec=dict(
                description='Performance of {name}'.format(name=self.name,index=marketIndex.id),
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







    def rateOfReturnPlot(self,period='M'):
        data=(
            self.shares[['share_value']]
            .resample('M')
            .last()
            .rename(columns=dict(share_value='rate of return %'))
            .pct_change()
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        return data

        # To plot:
        (100*data).plot(kind='histogram', bins=data.shape[0]/2)



    def incomePlot(self,period='M'):
        for p in self.periodPairs:
            if p['period']==period:
                break


        # https://stackoverflow.com/questions/68284757
        o1 = pd.tseries.frequencies.to_offset(p['period'])
        o2 = pd.tseries.frequencies.to_offset(p['macroPeriod'])

        t0 = pd.Timestamp(0)

        o2ns = ((t0 + o2) - t0).delta
        o1ns = ((t0 + o1) - t0).delta

        periodCountInMacroPeriod=round(o2ns/o1ns)


        # Now compute moving averages

        data=self.periodicReport(period)[['income']]
        data['moving_average']=data['income'].rolling(periodCountInMacroPeriod,min_periods=1).mean()
        data['moving_median']=data['income'].rolling(periodCountInMacroPeriod,min_periods=1).median()

#         data=data.tail(24)

#         ax = data[['moving_average']].plot(kind='line')
#         ax = data[['moving_median']].plot(kind='line', ax=ax)
#         ax = data[['income']].plot(kind='bar', ax=ax)

        return data



    def report(self, period='M', benchmark=None, output='styled',
                kpi=[
                    'rate of return','income','balance','savings',
                    'movements','shares','share_value',
                    'benchmark', 'benchmark rate of return', 'excess return'
                ]
        ):
        for p in self.periodPairs:
            if p['period']==period:
                break

        # Get bigger report with period data
        period      = self.periodicReport(p['period'], benchmark)[kpi]

        # Get summary report with summary of a period set
        macroPeriod = self.periodicReport(p['macroPeriod'], benchmark)[kpi]


        report=None

#         macroPeriod['new income']=None


        # Get income formatter
        if 'income' in self.formatters:
            incomeFormatter=self.formatters['income']['format']
        else:
            incomeFormatter=self.formatters['DEFAULT']['format']


        # Break the periodic report in chunks equivalent to the summary report
        for i in range(len(macroPeriod.index)):

            currentRange=None

            if i==0:
                line=period[:macroPeriod.index[i]]
                nPeriods=period[:macroPeriod.index[i]].shape[0]
            else:
                currentRange=(
                    (period.index > macroPeriod.index[i-1]) &
                    (period.index <= macroPeriod.index[i])
                )
                line=period[currentRange]
                nPeriods=period[currentRange].shape[0]

            # Add a row label, as '2020'
            line=pd.concat([line], axis=1, keys=[macroPeriod.index[i]])

            # Rename the title for labels so we can join latter
            line.rename_axis(['time','KPI'], axis='columns', inplace=True)

            # Convert index from full DateTimeIndex to something that can be matched
            # across macro-periods, as just '08·Aug'
            line[p['periodLabel']]=line.index.strftime(p['periodFormatter'])
            line.set_index(p['periodLabel'], inplace=True)
            line=pd.concat([line], axis=0, keys=['periods'])

            # Add to main report transposing it into a true row (we were columns until now)
            if report is not None:
                report=report.append(line.T, sort=True)
            else:
                report=line.T

            # Make the 'income' value of summary report the average multiplied
            # by number of periods
            if 'income' in kpi:
                macroPeriod.loc[macroPeriod.index[i],'new income']='{n} × {inc}'.format(
                    n=nPeriods,
                    inc=incomeFormatter.format(
                        macroPeriod.loc[macroPeriod.index[i],'income']/nPeriods
                    )
                )

        if 'income' in kpi:
            macroPeriod['income']=macroPeriod['new income']

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

        if output=='flat':
            ## Convert all to object to attain more flexibility per cell
            out=report.astype(object)

        if output=='styled':
            ## Convert all to object to attain more flexibility per cell
            out=report.style


        for i in kpi:
            for g in ['periods', 'summary of periods']:
                # Select formatter for KPI
                if i in self.formatters:
                    if g=='summary of periods' and 'summaryFormat' in self.formatters[i]:
                        f=self.formatters[i]['summaryFormat']
                    else:
                        f=self.formatters[i]['format']
                else:
                    if g=='summary of periods' and 'summaryFormat' in self.formatters['DEFAULT']:
                        f=self.formatters['DEFAULT']['summaryFormat']
                    else:
                        f=self.formatters['DEFAULT']['format']

                selector=pd.IndexSlice[
                    # Row selector
                    pd.IndexSlice[:,i],

                    # Column selector
                    pd.IndexSlice[g,:]
                ]

                if output=='flat':
                    out.loc[selector]=out.loc[selector].apply(
                        lambda s: [f.format(x) for x in s]
                    )
                elif output=='styled':
                    out=out.format(formatter=f, subset=selector, na_rep='')

        if output=='styled':
            # Styled report is ready to go
            return out



        # Final clenaup for flat
        out.replace(['nan','nan%'],'', inplace=True)
        out.index=['·'.join((k,p)).strip() for (p,k) in out.index.values]
        level=out.loc[:,pd.IndexSlice['summary of periods',:]].columns.values[0][1]
        out.rename(columns={level:'summary of periods'},inplace=True)
        out.columns=out.columns.droplevel(0)



        return out



    def pseudoRandomUniqueSeconds(self):
        # Cycle over self.twoMinutes which has 118 entries (0 to 117) with random
        # seconds in the range [-59..-1, 1..59]
        i=0
        while i<118:
            yield self.twoMinutes[i]
            i+=1
            if (i==118):
                i=0


    def getPeriodPairs():
        return [p['period'] for p in Fund.periodPairs]

    def getPeriodPairLabel(period):
        for p in Fund.periodPairs:
            if p['period']==period:
                return '{p1} & {p2}'.format(p1=p['periodLabel'],p2=p['macroPeriodLabel'])



