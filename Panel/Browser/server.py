from __future__ import annotations

import base64, hashlib, hmac, http.cookies, json, os, platform, re, secrets, signal
import shutil, socket, struct, subprocess, threading, time, urllib.error
import urllib.parse, urllib.request, uuid
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("TERRARIA_ROOT", HERE.parent.parent)).resolve()
STATIC = HERE / "static"
WORLDS = ROOT / "Worlds"
PROFILES = ROOT / "Panel" / "server-profiles.json"
SECRET_FILE = HERE / "webpanel-secrets.json"
HOST = os.environ.get("PANEL_HOST", "127.0.0.1")
PORT = int(os.environ.get("PANEL_PORT", "8765"))
GAME_PORT = int(os.environ.get("GAME_PORT", "7777"))
REST_PORT = int(os.environ.get("REST_PORT", "7878"))
MODES = {"Классический": "normal", "Эксперт": "expert", "Мастер": "master", "Путешествие": "journey"}
LOGS = deque(maxlen=1000)
LOCK = threading.RLock()
PROC = None
STARTED = None
CPU_SAMPLE = None
TOKENS = {}
ATTEMPTS = {}

def log(text, level="info"):
    with LOCK:
        LOGS.append({"id": LOGS[-1]["id"] + 1 if LOGS else 1, "time": datetime.now().strftime("%H:%M:%S"), "level": level, "text": str(text)[:2500]})

def readjson(path, default):
    try: return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception: return default

def writejson(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def get_profiles():
    data = readjson(PROFILES, {})
    ps = data.get("Profiles", []) if isinstance(data, dict) else []
    ps = [p for p in ps if isinstance(p, dict) and p.get("id") and p.get("name") and p.get("config_dir")] if isinstance(ps, list) else []
    if not ps: ps = [{"id": "main", "name": "Основной сервер", "world": "", "config_dir": "tshock"}]; data = {"Profiles": ps, "SelectedId": "main"}
    cur = next((p for p in ps if p["id"] == data.get("SelectedId")), ps[0])
    return data, ps, cur

def cfgpath(profile):
    rel = Path(str(profile.get("config_dir", "tshock")))
    if rel.is_absolute() or ".." in rel.parts: raise ValueError("Небезопасный путь профиля.")
    path = (ROOT / rel).resolve()
    if ROOT not in path.parents and path != ROOT: raise ValueError("Путь профиля вне папки сервера.")
    return path / "config.json"

def config(profile):
    data = readjson(cfgpath(profile), {})
    if not isinstance(data, dict): raise ValueError("Некорректный config.json.")
    settings = data.get("Settings", data.get("settings", data))
    return data, settings if isinstance(settings, dict) else data

def prop(obj, *names, default=None):
    if not isinstance(obj, dict): return default
    lower = {str(k).casefold(): v for k, v in obj.items()}
    for name in names:
        if name.casefold() in lower: return lower[name.casefold()]
    return default

def unwrap(data):
    if isinstance(data, dict) and isinstance(data.get("response"), str):
        try:
            parsed = json.loads(data["response"])
            if isinstance(parsed, (dict, list)): return parsed
        except Exception: pass
    return data

def rows(data, *keys):
    data = unwrap(data)
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for key in (*keys, "response", "players", "users", "groups", "accounts"):
            val = prop(data, key)
            if isinstance(val, list): return val
            if isinstance(val, dict):
                nested = rows(val, *keys)
                if nested: return nested
    return []

def worldfile(name):
    name = str(name or "")
    if Path(name).name != name or not name.casefold().endswith(".wld"): raise ValueError("Выбери мир .wld из списка.")
    path = (WORLDS / name).resolve()
    if path.parent != WORLDS.resolve() or not path.is_file(): raise ValueError("Файл мира не найден в Worlds.")
    return path

def rest_token(profile):
    if profile["id"] in TOKENS: return TOKENS[profile["id"]]
    _, settings = config(profile)
    tokens = prop(settings, "ApplicationRestTokens", default={}) or {}
    if not isinstance(tokens, dict): tokens = {}
    value = next((str(k) for k, v in tokens.items() if str(prop(v, "Username", default="")).casefold() == "terrariapanel"), "")
    if not value and len(tokens) == 1: value = str(next(iter(tokens)))
    if not value: raise RuntimeError("В config.json профиля не настроен REST-токен панели TShock.")
    TOKENS[profile["id"]] = value
    return value

def api(path, params=None, profile=None):
    if profile is None: profile = get_profiles()[2]
    query = dict(params or {}); query["token"] = rest_token(profile)
    url = "http://127.0.0.1:" + str(REST_PORT) + "/" + path.lstrip("/") + "?" + urllib.parse.urlencode(query)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=5) as response:
            raw = response.read(1_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc: raise RuntimeError(exc.read(3000).decode("utf-8", "replace") or "TShock HTTP " + str(exc.code))
    data = json.loads(raw) if raw else {}
    if isinstance(data, dict) and str(data.get("status", "200")) not in ("200", "OK", "ok", "success", "Success"):
        raise RuntimeError(str(data.get("response") or data.get("error") or raw))
    return unwrap(data)

def command(text, profile=None):
    if profile is None: profile = get_profiles()[2]
    _, settings = config(profile); text = str(text or "").strip()
    if not text: raise ValueError("Команда пустая.")
    prefix = str(prop(settings, "CommandSpecifier", default="/") or "/")
    silent = str(prop(settings, "CommandSilentSpecifier", default=".") or ".")
    if not text.startswith(prefix) and not text.startswith(silent): text = prefix + text
    try: return api("v3/server/rawcmd", {"cmd": text}, profile)
    except RuntimeError as exc:
        if "404" in str(exc) or "not found" in str(exc).casefold(): return api("v2/server/rawcmd", {"cmd": text}, profile)
        raise

def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.35): return True
    except OSError: return False

