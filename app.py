import os
import psycopg2
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import date, timedelta, datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_DATABASE"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to PostgreSQL database. Please check your .env configuration and ensure the database is running.")
        print(f"Details: {e}")
        return None

# --- NEW: Database Initialization ---
def initialize_database():
    """
    Checks for the required table on startup and creates it if it doesn't exist.
    This replaces the need for a separate init_db.py script on the server.
    """
    conn = get_db_connection()
    if not conn:
        print("CRITICAL: Could not connect to database for initialization. Aborting.")
        return
        
    try:
        cur = conn.cursor()
        print("Initializing database: Checking for 'time_log' table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS time_log (
                id SERIAL PRIMARY KEY,
                entry_date DATE NOT NULL,
                time_slot TIME NOT NULL,
                activity TEXT,
                category TEXT,
                priority TEXT,
                notes TEXT,
                UNIQUE (entry_date, time_slot)
            );
        """)
        conn.commit()
        cur.close()
        print("Database initialized successfully. Table 'time_log' is ready.")
    except Exception as e:
        print(f"An error occurred during database initialization: {e}")
    finally:
        if conn is not None:
            conn.close()

# --- Main Application Route ---
@app.route('/')
def index():
    """
    Main view that displays the time log for a specific day and the dashboard.
    """
    # Determine the date to show (today or from query parameter)
    date_str = request.args.get('date', date.today().isoformat())
    try:
        current_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        current_date = date.today()

    conn = get_db_connection()
    if not conn:
        return "<h1>Database Connection Error</h1><p>Could not connect to the database. Please check the console for details and verify your .env file settings.</p>", 500

    cur = conn.cursor()

    # Fetch existing entries for the current date
    cur.execute("SELECT time_slot, activity, category, priority, notes FROM time_log WHERE entry_date = %s", (current_date,))
    entries_list = cur.fetchall()
    entries = {row[0].strftime('%H:%M'): {'activity': row[1], 'category': row[2], 'priority': row[3], 'notes': row[4]} for row in entries_list}

    # Fetch dashboard data
    cur.execute("""
        SELECT category, COUNT(*) * 0.25 as total_hours
        FROM time_log
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY total_hours DESC
    """)
    dashboard_data = cur.fetchall()

    cur.close()
    conn.close()

    # Generate 15-minute time slots for a full day
    time_slots = []
    for hour in range(24):
        for minute in range(0, 60, 15):
            time_slots.append(f"{hour:02d}:{minute:02d}")

    # Navigation links for previous and next day
    prev_day = (current_date - timedelta(days=1)).isoformat()
    next_day = (current_date + timedelta(days=1)).isoformat()
    today_day = date.today().isoformat()

    return render_template_string(HTML_TEMPLATE,
                                  time_slots=time_slots,
                                  entries=entries,
                                  current_date=current_date,
                                  date_str=current_date.isoformat(),
                                  dashboard_data=dashboard_data,
                                  prev_day=prev_day,
                                  next_day=next_day,
                                  today_day=today_day)

# --- Form Submission Route ---
@app.route('/save_entry', methods=['POST'])
def save_entry():
    """Saves or updates a time log entry."""
    entry_date = request.form['entry_date']
    time_slot = request.form['time_slot']
    activity = request.form['activity']
    category = request.form['category']
    priority = request.form['priority']
    notes = request.form['notes']

    conn = get_db_connection()
    if not conn:
        return "<h1>Database Connection Error</h1>", 500
    
    cur = conn.cursor()

    # Use an "UPSERT" operation: INSERT if new, UPDATE if it exists
    cur.execute("""
        INSERT INTO time_log (entry_date, time_slot, activity, category, priority, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (entry_date, time_slot)
        DO UPDATE SET
            activity = EXCLUDED.activity,
            category = EXCLUDED.category,
            priority = EXCLUDED.priority,
            notes = EXCLUDED.notes;
    """, (entry_date, time_slot, activity, category, priority, notes))
    
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('index', date=entry_date))


# --- HTML Template (No Changes Below) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>15-Minute Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
        .dark { color-scheme: dark; }
    </style>
</head>
<body class="bg-gray-900 text-gray-200 p-4 sm:p-6 lg:p-8">
    <div class="max-w-7xl mx-auto">
        <header class="text-center mb-8">
            <h1 class="text-4xl font-bold text-white tracking-tight">15-Minute Time Tracker</h1>
            <p class="text-gray-400 mt-2">Meticulously track your schedule, priorities, and focus.</p>
        </header>

        <main class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <!-- Left Column: Dashboard -->
            <aside class="lg:col-span-1 space-y-6">
                 <div class="bg-gray-800 p-6 rounded-lg shadow-lg">
                    <h2 class="text-2xl font-semibold text-white mb-4">Dashboard</h2>
                    {% if dashboard_data %}
                        <ul class="space-y-3">
                        {% for item in dashboard_data %}
                            <li class="flex justify-between items-center bg-gray-700 p-3 rounded-md">
                                <span class="font-medium text-white">{{ item[0] }}</span>
                                <span class="text-lg font-semibold text-cyan-400">{{ '%.2f'|format(item[1]) }} hrs</span>
                            </li>
                        {% endfor %}
                        </ul>
                    {% else %}
                        <p class="text-gray-400">No data yet. Start tracking to see your summary here!</p>
                    {% endif %}
                </div>
            </aside>

            <!-- Right Column: Daily Log -->
            <div class="lg:col-span-2">
                <div class="bg-gray-800 p-6 rounded-lg shadow-lg">
                    <div class="flex flex-col sm:flex-row justify-between items-center mb-6">
                        <h2 class="text-2xl font-semibold text-white">Daily Log</h2>
                        <div class="flex items-center space-x-2 mt-4 sm:mt-0">
                            <a href="{{ url_for('index', date=prev_day) }}" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">&larr; Prev</a>
                            <a href="{{ url_for('index', date=today_day) }}" class="bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-4 rounded-lg transition-colors text-center">{{ current_date.strftime('%A, %B %d, %Y') }}</a>
                            <a href="{{ url_for('index', date=next_day) }}" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">Next &rarr;</a>
                        </div>
                    </div>

                    <div class="space-y-4">
                        {% for slot in time_slots %}
                            {% set entry = entries.get(slot) %}
                            <div class="bg-gray-900/50 p-4 rounded-lg" x-data="{ open: false }">
                                <div class="flex items-center cursor-pointer" @click="open = !open">
                                    <span class="font-mono text-lg text-cyan-400 w-20">{{ slot }}</span>
                                    <div class="flex-grow ml-4">
                                        {% if entry %}
                                            <p class="font-semibold text-white">{{ entry.activity or 'No activity logged' }}</p>
                                            <p class="text-sm text-gray-400">{{ entry.category or 'Uncategorized' }}</p>
                                        {% else %}
                                            <p class="text-gray-500">Empty slot...</p>
                                        {% endif %}
                                    </div>
                                    <button class="ml-4 text-gray-400 hover:text-white transition-transform" :class="{'rotate-180': open}">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                                    </button>
                                </div>
                                <div x-show="open" x-transition class="mt-4 pt-4 border-t border-gray-700">
                                    <form action="{{ url_for('save_entry') }}" method="post" class="space-y-4">
                                        <input type="hidden" name="entry_date" value="{{ date_str }}">
                                        <input type="hidden" name="time_slot" value="{{ slot }}">
                                        
                                        <div>
                                            <label class="block text-sm font-medium text-gray-300">Activity</label>
                                            <input type="text" name="activity" value="{{ entry.activity if entry else '' }}" placeholder="e.g., Wrote project proposal" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 text-white">
                                        </div>
                                        <div>
                                            <label class="block text-sm font-medium text-gray-300">Category</label>
                                            <input type="text" name="category" value="{{ entry.category if entry else '' }}" placeholder="e.g., Deep Work, Admin, Leisure" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 text-white">
                                        </div>
                                        <div>
                                            <label class="block text-sm font-medium text-gray-300">Intended Priority</label>
                                            <input type="text" name="priority" value="{{ entry.priority if entry else '' }}" placeholder="e.g., Finish Q3 report" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 text-white">
                                        </div>
                                        <div>
                                            <label class="block text-sm font-medium text-gray-300">Mental Focus / Notes</label>
                                            <textarea name="notes" rows="2" placeholder="e.g., Felt focused but distracted by emails" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 text-white">{{ entry.notes if entry else '' }}</textarea>
                                        </div>
                                        <div class="text-right">
                                            <button type="submit" class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 focus:ring-offset-gray-800">Save Entry</button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </main>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</body>
</html>
"""

# Call the initialization function when the script starts
initialize_database()

if __name__ == '__main__':
    # This is here for direct `python app.py` execution
    app.run(debug=True, port=5001)

