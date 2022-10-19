import asyncio
import re

import aiohttp as r
import aiosqlite as sql
import tldextract
from lxml import html
from vkwave.api import Token
from vkwave.bots import SimpleLongPollBot

import config as cfg

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/74.0.3729.157 Safari/537.36', 'x-requested-with': 'XMLHttpRequest'}

bot = SimpleLongPollBot(tokens=cfg.token, group_id=cfg.vkid)
bot_token = Token(cfg.token)


@bot.message_handler(bot.text_contains_filter(["/add"]))
async def addanime(event: bot.SimpleBotEvent):
    try:
        api = event.api_ctx
        db = await sql.connect('database.db')
        peer_id = event.object.object.message.peer_id
        args = event.object.object.message.text.split()
        url = str(args[1])
        episode = str(args[2])
        ext = tldextract.extract(url)
        if not episode.isnumeric():
            await event.answer("Укажите корректную серию")
        else:
            if ext.domain == 'animego':
                async with r.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return
                    tree = html.fromstring(await response.text())
                    title = str(tree.xpath("//*[@id='content']/div/div[1]/div[2]/div[2]/div/h1/text()"))[2:-2]
                    anime_id = str(re.findall('^.*-(.*)\.*', url))[3:-2]  # getting id of the anime
                    cursor = await db.cursor()
                    print(await cursor.execute("SELECT EXISTS(SELECT * FROM animes WHERE anime_id = ? AND "
                                               "peer_id = ?)", (anime_id, peer_id,)))
                    if await cursor.execute("SELECT EXISTS(SELECT * FROM animes WHERE anime_id = ? AND "
                                            "peer_id = ?)", (anime_id, peer_id,)) == 1:
                        await cursor.execute(
                            "UPDATE animes SET is_enabled = ? WHERE peer_id = ? AND anime_id = ?", ("true",
                                                                                                    peer_id,
                                                                                                    anime_id,))
                    else:
                        await cursor.execute("INSERT OR IGNORE INTO animes VALUES (?, ?, ?, ?, ?, true)",
                                             (title, episode, url, anime_id, peer_id))
                    await db.commit()
                    await cursor.close()
                    await session.close()
                    await event.answer('Добавил аниме')

    except Exception as e:
        api = event.api_ctx
        message = "There's an error in the ADD method. LOGS: " + str(e)
        await api.messages.send(peer_id="2000000005", message=message, random_id=1)



@bot.message_handler(bot.text_contains_filter(["/delete"]))
async def deleteanime(event: bot.SimpleBotEvent):
    try:
        args = event.object.object.message.text.split()
        anime_id = str(re.findall('^.*-(.*)\.*', args[1]))[3:-2]
        peer_id = event.object.object.message.peer_id
        db = await sql.connect('database.db')
        cursor = await db.cursor()
        await cursor.execute("UPDATE animes SET is_enabled = false WHERE peer_id = ? AND anime_id = ?",
                             (peer_id, anime_id,))
        await event.answer('Удалил это аниме!')
        await db.commit()
        await cursor.close()
    except Exception as e:
        await event.answer("а где ссылка????????? (или что-то другое не так)")
        print(e)


@bot.message_handler(bot.text_contains_filter(["/stop"]))
async def stop_notifying(event: bot.SimpleBotEvent):
    try:
        api = event.api_ctx
        peer_id = str(event.object.object.message.peer_id)
        db = await sql.connect('database.db')
        cur = await db.cursor()
        await cur.execute("DELETE FROM animes WHERE peer_id = ?", (peer_id,))
        await db.commit()
        await db.close()
    except Exception as e:
        api = event.api_ctx
        message = "There's an error in the STOP method. LOGS: " + str(e)
        await api.messages.send(peer_id="2000000005", message=message, random_id=1)


@bot.message_handler(bot.text_contains_filter(["/list"]))
async def stop_notifying(event: bot.SimpleBotEvent):
    try:
        api = event.api_ctx
        str1 = ''
        peer_id = str(event.object.object.message.peer_id)
        conn = await sql.connect('database.db')
        db = await conn.cursor()
        await db.execute("SELECT DISTINCT title, last_episode, url FROM animes WHERE peer_id = ? AND is_enabled = ?",
                         (peer_id, 1))
        name = str1.join(str(await db.fetchall()))
        first = name.replace("), (", ")\n(").replace("'", "")
        await db.close()
        try:
            if len(first) < 4:
                await event.answer('Пусто')
            else:
                await event.answer(str(first)[1:-1])
        except Exception as e:
            await event.answer("Произошла ошибка. Она уже отправлена создателю.")
            print(e)
    except Exception as e:
        api = event.api_ctx
        message = "There's an error in the LIST method. LOGS: " + str(e)
        await api.messages.send(peer_id="2000000005", message=message, random_id=1)


@bot.message_handler(bot.text_contains_filter(["/admin_command_to_start_the_fucking_bot"]))
async def start_notifying(event: bot.SimpleBotEvent):
    try:
        api = event.api_ctx
        while True:
            conn = await sql.connect('database.db')
            cur = await conn.cursor()
            await cur.execute("SELECT DISTINCT * FROM animes")
            anime_list = await cur.fetchall()
            print(anime_list)
            async with r.ClientSession(headers=headers) as session:
                for anime in anime_list:
                    anime_id = str(anime[3])
                    page = await session.get('https://animego.org/anime/' + anime_id + '/player?_allow=true')
                    json_data = await page.text()
                    tree = html.fromstring(json_data)
                    next_episode = anime[1] + 1
                    value = str(tree.xpath('//option[text() = "' + str(next_episode) + ' серия"]/@value'))[2:-2]
                    dubs = await (session.get(
                        'https://animego.org/anime/series?dubbing=2&provider=24&episode=' + str(
                            next_episode) + '&id=' + value))
                    if 'Субтитры' or 'AniLibria' in dubs.text():
                        message = str(next_episode) + " серия " + anime[0] + " вышла!\n" + anime[2]
                        await cur.execute("SELECT peer_id FROM animes WHERE anime_id = ?", (anime_id,))
                        peer_id = await cur.fetchall()
                        for pid in peer_id:
                            str(pid).replace(',', '').replace('(', '').replace(')', '')
                            await api.messages.send(peer_id=pid, message=message, random_id=1)
                        last_episode = next_episode
                        await cur.execute("UPDATE animes SET last_episode = ? WHERE anime_id = ?",
                                          (last_episode, anime[-2],))
                        await conn.commit()
                await conn.close()
                await asyncio.sleep(300)
    except Exception as e:
        api = event.api_ctx
        await event.answer("An error occurred. Check logs for additional info.")
        message = "There's an error in the START method. LOGS: " + str(e)
        await api.messages.send(peer_id="2000000005", message=message, random_id=1)
        print('start')


bot.run_forever()
