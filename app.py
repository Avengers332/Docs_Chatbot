from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify, make_response, send_from_directory, abort
from login import authenticate_user
from pdf_upload_and_embedding import app as upload_app
from query_response_processing import process_query_and_get_response, load_images_from_folder
from langchain import HuggingFaceHub
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from flask_cors import CORS
from query_response_processing import get_natural_response
from db_utils import get_db_connection
import secrets
from flask_session import Session
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json
import pymysql

app = Flask(__name__)
CORS(app, supports_credentials=True)

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)

# Secret key for session management
app.secret_key = secrets.token_hex(16)

app.register_blueprint(upload_app)



# Constants
VECTOR_DB_FOLDER = 'data/vector_db'
FEEDBACK_FOLDER = 'data/feedback_files'

# Embedding and Database Setup
embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
chroma_db = Chroma(persist_directory=VECTOR_DB_FOLDER, embedding_function=embedding_function)

# LLM Setup
llm = HuggingFaceHub(
    repo_id="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",   
    huggingfacehub_api_token="enter api token",
    model_kwargs={"temperature": 0.7, "max_length": 2000}
)
# LLM Setup
# llm = HuggingFaceHub(
#     repo_id="meta-llama/Llama-2-7b-chat-hf",   
#     huggingfacehub_api_token="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",
#     model_kwargs={"temperature": 0.7, "max_length": 2000}
# )

# Function to generate a refined conversation title
def generate_conversation_title(user_query):
    # Predefined list of casual greetings to handle generic queries
    casual_queries = ["hi", "hello", "how are you", "hey", "what's up", "greetings"]

    query_lower = user_query.lower().strip()
    if any(greeting in query_lower for greeting in casual_queries):
        return f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Split the query into words, removing common stop words
    stop_words = set(["the", "is", "in", "to", "and", "a", "of", "for", "on", "with", "it", "this", "that"])
    words = [word for word in query_lower.split() if word not in stop_words]
    
    # Take the first 3 words from the cleaned query for the title
    title = " ".join(words[:3])
    
    # If the title is still too short or generic, add a timestamp
    if not title or title.lower() in casual_queries:
        title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return title.strip()

def create_or_update_conversation(user_id, user_query):
    connection = None
    conversation_id = None
    try:
        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        with connection.cursor() as cur:
            # Check if a conversation already exists for the user
            query = "SELECT conversation_id, title FROM conversations WHERE user_id = %s ORDER BY created_at DESC LIMIT 1"
            cur.execute(query, (user_id,))
            conversation = cur.fetchone()

            if conversation:
                conversation_id = conversation["conversation_id"]
            else:
                # Create a new conversation with a title
                title = generate_conversation_title(user_query)
                insert_query = "INSERT INTO conversations (user_id, title, created_at) VALUES (%s, %s, %s)"
                cur.execute(insert_query, (user_id, title, datetime.now()))
                connection.commit()

                # Retrieve the new conversation ID
                conversation_id = cur.lastrowid

                # If that fails, fallback to SELECT LAST_INSERT_ID()
                if not conversation_id:
                    cur.execute("SELECT LAST_INSERT_ID()")
                    conversation_id = cur.fetchone()[0]

    except Exception as e:
        print(f"Error managing conversation: {str(e)}")
        raise

    finally:
        if connection:
            connection.close()

    return conversation_id

