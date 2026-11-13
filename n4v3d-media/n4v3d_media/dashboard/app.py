"""N4V3D MEDIA CONTROL CENTER — secure, responsive web dashboard (stdlib http.server + Jinja2).

Security model:
  * binds to 127.0.0.1 by default (put a TLS reverse proxy in front for remote access)
  * password stored only as PBKDF2-SHA256 (600k iterations) in var/auth.json
    — set it with:  python -m n4v3d_media.dashboard.app --set-password
  * HMAC-signed, expiring session cookie (HttpOnly, SameSite=Strict; Secure when N4V3D_HTTPS=1)
  * CSRF token on every state-changing POST; login rate-limited per IP
  * file serving restricted to releases/ (no path traversal); API credentials never rendered
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import html
import json
import os
import secrets
import shutil
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jinja2 import DictLoader, Environment, select_autoescape

from .. import PRODUCTIONS, RELEASES, ROOT, VAR, __version__
from ..orchestrator import db

AUTH = VAR / "auth.json"
SECRET = VAR / "secret.key"
SESSION_TTL = 12 * 3600
_fails: dict = {}


# --------------------------------------------------------------------------- auth helpers
def hash_password(pw: str, salt: bytes | None = None, it: int = 600_000) -> dict:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, it)
    return {"alg": "pbkdf2_sha256", "it": it, "salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(dk).decode()}


def check_password(pw: str) -> bool:
    if not AUTH.exists():
        return False
    a = json.loads(AUTH.read_text())
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(a["salt"]), a["it"])
    return hmac.compare_digest(base64.b64encode(dk).decode(), a["hash"])


def set_password(pw: str):
    VAR.mkdir(parents=True, exist_ok=True)
    AUTH.write_text(json.dumps(hash_password(pw)))
    os.chmod(AUTH, 0o600)


def _secret() -> bytes:
    if not SECRET.exists():
        VAR.mkdir(parents=True, exist_ok=True)
        SECRET.write_bytes(secrets.token_bytes(32))
        os.chmod(SECRET, 0o600)
    return SECRET.read_bytes()


def make_session(user="owner") -> str:
    payload = f"{user}|{int(time.time()) + SESSION_TTL}|{secrets.token_hex(8)}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def read_session(tok: str | None):
    if not tok:
        return None
    try:
        user, exp, nonce, sig = base64.urlsafe_b64decode(tok.encode()).decode().split("|")
    except Exception:
        return None
    good = hmac.new(_secret(), f"{user}|{exp}|{nonce}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or int(exp) < time.time():
        return None
    return {"user": user, "csrf": hmac.new(_secret(), f"csrf|{nonce}".encode(), hashlib.sha256).hexdigest()[:32]}


# --------------------------------------------------------------------------- data
def releases():
    out = []
    for d in sorted(RELEASES.glob("*")) if RELEASES.exists() else []:
        if not d.is_dir():
            continue
        r = {"dir": d.name}
        for f, k in (("production_report.json", "report"), ("scorecard.json", "card"), ("qc_report.json", "qc"),
                     ("youtube_metadata_DRAFT.json", "meta")):
            p = d / f
            r[k] = json.loads(p.read_text()) if p.exists() else None
        r["video"] = next((v.name for v in d.glob("N4V3D_*.mp4")), None)
        out.append(r)
    return out


def productions():
    out = []
    for d in sorted(PRODUCTIONS.glob("*/production.json")):
        p = json.loads(d.read_text())
        p["_path"] = str(d.parent.relative_to(ROOT))
        out.append(p)
    return out


def health():
    con = db.connect()
    hb = db.get_setting(con, "worker_heartbeat")
    age = None
    if hb:
        import datetime as dt
        age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(hb)).total_seconds()
    from n4v3d import voice as V
    du = shutil.disk_usage(ROOT)
    return {
        "version": __version__, "database": "ok", "emergency_stop": db.emergency_stopped(con),
        "worker_heartbeat_age_s": round(age) if age is not None else None,
        "worker_alive": age is not None and age < 300,
        "ffmpeg": bool(shutil.which("ffmpeg")), "neural_voice": V.kokoro_available(),
        "disk_free_gb": round(du.free / 1e9, 1),
        "youtube_connected": (VAR / "youtube_credentials.json").exists(),
        "invideo_connected": False,
    }


# --------------------------------------------------------------------------- templates
CSS = """
:root{--bg:#0b1020;--panel:#131a2e;--line:#243052;--ink:#e8ecf6;--mute:#93a0bf;--acc:#5ce1e6;--warn:#ffb648;--bad:#ff6b6b;--ok:#4ade80}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 Inter,system-ui,sans-serif;background:var(--bg);color:var(--ink)}
a{color:var(--acc);text-decoration:none}header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--line);background:#0e1427;position:sticky;top:0;z-index:5}
.brand{font-weight:900;letter-spacing:.04em}.brand span{color:var(--acc)}nav{display:flex;flex-wrap:wrap;gap:4px}
nav a{padding:6px 10px;border-radius:8px;color:var(--mute);font-weight:600;font-size:14px}nav a.on,nav a:hover{background:var(--panel);color:var(--ink)}
main{padding:20px;max-width:1280px;margin:0 auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}.big{font-size:30px;font-weight:900}
h1{font-size:22px;margin:0 0 14px}h2{font-size:17px;margin:18px 0 10px}.mute{color:var(--mute)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600}.wrap{overflow-x:auto}
.tag{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;font-weight:700;background:#24304f}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}.tag.ok{background:#173a2a}.tag.bad{background:#46202a}.tag.warn{background:#463614}
button,.btn{background:var(--acc);color:#04131a;border:0;border-radius:9px;padding:8px 14px;font-weight:800;cursor:pointer}
button.danger{background:var(--bad);color:#fff}button.ghost{background:#24304f;color:var(--ink)}
input,select,textarea{background:#0d1426;border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:8px;font:inherit;width:100%}
form.inline{display:inline}.stop{background:#46202a;border:1px solid var(--bad);padding:12px 16px;border-radius:12px;margin-bottom:14px;font-weight:700}
video{width:100%;max-width:340px;border-radius:12px;background:#000}img.sb{width:100%;border-radius:10px}
.stages{display:flex;flex-wrap:wrap;gap:3px}.st{font-size:10px;padding:2px 5px;border-radius:5px;background:#1b2440;color:var(--mute)}.st.done{background:#173a2a;color:var(--ok)}.st.cur{background:var(--acc);color:#04131a;font-weight:800}
pre{white-space:pre-wrap;background:#0d1426;padding:10px;border-radius:8px;font-size:12px}
@media (max-width:640px){main{padding:12px}.big{font-size:24px}nav a{padding:5px 7px;font-size:13px}th,td{padding:6px;font-size:13px}.hide-sm{display:none}}
"""

T = {
"base": """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>N4V3D Control Center</title><style>{{ css }}</style></head><body>
<header><div class="brand">N4V3D <span>MEDIA</span> · CONTROL CENTER</div>
{% if user %}<nav>{% for k,v in nav %}<a href="{{k}}" class="{{ 'on' if k==path else '' }}">{{v}}</a>{% endfor %}
<form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="{{csrf}}"><button class="ghost">Log out</button></form></nav>{% endif %}</header>
<main>{% if user and stopped %}<div class="stop">⛔ EMERGENCY STOP ENGAGED — no production or publishing stages will run.
<form class="inline" method="post" action="/resume"><input type="hidden" name="csrf" value="{{csrf}}"><button class="ghost">Release stop</button></form></div>{% endif %}
{% block body %}{% endblock %}</main></body></html>""",
"login": """{% extends "base" %}{% block body %}<div class="card" style="max-width:380px;margin:60px auto">
<h1>Sign in</h1>{% if err %}<p class="bad">{{err}}</p>{% endif %}{% if not configured %}<p class="warn">No password set. Run:<br><code>python -m n4v3d_media.dashboard.app --set-password</code></p>{% endif %}
<form method="post" action="/login"><p><input type="password" name="password" placeholder="Password" autofocus></p><button>Sign in</button></form></div>{% endblock %}""",
"overview": """{% extends "base" %}{% block body %}<h1>Production overview</h1>
<div class="grid">
<div class="card"><div class="mute">Jobs in pipeline</div><div class="big">{{jobs|length}}</div><div class="mute">{{ counts }}</div></div>
<div class="card"><div class="mute">Completed videos</div><div class="big">{{rels|length}}</div></div>
<div class="card"><div class="mute">Awaiting human action</div><div class="big warn">{{ waiting|length }}</div></div>
<div class="card"><div class="mute">System</div><div class="big {{ 'ok' if h.worker_alive else 'warn' }}">{{ 'Worker live' if h.worker_alive else 'Worker idle' }}</div>
<div class="mute">voice: {{ 'neural' if h.neural_voice else 'placeholder' }} · disk {{h.disk_free_gb}} GB free</div></div></div>
<h2>Emergency control</h2><div class="card">{% if stopped %}<form method="post" action="/resume"><input type="hidden" name="csrf" value="{{csrf}}"><button class="ghost">Release emergency stop</button></form>
{% else %}<form method="post" action="/stop" onsubmit="return confirm('Stop all automated production and publishing?')"><input type="hidden" name="csrf" value="{{csrf}}"><button class="danger">⛔ EMERGENCY STOP</button></form>{% endif %}
<p class="mute">Halts every pipeline stage (incl. publishing) before it starts. Also triggered by <code>var/STOP</code> or <code>python -m n4v3d_media stop</code>.</p></div>
<h2>Needs your attention</h2><div class="card wrap"><table><tr><th>Job</th><th>Stage</th><th>Reason</th></tr>
{% for j in waiting %}<tr><td>#{{j.id}} {{j.title}}</td><td>{{j.stage}}</td><td>{{j.wait_reason or j.last_error}}</td></tr>{% else %}<tr><td colspan=3 class="mute">Nothing waiting.</td></tr>{% endfor %}</table></div>
<h2>Recent events</h2><div class="card wrap"><table>{% for e in events %}<tr><td class="mute hide-sm">{{e.ts[11:19]}}</td><td class="hide-sm">#{{e.job_id}}</td><td>{{e.stage}}</td><td><span class="tag {{ {'error':'bad','blocked':'bad','action':'warn','warn':'warn'}.get(e.level,'') }}">{{e.level}}</span></td><td>{{e.message.split('\n')[0]}}</td></tr>{% endfor %}</table></div>{% endblock %}""",
"pipeline": """{% extends "base" %}{% block body %}<h1>Pipeline & render queue</h1>
<div class="card"><form method="post" action="/enqueue" style="display:flex;gap:8px;flex-wrap:wrap"><input type="hidden" name="csrf" value="{{csrf}}">
<select name="path" style="flex:1;min-width:220px">{% for p in prods %}<option value="{{p._path}}">{{p.id}} — {{p.title}}</option>{% endfor %}</select><button>Add to pipeline</button></form>
<p class="mute">The background worker (<code>python -m n4v3d_media worker</code>, systemd/cron in <code>deploy/</code>) advances jobs automatically and stops at human gates.</p></div>
<h2>Jobs</h2><div class="card wrap"><table><tr><th>#</th><th>Production</th><th>Progress</th><th>Status</th><th>Actions</th></tr>
{% for j in jobs %}<tr><td>{{j.id}}</td><td>{{j.title or j.path}}<div class="mute">{{j.path}}</div></td>
<td><div class="stages">{% for s in stages %}<span class="st {{ 'cur' if s==j.stage else ('done' if loop.index0 < stages.index(j.stage) else '') }}">{{s.replace('_',' ')}}</span>{% endfor %}</div></td>
<td><span class="tag {{ {'done':'ok','failed':'bad','blocked':'bad','waiting':'warn'}.get(j.status,'') }}">{{j.status}}</span><div class="mute">{{ (j.wait_reason or j.last_error or '')[:160] }}</div></td>
<td>{% if j.stage=='APPROVAL' %}<form class="inline" method="post" action="/job/{{j.id}}/approve" onsubmit="return confirm('Record YOUR publish approval for this video?')"><input type="hidden" name="csrf" value="{{csrf}}"><button>Approve publish</button></form>{% endif %}
{% if j.status in ('failed','blocked') %}<form class="inline" method="post" action="/job/{{j.id}}/retry"><input type="hidden" name="csrf" value="{{csrf}}"><button class="ghost">Retry</button></form>{% endif %}
{% if j.approved_by %}<div class="ok">approved by {{j.approved_by}}</div>{% endif %}</td></tr>{% else %}<tr><td colspan=5 class="mute">No jobs yet.</td></tr>{% endfor %}</table></div>{% endblock %}""",
"scripts": """{% extends "base" %}{% block body %}<h1>Script library & topic research</h1>{% for p in prods %}<div class="card" style="margin-bottom:14px">
<h2 style="margin-top:0">{{p.id}} · {{p.title}} <span class="tag">{{p.brand}}</span> <span class="tag">{{p.format}} · {{p.target_duration}}s</span></h2>
<table>{% for s in p.segments %}<tr><td><span class="tag">{{s.stage}}</span></td><td>{{s.text}}</td><td class="mute">{{ s.claims|join(', ') }}</td></tr>{% endfor %}</table>
<p class="mute">Keywords: {{ p.seo.keywords|join(', ') }} — title candidates: {{ p.seo.titles|join(' · ') }}</p></div>{% endfor %}{% endblock %}""",
"facts": """{% extends "base" %}{% block body %}<h1>Fact verification</h1>{% for p in prods %}{% set g = gates[p.id] %}<div class="card" style="margin-bottom:14px">
<h2 style="margin-top:0">{{p.title}} — <span class="{{ 'ok' if g.render_ok else 'bad' }}">{{ 'facts verified' if g.render_ok else 'BLOCKED' }}</span>
{% if g.publish_blockers %}<span class="tag warn">{{ g.publish_blockers|join('; ') }}</span>{% endif %}</h2>
<p class="mute">Author: {{p.review.author}} · fact-checker: {{p.review.fact_checker}} · expert review: {{p.review.expert_review.status}}</p>
<div class="wrap"><table><tr><th>Claim</th><th>Status</th><th>Evidence</th><th>Sources</th></tr>{% for c in p.claims %}<tr><td><b>{{c.id}}</b> {{c.text}}</td>
<td><span class="tag {{ 'ok' if c.status=='verified' else 'warn' }}">{{c.status}}{{ ' · hedged' if c.hedged }}</span></td><td class="mute">“{{c.evidence}}”</td><td>{% for s in c.sources %}{{s}} {% endfor %}</td></tr>{% endfor %}</table></div>
<p class="mute">{% for s in p.sources %}[{{s.id}}] <a href="{{s.url}}" rel="noopener noreferrer" target="_blank">{{s.title}}</a> — {{s.publisher}}<br>{% endfor %}</p></div>{% endfor %}{% endblock %}""",
"storyboards": """{% extends "base" %}{% block body %}<h1>Storyboards</h1>{% for r in rels %}<div class="card" style="margin-bottom:14px"><h2 style="margin-top:0">{{r.dir}}</h2>
{% if r.has_sb %}<img class="sb" src="/files/{{r.dir}}/storyboard.jpg" alt="storyboard">{% else %}<p class="mute">No storyboard.</p>{% endif %}</div>{% endfor %}{% endblock %}""",
"videos": """{% extends "base" %}{% block body %}<h1>Completed videos</h1><div class="grid">{% for r in rels %}{% if r.video %}<div class="card">
<video controls preload="metadata" src="/files/{{r.dir}}/{{r.video}}"></video><h2>{{ r.report.title if r.report else r.dir }}</h2>
<div class="mute">{{ r.report.duration if r.report }}s · QC {% if r.qc %}<span class="{{ 'ok' if r.qc.passed else 'bad' }}">{{ 'pass' if r.qc.passed else 'fail' }}</span>{% endif %}
{% if r.card %} · score {{r.card.total}}/100{% endif %}</div><p><a href="/files/{{r.dir}}/{{r.video}}" download>Download MP4</a></p></div>{% endif %}{% endfor %}</div>{% endblock %}""",
"quality": """{% extends "base" %}{% block body %}<h1>Quality reports</h1>{% for r in rels %}{% if r.card %}<div class="card" style="margin-bottom:14px">
<h2 style="margin-top:0">{{r.card.title}} — {{r.card.total}}/100 <span class="tag {{ 'ok' if r.card.status=='release_candidate' else 'warn' }}">{{r.card.status}}</span></h2>
<div class="wrap"><table><tr><th>Category</th><th>Score</th><th class="hide-sm">Basis</th><th>Reason</th></tr>{% for k,c in r.card.categories.items() %}<tr><td>{{k.replace('_',' ')}}</td><td>{{c.score}}/{{c.max}}</td><td class="mute hide-sm">{{c.basis}}</td><td>{{c.reason}}</td></tr>{% endfor %}</table></div>
<p><b>Blockers:</b> {{ r.card.blockers|join(' · ') or 'none' }}</p>{% if r.card.revision_plan %}<p><b>Revision plan:</b></p><ul>{% for x in r.card.revision_plan %}<li>{{x.category}} (+{{x.points_available}}): {{x.action}}</li>{% endfor %}</ul>{% endif %}
<p class="mute">Technical QC: {% for c in r.qc.checks if not c.passed %}<span class="bad">{{c.check}}</span> {% else %}all {{ r.qc.checks|length }} checks passed{% endfor %} · {{r.qc.lufs}} LUFS</p></div>{% endif %}{% endfor %}{% endblock %}""",
"publishing": """{% extends "base" %}{% block body %}<h1>YouTube publishing</h1>
<div class="card"><b>Channel connection:</b> {% if h.youtube_connected %}<span class="ok">credentials present</span>{% else %}<span class="warn">not connected</span> — see docs/YOUTUBE.md (owner authorisation required).{% endif %}
<p class="mute">Nothing is ever uploaded without (1) your approval on the Pipeline page, (2) all fact/expert/QC gates passing and (3) the emergency stop being off. Uploads default to <b>private</b>.</p></div>
{% for r in rels %}{% if r.meta %}<div class="card" style="margin-top:14px"><h2 style="margin-top:0">{{r.meta.title}}</h2>
<p class="mute">Approved: <b class="{{ 'ok' if r.meta.approved else 'warn' }}">{{ r.meta.approved }}</b> · made for kids: {{ r.meta.made_for_kids }}</p>
<p><b>Title candidates</b></p><ol>{% for t in r.meta.title_candidates %}<li>{{t.title}} <span class="mute">({{t.total}}/40{{ ', clickbait!' if t.clickbait }})</span></li>{% endfor %}</ol>
<pre>{{r.meta.description}}</pre><p class="mute">{{ r.meta.hashtags|join(' ') }}</p></div>{% endif %}{% endfor %}{% endblock %}""",
"analytics": """{% extends "base" %}{% block body %}<h1>Analytics & retention</h1><div class="card">
<p><span class="warn">No analytics connected.</span> Metrics (first-seconds retention, average % viewed, drop-off, rewatches, CTR, subscriber conversion)
appear here after you authorise YouTube Analytics (yt-analytics.readonly). <b>No numbers are estimated or fabricated.</b></p>
<p class="mute">Once connected, the IMPROVEMENT stage compares drop-off timestamps with the scene timeline in each production report to flag weak hooks, slow scenes and unclear visuals.</p></div>{% endblock %}""",
"finance": """{% extends "base" %}{% block body %}<h1>Revenue & expenses</h1><div class="grid">
<div class="card"><div class="mute">Revenue</div><div class="big ok">{{ '%.2f'|format(rev) }}</div></div><div class="card"><div class="mute">Expenses</div><div class="big bad">{{ '%.2f'|format(exp) }}</div></div>
<div class="card"><div class="mute">Net</div><div class="big">{{ '%.2f'|format(rev-exp) }}</div><div class="mute">manual ledger · actuals only, no projections</div></div></div>
<h2>Add entry</h2><div class="card"><form method="post" action="/finance" class="grid"><input type="hidden" name="csrf" value="{{csrf}}">
<input type="date" name="date" required><select name="kind"><option>expense</option><option>revenue</option></select><input name="amount" type="number" step="0.01" placeholder="Amount" required>
<input name="currency" value="USD"><input name="description" placeholder="Description" required><button>Add</button></form></div>
<h2>Ledger</h2><div class="card wrap"><table><tr><th>Date</th><th>Kind</th><th>Amount</th><th>Description</th></tr>{% for e in rows %}<tr><td>{{e.date}}</td><td>{{e.kind}}</td><td>{{e.amount}} {{e.currency}}</td><td>{{e.description}}</td></tr>{% else %}<tr><td colspan=4 class="mute">No entries. Current running cost of the local pipeline: $0 (no paid APIs active).</td></tr>{% endfor %}</table></div>{% endblock %}""",
"health": """{% extends "base" %}{% block body %}<h1>System health</h1><div class="card wrap"><table>{% for k,v in h.items() %}<tr><td>{{k.replace('_',' ')}}</td><td class="{{ 'ok' if v is sameas true else ('bad' if v is sameas false and k not in ('emergency_stop',) else '') }}">{{v}}</td></tr>{% endfor %}</table>
<p class="mute">JSON: <a href="/health.json">/health.json</a></p></div>{% endblock %}""",
}

NAV = [("/", "Overview"), ("/pipeline", "Pipeline"), ("/scripts", "Scripts"), ("/facts", "Facts"), ("/storyboards", "Storyboards"),
       ("/videos", "Videos"), ("/quality", "Quality"), ("/publishing", "Publishing"), ("/analytics", "Analytics"),
       ("/finance", "Finance"), ("/health", "Health")]
ENV = Environment(loader=DictLoader(T), autoescape=select_autoescape(default=True, default_for_string=True))


class Handler(BaseHTTPRequestHandler):
    server_version = "N4V3D"

    def log_message(self, fmt, *args):
        pass

    # -- helpers
    def session(self):
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return read_session(c["n4v3d"].value if "n4v3d" in c else None)

    def send_html(self, name, code=200, **ctx):
        s = self.session()
        con = db.connect()
        body = ENV.get_template(name).render(css=CSS, nav=NAV, path=urllib.parse.urlparse(self.path).path, user=s,
                                             csrf=s["csrf"] if s else "", stopped=db.emergency_stopped(con), **ctx).encode()
        self.send_response(code)
        self._sec_headers("text/html; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _sec_headers(self, ctype, length):
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self'; img-src 'self'; script-src 'unsafe-inline'")

    def redirect(self, to, cookie=None):
        self.send_response(303)
        self.send_header("Location", to)
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def form(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > 100_000:
            return {}
        return {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()}

    # -- routes
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/health.json":
            body = json.dumps(health()).encode()
            self.send_response(200)
            self._sec_headers("application/json", len(body))
            self.end_headers()
            return self.wfile.write(body)
        if path == "/login":
            return self.send_html("login", configured=AUTH.exists())
        s = self.session()
        if not s:
            return self.redirect("/login")
        con = db.connect()
        if path.startswith("/files/"):
            return self.serve_file(path[len("/files/"):])
        if path == "/":
            js = db.jobs(con)
            counts = ", ".join(f"{k}: {sum(1 for j in js if j['status'] == k)}" for k in db.STATUSES if any(j["status"] == k for j in js))
            return self.send_html("overview", jobs=js, counts=counts, rels=[r for r in releases() if r["video"]],
                                  waiting=[j for j in js if j["status"] in ("waiting", "blocked", "failed")], events=db.events(con, 25), h=health())
        if path == "/pipeline":
            return self.send_html("pipeline", jobs=db.jobs(con), prods=productions(), stages=db.STAGES)
        if path == "/scripts":
            return self.send_html("scripts", prods=productions())
        if path == "/facts":
            from ..research import gate
            ps = productions()
            return self.send_html("facts", prods=ps, gates={p["id"]: gate(p) for p in ps})
        if path == "/storyboards":
            rs = releases()
            for r in rs:
                r["has_sb"] = (RELEASES / r["dir"] / "storyboard.jpg").exists()
            return self.send_html("storyboards", rels=rs)
        if path == "/videos":
            return self.send_html("videos", rels=releases())
        if path == "/quality":
            return self.send_html("quality", rels=releases())
        if path == "/publishing":
            return self.send_html("publishing", rels=releases(), h=health())
        if path == "/analytics":
            return self.send_html("analytics")
        if path == "/finance":
            rows = [dict(r) for r in con.execute("SELECT * FROM ledger ORDER BY date DESC, id DESC")]
            rev = sum(r["amount"] for r in rows if r["kind"] == "revenue")
            exp = sum(r["amount"] for r in rows if r["kind"] == "expense")
            return self.send_html("finance", rows=rows, rev=rev, exp=exp)
        if path == "/health":
            return self.send_html("health", h=health())
        self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            ip = self.client_address[0]
            fails = [t for t in _fails.get(ip, []) if t > time.time() - 600]
            if len(fails) >= 5:
                return self.send_html("login", 429, err="Too many attempts. Try again in 10 minutes.", configured=True)
            f = self.form()
            if check_password(f.get("password", "")):
                _fails.pop(ip, None)
                secure = "; Secure" if os.environ.get("N4V3D_HTTPS") == "1" else ""
                return self.redirect("/", f"n4v3d={make_session()}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}{secure}")
            _fails[ip] = fails + [time.time()]
            return self.send_html("login", 401, err="Wrong password.", configured=AUTH.exists())
        s = self.session()
        if not s:
            return self.redirect("/login")
        f = self.form()
        if not hmac.compare_digest(f.get("csrf", ""), s["csrf"]):
            return self.send_error(403, "CSRF check failed")
        con = db.connect()
        if path == "/logout":
            return self.redirect("/login", "n4v3d=; Max-Age=0; Path=/")
        if path == "/stop":
            db.set_setting(con, "emergency_stop", True)
            db.log(con, None, "-", "action", f"EMERGENCY STOP engaged from dashboard by {s['user']}")
            return self.redirect("/")
        if path == "/resume":
            db.set_setting(con, "emergency_stop", False)
            (VAR / "STOP").unlink(missing_ok=True)
            db.log(con, None, "-", "info", f"emergency stop released by {s['user']}")
            return self.redirect("/")
        if path == "/enqueue":
            p = f.get("path", "")
            if not (ROOT / p / "production.json").exists():
                return self.send_error(400, "unknown production")
            db.enqueue(con, p)
            return self.redirect("/pipeline")
        if path.startswith("/job/"):
            parts = path.strip("/").split("/")
            jid, act = int(parts[1]), parts[2]
            if act == "approve":
                db.update(con, jid, approved_by=s["user"], approved_at=db.now(), next_run_at=None)
                db.log(con, jid, "APPROVAL", "info", f"publish approval recorded by {s['user']} (dashboard)")
            elif act == "retry":
                db.update(con, jid, status="pending", attempts=0, next_run_at=None, last_error=None)
                db.log(con, jid, "-", "info", "manual retry requested")
            return self.redirect("/pipeline")
        if path == "/finance":
            try:
                amt = float(f["amount"])
            except (KeyError, ValueError):
                return self.send_error(400)
            con.execute("INSERT INTO ledger(date, kind, amount, currency, description, created) VALUES (?,?,?,?,?,?)",
                        (f.get("date"), f.get("kind") if f.get("kind") in ("revenue", "expense") else "expense", amt,
                         f.get("currency", "USD")[:5], f.get("description", "")[:200], db.now()))
            return self.redirect("/finance")
        self.send_error(404)

    def serve_file(self, rel):
        target = (RELEASES / urllib.parse.unquote(rel)).resolve()
        if not str(target).startswith(str(RELEASES.resolve()) + os.sep) or not target.is_file():
            return self.send_error(404)
        ctype = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png", ".srt": "text/plain", ".md": "text/plain",
                 ".json": "application/json"}.get(target.suffix, "application/octet-stream")
        size = target.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else 0
            end = min(int(b), size - 1) if b else size - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Accept-Ranges", "bytes")
        self._sec_headers(ctype, end - start + 1)
        self.end_headers()
        with open(target, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = fh.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)


def serve(host="127.0.0.1", port=8787):
    if not AUTH.exists():
        print("No dashboard password set. Run: python -m n4v3d_media.dashboard.app --set-password")
    print(f"N4V3D Control Center on http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-password", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args()
    if a.set_password:
        pw = os.environ.get("N4V3D_DASHBOARD_PASSWORD") or getpass.getpass("New dashboard password: ")
        if len(pw) < 12:
            raise SystemExit("Use at least 12 characters.")
        set_password(pw)
        print("password saved (PBKDF2-SHA256) to", AUTH)
    else:
        serve(a.host, a.port)
