from flask import Flask, render_template, request, redirect, url_for, session, flash , jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"

DATABASE = "notes_manager.db"

# ---------------- Database Connection ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- Home Page ----------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sync_guest_notes', methods=['POST'])
def sync_guest_notes():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "User not logged in"}), 401

    user_id = session['user_id']
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

        # Check for duplicates (same title, content, and category)
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
        try:
            conn.execute('INSERT INTO Users (username, email, first_name, last_name, phone, password_hash) VALUES (?, ?, ?, ?, ?, ?)',
                         (username, email, first_name, last_name, phone, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "error")
        finally:
            conn.close()
    return render_template('register.html')

# ---------------- User Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM Users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
    return render_template('login.html')

# ---------------- User Dashboard with Search ----------------
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('user_id'):
        flash("Please login to access the dashboard.", "error")
        return redirect(url_for('login'))

    search_query = request.form.get("search", "")

    conn = get_db_connection()

    # Pinned notes
    pinned_notes = conn.execute('''
        SELECT * FROM Notes
        WHERE user_id = ? AND isdraft = 0 AND ispinned = 1
          AND (title LIKE ? OR content LIKE ?)
        ORDER BY updated_at DESC
    ''', (session['user_id'], f"%{search_query}%", f"%{search_query}%")).fetchall()

    # Non-pinned notes
    notes = conn.execute('''
        SELECT * FROM Notes
        WHERE user_id = ? AND isdraft = 0 AND ispinned = 0
          AND (title LIKE ? OR content LIKE ?)
        ORDER BY updated_at DESC
    ''', (session['user_id'], f"%{search_query}%", f"%{search_query}%")).fetchall()

    # Reminders (only active ones)
    reminders = conn.execute('''
        SELECT r.id, r.message, r.reminder_time, r.is_active, n.title as note_title
        FROM Reminders r
        JOIN Notes n ON r.note_id = n.id
        WHERE n.user_id = ? AND r.is_active = 1
        ORDER BY r.reminder_time ASC
    ''', (session['user_id'],)).fetchall()

    conn.close()

    # Convert sqlite3.Row → dict
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
def download_notes():
    if not session.get('user_id'):
        flash("Please login to download notes.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    notes = conn.execute(
        "SELECT title, content FROM Notes WHERE user_id = ? AND isdraft = 0 ORDER BY updated_at DESC",
        (session['user_id'],)
    ).fetchall()
    conn.close()

    # Create .txt file content
    content = ""
    for note in notes:
        content += f"Title: {note['title']}\n"
        content += f"Content:\n{note['content']}\n"
        content += "-" * 50 + "\n\n"

    # Send file as download
    from flask import Response
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment;filename=notes.txt"}
    )

# ---------------- User Logout ----------------
@app.route('/logout')
def logout():
    if session.get('username'):
        flash(f"Goodbye, {session.get('username')}! You have been logged out.", "success")
    session.clear()
    return redirect(url_for('index'))

# ---------------- Edit Note ----------------
@app.route('/edit_note/<int:note_id>', methods=['GET'])
def edit_note(note_id):
    if not session.get('user_id'):
        flash("Please login to edit notes.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    note = conn.execute(
        'SELECT * FROM Notes WHERE id = ? AND user_id = ?',
        (note_id, session['user_id'])
    ).fetchone()
    conn.close()

    if not note:
        flash("Note not found.", "error")
        return redirect(url_for('dashboard'))

    return render_template('edit_note.html', note=note)

