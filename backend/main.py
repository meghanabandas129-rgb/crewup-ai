"""CrewUp AI: runnable prototype API; SQLite persistence, access controls and explainable recommendations."""
import os, sqlite3, secrets, hashlib, hmac, time, json
import psycopg
from postgres_compat import PGConnection
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB=os.getenv('DATABASE_PATH',os.path.join(os.path.dirname(__file__),'crewup.db'))
DATABASE_URL=os.getenv('DATABASE_URL','')
if os.getenv('ENVIRONMENT','development').lower()=='production' and not DATABASE_URL:
    raise RuntimeError('Production requires DATABASE_URL')
SECRET=os.getenv('JWT_SECRET','crewup-local-development-key-change-before-release-2026')
if os.getenv('ENVIRONMENT','development').lower()=='production' and (len(SECRET)<32 or SECRET=='crewup-local-development-key-change-before-release-2026'):
    raise RuntimeError('Set a unique JWT_SECRET of at least 32 characters for production')
ORIGINS=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')
app=FastAPI(title='CrewUp AI API',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

def now(): return datetime.now(timezone.utc).isoformat()
@contextmanager
def db():
    if DATABASE_URL:
        c = PGConnection(DATABASE_URL)
    else:
        c = sqlite3.connect(DB, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
def asdict(r):return dict(r) if r else None
def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000).hex()
def verify(password,value):
    try:
        salt,_=value.split(':');return hmac.compare_digest(password_hash(password,salt),value)
    except: return False
def token(uid):return jwt.encode({'sub':str(uid),'exp':int(time.time())+86400*7},SECRET,algorithm='HS256')
def current(authorization:Optional[str]=Header(None)):
    if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Login required')
    try: uid=int(jwt.decode(authorization[7:],SECRET,algorithms=['HS256'])['sub'])
    except Exception:raise HTTPException(401,'Invalid or expired login')
    with db() as c:u=c.execute('SELECT id,name,email,skills,city,interests,avatar FROM users WHERE id=?',(uid,)).fetchone()
    if not u:raise HTTPException(401,'User no longer exists')
    return asdict(u)
def member(c,crew,user):
    r=c.execute('SELECT role FROM crew_members WHERE crew_id=? AND user_id=?',(crew,user)).fetchone()
    if not r:raise HTTPException(403,'Not a crew member')
    return r['role']
def manager(c,crew,user):
    if member(c,crew,user)!='owner':raise HTTPException(403,'Only the crew owner can approve')
def event_row(c,id):
    r=c.execute('SELECT * FROM events WHERE id=?',(id,)).fetchone()
    if not r:raise HTTPException(404,'Event not found')
    return r

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,skills TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '',interests TEXT NOT NULL DEFAULT '',avatar TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,title TEXT,category TEXT,location TEXT,event_date TEXT,description TEXT,cover TEXT,mode TEXT);
        CREATE TABLE IF NOT EXISTS crews(id INTEGER PRIMARY KEY,name TEXT NOT NULL,description TEXT DEFAULT '',event_id INTEGER,created_by INTEGER NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(event_id) REFERENCES events(id),FOREIGN KEY(created_by) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS crew_members(crew_id INTEGER NOT NULL,user_id INTEGER NOT NULL,role TEXT NOT NULL DEFAULT 'member',joined_at TEXT NOT NULL,PRIMARY KEY(crew_id,user_id));
        CREATE TABLE IF NOT EXISTS join_requests(id INTEGER PRIMARY KEY,crew_id INTEGER NOT NULL,user_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,UNIQUE(crew_id,user_id));
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,crew_id INTEGER NOT NULL,title TEXT NOT NULL,description TEXT DEFAULT '',status TEXT NOT NULL DEFAULT 'todo',priority TEXT NOT NULL DEFAULT 'medium',assignee_id INTEGER,due_date TEXT DEFAULT '',skills TEXT DEFAULT '',created_at TEXT NOT NULL,FOREIGN KEY(crew_id) REFERENCES crews(id));
        CREATE TABLE IF NOT EXISTS transfers(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL,from_user INTEGER NOT NULL,to_user INTEGER NOT NULL,reason TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'pending_recipient',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(task_id) REFERENCES tasks(id));
        CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,crew_id INTEGER NOT NULL,actor_id INTEGER NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,crew_id INTEGER NOT NULL,user_id INTEGER NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS travel_plans(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,event_id INTEGER NOT NULL,departure_city TEXT NOT NULL,travel_date TEXT NOT NULL,mode TEXT NOT NULL DEFAULT 'Flexible',visibility TEXT NOT NULL DEFAULT 'opt_in',created_at TEXT NOT NULL,UNIQUE(user_id,event_id),FOREIGN KEY(user_id) REFERENCES users(id),FOREIGN KEY(event_id) REFERENCES events(id));
        CREATE TABLE IF NOT EXISTS travel_requests(id INTEGER PRIMARY KEY,from_user INTEGER NOT NULL,to_user INTEGER NOT NULL,event_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,UNIQUE(from_user,to_user,event_id),FOREIGN KEY(from_user) REFERENCES users(id),FOREIGN KEY(to_user) REFERENCES users(id),FOREIGN KEY(event_id) REFERENCES events(id));
        ''')
        if c.execute('SELECT count(*) FROM users').fetchone()[0]:
            return
        if os.getenv('ENVIRONMENT', 'development').lower() == 'production':
            return
        demo=[('Aarav Mehta','aarav@demo.crewup','React,TypeScript,UI/UX','Bengaluru','Hackathons,Web Apps'),('Ishita Rao','ishita@demo.crewup','Python,FastAPI,AI/ML','Bengaluru','AI,Hackathons'),('Rohan Shah','rohan@demo.crewup','Node.js,PostgreSQL,APIs','Mysuru','Open Source,Startups'),('Zoya Khan','zoya@demo.crewup','Figma,Branding,React','Hyderabad','Design,Tech Events'),('Dev Patel','dev@demo.crewup','Python,Data Science,AI/ML','Pune','AI,Research'),('Ananya Iyer','ananya@demo.crewup','React,Accessibility,TypeScript','Chennai','Web Apps,Community')]
        for name,email,skills,city,interests in demo:c.execute('INSERT INTO users(name,email,password,skills,city,interests) VALUES(?,?,?,?,?,?)',(name,email,password_hash('demo1234'),skills,city,interests))
        events=[('CodeVerse India','Hackathon','Online','2026-11-11','Build purposeful technology with a team.','hackathon','Online'),('Design Forward Summit','Design','Bengaluru','2026-12-12','Connect with designers and builders.','design','In person'),('Open Source Weekend','Community','Hyderabad','2026-12-19','Contribute to real open-source projects.','opensource','Hybrid'),('AI Builders Jam','AI & ML','Online','2027-01-09','Prototype practical AI workflows.','ai','Online'),('Campus Innovation Fest','Tech Fest','Chennai','2027-01-23','A student-led technology showcase.','campus','In person'),('Full Stack Sprint','Workshop','Pune','2027-02-06','Build a full stack product together.','web','Hybrid')]
        for e in events:c.execute('INSERT INTO events(title,category,location,event_date,description,cover,mode) VALUES(?,?,?,?,?,?,?)',e)
        c.execute('INSERT INTO crews(name,description,event_id,created_by,created_at) VALUES(?,?,?,?,?)',('Pixel Pioneers','Building thoughtful products with AI and web technology.',1,1,now()))
        for uid,role in [(1,'owner'),(2,'member'),(3,'member')]:c.execute('INSERT INTO crew_members VALUES(?,?,?,?)',(1,uid,role,now()))
        for title,description,status,priority,uid,skills,due in [('Design landing page','Create a responsive design system','done','high',1,'React,UI/UX','2026-11-09'),('Build matching API','Implement compatibility ranking','in_progress','high',2,'Python,AI/ML','2026-11-10'),('Connect database','Set up storage and indexes','todo','high',3,'PostgreSQL,APIs','2026-11-10'),('Test user journeys','Run end-to-end checks','todo','medium',1,'React,Python','2026-11-11'),('Prepare demo deck','Explain the solution to judges','review','medium',2,'Design,Branding','2026-11-11')]:c.execute('INSERT INTO tasks(crew_id,title,description,status,priority,assignee_id,due_date,skills,created_at) VALUES(1,?,?,?,?,?,?,?,?)',(title,description,status,priority,uid,due,skills,now()))
        c.execute('INSERT INTO activity(crew_id,actor_id,action,detail,created_at) VALUES(?,?,?,?,?)',(1,1,'created','Created Pixel Pioneers workspace',now()))
if not DATABASE_URL:
    init()

class Login(BaseModel):email:str;password:str
class Register(BaseModel):name:str=Field(min_length=2);email:str;password:str=Field(min_length=8);skills:str='';city:str='';interests:str=''
class Profile(BaseModel):name:str;skills:str='';city:str='';interests:str=''
class CrewCreate(BaseModel):name:str=Field(min_length=3);description:str='';event_id:Optional[int]=None
class TaskCreate(BaseModel):title:str=Field(min_length=2);description:str='';priority:str='medium';assignee_id:Optional[int]=None;due_date:str='';skills:str=''
class StatusChange(BaseModel):status:str
class TransferCreate(BaseModel):to_user:int;reason:str=Field(min_length=3);notes:str=''
class Decision(BaseModel):decision:str
class ChatMessage(BaseModel):body:str=Field(min_length=1,max_length=1000)
class TravelPlan(BaseModel):event_id:int;departure_city:str=Field(min_length=2,max_length=70);travel_date:str=Field(min_length=8,max_length=10);mode:str='Flexible'
class TravelRequest(BaseModel):event_id:int;to_user:int

def log(c,crew,actor,action,detail):c.execute('INSERT INTO activity(crew_id,actor_id,action,detail,created_at) VALUES(?,?,?,?,?)',(crew,actor,action,detail,now()))

@app.get('/api/health')
def health():return {'ok':True,'service':'CrewUp AI'}

from collections import defaultdict, deque
from threading import Lock

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 900

_login_failures = defaultdict(deque)
_login_lock = Lock()
_login_failures_lock = _login_lock

def login_rate_key(request, email):
    ip = request.client.host if request.client else "unknown"
    return ip

def check_login_limit(key):
    current = time.monotonic()

    with _login_lock:
        attempts = _login_failures[key]

        while attempts and current - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()

        if len(attempts) >= LOGIN_MAX_FAILURES:
            retry_after = max(
                1, int(LOGIN_WINDOW_SECONDS - (current - attempts[0])) + 1
            )
            raise HTTPException(
                429,
                "Too many login attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)}
            )

def record_failed_login(key):
    with _login_lock:
        _login_failures[key].append(time.monotonic())

def clear_login_failures(key):
    with _login_lock:
        _login_failures.pop(key, None)

@app.post('/api/auth/login')
def login(x: Login, request: Request):
    email = x.email.strip().lower()
    key = login_rate_key(request, email)

    check_login_limit(key)

    with db() as c:
        u = c.execute(
            'SELECT * FROM users WHERE email=?',
            (email,)
        ).fetchone()

    if not u or not verify(x.password, u['password']):
        record_failed_login(key)
        raise HTTPException(401, "Incorrect email or password")

    clear_login_failures(key)

    return {
        'token': token(u['id']),
        'user': {
            k: u[k]
            for k in ['id', 'name', 'email', 'skills', 'city', 'interests']
        }
    }

@app.post('/api/auth/register')
def register(x:Register):
    with db() as c:
        try:cur=c.execute('INSERT INTO users(name,email,password,skills,city,interests) VALUES(?,?,?,?,?,?)',(x.name,x.email.strip().lower(),password_hash(x.password),x.skills,x.city,x.interests))
        except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation):raise HTTPException(409,'Email already registered')
        uid=cur.lastrowid
    return {'token':token(uid),'user':{'id':uid,'name':x.name,'email':x.email,'skills':x.skills,'city':x.city,'interests':x.interests}}
@app.get('/api/me')
def me(u=Depends(current)):return u
@app.patch('/api/me')
def update_me(x:Profile,u=Depends(current)):
    with db() as c:c.execute('UPDATE users SET name=?,skills=?,city=?,interests=? WHERE id=?',(x.name,x.skills,x.city,x.interests,u['id']))
    return {'ok':True}
@app.get('/api/people')
def people(u=Depends(current)):
    with db() as c:return [asdict(r) for r in c.execute('SELECT id,name,skills,city,interests FROM users WHERE id!=? ORDER BY id',(u['id'],))]
@app.get('/api/events')
def events(u=Depends(current)):
    with db() as c:return [asdict(r) for r in c.execute('SELECT * FROM events ORDER BY event_date')]
@app.get('/api/crews')
def crews(u=Depends(current)):
    with db() as c:return [asdict(r) for r in c.execute('''SELECT c.*,e.title AS event_title,(SELECT count(*) FROM crew_members m WHERE m.crew_id=c.id) AS member_count, (SELECT count(*) FROM tasks t WHERE t.crew_id=c.id) AS task_count, EXISTS(SELECT 1 FROM crew_members m WHERE m.crew_id=c.id AND m.user_id=?) AS joined FROM crews c LEFT JOIN events e ON c.event_id=e.id ORDER BY c.id DESC''',(u['id'],))]
@app.post('/api/crews')
def crew_create(x:CrewCreate,u=Depends(current)):
    with db() as c:
        if x.event_id:event_row(c,x.event_id)
        cur=c.execute('INSERT INTO crews(name,description,event_id,created_by,created_at) VALUES(?,?,?,?,?)',(x.name,x.description,x.event_id,u['id'],now()));id=cur.lastrowid
        c.execute('INSERT INTO crew_members VALUES(?,?,?,?)',(id,u['id'],'owner',now()));log(c,id,u['id'],'created','Created crew '+x.name)
    return {'id':id}
@app.post('/api/crews/{crew}/join')
def join(crew:int,u=Depends(current)):
    with db() as c:
        if not c.execute('SELECT 1 FROM crews WHERE id=?',(crew,)).fetchone():raise HTTPException(404,'Crew not found')
        if c.execute('SELECT 1 FROM crew_members WHERE crew_id=? AND user_id=?',(crew,u['id'])).fetchone():return {'status':'joined'}
        c.execute("INSERT INTO join_requests(crew_id,user_id,status,created_at) VALUES(?,?,?,?) ON CONFLICT(crew_id,user_id) DO UPDATE SET status='pending'",(crew,u['id'],'pending',now()))
    return {'status':'pending'}
@app.get('/api/crews/{crew}')
def crew_detail(crew:int,u=Depends(current)):
    with db() as c:
        member(c,crew,u['id'])
        r=c.execute('SELECT c.*,e.title AS event_title FROM crews c LEFT JOIN events e ON e.id=c.event_id WHERE c.id=?',(crew,)).fetchone()
        members=[asdict(v) for v in c.execute('SELECT u.id,u.name,u.email,u.skills,u.city,m.role FROM crew_members m JOIN users u ON u.id=m.user_id WHERE m.crew_id=?',(crew,))]
        tasks=[asdict(v) for v in c.execute('SELECT t.*,u.name AS assignee FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id WHERE t.crew_id=? ORDER BY t.id DESC',(crew,))]
        transfers=[asdict(v) for v in c.execute('''SELECT tr.*,t.title AS task_title,fu.name AS from_name,tu.name AS to_name FROM transfers tr JOIN tasks t ON t.id=tr.task_id JOIN users fu ON fu.id=tr.from_user JOIN users tu ON tu.id=tr.to_user WHERE t.crew_id=? ORDER BY tr.id DESC''',(crew,))]
        requests=[asdict(v) for v in c.execute('SELECT j.id,j.user_id,j.status,u.name,u.skills FROM join_requests j JOIN users u ON u.id=j.user_id WHERE j.crew_id=? AND j.status=?',(crew,'pending'))]
        activity=[asdict(v) for v in c.execute('SELECT a.*,u.name FROM activity a JOIN users u ON u.id=a.actor_id WHERE a.crew_id=? ORDER BY a.id DESC LIMIT 30',(crew,))]
        messages=[asdict(v) for v in c.execute('SELECT m.*,u.name FROM messages m JOIN users u ON u.id=m.user_id WHERE m.crew_id=? ORDER BY m.id DESC LIMIT 100',(crew,))]
    return {'crew':asdict(r),'members':members,'tasks':tasks,'transfers':transfers,'requests':requests,'activity':activity,'messages':list(reversed(messages))}
@app.post('/api/crews/{crew}/requests/{req}/decision')
def join_decide(crew:int,req:int,x:Decision,u=Depends(current)):
    if x.decision not in ('accept','reject'):raise HTTPException(400,'Invalid decision')
    with db() as c:
        manager(c,crew,u['id']);r=c.execute("SELECT * FROM join_requests WHERE id=? AND crew_id=? AND status='pending'",(req,crew)).fetchone()
        if not r:raise HTTPException(409,'Request unavailable')
        c.execute('UPDATE join_requests SET status=? WHERE id=?',('accepted' if x.decision=='accept' else 'rejected',req))
        if x.decision=='accept':c.execute('INSERT OR IGNORE INTO crew_members VALUES(?,?,?,?)',(crew,r['user_id'],'member',now()))
        log(c,crew,u['id'],'membership','Membership request '+x.decision+'ed')
    return {'ok':True}
@app.post('/api/crews/{crew}/tasks')
def task_create(crew:int,x:TaskCreate,u=Depends(current)):
    if x.priority not in ('low','medium','high'):raise HTTPException(400,'Invalid priority')
    with db() as c:
        member(c,crew,u['id'])
        if x.assignee_id:member(c,crew,x.assignee_id)
        cur=c.execute('INSERT INTO tasks(crew_id,title,description,status,priority,assignee_id,due_date,skills,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(crew,x.title,x.description,'todo',x.priority,x.assignee_id,x.due_date,x.skills,now()))
        log(c,crew,u['id'],'task','Created task '+x.title)
    return {'id':cur.lastrowid}
@app.patch('/api/tasks/{task}/status')
def task_status(task:int,x:StatusChange,u=Depends(current)):
    if x.status not in ('todo','in_progress','review','done'):raise HTTPException(400,'Invalid status')
    with db() as c:
        t=c.execute('SELECT * FROM tasks WHERE id=?',(task,)).fetchone()
        if not t:raise HTTPException(404,'Task not found')
        role=member(c,t['crew_id'],u['id'])
        if role!='owner' and t['assignee_id']!=u['id']:raise HTTPException(403,'Only assignee or owner can edit task')
        c.execute('UPDATE tasks SET status=? WHERE id=?',(x.status,task));log(c,t['crew_id'],u['id'],'status',f'Updated {t["title"]} to {x.status}')
    return {'ok':True}

def ranked(c,crew,skills,exclude=None):
    wanted={s.strip().lower() for s in (skills or '').split(',') if s.strip()}
    rows=c.execute('''SELECT u.id,u.name,u.skills,u.city, count(t.id) AS active_tasks FROM crew_members m JOIN users u ON u.id=m.user_id LEFT JOIN tasks t ON t.assignee_id=u.id AND t.status!='done' AND t.crew_id=m.crew_id WHERE m.crew_id=? GROUP BY u.id ORDER BY u.id''',(crew,)).fetchall()
    out=[]
    for r in rows:
        if r['id']==exclude:continue
        have={s.strip().lower() for s in (r['skills'] or '').split(',') if s.strip()}
        skill=len(wanted&have)/len(wanted) if wanted else .5
        capacity=1/(1+r['active_tasks']/2)
        score=round((.7*skill+.3*capacity)*100)
        out.append({**asdict(r),'score':score,'explanation':f'{len(wanted&have)} matching skill(s), {r["active_tasks"]} active task(s); score combines 70% skills and 30% available capacity.'})
    return sorted(out,key=lambda p:(-p['score'],p['id']))
@app.get('/api/crews/{crew}/recommendations')
def crew_recommendations(crew:int,skills:str='',exclude:Optional[int]=None,u=Depends(current)):
    with db() as c:member(c,crew,u['id']);return ranked(c,crew,skills,exclude)
@app.get('/api/radar')
def radar(skills:str='',event_id:Optional[int]=None,u=Depends(current)):
    wanted={s.strip().lower() for s in skills.split(',') if s.strip()} or {s.strip().lower() for s in (u['skills'] or '').split(',') if s.strip()}
    with db() as c:users=c.execute('SELECT id,name,skills,city,interests FROM users WHERE id!=?',(u['id'],)).fetchall()
    out=[]
    for p in users:
        have={s.strip().lower() for s in (p['skills'] or '').split(',') if s.strip()}
        overlap=len(wanted&have);complement=len(have-wanted)
        score=min(98,round(35+overlap*18+min(complement,3)*9+(8 if p['city']==u['city'] else 0)))
        out.append({**asdict(p),'score':score,'reason':f'{overlap} shared skills, {complement} complementary skills'+(', same city' if p['city']==u['city'] else '')})
    return sorted(out,key=lambda p:-p['score'])
@app.post('/api/tasks/{task}/transfers')
def transfer_create(task:int,x:TransferCreate,u=Depends(current)):
    with db() as c:
        t=c.execute('SELECT * FROM tasks WHERE id=?',(task,)).fetchone()
        if not t:raise HTTPException(404,'Task not found')
        member(c,t['crew_id'],u['id']);member(c,t['crew_id'],x.to_user)
        if t['assignee_id']!=u['id']:raise HTTPException(403,'Only current assignee can request transfer')
        if x.to_user==u['id']:raise HTTPException(400,'Choose another member')
        if c.execute("SELECT 1 FROM transfers WHERE task_id=? AND status IN ('pending_recipient','pending_owner')",(task,)).fetchone():raise HTTPException(409,'Pending transfer already exists')
        cur=c.execute('INSERT INTO transfers(task_id,from_user,to_user,reason,notes,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(task,u['id'],x.to_user,x.reason,x.notes,'pending_recipient',now(),now()))
        log(c,t['crew_id'],u['id'],'transfer','Requested transfer of '+t['title'])
    return {'id':cur.lastrowid}
@app.post('/api/transfers/{transfer}/decision')
def transfer_decide(transfer:int,x:Decision,u=Depends(current)):
    if x.decision not in ('accept','reject','approve'):raise HTTPException(400,'Invalid decision')
    with db() as c:
        t=c.execute('SELECT tr.*,ta.crew_id,ta.title,ta.assignee_id FROM transfers tr JOIN tasks ta ON ta.id=tr.task_id WHERE tr.id=?',(transfer,)).fetchone()
        if not t:raise HTTPException(404,'Transfer not found')
        member(c,t['crew_id'],u['id'])
        if t['status']=='pending_recipient':
            if u['id']!=t['to_user'] or x.decision not in ('accept','reject'):raise HTTPException(403,'Recipient must accept or reject')
            status='pending_owner' if x.decision=='accept' else 'rejected'
        elif t['status']=='pending_owner':
            manager(c,t['crew_id'],u['id'])
            if x.decision not in ('approve','reject'):raise HTTPException(400,'Owner must approve or reject')
            if x.decision=='approve':
                if t['assignee_id']!=t['from_user']:raise HTTPException(409,'Task ownership has changed')
                c.execute('UPDATE tasks SET assignee_id=? WHERE id=?',(t['to_user'],t['task_id']))
            status='approved' if x.decision=='approve' else 'rejected'
        else:raise HTTPException(409,'Transfer already closed')
        c.execute('UPDATE transfers SET status=?,updated_at=? WHERE id=?',(status,now(),transfer))
        log(c,t['crew_id'],u['id'],'transfer',f'{t["title"]}: {status.replace("_"," ")}')
    return {'status':status}
@app.post('/api/crews/{crew}/messages')
def message_create(crew:int,x:ChatMessage,u=Depends(current)):
    with db() as c:member(c,crew,u['id']);c.execute('INSERT INTO messages(crew_id,user_id,body,created_at) VALUES(?,?,?,?)',(crew,u['id'],x.body,now()))
    return {'ok':True}
@app.get('/api/crews/{crew}/insights')
def insights(crew:int,u=Depends(current)):
    with db() as c:
        member(c,crew,u['id'])
        tasks=[asdict(r) for r in c.execute('SELECT * FROM tasks WHERE crew_id=?',(crew,))]
        total=len(tasks);done=sum(t['status']=='done' for t in tasks);overdue=sum(bool(t['due_date']) and t['due_date']<datetime.now().date().isoformat() and t['status']!='done' for t in tasks)
        pending=c.execute("SELECT count(*) FROM transfers tr JOIN tasks t ON t.id=tr.task_id WHERE t.crew_id=? AND tr.status IN ('pending_recipient','pending_owner')",(crew,)).fetchone()[0]
        recommendations=[]
        if overdue:recommendations.append(f'{overdue} overdue task(s) need review.')
        if pending:recommendations.append(f'{pending} transfer request(s) need action.')
        if total and done<total:recommendations.append('Review in-progress work and assign owners to unassigned tasks.')
        if not recommendations:recommendations.append('No urgent alerts detected from the current task data.')
    return {'total':total,'done':done,'overdue':overdue,'pending_transfers':pending,'completion_rate':round(100*done/total) if total else 0,'summary':f'{done} of {total} tasks complete. {overdue} overdue. {pending} pending handovers.','recommendations':recommendations,'engine':'Transparent rules-based coordination (no external LLM required)'}


# Travel Radar is opt-in. Only participants who have created event plans are discoverable.
# The API intentionally does not publish emails, phone numbers, live positions or exact itineraries.
@app.get('/api/travel/plans')
def my_travel_plans(u=Depends(current)):
    with db() as c:
        return [asdict(r) for r in c.execute('''SELECT p.*,e.title AS event_title FROM travel_plans p JOIN events e ON e.id=p.event_id WHERE p.user_id=? ORDER BY p.travel_date''',(u['id'],))]

@app.post('/api/travel/plans')
def save_travel_plan(x:TravelPlan,u=Depends(current)):
    if x.mode not in ('Flexible','Train','Bus','Flight','Carpool'):raise HTTPException(422,'Invalid travel mode')
    with db() as c:
        event_row(c,x.event_id)
        c.execute('''INSERT INTO travel_plans(user_id,event_id,departure_city,travel_date,mode,created_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(user_id,event_id) DO UPDATE SET departure_city=excluded.departure_city,travel_date=excluded.travel_date,mode=excluded.mode''',
        (u['id'],x.event_id,x.departure_city.strip(),x.travel_date,x.mode,now()))
    return {'ok':True,'message':'You opted in to event-specific travel discovery.'}

@app.delete('/api/travel/plans/{event_id}')
def delete_travel_plan(event_id:int,u=Depends(current)):
    with db() as c:c.execute('DELETE FROM travel_plans WHERE user_id=? AND event_id=?',(u['id'],event_id))
    return {'ok':True}

@app.get('/api/travel/radar')
def travel_radar(event_id:Optional[int]=None,u=Depends(current)):
    with db() as c:
        plans=c.execute('''SELECT p.event_id,p.departure_city,p.travel_date,p.mode,p.user_id,u.name,e.title AS event_title
             FROM travel_plans p JOIN users u ON u.id=p.user_id JOIN events e ON e.id=p.event_id
             WHERE p.user_id!=? AND (? IS NULL OR p.event_id=?) AND EXISTS
             (SELECT 1 FROM travel_plans self WHERE self.user_id=? AND self.event_id=p.event_id)
             ORDER BY p.travel_date,p.id''',(u['id'],event_id,event_id,u['id'])).fetchall()
        my_plans={r['event_id']:r for r in c.execute('SELECT * FROM travel_plans WHERE user_id=?',(u['id'],))}
        out=[]
        for p in plans:
            mine=my_plans[p['event_id']]
            same_city=mine['departure_city'].strip().lower()==p['departure_city'].strip().lower()
            same_day=mine['travel_date']==p['travel_date']
            status=c.execute('''SELECT status FROM travel_requests WHERE from_user=? AND to_user=? AND event_id=?''',(u['id'],p['user_id'],p['event_id'])).fetchone()
            out.append({**asdict(p),'same_city':same_city,'same_day':same_day,'score':(55+int(same_city)*25+int(same_day)*20),'request_status':status['status'] if status else None})
        return sorted(out,key=lambda x:-x['score'])

@app.post('/api/travel/requests')
def send_travel_request(x:TravelRequest,u=Depends(current)):
    if u['id']==x.to_user:raise HTTPException(400,'Cannot request yourself')
    with db() as c:
        for uid in (u['id'],x.to_user):
            if not c.execute('SELECT 1 FROM travel_plans WHERE user_id=? AND event_id=?',(uid,x.event_id)).fetchone():
                raise HTTPException(403,'Both users must opt in for this event')
        c.execute('''INSERT INTO travel_requests(from_user,to_user,event_id,status,created_at) VALUES(?,?,?,?,?)
          ON CONFLICT(from_user,to_user,event_id) DO UPDATE SET status='pending',created_at=excluded.created_at''',
          (u['id'],x.to_user,x.event_id,'pending',now()))
    return {'ok':True,'status':'pending'}

@app.get('/api/travel/requests')
def travel_requests(u=Depends(current)):
    with db() as c:
        return [asdict(r) for r in c.execute('''SELECT tr.id,tr.from_user,tr.to_user,tr.event_id,tr.status,e.title AS event_title, a.name AS sender_name,b.name AS recipient_name
        FROM travel_requests tr JOIN events e ON e.id=tr.event_id JOIN users a ON a.id=tr.from_user JOIN users b ON b.id=tr.to_user
        WHERE tr.to_user=? OR tr.from_user=? ORDER BY tr.id DESC''',(u['id'],u['id']))]

@app.post('/api/travel/requests/{request_id}/decision')
def decide_travel(request_id:int,x:Decision,u=Depends(current)):
    if x.decision not in ('accept','reject'):raise HTTPException(422,'Invalid decision')
    with db() as c:
        r=c.execute('SELECT * FROM travel_requests WHERE id=?',(request_id,)).fetchone()
        if not r:raise HTTPException(404,'Request not found')
        if r['to_user']!=u['id']:raise HTTPException(403,'Only recipient can decide')
        if r['status']!='pending':raise HTTPException(409,'Request already processed')
        c.execute('UPDATE travel_requests SET status=? WHERE id=?',('accepted' if x.decision=='accept' else 'rejected',request_id))
    return {'ok':True,'status':'accepted' if x.decision=='accept' else 'rejected'}

# Phase 2: read-only, permission-checked tools with optional Ollama generation.
from ai_agent import run_tools, compose_answer, crew_builder, plan_tasks

class CopilotRequest(BaseModel):
    question: str = Field(min_length=3,max_length=1000)
class CrewBuilderRequest(BaseModel):
    skills: str = Field(min_length=2,max_length=400)
    event_id: Optional[int] = None
class PlanRequest(BaseModel):
    goal: str = Field(min_length=5,max_length=1000)

@app.post('/api/ai/crews/{crew}/copilot')
def ai_copilot(crew:int,x:CopilotRequest,u=Depends(current)):
    with db() as c:
        member(c,crew,u['id'])
        data=run_tools(c,crew,x.question)
    return compose_answer(x.question,data)

@app.post('/api/ai/crew-builder')
def ai_crew_builder(x:CrewBuilderRequest,u=Depends(current)):
    with db() as c:
        if x.event_id is not None:event_row(c,x.event_id)
        return crew_builder(c,u['id'],x.skills,x.event_id)

@app.post('/api/ai/crews/{crew}/plan')
def ai_plan(crew:int,x:PlanRequest,u=Depends(current)):
    with db() as c:member(c,crew,u['id'])
    return plan_tasks(x.goal)

@app.get('/api/ai/status')
def ai_status(u=Depends(current)):
    return {'enabled':os.getenv('AI_ENABLED','false').lower()=='true','provider':'Ollama','model':os.getenv('OLLAMA_MODEL','qwen2.5:3b'),'fallback':'transparent rules','actions':'read-only; writes require explicit approval'}
