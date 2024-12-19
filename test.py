from db_utils import get_db_connection
import pymysql

def get_users_status():
    try:
        # Connect to the database
        conn = get_db_connection('chatbot')
        
        # Use a cursor to execute the SQL query
        with conn.cursor() as cur:
            # SQL query to fetch user_id, user_name, login_status, and last_login
            sql = """
                SELECT user_id, user_name, login_status, last_login
                FROM users
                ORDER BY last_login DESC
            """
            cur.execute(sql)  # Use the cursor to execute the query
            users_status = cur.fetchall()  # Fetch all user data

        conn.close()

        # Return the result as a dictionary (for testing purposes)
        return {'status': 'success', 'data': users_status}

    except pymysql.MySQLError as e:  # Handle MySQL specific errors
        return {'status': 'error', 'message': f"Database error: {e.args[1]}"}
    except Exception as e:  # Catch other errors
        return {'status': 'failed', 'message': str(e)}

# Test the function without Flask context
print(get_users_status())
