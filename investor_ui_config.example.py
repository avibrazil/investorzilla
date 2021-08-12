context=dict(
    cache_file='cache.db',

    # Get your API key here https://www.cryptocompare.com/cryptopian/api-keys
    crypto_compare_apiKey='b1b9...f7123',

    google_credentials_file='credentials.json',


    # In here you describe how your Google sheet has the balance and the ledger sheets
    finance_sheet_structure=dict(
        # The ID of you Google Sheet (take it from the GSheet URL)
        sheet='1i...Rso',

        # The sheet/tab with your balances
        balance=dict(
            # The tab/sheet and range
            sheetRange='Saldos!A:D',

            # Columns description
            columns=dict(
                # Time is in column called 'Data'
                time='Data',

                # Name of fund on that row is under this column
                fund='Fundo composto',

                # Column called 'Saldo USD' contains values in 'USD' and so on.
                monetary=[
                    # (currency name, column name)
                    ('BRL','Saldo BRL'),
                    ('USD','Saldo USD')
                ]
            )
        ),


        # The sheet/tab with all your in and out movements (ledger)
        ledger=dict(
            # The tab/sheet and range
            sheetRange='Entradas e saidas brutas!A:E',

            # Columns description
            columns=dict(
                # Time is in column called 'Data'
                time='Data',

                # Name of fund on that row is under this column
                fund='Fundo composto',

                # A column with your random comments
                comment='Comentário',

                # Column called 'Saldo USD' contains values in 'USD' and so on.
                monetary=[
                    # (currency name, column name)
                    ('BRL','Movimento BRL'),
                    ('USD','Movimento USD')
                ],
            )
        )
    )
)