# Function to save chat history
def save_chat_history(conversation_id, content, sender):
    connection = None
    last_inserted_id = None
    try:
        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        with connection.cursor() as cur:
            # Insert the message into the Messages table
            query = """
                INSERT INTO messages (conversation_id, content, sender, created_at)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(query, (
                conversation_id,
                content,
                sender,
                datetime.now()
            ))
            connection.commit()

            # Get the last inserted ID
            cur.execute("SELECT LAST_INSERT_ID()")
            last_inserted_id = cur.fetchone()["LAST_INSERT_ID()"]  # Fetch as dict if cursor is DictCursor

    except Exception as e:
        print(f"Error saving chat history: {str(e)}")
        raise

    finally:
        if connection:
            connection.close()

    return last_inserted_id


@app.route("/query", methods=["POST"])
def query():
    try:
        data = request.get_json()
        query = data.get("query", "")
        if not query:
            return jsonify({"error": "Query is required"}), 400

        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "User not logged in"}), 403

        # Create or update conversation
        conversation_id = create_or_update_conversation(user_id, query)
        session["conversation_id"] = conversation_id

        retriever = chroma_db.as_retriever(search_kwargs={"k": 3})
        chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, input_key="question")
        
        all_images = load_images_from_folder('static/images')
        casual_queries = ["hi", "hello", "how are you", "hey", "what's up", "greetings"]

        query_lower = query.lower().strip()
        user_message_id = save_chat_history(conversation_id, query, "user")

        if any(greeting in query_lower for greeting in casual_queries):
            refined_prompt = get_natural_response(query)

            if refined_prompt.get("answer"):
                bot_message_id = save_chat_history(conversation_id, refined_prompt["answer"], "bot")
                bot_response = refined_prompt["answer"]
            else:
                # Handle case where bot response is missing or fails
                bot_message_id = save_chat_history(conversation_id, "Bot failed to respond", "bot")
                bot_response = "Bot failed to respond"
            
            session['chat_history'].append({"sender": "user", "message": query, "message_id": user_message_id})
            session['chat_history'].append({"sender": "bot", "message": bot_response, "message_id": bot_message_id})
            
            return jsonify({
                "response": bot_response,
                "conversation_id": conversation_id,
                "conversation_title": generate_conversation_title(query),
                "user_message_id": user_message_id,
                "bot_message_id": bot_message_id
            })

        try:
            response_data = process_query_and_get_response(query, chain, llm, all_images)
            bot_message_id = save_chat_history(conversation_id, response_data["answer"], "bot")
            bot_response = response_data["answer"]
        except Exception as e:
            # Handle case where bot processing fails for non-casual queries
            bot_message_id = save_chat_history(conversation_id, "Bot failed to process query", "bot")
            bot_response = "Bot failed to process query"

        # Save user message
        session['chat_history'].append({"sender": "user", "message": query, "message_id": user_message_id})
        session['chat_history'].append({"sender": "bot", "message": bot_response, "message_id": bot_message_id})

        return jsonify({
            "response": bot_response,
            "conversation_id": conversation_id,
            "conversation_title": generate_conversation_title(query),
            "user_message_id": user_message_id,
            "bot_message_id": bot_message_id
        })

    except Exception as e:
        return jsonify({"error 5": str(e)}), 500

@app.route('/') 
def start():
    if 'username' not in session :
       return render_template('login.html')
    return redirect(url_for('index'))

@app.route('/login_auth', methods=['POST'])
def login():
    data = request.get_json()

    if data:
        username = data.get('user_name')
        password = data.get('password')
        user = authenticate_user(username, password, get_db_connection('vtiger'))

        if user and user['status'] == 'success':
            session['username'] = user['data']['user_name']
            session['user_id'] = user['data']['user_id']
            session['is_admin'] = user['data']['is_admin']
            session['chat_history'] = []

            conn = get_db_connection('chatbot')
            with conn.cursor() as cursor:
                # Check for active conversation
                sql = """
                SELECT conversation_id, 
                       (SELECT COUNT(*) FROM messages WHERE conversation_id = c.conversation_id) AS message_count
                FROM conversations c 
                WHERE user_id = %s AND status = 'active'
                """
                cursor.execute(sql, (session['user_id'],))
                active_conversation = cursor.fetchone()

                if active_conversation:
                    message_count = active_conversation['message_count']
                    if message_count < 15:
                        # Reuse active conversation
                        session['conversation_id'] = active_conversation['conversation_id']
                        conn.close()
                        return jsonify({
                            'status': 'success',
                            'user': session['username'],
                            'id': session['user_id'],
                            'conversation_id': session['conversation_id'],
                        }), 200
                    elif message_count >= 15:
                        # Close the active conversation
                        cursor.execute(
                            "UPDATE conversations SET status = 'closed' WHERE conversation_id = %s",
                            (active_conversation['conversation_id'],)
                        )
                        conn.commit()

                # Create a new conversation
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                title = f"Conversation - {timestamp}"
                sql = "INSERT INTO conversations (user_id, title, status) VALUES (%s, %s, %s)"
                cursor.execute(sql, (session['user_id'], title, "active"))
                session['conversation_id'] = cursor.lastrowid
            conn.commit()
            conn.close()
            return jsonify({
                'status': 'success',
                'user': session['username'],
                'id': session['user_id'],
                'conversation_id': session['conversation_id'],
            }), 200

        return jsonify({'status': 'failed', 'message': user.get('message', 'Authentication failed')}), 401

    return jsonify({'status': 'failed', 'message': 'Invalid request data'}), 400

@app.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('start'))
    chat_history = session.get('chat_history', [])
    return render_template('index.html', chat_history=chat_history)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('start'))
    return render_template('dashboard.html')


@app.route('/get_history', methods=['GET'])
def history():
    try:
        # Get user details from the session
        user_id = session.get('user_id')
        username = session.get('username')

        if not user_id:
            return jsonify({'status': 'error', 'message': 'User is not logged in.'}), 401

        # Establish database connection
        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        seven_days_ago = datetime.now() - timedelta(days=7)

        # Fetch active and closed conversations separately
        with connection.cursor() as cur:
            # Fetch active conversations with messages, including feedback
            active_query = """
                SELECT 
                    c.conversation_id,
                    c.title,
                    c.created_at AS conversation_created_at,
                    m.message_id,
                    m.sender,
                    m.content AS message_content,
                    m.created_at AS message_created_at,
                    f.feedback,  -- Add feedback field
                    f.remarks,   -- Add remarks field
                    f.file_path  -- Add file path field
                FROM conversations c
                INNER JOIN messages m ON c.conversation_id = m.conversation_id
                LEFT JOIN feedback f ON m.message_id = f.message_id  -- Left join to include feedback
                WHERE c.user_id = %s AND c.status = 'active' AND c.created_at >= %s
                ORDER BY c.conversation_id, m.created_at
            """

            cur.execute(active_query, (user_id, seven_days_ago))
            active_results = cur.fetchall()

            # Fetch closed conversations (only IDs and titles)
            closed_query = """
                SELECT conversation_id, title 
                FROM conversations
                WHERE user_id = %s AND status = 'closed'
            """
            cur.execute(closed_query, (user_id,))
            closed_results = cur.fetchall()

        # Organize active conversations with feedback data
        # Organize active conversations with feedback data
        active_conversations = {}
        for row in active_results:
            conversation_id = row['conversation_id']
            if conversation_id not in active_conversations:
                active_conversations[conversation_id] = {
                    'title': row['title'],
                    'created_at': row['conversation_created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    'messages': []
                }
            
            # If feedback is NULL, set it to 'no response'
            feedback_data = {
                'feedback': row['feedback'] if row['feedback'] else 'no response',  # Set 'no response' if feedback is NULL
                'remarks': row['remarks'] if row['remarks'] else '',
                'file_path': row['file_path'] if row['file_path'] else ''
            }
            
            active_conversations[conversation_id]['messages'].append({
                'message_id': row['message_id'],
                'sender': row['sender'],
                'content': row['message_content'],
                'created_at': row['message_created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'feedback': feedback_data  # Add feedback, even if it's 'no response'
            })

        # Convert active conversations to a list
        active_chat_history = [
            {
                'conversation_id': conv_id,
                'title': conv_data['title'],
                'created_at': conv_data['created_at'],
                'messages': conv_data['messages']
            }
            for conv_id, conv_data in active_conversations.items()
        ]


        # Prepare closed conversations
        closed_conversations = [{'conversation_id': row['conversation_id'], 'title': row['title']} for row in closed_results]

        return jsonify({
            'status': 'success',
            'user': {'id': user_id, 'name': username},
            'active_chat_history': active_chat_history,
            'closed_conversations': closed_conversations
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/get_conversation_details', methods=['POST'])
def get_conversation_details():
    try:
        # Get conversation ID from the request
        conversation_id = request.json.get('conversation_id')

        if not conversation_id:
            return jsonify({'status': 'error', 'message': 'Conversation ID is required.'}), 400

        # Establish database connection
        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        # Fetch messages and feedback
        with connection.cursor() as cur:
            # Include message_id in the query
            messages_query = """
                SELECT 
                    message_id, sender, content, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at
            """
            cur.execute(messages_query, (conversation_id,))
            messages = cur.fetchall()

            feedback_query = """
                SELECT 
                    m.message_id,
                    m.content AS message_content, 
                    f.feedback, 
                    f.remarks, 
                    f.file_path, 
                    f.created_at AS feedback_created_at
                FROM feedback f
                INNER JOIN messages m ON f.message_id = m.message_id
                WHERE m.conversation_id = %s
            """
            cur.execute(feedback_query, (conversation_id,))
            feedbacks = cur.fetchall()

        # Format response to include message_id
        formatted_messages = [
            {
                'message_id': msg['message_id'],
                'sender': msg['sender'],
                'content': msg['content'],
                'created_at': msg['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            } for msg in messages
        ]

        formatted_feedbacks = [
            {
                'message_id': fb['message_id'],
                'message_content': fb['message_content'],
                'feedback': fb['feedback'],
                'remarks': fb['remarks'],
                'file_path': fb['file_path'],
                'created_at': fb['feedback_created_at'].strftime('%Y-%m-%d %H:%M:%S')
            } for fb in feedbacks
        ]

        return jsonify({
            'status': 'success',
            'messages': formatted_messages,
            'feedbacks': formatted_feedbacks
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/edit_conversation', methods=['POST'])
def edit_conversation():
    try:
        data = request.json
        conversation_id = data.get('conversation_id')
        new_title = data.get('title')

        if not conversation_id or not new_title:
            return jsonify({'status': 'error', 'message': 'Invalid input.'}), 400

        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        with connection.cursor() as cur:
            query = "UPDATE conversations SET title = %s WHERE conversation_id = %s"
            cur.execute(query, (new_title, conversation_id))
            connection.commit()

        return jsonify({'status': 'success', 'message': 'Conversation title updated successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/delete_conversation', methods=['POST'])
def delete_conversation():
    try:
        data = request.json
        conversation_id = data.get('conversation_id')

        if not conversation_id:
            return jsonify({'status': 'error', 'message': 'Invalid input.'}), 400

        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        with connection.cursor() as cur:
            # Delete messages and the conversation itself
            delete_messages_query = "DELETE FROM messages WHERE conversation_id = %s"
            delete_conversation_query = "DELETE FROM conversations WHERE conversation_id = %s"
            cur.execute(delete_messages_query, (conversation_id,))
            cur.execute(delete_conversation_query, (conversation_id,))
            connection.commit()

        return jsonify({'status': 'success', 'message': 'Conversation deleted successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/response_feedback', methods=['POST'])
def response_feedback():
    try:
        
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'User is not logged in.'}), 401

        data = request.get_json()
        message_id = data.get('message_id')
        feedback_type = data.get('feedback')

        if not message_id or not feedback_type:
            return jsonify({'status': 'error', 'message': 'Message ID and feedback type are required.'}), 400
        
        if feedback_type == "none":
            feedback_type = "no response" 

        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        with connection.cursor() as cur:
            
            feedback_check_query = """
                SELECT feedback_id FROM feedback WHERE message_id = %s
            """
            cur.execute(feedback_check_query, (message_id,))
            existing_feedback = cur.fetchone()

            if existing_feedback:
                
                update_query = """
                    UPDATE feedback
                    SET feedback = %s, created_at = NOW()
                    WHERE message_id = %s
                """
                cur.execute(update_query, (feedback_type, message_id))
            else:
                
                insert_query = """
                    INSERT INTO feedback (message_id, feedback, created_at)
                    VALUES (%s, %s, NOW())
                """
                cur.execute(insert_query, (message_id, feedback_type))

            connection.commit()

        return jsonify({'status': 'success', 'message': 'Feedback stored successfully.'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# Function to create a user folder if it doesn't exist
def create_user_folder(user_id, user_name):
    
    user_folder = os.path.join(FEEDBACK_FOLDER, f"{user_id}_{user_name}")
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder

# Function to save feedback into the database
def save_feedback(message_id, feedback, remarks, file_paths_json=None):
    connection = None
    try:
        connection = get_db_connection('chatbot')
        if connection is None:
            raise ValueError("Unable to establish database connection.")

        with connection.cursor() as cur:
            # Check if feedback already exists for this message_id
            check_query = """
                SELECT feedback_id FROM feedback WHERE message_id = %s
            """
            cur.execute(check_query, (message_id,))
            existing_feedback = cur.fetchone()

            if existing_feedback:
                # Update the existing feedback
                update_query = """
                    UPDATE feedback
                    SET feedback = %s, remarks = %s, file_path = %s, created_at = %s
                    WHERE message_id = %s
                """
                cur.execute(update_query, (
                    feedback,
                    remarks,
                    file_paths_json,
                    datetime.now(),
                    message_id
                ))
                connection.commit()
                return existing_feedback['feedback_id']  # Return the feedback_id of the updated record
            else:
                # Insert new feedback if no feedback exists for this message_id
                insert_query = """
                    INSERT INTO feedback (message_id, feedback, remarks, file_path, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(insert_query, (
                    message_id,
                    feedback,
                    remarks,
                    file_paths_json,
                    datetime.now()
                ))
                connection.commit()
                feedback_id = cur.lastrowid 
                return feedback_id

    except Exception as e:
        print(f"Error saving feedback: {str(e)}")
        raise

    finally:
        if connection:
            connection.close()


# Route to handle feedback submission
@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    try:
        message_id = request.form.get("message_id")
        feedback = request.form.get("feedback")
        remarks = request.form.get("remarks", "").strip()
        user_id = session.get("user_id")
        user_name = session.get("username")        

        if not message_id or not feedback or not user_id:
            return jsonify({"error": "Message ID, feedback, user ID, and user name are required"}), 400

        user_folder = create_user_folder(user_id, user_name)

        files = request.files.getlist("files[]") 
        file_paths = []

        for file in files:
            if file:
                filename = secure_filename(file.filename)
                file_name_without_extension, file_extension = os.path.splitext(filename)
                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                file_name_with_timestamp = f"{file_name_without_extension}_{timestamp}{file_extension}"
                file_path = os.path.join(user_folder, file_name_with_timestamp)
                file.save(file_path)

                file_paths.append(file_path)

        file_paths_json = json.dumps(file_paths)
        # return jsonify({"message_id" : message_id,"feedback" : feedback,"remarks" : remarks,"file_paths":file_paths  })
        feedback_id = save_feedback(message_id, feedback, remarks, file_paths_json)
        if not feedback_id:
            return jsonify({"error": "Error saving feedback"}), 500  # Ensure feedback_id is valid

        return jsonify({
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_id
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Start a new chat
@app.route('/new_chat', methods=['POST'])
def new_chat():
    conversation_id = session.get('conversation_id')
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection('chatbot')
    with conn.cursor() as cursor:
                
        if conversation_id:
          
            cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s", (conversation_id,))
            message_count = cursor.fetchone()['COUNT(*)']  # Access the count value
            if message_count > 15:
                cursor.execute("UPDATE conversations SET status = 'closed' WHERE conversation_id = %s", (conversation_id,))
        
                # Get current timestamp and format it as desired
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                title = f"Conversation - {timestamp}"

                # Create a new conversation with the timestamp in the title
                cursor.execute("INSERT INTO conversations (user_id, title, status) VALUES (%s, %s, %s)", 
                            (user_id, title, "active"))
                session['conversation_id'] = cursor.lastrowid

                conn.commit()
                conn.close()
                return jsonify({'message': 'New chat started', 'conversation_id': session['conversation_id']})
    return jsonify({'message': 'Already a chat is existing without messages', "message_count":message_count})


@app.route('/get_all_users_status', methods=['GET'])
def get_users_status():
    # Check if the current user is admin
    if 'is_admin' in session and session['is_admin'] == 1:
        try:
            # Connect to the database
            conn = get_db_connection('chatbot')
            with conn.cursor() as cur:
                # SQL query to fetch user_id, user_name, login_status, and last_login
                sql = """
                    SELECT user_id, user_name, login_status, last_login
                    FROM users
                    ORDER BY last_login DESC
                """
                cur.execute(sql) 
                users_status = cur.fetchall()  

            conn.close()

            # Return the result to frontend
            return jsonify({'status': 'success', 'data': users_status}), 200

        except pymysql.MySQLError as e:
            return jsonify({'status': 'error', 'message': f"Database error: {e.args[1]}"}), 500
    else:
        return jsonify({'status': 'failed', 'message': 'Unauthorized access'}), 403


@app.route('/overview', methods=['GET'])
def get_overview_data():
    conn = get_db_connection('chatbot')
    data = {}
    try:
        with conn.cursor() as cursor:

            # Fetch total number of users
            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            data['total_users'] = cursor.fetchone()['total_users']

            # Fetch online users count
            cursor.execute("SELECT COUNT(*) AS online_users FROM users WHERE login_status = 'online'")
            data['online_users'] = cursor.fetchone()['online_users']

            # Fetch likes and dislikes count
            cursor.execute("SELECT COUNT(*) AS likes FROM feedback WHERE feedback = 'like'")
            data['likes'] = cursor.fetchone()['likes']

            cursor.execute("SELECT COUNT(*) AS dislikes FROM feedback WHERE feedback = 'dislike'")
            data['dislikes'] = cursor.fetchone()['dislikes']
    finally:
        conn.close()
    return jsonify(data)

@app.route('/users', methods=['GET'])
def get_users_data():
    conn = get_db_connection('chatbot')
    data = []
    try:
        with conn.cursor() as cursor:
            # Fetch recent users
            cursor.execute("""
                SELECT user_id, user_name, login_status, last_login
                FROM users
                ORDER BY last_login DESC
                LIMIT 10
            """)
            data = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(data)

@app.route('/user_usage', methods=['GET'])
def get_user_usage_data():
    # Get the time range parameter from the request
    time_range = request.args.get('time_range', default=7, type=int)  # Default is 7 days

    conn = get_db_connection('chatbot')
    data = []
    try:
        with conn.cursor() as cursor:
            # Adjust the SQL query based on the selected time range
            cursor.execute(f"""
                SELECT 
                    DATE(m.created_at) AS date,
                    COUNT(m.message_id) AS total_messages,
                    COUNT(DISTINCT c.user_id) AS total_users
                FROM 
                    messages m
                JOIN 
                    conversations c ON m.conversation_id = c.conversation_id
                JOIN 
                    users u ON c.user_id = u.user_id
                WHERE
                    m.created_at >= CURDATE() - INTERVAL {time_range} DAY
                GROUP BY 
                    DATE(m.created_at)
                ORDER BY 
                    DATE(m.created_at) DESC
            """)
            data = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(data)


@app.route('/get_feedbacks', methods=['GET'])
def get_feedbacks():
    feedback_type = request.args.get('feedback_type', default='like', type=str)
    connection = get_db_connection('chatbot')
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    
    try:
        query = """
            SELECT 
                m.message_id, 
                m.content, 
                f.feedback, 
                f.remarks, 
                f.created_at,
                c.user_id, 
                u.user_name
            FROM messages m
            JOIN feedback f ON m.message_id = f.message_id
            JOIN conversations c ON m.conversation_id = c.conversation_id
            JOIN users u ON c.user_id = u.user_id
            WHERE f.feedback = %s
            ORDER BY f.created_at DESC;
        """
        
        cursor.execute(query, (feedback_type,))
        feedbacks = cursor.fetchall()

        return jsonify(feedbacks) 
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        cursor.close()
        connection.close()


@app.route('/logout')
def logout():
    if 'username' not in session:
        return render_template('login.html')
    
    user_id = session.get('user_id')
    conversation_id = session.get('conversation_id')

    if user_id:
        conn = get_db_connection('chatbot')
        with conn.cursor() as cursor:
            sql_update_user = """
                UPDATE users
                SET login_status = 'offline', last_login = NOW()
                WHERE user_id = %s
            """
            cursor.execute(sql_update_user, (user_id,))
        
        conn.commit()
        conn.close()

    if conversation_id:
        conn = get_db_connection('chatbot')
        with conn.cursor() as cursor:
            sql = "SELECT COUNT(*) AS message_count FROM messages WHERE conversation_id = %s"
            cursor.execute(sql, (conversation_id,))
            message_count = cursor.fetchone()['message_count']

            if message_count >= 15:
                cursor.execute("UPDATE conversations SET status = 'closed' WHERE conversation_id = %s", (conversation_id,))
        conn.commit()
        conn.close()

    session.clear()
    return redirect(url_for('start'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5003)
