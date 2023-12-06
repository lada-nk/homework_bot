import os
import sys
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
RETRY_PERIOD_IN_SEC = RETRY_PERIOD

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
    format='%(asctime)s, %(levelname)s, %(message)s, %(funcName)s',
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

HOMEWORK_KEYS = ('status', 'homework_name')


def check_tokens():
    """Проверка доступности переменных окружения."""
    for token_const in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if not token_const:
            logger.critical(f'Отсутствует {token_const}.')
            raise SystemExit(
                f'Невозможно запустить програму: отсутствует {token_const}.'
            )


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат с TELEGRAM_CHAT_ID."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        # c "raise telegram.error.TelegramError" pytest не проходит
        logger.exception(f'Сбой при отправкке сообщения: {error}.')

    logger.debug(f'Удачная отправка сообщения {message} в Telegram.')


def get_api_answer(timestamp):
    """Посылает запрос к API Практикум.Домашка с заданной временной меткой."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except ConnectionError:
        raise ConnectionError(f'Недоступность эндпоинта {ENDPOINT}.')
    except Exception as error:
        raise Exception(f'Ошибка при запросе к основному API: {error}.')

    if response.status_code != HTTPStatus.OK:
        raise requests.HTTPError(
            f'Некорректный код ответа от {ENDPOINT}'
            f' - {response.status_code}'
            f'с параметрами: params="from_date": {timestamp}, '
            f'headers={HEADERS}. '
            f'{response}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Некорректный тип данных ответа API: {type(response)}.'
        )
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks в ответе API.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Некорректный тип данных под ключем homeworks: '
            f'{type(homeworks)}.'
        )
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    for key in HOMEWORK_KEYS:
        if key not in homework:
            raise KeyError(f'Отсутствует ключ {key} в ответе API.')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Неожиданный статус домашней работы, '
            f'в ответе API: {status}.'
        )
    last_status = []
    homework_name = homework['homework_name']
    if status == last_status:
        logger.debug('Отсутствует новый статус в ответе API.')
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
            parsed_response = get_api_answer(timestamp)
            homeworks = check_response(parsed_response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = parsed_response.get('current_date', int(time.time()))
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            send_message(bot, message)
            logger.exception(message)
        finally:
            time.sleep(RETRY_PERIOD_IN_SEC)


if __name__ == '__main__':
    main()