# ---------------- Create Note ----------------
@app.route('/create_note', methods=['GET'])
def create_note():
    if not session.get('user_id'):
        flash("Please login to create notes.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    draft_note = conn.execute('''
        SELECT * FROM Notes 
        WHERE user_id = ? AND isdraft = 1 
        ORDER BY updated_at DESC LIMIT 1
    ''', (session['user_id'],)).fetchone()
    conn.close()

    return render_template('create_note.html', draft_note=draft_note)

# ---------------- Auto-save Note API ----------------
@app.route('/autosave_note', methods=['POST'])
def autosave_note():
    if not session.get('user_id'):
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 403

    data = request.get_json()
    title = data.get('title', '').strip()  # no Untitled default
    content = data.get('content', '').strip()
    categoryname = data.get('categoryname', 'Miscellaneous')
    ispinned = 1 if data.get('ispinned') else 0
    isdraft = 1  # autosave always stores as draft
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for existing draft note
    existing_draft = cursor.execute('''
        SELECT id FROM Notes 
        WHERE user_id = ? AND isdraft = 1 
        ORDER BY updated_at DESC LIMIT 1
    ''', (session['user_id'],)).fetchone()

    if existing_draft:  # update existing draft
        note_id = existing_draft['id']
        cursor.execute('''
            UPDATE Notes
            SET title = ?, content = ?, categoryname = ?, ispinned = ?, isdraft = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
        ''', (title, content, categoryname, ispinned, isdraft, now, note_id, session['user_id']))
    else:  # insert new draft
        cursor.execute('''
            INSERT INTO Notes (user_id, title, content, categoryname, ispinned, isdraft, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, content, categoryname, ispinned, isdraft, now, now))
        note_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'note_id': note_id})

# ---------------- Finalize Note ----------------
@app.route('/finalize_note', methods=['POST'])
def finalize_note():
    if not session.get('user_id'):
        flash("Please login to finalize notes.", "error")
        return redirect(url_for('login'))

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
    ''', (now, note_id, session['user_id']))
    conn.commit()
    conn.close()

    flash("Note finalized successfully!", "success")
    return redirect(url_for('dashboard'))

# ---------------- Delete Note ----------------
@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    if not session.get('user_id'):
        flash("Please login to delete notes.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM Notes WHERE id = ? AND user_id = ?', (note_id, session['user_id']))
    conn.commit()
    conn.close()

    flash("Note deleted successfully!", "success")
    return redirect(url_for('dashboard'))

# ---------------- Add / Edit Reminder ----------------
@app.route('/add_reminder', methods=['GET', 'POST'])
@app.route('/add_reminder/<int:reminder_id>', methods=['GET', 'POST'])
def add_reminder(reminder_id=None):
    if not session.get('user_id'):
        flash("Please login to manage reminders.", "error")
        return redirect(url_for('login'))

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
        ''', (reminder_id, session['user_id'])).fetchone()

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

    # Fetch all notes (only finalized notes)
    notes = cursor.execute('''
        SELECT id, title FROM Notes WHERE user_id = ? AND isdraft = 0
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template("add_reminder.html", reminder=reminder, notes=notes)



# ---------------- View Reminders ----------------
@app.route('/view_reminders', methods=['GET', 'POST'])
def view_reminders():
    if not session.get('user_id'):
        flash("Please login to view reminders.", "error")
        return redirect(url_for('login'))

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
        ''', (session['user_id'], f"%{search_query}%", f"%{search_query}%")).fetchall()
    else:
        reminders = conn.execute('''
            SELECT r.*, n.title AS note_title 
            FROM Reminders r
            JOIN Notes n ON r.note_id = n.id
            WHERE n.user_id = ?
            ORDER BY r.reminder_time ASC
        ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template("view_reminder.html", reminders=reminders, search_query=search_query)


# ---------------- Delete Reminder ----------------
@app.route('/delete_reminder/<int:reminder_id>', methods=['POST'])
def delete_reminder(reminder_id):
    if not session.get('user_id'):
        flash("Please login to delete reminders.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM Reminders 
        WHERE id = ? 
          AND note_id IN (SELECT id FROM Notes WHERE user_id = ?)
    ''', (reminder_id, session['user_id']))
    conn.commit()
    conn.close()

    flash("Reminder deleted successfully!", "success")
    return redirect(url_for('view_reminders'))


# ---------------- Run ----------------
if __name__ == '__main__':
    app.run(debug=True)
