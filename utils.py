# from instabot import Bot
import nltk
nltk.download('stopwords')
nltk.download('punkt')
from nltk.corpus import stopwords
from collections import Counter
import re
import plotly.express as px

import pandas as pd
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

import os
from dotenv import load_dotenv

load_dotenv()
PostgreSQL_PW = os.getenv('PostgreSQL_PW')

def postgres_parser():
    # Connect to PostgreSQL DBMS
    con = psycopg2.connect(dbname='reviews', user='postgres', password=PostgreSQL_PW, host='localhost', port='5432');
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT);

    # Obtain a DB Cursor
    cursor = con.cursor();

    # Create table statement
    sql = "select * from cx_reviews"

    # Create a table in PostgreSQL database
    cursor.execute(sql)

    data = cursor.fetchall()

    cols = []
    for d in cursor.description:
        cols.append(d[0])

    df = pd.DataFrame(data=data, columns=cols)

    return df


def sunburst(df, name):

    df = df[df['name']==name]
    df['review'] = df['review'].str.replace('(Translated by Google)', '')
    # preprocess
    df_groupby = df.groupby(by='rating').count()['review']
    df_groupby = df_groupby / sum(df_groupby)

    df_viz = df_groupby.reset_index()
    df_viz = df_viz.rename(columns={"rating": "item", "review": "weight"})
    df_viz['parent'] = name.split(" ")[0]

    # Find the ten most common words
    for i in range(1, 6):
        try:
            context = df[(df['rating'] == i) & ~df['review'].isna()]['review'].str.lower().tolist()[0]
            context = ''.join([i for i in context if not i.isdigit()])

            words = re.findall(r'\w+', context)
            words = [word for word in words if not word in stopwords.words()]

            temp = pd.DataFrame(Counter(words).most_common(5), columns=['item', 'weight'])

            temp.item = temp.item + '_' + str(i)

            temp['weight'] = temp['weight'] * float(df_groupby[i]) / sum(temp['weight'])
            temp['parent'] = i

            df_viz = pd.concat([df_viz, temp])
        except Exception as e:
            print(e)

    df_viz = df_viz.reset_index(drop=True)

    # show sunburst graph
    data = dict(
        character=df_viz['item'].tolist(),
        parent=df_viz['parent'].tolist(),
        value=df_viz['weight'].tolist())

    fig = px.sunburst(
        data,
        names='character',
        parents='parent',
        values='value',
        branchvalues='total',
        height=700
    )

    fig.write_image("sunburst.jpeg")

    return
