# -*- coding: utf-8 -*-

# TODO: добавить в бд id. Ссылку убрать до '-', последние цифры занести как id
# TODO: value получается в заросе https://animego.org/anime/id/player?_allow=true, где id из todo выше

import re
import time
import json
import vk_api
import asyncio
import requests
import config as cfg
import sqlite3 as sql
from lxml import html
from bs4 import BeautifulSoup as BS
from vk_api.longpoll import VkLongPoll, VkEventType

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36', 'x-requested-with': 'XMLHttpRequest'}  # 2nd header is very important, server returns an 500 error without it

vkSession = vk_api.VkApi(token=cfg.token)
longpoll = VkLongPoll(vkSession)
vk = vkSession.get_api()
notify = True

def add(url, last_episode):
    conn = sql.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM animes where url=?", (url,))
    page = requests.get(url, headers=headers, timeout=10)
    tree = html.fromstring(page.content)
    title = (str(tree.xpath("//*[@id='content']/div/div[1]/div[2]/div[2]/div/h1/text()"))[2:-2])  # Find anime title by XPath
    if title is None:
        print('404')
    anime_url = url.replace("/", "")  # used to remove all slashes
    id = str(re.findall('^.*\-(.*)\.*', anime_url))[3:-2]
    # ^.*\-(.*)\.*
    cur.execute("INSERT INTO animes VALUES (?, ?, ?, ?)", (id, url, title, last_episode))
    conn.commit()
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Added ' + title + ' with id ' + id )
    conn.close()

def delete(url):
    conn = sql.connect('database.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM animes WHERE url=url")
    conn.commit()
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Deleted ')
    conn.close()

async def start_notify():
    global notify
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Started notifying')
    conn = sql.connect('database.db')
    cur = conn.cursor()

    while notify:
        cur.execute("SELECT * FROM animes")
        anime_list = cur.fetchall()
        for anime in anime_list:
            id, url, title, last_episode = anime
            page = requests.get('https://animego.org/anime/'+ str(id) +'/player?_allow=true', headers=headers)
            print(page)
            jsonData = json.loads(page.text)
            a = jsonData["content"]
            tree = html.fromstring(a)
            next_episode = last_episode + 1
            vk.messages.send(peer_id=cfg.id, random_id=0, message='начал поиск')
            episode = str(next_episode)
            value = str(tree.xpath('//option[text() = "' + episode + ' серия"]/@value'))[2:-2]
            print(value)
            dubs = requests.get('https://animego.org/anime/series?dubbing=2&provider=24&episode=' + str(next_episode) + '&id=' + value, headers=headers).json()['content']
            if 'Студийная' or 'AniLibria' in dubs:
                vk.messages.send(peer_id=cfg.id, random_id=0, message= str(next_episode) + ' серия ' + title + ' вышла!\n' + url)
                last_episode = next_episode
                cur.execute("UPDATE animes SET last_episode=? WHERE title=?", (last_episode, title))
                conn.commit()
        await time.sleep(300)
    conn.close()
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Stopped notifying')

def counter():
    str1 = ''
    conn = sql.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT title, last_episode, url FROM animes")
    name = str(cur.fetchall())
    name = str1.join(name)
    first = name.replace("), (", ")\n(").replace("'", "")
    vk.messages.send(peer_id=cfg.id, random_id=0, message=str(first)[1:-1])
    conn.close()

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.text.lower().startswith('/addanime'):
        s = str(event.text.lower())
        arguments = s.split(' ')
        url = str(arguments[1])
        last_episode = int(arguments[2])
        print(url)
        print(last_episode)
        print('asked for add')
        # try:
        add(url, last_episode)
        # except NameError:
        #     vk.messages.send(peer_id=cfg.id, random_id=0, message='Укажи серию')
        # else:
        #     vk.messages.send(peer_id=cfg.id, random_id=0, message='error')
    if event.type == VkEventType.MESSAGE_NEW and event.text.lower().startswith('/deleteanime'):
        s = str(event.text.lower())
        url = s[s.find(" ") + 1:]
        print('asked for delete')
        delete(url)

    if event.type == VkEventType.MESSAGE_NEW and event.text.lower().startswith('/list'):
        counter()

    if event.type == VkEventType.MESSAGE_NEW and event.text.lower().startswith('/startnotify'):
        await.run(start_notify())