"""Host-side tests for tools/plug_cal.py against a fake plug."""
import base64
import http.server
import json
import os
import sys
import threading
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import plug_cal  # noqa: E402


class FakePlug(http.server.BaseHTTPRequestHandler):
    log = []
    state = {"sensor/Voltage": 250.0, "sensor/Current": 0.24, "sensor/Power": 48.5, "number/Cal Scale Power": 1.0,
             "number/Cal Scale Voltage": 1.0, "number/Cal Scale Current": 1.0}

    def _auth(self):
        want = "Basic " + base64.b64encode(b"admin:secret").decode()
        if self.headers.get("Authorization") != want:
            self.send_response(401)
            self.end_headers()
            return False
        return True

    def _send(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._auth():
            return
        path = urllib.parse.unquote(self.path.lstrip("/"))
        if path in self.state:
            self._send({"id": path, "value": self.state[path], "state": str(self.state[path])})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self._auth():
            return
        path = urllib.parse.unquote(self.path.lstrip("/"))
        FakePlug.log.append(path)
        if path == "button/Calibrate Power/press":
            ref = float(FakePlug.log[-2].split("value=")[1])
            self.state["number/Cal Scale Power"] = round(self.state["number/Cal Scale Power"] * ref / self.state["sensor/Power"], 4)
        self._send({})

    def log_message(self, *a):
        pass


def serve():
    srv = http.server.HTTPServer(("127.0.0.1", 0), FakePlug)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_calibrate_sets_target_presses_button_and_reports_scale():
    FakePlug.log.clear()
    srv = serve()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    lines = []
    before, after = plug_cal.calibrate(base, "power", 41.0, "admin", "secret", out=lines.append)
    srv.shutdown()
    assert FakePlug.log == ["number/Cal Target Power/set?value=41.0", "button/Calibrate Power/press"]
    assert before == 1.0 and abs(after - 41.0 / 48.5) < 1e-3
    assert "power scale" in lines[0]


def test_read_counts_distinct_values_and_wrong_password_fails():
    srv = serve()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    lines = []
    seen = plug_cal.read_values(base, "admin", "secret", 0.0, step=0.0, out=lines.append)
    assert seen["Power"] == [48.5] and "Power" in "".join(lines)
    try:
        plug_cal.get_value(base, "sensor", "Power", "admin", "wrong")
        raised = False
    except Exception:
        raised = True
    srv.shutdown()
    assert raised
