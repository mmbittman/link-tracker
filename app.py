# app.py
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, g, render_template_string, abort

DATABASE = os.path.join(os.path.dirname(__file__), 'clicks.db')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'changeme')  # change this in env for security

app = Flask(__name__)

# ---- Database helpers ----
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS links (
      slug TEXT PRIMARY KEY,
      target_url TEXT NOT NULL,
      description TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS clicks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      ip TEXT,
      user_agent TEXT,
      referrer TEXT,
      slug TEXT,
      campaign TEXT
    )
    ''')
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ---- Helper: create or update a slug mapping ----
def upsert_link(slug, target_url, description=None):
    db = get_db()
    cur = db.cursor()
    cur.execute('''
      INSERT INTO links (slug, target_url, description) VALUES (?, ?, ?)
      ON CONFLICT(slug) DO UPDATE SET target_url=excluded.target_url, description=excluded.description
    ''', (slug, target_url, description))
    db.commit()

# ---- Public redirect route ----
@app.route('/<slug>')
def track_and_redirect(slug):
    db = get_db()
    # find mapping
    cur = db.execute('SELECT target_url FROM links WHERE slug = ?', (slug,))
    row = cur.fetchone()
    if not row:
        return "Link not found", 404
    target = row['target_url']

    # collect info
    ts = datetime.utcnow().isoformat()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    ua = request.headers.get('User-Agent')
    ref = request.referrer
    campaign = request.args.get('campaign')

    # store click
    db.execute('INSERT INTO clicks (timestamp, ip, user_agent, referrer, slug, campaign) VALUES (?, ?, ?, ?, ?, ?)',
               (ts, ip, ua, ref, slug, campaign))
    db.commit()

    # redirect
    return redirect(target, code=302)

# ---- Simple admin dashboard ----
ADMIN_TEMPLATE = """
<!doctype html>
<title>Click Tracker Admin</title>
<h1>Click stats</h1>
<p>Totals per slug (last 1000 clicks considered):</p>
<table border="1" cellpadding="6">
<tr><th>slug</th><th>target_url</th><th>clicks</th></tr>
{% for row in totals %}
<tr>
  <td>{{ row.slug }}</td>
  <td>{{ row.target_url }}</td>
  <td>{{ row.count }}</td>
</tr>
{% endfor %}
</table>

<h2>Recent clicks</h2>
<table border="1" cellpadding="6">
<tr><th>time (UTC)</th><th>slug</th><th>ip</th><th>ua</th><th>referrer</th><th>campaign</th></tr>
{% for c in recent %}
<tr>
  <td>{{ c.timestamp }}</td>
  <td>{{ c.slug }}</td>
  <td>{{ c.ip }}</td>
  <td style="max-width:300px;word-wrap:break-word">{{ c.user_agent }}</td>
  <td>{{ c.referrer }}</td>
  <td>{{ c.campaign }}</td>
</tr>
{% endfor %}
</table>
"""

@app.route('/admin')
def admin():
    token = request.args.get('token')
    if token != ADMIN_TOKEN:
        abort(401)

    db = get_db()
    # totals
    totals = db.execute('''
      SELECT l.slug, l.target_url, COUNT(c.id) AS count
      FROM links l LEFT JOIN clicks c ON l.slug = c.slug
      GROUP BY l.slug
      ORDER BY count DESC
    ''').fetchall()

    recent = db.execute('SELECT timestamp, slug, ip, user_agent, referrer, campaign FROM clicks ORDER BY id DESC LIMIT 100').fetchall()
    return render_template_string(ADMIN_TEMPLATE, totals=totals, recent=recent)

# ---- simple CLI helper route (optional) to add links via HTTP POST for quick setup ----
@app.route('/admin/add', methods=['POST'])
def admin_add():
    token = request.args.get('token')
    if token != ADMIN_TOKEN:
        abort(401)
    slug = request.form.get('slug')
    target = request.form.get('target_url')
    desc = request.form.get('description')
    if not slug or not target:
        return "slug and target_url required", 400
    upsert_link(slug, target, desc)
    return f"Added/updated {slug} -> {target}\n"

@app.route('/')
def index():
    return "✅ Flask Click Tracker is running! Try visiting /admin or /<slug>"

# ---- On start, ensure DB exists ----
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
else:
    # When running on Render or another WSGI host, initialize the DB once
    with app.app_context():
        init_db()



