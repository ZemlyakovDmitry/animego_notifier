# -*- coding: utf-8 -*-

import re
import time
import json
import logging
import requests
import aiohttp
import tldextract
import config as cfg
import sqlite3 as sql

from lxml import html
from vkwave.bots import SimpleLongPollBot

filename = './log_bot.txt'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest'}  # 2nd header is very important, server returns an 500 error if request was sent without it
bot = SimpleLongPollBot(tokens=cfg.token, group_id=cfg.vkid)
logging.basicConfig(filename=filename, level=logging.DEBUG)


@bot.message_handler(bot.text_contains_filter(["/add"]))
async def addanime(event: bot.SimpleBotEvent) -> str:
    try:
        conn = sql.connect('database.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM animes")
        args = event.object.object.message.text.split()
        url = str(args[1])
        ext = tldextract.extract(url)
        last_episode = args[2]
        if ext.domain != 'animego':
            await event.answer("Это не animego.org")
        if last_episode.isnumeric() == False: # domain and episode validation
            await event.answer("Укажите корректную серию")
        if ext.domain == 'animego':
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status_code != 200:
                        await event.answer('Не удалось получить страницу, попробуйте проверить данные')
                    else:
                        tree = html.fromstring(response.content)
                        title = (str(tree.xpath("//*[@id='content']/div/div[1]/div[2]/div[2]/div/h1/text()"))[2:-2])  # Searching for an anime title using XPath
                        last_episode = int(args[2])
                        anime_url = url.replace("/", "")  # removing all slashes
                        id = str(re.findall('^.*\-(.*)\.*', anime_url))[3:-2]  # getting id of the anime
                        cur.execute("INSERT OR IGNORE INTO animes VALUES (?, ?, ?, ?)", (title, last_episode, url, id))
                        conn.commit()
                        conn.close()
                        await event.answer('Добавил аниме "' + title + '" его id = ' + id)
    except Exception as e:
        await event.answer("Произошла ошибка, убедитесь в правильности переданных параметров(")
        logging.error(e, exc_info=True)


@bot.message_handler(bot.text_contains_filter(["/delete"]))
async def deleteanime(event: bot.SimpleBotEvent) -> str:
    try:
        args = event.object.object.message.text.split()
        url = str(args[1])
        conn = sql.connect('database.db')
        cur = conn.cursor()
        cur.execute("DELETE FROM animes where url=?", (url,))
        conn.commit()
        conn.close()
        return ("Удалил это аниме")
    except Exception as e:
        await event.answer("а где ссылка????????? (или что-то другое не так)")
        logging.error(e, exc_info=True)


@bot.message_handler(bot.text_contains_filter(["/startnotifying"]))
async def start_notifying(event: bot.SimpleBotEvent) -> str:
    try:
        await event.answer("Начал уведомление")
        while True:
            conn = sql.connect('database.db')
            cur = conn.cursor()
            cur.execute("SELECT * FROM animes")
            anime_list = cur.fetchall()
            for anime in anime_list:
                id, url, title, last_episode = anime
                page = requests.get('https://animego.org/anime/' + str(id) + '/player?_allow=true', headers=headers)
                jsonData = json.loads(page.text)
                a = jsonData["content"]
                tree = html.fromstring(a)
                next_episode = last_episode + 1
                episode = str(next_episode)
                value = str(tree.xpath('//option[text() = "' + episode + ' серия"]/@value'))[2:-2]
                dubs = requests.get(
                    'https://animego.org/anime/series?dubbing=2&provider=24&episode=' + episode + '&id=' + value,
                    headers=headers).json()['content']
                if 'Студийная' or 'AniLibria' in dubs:
                    last_episode = next_episode
                    cur.execute("UPDATE animes SET last_episode=? WHERE url=?", (last_episode, url))
                    conn.commit()
                    await event.answer((str(int(episode) - 1)) + " серия " + title + " вышла!\n" + url)
            conn.close()
            time.sleep(300)
    except Exception as e:
        await event.answer("An error occurred. Check logs for additional info.")
        logging.error(e, exc_info=True)


@bot.message_handler(bot.text_contains_filter(["/list"]))
async def list(event: bot.SimpleBotEvent) -> str:
    try:
        str1 = ''
        conn = sql.connect('database.db')
        cur = conn.cursor()
        cur.execute("SELECT title, last_episode, url FROM animes")
        name = str1.join(str(cur.fetchall()))
        first = name.replace("), (", ")\n(").replace("'", "")
        conn.close()
        try:
            print(first)
            if len(first) < 4:
                await event.answer('Пусто')
            else:
                await event.answer(str(first)[1:-1])
        except Exception as e:
            await event.answer("An error occurred. Check logs for additional info. ")
            logging.error(e, exc_info=True)
    except Exception as e:
        await event.answer("An error occurred. Check logs for additional info.")
        logging.error(e, exc_info=True)


@bot.message_handler(bot.text_contains_filter(["брат, ты живой?"]))
async def alive(event: bot.SimpleBotEvent) -> str:
    try:
        await event.answer('да брат')
    except Exception as e:
        logging.error(e, exc_info=True)


bot.run_forever()