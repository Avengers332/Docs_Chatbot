import secrets

class Config:
    SECRET_KEY = secrets.token_hex(16)

    # MySQL configurations for vtiger
    MYSQL_VTIGER = {
        'host': '172.16.12.184',
        'user': 'vtiger',
        'password': 'dtel123',
        'db': 'crm',
    }

    # MySQL configurations for chatbot
    MYSQL_CHATBOT = {
        'host': '172.16.12.109',
        'user': 'dtel',
        'password': 'dtel123',
        'db': 'chatbot_db',
    }
