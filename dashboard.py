from flask import Flask, jsonify, render_template,Blueprint,request
from db_utils import get_db_connection

app = Blueprint('dashboard', __name__)







@app.route('/dashboard/user_usage', methods=['GET'])
def get_user_usage_data():
    conn = get_db_connection('chatbot')
    data = {}
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.user_name, COUNT(m.message_id) AS messages_count
                FROM users u
                LEFT JOIN conversations c ON u.user_id = c.user_id
                LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                GROUP BY u.user_name
                ORDER BY messages_count DESC
                LIMIT 10
            """)
            data = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(data)


@app.route('/dashboard/feedbacks_data', methods=['GET'])
def get_feedbacks_data():
    conn = get_db_connection('chatbot')
    data = {}
    try:
        with conn.cursor() as cursor:
            # Fetch feedback summary for visualization
            cursor.execute("""
                SELECT feedback, COUNT(*) AS count
                FROM feedback
                GROUP BY feedback
            """)
            feedback_summary = cursor.fetchall()
            data['feedback_summary'] = feedback_summary
    finally:
        conn.close()
    return jsonify(data)


# Main route to render the dashboard modal
@app.route('/dashboard', methods=['GET'])
def render_dashboard():
    return render_template('dashboard.html')  # Your HTML with the modal implementation