def parse_mode(data):
    data = unwrap(data)
    if isinstance(data, dict) and prop(data, "response", default=None) is not None:
        data = prop(data, "response")
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    if isinstance(data, dict):
        try: mode = int(prop(data, "mode", default=-1))
        except Exception: mode = -1
        return {0: "Классический", 1: "Эксперт", 2: "Мастер", 3: "Путешествие"}.get(mode), str(prop(data, "name", "worldname", default="") or "")
    text = "\n".join(map(str, data if isinstance(data, (list, tuple)) else str(data or "").splitlines()))
    m = re.search(r"(?:режим|mode)\s*:\s*(\d+)", text, re.I); n = re.search(r"(?:название|name)\s*:\s*(.+)", text, re.I)
    return ({0: "Классический", 1: "Эксперт", 2: "Мастер", 3: "Путешествие"}.get(int(m.group(1))) if m else None), (n.group(1).strip() if n else "")

def world_header(path):
    with path.open("rb") as f:
        raw = f.read(4)
        if len(raw) != 4: raise ValueError("Файл мира обрезан.")
        version = struct.unpack("<i", raw)[0]
        if version < 140 or f.read(7) != b"relogic" or not f.read(1): raise ValueError("Заголовок мира не распознан.")
        if len(f.read(12)) != 12: raise ValueError("Файл мира обрезан.")
        raw = f.read(2)
        if len(raw) != 2: raise ValueError("Файл мира обрезан.")
        count = struct.unpack("<h", raw)[0]
        if not 1 <= count <= 128: raise ValueError("Некорректная таблица разделов мира.")
        pointers = []
        for _ in range(count):
            raw = f.read(4)
            if len(raw) != 4: raise ValueError("Файл мира обрезан.")
            pointers.append(struct.unpack("<i", raw)[0])
        if pointers[0] <= f.tell() or pointers[0] >= path.stat().st_size: raise ValueError("Некорректный заголовок мира.")
        f.seek(pointers[0])
        def read_string():
            length = 0; shift = 0
            while shift < 35:
                raw = f.read(1)
                if not raw: raise ValueError("Заголовок мира обрезан.")
                length |= (raw[0] & 127) << shift
                if not raw[0] & 128: break
                shift += 7
            if length > 1048576: raise ValueError("Поле заголовка слишком длинное.")
            return f.read(length).decode("utf-8", "replace")
        name = read_string()
        if version >= 179:
            if version == 179: f.read(4)
            else: read_string()
            f.read(8)
        if version >= 181: f.read(16)
        f.read(28)
        mode_offset = f.tell() if version >= 209 else None
        mode = struct.unpack("<i", f.read(4))[0] if mode_offset is not None else None
    return name, {0: "Классический", 1: "Эксперт", 2: "Мастер", 3: "Путешествие"}.get(mode), mode_offset

