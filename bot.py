# -*- coding: utf-8 -*-

import config as cfg
import json
import mysql.connector
import re
import requests
import threading
import time
import tldextract

from bs4 import BeautifulSoup as BS
from lxml import html
from vkwave.bots import SimpleLongPollBot, SimpleBotEvent

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest'}  # 2nd header is very important, server returns an 500 error if request was sent without it
bot = SimpleLongPollBot(tokens=cfg.token, group_id=cfg.group_id)
notify = True


def get_conn():
    try:
        conn = mysql.connector.connect(
            user="root",
            # My database is accessible only for the localhost. That's why I didn't set a very secure login/password combination.
            password="root",
            host="localhost",
            port=3306,
            charset="utf8mb4",
            database="animes"
        )
        cur = conn.cursor(buffered=True)
        return conn, cur
    except Exception as e:
        print(e)
        event.answer("Произошла ошибка подключения к БД. Повторите попытку позднее.")


@bot.message_handler(bot.text_contains_filter(["/add"]))
async def addanime(event: bot.SimpleBotEvent) -> str:
    try:
        conn, cur = get_conn()
        cur.execute("SELECT * FROM animes")
        args = event.object.object.message.text.split()
        url = str(args[1])
        ext = tldextract.extract(url)
        last_episode = args[2]
        if ext.domain != 'animego':
            await event.answer("Это не animego.org")
        if not last_episode.isnumeric():  # domain and episode validation
            await event.answer("Укажите корректную серию")
        if ext.domain == 'animego' and last_episode.isnumeric() == True:
            page = requests.get(url, headers=headers, timeout=10)
            if page.status_code != 200:
                await event.answer('Не удалось получить страницу, попробуйте проверить данные')
            else:
                tree = html.fromstring(page.content)
                title = (str(tree.xpath("//*[@id='content']/div/div[1]/div[2]/div[2]/div/h1/text()"))[
                         2:-2])  # Searching for an anime title using XPath
                last_episode = int(args[2])
                anime_url = url.replace("/", "")  # removing all slashes
                id = str(re.findall('^.*\-(.*)\.*', anime_url))[3:-2]  # getting id of the anime
                cur.execute(
                    "INSERT INTO animes (title, last_episode, url, id) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE last_episode = VALUES(last_episode)",
                    (title, last_episode, url, id))
                conn.commit()
                conn.close()
                await event.answer('Добавил аниме "' + title + '" его id = ' + id)
    except Exception as e:
        print(e)
        await event.answer("Произошла ошибка, убедитесь в правильности переданных параметров(")


@bot.message_handler(bot.text_contains_filter(["/delete"]))
async def deleteanime(event: bot.SimpleBotEvent) -> str:
    try:
        conn, cur = get_conn()
        args = event.object.object.message.text.split()
        url = str(args[1])
        cur.execute("DELETE FROM animes where url=%s", (url,))
        conn.commit()
        cur.close()
        conn.close()
        await event.answer("Удалил это аниме")
    except Exception as e:
        print(e)
        await event.answer("а где ссылка???????")


@bot.message_handler(bot.text_contains_filter(["/startnotifying"]))
async def start_notifying(event: bot.SimpleBotEvent) -> str:
    global notify
    try:
        await event.answer("Начал уведомление")
        while notify:
            conn, cur = get_conn()
            cur.execute("SELECT * FROM animes")
            anime_list = cur.fetchall()
            for anime in anime_list:
                title, last_episode, url, id = anime
                page = requests.get('https://animego.org/anime/' + str(id) + '/player?_allow=true', headers=headers)
                print(page.status_code)
                if page.status_code != '200':
                    episode = str(last_episode)
                    jsonData = json.loads(page.text)
                    a = jsonData["content"]
                    tree = html.fromstring(a)
                    value = str(tree.xpath('//option[text() = "' + episode + ' серия"]/@value'))[2:-2]
                    dubs = requests.get(
                        'https://animego.org/anime/series?dubbing=2&provider=24&episode=' + episode + '&id=' + value,
                        headers=headers).json()['content']
                    if 'Студийная' or 'AniLibria' in dubs:
                        last_episode = last_episode + 1
                        cur.execute("UPDATE animes SET last_episode=%s WHERE url=%s", (last_episode, url))
                        await event.answer((str(int(last_episode) - 1)) + " серия " + title + " вышла!\n" + url)
            conn.commit()
            cur.close()
            conn.close()
            time.sleep(300)
        vk.messages.send(peer_id=cfg.id, random_id=0, message='Stopped notifying')
    except Exception as e:
        print(e)
        await event.answer("An error occurred. Check logs for additional info.")


@bot.message_handler(bot.text_contains_filter(["/list"]))
async def list(event: bot.SimpleBotEvent) -> str:
    try:
        conn, cur = get_conn()
        str1 = ''
        cur.execute("SELECT title, last_episode, url FROM animes")
        name = str1.join(str(cur.fetchall()))
        first = name.replace("), (", ")\n(").replace("'", "")
        conn.commit()
        cur.close()
        conn.close()
        try:
            if len(first) < 4:
                await event.answer('Пусто')
            else:
                await event.answer(str(first)[1:-1])
        except Exception as e:
            print(e)
            await event.answer("An error occurred. Check console for additional info. ")
    except Exception as e:
        print(e)
        await event.answer("An error occurred. Check console for additional info.")


@bot.message_handler(bot.text_contains_filter(["брат, ты живой?"]))
async def alive(event: bot.SimpleBotEvent) -> str:
    try:
        await event.answer('да брат')
    except Exception as e:
        print(e)


bot.run_forever()
