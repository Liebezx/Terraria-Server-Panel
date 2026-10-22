from __future__ import annotations
import ctypes
# Set distinct Windows App ID so Taskbar groups this as its own dedicated program
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Terraria.ServerManager.Panel.v2")
except Exception:
    pass
import json
import logging
import os
import io
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
from pathlib import Path
import webview

# --- Paths & Setup ---
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "TShock.Server.exe").is_file():
        ROOT = exe_dir
        PANEL_DIR = ROOT / "Panel"
    elif (exe_dir.parent / "TShock.Server.exe").is_file():
        PANEL_DIR = exe_dir
        ROOT = PANEL_DIR.parent
    else:
        PANEL_DIR = exe_dir
        ROOT = PANEL_DIR.parent
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "ui").is_dir():
        UI_DIR = Path(meipass) / "ui"
    elif (PANEL_DIR / "ui").is_dir():
        UI_DIR = PANEL_DIR / "ui"
    else:
        UI_DIR = ROOT / "Panel" / "ui"
else:
    ROOT = Path(__file__).resolve().parent.parent
    PANEL_DIR = ROOT / "Panel"
    UI_DIR = PANEL_DIR / "ui"
LOG_FILE = PANEL_DIR / "panel_error.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

def log_error(msg: str, exc: Exception | None = None):
    if exc:
        logging.error(f"{msg}: {exc}", exc_info=True)
    else:
        logging.error(msg)

sys.excepthook = lambda t, v, tb: logging.critical("Uncaught exception", exc_info=(t, v, tb))

# Constants
CONFIG = ROOT / "tshock" / "config.json"
SETUP = ROOT / "tshock" / "setup-code.txt"
SERVER = ROOT / "TShock.Server.exe"
WORLDS_DIR = ROOT / "Worlds"
TERRARIA_USER_WORLDS_DIR = Path.home() / "Documents" / "My Games" / "Terraria" / "Worlds"
PANEL_STATE = PANEL_DIR / "panel-settings.json"
PROFILES_FILE = PANEL_DIR / "server-profiles.json"
PROFILES_DIR = ROOT / "ServerProfiles"

WORLD_MODE_NAMES = {0: "Классический", 1: "Эксперт", 2: "Мастер", 3: "Путешествие"}
WORLD_MODE_COMMANDS = {"Классический": "normal", "Эксперт": "expert", "Мастер": "master", "Путешествие": "journey"}
GAME_PORT = 7777
REST_PORT = 7878

SECRET_SEEDS_INFO = {
    "tooeasy": {
        "title": "Секретный сид: Tooeasy (Мгновенный Хардмод)",
        "badge": "ХАРДМОД СО СТАРТА",
        "color": "amber",
        "desc": "Мир начинает игру сразу по законам Хардмода с первой секунды. Спавнятся хардмодные враги, убийство Стены Плоти не требуется.",
        "force_hardmode": True
    },
    "too easy": {
        "title": "Секретный сид: Too Easy (Мгновенный Хардмод)",
        "badge": "ХАРДМОД СО СТАРТА",
        "color": "amber",
        "desc": "Мир начинает игру сразу по законам Хардмода с первой секунды. Спавнятся хардмодные враги, убийство Стены Плоти не требуется.",
        "force_hardmode": True
    },
    "pumpkinseason": {
        "title": "Модификатор: Сезон Тыкв (Pumpkin Season)",
        "badge": "СЕЗОН ТЫКВ",
        "color": "orange",
        "desc": "По всему миру естественно произрастают тыквы, праздничная атмосфера.",
        "force_hardmode": False
    },
    "pumpkin season": {
        "title": "Модификатор: Сезон Тыкв (Pumpkin Season)",
        "badge": "СЕЗОН ТЫКВ",
        "color": "orange",
        "desc": "По всему миру естественно произрастают тыквы, праздничная атмосфера.",
        "force_hardmode": False
    },
    "05162020": {
        "title": "Секретный сид: Drunk World (Пьяный мир)",
        "badge": "ПЬЯНЫЙ МИР (ОБА ЗЛА)",
        "color": "purple",
        "desc": "Сгенерированы оба зла одновременно (Искажение и Багрянец), оба вида руд, скрытый данж под деревом.",
        "force_hardmode": False
    },
    "5162020": {
        "title": "Секретный сид: Drunk World (Пьяный мир)",
        "badge": "ПЬЯНЫЙ МИР (ОБА ЗЛА)",
        "color": "purple",
        "desc": "Сгенерированы оба зла одновременно (Искажение и Багрянец), оба вида руд, скрытый данж под деревом.",
        "force_hardmode": False
    },
    "for the worthy": {
        "title": "Секретный сид: For the Worthy (Легендарная сложность)",
        "badge": "FOR THE WORTHY (ХАРДКОР)",
        "color": "red",
        "desc": "Экстремальный уровень сложности, взрывные кролики, смертоносные ловушки и колоссальный урон боссов.",
        "force_hardmode": False
    },
    "get fixed boi": {
        "title": "Секретный сид: Zenith / Get Fixed Boi (Всё и сразу)",
        "badge": "ЗЕНИТ (СУПЕР-СИД)",
        "color": "rainbow",
        "desc": "Ультимативный мир — безумное сочетание всех секретных сидов одновременно.",
        "force_hardmode": False
    },
    "zenith": {
        "title": "Секретный сид: Zenith / Get Fixed Boi (Всё и сразу)",
        "badge": "ЗЕНИТ (СУПЕР-СИД)",
        "color": "rainbow",
        "desc": "Ультимативный мир — безумное сочетание всех секретных сидов одновременно.",
        "force_hardmode": False
    },
    "dont dig up": {
        "title": "Секретный сид: Don't Dig Up (Мир снизу вверх)",
        "badge": "НЕ КОПАЙ ВВЕРХ (АД)",
        "color": "amber",
        "desc": "Начало в Преисподней (Аду), путь лежит наверх к смертоносной поверхности.",
        "force_hardmode": False
    },
    "not the bees": {
        "title": "Секретный сид: Not the Bees (Пчелиный мир)",
        "badge": "ТОЛЬКО НЕ ПЧЁЛЫ",
        "color": "yellow",
        "desc": "Весь мир состоит из джунглей, мёда, ульев и пчёл.",
        "force_hardmode": False
    },
    "celebrationmk10": {
        "title": "Секретный сид: Celebrationmk10 (Праздничный мир)",
        "badge": "ПРАЗДНИК MK10",
        "color": "pink",
        "desc": "Праздничный мир, редкий лут с повышенным шансом, стартовые NPC на пляже.",
        "force_hardmode": False
    },
    "the constant": {
        "title": "Секретный сид: The Constant (Don't Starve)",
        "badge": "THE CONSTANT (ГОЛОД)",
        "color": "dim",
        "desc": "Коллаборация Don't Starve — механика голода, смертельная темнота и винтажный фильтр.",
        "force_hardmode": False
    },
    "no traps": {
        "title": "Секретный сид: No Traps (Мир с ловушками)",
        "badge": "NO TRAPS (ЛОВУШКИ)",
        "color": "red",
        "desc": "Ироничный сид — мир переполнен смертоносными ловушками всех видов.",
        "force_hardmode": False
    },
    "skyblock": {
        "title": "Секретный сид: Skyblock (Скайблок)",
        "badge": "СКАЙБЛОК (ОСТРОВА)",
        "color": "cyan",
        "desc": "Ограниченный старт на парящих островах над бездной.",
        "force_hardmode": False
    },
    "toadstool": {
        "title": "Модификатор: Грибная поверхность (Toadstool)",
        "badge": "ГРИБНОЙ МИР",
        "color": "cyan",
        "desc": "Светящиеся грибные биомы прямо на поверхности.",
        "force_hardmode": False
    },
    "fishmox": {
        "title": "Модификатор: Очищенное зло (Fishmox)",
        "badge": "ОЧИЩЕННОЕ ЗЛО",
        "color": "green",
        "desc": "Блоки зла очищены при создании, механики заражения ждут хардмода.",
        "force_hardmode": False
    },
    "waterpark": {
        "title": "Модификатор: Аквапарк (Waterpark)",
        "badge": "АКВАПАРК",
        "color": "blue",
        "desc": "Затопленный мир с огромными океанами и водными просторами.",
        "force_hardmode": False
    },
    "purify this": {
        "title": "Модификатор: Тотальное заражение (Purify This)",
        "badge": "ПОЛНОЕ ЗАРАЖЕНИЕ",
        "color": "purple",
        "desc": "Весь мир изначально заражён Искажением или Багрянцем.",
        "force_hardmode": False
    },
    "does that sparkle": {
        "title": "Модификатор: Освящение на спавне (Does That Sparkle)",
        "badge": "ОСВЯЩЕНИЕ НА СПАВНЕ",
        "color": "pink",
        "desc": "Освящённый биом (Hallow) генерируется прямо на поверхности при спавне.",
        "force_hardmode": False
    },
    "night of the living dead": {
        "title": "Модификатор: Ночь живых мертвецов",
        "badge": "КРОВАВАЯ ЛУНА",
        "color": "red",
        "desc": "Вечная Кровавая Луна и атмосфера кладбища со старта.",
        "force_hardmode": False
    },
    "more traps please": {
        "title": "Модификатор: Без ловушек (More Traps Please)",
        "badge": "БЕЗ ЛОВУШЕК",
        "color": "green",
        "desc": "Естественные ловушки удалены из мира.",
        "force_hardmode": False
    },
    "beam me up": {
        "title": "Модификатор: Телепорты (Beam Me Up)",
        "badge": "ТЕЛЕПОРТЫ",
        "color": "cyan",
        "desc": "Случайные телепорты разбросаны по всему миру.",
        "force_hardmode": False
    },
    "how did i get here": {
        "title": "Модификатор: Случайный спавн (How Did I Get Here)",
        "badge": "СЛУЧАЙНЫЙ СПАВН",
        "color": "yellow",
        "desc": "Случайная точка появления игрока в мире.",
        "force_hardmode": False
    },
    "monochrome": {
        "title": "Модификатор: Монохром (Monochrome)",
        "badge": "ЧЁРНО-БЕЛЫЙ",
        "color": "dim",
        "desc": "Чёрно-белый ретро-фильтр для всего мира.",
        "force_hardmode": False
    },
    "rainbow road": {
        "title": "Модификатор: Радужная дорога (Rainbow Road)",
        "badge": "РАДУЖНЫЕ БЛОКИ",
        "color": "rainbow",
        "desc": "По всему миру разбросаны яркие светящиеся радужные блоки.",
        "force_hardmode": False
    }
}

