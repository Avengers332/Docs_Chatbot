import pymysql
import bcrypt 
import logging
from db_utils import get_db_connection

def authenticate_user(username, password, connection: pymysql.connections.Connection):
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        query = "SELECT id,user_name, first_name, last_name, email1, user_password, is_admin FROM vtiger_users WHERE user_name = %s AND status='Active'"
        cursor.execute(query, (username,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            stored_password = user['user_password'] 
            if not stored_password:
                return {
                    'status': 'error',
                    'message': 'Password hash is missing for this user.'
                }

            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):

                user['is_admin'] = 1 if user['is_admin'] == 'on' else 0

                save_user_to_chatbot_db(user)

                return {
                    'status': 'success',
                    'data': {
                        'user_id': user['id'],       
                        'user_name': user['user_name'], 
                        'first_name': user['first_name'],  
                        'last_name': user['last_name'],   
                        'email1': user['email1'],      
                        'is_admin': user['is_admin'] 
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Incorrect password.'
                }
        else:
            return {
                'status': 'error',
                'message': 'User not found.'
            }

    except pymysql.MySQLError as e:

        logging.error(f"Database error code: {e.args[0]}, Error message: {e.args[1]}")
        return {
            'status': 'error',
            'message': f"Database error: {e.args[1]}"
        }
    
def save_user_to_chatbot_db(user):
   
    connection = get_db_connection('chatbot')  
    try:
        with connection.cursor() as cursor:
            
            query = """
                INSERT INTO users (user_id, user_name, email, first_name, last_name, is_admin, login_status, last_login)
                VALUES (%s, %s, %s, %s, %s, %s, 'online', NOW())
                ON DUPLICATE KEY UPDATE
                    user_name = VALUES(user_name),
                    email = VALUES(email),
                    first_name = VALUES(first_name),
                    last_name = VALUES(last_name),
                    is_admin = VALUES(is_admin),
                    login_status = 'online',
                    last_login = NOW();
            """
            cursor.execute(query, (
                user['id'],              
                user['user_name'],       
                user['email1'],          
                user['first_name'],      
                user['last_name'],      
                user['is_admin']        
            ))
        connection.commit() 
    except pymysql.MySQLError as e:
        logging.error(f"Failed to save user data to chatbot DB. Error: {e}")
    finally:
        connection.close()  
