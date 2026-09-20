import urllib.request, sys
url = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000/health'
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        print(r.read().decode())
        sys.exit(0)
except Exception as e:
    print('FAIL', e)
    sys.exit(1)
