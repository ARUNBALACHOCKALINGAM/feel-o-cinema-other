from flask import Flask, request, jsonify, session
from flask_cors import CORS
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Fix proxy configuration
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure CORS
CORS(
    app,
    supports_credentials=True,
    origins=["https://feel-o-cinema.vercel.app"]  # Frontend domain
)

# Session configuration
app.config.update({
    'SECRET_KEY': os.getenv("SECRET_KEY"),
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_SAMESITE': 'None',
    'SESSION_COOKIE_HTTPONLY': True,
})

# MongoDB Connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]
users_collection = db["users"]
watchlists_collection = db["watchlists"]

# Google OAuth Client ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

@app.route("/auth/google", methods=["POST"])
def google_auth():
    token = request.json.get("token")
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        user = users_collection.find_one({"email": idinfo["email"]})
        if not user:
            user = {"email": idinfo["email"], "name": idinfo["name"]}
            users_collection.insert_one(user)
        
        session["user_email"] = user["email"]
        print("Session after login:", session)
        
        user["_id"] = str(user["_id"])
        return jsonify({"message": "Login successful", "user": user})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route("/watchlist", methods=["GET"])
def get_watchlists():
    print("Session in /watchlist:", session)
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