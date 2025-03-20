from flask import Flask, request, jsonify, session
from flask_cors import CORS
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://feel-o-cinema.vercel.app"])
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SESSION_COOKIE_NAME'] = 'feel_o_cinema_session'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_DOMAIN'] = '.onrender.com'  # Replace with your backend domain

# MongoDB Connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]
users_collection = db["users"]
watchlists_collection = db["watchlists"]

# Google OAuth Client ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route("/auth/google", methods=["POST"])
def google_auth():
    token = request.json.get("token")
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        user = users_collection.find_one({"email": idinfo["email"]})
        if not user:
            user = {"email": idinfo["email"], "name": idinfo["name"]}
            users_collection.insert_one(user)
        
        # Set user_email in the session
        session["user_email"] = user["email"]
        print("Session after login:", session)  # Debugging: Print the session
        
        user["_id"] = str(user["_id"])
        return jsonify({"message": "Login successful", "user": user})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route("/watchlist", methods=["GET"])
def get_watchlists():
    print("Session in /watchlist:", session)  # Debugging: Print the session
    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    
    watchlists = list(watchlists_collection.find({"user_email": user_email}))
    for watchlist in watchlists:
        watchlist["_id"] = str(watchlist["_id"])
    
    return jsonify(watchlists)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True, port=port)