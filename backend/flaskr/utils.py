import os
import psycopg2
from psycopg2 import Error, sql
from datetime import date
import yfinance as yahoo
from forex_python.converter import CurrencyRates
from dotenv import load_dotenv

env = os.getenv("ENV")
load_dotenv(f".env.{env}")


def lorem_ipsum():
    data = {
        "message": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec lobortis condimentum arcu quis bibendum. Phasellus lacinia nisl non diam bibendum fringilla. Pellentesque quis justo tincidunt, lobortis elit a, egestas felis. Cras non eleifend sem. Donec non auctor mauris. Proin imperdiet nisi vel condimentum ultrices. Etiam non quam mi. In vel porta sapien. Nullam pulvinar id tellus nec sodales. Nunc faucibus a sapien ullamcorper lacinia. Aenean at porttitor orci. Donec ac massa id elit rutrum fringilla sed sed nunc. Ut dapibus dolor libero, eu mollis mi suscipit ut."
    }
    return data


def connect_to_db():
    """
    Function to connect to the database
    Returns: connection object

    Example of use:\n
    connection = utils.connect_to_db()\n
    cursor = connection.cursor()\n
    cursor.execute("SELECT * FROM table_name")\n
    cursor.fetchall()\n
    cursor.close()
    """
    try:
        connection = psycopg2.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_DATABASE"),
        )

        print("Connected to Database")
        return connection

    except (Exception, Error) as error:
        print("Error while connecting to PostgreSQL", error)
        return None


def process_stock_data(tickers):
    """
    Function to process stock data from the Yahoo Finance API
    """
    current_date = date.today()
    stock_data = []

    for ticker in tickers.tickers.values():
        try:
            stock_data.append(
                {
                    "ticker": ticker.info["symbol"],
                    "name": ticker.info["shortName"],
                    "market_cap": ticker.info["marketCap"],
                    "currency": ticker.info["financialCurrency"],
                    "date": current_date,
                    "sector": ticker.info["sector"],
                    "website": ticker.info["website"],
                }
            )
        except KeyError:
            print("Failed to get market cap information on {}", ticker.ticker["symbol"])
            continue

    return stock_data


def get_stock_data(stocks):
    """
    Takes a space-separated string of tickers/symbols as the parameter
    and returns a list of objects containing the stock data needed in the DB
    used in database upserts
    """
    tickers = yahoo.Tickers(stocks)
    stock_data = process_stock_data(tickers)

    return stock_data


def upsert_stock_data(data):
    """
    Function for upserting stock data into the "company" table in the database.
    """
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            for row in data:
                # Construct SQL query
                query = sql.SQL(
                    """
                    INSERT INTO Company (ticker, name, market_cap, currency, date, sector, website)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker) DO UPDATE
                    SET market_cap = EXCLUDED.market_cap,
                        date = EXCLUDED.date,
                        currency = EXCLUDED.currency,
                        website = EXCLUDED.website;
                """
                )
                # Execute the query
                cursor.execute(
                    query,
                    (
                        row["ticker"],
                        row["name"],
                        row["market_cap"],
                        row["currency"],
                        row["date"],
                        row["sector"],
                        row["website"],
                    ),
                )

            conn.commit()


def get_currencies_from_database():
    """
    Function to get all currencies from the database.
    """
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT currency FROM Company;")
            currencies = cursor.fetchall()
            currencies = [currency[0] for currency in currencies]
    return currencies


def process_currency_data(existing_currencies, rates):
    needed_currency_rates = [
        {currency: rates[currency]}
        for currency in existing_currencies
        if currency != "USD"
    ]
    return needed_currency_rates


def get_exchange_rates_from_api():
    """
    Function for getting exchange rates from Forex API.
    """
    existing_currencies = get_currencies_from_database()
    c = CurrencyRates()
    rates = c.get_rates("USD")
    processed_currencies = process_currency_data(existing_currencies, rates)

    return processed_currencies


def upsert_exchange_rates(data):
    """
    Function for upserting exchange rates into the "exchange_rate" table in the database.
    """
    current_date = date.today()
    with connect_to_db() as conn:
        with conn.cursor() as cursor:
            for row in data:
                currency = list(row.keys())[0]
                # Revert the exchange rate to get the rate from the currency to USD
                rate = 1 / row[currency]
                # Construct SQL query
                query = sql.SQL(
                    """
                    INSERT INTO ExchangeRates (from_currency, to_currency, ratio, date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (from_currency, to_currency) DO UPDATE
                    SET ratio = EXCLUDED.ratio;
                """
                )
                # Execute the query
                cursor.execute(query, (currency, "USD", rate, current_date))
            conn.commit()


def get_companies_from_database(
    count=10, exclude_companies=[], wanted_categories=[], wanted_currency="USD"
):
    """
    Function for getting companies from database

    Params:
            count:              How many companies are needed
                                (int)
            exclude_companies:  Companies that needs to be excluded from search
                                (array of tickers)
            wanted_categories:   Companies that needs to appear in search.
                                If only these companies are needed, set the count to be exactly the amount of items in this array.
                                (array of tickers)
            wanted_currency:    Currency that market_cap value needs to be in
                                (str)
    Returns:
            Array of dictionaries of company data
    """
    with connect_to_db() as conn:
        with conn.cursor() as cursor:

            # Construct SQL query
            query_string = f"SELECT * FROM Company"

            if len(exclude_companies) != 0:
                query_string += f" WHERE ticker NOT IN ("
                for ticker in exclude_companies:
                    query_string += ticker
                query_string += ")"

            if len(exclude_companies) != 0 and len(wanted_categories) != 0:
                query_string += f" AND sector IN ("
                for sector in wanted_categories:
                    query_string += sector
                query_string += ")"

            if len(exclude_companies) == 0 and len(wanted_categories) != 0:
                query_string += f" WHERE sector IN ("
                for sector in wanted_categories:
                    query_string += sector
                query_string += ")"

            query_string += f" ORDER BY RANDOM() LIMIT {count};"

            query = sql.SQL(query_string)

            # Execute the query
            cursor.execute(query)

            company_data = cursor.fetchall()

            # TODO: Another query here to fetch the exchange rates and then update those to the final

            # List of companies
            company_array = [
                {
                    "ticker": company[1],
                    "name": company[2],
                    "market_cap": company[3],
                    "currency": company[4],  # TODO: make currency convertion here
                    "date": company[5],
                    "sector": company[6],
                    "website": company[7],
                }
                for company in company_data
            ]

    breakpoint()
    return company_array


upsert_stock_data(get_stock_data("AAPL AMD GOOGL"))
get_companies_from_database()
