import pymysql

# Database configurations
db_config = {
    'vtiger': {
        'user': 'vtiger',
        'password': 'dtel123',
        'host': '172.16.12.184',
        'database': 'crm'
    },
    'chatbot': {
        'user': 'dtel',
        'password': 'dtel123',
        'host': '172.16.12.109',
        'database': 'chatbot_db'
    }
}

# Database connection function
def get_db_connection(db_name):
    config = db_config.get(db_name)
    if config:
        return pymysql.connect(
            host=config['host'],
            user=config['user'],
            password=config['password'],
            db=config['database'],
            cursorclass=pymysql.cursors.DictCursor
        )
    return None