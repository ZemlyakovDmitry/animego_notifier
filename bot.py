# -*- coding: utf-8 -*-

import time
import vk_api
import requests
import config as cfg
import sqlite3 as sql
from lxml import html
from bs4 import BeautifulSoup as BS
from vk_api.longpoll import VkLongPoll, VkEventType

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36'}

vkSession = vk_api.VkApi(token=cfg.token)
longpoll = VkLongPoll(vkSession)
vk = vkSession.get_api()
notify = True

def add(url, last_episode):
    conn = sql.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM animes where url=?", (url,))
    page = requests.get(url, headers=headers, timeout=10)  #
    tree = html.fromstring(page.content)
    name = str(tree.xpath("//*[@id='content']/div/div[1]/div[2]/div[2]/div/h1/text()"))[2:-2]
    name_utf = name.encode('utf-8')
    if name_utf is None:
        print('404')
    print(name_utf)
    cur.execute("INSERT INTO animes VALUES (?, ?, ?)", (name, url, last_episode))
    conn.commit()
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Added ' + name)
    conn.close()

def delete(url):
    conn = sql.connect('database.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM animes WHERE url=url")
    conn.commit()
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Deleted ')
    conn.close()

def start_notify(update, context):
    global notify
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Started notifying')
    conn = sql.connect('database.db')
    cur = conn.cursor()

    while notify:
        cur.execute("SELECT * FROM animes")
        anime_list = cur.fetchall()
        for anime in anime_list:
            name, url, last_episode = anime
            soup = BS(requests.get(url).text, 'lxml')
            soup = soup.find_all('div', class_='video-carousel')
            print(anime)
            if actual_episodes > last_episode:
                vk.messages.send(peer_id=cfg.id, random_id=0, message='New apisode of ' + name + ' is out!\n' + url)
                cur.execute("UPDATE animes SET episodes=? WHERE name=?", (last_episode, name))
                conn.commit()
        time.sleep(300)
    conn.close()
    vk.messages.send(peer_id=cfg.id, random_id=0, message='Stopped notifying')

def counter():
    str1 = ''
    conn = sql.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT name, last_episode, url FROM animes")
    name = str(cur.fetchall())
    name = str1.join(name)
    first = name.replace("), (", ")\n(")
    second = first.replace("'", "")
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
        print(s)
        url = s[s.find(" ") + 1:]
        print(url)
        print('asked for delete')
        delete(url)

    if event.type == VkEventType.MESSAGE_NEW and event.text.lower().startswith('/list'):
        counter()