def get_player(obj):
    if not isinstance(obj, dict): return {"name": str(obj), "account": "—", "group": "—", "position": "нет данных"}
    pos = prop(obj, "position", "pos", default={}); x = prop(pos, "x", "X") if isinstance(pos, dict) else None; y = prop(pos, "y", "Y") if isinstance(pos, dict) else None
    if isinstance(pos, (list, tuple)) and len(pos) > 1: x, y = pos[:2]
    x = x if x is not None else prop(obj, "x", "X"); y = y if y is not None else prop(obj, "y", "Y")
    try:
        x = float(x); y = float(y)
        if abs(x) > 9000 or abs(y) > 3000: x /= 16; y /= 16
        position = str(round(x)) + " / " + str(round(y))
    except Exception: position = "нет данных"
    group = prop(obj, "group", "groupname", default="—")
    if isinstance(group, dict): group = prop(group, "name", default="—")
    return {"name": str(prop(obj, "nickname", "name", "player", "character", default="—")), "account": str(prop(obj, "username", "user", "account", default="—") or "—"), "group": str(group or "—"), "position": position}

def get_metrics():
    global CPU_SAMPLE
    result = {"server_memory_mb": None, "server_cpu_percent": None, "system_memory_percent": None, "system_load": None}
    with LOCK: proc = PROC
    if proc is None or proc.poll() is not None: return result
    try:
        stat = Path("/proc/" + str(proc.pid) + "/statm")
        if stat.exists():
            result["server_memory_mb"] = round(int(stat.read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576, 1)
            result["system_load"] = round(os.getloadavg()[0], 2)
            proc_stat = Path("/proc/" + str(proc.pid) + "/stat").read_text()
            proc_fields = proc_stat[proc_stat.rfind(")") + 2:].split()
            proc_ticks = int(proc_fields[11]) + int(proc_fields[12])
            now = time.monotonic()
            if CPU_SAMPLE:
                elapsed = now - CPU_SAMPLE[0]
                if elapsed > 0:
                    hz = os.sysconf("SC_CLK_TCK"); cores = max(1, os.cpu_count() or 1)
                    result["server_cpu_percent"] = round(max(0, (proc_ticks - CPU_SAMPLE[1]) / hz / elapsed / cores * 100), 1)
            CPU_SAMPLE = (now, proc_ticks)
            mem = Path("/proc/meminfo").read_text(); total = re.search(r"MemTotal:\s+(\d+)", mem); avail = re.search(r"MemAvailable:\s+(\d+)", mem)
            if total and avail: result["system_memory_percent"] = round((int(total.group(1)) - int(avail.group(1))) * 100 / int(total.group(1)), 1)
        elif os.name == "nt":
            try:
                import psutil
                result["server_memory_mb"] = round(psutil.Process(proc.pid).memory_info().rss / 1048576, 1)
                result["server_cpu_percent"] = round(psutil.Process(proc.pid).cpu_percent(interval=.05), 1)
                result["system_memory_percent"] = round(psutil.virtual_memory().percent, 1)
            except Exception: pass
    except Exception: pass
    return result

def state():
    _, ps, cur = get_profiles(); _, settings = config(cur); world = str(cur.get("world") or ""); players = []; running = False; connected = False; active_world = world; mode = None; error = ""
    worlds = []
    if WORLDS.exists():
        for f in WORLDS.glob("*.wld"):
            try: worlds.append({"name": f.name, "size_mb": round(f.stat().st_size / 1048576, 1), "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M")})
            except OSError: pass
    try:
        status = api("v2/server/status", {"players": "true"}, cur); running = connected = True
        items = rows(status, "players", "activePlayers")
        if not items:
            try: items = rows(api("v2/players/list", profile=cur), "players")
            except Exception: pass
        players = [get_player(x) for x in items]
        active_world = str(prop(status, "world", "worldname", "worldName", default=world) or world)
        if isinstance(prop(status, "world"), dict): active_world = str(prop(prop(status, "world"), "name", default=world))
        try: mode, name = parse_mode(command("worldinfo", cur)); active_world = name or active_world
        except Exception: pass
    except Exception as exc:
        error = str(exc); running = port_open(GAME_PORT)
        if not running:
            try: active_world, mode, _ = world_header(worldfile(world))
            except Exception: pass
    with LOCK:
        own = PROC is not None and PROC.poll() is None; up = int(time.time() - STARTED) if own and STARTED else None; log_id = LOGS[-1]["id"] if LOGS else 0
    return {"running": running or own, "api_connected": connected, "api_error": error, "players": players, "world": {"name": active_world, "mode": mode}, "worlds": worlds, "profiles": [{"id": p["id"], "name": p["name"], "world": p.get("world", "")} for p in ps], "selected_profile": cur["id"], "settings": {"password": str(prop(settings, "ServerPassword", default="") or ""), "max_players": prop(settings, "MaxSlots", default=8), "autosave": prop(settings, "AutoSave", default=True), "world": world}, "game_address": os.environ.get("GAME_PUBLIC_ADDRESS", ""), "metrics": get_metrics(), "uptime_seconds": up, "logs_last_id": log_id}

