from . import init_mysql

def init_chatbot_connection(app, config):
    return init_mysql(app, config.MYSQL_CHATBOT)
