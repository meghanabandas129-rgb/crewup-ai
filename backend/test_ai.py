"""Safety and regression checks for Phase 2 AI features."""
import os,tempfile
fd,path=tempfile.mkstemp(prefix='crewup_ai_test_',suffix='.db');os.close(fd)
os.environ['DATABASE_PATH']=path
os.environ['AI_ENABLED']='false'
try:
    from fastapi.testclient import TestClient
    from main import app
    c=TestClient(app)
    def login(name):
        r=c.post('/api/auth/login',json={'email':name+'@demo.crewup','password':'demo1234'})
        assert r.status_code==200,r.text
        return {'Authorization':'Bearer '+r.json()['token']}
    owner=login('aarav');outsider=login('zoya')
    resp=c.post('/api/ai/crew-builder',headers=owner,json={'skills':'Python,AI/ML'})
    assert resp.status_code==200,resp.text
    assert resp.json()['candidates'] and resp.json()['engine']=='rules_fallback'
    assert all('email' not in p for p in resp.json()['candidates'])
    denied=c.post('/api/ai/crews/1/copilot',headers=outsider,json={'question':'What are tasks?'})
    assert denied.status_code==403,denied.text
    ok=c.post('/api/ai/crews/1/copilot',headers=owner,json={'question':'What is overdue?'})
    assert ok.status_code==200,ok.text
    assert 'active_tasks' in ok.json()['tools_used']
    planned=c.post('/api/ai/crews/1/plan',headers=owner,json={'goal':'Create a school hackathon project'})
    assert planned.status_code==200 and planned.json()['saved'] is False
    bad=c.post('/api/ai/crew-builder',headers={},json={'skills':'Python'})
    assert bad.status_code==401
    print('PASS — builder, private fields excluded, crew permission, read-only tools, task planning, auth and no-key fallback')
finally:
    os.unlink(path)
