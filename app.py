import os, sqlite3, secrets, uuid
from pathlib import Path
from flask import Flask, request, session, redirect, url_for, render_template, abort, send_from_directory, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
app=Flask(__name__)
ROOT=Path(__file__).resolve().parent
UPLOAD=ROOT/'uploads'; UPLOAD.mkdir(exist_ok=True)
key=ROOT/'.secret'; key.touch(exist_ok=True)
if not key.read_text(): key.write_text(secrets.token_hex(32))
app.secret_key=key.read_text(); app.config['MAX_CONTENT_LENGTH']=20*1024*1024

def db():
    c=sqlite3.connect(ROOT/'edutrack.db'); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
    with db() as c:
        c.executescript((ROOT/'schema.sql').read_text())
        if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            password=os.environ.get('EDUTRACK_ADMIN_PASSWORD') or secrets.token_urlsafe(12)
            c.execute('INSERT INTO users(name,password,role) VALUES(?,?,?)',('admin',generate_password_hash(password),'admin'))
            print('Initial admin login: admin / '+password,flush=True)
init()
@app.before_request
def csrf():
    if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
    if request.method=='POST' and request.form.get('csrf')!=session['csrf']: abort(400)

def login_required(f):
    @wraps(f)
    def wrapped(*a,**k):
        if not session.get('uid'): return redirect(url_for('login'))
        return f(*a,**k)
    return wrapped

def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*a,**k):
        if session.get('role')!='admin': abort(403)
        return f(*a,**k)
    return wrapped

QUERY='''SELECT r.*,u.name author, COALESCE((SELECT AVG(stars) FROM ratings WHERE resource_id=r.id),0) rating,(SELECT COUNT(*) FROM ratings WHERE resource_id=r.id) votes FROM resources r JOIN users u ON u.id=r.user_id'''
@app.route('/')
def home():
    q=request.args.get('q',''); subject=request.args.get('subject',''); category=request.args.get('category',''); semester=request.args.get('semester','')
    with db() as c:
        rows=c.execute(QUERY+" WHERE status='approved' AND (title LIKE ? OR description LIKE ?) AND (?='' OR subject=?) AND (?='' OR category=?) AND (?='' OR semester=?) ORDER BY views DESC,r.id DESC",('%'+q+'%','%'+q+'%',subject,subject,category,category,semester,semester)).fetchall()
        subjects=c.execute("SELECT DISTINCT subject FROM resources WHERE status='approved' ORDER BY subject").fetchall()
    return render_template('page.html',page='home',rows=rows,subjects=subjects)
@app.route('/register',methods=['GET','POST'])
@app.route('/login',methods=['GET','POST'])
def login():
    register=request.path=='/register'
    if request.method=='POST':
        name=request.form['name'].strip(); password=request.form['password']
        with db() as c:
            if register:
                if not name or len(name)>60 or len(password)<8: flash('Enter a username and at least 8 password characters.')
                else:
                    try:
                        c.execute('INSERT INTO users(name,password) VALUES(?,?)',(name,generate_password_hash(password))); flash('Account created. Please sign in.'); return redirect(url_for('login'))
                    except sqlite3.IntegrityError: flash('Username already exists.')
            else:
                u=c.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
                if u and check_password_hash(u['password'],password):
                    session.clear(); session.update(uid=u['id'],name=u['name'],role=u['role']); return redirect(url_for('home'))
                flash('Incorrect username or password.')
    return render_template('page.html',page='register' if register else 'login')
@app.post('/logout')
def logout(): session.clear(); return redirect(url_for('home'))
@app.route('/upload',methods=['GET','POST'])
@login_required
def upload():
    if request.method=='POST':
        f=request.files.get('file'); original=secure_filename(f.filename) if f else ''; ext=Path(original).suffix.lower()
        title=request.form['title'].strip(); subject=request.form['subject'].strip(); category=request.form['category']; semester=request.form['semester']; desc=request.form['description'].strip()
        if not title or not subject or category not in ['PYQ','Notes','Project'] or semester not in list(map(str,range(1,9))) or ext not in ['.pdf','.txt','.docx','.pptx','.zip','.py']:
            flash('Please enter valid details and a supported file.'); return redirect(url_for('upload'))
        stored=uuid.uuid4().hex+ext; f.save(UPLOAD/stored)
        with db() as c: c.execute('INSERT INTO resources(title,subject,category,semester,description,filename,original,user_id) VALUES(?,?,?,?,?,?,?,?)',(title,subject,category,semester,desc,stored,original,session['uid']))
        flash('Uploaded! Waiting for admin approval.'); return redirect(url_for('mine'))
    return render_template('page.html',page='upload')
@app.get('/mine')
@login_required
def mine():
    with db() as c: rows=c.execute(QUERY+' WHERE user_id=? ORDER BY r.id DESC',(session['uid'],)).fetchall()
    return render_template('page.html',page='mine',rows=rows)
@app.get('/admin')
@admin_required
def admin():
    with db() as c: rows=c.execute(QUERY+' ORDER BY r.id DESC').fetchall()
    return render_template('page.html',page='admin',rows=rows)
@app.post('/review/<int:rid>')
@admin_required
def review(rid):
    status=request.form['status'];
    if status not in ['approved','rejected']: abort(400)
    with db() as c: c.execute('UPDATE resources SET status=? WHERE id=?',(status,rid))
    return redirect(url_for('admin'))
def resource(c,rid):
    r=c.execute(QUERY+' WHERE r.id=?',(rid,)).fetchone()
    if not r or (r['status']!='approved' and session.get('role')!='admin' and session.get('uid')!=r['user_id']): abort(404)
    return r
@app.get('/resource/<int:rid>')
def detail(rid):
    with db() as c:
        r=resource(c,rid)
        if r['status']=='approved': c.execute('UPDATE resources SET views=views+1 WHERE id=?',(rid,))
        r=resource(c,rid); comments=c.execute('SELECT comments.*,users.name FROM comments JOIN users ON users.id=comments.user_id WHERE resource_id=? ORDER BY comments.id DESC',(rid,)).fetchall()
    return render_template('page.html',page='detail',r=r,comments=comments)
@app.get('/download/<int:rid>')
def download(rid):
    with db() as c: r=resource(c,rid)
    return send_from_directory(UPLOAD,r['filename'],as_attachment=True,download_name=r['original'])
@app.post('/feedback/<int:rid>')
@login_required
def feedback(rid):
    with db() as c:
        r=resource(c,rid)
        if r['status']!='approved': abort(403)
        if 'stars' in request.form:
            stars=request.form['stars']
            if stars not in ['1','2','3','4','5']: abort(400)
            c.execute('INSERT INTO ratings VALUES(?,?,?) ON CONFLICT(resource_id,user_id) DO UPDATE SET stars=excluded.stars',(rid,session['uid'],int(stars)))
        else:
            body=request.form.get('body','').strip()
            if body and len(body)<=2000: c.execute('INSERT INTO comments(resource_id,user_id,body) VALUES(?,?,?)',(rid,session['uid'],body))
    return redirect(url_for('detail',rid=rid))
if __name__=='__main__': app.run(host='127.0.0.1',port=5000)
