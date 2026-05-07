import os
import sqlite3
from flask import Flask, request, render_template, jsonify
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "website", "website", "templates")

app = Flask(__name__, template_folder=TEMPLATES_DIR)

# ------------------ DATABASE SETUP ------------------

def get_db():
    return sqlite3.connect("users.db")

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS users")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,

        ewaste_points INTEGER DEFAULT 0,
        organic_points INTEGER DEFAULT 0,
        plastic_points INTEGER DEFAULT 0,
        metal_points INTEGER DEFAULT 0,
        glass_points INTEGER DEFAULT 0,

        total_points INTEGER DEFAULT 0,
        rank TEXT DEFAULT 'Iron',
        
        daily_points_today INTEGER DEFAULT 0,
        last_update_date TEXT DEFAULT '',
        daily_cap INTEGER DEFAULT 500
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ------------------ RANK SYSTEM ------------------

def calculate_rank(points):
    ranks = [
        ('Iron', 0, 99),
        ('Bronze', 100, 249),
        ('Silver', 250, 499),
        ('Gold', 500, 999),
        ('Platinum', 1000, 1499),
        ('Diamond', 1500, 2499),
        ('Ascendant', 2500, 3999),
        ('Immortal', 4000, 5999),
        ('Radiant', 6000, float('inf'))
    ]

    for name, low, high in ranks:
        if low <= points <= high:
            return name
    return "Iron"

# ------------------ ROUTES ------------------
@app.route('/organic-ranked.html')
def organic_ranked():
    return render_template("organic-ranked.html")

@app.route('/plastic-ranked.html')
def plastic_ranked():
    return render_template("plastic-ranked.html")

@app.route('/metal-ranked.html')
def metal_ranked():
    return render_template("metal-ranked.html")

@app.route('/glass-ranked.html')
def glass_ranked():
    return render_template("glass-ranked.html")

@app.route('/ewaste-ranked.html')
def ewaste_ranked():
    return render_template("ewaste-ranked.html")


@app.route('/ranked.html')
def ranked():
    return render_template("ranked.html")

@app.route('/SDG.html')
def sdg():
    return render_template("SDG.html")

@app.route('/map.html')
def map():
    return render_template("map.html")

@app.route('/quiz.html')
def quiz():
    return render_template("quiz.html")

@app.route('/')
def home():
    return render_template("login.html")

@app.route('/index.html')
def index():
    return render_template("index.html")

@app.route('/tierlist.html')
def tierlist():
    return render_template("tierlist.html")

@app.route('/AIbot.html')
def AIbot():
    return render_template("AIbot.html")

# ------------------ AUTH ------------------

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return "fail"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    if cursor.fetchone():
        conn.close()
        return "exists"

    cursor.execute("""
        INSERT INTO users (username, password)
        VALUES (?, ?)
    """, (username, password))

    conn.commit()
    conn.close()

    return "success"

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()

    conn.close()

    return "success" if user else "fail"

# ------------------ UPDATE POINTS ------------------

@app.route('/api/update_ranking', methods=['POST'])
def update_ranking():
    data = request.json
    username = data.get('username')

    if not username:
        return jsonify({'error': 'Username required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Get user's current daily cap info
    cursor.execute("""
        SELECT daily_points_today, last_update_date, daily_cap
        FROM users WHERE username=?
    """, (username,))
    
    cap_info = cursor.fetchone()
    if not cap_info:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    daily_points_today, last_update_date, daily_cap = cap_info
    today = datetime.now().strftime('%Y-%m-%d')

    # Reset daily counter if it's a new day
    if last_update_date != today:
        daily_points_today = 0

    # Calculate points to add
    points_to_add = (
        int(data.get('ewaste_points', 0)) +
        int(data.get('organic_points', 0)) +
        int(data.get('plastic_points', 0)) +
        int(data.get('metal_points', 0)) +
        int(data.get('glass_points', 0))
    )

    # Check if adding these points would exceed daily cap
    if daily_points_today + points_to_add > daily_cap:
        remaining = max(0, daily_cap - daily_points_today)
        conn.close()
        return jsonify({
            'error': 'Daily cap exceeded',
            'daily_cap': daily_cap,
            'points_today': daily_points_today,
            'remaining': remaining
        }), 429

    # Update each category
    cursor.execute("""
        UPDATE users SET
            ewaste_points = ewaste_points + ?,
            organic_points = organic_points + ?,
            plastic_points = plastic_points + ?,
            metal_points = metal_points + ?,
            glass_points = glass_points + ?,
            daily_points_today = daily_points_today + ?,
            last_update_date = ?
        WHERE username = ?
    """, (
        int(data.get('ewaste_points', 0)),
        int(data.get('organic_points', 0)),
        int(data.get('plastic_points', 0)),
        int(data.get('metal_points', 0)),
        int(data.get('glass_points', 0)),
        points_to_add,
        today,
        username
    ))

    # Get updated values
    cursor.execute("""
        SELECT ewaste_points, organic_points, plastic_points, metal_points, glass_points
        FROM users WHERE username=?
    """, (username,))
    
    row = cursor.fetchone()
    total_points = sum(row)
    rank = calculate_rank(total_points)

    # Save total + rank
    cursor.execute("""
        UPDATE users SET total_points=?, rank=? WHERE username=?
    """, (total_points, rank, username))

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'total_points': total_points,
        'rank': rank,
        'daily_points_today': daily_points_today + points_to_add,
        'daily_cap': daily_cap,
        'remaining_today': daily_cap - (daily_points_today + points_to_add)
    })

# ------------------ GET USER DATA ------------------

@app.route('/get_user_data')
def get_user_data():
    username = request.args.get('username')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ewaste_points, organic_points, plastic_points,
               metal_points, glass_points, total_points, rank
        FROM users WHERE username=?
    """, (username,))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found'})

    return jsonify({
        'ewaste': user[0],
        'organic': user[1],
        'plastic': user[2],
        'metal': user[3],
        'glass': user[4],
        'total_points': user[5],
        'rank': user[6]
    })

# ------------------ DAILY CAP STATUS ------------------

@app.route('/get_daily_cap_status')
def get_daily_cap_status():
    username = request.args.get('username')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT daily_points_today, daily_cap, last_update_date
        FROM users WHERE username=?
    """, (username,))

    cap_info = cursor.fetchone()
    conn.close()

    if not cap_info:
        return jsonify({'error': 'User not found'})

    daily_points_today, daily_cap, last_update_date = cap_info
    today = datetime.now().strftime('%Y-%m-%d')

    # If it's a new day, reset the count
    if last_update_date != today:
        daily_points_today = 0

    return jsonify({
        'daily_points_today': daily_points_today,
        'daily_cap': daily_cap,
        'remaining_today': max(0, daily_cap - daily_points_today)
    })

# ------------------ LEADERBOARD ------------------

@app.route('/get_users')
def get_users():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, rank, total_points
        FROM users
        WHERE total_points > 0
    """)

    users = cursor.fetchall()
    conn.close()

    # Sort descending
    users.sort(key=lambda x: x[2], reverse=True)

    return jsonify([{
        'username': u[0],
        'rank': u[1],
        'points': u[2]
    } for u in users])

# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run(debug=True, port=5500)
