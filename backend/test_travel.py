"""Smoke test for privacy opt-in event travel connections."""
import os,tempfile
fd,path=tempfile.mkstemp(prefix='crewup_travel_',suffix='.db');os.close(fd)
os.environ['DATABASE_PATH']=path
try:
    from fastapi.testclient import TestClient
    from main import app
    client=TestClient(app)
    def auth(name):
        r=client.post('/api/auth/login',json={'email':name+'@demo.crewup','password':'demo1234'})
        assert r.status_code==200,r.text
        return {'Authorization':'Bearer '+r.json()['token']}
    a,b=auth('aarav'),auth('ishita')
    assert client.get('/api/travel/radar',headers=a).json()==[]
    pa={'event_id':2,'departure_city':'Bengaluru','travel_date':'2026-12-12','mode':'Train'}
    assert client.post('/api/travel/plans',headers=a,json=pa).status_code==200
    assert client.get('/api/travel/radar',headers=a).json()==[]
    assert client.post('/api/travel/requests',headers=a,json={'event_id':2,'to_user':2}).status_code==403
    assert client.post('/api/travel/plans',headers=b,json=pa).status_code==200
    matches=client.get('/api/travel/radar',headers=a).json()
    assert len(matches)==1 and matches[0]['score']==100 and 'email' not in matches[0]
    assert client.post('/api/travel/requests',headers=a,json={'event_id':2,'to_user':2}).status_code==200
    req=client.get('/api/travel/requests',headers=b).json()[0]
    assert client.post(f"/api/travel/requests/{req['id']}/decision",headers=a,json={'decision':'accept'}).status_code==403
    assert client.post(f"/api/travel/requests/{req['id']}/decision",headers=b,json={'decision':'accept'}).json()['status']=='accepted'
    assert client.delete('/api/travel/plans/2',headers=b).status_code==200
    assert client.get('/api/travel/radar',headers=a).json()==[]
    print('PASS — travel opt-in, matching, private fields, permission checks, request approvals and removal')
finally:
    os.unlink(path)
