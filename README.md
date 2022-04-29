# Personal Investments Dashboard

Classes and Streamlit app to manage a diverse investment portfolio in multiple
currencies, including crypto and market indexes.

![](pics/overview.png)

Dashboards reads your **ledger** and **balances** from an online Google
Spreadsheet ([see example](https://docs.google.com/spreadsheets/d/1AE0F_mzXTJJuuuQwPnSzBejRrmui01CfUUY1qyvnbkk)),
get historical benchmarks and currency convertion tables from multiple
configurabe internet sources, and created a rich explorable dashboard.

All or some or each of your investments are internally normalized into a single
“fund” with **number of shares** and **share value**. From there, multiple
visualizations are possible, such as:

## Install and Run
Runs on macOS, Windows, Linux or anywhere Python, Pandas and Streamlit can be
installed.

### Install
After getting Python installed, install also some requirements as:

```shell
pip3 install -r requirements.txt --user
```

### Configure
Create `investor_ui_config.yaml` file copying [`investor_ui_config.example.yaml`](blob/main/investor_ui_config.example.yaml)
and edit to your needs.

Get CryptoCompare (in case of having crypto) and Google Sheets API keys and
update on `investor_ui_config.yaml`. More instructions on
`investor_ui_config.example.yaml`. 

### Run
After installing your API keys, current configuration on the example file will
work out of the box as I left a [usable example spreadsheet](https://docs.google.com/spreadsheets/d/1AE0F_mzXTJJuuuQwPnSzBejRrmui01CfUUY1qyvnbkk)
on the web.

Run it as:

```shell
streamlit run investor_ui.py
```

Access the dashboard on http://localhost:8501

## Features

### Virtual Funds

Create a unified virtual fund with only some of the investments found in your
portfolio spreadsheet.

![](pics/virtual_fund_composer.png)

Your whole porfolio will be used if left balnk. Then you might *exclude*
some to match the particular visualization you are trying to attain.

### Currency and Benchmarks

You may track your investments using multiple currencies, inluding crypto. I
have investments in USD and BRL. You can create virtual funds that mix different
currencies, in this case you must select a currency under which you’ll view that
(virtual) fund. Values from your spreadsheet will be converted to the target
currency on a daily basis.

Also, you might compare your investment performance with market benchmarks as
S&P 500, NASDAQ index etc. Just remember to use a benchmark that matches the
current currency, otherwise comparisons won’t make sense.

![](pics/currencies_and_benchmarks.png)

### Period Selector

![](pics/period_selector.png)

If you have enough or high frequency data, you can divide time in more granular
regular periods. Default is monthy view with an anual summary.


## Graphs and Reports

![](pics/graphs.png)

Currently supports 4 graphs, from left to right, top to bottom:

1. Virtual share value performance compared to a selected benchmark
1. Periodic (monthly, weekly) gain, along with 12M moving average and moving median
1. Frequency histogram of percent return rate per period (default is per month)
1. Fund savings, balance and gains (which is pure balance minus savings)

There is also numerical reports showing:
1. Performance
    1. Periodic (monthly) rate of return with an macro-period (yearly) accumulated value
    1. Same for selecte benchmark
    1. Excess return over benchmark
    1. Periodic and accumulated gain
1. Wealth Evolution
    1. Current balance
    1. Balance over savings
    1. Cumulated gains
    1. Cumulated savings
    1. Movements on the periods, which is the sum of money added to and removed
        from virtual fund

![](pics/periodic_report.png)


## Usage Tips
1. Select a custom period on the slider
1. View your main metrics on top of report
1. To optimize screen usage, on the the top right menu, select **Settings** and then **Wide mode**
1. Hide the left panel to gain even more screen real estate
1. Use **Refresh data** buttons to update local cache with latest info from your
   **porfolio spreadsheet**, **market data** or **both**.


