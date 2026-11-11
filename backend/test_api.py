"""Integration smoke tests for CrewUp's core end-to-end business flow."""
import os,tempfile
fd,path=tempfile.mkstemp(prefix='crewup_test_',suffix='.db');os.close(fd)
os.environ['DATABASE_PATH']=path
try:
    from fastapi.testclient import TestClient
    from main import app
    client=TestClient(app)
    def auth(who):
        r=client.post('/api/auth/login',json={'email':f'{who}@demo.crewup','password':'demo1234'})
        assert r.status_code==200,r.text
        return {'Authorization':'Bearer '+r.json()['token']}
    owner,source,target=auth('aarav'),auth('ishita'),auth('rohan')
    for path_ in ('/api/events','/api/radar','/api/crews','/api/crews/1','/api/crews/1/insights','/api/crews/1/recommendations?skills=Python'):
        assert client.get(path_,headers=owner).status_code==200,path_
    new=client.post('/api/crews/1/tasks',headers=owner,json={'title':'Integration smoke test','assignee_id':2,'skills':'Node.js,PostgreSQL'})
    assert new.status_code==200,new.text
    tid=new.json()['id']
    transfer=client.post(f'/api/tasks/{tid}/transfers',headers=source,json={'to_user':3,'reason':'Cannot continue','notes':'Please finish the API'})
    assert transfer.status_code==200,transfer.text
    xid=transfer.json()['id']
    assert client.post(f'/api/transfers/{xid}/decision',headers=owner,json={'decision':'approve'}).status_code==403
    assert client.post(f'/api/transfers/{xid}/decision',headers=target,json={'decision':'accept'}).json()['status']=='pending_owner'
    assert client.post(f'/api/transfers/{xid}/decision',headers=owner,json={'decision':'approve'}).json()['status']=='approved'
    assert client.post(f'/api/transfers/{xid}/decision',headers=owner,json={'decision':'approve'}).status_code==409
    task=next(t for t in client.get('/api/crews/1',headers=owner).json()['tasks'] if t['id']==tid)
    assert task['assignee_id']==3
    print('PASS — auth, events, matching, crew, insights, task creation, handover permissions, recipient approval, owner approval, reassignment, idempotence protection')
finally:
    os.unlink(path)
