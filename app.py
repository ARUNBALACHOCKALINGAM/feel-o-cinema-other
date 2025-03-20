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

# Add Access-Control-Allow-Credentials header
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# MongoDB Connection
try:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DB_NAME")]
    print("Connected to MongoDB")
except Exception as e:
    print("Failed to connect to MongoDB:", str(e))

# Google OAuth Client ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")




db = client[os.getenv("MONGO_DB_NAME")]
users_collection = db["users"]
watchlists_collection = db["watchlists"]
journals_collection = db["journals"]



@app.route("/auth/google", methods=["POST"])
def google_auth():
    token = request.json.get("token")
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        print("Google OAuth successful:", idinfo)
        
        user = users_collection.find_one({"email": idinfo["email"]})
        if not user:
            user = {"email": idinfo["email"], "name": idinfo["name"]}
            users_collection.insert_one(user)
        
        session["user_email"] = user["email"]
        print("Session after login:", session)
        
        user["_id"] = str(user["_id"])
        return jsonify({"message": "Login successful", "user": user})
    except Exception as e:
        print("Google OAuth failed:", str(e))
        return jsonify({"error": str(e)}), 401



@app.route("/watchlist", methods=["POST"])
def create_watchlist():
    user_email = session.get("user_email")
    
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    watchlist_name = data.get("name")

    # Check if a watchlist with the same name already exists
    existing_watchlist = watchlists_collection.find_one({
        "user_email": user_email,
        "name": watchlist_name
    })

    if existing_watchlist:
        return jsonify({"error": "Watchlist with this name already exists"}), 400

    # Create new watchlist
    watchlist = {
        "name": watchlist_name,
        "user_email": user_email,
        "movies": []
    }
    result = watchlists_collection.insert_one(watchlist)
    watchlist["_id"] = str(result.inserted_id)

    return jsonify(watchlist)

@app.route("/watchlist/<watchlist_name>", methods=["PUT"])
def add_movie_to_watchlist(watchlist_name):
    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    result = watchlists_collection.update_one(
        {"name": watchlist_name, "user_email": user_email},
        {"$push": {"movies": data["movie"]}}
    )
    if result.modified_count > 0:
        return jsonify({"message": "Movie added to watchlist"})
    return jsonify({"error": "Watchlist not found"}), 404



@app.route("/watchlist", methods=["GET"])
def get_watchlists():
    user_email = session.get("user_email")
    print("Session:", session)  # Debugging: Print the session
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    
    watchlists = list(watchlists_collection.find({"user_email": user_email}))
   
    for watchlist in watchlists:
        watchlist["_id"] = str(watchlist["_id"])
    
    return jsonify(watchlists)

# Add Journal Entry
@app.route("/journal", methods=["POST"], endpoint="add_journal_entry")
def add_journal_entry():
    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    journal_entry = {
        "user_email": user_email,
        "movie_title": data["movie_title"],
        "entry": data["entry"],
        "date": data["date"]
    }
    result = journals_collection.insert_one(journal_entry)
    journal_entry["_id"] = str(result.inserted_id)
    
    return jsonify(journal_entry)

# Get Journal Entries
@app.route("/journal", methods=["GET"], endpoint="get_journal_entries")
def get_journal_entries():
    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    
    entries = list(journals_collection.find({"user_email": user_email}))
    for entry in entries:
        entry["_id"] = str(entry["_id"])
    
    return jsonify(entries)


@app.route("/watchlist/<name>", methods=["GET"])
def get_watchlist(name):
    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    
    watchlist = watchlists_collection.find_one({
        "user_email": user_email,
        "name": name
    })
    
    if not watchlist:
        return jsonify({"error": "Watchlist not found"}), 404
    
    watchlist["_id"] = str(watchlist["_id"])
    return jsonify(watchlist)

@app.route('/watchlist/<name>/cover')
def get_watchlist_cover(name):
    user_email = session.get("user_email")
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401

    # Get watchlist movies
    watchlist = watchlists_collection.find_one({
        "user_email": user_email,
        "name": name
    })
    
    if not watchlist:
        return jsonify({"error": "Watchlist not found"}), 404

    posters = []
    for movie in watchlist["movies"][:4]:  # Get first 4 movies
        if movie.get("poster_path"):
            response = requests.get(f"https://image.tmdb.org/t/p/w500{movie['poster_path']}")
            if response.status_code == 200:
                posters.append(Image.open(BytesIO(response.content)))

    if not posters:
        # Return default cover image
        return send_file("static/default-cover.jpg", mimetype='image/jpeg')

    # Create collage
    if len(posters) == 1:
        collage = posters[0]
    else:
        # Calculate grid size
        cols = min(2, len(posters))
        rows = math.ceil(len(posters) / cols)
        
        # Resize images
        poster_size = (600, 900)
        resized = [poster.resize(poster_size) for poster in posters]
        
        # Create canvas
        collage = Image.new('RGB', (poster_size[0]*cols, poster_size[1]*rows))
        
        # Paste images
        for i, img in enumerate(resized):
            row = i // cols
            col = i % cols
            collage.paste(img, (col*poster_size[0], row*poster_size[1]))

    # Save to bytes
    img_io = BytesIO()
    collage.save(img_io, 'JPEG', quality=85)
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/jpeg')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True,port=port)