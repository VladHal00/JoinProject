import json
from flask import Flask, redirect, request
import requests
import asyncio
import logging
from aiogram import Bot, Dispatcher

# настройка логирования в файл service_log.txt
logging.basicConfig(filename='service_log.txt', level=logging.INFO)

# Создание экземпляра бота и диспетчера
bot = Bot(token="6511701150:AAFj07NFXSEIQk6a25cEIzG-r16c0kfOhN8")
dp = Dispatcher()


# Функция для отправки уведомления в Telegram
async def send_notification(chat_id, text):
    await bot.send_message(chat_id=chat_id, text=text)


# Класс для хранения данных подключения и авторизации
class Connection:
    def __init__(self, alias, comment, url, client_id, client_secret):
        self.alias = alias
        self.comment = comment
        self.url = url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None

    # Метод для аутентификации
    def authenticate(self):
        logging.info(f"sending notification to telegram for authentication {self.alias}")
        asyncio.run(send_notification(self.alias, f"connection {self.alias} requires authentication"))

        # Формирование URL для аутентификации
        auth_url = f"{self.url}/oauth/token"

        # Параметры для запроса на аутентификацию
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        # Отправка POST-запроса на аутентификацию
        response = requests.post(auth_url, data=data)

        # проверка статуса ответа
        if response.status_code == 200:
            self.access_token = response.json().get("access_token")
            logging.info(f"successfully authenticated {self.alias}")
        else:
            logging.error(f"failed to authenticate {self.alias}")

    # Метод для проверки аутентификации
    def is_authenticated(self):
        return self.access_token is not None

    # Метод для проверки срока действия токена
    def check_token_expiry(self):
        logging.info(f"checking token expiry for {self.alias}")

        # Формирование URL для проверки срока действия токена
        check_url = f"{self.url}/method/users.get?access_token={self.access_token}"

        # Отправка GET-запроса на проверку срока действия токена
        response = requests.get(check_url)

        # Проверка статуса ответа
        if response.status_code == 200:
            # Проверка на наличие ошибки в ответе
            if "error" in response.json():
                logging.info(f"token expired for {self.alias}")
                self.access_token = None
                return False
            else:
                logging.info(f"token is still valid for {self.alias}")
                return True
        else:
            logging.error(f"failed to check token expiry for {self.alias}")
            return False

    def make_api_request(self, endpoint):
        self.check_token_expiry()
        headers = {
            "authorization": f"bearer {self.access_token}",
            "content-type": "application/json"
        }
        url = f"{self.url}{endpoint}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"api request failed for {self.alias}")
            return None


class Service:
    def __init__(self):
        self.connections = []

    def load_configurations(self, config_file):
        with open(config_file) as f:
            config_data = json.load(f)
        for connection_data in config_data:
            connection = Connection(
                connection_data['alias'],
                connection_data['comment'],
                connection_data['url'],
                connection_data['clientid'],
                connection_data['clientsecret']
            )
            self.connections.append(connection)

    def get_all_connections_info(self):
        connection_info = []
        for connection in self.connections:
            connection_info.append({
                'alias': connection.alias,
                'comment': connection.comment,
                'type': type(connection).__name__
            })
        return connection_info

    def get_token_by_alias(self, alias):
        for connection in self.connections:
            if connection.alias == alias:
                if not connection.is_authenticated():
                    connection.authenticate()
                    asyncio.run(send_notification(alias, f"authentication required for {alias}"))
                return connection.access_token
        logging.error(f"no connection found for {alias}")
        asyncio.run(send_notification(alias, f"no connection found for {alias}"))
        return None

    def process_token_expiry_signal(self, alias):
        for connection in self.connections:
            if connection.alias == alias:
                connection.check_token_expiry()
                return
        logging.error(f"no connection found for {alias}")
        asyncio.run(send_notification(alias, f"no connection found for {alias}"))


app = Flask(__name__)

# Данные для аутентификации
client_id = 'YOUR_CLIENT_ID'
client_secret = 'YOUR_CLIENT_SECRET'
redirect_uri = 'http://your-domain.com/callback'

# Ссылка для получения кода авторизации
auth_url = f'https://oauth.vk.com/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=offline'


@app.route('/')
def hello():
    return f"<a href='{auth_url}'>Авторизация через VK</a>"


@app.route('/callback')
def callback():
    # Получение кода авторизации из параметров запроса
    code = request.args.get('code')

    # Формирование параметров для запроса на получение токена
    token_params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code
    }

    # Отправка POST-запроса на получение токена
    response = requests.post('https://oauth.vk.com/access_token', params=token_params)
    token_data = response.json()

    # Получение access_token и user_id из ответа
    access_token = token_data['access_token']
    user_id = token_data['user_id']

    # Дальнейшая обработка токена и user_id...

    return f"Access Token: {access_token}<br>User ID: {user_id}"


if __name__ == '__main__':
    app.run()
    service = Service()
    service.load_configurations("config.json")
    print(service.get_all_connections_info())
    alias = input("enter alias to get token: ")
    password = input("enter password for authentication: ")
    for connection in service.connections:
        if connection.alias == alias:
            connection.password = password
            connection.authenticate()
            token = service.get_token_by_alias(alias)
            if token:
                print(f"token for alias {alias}: {token}")
            break
    else:
        print(f"no connection found for {alias}")

