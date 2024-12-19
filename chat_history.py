from flask import session
import pymysql

def get_chathistory(connection: pymysql.connections.Connection):
    try:
        username = session.get('username')
        
        if not username:
            return {
                'status': 'error',
                'message': 'User not logged in.'
            }

        cursor = connection.cursor()

        query = """
            SELECT id, user_id, user_name, message, sender, feedback, remarks, file_path, created_at
            FROM chat_history
            WHERE user_name = %s
            ORDER BY created_at ASC
        """
        cursor.execute(query, (username,))
        history = cursor.fetchall() 
        cursor.close()  

        if history:
            return {
                'status': 'success',
                'data': history
            }
        else:
            return {
                'status': 'success',
                'message': 'No chat history found for this user.'
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': f"Database error: {str(e)}"
        }