def analyze_world_seed(seed_str: str, meta: dict | None = None) -> dict:
    meta = meta or {}
    detected = []
    forces_hardmode = False

    raw_seed = str(seed_str or "").strip()
    # Normalize tokens: split by pipe '|' or analyze whole string
    tokens = [t.strip().lower() for t in raw_seed.split("|") if t.strip()]
    if not tokens and raw_seed:
        tokens = [raw_seed.lower()]

    # Match tokens against known secret seeds
    for tok in tokens:
        clean_tok = tok.replace(" ", "").replace("_", "").replace("-", "").replace("!", "")
        matched = False
        for key, info in SECRET_SEEDS_INFO.items():
            clean_key = key.replace(" ", "").replace("_", "").replace("-", "").replace("!", "")
            if clean_tok == clean_key:
                if not any(d.get("title") == info["title"] for d in detected):
                    detected.append(dict(info, id=key))
                if info.get("force_hardmode"):
                    forces_hardmode = True
                matched = True
                break
        if not matched:
            for key, info in SECRET_SEEDS_INFO.items():
                clean_key = key.replace(" ", "").replace("_", "").replace("-", "").replace("!", "")
                if clean_key in clean_tok or clean_tok in clean_key:
                    if not any(d.get("title") == info["title"] for d in detected):
                        detected.append(dict(info, id=key))
                    if info.get("force_hardmode"):
                        forces_hardmode = True
                    break

    # Also check boolean flags in meta if present
    flags_map = [
        ("drunkWorld", "05162020"),
        ("getGoodWorld", "for the worthy"),
        ("tenthAnniversaryWorld", "celebrationmk10"),
        ("dontStarveWorld", "the constant"),
        ("notTheBeesWorld", "not the bees"),
        ("remixWorld", "dont dig up"),
        ("noTrapsWorld", "no traps"),
        ("zenithWorld", "get fixed boi"),
        ("skyblockWorld", "skyblock")
    ]
    for flag_name, seed_key in flags_map:
        if meta.get(flag_name) and seed_key in SECRET_SEEDS_INFO:
            info = SECRET_SEEDS_INFO[seed_key]
            if not any(d.get("title") == info["title"] for d in detected):
                detected.append(dict(info, id=seed_key))
            if info.get("force_hardmode"):
                forces_hardmode = True

    return {
        "raw_seed": raw_seed,
        "is_special": len(detected) > 0,
        "forces_hardmode": forces_hardmode,
        "detected": detected
    }

