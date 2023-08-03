import requests as req
from bs4 import BeautifulSoup
import re
import os

# search recipe
from apiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('API_KEY')

def cooking_suggest():
    url = "https://www.lidl.de/c/billiger-montag/a10006065?channel=store&tabCode=Current_Sales_Week"
    page = req.get(url)

    # target meat and veg
    fleisch = page.text.split('Fleisch für Genießer')[-1]

    # bs4
    soup = BeautifulSoup(fleisch, 'html.parser')
    class_match = soup.find_all(class_='ACampaignGrid__item ACampaignGrid__item--product')

    # extract bargain item
    regex = re.compile(r'(?<=fulltitle=")[^"]+')
    lang_food = regex.search(str(class_match))[0]
    print(lang_food)

    regex = re.compile(r'(?<=oldPrice":)\d.\d+')
    old_price = regex.search(str(class_match))[0]
    print('old_price', old_price)

    regex = re.compile(r'(?<=price":)\d.\d+')
    price = regex.search(str(class_match))[0]
    print('price', price)

    regex = re.compile(r'(?<=image=")[^"]+')
    image = regex.search(str(class_match))[0]
    print(image)

    # to search
    food = lang_food.split(' ')[-1]
    print(food)

    # connect with website
    cx_id = '677fa68d5f7584cc3'
    resource = build("customsearch", 'v1', developerKey=API_KEY).cse()
    result = resource.list(q='Puten-Mini-Filets', cx=cx_id).execute()
    title = result['items'][0]['title']
    print(title)
    rezepte = result['items'][0]['link']

    suggestion = f"Bargain Food This Week from Lidl = \n{lang_food}\n" \
                f"- Old Price = {old_price}\n" \
                f"- Price = {price}\n" \
                f"- Image = {image}\n" \
                f"- Rezepte = {rezepte}\n" \
                f"- Title = {title}"

    return suggestion
