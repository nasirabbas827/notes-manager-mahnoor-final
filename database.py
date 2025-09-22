import sqlite3

# Create a new SQLite3 database (or connect if it exists)
conn = sqlite3.connect('notes_manager.db')
cursor = conn.cursor()

# Enable foreign key constraint enforcement
cursor.execute("PRAGMA foreign_keys = ON;")

# Create Users Table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT NOT NULL
);
''')

# Create Notes Table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    categoryname TEXT CHECK(categoryname IN ('Work', 'Personal', 'Study', 'Miscellaneous')),
    ispinned BOOLEAN DEFAULT 0,
    isdraft BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);
''')

# Create Reminders Table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    message TEXT,
    reminder_time DATETIME NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES Notes(id) ON DELETE CASCADE
);
''')

# Commit changes and close the connection
conn.commit()
conn.close()

print("Database and tables created successfully!")