def config_settings(path: Path) -> tuple[dict, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = data.get("Settings") if isinstance(data, dict) and isinstance(data.get("Settings"), dict) else data
        return data, settings if isinstance(settings, dict) else {}
    except Exception as e:
        log_error(f"Failed to read config {path}", e)
        return {}, {}

def prop(d: dict, *keys, default=""):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default

def players_from(payload) -> list[dict]:
    if isinstance(payload, dict):
        for k in ("players", "rows", "items", "data"):
            val = payload.get(k)
            if isinstance(val, list):
                return [p for p in val if isinstance(p, dict)]
        if "nickname" in payload or "name" in payload:
            return [payload]
    elif isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    return []

def _read_7bit_int(stream):
    value = 0
    for shift in range(0, 35, 7):
        raw = stream.read(1)
        if not raw:
            raise ValueError("Файл мира обрезан.")
        byte = raw[0]
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value
    raise ValueError("Некорректная строка в файле мира.")

def _read_dotnet_string(stream):
    length = _read_7bit_int(stream)
    if length > 1024 * 1024:
        raise ValueError("Слишком длинное поле в заголовке мира.")
    value = stream.read(length)
    if len(value) != length:
        raise ValueError("Файл мира обрезан.")
    return value.decode("utf-8", errors="replace")

def read_world_metadata(path: Path) -> dict:
    """Read only the stable Terraria world header fields; never modifies the file."""
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(4)
        if len(raw) != 4:
            raise ValueError("Файл мира слишком короткий.")
        version = struct.unpack("<i", raw)[0]
        if version < 140:
            raise ValueError("Слишком старый формат мира для чтения режима.")
        if stream.read(7) != b"relogic":
            raise ValueError("Не удалось распознать заголовок файла мира.")
        if not stream.read(1):
            raise ValueError("Файл мира обрезан.")
        if len(stream.read(4)) != 4 or len(stream.read(8)) != 8:
            raise ValueError("Файл мира обрезан.")
        count_raw = stream.read(2)
        if len(count_raw) != 2:
            raise ValueError("Файл мира обрезан.")
        section_count = struct.unpack("<h", count_raw)[0]
        if section_count < 1 or section_count > 128:
            raise ValueError("Некорректная таблица разделов мира.")
        pointers = []
        for _ in range(section_count):
            raw = stream.read(4)
            if len(raw) != 4:
                raise ValueError("Файл мира обрезан.")
            pointers.append(struct.unpack("<i", raw)[0])
        header_offset = pointers[0]
        if header_offset <= stream.tell() or header_offset >= path.stat().st_size:
            raise ValueError("Некорректное смещение заголовка мира.")
        stream.seek(header_offset)
        name = _read_dotnet_string(stream)
        seed = ""
        if version >= 179:
            if version == 179:
                stream.read(4)
            else:
                seed = _read_dotnet_string(stream)
            stream.read(8)
        guid = ""
        if version >= 181:
            raw_guid = stream.read(16)
            if len(raw_guid) == 16:
                guid = raw_guid.hex()
        raw28 = stream.read(28)
        if len(raw28) != 28:
            raise ValueError("Файл мира обрезан.")
        wid, left, right, top, bottom, max_y, max_x = struct.unpack("<7i", raw28)
        mode_offset = stream.tell()
        if version >= 209:
            raw = stream.read(4)
            if len(raw) != 4:
                raise ValueError("Файл мира обрезан.")
            mode = struct.unpack("<i", raw)[0]
        elif version == 208:
            raw = stream.read(1)
            if not raw:
                raise ValueError("Файл мира обрезан.")
            mode = 2 if raw[0] else None
        elif version >= 112:
            raw = stream.read(1)
            if not raw:
                raise ValueError("Файл мира обрезан.")
            mode = 1 if raw[0] else 0
        else:
            mode = 0

        drunk = False
        good = False
        tenth = False
        constant = False
        bees = False
        remix = False
        traps = False
        zenith = False
        skyblock = False
        hardmode = False
        try:
            if version >= 222:
                drunk = bool(stream.read(1)[0])
            if version >= 227:
                good = bool(stream.read(1)[0])
            if version >= 238:
                tenth = bool(stream.read(1)[0])
            if version >= 239:
                constant = bool(stream.read(1)[0])
            if version >= 241:
                bees = bool(stream.read(1)[0])
            if version >= 249:
                remix = bool(stream.read(1)[0])
            if version >= 266:
                traps = bool(stream.read(1)[0])
            if version >= 267:
                zenith = bool(stream.read(1)[0])
            if version >= 302:
                skyblock = bool(stream.read(1)[0])

            stream.read(8 + 1 + 12 + 16 + 12 + 16 + 4 + 4 + 4 + 4 + 4 + 8 + 8 + 8 + 1 + 4 + 1 + 1 + 4 + 4 + 1 + 14 + 1 + 1 + 1)
            hardmode = bool(struct.unpack("<?", stream.read(1))[0])
        except Exception:
            pass

    if mode not in WORLD_MODE_NAMES:
        mode = None
    return {
        "version": version,
        "name": name,
        "seed": seed,
        "guid": guid,
        "width": max_x,
        "height": max_y,
        "mode": mode,
        "hardmode": hardmode,
        "mode_offset": mode_offset if version >= 209 else None,
        "drunkWorld": drunk,
        "getGoodWorld": good,
        "tenthAnniversaryWorld": tenth,
        "dontStarveWorld": constant,
        "notTheBeesWorld": bees,
        "remixWorld": remix,
        "noTrapsWorld": traps,
        "zenithWorld": zenith,
        "skyblockWorld": skyblock
    }

def parse_worldinfo(data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass
    if isinstance(data, dict):
        response = prop(data, "response", default=None)
        if response is not None:
            data = response
        else:
            mode = prop(data, "mode", default=None)
            name = prop(data, "name", "worldname", default="")
            try:
                mode = int(mode)
            except (TypeError, ValueError):
                mode = None
            return {"mode": mode if mode in WORLD_MODE_NAMES else None, "name": str(name or "")}
    lines = data if isinstance(data, (list, tuple)) else str(data or "").splitlines()
    text = "\n".join(str(x) for x in lines)
    mode_match = re.search(r"(?:режим|mode)\s*:\s*(\d+)", text, re.IGNORECASE)
    name_match = re.search(r"(?:название|name)\s*:\s*(.+)", text, re.IGNORECASE)
    hard_match = re.search(r"(?:хардмод|hardmode)\s*:\s*(.+)", text, re.IGNORECASE)
    try:
        mode = int(mode_match.group(1)) if mode_match else None
    except (TypeError, ValueError):
        mode = None
    return {
        "mode": mode if mode in WORLD_MODE_NAMES else None,
        "name": name_match.group(1).strip() if name_match else "",
        "hardmode": bool(hard_match and "true" in hard_match.group(1).lower()),
        "lines": [str(x) for x in lines]
    }

CURRENT_PANEL_WINDOW = None

DEFAULT_PLAYER_PERMISSIONS = [
    "tshock.world.modify",
    "tshock.world.paint",
    "tshock.world.movenpc",
    "tshock.world.worldupgrades",
    "tshock.world.time.usesundial",
    "tshock.world.time.usemoondial",
    "tshock.tp.rod",
    "tshock.tp.wormhole",
    "tshock.tp.pylon",
    "tshock.tp.tppotion",
    "tshock.tp.magicconch",
    "tshock.tp.demonconch",
    "tshock.tp.home",
    "tshock.tp.spawn",
    "tshock.npc.summonboss",
    "tshock.npc.startinvasion",
    "tshock.npc.startdd2",
    "tshock.npc.spawnpets",
    "tshock.npc.hurttown",
    "tshock.item.usebanned",
    "tshock.projectiles.usebanned",
    "tshock.tiles.usebanned",
    "tshock.ignore.placetile",
    "tshock.ignore.removetile",
    "tshock.ignore.projectile",
    "tshock.ignore.itemstack",
    "tshock.warp",
    "tshock.whisper",
    "tshock.sendemoji",
    "tshock.synclocalarea",
    "tshock.account.changepassword",
    "tshock.account.logout",
]

# --- Core Panel Logic ---
class PanelController:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.q = queue.Queue()
        self.closing = False
        self.current_page = "server"
        
        self.server_profiles = []
        self.current_profile = {}
        self.server_port_open = False
        self.server_port_known = False
        self.server_refresh_at = 0.0
        self.api_ok = False
        self.status = {}
        self.players = []
        
        self.metric_previous = None
        self.metric_values = {}
        self.metrics_refresh_at = 0.0
        self._metrics_busy = False
        
        self._load_profiles()
        self._ensure_tshock_roles_and_permissions()
        self._start_background_timer()

    def _ensure_tshock_roles_and_permissions(self):
        """Ensures that the default player role has access to all standard game items, teleport items (rod, pylon, conch, potions), explosives, and ensures logged-in accounts are assigned to 'default' (player) rather than 'guest'."""
        default_cmds = ",".join(DEFAULT_PLAYER_PERMISSIONS)
        db_paths = [self._profile_dir() / "tshock.sqlite", ROOT / "tshock" / "tshock.sqlite"]
        for p in db_paths:
            if not p.is_file():
                continue
            try:
                con = sqlite3.connect(str(p))
                cur = con.cursor()
                cur.execute("UPDATE GroupList SET Commands = ? WHERE GroupName = 'default'", (default_cmds,))
                cur.execute("UPDATE Users SET Usergroup = 'default' WHERE Usergroup = 'guest' OR Usergroup = '' OR Usergroup IS NULL")
                con.commit()
                con.close()
            except Exception as e:
                log_error(f"Error updating roles in {p}", e)

        if self.is_server_running() and self.api_ok:
            try:
                for perm in DEFAULT_PLAYER_PERMISSIONS:
                    self.api("v3/server/rawcmd", {"cmd": f"/group addperm default {perm}"})
                self.api("v3/server/rawcmd", {"cmd": "/reload"})
            except Exception:
                pass

    def set_window(self, window):
        global CURRENT_PANEL_WINDOW
        CURRENT_PANEL_WINDOW = window

    def _safe_profile_folder(self, value: str) -> str:
        s = re.sub(r'[\r\n\t\x00-\x1f<>:"/\\|?*]+', " ", str(value)).strip()
        s = re.sub(r"\s+", " ", s).rstrip(". ")
        return s or "Сервер"

    def _safe_world_stem(self, value: str) -> str:
        s = re.sub(r'[\r\n\t\x00-\x1f<>:"/\\|?*]+', " ", str(value)).strip()
        s = re.sub(r"\s+", " ", s).rstrip(". ")
        return s or "Мир"

    def _unique_world_path(self, stem: str) -> Path:
        base = stem or "Мир"
        target = WORLDS_DIR / f"{base}.wld"
        idx = 2
        while target.exists():
            target = WORLDS_DIR / f"{base}_{idx}.wld"
            idx += 1
        return target

    def get_worlds_list(self) -> dict:
        worlds = []
        WORLDS_DIR.mkdir(parents=True, exist_ok=True)
        current = self.current_profile.get("world", "FriendsWorld.wld")
        for f in sorted(WORLDS_DIR.glob("*.wld"), key=lambda p: p.name.lower()):
            sz_mb = round(f.stat().st_size / (1024 * 1024), 2)
            meta = {}
            try:
                meta = read_world_metadata(f)
            except Exception:
                pass
            seed_analysis = analyze_world_seed(meta.get("seed", ""), meta)
            seed_label = f" · {seed_analysis['detected'][0]['badge']}" if seed_analysis["is_special"] else ""
            mode_name = WORLD_MODE_NAMES.get(meta.get("mode"), "Неизвестно")
            worlds.append({
                "filename": f.name,
                "name": f.stem,
                "size_mb": sz_mb,
                "mode": meta.get("mode"),
                "mode_name": f"{mode_name}{seed_label}",
                "special_seeds": seed_analysis["detected"]
            })
        active_info = self.get_world_details(current) if current and (WORLDS_DIR / current).is_file() else (self.get_world_details(worlds[0]["filename"]) if worlds else self.get_world_details(""))
        return {"worlds": worlds, "current": current if worlds else "", "info": active_info}

    def get_world_details(self, filename: str) -> dict:
        target = WORLDS_DIR / filename if filename else None
        if not target or not target.is_file():
            return {
                "name": "Мир не выбран",
                "filename": "",
                "mode_name": "—",
                "hardmode": False,
                "hardmode_str": "—",
                "size_mb": 0,
                "special_seeds": [],
                "raw": "В папке Worlds пока нет файлов миров.\n\nНажмите кнопку «Создать мир» для генерации нового мира\nили «Загрузить свой мир» для импорта файла .wld из ваших документов Terraria."
            }
        sz_mb = round(target.stat().st_size / (1024 * 1024), 2)
        meta = {}
        try:
            meta = read_world_metadata(target)
        except Exception as e:
            log_error(f"Error reading metadata for {filename}", e)
        
        seed_analysis = analyze_world_seed(meta.get("seed", ""), meta)
        live_mode = meta.get("mode")
        live_hardmode = meta.get("hardmode", False)
        if seed_analysis["forces_hardmode"]:
            live_hardmode = True

        from datetime import datetime
        mtime_str = datetime.fromtimestamp(target.stat().st_mtime).strftime("%d.%m.%Y %H:%M:%S")
        w_mode_name = WORLD_MODE_NAMES.get(live_mode, "Неизвестно")

        width = meta.get("width", 0)
        height = meta.get("height", 0)
        size_label = "Неизвестный"
        if width >= 8400:
            size_label = f"Большой ({width}×{height})"
        elif width >= 6400:
            size_label = f"Средний ({width}×{height})"
        elif width >= 4200:
            size_label = f"Маленький ({width}×{height})"
        elif width > 0:
            size_label = f"{width}×{height}"

        if seed_analysis["forces_hardmode"]:
            hardmode_str = "Да (Хардмод активен · запущен сидом «Tooeasy»)"
        elif live_hardmode:
            hardmode_str = "Да (Хардмод активен · Стена Плоти побеждена)"
        else:
            hardmode_str = "Нет (Пре-хардмод)"
        is_running = self.is_server_running()

        tech_lines = [
            "=== ТЕХНИЧЕСКИЙ ОТЧЁТ О МИРЕ ===",
            f"Файл мира: {filename} ({sz_mb} МБ)",
            f"Полный путь: {target}",
            f"Название мира: {meta.get('name') or target.stem}",
            f"Формат файла: v{meta.get('version', '—')} (Terraria 1.4+)",
            f"Режим сложности: {w_mode_name} (GameMode: {live_mode if live_mode is not None else '—'})",
            f"Стадия прохождения: {hardmode_str}",
            f"Размер карты: {size_label}",
            f"Сид генерации (Seed): {meta.get('seed') or 'Стандартный / Не указан'}",
            f"UUID мира: {meta.get('guid') or '—'}",
            f"Дата последнего сохранения: {mtime_str}",
            f"Текущий профиль сервера: {self.current_profile.get('name', 'Основной')}",
            f"Статус сервера: {'Онлайн (порт ' + str(GAME_PORT) + ')' if is_running else 'Оффлайн (остановлен)'}"
        ]
        if seed_analysis["is_special"]:
            tech_lines.append("")
            tech_lines.append("--- ОСОБЕННОСТИ И СЕКРЕТНЫЕ СИДЫ ---")
            for item in seed_analysis["detected"]:
                tech_lines.append(f"★ {item['title']}")
                tech_lines.append(f"  └ {item['desc']}")

        return {
            "name": target.stem,
            "filename": filename,
            "size_mb": sz_mb,
            "mode": live_mode,
            "mode_name": w_mode_name,
            "hardmode": live_hardmode,
            "hardmode_str": hardmode_str,
            "seed": meta.get("seed", ""),
            "special_seeds": seed_analysis["detected"],
            "raw": "\n".join(tech_lines)
        }

    def set_active_world(self, filename: str) -> dict:
        if self.is_server_running():
            return {"ok": False, "error": "Сервер сейчас работает. Чтобы сменить мир без сбоев карты, сначала остановите сервер!"}
        target = WORLDS_DIR / filename
        if not target.is_file():
            return {"ok": False, "error": f"Файл мира {filename} не существует."}
        try:
            read_world_metadata(target)
        except Exception as e:
            return {"ok": False, "error": f"Файл мира повреждён: {e}"}
        self.current_profile["world"] = filename
        self._save_profiles()
        return {"ok": True}

    def remove_world_from_list(self, filename: str) -> dict:
        if self.is_server_running():
            curr_world = self.current_profile.get("world", "")
            if curr_world.lower() == filename.lower():
                return {"ok": False, "error": "Нельзя убрать активный мир во время работы сервера! Сначала остановите сервер."}
        
        target = WORLDS_DIR / filename
        if not target.is_file():
            return {"ok": False, "error": f"Файл мира '{filename}' не найден."}
        
        try:
            # Safe archive into Backups/RemovedWorlds (never permanent destructive deletion)
            archive_dir = WORLDS_DIR / "Backups" / "RemovedWorlds"
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            stem = target.stem
            # Move the .wld and any matching .bak, .bak2
            for f in WORLDS_DIR.glob(f"{stem}.*"):
                if f.is_file():
                    dest = archive_dir / f"{f.stem}_{time.strftime('%Y%m%d_%H%M%S')}{f.suffix}"
                    shutil.move(str(f), str(dest))
            
            # If this world was the active world for current profile, switch to another world
            if self.current_profile.get("world", "").lower() == filename.lower():
                remaining = [f.name for f in WORLDS_DIR.glob("*.wld") if f.is_file()]
                if remaining:
                    self.current_profile["world"] = remaining[0]
                else:
                    self.current_profile["world"] = "FriendsWorld.wld"
                self._save_profiles()
            
            self.add_log(f"Мир «{filename}» убран из списка и сохранён в архив Backups/RemovedWorlds.", "notice")
            return {"ok": True, "message": f"Мир «{filename}» успешно убран из списка."}
        except Exception as e:
            log_error(f"Error removing world {filename}", e)
            return {"ok": False, "error": f"Ошибка перемещения файла: {e}"}

    def rename_world(self, old_filename: str, new_name: str) -> dict:
        old_target = WORLDS_DIR / old_filename
        if not old_target.is_file():
            return {"ok": False, "error": f"Файл мира '{old_filename}' не найден."}

        # Check server running if active world
        if self.is_server_running():
            curr_world = self.current_profile.get("world", "")
            if curr_world.lower() == old_filename.lower():
                return {"ok": False, "error": "Нельзя переименовать активный мир во время работы сервера! Сначала остановите сервер."}

        clean_stem = re.sub(r'[\r\n\t\x00-\x1f<>:"/\\|?*]+', " ", str(new_name)).strip()
        clean_stem = re.sub(r'\s+', " ", clean_stem).rstrip(". ")
        if clean_stem.lower().endswith(".wld"):
            clean_stem = clean_stem[:-4].rstrip(". ")

        if not clean_stem:
            return {"ok": False, "error": "Укажите корректное название мира."}

        new_filename = f"{clean_stem}.wld"
        new_target = WORLDS_DIR / new_filename

        # If name hasn't changed at all
        if new_target.resolve() == old_target.resolve() and new_target.name == old_target.name:
            return {"ok": True, "old_filename": old_filename, "new_filename": new_filename}

        # If another file with that name exists
        if new_target.exists() and new_target.resolve() != old_target.resolve():
            return {"ok": False, "error": f"Мир с именем '{new_filename}' уже существует!"}

        try:
            # 1. Safely rename the world file on disk (preserving 100% binary integrity)
            shutil.move(str(old_target), str(new_target))

            # 2. Rename any matching backups (.bak, .bak2, etc.)
            old_stem = old_target.stem
            for f in WORLDS_DIR.glob(f"{old_stem}.*"):
                if f.is_file() and f.resolve() != new_target.resolve():
                    dest = WORLDS_DIR / f"{clean_stem}{f.suffix}"
                    try:
                        shutil.move(str(f), str(dest))
                    except Exception:
                        pass

            # 3. Update profiles
            for prof in self.server_profiles:
                if prof.get("world", "").lower() == old_filename.lower():
                    prof["world"] = new_filename
            if self.current_profile.get("world", "").lower() == old_filename.lower():
                self.current_profile["world"] = new_filename
            self._save_profiles()

            self.add_log(f"Мир «{old_filename}» успешно переименован в «{new_filename}».", "notice")
            return {"ok": True, "old_filename": old_filename, "new_filename": new_filename}
        except Exception as e:
            log_error(f"Error renaming world {old_filename} to {new_filename}", e)
            return {"ok": False, "error": f"Ошибка переименования: {e}"}

    def _save_profiles(self):
        try:
            PANEL_DIR.mkdir(parents=True, exist_ok=True)
            payload = {"profiles": self.server_profiles}
            PROFILES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            log_error("Error saving server-profiles.json", e)

    def get_profiles_data(self) -> dict:
        _, s = config_settings(self._profile_config())
        settings = {
            "password": str(prop(s, "ServerPassword", default="") or ""),
            "max_slots": int(prop(s, "MaxSlots", default=8) or 8),
            "autosave": bool(prop(s, "AutoSave", default=True))
        }
        return {
            "profiles": self.server_profiles,
            "current_id": self.current_profile.get("id", "default"),
            "settings": settings
        }

    def switch_profile(self, profile_id: str) -> dict:
        if self.is_server_running():
            return {"ok": False, "error": "Профили переключаются по очереди. Сначала останови текущий сервер."}
        p = next((x for x in self.server_profiles if x.get("id") == profile_id), None)
        if not p:
            return {"ok": False, "error": "Профиль не найден"}
        self.current_profile = p
        return {"ok": True, "profile_name": p["name"]}

    def save_server_settings(self, password: str, max_slots: int, autosave: bool) -> dict:
        cfg_path = self._profile_config()
        if not cfg_path.is_file():
            return {"ok": False, "error": "Файл config.json не найден в профиле"}
        try:
            data, settings = config_settings(cfg_path)
            settings["ServerPassword"] = str(password or "")
            settings["MaxSlots"] = max(1, min(64, int(max_slots)))
            settings["AutoSave"] = bool(autosave)
            cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            global CURRENT_PANEL_WINDOW
            if CURRENT_PANEL_WINDOW:
                try:
                    CURRENT_PANEL_WINDOW.evaluate_js(f"updateServerState({json.dumps(self.get_ui_state())})")
                except Exception:
                    pass
            return {"ok": True, "ui_state": self.get_ui_state()}
        except Exception as e:
            log_error("Error saving server settings", e)
            return {"ok": False, "error": str(e)}

    def get_tshock_gameplay_settings(self) -> dict:
        cfg_path = self._profile_config()
        tshock_dir = self._profile_dir()
        sqlite_path = tshock_dir / "tshock.sqlite"
        
        cfg_data = {}
        if cfg_path.is_file():
            try:
                _, s = config_settings(cfg_path)
                cfg_data = {
                    "RememberLeavePos": bool(prop(s, "RememberLeavePos", default=True)),
                    "RequireLogin": bool(prop(s, "RequireLogin", default=True)),
                    "DisableUUIDLogin": bool(prop(s, "DisableUUIDLogin", default=False)),
                    "DisableLoginBeforeJoin": bool(prop(s, "DisableLoginBeforeJoin", default=False)),
                    "MinimumPasswordLength": int(prop(s, "MinimumPasswordLength", default=4) or 4),
                    "MaxSlots": int(prop(s, "MaxSlots", default=8) or 8),
                    "SpawnProtection": bool(prop(s, "SpawnProtection", default=False)),
                    "SpawnProtectionRadius": int(prop(s, "SpawnProtectionRadius", default=10) or 10),
                    "DisableBuild": bool(prop(s, "DisableBuild", default=False)),
                    "RegionProtectChests": bool(prop(s, "RegionProtectChests", default=False)),
                    "DisableClownBombs": bool(prop(s, "DisableClownBombs", default=False)),
                    "DisablePrimeBombs": bool(prop(s, "DisablePrimeBombs", default=False)),
                    "PreventDeadModification": bool(prop(s, "PreventDeadModification", default=True)),
                    "AllowCorruptionCreep": bool(prop(s, "AllowCorruptionCreep", default=True)),
                    "AllowCrimsonCreep": bool(prop(s, "AllowCrimsonCreep", default=True)),
                    "AllowHallowCreep": bool(prop(s, "AllowHallowCreep", default=True)),
                    "ForceHalloween": bool(prop(s, "ForceHalloween", default=False)),
                    "ForceXmas": bool(prop(s, "ForceXmas", default=False)),
                    "DisableTombstones": bool(prop(s, "DisableTombstones", default=False)),
                    "GiveItemsDirectly": bool(prop(s, "GiveItemsDirectly", default=False)),
                    "DefaultSpawnRate": int(prop(s, "DefaultSpawnRate", default=600) or 600),
                    "DefaultMaximumSpawns": int(prop(s, "DefaultMaximumSpawns", default=5) or 5),
                    "InfiniteInvasion": bool(prop(s, "InfiniteInvasion", default=False)),
                    "InvasionMultiplier": int(prop(s, "InvasionMultiplier", default=1) or 1),
                    "RespawnSeconds": int(prop(s, "RespawnSeconds", default=0) or 0),
                    "RespawnBossSeconds": int(prop(s, "RespawnBossSeconds", default=0) or 0),
                    "AnonymousBossInvasions": bool(prop(s, "AnonymousBossInvasions", default=True)),
                    "AutoSave": bool(prop(s, "AutoSave", default=True))
                }
            except Exception as e:
                log_error("Error reading config for gameplay settings", e)

        groups = []
        if sqlite_path.is_file():
            try:
                import sqlite3
                con = sqlite3.connect(sqlite_path)
                cur = con.cursor()
                for row in cur.execute("SELECT GroupName, Prefix, ChatColor, Commands FROM GroupList").fetchall():
                    groups.append({
                        "name": row[0],
                        "prefix": row[1] or "",
                        "color": row[2] or "255,255,255",
                        "commands": row[3] or ""
                    })
                con.close()
            except Exception as e:
                log_error("Error reading groups from tshock.sqlite", e)

        return {
            "ok": True,
            "settings": cfg_data,
            "groups": groups,
            "server_running": self.is_server_running()
        }

    def save_tshock_gameplay_settings(self, payload: dict) -> dict:
        cfg_path = self._profile_config()
        tshock_dir = self._profile_dir()
        sqlite_path = tshock_dir / "tshock.sqlite"
        if not cfg_path.is_file():
            return {"ok": False, "error": "Файл config.json не найден"}

        try:
            data, settings = config_settings(cfg_path)
            new_s = payload.get("settings", {})
            
            for k, v in new_s.items():
                if k in settings:
                    if isinstance(settings[k], bool):
                        settings[k] = bool(v)
                    elif isinstance(settings[k], int):
                        settings[k] = int(v)
                    else:
                        settings[k] = v

            cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            roles = payload.get("roles")
            if roles and sqlite_path.is_file():
                import sqlite3
                con = sqlite3.connect(sqlite_path)
                cur = con.cursor()
                for r in roles:
                    gname = r.get("name")
                    prefix = r.get("prefix")
                    if gname and prefix is not None:
                        cur.execute("UPDATE GroupList SET Prefix=? WHERE GroupName=?", (prefix, gname))
                con.commit()
                con.close()

            reloaded = False
            rem_pos = "ВКЛ" if new_s.get("RememberLeavePos", True) else "ВЫКЛ"
            req_log = "ВКЛ" if new_s.get("RequireLogin", True) else "ВЫКЛ"
            sp_prot = "ВКЛ" if new_s.get("SpawnProtection", False) else "ВЫКЛ"

            if self.is_server_running():
                try:
                    self.send_command("/reload")
                    self.send_broadcast("★ Сервер: Настройки геймплея и защиты обновлены (/reload)!", color_hex="00ffcc")
                    reloaded = True
                    self.add_log(f"[INF] Параметры TShock обновлены (Позиция: {rem_pos}, Заморозка: {req_log}, Защита спавна: {sp_prot}).", "notice")
                    self.add_log("[INF] Конфигурация TShock успешно перезагружена на лету (/reload)!", "notice")
                except Exception:
                    pass
            else:
                self.add_log(f"[INF] Параметры TShock сохранены в файл конфигурации (Позиция: {rem_pos}, Заморозка: {req_log}).", "notice")

            global CURRENT_PANEL_WINDOW
            if CURRENT_PANEL_WINDOW:
                try:
                    CURRENT_PANEL_WINDOW.evaluate_js(f"updateServerState({json.dumps(self.get_ui_state())})")
                except Exception:
                    pass

            return {"ok": True, "reloaded": reloaded}
        except Exception as e:
            log_error("Error saving tshock gameplay settings", e)
            return {"ok": False, "error": str(e)}

    def execute_gameplay_action(self, action: str) -> dict:
        if not self.is_server_running():
            return {"ok": False, "error": "Сервер сейчас выключен. Запустите сервер для выполнения действий."}

        action = str(action or "").strip().lower()
        mapping = {
            "save": ("/save", "Мир успешно сохранён на диск (/save)!", "00ffcc"),
            "clear": ("/clear", "Все брошенные предметы очищены с карты (/clear)!", "ffaa33"),
            "settle": ("/settle", "Все жидкости в мире осаждены (/settle)!", "33ccff"),
            "butcher": ("/butcher", "Все враждебные мобы уничтожены (/butcher)!", "ff4444"),
            "clearangler": ("/clearangler", "Ежедневные квесты Рыбака сброшены (/clearangler)!", "33ff99"),
            "grow": ("/grow", "Рост деревьев и растений ускорен (/grow)!", "66ff66"),
            "day": ("/time 12:00", "Установлено дневное время (полдень)!", "ffff33"),
            "night": ("/time 00:00", "Установлено ночное время (полночь)!", "9999ff")
        }

        if action not in mapping:
            return {"ok": False, "error": f"Неизвестное действие: {action}"}

        cmd, desc, color = mapping[action]
        try:
            res = self.send_command(cmd)
            self.send_broadcast(f"★ Сервер: {desc}", color_hex=color)
            self.add_log(f"[Геймплей] {desc}", "notice")
            return {"ok": True, "message": desc, "output": res.get("response", "")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_current_profile(self) -> dict:
        if self.is_server_running():
            return {"ok": False, "error": "Сначала останови сервер перед удалением профиля."}
        if len(self.server_profiles) < 2:
            return {"ok": False, "error": "Нельзя удалить единственный (последний) сервер."}
        
        old = self.current_profile
        name = old["name"]
        world_name = Path(str(old.get("world", ""))).name
        shared = bool(world_name and any(p is not old and Path(str(p.get("world", ""))).name.casefold() == world_name.casefold() for p in self.server_profiles))

        # 1. Delete on-disk profile folder
        try:
            config = (ROOT / Path(str(old.get("config_dir", "tshock")))).resolve()
            relative = config.relative_to(PROFILES_DIR.resolve())
            storage = (PROFILES_DIR / relative.parts[0]).resolve()
            if storage.exists():
                shutil.rmtree(storage)
        except Exception as e:
            log_error(f"Error removing profile folder for {name}", e)
            return {"ok": False, "error": f"Не удалось удалить папку профиля: {e}"}

        # 2. Delete world if not shared
        if world_name and not shared:
            try:
                w_path = WORLDS_DIR / world_name
                if w_path.is_file():
                    w_path.unlink()
                companion = w_path.with_suffix(".twld")
                if companion.is_file():
                    companion.unlink()
            except Exception as e:
                log_error(f"Error deleting unshared world {world_name}", e)

        # 3. Remove from profiles list and switch to first
        self.server_profiles.remove(old)
        self.current_profile = self.server_profiles[0]
        self._save_profiles()
        return {"ok": True, "message": f"Сервер «{name}» и его файлы удалены." + (" (Общий мир оставлен)" if shared else "")}

    def create_profile_wizard(self, params: dict) -> dict:
        if self.is_server_running():
            return {"ok": False, "error": "Перед созданием профиля останови текущий сервер."}
        
        name = self._safe_profile_folder(params.get("name", "Новый сервер"))
        if any(p["name"].casefold() == name.casefold() for p in self.server_profiles):
            return {"ok": False, "error": "Сервер с таким названием уже существует."}
        
        profile_id = uuid.uuid4().hex[:12]
        config_path = Path("ServerProfiles") / name / "tshock"
        target_dir = ROOT / config_path

        try:
            target_dir.mkdir(parents=True, exist_ok=False)
            source = self._profile_dir()
            for filename in ("config.json", "sscconfig.json", "motd.txt", "rules.txt", "whitelist.txt"):
                src = source / filename
                if src.is_file():
                    shutil.copy2(src, target_dir / filename)
            
            cfg_path = target_dir / "config.json"
            if cfg_path.is_file():
                new_cfg, new_settings = config_settings(cfg_path)
            else:
                new_cfg, new_settings = config_settings(CONFIG)
            
            new_settings["ServerPassword"] = secrets.token_urlsafe(9)
            new_settings["LogPath"] = (config_path / "logs").as_posix()
            cfg_path.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            shutil.rmtree(target_dir.parent, ignore_errors=True)
            log_error(f"Error creating profile folder for {name}", e)
            return {"ok": False, "error": f"Не удалось создать файлы профиля: {e}"}

        # World setup
        world_name = "FriendsWorld.wld"
        if params.get("world_type") == "existing":
            world_name = params.get("world_file") or world_name
        else:
            # Generate new world
            gen_size = params.get("world_size", 2)
            gen_mode = params.get("world_mode", 0)
            gen_seed = params.get("world_seed", "")
            res = self.create_world_background(name, gen_size, gen_mode, gen_seed)
            if res.get("ok"):
                world_name = res["filename"]

        new_profile = {
            "id": profile_id,
            "name": name,
            "world": world_name,
            "config_dir": str(config_path)
        }
        self.server_profiles.append(new_profile)
        self.current_profile = new_profile
        self._save_profiles()
        return {"ok": True, "profile": new_profile}

    def change_world_mode(self, target_mode_name: str) -> dict:
        if target_mode_name not in WORLD_MODE_COMMANDS:
            return {"ok": False, "error": "Неверный режим мира"}
        code = next(k for k, v in WORLD_MODE_NAMES.items() if v == target_mode_name)
        command_arg = WORLD_MODE_COMMANDS[target_mode_name]

        # 1. If server is running, change live via REST API
        if self.is_server_running() and self.api_ok:
            try:
                self.api("v3/server/rawcmd", {"cmd": f"worldmode {command_arg}"})
                return {"ok": True, "message": f"Режим сервера переключён на {target_mode_name}"}
            except Exception as e:
                log_error(f"Error changing live worldmode", e)
                return {"ok": False, "error": str(e)}

        # 2. Offline change: binary patch with automatic backup
        filename = self.current_profile.get("world", "FriendsWorld.wld")
        target = WORLDS_DIR / filename
        if not target.is_file():
            return {"ok": False, "error": "Файл мира не найден."}
        try:
            meta = read_world_metadata(target)
            offset = meta.get("mode_offset")
            if offset is None:
                return {"ok": False, "error": "Смещение режима не поддерживается для этой версии мира."}
            
            # Backup
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup_dir = WORLDS_DIR / "Backups" / f"before-mode-{stamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_dir / target.name)

            # Write code byte
            with target.open("r+b") as stream:
                stream.seek(offset)
                stream.write(struct.pack("<i", code))
            return {"ok": True, "message": f"Сложность изменена на {target_mode_name}. Бэкап сохранён."}
        except Exception as e:
            log_error(f"Error patching world mode offline", e)
            return {"ok": False, "error": str(e)}

    def create_world_background(self, world_name: str, size: int, mode: int, seed: str = "") -> dict:
        if self.is_server_running():
            return {"ok": False, "error": "Перед созданием мира останови сервер."}
        
        if getattr(self, "_world_gen_active", False):
            return {"ok": False, "error": "Генерация мира уже выполняется! Подождите завершения."}
        
        clean_name = re.sub(r'[\r\n\x00-\x1f"]+', " ", str(world_name)).strip()
        clean_seed = re.sub(r'[\r\n\x00-\x1f]+', " ", str(seed)).strip()
        if not clean_name:
            clean_name = "Новый мир"

        stem = self._safe_world_stem(clean_name)
        target_path = self._unique_world_path(stem)
        config_dir = self._profile_dir()

        self._world_gen_active = True
        self.world_gen_info = {
            "active": True,
            "world_name": clean_name,
            "filename": target_path.name,
            "percent": 0,
            "stage": "Запуск генератора...",
            "done": False,
            "error": ""
        }
        self._emit_world_gen_progress()

        def worker():
            temp_dir = PANEL_DIR / "WorldGeneration" / f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}"
            proc = None
            try:
                temp_dir.mkdir(parents=True, exist_ok=True)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind(("127.0.0.1", 0))
                    port = probe.getsockname()[1]
                
                config_file = temp_dir / "serverconfig.txt"
                lines = [f"difficulty={mode}"]
                if clean_seed:
                    lines.append(f"seed={clean_seed}")
                config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

                env = os.environ.copy()
                runtime = ROOT / "dotnet"
                env["DOTNET_ROOT"] = str(runtime)
                env["PATH"] = str(runtime) + os.pathsep + env.get("PATH", "")

                args = [
                    str(SERVER), "-configpath", str(ROOT / Path(config_dir)),
                    "-config", str(config_file), "-ip", "127.0.0.1", "-port", str(port),
                    "-maxplayers", "1", "-world", str(target_path),
                    "-autocreate", str(size), "-worldname", clean_name, "-noupnp"
                ]

                proc = subprocess.Popen(
                    args, cwd=str(ROOT), env=env, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )

                ready = threading.Event()

                def reader():
                    try:
                        for line in iter(proc.stdout.readline, ""):
                            if not line:
                                break
                            line_clean = line.strip()
                            if not line_clean:
                                continue
                            
                            # Regex for percentage: e.g. "15%" or "Generating terrain: 25%"
                            pct_match = re.search(r'(\d{1,3})\s*%', line_clean)
                            if pct_match:
                                p = int(pct_match.group(1))
                                if 0 <= p <= 100:
                                    self.world_gen_info["percent"] = p
                            
                            # Stage description
                            stage_raw = re.sub(r'\[.*?\]', '', line_clean).strip()
                            if stage_raw:
                                lower_s = stage_raw.lower()
                                if "terrain" in lower_s or "land" in lower_s:
                                    stage_desc = "Генерация ландшафта"
                                elif "settling" in lower_s or "liquid" in lower_s:
                                    stage_desc = "Осаждение жидкостей"
                                elif "saving" in lower_s:
                                    stage_desc = "Сохранение мира"
                                elif "resetting" in lower_s or "clearing" in lower_s:
                                    stage_desc = "Подготовка мира"
                                elif "structure" in lower_s or "ore" in lower_s or "placing" in lower_s:
                                    stage_desc = "Размещение структур и руды"
                                elif "biome" in lower_s or "dungeon" in lower_s:
                                    stage_desc = "Создание биомов"
                                elif "%" in stage_raw:
                                    stage_desc = stage_raw
                                else:
                                    stage_desc = stage_raw[:40]
                                self.world_gen_info["stage"] = stage_desc
                            
                            self._emit_world_gen_progress()

                            lower = line_clean.lower()
                            if ("saving world data" in lower and "100%" in lower) or "listening on" in lower or "server started" in lower or "ready" in lower:
                                ready.set()
                    except Exception:
                        pass

                t_reader = threading.Thread(target=reader, daemon=True)
                t_reader.start()

                # Poll in worker thread without blocking
                deadline = time.monotonic() + 360  # 6 min max
                last_size = 0
                size_stable_count = 0

                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        break
                    if ready.is_set():
                        break
                    if self.port_open(port):
                        ready.set()
                        break
                    if target_path.is_file():
                        sz = target_path.stat().st_size
                        if sz > 500_000:
                            if sz == last_size:
                                size_stable_count += 1
                                if size_stable_count >= 5:  # size unchanged for 2.5 seconds
                                    ready.set()
                                    break
                            else:
                                last_size = sz
                                size_stable_count = 0
                    time.sleep(0.5)

                # Stop the generator process gracefully
                if proc.poll() is None:
                    try:
                        proc.stdin.write("exit\n")
                        proc.stdin.flush()
                        proc.wait(timeout=10)
                    except Exception:
                        pass
                    if proc.poll() is None:
                        try:
                            proc.kill()
                            proc.wait(timeout=5)
                        except Exception:
                            pass

                # Final verification: check world file existence and size
                time.sleep(0.5)
                if target_path.is_file() and target_path.stat().st_size > 1024:
                    self.add_log(f"Мир «{target_path.name}» успешно сгенерирован.", "notice")
                    self.current_profile["world"] = target_path.name
                    self._save_profiles()
                    self.world_gen_info["percent"] = 100
                    self.world_gen_info["stage"] = "Мир успешно создан!"
                    self.world_gen_info["done"] = True
                    self.world_gen_info["active"] = False
                    self._emit_world_gen_progress()
                else:
                    raise RuntimeError("Файл мира не найден после завершения генератора.")
            except Exception as e:
                log_error("World generation failed", e)
                self.add_log(f"Ошибка создания мира: {e}", "error")
                self.world_gen_info["error"] = str(e)
                self.world_gen_info["active"] = False
                self.world_gen_info["done"] = False
                self._emit_world_gen_progress()
            finally:
                self._world_gen_active = False
                shutil.rmtree(temp_dir, ignore_errors=True)

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "filename": target_path.name, "started": True}

    def _emit_world_gen_progress(self):
        global CURRENT_PANEL_WINDOW
        if CURRENT_PANEL_WINDOW:
            try:
                info = getattr(self, "world_gen_info", {})
                CURRENT_PANEL_WINDOW.evaluate_js(f"updateWorldGenProgress({json.dumps(info)})")
            except Exception:
                pass

    def get_game_documents_worlds(self, force: bool = False) -> list[dict]:
        """Scans user's Terraria Documents directory for single-player worlds with anti-lag caching."""
        now = time.monotonic()
        if not force and hasattr(self, "_doc_worlds_cache") and self._doc_worlds_cache is not None:
            if now - getattr(self, "_doc_worlds_cache_time", 0) < 10.0:
                return self._doc_worlds_cache
        docs = []
        try:
            buf = ctypes.create_unicode_buffer(300)
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
            docs.append(Path(buf.value) / "My Games" / "Terraria" / "Worlds")
        except Exception:
            pass
        docs.append(Path.home() / "Documents" / "My Games" / "Terraria" / "Worlds")
        docs.append(Path.home() / "OneDrive" / "Документы" / "My Games" / "Terraria" / "Worlds")
        docs.append(Path.home() / "OneDrive" / "Documents" / "My Games" / "Terraria" / "Worlds")

        seen_paths = set()
        worlds = []
        for d in docs:
            if d.is_dir():
                for p in d.glob("*.wld"):
                    try:
                        resolved = p.resolve()
                        if resolved in seen_paths:
                            continue
                        seen_paths.add(resolved)
                        meta = read_world_metadata(p)
                        sz_mb = round(p.stat().st_size / (1024 * 1024), 2)
                        from datetime import datetime
                        mtime_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
                        worlds.append({
                            "name": meta.get("name") or p.stem,
                            "filename": p.name,
                            "path": str(p),
                            "size_mb": sz_mb,
                            "mode": meta.get("mode"),
                            "mode_name": WORLD_MODE_NAMES.get(meta.get("mode"), "Неизвестно"),
                            "mtime": mtime_str
                        })
                    except Exception:
                        pass
        return sorted(worlds, key=lambda w: w["name"].lower())

    def import_world_from_path(self, source_path: str) -> dict:
        """Copies an existing .wld (+ .twld companion) into server Worlds directory."""
        if self.is_server_running():
            return {"ok": False, "error": "Остановите сервер перед загрузкой или сменой мира."}
        src = Path(source_path)
        if not src.is_file():
            return {"ok": False, "error": f"Файл не найден: {source_path}"}
        try:
            meta = read_world_metadata(src)
            target = self._unique_world_path(self._safe_world_stem(src.stem))
            shutil.copy2(src, target)
            twld = src.with_suffix(".twld")
            if twld.is_file():
                try:
                    shutil.copy2(twld, target.with_suffix(".twld"))
                except Exception:
                    pass
            self.current_profile["world"] = target.name
            self._save_profiles()
            self.add_log(f"Мир «{target.name}» успешно импортирован из {src.parent.name}.", "notice")
            return {
                "ok": True,
                "filename": target.name,
                "world_name": meta.get("name") or target.stem,
                "message": f"Мир «{target.name}» добавлен и выбран."
            }
        except Exception as e:
            log_error(f"Error importing world {source_path}", e)
            return {"ok": False, "error": f"Ошибка добавления мира: {e}"}

    def _load_profiles(self):
        saved_world = "FriendsWorld.wld"
        try:
            if CONFIG.is_file():
                _, s = config_settings(CONFIG)
                saved_world = str(prop(s, "World", "WorldName", default=saved_world) or saved_world)
        except Exception:
            pass
        default_profile = {
            "id": "default",
            "name": "Основной",
            "world": saved_world,
            "config_dir": "tshock"
        }
        self.server_profiles = [default_profile]
        if PROFILES_FILE.is_file():
            try:
                raw = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
                profiles = raw.get("profiles") if isinstance(raw, dict) else raw
                if isinstance(profiles, list) and profiles:
                    loaded = []
                    for item in profiles:
                        if isinstance(item, dict) and item.get("id") and item.get("name"):
                            loaded.append(item)
                    if loaded:
                        self.server_profiles = loaded
            except Exception as e:
                log_error("Error loading server-profiles.json", e)
        self.current_profile = self.server_profiles[0]

    def _profile_dir(self, profile: dict | None = None) -> Path:
        p = profile or self.current_profile
        return ROOT / Path(str(p.get("config_dir", "tshock")))

    def _profile_config(self, profile: dict | None = None) -> Path:
        return self._profile_dir(profile) / "config.json"

    def token(self) -> str | None:
        try:
            _, s = config_settings(self._profile_config())
            tokens = prop(s, "ApplicationRestTokens", default={}) or {}
            if isinstance(tokens, dict):
                for key, val in tokens.items():
                    if str(prop(val, "Username", default="")).casefold() == "terrariapanel":
                        return key
        except Exception:
            pass
        return None

    def api(self, path: str, params: dict | None = None) -> dict | list | str:
        token = self.token()
        if not token:
            raise RuntimeError("В config.json не найден локальный токен панели.")
        query = dict(params or {})
        query["token"] = token
        url = f"http://127.0.0.1:{REST_PORT}/{path.lstrip('/')}?{urllib.parse.urlencode(query)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3.0) as response:
            body = response.read().decode("utf-8", "replace")
        data = json.loads(body) if body else {}
        if isinstance(data, dict):
            status = str(data.get("status", "200"))
            if status not in ("200", "OK", "ok", "success", "Success"):
                raise RuntimeError(str(data.get("response") or data.get("error") or body))
            if "response" in data:
                return data["response"]
        return data

    def get_players(self) -> list[dict]:
        if not self.is_server_running():
            self.players = []
            return []
        try:
            data = self.api("v2/server/status", {"players": "true"})
            ps = players_from(data)
            if not ps:
                try:
                    ps = players_from(self.api("v2/players/list"))
                except Exception:
                    pass
            self.players = ps
            self.api_ok = True
        except Exception as e:
            # Server might be running without REST API or starting up
            if not self.api_ok:
                log_error("Could not fetch players via REST API", e)
        return self.players

    def kick_player(self, player_name: str, reason: str = "") -> dict:
        clean_name = re.sub(r'[\r\n\t\x00-\x1f"]+', "", player_name).strip()
        clean_reason = re.sub(r'[\r\n\t\x00-\x1f]+', " ", reason).strip() or "Отключён администратором"
        if not clean_name:
            return {"ok": False, "error": "Имя игрока не указано."}
        
        # 1. Try stdin command if process owned
        if self.proc is not None and self.proc.poll() is None and self.proc.stdin:
            try:
                cmd = f'kick "{clean_name}" {clean_reason}\n'
                self.proc.stdin.write(cmd)
                self.proc.stdin.flush()
                return {"ok": True, "message": f"Команда кика отправлена для {clean_name}"}
            except Exception as e:
                log_error(f"Error kicking player {clean_name} via stdin", e)

        # 2. Try REST API
        try:
            self.api("v2/players/kick", {"player": clean_name, "reason": clean_reason})
            return {"ok": True, "message": f"Игрок {clean_name} отключён через REST API"}
        except Exception as e:
            log_error(f"Error kicking player {clean_name} via REST API", e)
            return {"ok": False, "error": str(e)}

    def add_log(self, text: str, log_type: str = ""):
        global CURRENT_PANEL_WINDOW
        if CURRENT_PANEL_WINDOW:
            safe_text = json.dumps(str(text))
            safe_type = json.dumps(str(log_type))
            try:
                CURRENT_PANEL_WINDOW.evaluate_js(f"appendLog({safe_text}, {safe_type})")
            except Exception:
                pass

    def send_broadcast(self, text: str, color_hex: str = "00ffcc") -> dict:
        """Sends a colored broadcast message to in-game chat for all players."""
        clean = str(text or "").strip()
        if not clean:
            return {"ok": False, "error": "Пустое сообщение"}
        formatted = f"[c/{color_hex}:{clean}]"
        try:
            res = self.api("v3/server/rawcmd", {"cmd": f"/broadcast {formatted}"})
            return {"ok": True, "response": res}
        except Exception as e:
            try:
                self.api("v3/server/rawcmd", {"cmd": f"/bc {clean}"})
                return {"ok": True}
            except Exception:
                pass
            if self.proc and self.proc.poll() is None and self.proc.stdin:
                try:
                    self.proc.stdin.write(f"say {clean}\n")
                    self.proc.stdin.flush()
                except Exception:
                    pass
            return {"ok": False, "error": str(e)}

    def send_command(self, cmd: str) -> dict:
        clean = str(cmd or "").strip()
        if not clean:
            return {"ok": False, "error": "Пустая команда"}
        
        api_cmd = clean if clean.startswith(("/", ".")) else ("/" + clean)
        
        # 1. Prefer REST API v3/server/rawcmd for reliable TShock execution
        try:
            res = self.api("v3/server/rawcmd", {"cmd": api_cmd})
            lines = []
            if isinstance(res, dict):
                resp_val = res.get("response", [])
                if isinstance(resp_val, list):
                    lines = [str(x) for x in resp_val if str(x).strip()]
                elif resp_val:
                    lines = [str(resp_val)]
            elif isinstance(res, list):
                lines = [str(x) for x in res if str(x).strip()]
            
            output_text = "\n".join(lines) if lines else "Команда выполнена."
            for line in lines:
                self.add_log(line, "info")
            return {"ok": True, "response": output_text}
        except Exception as e:
            log_error(f"Error executing command {api_cmd} via REST API", e)
        
        # 2. Fallback to stdin if REST API is not responding
        if self.proc is not None and self.proc.poll() is None and self.proc.stdin:
            try:
                self.proc.stdin.write(clean + "\n")
                self.proc.stdin.flush()
                return {"ok": True, "response": f"Команда передана серверу (stdin): {clean}"}
            except Exception as e:
                log_error("Error writing to stdin", e)
                return {"ok": False, "error": str(e)}

        return {"ok": False, "error": "Сервер не отвечает"}

    def send_chat(self, msg: str) -> dict:
        clean = str(msg or "").strip()
        if not clean:
            return {"ok": False, "error": "Пустое сообщение"}
        
        res = self.send_broadcast(f"[Сервер] {clean}", color_hex="00ffcc")
        self.add_log(f"[Сервер в чат] {clean}", "notice")
        return res

    def port_open(self, port: int) -> bool:
        if os.name == "nt":
            return self._listening_pid(port) is not None
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            return False

    def is_server_running(self) -> bool:
        own = self.proc is not None and self.proc.poll() is None
        if own or self.api_ok:
            return True
        if self._listening_server_pid() is not None:
            return True
        return False

    def get_playit_address(self) -> str:
        now = time.time()
        if hasattr(self, "_cached_playit_address") and (now - getattr(self, "_last_playit_check", 0) < 60):
            return self._cached_playit_address

        self._cached_playit_address = ""
        self._last_playit_check = now

        def bg_check():
            try:
                import urllib.request, json
                secret = None
                for sp in [Path("C:/ProgramData/playit_gg/playit.toml"), Path(os.environ.get("LOCALAPPDATA", "")) / "playit_gg" / "playit.toml"]:
                    if sp.is_file():
                        try:
                            for line in sp.read_text(encoding="utf-8", errors="ignore").splitlines():
                                if "secret_key" in line and "=" in line:
                                    sec = line.split("=")[1].strip().strip("\"' ")
                                    if len(sec) > 10:
                                        secret = sec
                                        break
                        except Exception:
                            pass
                    if secret:
                        break

                if not secret:
                    return

                req = urllib.request.Request(
                    "https://api.playit.gg/v1/tunnels/list",
                    data=b"{}",
                    headers={
                        "Authorization": f"Agent-Key {secret}",
                        "Content-Type": "application/json",
                        "User-Agent": "TerrariaPanel/1.0"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_tunnels = data.get("data", {}).get("tunnels", [])
                    best = ""
                    for t in raw_tunnels:
                        t_type = str(t.get("tunnel_type", "")).lower()
                        t_name = str(t.get("name", "")).lower()
                        addrs = t.get("connect_addresses", [])
                        t_addr = ""
                        for a in addrs:
                            val = a.get("value", {}).get("address", "")
                            if val and ".ply.gg" in val:
                                t_addr = val
                                break
                        if not t_addr and addrs:
                            t_addr = addrs[0].get("value", {}).get("address", "")
                        if "terraria" in t_type or "7777" in t_name or "terraria" in t_name:
                            best = t_addr
                            break
                        if not best and t_addr:
                            best = t_addr

                    if best:
                        self._cached_playit_address = best
                        global CURRENT_PANEL_WINDOW
                        if CURRENT_PANEL_WINDOW:
                            safe_addr = json.dumps(best)
                            try:
                                CURRENT_PANEL_WINDOW.evaluate_js(f"window.updatePlayitAddress && window.updatePlayitAddress({safe_addr})")
                            except Exception:
                                pass
            except Exception:
                pass

        threading.Thread(target=bg_check, daemon=True).start()
        return self._cached_playit_address

    def get_ui_state(self) -> dict:
        running = self.is_server_running()
        world = self.current_profile.get("world", "")
        world_path = WORLDS_DIR / world if world else None
        has_world = world_path is not None and world_path.is_file()

        world_display = Path(world).name if has_world else "Мир не выбран"
        world_mode_display = "Создайте или выберите мир"
        if has_world:
            try:
                meta = read_world_metadata(world_path)
                world_mode_display = WORLD_MODE_NAMES.get(meta.get("mode"), "Классический")
            except Exception:
                pass

        playit_addr = self.get_playit_address()
        display_address = playit_addr if playit_addr else f"localhost:{GAME_PORT}"

        max_slots = 8
        try:
            _, s = config_settings(self._profile_config())
            max_slots = max(1, min(64, int(prop(s, "MaxSlots", default=8) or 8)))
        except Exception:
            pass

        return {
            "running": running,
            "has_world": has_world,
            "profile_name": self.current_profile.get("name", "Основной"),
            "world_name": world_display,
            "world_mode": world_mode_display,
            "players_count": len(self.players),
            "max_players": max_slots,
            "uptime": "онлайн" if running else "—",
            "address": display_address,
            "playit_address": playit_addr,
            "rest_status": ("🌐 Playit туннель активен" if playit_addr else ("REST API подключён" if self.api_ok else ("Сервер работает" if running else "REST API ожидает запуск")))
        }

    def _listening_pid(self, port: int) -> int | None:
        if os.name != "nt":
            return None
        class TCPROW_OWNER_PID(ctypes.Structure):
            _fields_ = [("state", ctypes.c_ulong), ("local_addr", ctypes.c_ulong), ("local_port", ctypes.c_ulong),
                        ("remote_addr", ctypes.c_ulong), ("remote_port", ctypes.c_ulong), ("pid", ctypes.c_ulong)]
        get_table = ctypes.windll.iphlpapi.GetExtendedTcpTable
        get_table.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_int, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        get_table.restype = ctypes.c_ulong
        size = ctypes.c_ulong(0)
        get_table(None, ctypes.byref(size), 0, 2, 5, 0)
        if not size.value:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        status = get_table(buffer, ctypes.byref(size), 0, 2, 5, 0)
        if status:
            return None
        count = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ulong)).contents.value
        rows_type = TCPROW_OWNER_PID * count
        rows = ctypes.cast(ctypes.addressof(buffer) + ctypes.sizeof(ctypes.c_ulong), ctypes.POINTER(rows_type)).contents
        for row in rows:
            if row.state == 2 and socket.ntohs(row.local_port & 0xffff) == int(port):
                return int(row.pid)
        return None

    def _find_tshock_pid(self) -> int | None:
        """Finds running TShock.Server.exe PID using Win32 Toolhelp snapshot."""
        if os.name != "nt":
            return None
        try:
            from ctypes import wintypes
            TH32CS_SNAPPROCESS = 0x00000002
            class PROCESSENTRY32(ctypes.Structure):
                _fields_ = [
                    ("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)
                ]
            hSnap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if not hSnap or hSnap == -1:
                return None
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            res = ctypes.windll.kernel32.Process32FirstW(hSnap, ctypes.byref(pe))
            found_pid = None
            while res:
                exe = pe.szExeFile.lower()
                if "tshock.server" in exe or "tshock" in exe:
                    found_pid = int(pe.th32ProcessID)
                    break
                res = ctypes.windll.kernel32.Process32NextW(hSnap, ctypes.byref(pe))
            ctypes.windll.kernel32.CloseHandle(hSnap)
            return found_pid
        except Exception:
            return None

    def is_server_log_locked(self) -> bool:
        log_file = ROOT / "ServerLog.txt"
        if not log_file.is_file():
            return False
        try:
            with open(log_file, "a+b") as f:
                pass
            return False
        except OSError:
            return True

    def _listening_server_pid(self) -> int | None:
        pid = self._listening_pid(GAME_PORT)
        if pid is not None:
            return pid
        pid = self._listening_pid(REST_PORT)
        if pid is not None:
            return pid
        return self._find_tshock_pid()

    def _resource_snapshot(self) -> dict:
        if os.name != "nt":
            return {}
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        def ft_value(v):
            return (int(v.dwHighDateTime) << 32) | int(v.dwLowDateTime)
        now = time.perf_counter()
        result = {"time": now}
        try:
            installed = ctypes.c_ulonglong()
            if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(installed)):
                result["ram_total"] = int(installed.value) * 1024
        except Exception:
            pass
        pid = None
        try:
            pid = self._listening_server_pid()
        except Exception:
            pass
        if pid is None and self.proc is not None and self.proc.poll() is None:
            pid = self.proc.pid
        if pid:
            result["proc_pid"] = int(pid)
            handle = None
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
                kernel32.OpenProcess.restype = ctypes.c_void_p
                kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel32.CloseHandle.restype = ctypes.c_int
                kernel32.GetProcessTimes.argtypes = [ctypes.c_void_p, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
                kernel32.GetProcessTimes.restype = ctypes.c_int
                handle = kernel32.OpenProcess(0x1000 | 0x0400 | 0x0010, 0, int(pid))
                if handle:
                    c_time, e_time, k_time, u_time = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                    if kernel32.GetProcessTimes(handle, ctypes.byref(c_time), ctypes.byref(e_time), ctypes.byref(k_time), ctypes.byref(u_time)):
                        result["proc_cpu"] = ft_value(k_time) + ft_value(u_time)
                    counters = PROCESS_MEMORY_COUNTERS()
                    counters.cb = ctypes.sizeof(counters)
                    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
                    get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.c_ulong]
                    get_memory.restype = ctypes.c_int
                    if get_memory(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
                        result["proc_ram"] = int(counters.WorkingSetSize)
            except Exception as e:
                log_error("Error in process resource snapshot", e)
            finally:
                if handle:
                    try:
                        ctypes.windll.kernel32.CloseHandle(handle)
                    except Exception:
                        pass
        return result

    def get_metrics_now(self) -> dict:
        current = self._resource_snapshot()
        previous = self.metric_previous
        self.metric_previous = current
        pid = current.get("proc_pid")
        if not pid:
            return {
                "running": False,
                "pid": None,
                "cpu": 0.0,
                "cpu_percent": 0.0,
                "ram_mb": 0.0,
                "memory_mb": 0.0,
                "ram_percent": 0.0,
                "memory_percent": 0.0
            }
        
        cpu = 0.0
        if previous and "proc_cpu" in current and "proc_cpu" in previous and current.get("proc_pid") == previous.get("proc_pid"):
            elapsed = current.get("time", 0) - previous.get("time", 0)
            if elapsed > 0:
                delta = current["proc_cpu"] - previous["proc_cpu"]
                cores = max(1, os.cpu_count() or 1)
                cpu = max(0.0, min(100.0, delta / (elapsed * 10_000_000 * cores) * 100))
        
        ram_bytes = current.get("proc_ram", 0)
        ram_mb = ram_bytes / (1024 * 1024)
        ram_total = current.get("ram_total", 1) or 1
        ram_pct = (ram_bytes / ram_total) * 100

        return {
            "running": True,
            "pid": pid,
            "cpu": cpu,
            "cpu_percent": cpu,
            "ram_mb": ram_mb,
            "memory_mb": ram_mb,
            "ram_percent": ram_pct,
            "memory_percent": ram_pct
        }

    def _start_background_timer(self):
        def loop():
            while not self.closing:
                try:
                    self._tick()
                except Exception as e:
                    log_error("Tick error", e)
                time.sleep(5.0)
        threading.Thread(target=loop, daemon=True).start()

    def _tick(self):
        # 1. Update running state
        pid = self._listening_server_pid()
        is_running = pid is not None or (self.proc is not None and self.proc.poll() is None)
        self.server_port_open = is_running
        self.server_port_known = True
        self.server_refresh_at = time.monotonic()
        
        # 2. If running, poll REST status
        if is_running:
            try:
                data = self.api("v2/server/status", {"players": "true"})
                if isinstance(data, dict):
                    self.status = data
                    self.api_ok = True
                    self.players = self.get_players()
            except Exception:
                pass
        else:
            self.api_ok = False
            self.players = []

        # Notify UI if window ready
        global CURRENT_PANEL_WINDOW
        if CURRENT_PANEL_WINDOW:
            state = self.get_ui_state()
            try:
                CURRENT_PANEL_WINDOW.evaluate_js(f"updateServerState({json.dumps(state)})")
            except Exception:
                pass
            
            # Only poll resource metrics if on the metrics page!
            if self.current_page == "metrics":
                try:
                    metrics = self.get_metrics_now()
                    CURRENT_PANEL_WINDOW.evaluate_js(f"updateMetrics({json.dumps(metrics)})")
                except Exception:
                    pass

    def toggle_server(self):
        if self.is_server_running():
            self.stop_server()
        else:
            self.start_server()

    def _read_setup_code(self) -> str:
        code_file = self._profile_dir() / "setup-code.txt"
        if not code_file.is_file():
            code_file = ROOT / "tshock" / "setup-code.txt"
        if code_file.is_file():
            try:
                txt = code_file.read_text(encoding="utf-8").strip()
                if txt:
                    return txt
            except Exception:
                pass
        return ""

    def get_admin_data(self) -> dict:
        setup_code = self._read_setup_code()
        accounts = []
        groups = ["guest", "default", "vip", "admin", "superadmin"]

        # 1. Try via REST API if server is running
        if self.is_server_running() and self.api_ok:
            try:
                u_res = self.api("v2/users/list")
                if isinstance(u_res, dict) and "users" in u_res:
                    for u in u_res["users"]:
                        accounts.append({
                            "name": u.get("name") or u.get("username", "—"),
                            "group": u.get("group", "default")
                        })
                g_res = self.api("v2/groups/list")
                if isinstance(g_res, dict) and "groups" in g_res:
                    loaded_g = [g.get("name") for g in g_res["groups"] if isinstance(g, dict) and g.get("name")]
                    if loaded_g:
                        groups = loaded_g
            except Exception as e:
                log_error("Error reading admin data via REST API", e)

        # 2. Offline fallback: read SQLite database tshock.sqlite directly
        if not accounts:
            db_path = self._profile_dir() / "tshock.sqlite"
            if not db_path.is_file():
                db_path = ROOT / "tshock" / "tshock.sqlite"
            if db_path.is_file():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT Username, UserGroup FROM Users")
                    for row in cursor.fetchall():
                        accounts.append({"name": str(row[0]), "group": str(row[1])})
                    cursor.execute("SELECT GroupName FROM GroupList")
                    db_groups = [str(r[0]) for r in cursor.fetchall() if r[0]]
                    if db_groups:
                        groups = db_groups
                    conn.close()
                except Exception as e:
                    log_error(f"Error reading {db_path}", e)

        return {
            "setup_code": setup_code,
            "accounts": accounts,
            "groups": sorted(list(set(groups)))
        }

    def get_group_permissions(self, group_name: str) -> list[str]:
        perms = []
        # 1. Try REST API
        if self.is_server_running() and self.api_ok:
            try:
                res = self.api("v2/groups/read", {"group": group_name})
                if isinstance(res, dict):
                    p = res.get("permissions") or res.get("totalpermissions")
                    if isinstance(p, list):
                        return [str(x) for x in p]
            except Exception:
                pass

        # 2. Offline read from tshock.sqlite
        db_path = self._profile_dir() / "tshock.sqlite"
        if not db_path.is_file():
            db_path = ROOT / "tshock" / "tshock.sqlite"
        if db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT Commands FROM GroupList WHERE GroupName = ?", (group_name,))
                row = cursor.fetchone()
                if not row:
                    try:
                        cursor.execute("SELECT Permissions FROM Groups WHERE Name = ?", (group_name,))
                        row = cursor.fetchone()
                    except Exception:
                        pass
                if row and row[0]:
                    raw = str(row[0])
                    perms = [x.strip() for x in raw.split(",") if x.strip()]
                conn.close()
            except Exception as e:
                log_error("Error reading group permissions from sqlite", e)

        return perms

    def assign_account_group(self, username: str, group_name: str) -> dict:
        clean_user = re.sub(r'[\r\n\t\x00-\x1f"]+', "", username).strip()
        clean_group = re.sub(r'[\r\n\t\x00-\x1f"]+', "", group_name).strip()
        if not clean_user or not clean_group:
            return {"ok": False, "error": "Не указан пользователь или группа"}

        # Prevent assigning 'guest' to registered accounts: registered accounts are at least 'default' (player)
        if clean_group.lower() == "guest":
            clean_group = "default"

        executed = False

        # 1. Always update SQLite database so change is persistent across restarts
        db_path = self._profile_dir() / "tshock.sqlite"
        if not db_path.is_file():
            db_path = ROOT / "tshock" / "tshock.sqlite"
        if db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("UPDATE Users SET UserGroup = ? WHERE Username = ?", (clean_group, clean_user))
                conn.commit()
                conn.close()
                executed = True
            except Exception as e:
                log_error("Error updating group in sqlite", e)

        # 2. Live server updates: permanent account group AND online player session without reconnect!
        if self.is_server_running():
            try:
                # Update user account permanently in TShock
                self.send_command(f'/user group "{clean_user}" "{clean_group}"')
                # Update active online session in memory immediately
                self.send_command(f'/tempgroup "{clean_user}" "{clean_group}"')

                # Also find any online player connected under character name matching clean_user
                try:
                    online = self.get_players()
                    for p in online:
                        p_name = p.get("nickname") or p.get("name")
                        if p_name and (p_name.lower() == clean_user.lower() or str(p.get("account", "")).lower() == clean_user.lower()):
                            self.send_command(f'/tempgroup "{p_name}" "{clean_group}"')
                except Exception:
                    pass

                role_names = {
                    "admin": "Администратор",
                    "default": "Игрок",
                    "guest": "Гость",
                    "vip": "VIP",
                    "superadmin": "Главный Администратор"
                }
                role_title = role_names.get(clean_group.lower(), clean_group)
                self.send_broadcast(f"★ Сервер: Игроку {clean_user} назначена роль [{role_title}]!", color_hex="00ffcc")
                executed = True
            except Exception as e:
                log_error("Error assigning live group via send_command", e)

        if executed:
            self.add_log(f"[Админка] Аккаунту «{clean_user}» назначена группа «{clean_group}» (применено в реальном времени!).", "notice")
            return {"ok": True}
        return {"ok": False, "error": "Не удалось обновить группу аккаунта"}

    def change_group_permission(self, group_name: str, permission: str, allow: bool) -> dict:
        clean_group = re.sub(r'[\r\n\t\x00-\x1f"]+', "", group_name).strip()
        clean_perm = re.sub(r'[\r\n\t\x00-\x1f"]+', "", permission).strip()
        if not clean_group or not clean_perm:
            return {"ok": False, "error": "Неверные параметры"}

        subcmd = "addperm" if allow else "delperm"
        cmd = f'/group {subcmd} "{clean_group}" {clean_perm}'
        res = self.send_command(cmd)
        if res.get("ok"):
            self.add_log(f"[Права] Группе {clean_group} {'добавлено' if allow else 'удалено'} право {clean_perm}", "notice")
        return res

    def start_server(self):
        self._ensure_tshock_roles_and_permissions()
        running_pid = self._listening_server_pid()
        if running_pid or self.is_server_running() or self.is_server_log_locked():
            self.add_log(f"Сервер TShock уже работает (PID {running_pid or 'активен'}). Панель подключена.", "notice")
            self.server_port_open = True
            self.server_port_known = True
            self._tick()
            return
        world_filename = self.current_profile.get("world", "")
        world_path = WORLDS_DIR / world_filename if world_filename else None
        if not world_path or not world_path.is_file():
            self.add_log("Для запуска сервера сначала создайте мир (вкладка «Миры» -> «Создать мир») или выберите существующий.", "error")
            return
        
        _, s = config_settings(self._profile_config())
        slots = max(1, min(64, int(prop(s, "MaxSlots", default=8) or 8)))

        env = os.environ.copy()
        runtime = ROOT / "dotnet"
        env["DOTNET_ROOT"] = str(runtime)
        env["PATH"] = str(runtime) + os.pathsep + env.get("PATH", "")

        args = [
            str(SERVER), "-configpath", str(self._profile_dir()),
            "-world", str(world_path), "-port", str(GAME_PORT),
            "-maxplayers", str(slots)
        ]

        def work():
            try:
                self.add_log(f"Запускаю TShock для сервера «{self.current_profile['name']}»...", "notice")
                self.proc = subprocess.Popen(
                    args, cwd=str(ROOT), env=env, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                proc = self.proc
                
                # Background stream reader
                def reader():
                    try:
                        for line in proc.stdout:
                            self.add_log(line.rstrip())
                    except Exception as e:
                        log_error("Error reading server stdout", e)
                threading.Thread(target=reader, daemon=True).start()

                # Wait for exit
                code = proc.wait()
                self.add_log(f"Сервер завершил работу (код {code}).", "notice")
                self.proc = None
                self.server_port_open = False
                self._tick()
            except Exception as e:
                self.proc = None
                log_error("Failed to start server", e)
                self.add_log(f"Не удалось запустить сервер: {e}", "error")

        threading.Thread(target=work, daemon=True).start()

    def stop_server(self):
        own = self.proc is not None and self.proc.poll() is None
        if not own and not self.server_port_open and not self.api_ok:
            self.add_log("Сервер уже выключен.", "notice")
            return
        
        self.add_log("Отправляю команду сохранения и выключения сервера...", "notice")
        def work():
            # 1. Try REST API off
            try:
                self.api("v2/server/off", {"confirm": "true", "nosave": "false", "message": "Server shutting down"})
            except Exception:
                if self.proc and self.proc.poll() is None and self.proc.stdin:
                    try:
                        self.proc.stdin.write("exit\n")
                        self.proc.stdin.flush()
                    except Exception:
                        pass
            
            p = self.proc
            if p and p.poll() is None:
                try:
                    p.wait(timeout=30)
                    self.add_log("Сервер успешно остановлен; мир сохранён.", "notice")
                except subprocess.TimeoutExpired:
                    self.add_log("Сервер ещё завершает работу (сохраняет мир). Не прерываю процесс.", "notice")
            else:
                for _ in range(20):
                    time.sleep(0.5)
                    if not self.is_server_running():
                        break
                self.add_log("Сервер остановлен.", "notice")
            self._tick()

        threading.Thread(target=work, daemon=True).start()

# --- JS API Bridge ---
class PanelApi:
    def __init__(self, controller: PanelController):
        self._ctrl = controller

    def get_initial_state(self):
        return self._ctrl.get_ui_state()

    def toggle_server(self):
        self._ctrl.toggle_server()
        return self._ctrl.get_ui_state()

    def get_players(self):
        return self._ctrl.get_players()

    def kick_player(self, player_name: str, reason: str = ""):
        return self._ctrl.kick_player(player_name, reason)

    def send_command(self, cmd: str):
        return self._ctrl.send_command(cmd)

    def send_chat(self, msg: str):
        return self._ctrl.send_chat(msg)

    def send_broadcast(self, text: str, color_hex: str = "00ffcc"):
        return self._ctrl.send_broadcast(text, color_hex)

    def get_worlds_list(self):
        return self._ctrl.get_worlds_list()

    def get_world_details(self, filename: str):
        return self._ctrl.get_world_details(filename)

    def get_game_documents_worlds(self):
        return self._ctrl.get_game_documents_worlds()

    def import_world_from_path(self, source_path: str):
        return self._ctrl.import_world_from_path(source_path)

    def browse_and_import_world(self):
        if self._ctrl.is_server_running():
            return {"ok": False, "error": "Остановите сервер перед добавлением мира."}
        picked = None
        try:
            if self._ctrl._window:
                res = self._ctrl._window.create_file_dialog(
                    1, # webview.OPEN_DIALOG
                    file_types=('Миры Terraria (*.wld)', 'Все файлы (*.*)')
                )
                if res and len(res) > 0:
                    picked = res[0]
        except Exception:
            pass
        if not picked:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                picked = filedialog.askopenfilename(
                    title="Выберите файл мира Terraria (.wld)",
                    filetypes=[("Миры Terraria", "*.wld"), ("Все файлы", "*.*")]
                )
                root.destroy()
            except Exception:
                pass
        if picked:
            return self._ctrl.import_world_from_path(picked)
        return {"ok": False, "cancelled": True}

    def set_active_world(self, filename: str):
        return self._ctrl.set_active_world(filename)

    def remove_world_from_list(self, filename: str):
        return self._ctrl.remove_world_from_list(filename)

    def rename_world(self, old_filename: str, new_name: str):
        return self._ctrl.rename_world(old_filename, new_name)

    def change_world_mode(self, mode: str):
        return self._ctrl.change_world_mode(mode)

    def create_world_background(self, name: str, size: int, mode: int, seed: str = ""):
        return self._ctrl.create_world_background(name, size, mode, seed)

    def get_world_gen_status(self):
        return getattr(self._ctrl, "world_gen_info", {"active": False})

    def get_profiles_data(self):
        return self._ctrl.get_profiles_data()

    def switch_profile(self, profile_id: str):
        return self._ctrl.switch_profile(profile_id)

    def save_server_settings(self, password: str, max_slots: int, autosave: bool):
        return self._ctrl.save_server_settings(password, max_slots, autosave)

    def get_tshock_gameplay_settings(self):
        return self._ctrl.get_tshock_gameplay_settings()

    def save_tshock_gameplay_settings(self, payload: dict):
        return self._ctrl.save_tshock_gameplay_settings(payload)

    def execute_gameplay_action(self, action: str):
        return self._ctrl.execute_gameplay_action(action)

    def delete_current_profile(self):
        return self._ctrl.delete_current_profile()

    def create_profile_wizard(self, params: dict):
        return self._ctrl.create_profile_wizard(params)

    def get_metrics_now(self):
        return self._ctrl.get_metrics_now()

    def get_admin_data(self):
        return self._ctrl.get_admin_data()

    def get_group_permissions(self, group_name: str):
        return self._ctrl.get_group_permissions(group_name)

    def assign_account_group(self, username: str, group_name: str):
        return self._ctrl.assign_account_group(username, group_name)

    def change_group_permission(self, group_name: str, permission: str, allow: bool):
        return self._ctrl.change_group_permission(group_name, permission, allow)

    def on_page_switched(self, page_name: str):
        self._ctrl.current_page = page_name

    def minimize_window(self):
        global CURRENT_PANEL_WINDOW
        if CURRENT_PANEL_WINDOW:
            try:
                CURRENT_PANEL_WINDOW.minimize()
            except Exception:
                pass

    def toggle_maximize_window(self):
        global CURRENT_PANEL_WINDOW
        if CURRENT_PANEL_WINDOW:
            try:
                if getattr(self._ctrl, "_is_maximized", False):
                    CURRENT_PANEL_WINDOW.restore()
                    self._ctrl._is_maximized = False
                else:
                    CURRENT_PANEL_WINDOW.maximize()
                    self._ctrl._is_maximized = True
            except Exception:
                pass
            return getattr(self._ctrl, "_is_maximized", False)

    def close_window(self):
        global CURRENT_PANEL_WINDOW
        if CURRENT_PANEL_WINDOW:
            try:
                CURRENT_PANEL_WINDOW.destroy()
            except Exception:
                pass
        try:
            import os
            os._exit(0)
        except Exception:
            pass

# --- Main Entry Point ---
def main():
    try:
        controller = PanelController()
        api = PanelApi(controller)
        index_html = UI_DIR / "index.html"
        icon_path = PANEL_DIR / "TerrariaPanel.ico"
        icon_arg = str(icon_path) if icon_path.exists() else None
        
        window = webview.create_window(
            title="Панель управления Terraria",
            url=str(index_html.as_uri()),
            js_api=api,
            width=1080,
            height=720,
            min_size=(680, 500),
            text_select=True,
            frameless=True,
            easy_drag=False
        )
        controller.set_window(window)
        
        # When loaded, push initial state
        window.events.loaded += lambda: window.evaluate_js(f"updateServerState({json.dumps(controller.get_ui_state())})")
        
        def on_started(w):
            if "--test-launch" in sys.argv:
                time.sleep(1)
                w.destroy()
        
        webview.start(on_started, window, debug=False, icon=icon_arg)
    except Exception as e:
        log_error("Fatal startup error", e)
        raise

if __name__ == "__main__":
    main()