def admin_data(p):
    users = rows(api("v2/users/list", profile=p), "users", "accounts"); groups = rows(api("v2/groups/list", profile=p), "groups"); details = []
    for g in groups:
        name = str(prop(g, "name", "groupname", "group", default=g if isinstance(g, str) else "") or "").strip()
        if not name: continue
        try:
            d = unwrap(api("v2/groups/read", {"group": name}, p))
            if isinstance(d, dict) and isinstance(prop(d, "group"), dict): d = prop(d, "group")
            details.append({"name": name, "parent": prop(d, "parent", "parentgroup", default=""), "permissions": prop(d, "permissions", default=[]) or [], "negatedpermissions": prop(d, "negatedpermissions", default=[]) or []})
        except Exception as e: details.append({"name": name, "error": str(e), "permissions": []})
    return {"users": users, "groups": details}

def is_running():
    with LOCK:
        if PROC is not None and PROC.poll() is None: return True
    return port_open(GAME_PORT)

def start_server(body):
    global PROC, STARTED
    if is_running(): raise ValueError("Сервер уже работает.")
    data, ps, cur = get_profiles(); profile = next((p for p in ps if p["id"] == str(body.get("profile_id") or cur["id"])), None)
    if profile is None: raise ValueError("Профиль не найден.")
    world = worldfile(str(body.get("world") or profile.get("world") or "")); slots = int(body.get("max_players", 8))
    if not 1 <= slots <= 255: raise ValueError("Число игроков должно быть от 1 до 255.")
    cfg, settings = config(profile); settings["ServerPassword"] = str(body.get("password") or "")[:128]; settings["MaxSlots"] = slots; settings["AutoSave"] = bool(body.get("autosave", True))
    writejson(cfgpath(profile), cfg); profile["world"] = world.name; data["Profiles"] = ps; data["SelectedId"] = profile["id"]; writejson(PROFILES, data)
    dll = ROOT / "TShock.Server.dll"; exe = ROOT / "TShock.Server.exe"; app = ROOT / "TShock.Server"; runtime = ROOT / "dotnet"; env = os.environ.copy()
    if runtime.is_dir(): env["DOTNET_ROOT"] = str(runtime); env["PATH"] = str(runtime) + os.pathsep + env.get("PATH", "")
    if dll.is_file(): args = [shutil.which("dotnet") or str(runtime / ("dotnet.exe" if os.name == "nt" else "dotnet")), str(dll)]
    elif os.name == "nt" and exe.is_file(): args = [str(exe)]
    elif app.is_file(): args = [str(app)]
    elif exe.is_file(): args = [shutil.which("dotnet") or "dotnet", str(exe)]
    else: raise FileNotFoundError("Не найден TShock.Server.dll или TShock.Server.exe.")
    args += ["-configpath", str(cfgpath(profile).parent), "-world", str(world), "-port", str(GAME_PORT), "-maxplayers", str(slots)]
    kw = {"cwd": str(ROOT), "env": env, "stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1}
    if os.name == "nt": kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else: kw["start_new_session"] = True
    with LOCK: PROC = subprocess.Popen(args, **kw); STARTED = time.time(); proc = PROC
    log("Запускаю Terraria/TShock: " + world.name)
    def reader():
        try:
            for line in proc.stdout: log(line.rstrip(), "error" if "error" in line.casefold() or "exception" in line.casefold() else "info")
        except Exception as e: log("Ошибка журнала: " + str(e), "error")
    def watch():
        global PROC
        code = proc.wait()
        with LOCK:
            if PROC is proc: PROC = None
        log("Сервер завершил работу, код " + str(code))
    threading.Thread(target=reader, daemon=True).start(); threading.Thread(target=watch, daemon=True).start()
    return {"ok": True, "message": "Сервер запускается."}

def stop_server():
    with LOCK: proc = PROC
    if proc is None and not port_open(GAME_PORT): return {"ok": True, "message": "Сервер уже выключен."}
    try: api("v2/server/off", {"confirm": "true", "nosave": "false", "message": "Server shutting down"})
    except Exception:
        if proc and proc.poll() is None and proc.stdin:
            try: proc.stdin.write("exit\n"); proc.stdin.flush()
            except OSError: pass
    log("Запрошено выключение с сохранением.", "warn")
    return {"ok": True, "message": "Выключение отправлено. Дождись сохранения мира."}

def secret_config():
    password = os.environ.get("PANEL_PASSWORD"); data = readjson(SECRET_FILE, {})
    if not isinstance(data, dict) or not data.get("key"):
        password = password or secrets.token_urlsafe(18); salt = secrets.token_bytes(16)
        data = {"salt": base64.b64encode(salt).decode(), "hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 250000).hex(), "key": secrets.token_urlsafe(40)}
        writejson(SECRET_FILE, data)
        try: os.chmod(SECRET_FILE, 0o600)
        except OSError: pass
        if not os.environ.get("PANEL_PASSWORD"): print("\nПАРОЛЬ ПАНЕЛИ (сохрани, показывается один раз):\n" + password + "\n", flush=True)
    elif password:
        salt = base64.b64decode(data["salt"]); data["hash"] = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 250000).hex(); writejson(SECRET_FILE, data)
    return data

AUTH = secret_config()
def pass_ok(value):
    try: return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", value.encode(), base64.b64decode(AUTH["salt"]), 250000).hex(), AUTH["hash"])
    except Exception: return False
def new_cookie():
    exp = str(int(time.time()) + 43200); mac = hmac.new(AUTH["key"].encode(), exp.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(exp.encode() + b"." + mac).decode().rstrip("=")
def check_cookie(value):
    try:
        exp, sig = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).split(b".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, hmac.new(AUTH["key"].encode(), exp, hashlib.sha256).digest())
    except Exception: return False

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args): log(self.client_address[0] + " " + fmt % args, "http")
    def send(self, status, body, kind="application/json; charset=utf-8", headers=()):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for k, v in headers: self.send_header(k, v)
        self.end_headers(); self.wfile.write(raw)
    def body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size < 0 or size > 1000000: raise ValueError("Запрос слишком большой.")
        obj = json.loads(self.rfile.read(size).decode() or "{}")
        if not isinstance(obj, dict): raise ValueError("Некорректный запрос.")
        return obj
    def authed(self):
        try:
            c = http.cookies.SimpleCookie(); c.load(self.headers.get("Cookie", "")); m = c.get("terraria_session")
            return bool(m and check_cookie(m.value))
        except Exception: return False
    def origin_ok(self):
        origin = self.headers.get("Origin")
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").casefold()
        return not origin or urllib.parse.urlsplit(origin).netloc.casefold() == host
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if path in files:
            name, kind = files[path]
            try: self.send(200, (STATIC / name).read_bytes(), kind)
            except OSError: self.send(404, b"Not found", "text/plain; charset=utf-8")
            return
        if path == "/api/session": self.send(200, {"authenticated": self.authed()}); return
        if not path.startswith("/api/"): self.send(404, {"error": "Страница не найдена."}); return
        if not self.authed(): self.send(401, {"error": "Войди в панель."}); return
        try:
            if path == "/api/state": self.send(200, state())
            elif path == "/api/admin": self.send(200, admin_data(get_profiles()[2]))
            elif path == "/api/logs":
                since = int(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("since", ["0"])[0])
                with LOCK: items = list(LOGS)
                self.send(200, {"entries": items[-100:] if since <= 0 else [x for x in items if x["id"] > since], "last_id": items[-1]["id"] if items else 0})
            else: self.send(404, {"error": "Неизвестный запрос."})
        except Exception as e: self.send(500, {"error": str(e)})
    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if not self.origin_ok(): self.send(403, {"error": "Источник запроса не совпадает с панелью."}); return
        try: body = self.body()
        except Exception as e: self.send(400, {"error": str(e)}); return
        if path == "/api/login":
            ip = self.client_address[0]; now = time.time(); attempts = ATTEMPTS.setdefault(ip, deque())
            while attempts and now - attempts[0] > 60: attempts.popleft()
            if len(attempts) >= 6: self.send(429, {"error": "Подожди минуту перед новой попыткой."}); return
            attempts.append(now)
            if not pass_ok(str(body.get("password") or "")): self.send(401, {"error": "Пароль не подошёл."}); return
            ATTEMPTS.pop(ip, None); cookie = "terraria_session=" + new_cookie() + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200"
            if self.headers.get("X-Forwarded-Proto", "").casefold() == "https": cookie += "; Secure"
            self.send(200, {"ok": True}, headers=[("Set-Cookie", cookie)]); return
        if path == "/api/logout": self.send(200, {"ok": True}, headers=[("Set-Cookie", "terraria_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")]); return
        if not self.authed(): self.send(401, {"error": "Войди в панель."}); return
        try:
            data, ps, cur = get_profiles()
            if path == "/api/start": out = start_server(body)
            elif path == "/api/stop": out = stop_server()
            elif path == "/api/command":
                text = str(body.get("command") or ""); out = {"ok": True, "response": command(text, cur)}; log("> " + text, "command")
            elif path == "/api/chat":
                text = str(body.get("message") or "").strip()
                if not text or len(text) > 200: raise ValueError("Сообщение должно быть до 200 символов.")
                out = {"ok": True, "response": api("v2/server/broadcast", {"msg": text}, cur)}; log("Сообщение в чат: " + text, "command")
            elif path == "/api/kick":
                name = str(body.get("player") or "").strip()
                if not name: raise ValueError("Выбери игрока.")
                out = {"ok": True, "response": api("v2/players/kick", {"player": name}, cur)}; log("Кик игрока " + name, "warn")
            elif path == "/api/settings":
                if is_running(): raise ValueError("Останови сервер перед сменой настроек запуска.")
                profile = next((p for p in ps if p["id"] == str(body.get("profile_id") or cur["id"])), None)
                if profile is None: raise ValueError("Профиль не найден.")
                world = worldfile(str(body.get("world") or "")); slots = int(body.get("max_players", 8))
                if not 1 <= slots <= 255: raise ValueError("Число игроков должно быть 1–255.")
                cfg, s = config(profile); s["ServerPassword"] = str(body.get("password") or "")[:128]; s["MaxSlots"] = slots; s["AutoSave"] = bool(body.get("autosave", True)); profile["world"] = world.name
                writejson(cfgpath(profile), cfg); data["Profiles"] = ps; data["SelectedId"] = profile["id"]; writejson(PROFILES, data); out = {"ok": True, "message": "Настройки сохранены."}
            elif path == "/api/mode":
                label = str(body.get("mode") or "")
                if label not in MODES: raise ValueError("Выбери режим мира.")
                world = worldfile(str(cur.get("world") or "")); folder = WORLDS / "Backups"; folder.mkdir(parents=True, exist_ok=True); stamp = time.strftime("%Y%m%d-%H%M%S")
                if port_open(GAME_PORT):
                    command("save", cur)
                    backup = folder / (world.stem + ".before-mode-" + stamp + ".wld")
                    shutil.copy2(world, backup)
                    companion = world.with_suffix(".twld")
                    if companion.is_file(): shutil.copy2(companion, backup.with_suffix(".twld"))
                    result = command("worldmode " + MODES[label], cur)
                    command("save", cur)
                    backups = [backup.name] + ([backup.with_suffix(".twld").name] if backup.with_suffix(".twld").exists() else [])
                else:
                    world_name, old_mode, offset = world_header(world)
                    if old_mode == label: raise ValueError("У этого мира уже такой режим.")
                    if offset is None: raise ValueError("Этот старый формат нельзя изменить безопасно. Запусти мир и попробуй снова.")
                    backup = folder / (world.stem + ".before-mode-" + stamp + ".wld"); shutil.copy2(world, backup)
                    companion = world.with_suffix(".twld")
                    if companion.is_file(): shutil.copy2(companion, backup.with_suffix(".twld"))
                    raw = bytearray(world.read_bytes()); mode_code = list(MODES).index(label); raw[offset:offset + 4] = struct.pack("<i", mode_code)
                    tmp = world.with_name(world.name + ".mode.tmp"); replaced = False
                    try:
                        tmp.write_bytes(raw); os.replace(tmp, world); replaced = True
                        if world_header(world)[1] != label: raise ValueError("Проверка файла после смены режима не совпала.")
                    except Exception:
                        if replaced: shutil.copy2(backup, world)
                        raise
                    finally:
                        if tmp.exists(): tmp.unlink()
                    result = "Режим файла мира изменён."
                    backups = [backup.name] + ([backup.with_suffix(".twld").name] if backup.with_suffix(".twld").exists() else [])
                out = {"ok": True, "response": result, "backups": backups}; log("Смена режима: " + label, "warn")
            elif path == "/api/profile/select":
                if is_running(): raise ValueError("Сначала останови сервер.")
                target = next((p for p in ps if p["id"] == str(body.get("id") or "")), None)
                if target is None: raise ValueError("Профиль не найден.")
                config(target); data["SelectedId"] = target["id"]; writejson(PROFILES, data); out = {"ok": True}
            elif path == "/api/profile/create":
                if is_running(): raise ValueError("Сначала останови сервер.")
                name = str(body.get("name") or "").strip()
                if not name or len(name) > 60 or any(p["name"].casefold() == name.casefold() for p in ps): raise ValueError("Задай уникальное название профиля.")
                pid = uuid.uuid4().hex[:12]; rel = Path("ServerProfiles") / pid / "tshock"; dest = ROOT / rel; dest.mkdir(parents=True, exist_ok=True); source = cfgpath(cur).parent
                for fn in ("config.json", "sscconfig.json", "motd.txt", "rules.txt", "whitelist.txt"):
                    if (source / fn).is_file(): shutil.copy2(source / fn, dest / fn)
                cfg, s = config({"id": pid, "name": name, "config_dir": str(rel)}); s["ServerPassword"] = secrets.token_urlsafe(9); writejson(dest / "config.json", cfg)
                world = str(cur.get("world") or "")
                try:
                    old = worldfile(world); safe = re.sub(r'[<>:"/\\|?*]+', "-", name).strip(" .-") or "server"; stem = old.stem + " - " + safe; candidate = stem; n = 2
                    while (WORLDS / (candidate + ".wld")).exists(): candidate = stem + " (" + str(n) + ")"; n += 1
                    shutil.copy2(old, WORLDS / (candidate + ".wld"))
                    if old.with_suffix(".twld").exists(): shutil.copy2(old.with_suffix(".twld"), WORLDS / (candidate + ".twld"))
                    world = candidate + ".wld"
                except Exception: pass
                ps.append({"id": pid, "name": name, "world": world, "config_dir": str(rel)}); data["Profiles"] = ps; data["SelectedId"] = pid; writejson(PROFILES, data); out = {"ok": True}
            elif path == "/api/profile/rename":
                if is_running(): raise ValueError("Сначала останови сервер.")
                p = next((x for x in ps if x["id"] == str(body.get("id") or "")), None); name = str(body.get("name") or "").strip()
                if p is None or not name or len(name) > 60 or any(x is not p and x["name"].casefold() == name.casefold() for x in ps): raise ValueError("Проверь название профиля.")
                p["name"] = name; writejson(PROFILES, data); out = {"ok": True}
            elif path == "/api/profile/remove":
                if is_running() or len(ps) < 2: raise ValueError("Останови сервер; последний профиль убрать нельзя.")
                p = next((x for x in ps if x["id"] == str(body.get("id") or "")), None)
                if p is None: raise ValueError("Профиль не найден.")
                ps.remove(p); data["Profiles"] = ps
                if data.get("SelectedId") == p["id"]: data["SelectedId"] = ps[0]["id"]
                writejson(PROFILES, data); out = {"ok": True}
            elif path == "/api/account/group":
                user = str(body.get("user") or "").strip(); group = str(body.get("group") or "").strip()
                if not user or not group: raise ValueError("Выбери аккаунт и группу.")
                out = {"ok": True, "response": api("v2/users/update", {"user": user, "type": "name", "group": group}, cur)}; log("Группа " + group + " назначена " + user, "warn")
            elif path == "/api/group/personal":
                user = str(body.get("user") or "").strip(); parent = str(body.get("parent") or "default").strip()
                if not user: raise ValueError("Выбери аккаунт.")
                group_rows = rows(api("v2/groups/list", profile=cur), "groups")
                existing = {str(prop(g, "name", "groupname", "group", default=g if isinstance(g, str) else "")).casefold() for g in group_rows}
                base = "panel_" + re.sub(r"[^a-z0-9_]", "_", user.casefold()).strip("_")[:20]
                base = base.rstrip("_") or "panel_user"; group = base; suffix = 2
                while group.casefold() in existing: group = base[:27] + "_" + str(suffix); suffix += 1
                api("v2/groups/create", {"group": group, "parent": parent}, cur)
                api("v2/users/update", {"user": user, "type": "name", "group": group}, cur)
                out = {"ok": True, "message": "Для " + user + " создана личная группа " + group + "."}; log("Создана личная группа " + group + " для " + user, "warn")
            elif path == "/api/account/create":
                user = str(body.get("user") or "").strip(); password = str(body.get("password") or ""); group = str(body.get("group") or "default")
                if not user or not password: raise ValueError("Для создания аккаунта нужны имя и пароль.")
                out = {"ok": True, "response": api("v2/users/create", {"user": user, "group": group, "password": password}, cur)}; log("Создан аккаунт " + user + " (" + group + ")", "warn")
            elif path == "/api/group/permission":
                group = str(body.get("group") or "").strip(); mode = str(body.get("mode") or ""); perms = body.get("permissions")
                if not group or mode not in ("allow", "deny", "clear") or not isinstance(perms, list) or not perms: raise ValueError("Выбери группу, право и действие.")
                d = unwrap(api("v2/groups/read", {"group": group}, cur))
                if isinstance(d, dict) and isinstance(prop(d, "group"), dict): d = prop(d, "group")
                direct = prop(d, "permissions", default=[]) or []; denied = prop(d, "negatedpermissions", default=[]) or []
                if isinstance(direct, str): direct = [x.strip() for x in direct.split(",") if x.strip() and not x.strip().startswith("!")]
                if isinstance(denied, str): denied = [x.strip().lstrip("!") for x in denied.split(",") if x.strip()]
                direct = [str(x).strip() for x in direct]; denied = [str(x).strip().lstrip("!") for x in denied]; clean = []
                for raw in perms:
                    item = str(raw).strip().lstrip("!").strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.*-]+", item): raise ValueError("Недопустимое имя права.")
                    clean.append(item)
                for item in clean:
                    direct = [x for x in direct if x.casefold() != item.casefold()]; denied = [x for x in denied if x.casefold() != item.casefold()]
                    if mode == "allow": direct.append(item)
                    elif mode == "deny": denied.append(item)
                out = {"ok": True, "response": api("v2/groups/update", {"group": group, "permissions": ",".join(direct + ["!" + x for x in denied])}, cur)}; log("Изменены права группы " + group, "warn")
            else: self.send(404, {"error": "Неизвестное действие."}); return
            self.send(200, out)
        except Exception as e: log("Ошибка панели: " + str(e), "error"); self.send(400, {"error": str(e)})

