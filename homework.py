import os
import requests
import telegram
import logging
import time

from http import HTTPStatus
from dotenv import load_dotenv

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

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(funcName)s'
)

HOMEWORK_KEYS = ("status", "homework_name")


def check_tokens():
    """Проверка доступности переменных окружения."""
    for token_const in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if not token_const:
            logging.critical(f'Отсутствует {token_const}.')
            raise SystemExit(
                f'Невозможно запустить програму: отсутствует {token_const}.'
            )


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат с TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Удачная отправка сообщения {message} в Telegram.')
    except Exception as error:
        logging.error(f'Сбой при отправкке сообщения: {error}.')


def get_api_answer(timestamp):
    """Посылает запрос к API Практикум.Домашка с заданной временной меткой."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except ConnectionError:
        logging.error(f'Недоступность эндпоинта {ENDPOINT}.')
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}.')

    if response.status_code != HTTPStatus.OK:
        message = (
            f'Некорректный код ответа от {ENDPOINT}: '
            f'{response.status_code}.')
        logging.error(message)
        raise requests.HTTPError(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        message = f'Некорректный тип данных ответа API: {type(response)}.'
        logging.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Отсутствует ключ homeworks в ответе API.'
        logging.error(message)
        raise KeyError(message)
    if type(response['homeworks']) is not list:
        message = (
            f'Некорректный тип данных под ключем homeworks: '
            f'{type(response["homeworks"])}.'
        )
        logging.error(message)
        raise TypeError(message)
    for hw in response['homeworks']:
        for key in HOMEWORK_KEYS:
            if key not in hw:
                message = f'Отсутствует ключ {key} в ответе API.'
                logging.error(message)
                raise KeyError(message)
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    for key in HOMEWORK_KEYS:
        if key not in homework:
            message = f'Отсутствует ключ {key} в ответе API.'
            logging.error(message)
            raise KeyError(message)
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        message = (
            f'Неожиданный статус домашней работы, '
            f'в ответе API: {homework["status"]}.'
        )
        logging.error(message)
        raise KeyError(message)
    last_status = []
    homework_name = homework['homework_name']
    if status == last_status:
        logging.debug('Отсутствует новый статус в ответе API.')
    verdict = HOMEWORK_VERDICTS[status]
    last_status.append(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = response.get('current_date', int(time.time()))
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            send_message(bot, message)
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
