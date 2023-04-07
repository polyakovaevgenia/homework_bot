import telegram
import requests
import time
import os
import sys
import logging

from http import HTTPStatus
from dotenv import load_dotenv
from exceptions import (TokenError,
                        SendMessageError,
                        ApiAnswerError,
                        StatusError)

load_dotenv()


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

# logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка токенов."""
    token_list = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in token_list:
        if token is None:
            logger.critical('Отсутствует обязательная переменная')
            raise TokenError('Токен отсутствует')
    return True


def send_message(bot, message):
    """Бот отправляет сообщение."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, message)
    except Exception as error:
        logger.error('Сбой при отправке сообщения в Telegram')
        raise SendMessageError(f'Сбой при отправке сообщения {error}')
    else:
        logger.debug('Сообщение успешно отправлено')


def get_api_answer(timestamp):
    """Получает ответ от API Яндекс."""
    payload = {'from_date': timestamp}
    try:
        homework_status = requests.get(ENDPOINT,
                                       headers=HEADERS,
                                       params=payload)
    except requests.RequestException as err:
        logger.error(f'Ошибка {err} при обращении к эндпоинту')
    try:
        response = homework_status
        if response.status_code != HTTPStatus.OK:
            logger.error(f'Эндпоинт {ENDPOINT} недоступен')
            raise ApiAnswerError(
                f'Эндпоинт {ENDPOINT} недоступен. Зайдите позже')
        response = response.json()
        return response

    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        raise ApiAnswerError(f'Сбой при запросе к эндпоинту {ENDPOINT}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не соответствует формату JSON')
    if 'current_date' not in response.keys():
        logger.error('Не найден ключ "current_date" в словаре ответа API')
        raise KeyError('Ключ "current_date" отсутствует в ответе API')
    if 'homeworks' not in response.keys():
        logger.error('Не найден ключ "homeworks" в словаре ответа API')
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('homeworks не соответствует формату list')
    return True


def parse_status(homework):
    """Определяет статус проверки домашней работы."""
    homework_status = homework.get('status')
    try:
        homework_name = homework.get('homework_name')
    except KeyError:
        raise KeyError('Нет работы с таким названием')
    if 'homework_name' not in homework.keys():
        raise TypeError('Нет работы с таким названием')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error('Неожиданный статус домашней работы')
        raise StatusError('Неизвестный статус домашней работы')
    if homework_status is None:
        logger.debug('Новый статус работы отсутствует')
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens() is not True:
        logger.critical('Программа остановлена')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            try:
                homework = response.get('homeworks')[0]
                homework_status = parse_status(homework)
            except IndexError:
                logger.debug('Новый статус работы отсутствует')
            if homework_status:
                send_message(bot, homework_status)
                logger.debug('Сообщение о статусе работы отправлено')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
