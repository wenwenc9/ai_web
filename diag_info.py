import requests
BASE = 'http://localhost:9001/ag-ui'
for method, url in [('GET', f'{BASE}/info'), ('POST', f'{BASE}/info'), ('OPTIONS', f'{BASE}/info'), ('GET', f'{BASE}/openapi.json')]:
    try:
        r = requests.request(method, url, timeout=10)
        print(f'[{method} {url}] -> {r.status_code}')
        print('   ', r.text[:300].replace(chr(10), ' '))
    except Exception as e:
        print(f'[{method} {url}] -> ERROR {e}')
