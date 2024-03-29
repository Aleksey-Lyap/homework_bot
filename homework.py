import logging
import sys
import os
import time
from logging.handlers import RotatingFileHandler
import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_YANDEX')
TELEGRAM_TOKEN = os.getenv('TOKEN_TELEGRAM')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных.
    Которые необходимы для работы программы.
    """
    secrets = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for secret in secrets:
        result = True
        if secret is None:
            logging.error(f'Отсутствует переменная {secret}')
            result = False
    return result


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except telegram.TelegramError:
        logging.error('Не удалось отправить сообщение')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    PAYLOAD = {'from_date': timestamp}
    ERROR_DESCRIPTHION = 'Не удалось выполнить запрос к API'
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=PAYLOAD
        )
    except requests.exceptions.RequestException:
        requests.RequestException(ERROR_DESCRIPTHION)
    if homework_statuses.status_code == 200:
        return homework_statuses.json()
    logging.error('API недоступно')
    raise requests.RequestException(ERROR_DESCRIPTHION)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Получены данные не в виде словаря')
    if 'homeworks' not in response:
        raise KeyError('В полученых данных нет ключа homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Получены данные не в виде списка')
    return response


def parse_status(homework):
    """Определяем статус домашней работы."""
    if not isinstance(homework, dict):
        raise TypeError('Получены данные не в виде словаря')
    if 'homework_name' not in homework:
        raise KeyError('В полученых данных нет ключа homework_name')
    if 'status' not in homework:
        raise KeyError('В полученых данных нет ключа status')
    homework_name = homework['homework_name']
    verdict = homework['status']
    if verdict not in HOMEWORK_VERDICTS:
        raise TypeError('неизвестный статус')
    return (
        f'Изменился статус проверки работы "{homework_name}".'
        + f'{HOMEWORK_VERDICTS[verdict]}'
    )


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler = RotatingFileHandler(
        'main.log', maxBytes=50000000, backupCount=5,
    )
    handler.setFormatter(formatter)
    handler_stream = logging.StreamHandler(sys.stdout)
    handler_stream.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(handler_stream)

    NONE_VARIABLE = 'Отсутствуют обязательные переменные'

    result = check_tokens()

    if result is False:
        logger.critical(NONE_VARIABLE)
        raise sys.exit(NONE_VARIABLE)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    status_cache = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            status = homework['homeworks'][0]['status']
            message = parse_status(homework['homeworks'][0])
            if status != status_cache:
                send_message(bot, message)
                logger.debug('Сообщение отправлено')
                status_cache = status
            else:
                logger.info('Нет изменений в статусе')

        except (
            ConnectionError, requests.RequestException, TypeError, KeyError
        ) as error:
            logging.error(error)
            bot.send_message(TELEGRAM_CHAT_ID, error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
