from flask_mysqldb import MySQL
from flask import g

def init_mysql(app, db_config):
    # Configure the MySQL connection
    app.config['MYSQL_HOST'] = db_config['host']
    app.config['MYSQL_USER'] = db_config['user']
    app.config['MYSQL_PASSWORD'] = db_config['password']
    app.config['MYSQL_DB'] = db_config['db']

    # Initialize MySQL
    mysql = MySQL(app)
    
    # Close the MySQL connection after each request
    @app.teardown_appcontext
    def close_db(error):
        if hasattr(g, 'mysql_db'):
            g.mysql_db.close()

    return mysql
