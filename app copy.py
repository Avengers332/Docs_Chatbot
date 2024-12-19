from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify, make_response
from flask_mysqldb import MySQL
from login import authenticate_user
from pdf_upload_and_embedding import app as upload_app
from query_response_processing import process_query_and_get_response, load_images_from_folder
from langchain import HuggingFaceHub
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from flask_cors import CORS
from query_response_processing import get_natural_response
import secrets
import logging
from config import Config
from database.chatbot import init_chatbot_connection
from database.vtiger import init_vtiger_connection

app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

# Secret key for session management
app.secret_key = secrets.token_hex(16)

app.register_blueprint(upload_app)

# Initialize MySQL
global mysql_vtiger 
mysql_vtiger = init_vtiger_connection(app, Config)
mysql_chatbot = init_chatbot_connection(app, Config)

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_FOLDER = 'data/vector_db'

# Embedding and Database Setup
embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
chroma_db = Chroma(persist_directory=VECTOR_DB_FOLDER, embedding_function=embedding_function)

# LLM Setup
llm = HuggingFaceHub(
    repo_id="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",   
    huggingfacehub_api_token="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",
    model_kwargs={"temperature": 0.7, "max_length": 500}
)

def save_chat_history(user_id, user_name, message, sender, feedback=None, remarks=None, file_path=None):
   
    try:
        cur = mysql_chatbot.connection.cursor()
        query = """
        INSERT INTO chat_history (user_id, user_name, message, sender, feedback, remarks, file_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (user_id, user_name, message, sender, feedback, remarks, file_path))
        mysql_chatbot.connection.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Error saving chat history: {str(e)}")
        mysql_chatbot.connection.rollback()

@app.route("/query", methods=["POST"])
def query():
    try:
        data = request.get_json()
        query = data.get("query", "")
        if not query:
            return jsonify({"error": "Query is required"}), 400

        retriever = chroma_db.as_retriever(search_kwargs={"k": 3})
        chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, input_key="question")
        
        all_images = load_images_from_folder('static/images')
        casual_queries = ["hi", "hello", "how are you", "hey", "what's up", "greetings"]

        # Convert query to lowercase for simple matching
        query_lower = query.lower().strip()

        # Check if the query matches any of the casual queries
        if any(greeting in query_lower for greeting in casual_queries):
            # Return a simple, dynamic casual response
            refined_prompt = get_natural_response(query)
            save_chat_history(user_id=session.get('user_id'), user_name=session.get('user'), message=query, sender='user')
            save_chat_history(user_id=session.get('user_id'), user_name=session.get('user'), message=refined_prompt, sender='bot')
             # Store the chat in session
            session.setdefault('chat_history', []).append({"sender": "user", "message": query})
            session.setdefault('chat_history', []).append({"sender": "bot", "message": refined_prompt})
            return jsonify({"response": refined_prompt})
        # else:
        
            # refined_prompt = f"""
            # You are an AI assistant trained to answer questions based on both text and images. To better understand and respond to the query below, consider the following steps:
            
            # 1. First, fully comprehend the query by analyzing its core intent.
            # 2. Retrieve the most relevant information from the text and images available, ensuring you pay attention to details that will help clarify the user's question.

            # Query: "{query}"

            # Context: You have access to the following:
            # - Text from documents retrieved based on the query.
            # - Images that may provide additional context or visual explanations related to the query.

            # Your response should:
            # - Be clear and well-structured, answering the question as comprehensively as possible based on the available information.
            # - When appropriate, reference relevant images to explain the query more clearly, providing a description of what’s visible in the image and its relation to the query.
            # - Ensure your answer is coherent and free from abrupt or incomplete sentences.
            # - If the query is casual or conversational (like 'Hi'), respond briefly and friendly:
            #     - For example, simply return: "Hello! How can I assist you today?"
            #     - Avoid overly long responses. Only acknowledge greetings or casual questions with a brief, natural reply, without requesting more details or explanation.
            # - If the query is too vague or doesn't relate to any available data, provide a short and clear response like: "I wasn't able to find anything related to your query. Could you provide more details or clarify?"

            # If no relevant data or information is found, reply with a simple message:
            #     "Unfortunately, I couldn't find anything related to your query. Could you provide more details or clarify your question?"

            # The goal is to provide a response that fits the tone of the query—short and friendly for casual greetings, and clear and informative for more specific inquiries.
            # """
        
        response_data = process_query_and_get_response(query, chain, llm, all_images)
        save_chat_history(user_id=session.get('user_id'), user_name=session.get('user'), message=query, sender='user')
        save_chat_history(user_id=session.get('user_id'), user_name=session.get('user'), message=response_data.get("response"), sender='bot')
        
        # Store the chat in session
        session.setdefault('chat_history', []).append({"sender": "user", "message": query})
        session.setdefault('chat_history', []).append({"sender": "bot", "message": response_data.get("response")})

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def start():
    return render_template('login.html')



@app.route('/login_auth', methods=['POST'])
def login():
    data = request.get_json()  # Extract JSON data
    if data:
        username = data.get("user_name")
        password = data.get("password")
        # return {'user_name': username, 'password' : password}
    
    user = authenticate_user(username, password, mysql_vtiger)
    return {'user': user}
    
    if user:
        # session['user'] = user['data']['user_name']
        # session['user_id'] = user['data']['user_id'] 
        # session['chat_history'] = [] 
        # return {'status': 'success', 'user': session['user']}  
        return {'status': 'success', 'user': user}  
    else:
        return {'status': 'failed'}  
    
    

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('start'))
    chat_history = session.get('chat_history', [])
    return render_template('index.html', chat_history=chat_history)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('start'))
    return render_template('dashboard.html')


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5003)
