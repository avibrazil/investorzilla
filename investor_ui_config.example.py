import investor
import investor.currency.brasil_banco_central        as currency_bcb
import investor.currency.cryptocompare               as currency_cryptocompare
import investor.marketindex.brasil_banco_central     as mktidx_bcb
import investor.marketindex.federal_reserve          as mktidx_fred
import investor.marketindex.yahoo_finance            as mktidx_yahoo


# Get your API key at https://www.cryptocompare.com/cryptopian/api-keys
crypto_compare_apiKey = 'b1....123',


context = dict(
    # The «?check_same_thread=False» is important for SQLite multithreading support
    cache_database       = 'sqlite:///investor.cache?check_same_thread=False',

    portfolio            = [
        dict(
            klass                 = investor.GoogleSheetsBalanceAndLedger,
            params = dict(
                # Get Google Sheets API access credentials at https://console.cloud.google.com/apis/credentials/oauthclient/
                credentialsFile   = 'credentials.json',
                sheetStructure    = dict(
                    # In here you describe how your Google sheet contains the balance and the ledger sheets

                    # The ID of your Google Sheet
                    sheet='1i...HEtBIv...E2Vyo...yJRso',

                    # The sheet/tab with your balances
                    balance=dict(
                        # The tab/sheet and range
                        sheetRange='Balance!A:D',

                        # Columns description
                        columns=dict(
                            # Time is in column called 'Data'
                            time='Date',

                            # Name of fund on that row is under this column
                            fund='Compound fund',

                            # Column called 'Saldo USD' contains values in 'USD' and so on.
                            monetary=[
                                # (currency name, column name)
                                ('BRL','Balance BRL'),
                                ('USD','Balance USD')
                            ]
                        )
                    ),


                    # The sheet/tab with all your in and out movements (ledger)
                    ledger=dict(
                        # The tab/sheet and range
                        sheetRange='Ins and Outs!A:E',

                        # Columns description
                        columns=dict(
                            # Time is in column called 'Data'
                            time='Date',

                            # Name of fund on that row is under this column
                            fund='Compound fund',

                            # A column with your random comments
                            comment='Comment',

                            # Column called 'Saldo USD' contains values in 'USD' and so on.
                            monetary=[
                                # (currency name, column name)
                                ('BRL','Moviment BRL'),
                                ('USD','Moviment USD')
                            ],
                        )
                    )
                ),
            )
        )
    ],

    currency_converters  = [
        dict(
            # USD➔BRL
            klass                 = currency_bcb.BCBCurrencyConverter,
            params = dict(
                currencyFrom='USD',
            )
        ),
        dict(
            # EUR➔BRL
            klass                 = currency_bcb.BCBCurrencyConverter,
            params=dict(
                currencyFrom='EUR',
            )
        ),
        dict(
            # USD➔BTC
            klass                 = currency_cryptocompare.CryptoCompareCurrencyConverter,
            params=dict(
                currencyFrom      = 'BTC',
                apiKey            = crypto_compare_apiKey
            )
        ),
        dict(
            # USD➔ETH
            klass                 = currency_cryptocompare.CryptoCompareCurrencyConverter,
            params=dict(
                currencyFrom      = 'ETH',
                apiKey            = crypto_compare_apiKey
            )
        ),
    ],

    benchmarks           = [
        dict(
            kind                  = 'from_currency_converter',
            from_to               = 'BRLUSD'
        ),
        dict(
            kind                  = 'from_currency_converter',
            from_to               = 'USDBRL'
        ),
        dict(
            kind                  = 'from_currency_converter',
            from_to               = 'BTCUSD'
        ),
        dict(
            klass                 = mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='IPCA',
            )
        ),
        dict(
            klass                 = mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='CDI',
            )
        ),
        dict(
            klass                 = mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='SELIC',
            )
        ),
        dict(
            klass                 = mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='IGPM',
            )
        ),
        dict(
            klass                 = mktidx_bcb.BCBMarketIndex,
            params=dict(
                name='INPC',
            )
        ),
        dict(
            klass                 = mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^BVSP',
                friendlyName='Índice BoVESPa (^BVSP)',
                currency='BRL',
            )
        ),
        dict(
            klass                 = mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^GSPC',
                friendlyName='S&P 500 (^GSPC)',
            )
        ),
        dict(
            klass                 = mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^DJI',
                friendlyName='Dow Jones (^DJI)',
            )
        ),
        dict(
            klass                 = mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^IXIC',
                friendlyName='NASDAQ (^IXIC)',
            )
        ),
        dict(
            kind                  = mktidx_yahoo.YahooMarketIndex,
            params=dict(
                name='^IXIC',
                friendlyName='NASDAQ (^IXIC)',
            )
        )
    ]
)