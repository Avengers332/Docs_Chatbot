from . import init_mysql

def init_vtiger_connection(app, config):
    return init_mysql(app, config.MYSQL_VTIGER)
