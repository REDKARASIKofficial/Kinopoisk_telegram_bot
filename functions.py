import logging
from pprint import pprint

import aiohttp
from aiogram import types
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import API_KEY, API_KEY_2

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)

logger = logging.getLogger(__name__)


async def start(update, context):
    if 'chat_id' not in context.user_data:
        context.user_data['chat_id'] = update.message.chat_id
        context.user_data['username'] = update.message.username
        context.user_data['id'] = update.message.id
    keyboard = [[InlineKeyboardButton("Поиск фильма", callback_data='search'),
                 InlineKeyboardButton("Оценки фильмов", callback_data='assessments')],
                [InlineKeyboardButton("Мои фильмы", callback_data='my_movies'),
                 InlineKeyboardButton("Подборки", callback_data='mixes')],
                [InlineKeyboardButton("Рандом", callback_data='random')]
                ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    context.user_data['message_type'] = 'text'
    context.user_data['message'] = await context.bot.send_message(text=
                                                                  "Добро пожаловать в стартовое меню бота.\nЗдесь вы можете найти нужную вам функцию.",
                                                                  chat_id=context.user_data['chat_id'],
                                                                  reply_markup=reply_markup)


async def button(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        print(query.data)
        context.user_data['query_data'] = query.data
        if query.data == 'search':
            await search_film(query, context)
        if query.data == 'search_by_name':
            await search_by_name(query, context)
        if query.data.startswith('search_by_name'):
            await random(context, 'https://api.kinopoisk.dev/v1/movie', params={'name': query.data.split('~')[1]},
                         dlt=True)
        if query.data == 'search_by_actor':
            await search_by_actor(query, context)
        if query.data == 'random':
            await random(context, 'https://api.kinopoisk.dev/v1/movie/random')
        if query.data == 'start':
            await start(update, context)
        if query.data == 'delete':
            await context.bot.delete_message(chat_id=context.user_data['chat_id'],
                                             message_id=context.user_data['message'].message_id)
            context.user_data['message_type'] = 'text'
        if query.data.split('.')[0] == 'add_to_want_films':
            print(add_to_want_films(context.user_data['id'], context.user_data['username'], query.data.split('.')[1]))

    else:
        if 'query_data' in context.user_data:
            name = update.message.text
            if context.user_data['query_data'] == 'search_by_name':
                print(context.user_data)
                await random(context, 'https://api.kinopoisk.dev/v1/movie', params={'name': name})
            if context.user_data['query_data'] == 'search_by_actor':
                print(context.user_data)
                await print_films_by_actor(context, 'https://kinopoiskapiunofficial.tech/api/v1/persons',
                                           params={'name': name},
                                           headers={"X-API-KEY": API_KEY_2})
            del context.user_data['query_data']


async def search_film(query, context):
    keyboard = [[InlineKeyboardButton('По названию', callback_data='search_by_name'),
                 InlineKeyboardButton('По актёру', callback_data='search_by_actor')],
                [InlineKeyboardButton('По режиссёру', callback_data='search_by_director'),
                 InlineKeyboardButton('По жанру', callback_data='search_by_genre')],
                [InlineKeyboardButton('Назад', callback_data='start')]]
    markup = InlineKeyboardMarkup(keyboard)
    if context.user_data['message_type'] == 'text':
        context.user_data['message'] = await context.bot.edit_message_text(
            text='Вы можете найти фильмы, по заданным вами параметрам.',
            message_id=context.user_data['message'].message_id,
            chat_id=context.user_data['chat_id'], reply_markup=markup)
    else:
        context.user_data['message_type'] = 'text'
        context.user_data['message'] = await context.bot.send_message(
            text='Вы можете найти фильмы, по заданным вами параметрам.',
            chat_id=context.user_data['chat_id'], reply_markup=markup)


async def get_response(url, params=None, headers=None):
    logger.info(f"getting {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            return await resp.json()


async def random(context, url, params=None, dlt=False):
    response = await get_response(url, headers={'X-API-KEY': API_KEY}, params=params)
    pprint(response)
    text, img, url_trailer, url_sources, id_film, title = parser_film(response)
    print(add_film_title_to_db(id_film, title))
    chat_id = context.user_data['chat_id']
    special_data = 'delete' if dlt else 'start'
    if url == 'https://api.kinopoisk.dev/v1/movie/random':
        keyboard = [[InlineKeyboardButton('Рандом', callback_data='random'),
                     InlineKeyboardButton('Добавить в посмотреть позже',
                                          callback_data=f'add_to_want_films.{id_film}.{title}')],
                    [InlineKeyboardButton('Назад', callback_data=special_data)]]
    else:
        keyboard = [[InlineKeyboardButton('Другое название', callback_data='search_by_name'),
                     InlineKeyboardButton('Добавить в посмотреть позже', callback_data='add_to_want_films')],
                    [InlineKeyboardButton('Назад', callback_data=special_data)]]

    keyboard[0] = [InlineKeyboardButton('Трейлер', url=url_trailer)] + keyboard[0] if url_trailer else keyboard[0]
    keyboard = [[InlineKeyboardButton(text=k, url=v) for k, v in
                url_sources.items()]] + keyboard if url_sources else keyboard
    print(keyboard)
    markup = InlineKeyboardMarkup(keyboard)
    print(context.user_data['message_type'])
    if context.user_data['message_type'] != 'media':
        context.user_data['message'] = await context.bot.send_photo(chat_id, img['url'], caption=text,
                                                                    reply_markup=markup,
                                                                    parse_mode=types.ParseMode.HTML)
        context.user_data['message_type'] = 'media'
    else:
        context.user_data['message'] = await context.bot.delete_message(chat_id,
                                                                        context.user_data['message'].message_id)
        context.user_data['message'] = await context.bot.send_photo(chat_id, img['url'], caption=text,
                                                                    reply_markup=markup,
                                                                    parse_mode=types.ParseMode.HTML)


def parser_film(response):
    pprint(response)
    response = response['docs'][0] if 'docs' in response else response
    id_film = response['id']
    alt_name = response.get('alternativeName', '')
    name = response.get('name', '')
    description = response.get('description', '')
    year = response.get('year', '')
    age_rate = response.get('ageRating', '')
    genre = ', '.join(map(lambda x: x['name'], response.get('genres', '')[:5]))
    poster = response.get('poster', '')
    rate_imdb, rate_kp = response['rating']['imdb'], response['rating']['kp']
    video = response.get('videos', '')
    trailer = video.get('trailers', '') if video else ''
    url_trailer = trailer[0].get('url', '') if trailer else ''
    watchability = response['watchability']['items']
    sources = {}
    if watchability:
        for source in watchability:
            sources[source['name']] = source['url']
    persons = parser_person(response.get('persons', ''))
    persons_text = ''
    pprint(persons)
    if rate_imdb and rate_imdb > 7:
        if persons:
            for k, v in persons.items():
                if len(v): persons_text += f"<strong>{k}</strong>: {', '.join(v)}\n"
    else:
        if persons:
            if persons['Режиссеры']: persons_text += f"<strong>Режиссёры</strong>: {', '.join(persons['Режиссеры'])}\n"
            if persons['Актеры']: persons_text += f"<strong>Актёры</strong>: {', '.join(persons['Актеры'])}\n"

    text = f"<strong>{year if year else ''}</strong>\n<strong>{name}</strong> {f'(<strong>{alt_name}</strong>)' if alt_name is not None else ''} <strong>{str(age_rate) + '+' if age_rate else ''}</strong>\n" \
           f"<strong>жанр:</strong> {genre}\n" \
           f"<strong>IMDb:</strong> {rate_imdb if rate_imdb else '-'}\n<strong>Кинопоиск</strong>: {rate_kp}\n" \
           f"{persons_text}\n" \
           f"{description if description else ''}"
    if len(text) > 4096: text = '\n'.join(text.split('\n')[:-1]) if len(
        '\n'.join(text.split('\n')[:-1])) <= 4096 else '\n'.join(text.split('\n')[:-2])
    return text, poster, url_trailer, sources, id_film, name


def parser_person(response):
    if not response:
        return ''
    persons = {'Режиссеры': [], 'Продюсеры': [], 'Композиторы': [], 'Актеры': []}
    for data in response:
        if data['profession'].capitalize() in persons:
            persons[data['profession'].capitalize()].append(
                data['name'] if data['name'] is not None else data['enName'])
    persons['Актеры'] = persons['Актеры'] if len(persons['Актеры']) < 10 else persons['Актеры'][:10]
    return persons


async def search_by_name(query, context):
    keyboard = [[InlineKeyboardButton('Назад', callback_data='search')]]
    markup = InlineKeyboardMarkup(keyboard)
    if context.user_data['message_type'] == 'text':
        context.user_data['message'] = await context.bot.edit_message_text(text='Напишите название фильма',
                                                                           chat_id=context.user_data['chat_id'],
                                                                           reply_markup=markup,
                                                                           message_id=context.user_data[
                                                                               'message'].message_id)
    else:
        context.user_data['message_type'] = 'text'
        context.user_data['message'] = await context.bot.send_message(text='Напишите название фильма',
                                                                      chat_id=context.user_data['chat_id'],
                                                                      reply_markup=markup)


async def search_by_actor(query, context):
    keyboard = [[InlineKeyboardButton('Назад', callback_data='search')]]
    markup = InlineKeyboardMarkup(keyboard)
    if context.user_data['message_type'] == 'text':
        context.user_data['message'] = await context.bot.edit_message_text(text='Напишите имя актёра',
                                                                           chat_id=context.user_data['chat_id'],
                                                                           reply_markup=markup,
                                                                           message_id=context.user_data[
                                                                               'message'].message_id)
    else:
        context.user_data['message_type'] = 'text'
        context.user_data['message'] = await context.bot.send_message(text='Напишите имя актёра',
                                                                      chat_id=context.user_data['chat_id'],
                                                                      reply_markup=markup)


async def print_films_by_actor(context, url, params=None, headers=None):
    response = await get_response(url, headers={'X-API-KEY': API_KEY_2}, params=params)
    pprint(response)
    id = response['items'][0]['kinopoiskId']
    img = response['items'][0]['posterUrl']
    response = await get_response('https://kinopoiskapiunofficial.tech/api/v1/staff/' + str(id), headers=headers)
    names = [item['nameRu'] for item in response['films'] if item['professionKey'] == 'ACTOR']
    keyboard = []
    for i in range(0, 11, 2):
        print('ok')
        line = names[i:(i + 2) % len(names)]
        print(line)
        keyb = [InlineKeyboardButton(name[:21], callback_data=f'search_by_name~{name[:20]}') for name in line]
        keyboard.append(keyb)
    keyboard.append([InlineKeyboardButton('Другой актёр', callback_data='search_by_actor'),
                     InlineKeyboardButton('Назад', callback_data='search')])
    markup = InlineKeyboardMarkup(keyboard)
    context.user_data['message_type'] = 'text'
    pprint(markup)
    context.user_data['message'] = await context.bot.send_photo(context.user_data['chat_id'], img,
                                                                caption=params['name'], reply_markup=markup,
                                                                parse_mode=types.ParseMode.HTML)
