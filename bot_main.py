import discord
from discord.ext import tasks

import asyncio

from dotenv import load_dotenv
from utils import *
from review_parser import *
from valuation import *
from cooking_suggest import *

import datetime

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

load_dotenv()
TOKEN = os.getenv('TOKEN')

@client.event
async def on_message(message):
    # cooking suggestion support
    if message.content.startswith('$cook'):
        try:
            await message.channel.send(content="Please wait for the process...")
            # download user requests
            # request = message.content[4:]
            # print(request)

            # download google review database
            suggestion = cooking_suggest()
            await message.channel.send(content=suggestion)

        except Exception as e:
            print(e)
            await message.channel.send(content="Error... Please be more specific and try again")

    # cx support
    if message.content.startswith('$cx '):
        try:
            await message.channel.send(content="Please wait for the process...")
            # download user requests
            request = message.content[4:]
            print(request)

            # download google review database
            df = postgres_parser()

            # search = 'SEEN RESTAURANT'
            name = google_review_parser(df, request)

            # download google review database
            df_new = postgres_parser()

            # create sunburst
            sunburst(df_new, name)

            file = discord.File("image/sunburst.jpeg")
            await message.channel.send(file=file, content="Here is your 5* rating NLP analysis")

        except Exception as e:
            print(e)
            await message.channel.send(content="Error... Please be more specific and try again")

    # 13F
    if message.content.startswith('$13f'):
        try:
            await message.channel.send(content="Please wait for the process...")

            filing13f = Filing13F()

            # specific sub-methods
            if message.content.startswith('$13fvalue'):
                filing13f.value_plot()
                file = discord.File("image/13f_price_delta.jpeg")
                await message.channel.send(file=file, content="Here is your 13F status report")

            else:
                # download user requests
                cik = message.content.split(' ')[1]
                print(cik)

                filing13f.status_report(institution_id=cik)

                file = discord.File("image/share_%change.jpeg")
                await message.channel.send(file=file, content="Here is your 13F status report")

        except Exception as e:
            print(e)
            await message.channel.send(content="Error... Please be more specific and try again")

    # npv
    if message.content.startswith('$npv'):
        try:
            await message.channel.send(content="Please wait for the process...")
            # download user requests
            ticker = message.content.split(' ')[1]
            print(ticker)

            # specific sub-methods
            if message.content.startswith('$npvcape'):
                npv_reply = stock_price_target(ticker)
            else:
                npv_reply = stock_price_target(ticker, CAPE=False, SEC_13F=False)

            print(npv_reply)
            await message.channel.send(npv_reply)

        except Exception as e:
            print(e)
            await message.channel.send(content="Error... Please type a correct ticker and try again")

    # bot interaction
    if message.content.startswith('$roic'):
        try:
            await message.channel.send(content="Please wait for the process...")
            # download user requests
            ticker = message.content.split(' ')[1]
            print(ticker)

            # specific sub-methods
            if message.content.startswith('$roicq'):
                roic_reply = intrinsic_value_quarterly(ticker)
            else:
                roic_reply = intrinsic_value(ticker)

            print(roic_reply)

            await message.channel.send(roic_reply)

        except Exception as e:
            print(e)
            await message.channel.send(content="Error... Please type a correct ticker and try again")

    # value each stock in the ETF
    if message.content.startswith('$value'):
        try:
            await message.channel.send(content="Please wait for the process...")

            # specific sub-methods
            if message.content.startswith('$valueETF'):

                # https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average
                data_frames = pd.read_html(io='https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', index_col=0)
                df_etf = pd.DataFrame({'Symbol': data_frames[0].index, 'Security': data_frames[0].Security})

                tickers = ['ALV.DE', 'AMZN', 'AAPL', 'MSFT', 'TSM'] + df_etf['Symbol'].tolist()
                securities = ['ALV.DE', 'AMZN', 'AAPL', 'MSFT', 'TSM'] + df_etf['Security'].tolist()

                for ticker, security in zip(tickers, securities):
                    try:
                        print(f"{security}")
                        npv_reply = stock_price_target(ticker, CAPE=False, SEC_13F=False)
                        print(npv_reply)

                        if "Good Bargain" in npv_reply:
                            await message.channel.send(f"{security} | {npv_reply}")

                            # roic_reply = intrinsic_value(ticker)
                            # print(roic_reply)
                            # await message.channel.send(f"{roic_reply}")
                            #
                            # roicq_reply = intrinsic_value_quarterly(ticker)
                            # print(roicq_reply)
                            # await message.channel.send(f"{roicq_reply}")

                    except Exception as e:
                        print(e)

            else:

                # download user requests
                ticker = message.content.split(' ')[1]
                print(ticker)

                npv_reply = stock_price_target(ticker)
                print(npv_reply)

                await message.channel.send(f"{npv_reply}")

                roic_reply = intrinsic_value(ticker)
                print(roic_reply)

                await message.channel.send(f"{roic_reply}")

                roicq_reply = intrinsic_value_quarterly(ticker)
                print(roicq_reply)

                await message.channel.send(f"{roicq_reply}")

        except Exception as e:
            print(e)
            await message.channel.send(content="Error... Please type a correct ticker and try again")

@client.event
async def on_connect():
    print("Bot connected to the server")


async def notification_13f():
    while True:
        now = datetime.datetime.now()
        then = now.replace(hour=23, minute=0)
        wait_time = (then - now).total_seconds()
        if wait_time <= 0:
            wait_time = 3600
            print(wait_time, then)
            await asyncio.sleep(wait_time)
            return

        print(wait_time)
        await asyncio.sleep(wait_time)

        print("notification_13f")

        # download user requests
        cik = '0001067983'
        print(cik)

        filing13f = Filing13F()
        filing13f.status_report(institution_id=cik)

        file = discord.File("image/share_%change.jpeg")
        user = await client.fetch_user("707293423711027262")
        await user.send(file=file, content="Here is your 13F status report")
        # channel = client.get_channel(1030160389582889001)
        # await channel.send(file=file, content="Here is your 13F status report")

        print('13F Update')


@client.event
async def on_ready():
    print("Ready")


if __name__ == '__main__':

    # client.run(TOKEN)

    print(cooking_suggest())
    print(stock_price_target('AMZN', CAPE=False, SEC_13F=False))

    now = datetime.datetime.now()
    print(now.year-1)
