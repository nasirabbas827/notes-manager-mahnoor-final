from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"

DATABASE = "notes_manager.db"

# ---------------- Flask-Login Setup ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, username, email, first_name, last_name, phone):
        self.id = user_id
        self.username = username
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM Users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['user_id'], user['username'], user['email'], user['first_name'], user['last_name'], user['phone'])
    return None

# ---------------- Database Connection ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- Home Page ----------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- Sync Guest Notes ----------------
@app.route('/sync_guest_notes', methods=['POST'])
@login_required
def sync_guest_notes():
    user_id = current_user.id
    notes = request.json.get("notes", [])

    conn = get_db_connection()
    cursor = conn.cursor()

    synced_count = 0
    for note in notes:
        title = note.get("title", "Untitled")
        content = note.get("content", "")
        categoryname = note.get("categoryname", "Miscellaneous")
        ispinned = int(note.get("ispinned", 0))
        created_at = note.get("created_at", None)

        cursor.execute("""
            SELECT id FROM Notes 
            WHERE user_id = ? AND title = ? AND content = ? AND categoryname = ?
        """, (user_id, title, content, categoryname))
        exists = cursor.fetchone()

        if not exists:
            cursor.execute("""
                INSERT INTO Notes (user_id, title, content, categoryname, ispinned, isdraft, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (user_id, title, content, categoryname, ispinned, created_at))
            synced_count += 1

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": f"{synced_count} notes synced"})

# ---------------- User Registration ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for existing username
        existing_user = cursor.execute('SELECT * FROM Users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            conn.close()
            flash("Username already exists. Please choose a different username.", "error")
            return render_template('register.html')

        # Check for existing email
        existing_email = cursor.execute('SELECT * FROM Users WHERE email = ?', (email,)).fetchone()
        if existing_email:
            conn.close()
            flash("Email already exists. Please use a different email.", "error")
            return render_template('register.html')

        try:
            cursor.execute('INSERT INTO Users (username, email, first_name, last_name, phone, password_hash) VALUES (?, ?, ?, ?, ?, ?)',
                          (username, email, first_name, last_name, phone, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}", "error")
        finally:
            conn.close()
    return render_template('register.html')

# ---------------- User Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['user_id'], user['username'], user['email'], user['first_name'], user['last_name'], user['phone'])
            login_user(user_obj)
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
    return render_template('login.html')

# ---------------- User Dashboard with Search ----------------
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    search_query = request.form.get("search", "")

    conn = get_db_connection()

    pinned_notes = conn.execute('''
        SELECT * FROM Notes
        WHERE user_id = ? AND isdraft = 0 AND ispinned = 1
          AND (title LIKE ? OR content LIKE ?)
        ORDER BY updated_at DESC
    ''', (current_user.id, f"%{search_query}%", f"%{search_query}%")).fetchall()

    notes = conn.execute('''
        SELECT * FROM Notes
        WHERE user_id = ? AND isdraft = 0 AND ispinned = 0
          AND (title LIKE ? OR content LIKE ?)
        ORDER BY updated_at DESC
    ''', (current_user.id, f"%{search_query}%", f"%{search_query}%")).fetchall()

    reminders = conn.execute('''
        SELECT r.id, r.message, r.reminder_time, r.is_active, n.title as note_title
        FROM Reminders r
        JOIN Notes n ON r.note_id = n.id
        WHERE n.user_id = ? AND r.is_active = 1
        ORDER BY r.reminder_time ASC
    ''', (current_user.id,)).fetchall()

    conn.close()

    pinned_notes = [dict(row) for row in pinned_notes]
    notes = [dict(row) for row in notes]
    reminders = [dict(row) for row in reminders]

    return render_template(
        'dashboard.html',
        notes=notes,
        pinned_notes=pinned_notes,
        reminders=reminders,
        search_query=search_query
    )

# ---------------- Download Notes ----------------
@app.route('/download_notes')
@login_required
def download_notes():
    conn = get_db_connection()
    notes = conn.execute(
        "SELECT title, content FROM Notes WHERE user_id = ? AND isdraft = 0 ORDER BY updated_at DESC",
        (current_user.id,)
    ).fetchall()
    conn.close()

    content = ""
    for note in notes:
        content += f"Title: {note['title']}\n"
        content += f"Content:\n{note['content']}\n"
        content += "-" * 50 + "\n\n"

    from flask import Response
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment;filename=notes.txt"}
    )

# ---------------- User Logout ----------------
@app.route('/logout')
@login_required
def logout():
    flash(f"Goodbye, {current_user.username}! You have been logged out.", "success")
    logout_user()
    return redirect(url_for('index'))

# ---------------- Edit Note ----------------
@app.route('/edit_note/<int:note_id>', methods=['GET'])
@login_required
def edit_note(note_id):
    conn = get_db_connection()
    note = conn.execute(
        'SELECT * FROM Notes WHERE id = ? AND user_id = ?',
        (note_id, current_user.id)
    ).fetchone()
    conn.close()

    if not note:
        flash("Note not found.", "error")
        return redirect(url_for('dashboard'))

    return render_template('edit_note.html', note=note)

# ---------------- Create Note ----------------
@app.route('/create_note', methods=['GET'])
@login_required
def create_note():
    conn = get_db_connection()
    draft_note = conn.execute('''
        SELECT * FROM Notes 
        WHERE user_id = ? AND isdraft = 1 
        ORDER BY updated_at DESC LIMIT 1
    ''', (current_user.id,)).fetchone()
    conn.close()

    return render_template('create_note.html', draft_note=draft_note)

# ---------------- Auto-save Note API ----------------
@app.route('/autosave_note', methods=['POST'])
@login_required
def autosave_note():
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    categoryname = data.get('categoryname', 'Miscellaneous')
    ispinned = 1 if data.get('ispinned') else 0
    isdraft = 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    existing_draft = cursor.execute('''
        SELECT id FROM Notes 
        WHERE user_id = ? AND isdraft = 1 
        ORDER BY updated_at DESC LIMIT 1
    ''', (current_user.id,)).fetchone()

    if existing_draft:
        note_id = existing_draft['id']
        cursor.execute('''
            UPDATE Notes
            SET title = ?, content = ?, categoryname = ?, ispinned = ?, isdraft = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
        ''', (title, content, categoryname, ispinned, isdraft, now, note_id, current_user.id))
    else:
        cursor.execute('''
            INSERT INTO Notes (user_id, title, content, categoryname, ispinned, isdraft, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (current_user.id, title, content, categoryname, ispinned, isdraft, now, now))
        note_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'note_id': note_id})

# ---------------- Finalize Note ----------------
@app.route('/finalize_note', methods=['POST'])
@login_required
def finalize_note():
    note_id = request.form.get('note_id')
    if not note_id:
        flash("No draft note found to finalize.", "error")
        return redirect(url_for('create_note'))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute('''
        UPDATE Notes
        SET isdraft = 0, updated_at = ?
        WHERE id = ? AND user_id = ?
    ''', (now, note_id, current_user.id))
    conn.commit()
    conn.close()

    flash("Note finalized successfully!", "success")
    return redirect(url_for('dashboard'))

# ---------------- Delete Note ----------------
@app.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM Notes WHERE id = ? AND user_id = ?', (note_id, current_user.id))
    conn.commit()
    conn.close()

    flash("Note deleted successfully!", "success")
    return redirect(url_for('dashboard'))

# ---------------- Add / Edit Reminder ----------------
@app.route('/add_reminder', methods=['GET', 'POST'])
@app.route('/add_reminder/<int:reminder_id>', methods=['GET', 'POST'])
@login_required
def add_reminder(reminder_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    reminder = None
    if reminder_id:
        reminder = cursor.execute('''
            SELECT r.*, n.title AS note_title 
            FROM Reminders r 
            JOIN Notes n ON r.note_id = n.id
            WHERE r.id = ? 
              AND n.user_id = ?
        ''', (reminder_id, current_user.id)).fetchone()

        if not reminder:
            conn.close()
            flash("Reminder not found.", "error")
            return redirect(url_for('view_reminders'))

    if request.method == 'POST':
        note_id = request.form.get('note_id')
        message = request.form.get('message')
        reminder_time = request.form.get('reminder_time')
        is_active = 1 if request.form.get('is_active') else 0

        if reminder_id:
            cursor.execute('''
                UPDATE Reminders
                SET note_id = ?, message = ?, reminder_time = ?, is_active = ?
                WHERE id = ?
            ''', (note_id, message, reminder_time, is_active, reminder_id))
            flash("Reminder updated successfully!", "success")
        else:
            cursor.execute('''
                INSERT INTO Reminders (note_id, message, reminder_time, is_active)
                VALUES (?, ?, ?, ?)
            ''', (note_id, message, reminder_time, is_active))
            flash("Reminder added successfully!", "success")

        conn.commit()
        conn.close()
        return redirect(url_for('view_reminders'))

    notes = cursor.execute('''
        SELECT id, title FROM Notes WHERE user_id = ? AND isdraft = 0
    ''', (current_user.id,)).fetchall()
    conn.close()

    return render_template("add_reminder.html", reminder=reminder, notes=notes)

# ---------------- View Reminders ----------------
@app.route('/view_reminders', methods=['GET', 'POST'])
@login_required
def view_reminders():
    search_query = request.form.get("search", "")

    conn = get_db_connection()
    if search_query:
        reminders = conn.execute('''
            SELECT r.*, n.title AS note_title 
            FROM Reminders r
            JOIN Notes n ON r.note_id = n.id
            WHERE n.user_id = ? 
              AND (r.message LIKE ? OR n.title LIKE ?)
            ORDER BY r.reminder_time ASC
        ''', (current_user.id, f"%{search_query}%", f"%{search_query}%")).fetchall()
    else:
        reminders = conn.execute('''
            SELECT r.*, n.title AS note_title 
            FROM Reminders r
            JOIN Notes n ON r.note_id = n.id
            WHERE n.user_id = ?
            ORDER BY r.reminder_time ASC
        ''', (current_user.id,)).fetchall()
    conn.close()

    return render_template("view_reminder.html", reminders=reminders, search_query=search_query)

# ---------------- Delete Reminder ----------------
@app.route('/delete_reminder/<int:reminder_id>', methods=['POST'])
@login_required
def delete_reminder(reminder_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM Reminders 
        WHERE id = ? 
          AND note_id IN (SELECT id FROM Notes WHERE user_id = ?)
    ''', (reminder_id, current_user.id))
    conn.commit()
    conn.close()

    flash("Reminder deleted successfully!", "success")
    return redirect(url_for('view_reminders'))

# ---------------- Run ----------------
if __name__ == '__main__':
    app.run(debug=True)