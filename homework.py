import telegram
import requests
import time
import os
import sys
import logging
import json

from http import HTTPStatus
from dotenv import load_dotenv
from exceptions import (TokenError,
                        ApiAnswerError,
                        StatusError)

load_dotenv()

logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка токенов."""
    token_list = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(token_list):
        return True
    logger.critical('Отсутствует обязательная переменная')
    raise TokenError('Токен отсутствует')


def send_message(bot, message):
    """Бот отправляет сообщение."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, message)
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')
    else:
        logger.debug('Сообщение успешно отправлено')


def get_api_answer(timestamp):
    """Получает ответ от API Яндекс."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=payload)
    except requests.RequestException as err:
        message = f'Ошибка {err} при обращении к эндпоинту'
        raise ApiAnswerError(message)
    if response.status_code != HTTPStatus.OK:
        message = f'Эндпоинт {ENDPOINT} недоступен'
        raise ApiAnswerError(message)
    try:
        response = response.json()
    except json.decoder.JSONDecodeError:
        message = 'Ответ сервера не может быть преобразован в JSON'
        raise ApiAnswerError(message)
    return response


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не соответствует формату JSON')
    if 'current_date' not in response.keys():
        message = 'Не найден ключ "current_date" в словаре ответа API'
        raise KeyError(message)
    if 'homeworks' not in response.keys():
        message = 'Не найден ключ "homeworks" в словаре ответа API'
        raise KeyError(message)
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('homeworks не соответствует формату list')


def parse_status(homework):
    """Определяет статус проверки домашней работы."""
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if 'homework_name' not in homework:
        raise ValueError('Нет работы с таким названием')
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неожиданный статус домашней работы'
        raise StatusError(message)
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time() - RETRY_PERIOD)
    saved_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            timestamp = response['current_date']
            homework = response.get('homeworks')
            if homework:
                homework_status = parse_status(homework[0])
                send_message(bot, homework_status)
                logger.debug('Сообщение о статусе работы отправлено')
            else:
                logger.debug('Новый статус работы отсутствует')
            saved_message = ''
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            if message != saved_message:
                send_message(bot, message)
                saved_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()
