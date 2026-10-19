# Boggle Backend

A Django REST API for generating and solving Boggle games, managing player
sessions, and saving leaderboard results. This repository covers the backend
assignment.
## Requirements

- Python 3.11 or newer
- pip

## Setup

Run these commands from the repository root:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/`. SQLite is used by default;
the local `db.sqlite3` file is ignored by Git.

## Authentication

Register to receive a token:

```http
POST /api/auth/register/
Content-Type: application/json

{"username": "alice", "email": "alice@example.com", "password": "a-strong-password"}
```

Log in with an existing account:

```http
POST /api/auth/token/
Content-Type: application/json

{"username": "alice", "password": "a-strong-password"}
```

Include the returned token on protected requests:

```http
Authorization: Token <token>
```

Log out and revoke the token with `POST /api/auth/logout/`. Reads are public;
creating or changing games, joining sessions, submitting leaderboard entries,
and delete operations require authentication.

## API endpoints

All paths below are relative to `/api`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/dictionaries/` | List supported dictionaries |
| `POST` | `/game/<size>/` | Create a random game (size 3–10); accepts optional `name` and `dictionary` |
| `GET` | `/game/<size>/` | Legacy game-creation route, retained for compatibility |
| `GET` | `/games/` | List games, newest first |
| `GET` | `/games/<game-id>/` | Retrieve a game |
| `PATCH` | `/games/<game-id>/` | Rename a game with `{"name": "New name"}` |
| `DELETE` | `/games/<game-id>/delete/` | Delete a game and its related records |
| `GET` | `/games/<game-id>/words/` | List valid words and points (administrators only) |
| `POST` | `/games/<game-id>/join/` | Join a game and create or resume an active player session |
| `POST` | `/sessions/<player-id>/start/` | Start a session timer |
| `POST` | `/sessions/<player-id>/words/` | Submit a solution word with `{"word": "WORD"}` |
| `POST` | `/sessions/<player-id>/finish/` | Finish a session and save its result to the leaderboard |
| `GET` | `/games/<game-id>/leaderboard/` | Retrieve a game's leaderboard |
| `POST` | `/games/<game-id>/leaderboard/` | Add a leaderboard entry |
| `GET` | `/leaderboard/<entry-id>/` | Retrieve a leaderboard entry |
| `DELETE` | `/leaderboard/<entry-id>/delete/` | Delete a leaderboard entry |

Session word submissions are checked against the game's precomputed solution
set; duplicate submissions are rejected. Session scoring follows the existing
leaderboard rule of one point per valid word. Finishing a session records its
elapsed time, found-word count, score, and player on the game's leaderboard.
Players can start another session for a game after completing their current
one.

Game API responses do not include the precomputed solution words. Players can
see the number of words remaining in their session response; leaderboard
entries include both words found and words not found. The complete solution
list is restricted to administrators.

## Dictionaries

English is the default. Select French when creating a game with
`?dictionary=French` or `?language=fr`. Dictionary names and codes are
case-insensitive. The French word list is normalized to ASCII so its words can
be matched against the game's letter tiles. Its attribution and license are
documented in
[`boggle_backend/static/data/FRENCH-WORDLIST-LICENSE.txt`](boggle_backend/static/data/FRENCH-WORDLIST-LICENSE.txt).

## Tests and checks

Run the API tests and Django configuration checks from the repository root:

```powershell
python manage.py test api.tests
python manage.py check
python manage.py makemigrations --check --dry-run
```

The tests cover authentication, game CRUD, dictionary selection, multiplayer
sessions, word validation, and leaderboard recording.

## Development and deployment note

The checked-in Django settings are for local development and are not
production-ready. Before deploying, configure a private `SECRET_KEY`, disable
debug mode, and set appropriate allowed hosts, HTTPS, CSRF, and CORS settings.
