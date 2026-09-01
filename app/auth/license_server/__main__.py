"""python -m app.auth.license_server"""
from app.auth.license_server.server import CFG, app, init_db
init_db()
host = CFG.get('host', '0.0.0.0')
port = int(CFG.get('port', 5050))
print('==================================================')
print('  Control PS License Server')
print(f'  Admin: http://127.0.0.1:{port}/admin')
print(f'  Telefon: http://KOMPUTER_IP:{port}/admin')
print('==================================================')
app.run(host=host, port=port, debug=False, threaded=True)