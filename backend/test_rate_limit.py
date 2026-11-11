"""CrewUp login rate limiting smoke test; isolated temporary database."""
import os
import tempfile

fd, path = tempfile.mkstemp(prefix='crewup_rate_limit_', suffix='.db')
os.close(fd)
os.environ['DATABASE_PATH'] = path
os.environ['ENVIRONMENT'] = 'development'

try:
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)
    valid = {'email': 'aarav@demo.crewup', 'password': 'demo1234'}
    assert client.post('/api/auth/login', json=valid).status_code == 200

    incorrect = {'email': 'unknown@example.invalid', 'password': 'not-the-password'}
    for i in range(5):
        response = client.post('/api/auth/login', json=incorrect)
        assert response.status_code == 401, (i, response.text)

    limited = client.post('/api/auth/login', json=incorrect)
    assert limited.status_code == 429, limited.text
    assert int(limited.headers.get('Retry-After', '0')) > 0

    # An IP-based limit also blocks changing the email on the same client.
    limited_by_ip = client.post('/api/auth/login', json=valid)
    assert limited_by_ip.status_code == 429, limited_by_ip.text

    # Simulate the end of the 15-minute window and verify successful recovery.
    with main._login_failures_lock:
        main._login_failures.clear()
    recovered = client.post('/api/auth/login', json=valid)
    assert recovered.status_code == 200, recovered.text

    print('PASS — five failed logins, 429 with Retry-After, IP limit, recovery')
finally:
    os.unlink(path)
