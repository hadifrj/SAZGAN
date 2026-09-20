from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The isolated test environment used for static validation does not ship the
# full Flask runtime. core.access only needs these names at import time; tests
# below exercise its pure role/path decisions without starting Flask.
if 'flask' not in sys.modules:
    flask_stub = types.ModuleType('flask')
    flask_stub.redirect = lambda *args, **kwargs: None
    flask_stub.request = types.SimpleNamespace()
    flask_stub.session = {}
    flask_stub.g = types.SimpleNamespace()
    flask_stub.has_request_context = lambda: False
    sys.modules['flask'] = flask_stub

# PyQt5 is not required for HTTP-client unit tests; provide the tiny subset
# used by native_client.api_client at import time.
if 'PyQt5' not in sys.modules:
    pyqt5_stub = types.ModuleType('PyQt5')
    qtcore_stub = types.ModuleType('PyQt5.QtCore')

    class _QObject:
        def __init__(self, *args, **kwargs):
            pass

    class _Signal:
        def emit(self, *args, **kwargs):
            pass

    qtcore_stub.QObject = _QObject
    qtcore_stub.pyqtSignal = lambda *args, **kwargs: _Signal()
    pyqt5_stub.QtCore = qtcore_stub
    sys.modules['PyQt5'] = pyqt5_stub
    sys.modules['PyQt5.QtCore'] = qtcore_stub