def main():
    if not ROOT.is_dir(): raise SystemExit("Папка Terraria не найдена: " + str(ROOT) + ". Задай TERRARIA_ROOT.")
    server = ThreadingHTTPServer((HOST, PORT), Handler); server.daemon_threads = True
    log("Веб-панель: http://" + HOST + ":" + str(PORT)); log("Папка сервера: " + str(ROOT))
    print("Terraria Web Panel: http://" + HOST + ":" + str(PORT), flush=True); print("Серверные файлы: " + str(ROOT), flush=True)
    if HOST not in ("127.0.0.1", "localhost", "::1"): log("Внешний интерфейс включён: для интернета обязателен HTTPS-прокси.", "warn")
    def graceful_shutdown(signum, frame):
        log("Останавливаю игровую сессию перед закрытием веб-панели.", "warn")
        try: stop_server()
        except Exception as exc: log("Не удалось отправить штатную команду остановки: " + str(exc), "error")
        deadline = time.time() + 45
        while time.time() < deadline:
            with LOCK: active = PROC is not None and PROC.poll() is None
            if not active: break
            time.sleep(.5)
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, graceful_shutdown)
    try: server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt: print("\nВеб-панель закрыта; Terraria-сервер не выключался.", flush=True)
    finally: server.server_close()

if __name__ == "__main__": main()
