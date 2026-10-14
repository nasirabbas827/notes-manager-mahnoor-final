# Notes Manager Mahnoor Final

notes-manager-mahnoor-final is a notes application with editing, downloads, and reminders.

![Flask](https://img.shields.io/badge/Flask-2563EB?style=flat-square) ![SQLite](https://img.shields.io/badge/SQLite-0F172A?style=flat-square)

## Overview

The Flask implementation is organized around the entry points and modules below.

## Implemented workflows

The source defines these handlers:

- **Index** — `index`
- **Sync Guest Notes** — `sync_guest_notes`
- **Register** — `register`
- **Login** — `login`
- **Dashboard** — `dashboard`
- **Download Notes** — `download_notes`
- **Logout** — `logout`
- **Edit Note** — `edit_note`
- **Create Note** — `create_note`
- **Autosave Note** — `autosave_note`
- **Finalize Note** — `finalize_note`
- **Delete Note** — `delete_note`

## Getting started

### 1. Get the project

```bash
git clone https://github.com/nasirabbas827/notes-manager-mahnoor-final.git
cd notes-manager-mahnoor-final
```

### 2. Prepare Python

Create an isolated environment:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\activate` on Windows Command Prompt, or `source .venv/bin/activate` on macOS/Linux.

No requirements file is included. The inspected Python imports indicate these dependencies as a starting point:

```bash
python -m pip install Flask Flask-Login Werkzeug
```

Dependency versions are not pinned in this repository.

### 3. Configure and run

Keep the included SQLite database files in their expected locations: [`notes_manager.db`](notes_manager.db).

Run from the repository root so relative file paths resolve correctly:

```bash
python app.py
```

Open http://127.0.0.1:5000/, or use the address printed by the application.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`app.py`](app.py) | Application entry point |
| [`templates`](templates) | HTML page templates |

## Development notes

These setup instructions are based on the repository source. The application has not been executed as part of this documentation update; verify dependencies and configuration in your local environment.
