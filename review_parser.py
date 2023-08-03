from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By

import time
from bs4 import BeautifulSoup

# As there are possibilities of different chrome
# browser and we are not sure under which it get
# executed let us use the below syntax
from selenium.webdriver.chrome.options import Options
import pandas as pd

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

import os
from dotenv import load_dotenv

load_dotenv()
PostgreSQL_PW = os.getenv('PostgreSQL_PW')

def postgres_upload(request):

    print("start postgres uploading...")

    # Connect to PostgreSQL DBMS
    con = psycopg2.connect(dbname='reviews', user='postgres', password=PostgreSQL_PW, host='localhost', port='5432');
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT);

    # Obtain a DB Cursor
    cursor = con.cursor();

    # request = 'SEEN RESTAURANT'
    with open(f'{request}.csv', 'r') as f:
        next(f)

        copy = "COPY cx_reviews(review, rating, date, name, review_number, average_rating, category, search, insert_date) FROM STDIN with csv"
        cursor.copy_expert(sql=copy, file=f)
        con.commit()

    print("uploading successfully")

    os.remove(f'{request}.csv')

    print(f"{request}.csv has been removed successfully")

    return


def google_review_parser(df, request):
    print("start review parser...")

    options = Options()
    # options.add_argument('--headless')
    options.add_argument("--window-size=100,100")

    # for docker use
    # driver = webdriver.Remote("http://selenium:4444/wd/hub",
    #                           DesiredCapabilities.CHROME, options=options)

    # for local use
    serv = webdriver.chrome.service.Service('./config/chromedriver')
    driver = webdriver.Chrome(service=serv, options=options)

    # search
    search = '+'.join(request.split(' '))

    url = f'https://www.google.com/maps/place/{search}/?hl=en'
    driver.get(url)

    # process of parsing reviews
    driver.find_element(by=By.XPATH,
                        value='//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[1]/div[3]/div[1]/div[1]/form[2]/div/div/button/span').click()
    time.sleep(4)

    # button
    driver.find_element(by=By.XPATH,
                        value='//*[@id="searchbox-searchbutton"]').click()
    time.sleep(2)

    # get url location
    info_text = driver.find_element(by=By.XPATH,
                                   value='//*[@id="QA0Szd"]').text
    info = info_text.split('\n')
    name = info[0]

    if 'reviews' in info_text:
        info = [x for x in info if "·" not in x]
        for count, i in enumerate(info):
            try:
                if '.' in str(i):
                    average_rating = float(i[:3])
                    category = info[count+2]

                if 'reviews' in str(i):
                    i = i.replace(',', '')
                    reviews_count = int(i[:-8])
                    break

            except Exception as e:
                print(e)

    if df[df['name'] == name].empty:

        # button
        try: #//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[58]/div/button/span/span[2]
            driver.find_element(By.XPATH, "//*[@id='QA0Szd']/div/div/div[1]/div[2]/div/div[1]/div/div/div[58]/div/button").click()

            # driver.find_element(By.XPATH, "//*[@id='QA0Szd']/div/div/div[1]/div[2]/div/div[1]/div/div/div[56]/div/button").click()
        except Exception as e:
            print(e)
            driver.find_element(By.XPATH, "//*[@id='QA0Szd']/div/div/div[1]/div[2]/div/div[1]/div/div/div[55]/div/button").click()

        time.sleep(2)

        scrollable_div = driver.find_element(By.XPATH, "//*[@id='QA0Szd']/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]")

        # Scroll as many times as necessary to load all reviews
        for i in range(50):
            more = driver.find_elements(by=By.XPATH,
                                        value='//*[@aria-label=" See more "]')
            for m in more:
                m.click()
            driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight',
                                  scrollable_div)
            time.sleep(2)

        # extract reviews by BeatifulSoup
        response = BeautifulSoup(driver.page_source, 'html.parser')
        texts = response.find_all('span', class_='wiI7pd')
        rates = response.find_all('div', class_='DU9Pgb')

        def get_review_summary(text_set, rates):
            rev_dict = {'review': [],
                        'rating': [],
                        'date': [],
                        'name': [],
                        'review_number': [],
                        'average_rating': [],
                        'category': []}
            for text, rate in zip(text_set, rates):
                review_rate = rate.find('span', class_='kvMYJc')["aria-label"].strip()[0]
                review_time = rate.find('span', class_='rsqaWe').text
                review_text = text.text
                rev_dict['rating'].append(review_rate)
                rev_dict['date'].append(review_time)
                rev_dict['review'].append(review_text)
                rev_dict['name'].append(name)
                rev_dict['review_number'].append(reviews_count)
                rev_dict['average_rating'].append(average_rating)
                rev_dict['category'].append(category)

            return (pd.DataFrame(rev_dict))

        def get_review_summary_v2(text_set, rates):
            rev_dict = {'review': [],
                        'rating': [],
                        'date': [],
                        'name': [],
                        'review_number': [],
                        'average_rating': [],
                        'category': []}
            for text, rate in zip(text_set, rates):
                review_rate = rate.find('span', class_='fzvQIb').text[0]
                review_time = rate.find('span', class_='xRkPPb').text.split(' on ')[0].strip()
                review_text = text.text
                rev_dict['rating'].append(review_rate)
                rev_dict['date'].append(review_time)
                rev_dict['review'].append(review_text)
                rev_dict['name'].append(name)
                rev_dict['review_number'].append(reviews_count)
                rev_dict['average_rating'].append(average_rating)
                rev_dict['category'].append(category)

            return (pd.DataFrame(rev_dict))

        try:
            df = get_review_summary(texts, rates)

        except Exception as e:
            print(e)
            print('somehow google has different version of webpage...')
            df = get_review_summary_v2(texts, rates)

        from datetime import date

        df['search'] = request
        df['insert_date'] = date.today()

        df.to_csv(f'review.csv', index=False)

        # upload parsed reviews
        postgres_upload('review')

    else:
        print("have parsed before")

    return name



