import pygame
import pygame.freetype
import numpy as np
import math
import os
import sys
import json
import io
import base64
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple, Optional, Callable
from collections import OrderedDict


def _force_window_full(dw: float, dh: float) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        info = pygame.display.get_wm_info()
        hwnd = info.get("window") if isinstance(info, dict) else None
        if not hwnd:
            return
        u = ctypes.windll.user32
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        u.SetWindowPos(int(hwnd), -1, 0, 0, int(dw), int(dh),
                       SWP_NOACTIVATE | SWP_SHOWWINDOW)
        try:
            u.SetWindowPos(int(hwnd), -1, 0, 0, int(dw), int(dh),
                           SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass
    except Exception:
        pass


def _enable_dpi_awareness() -> None:
    try:
        if sys.platform == "win32":
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                return
            except Exception:
                pass
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    except Exception:
        pass

try:
    _SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    _SCRIPT_DIR = Path.cwd()


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", "")) if _is_frozen() else _SCRIPT_DIR
    if not base:
        base = _SCRIPT_DIR
    return Path(base) / rel


def _exe_dir() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return _SCRIPT_DIR


def _user_data_dir() -> Path:
    app = "SYRUP"
    try:
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA")
            if not base:
                base = os.environ.get("APPDATA")
            if base:
                return Path(base) / app
            return Path.home() / "AppData" / "Local" / app
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / app
        xdg = os.environ.get("XDG_DATA_HOME")
        return Path(xdg) if xdg else (Path.home() / ".local" / "share" / app)
    except Exception:
        return _exe_dir()


def _resolve_save_path() -> str:
    fname = "syrup_save.json"
    portable = _exe_dir() / fname
    try:
        ud = _user_data_dir()
        ud.mkdir(parents=True, exist_ok=True)
        target = ud / fname
        if (not target.exists()) and portable.exists() and portable != target:
            try:
                target.write_bytes(portable.read_bytes())
                portable.rename(portable.with_suffix(portable.suffix + ".migrated"))
            except Exception:
                pass
        return str(target)
    except Exception:
        return str(portable)


def vlen(v) -> float:
    a = float(v[0]); b = float(v[1])
    return math.sqrt(a * a + b * b)


def ease_linear(t: float) -> float:
    return t

def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3

def ease_out_back(t: float) -> float:
    s = 1.70158
    return 1.0 + (s + 1.0) * (t - 1.0) ** 3 + s * (t - 1.0) ** 2

def ease_in_out_quad(t: float) -> float:
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0

def ease_out_expo(t: float) -> float:
    if t >= 1.0: return 1.0
    if t <= 0.0: return 0.0
    return 1.0 - 2.0 ** (-10.0 * t)


def breath_wave(phase: float, dwell: float = 0.0, mode: str = "triangle") -> float:
    p = phase % 1.0
    if mode == "sine":
        return math.sin(p * 2.0 * math.pi)
    if mode == "trapezoid":
        e = ANIM_TRAPEZOID_E
        t = (p * 2.0) % 1.0
        prog = _trapezoid_progress(t, e)
        return 1.0 - 2.0 * prog if p < 0.5 else -1.0 + 2.0 * prog
    if mode != "dwell":
        p2 = p * 2.0
        return 1.0 - 2.0 * p2 if p2 < 1.0 else (p2 - 1.0) * 2.0 - 1.0
    d = max(0.0, min(0.90, dwell)) * 0.5
    m = 0.5 - d
    if m <= 1e-6:
        return math.sin(p * 2.0 * math.pi)
    if p < d:
        return 1.0
    if p < d + m:
        t = (p - d) / m
        return 1.0 - 2.0 * (t * t * (3.0 - 2.0 * t))
    if p < 2.0 * d + m:
        return -1.0
    t = (p - (2.0 * d + m)) / m
    return -1.0 + 2.0 * (t * t * (3.0 - 2.0 * t))


ANIM_TRAPEZOID_E = 0.15


def _trapezoid_progress(t: float, e: float) -> float:
    if e <= 1e-6:
        return t
    e = min(0.45, e)
    v = (1.0 - e) / (1.0 - 2.0 * e)
    if t < e:
        u = t / e
        return 0.5 * e * (u * u * (3.0 - 2.0 * u))
    if t < 1.0 - e:
        return 0.5 * e + v * (t - e)
    u = (t - (1.0 - e)) / e
    return 1.0 - 0.5 * e * (1.0 - (u * u * (3.0 - 2.0 * u)))


class ValueTween:
    __slots__ = ("value", "from_value", "target", "duration", "ease", "t", "done")

    def __init__(self, init: float = 0.0,
                 duration: float = 0.22,
                 ease: Callable[[float], float] = ease_out_cubic) -> None:
        self.value = float(init)
        self.from_value = float(init)
        self.target = float(init)
        self.duration = max(1e-4, float(duration))
        self.ease = ease
        self.t = self.duration
        self.done = True

    def set_target(self, new_target: float,
                   duration: Optional[float] = None,
                   ease: Optional[Callable[[float], float]] = None) -> None:
        if abs(new_target - self.target) < 1e-9 and not self.done:
            return
        self.from_value = self.value
        self.target = float(new_target)
        if duration is not None:
            self.duration = max(1e-4, float(duration))
        if ease is not None:
            self.ease = ease
        self.t = 0.0
        self.done = False

    def update(self, dt: float) -> float:
        if self.done:
            return self.value
        self.t += dt
        if self.t >= self.duration:
            self.t = self.duration
            self.value = self.target
            self.done = True
        else:
            k = self.t / self.duration
            self.value = self.from_value + (self.target - self.from_value) * self.ease(k)
        return self.value

    def snap(self, v: float) -> None:
        self.value = self.from_value = self.target = float(v)
        self.t = self.duration
        self.done = True


SAVE_DEFAULTS: Dict[str, Any] = {
    "version": 1,
    "lang": "en",
    "training_unlocked_stage": 1,
    "training_done": False,
    "best_score": 0,
    "best_chain": 0,
    "best_wave": 0,
    "best_time": 0.0,
    "total_detonate": 0,
    "total_perfect": 0,
    "total_kill": 0,
    "total_runs": 0,
    "body_size": 18,
    "skin": 0,
    "fx_trail": 0,
    "fx_afterimage": True,
    "fx_energy_glow": False,
    "fx_detonate_self": False,
    "fx_swap_ghost": False,
    "fx_poem": True,
}


def load_save(path_str: str, version: int) -> dict:
    p = Path(path_str)
    if not p.exists():
        return dict(SAVE_DEFAULTS)
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or int(data.get("version", -1)) != version:
            raise ValueError("version mismatch")
        merged = dict(SAVE_DEFAULTS)
        for k in SAVE_DEFAULTS:
            if k in data:
                merged[k] = data[k]
        merged["version"] = version
        return merged
    except Exception:
        try:
            backup = p.with_suffix(p.suffix + ".corrupt")
            if backup.exists():
                backup.unlink()
            p.rename(backup)
        except Exception:
            pass
        return dict(SAVE_DEFAULTS)


def save_now(path_str: str, data: dict) -> None:
    try:
        p = Path(path_str)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(p)
    except Exception:
        pass


CONFIG: Dict[str, Any] = {
    "WIDTH": 1280, "HEIGHT": 720, "FPS": 60,

    "START_FULLSCREEN":   False,
    "WINDOW_SCALE":       3.0,
    "WINDOW_SCREEN_FIT":  0.9,
    "RESIZE_SETTLE_FRAMES": 10,
    "FULLSCREEN_BORDERLESS": True,
    "RENDER_MAX_SCALE":   3.0,
    "ADAPTIVE_VIEWPORT":  True,
    "VIEWPORT_BASE_H":    720,
    "VIEWPORT_W_MIN":     1120,
    "VIEWPORT_W_MAX":     2560,
    "FORCE_RENDER_SIZE":  [0, 0],
    "VIGNETTE_MERGE_SCALE": 2.5,
    "RENDER_SCALE_PRESET": 0.0,

    "SAVE_PATH": _resolve_save_path(),
    "SAVE_VERSION": 1,
    "FONT_PATH": "",

    "TOPGOAL_FADE": 0.5,

    "LOGO_SS": 4,
    "LOGO_BEZ_SEGMENTS": 32,
    "GLOW_ENABLE_PLAYER":  False,
    "GLOW_ENABLE_THREAT":  False,
    "GLOW_ENABLE_SPITTER": False,

    "GLOW_SIZE_P":       76, "GLOW_PEAK_P": 118, "GLOW_RING_AT_P": 0.36,
    "GLOW_RING_W_P":     0.22, "GLOW_TAIL_P": 10,
    "GLOW_SIZE_T":       68, "GLOW_PEAK_T": 132, "GLOW_RING_AT_T": 0.26,
    "GLOW_RING_W_T":     0.19, "GLOW_TAIL_T": 8,
    "GLOW_SIZE_S":       64, "GLOW_PEAK_S": 104, "GLOW_RING_AT_S": 0.30,
    "GLOW_RING_W_S":     0.20, "GLOW_TAIL_S": 8,
    "LOGO_SHADOW_SIZE":    7.5,
    "LOGO_SHADOW_ROT":   -15.0,
    "LOGO_SHADOW_ALPHA":   95,
    "LOGO_SHADOW_FILL":    22,
    "SUBPIX_STEPS": 4,

    "LOGO_ANIM_HZ":          0.16,
    "ANIM_MENU_BREATH_HZ":   0.14,
    "ANIM_MENU_SWEEP_HZ":    0.15,
    "ANIM_STUN_PULSE_HZ":    1.20,
    "ANIM_STUN_STAR_HZ":     1.10,
    "ANIM_TRAP_ROT_HZ":      0.55,

    "ANIM_LOGO_BREATH_AMP":  10.0,
    "ANIM_MENU_BREATH_AMP":  7.0,

    "ANIM_WAVE": "trapezoid",
    "ANIM_DWELL":   0.0,

    "UI_TWEEN_FAST":   0.12,
    "UI_TWEEN_NORMAL": 0.22,
    "UI_TWEEN_SLOW":   0.35,

    "SHOW_FPS": False,
    "DEBUG_ANIM": False,

    "SHAKE_MAX_OFFSET": 16.0,
    "SHAKE_DECAY": 1.8,
    "SHAKE_MAX_TRAUMA": 1.0,

    "HITSTOP_DETONATE": 4,
    "HITSTOP_PERFECT": 8,
    "HITSTOP_CANCEL": 2,

    "DEATH_SLOWMO_DURATION": 0.35,
    "DEATH_SLOWMO_SCALE": 0.30,

    "RUN_LIVES":             3,
    "RESPAWN_IFRAMES":       90,
    "RESPAWN_CLEAR_RADIUS":  240.0,
    "RESPAWN_SLOWMO":        0.30,
    "RESPAWN_HITSTOP":       10,

    "TRANSITION_DURATION": 0.25,

    "FONT_BODY_STD": 18,
    "FONT_BODY_LARGE": 21,
    "FONT_HEAD": 24,
    "FONT_MENU": 26,
    "MENU_ROW_GAP":  8,
    "MENU_ROW_Y0":   266,
    "MENU_ROW_W":    520,
    "MENU_ROW_W_MAXF": 0.52,
    "MENU_BLOCK_ORIGIN": 49,
    "MENU_BOTTOM_RESERVE": 60,
    "MENU_BLOCK_TOP_MIN": 20,
    "MENU_LOGO_Y":    104,
    "MENU_LOGO_SCALE": 0.94,
    "MENU_TITLE_Y":   168,
    "MENU_TAG_Y":     220,
    "MENU_DIV_Y":     248,
    "MENU_TAG_TRACK_CJK":   4,
    "MENU_TAG_MAX_RATIO":   0.74,
    "MENU_TAG_TRACK_LATIN": ((1, 5), (0, 5), (0, 3), (0, 1), (0, 0)),
    "MENU_TAG_SIZE":      16,
    "MENU_TAG_ICON":       1,
    "MENU_TAG_ICON_SCALE": 1.30,
    "MENU_TAG_ICON_PAD":   0.46,
    "MENU_TAG_ICON_TEETH": (0.30, 0.50, 0.68),
    "BODY_LINE_H": 28,
    "BODY_PARA_GAP": 14,

    "BG":          (11, 15, 20),
    "GRID":        (20, 24, 31),
    "GRID_STEP":   96,
    "VIGNETTE":    (7, 10, 14),
    "C_PLAYER":    (34, 211, 238),
    "C_THREAT":    (255, 107, 74),
    "C_SPITTER":   (196, 186, 108),
    "C_MARK":      (255, 255, 255),
    "G_20":        (25, 30, 38),
    "G_40":        (55, 65, 80),
    "G_60":        (100, 112, 130),
    "G_80":        (165, 175, 190),
    "SLIME_COLOR": (30, 75, 92),

    "SKINS": [
        {"name": "糖浆", "en": "SYRUP",   "color": (34, 211, 238),  "trail": "syrup",
         "tlen": 26, "twidth": 6.0, "talpha": 150, "tfade": 1.25, "ai": "shrink", "ai_n": 5, "ai_life": 0.30,
         "body": "drip", "req": None},
        {"name": "水银", "en": "MERCURY", "color": (198, 210, 230), "trail": "mercury",
         "tlen": 11, "twidth": 3.0, "talpha": 215, "tfade": 2.8, "ai": "bead",   "ai_n": 3, "ai_life": 0.12,
         "body": "spec", "req": ("train", 0)},
        {"name": "气泡", "en": "BUBBLE",  "color": (126, 232, 178), "trail": "bubble",
         "tlen": 19, "twidth": 5.0, "talpha": 140, "tfade": 1.5, "ai": "grow",   "ai_n": 5, "ai_life": 0.32,
         "body": "film", "req": ("score", 5000)},
        {"name": "油",   "en": "OIL",     "color": (178, 138, 255), "trail": "oil", "hue": True,
         "spread": 0.55, "film_pale": 0.05, "hue_span": 1.00, "sheen": 1.50, "sheen_step": 3.2,
         "film_dark": (26, 24, 46), "film_base_a": 0.55,
         "film_drift": 0.34, "film_silver": 0.08,
         "film_cycles": 2.6, "film_cross": 1.7, "film_cross_hue": 0.55,
         "film_head": 0.34, "film_step": 7.0, "film_grid": 1.0, "film_edge": 0.60,
         "film_sat": 0.80,
         "tlen": 18, "twidth": 7.0, "talpha": 165, "tfade": 1.35, "ai": "iris",   "ai_n": 4, "ai_life": 0.22,
         "body": "iris", "req": ("score", 10000)},
        {"name": "墨",   "en": "INK",     "color": (214, 228, 248), "trail": "ink",
         "ink": (72, 92, 130), "indigo": (88, 142, 202), "gold": (216, 178, 108),
         "poem_col": (124, 156, 206), "poem_a": 235, "poem_bleed": 0.34,
         "tlen": 30, "twidth": 7.5, "talpha": 235, "tfade": 0.58, "ai": "poem", "ai_n": 6, "ai_life": 0.44,
         "body": "poem", "top": True, "poem": True, "req": ("score", 20000)},
    ],
    "SKIN_UNLOCK_ALL": False,
    "POEM_SS": 6,
    "POEM_BLUR": 3,
    "POEM_HALO": 0.38,
    "POEM_SHARP": 1.0,
    "POEM_POST": 1,
    "POEM_FS": 22,
    "POEM_SOFT_PAD": 4,
    "POEM_FONT_PATH": "syrup_poem.ttf",
    "IRIS_BODY_SCALE": 0.8,
    "PV_W": 60.0,
    "PV_H": 32.0,
    "PV_CX": 28.0,
    "PV_TRAIL": 26.0,
    "PV_GLYPH": 14.0,
    "QI_CAP": 16,
    "PV_FREEZE_T": 1.7,
    "QI_ALPHA": 178,
    "QI_GROW": 10.5,
    "QI_WD": 2.5,
    "POEM_LINES": ["直挂云帆济沧海", "天生我材必有用", "人生得意须尽欢",
                   "莫使金樽空对月", "千金散尽还复来", "飞流直下三千尺",
                   "疑是银河落九天", "大鹏一日同风起", "仰天大笑出门去",
                   "长风破浪会有时"],
    "TRAIL_STYLES": ["材质", "线", "关闭"],
    "TRAIL_STYLES_EN": ["MATERIAL", "LINE", "OFF"],
    "FX_NAMES":    ["材质", "拖尾形态", "冲刺残影", "能量满微光", "引爆自反馈", "换位残留", "诗句浮现"],
    "FX_NAMES_EN": ["MATERIAL", "TRAIL", "AFTERIMAGE", "FULL ENERGY", "DETONATE FX", "SWAP GHOST", "POEM"],


    "PLAYER_SPEED":      300.0,
    "PLAYER_SMOOTH":     6.5,
    "PLAYER_MARGIN":     28,
    "PLAYER_TRAIL_LEN":  16,
    "DEATH_RADIUS":      18.0,

    "DASH_SPEED":         900.0,
    "DASH_FRAMES":        8,
    "DASH_COST":          1.0,
    "DASH_CANCEL_FREE":   True,
    "DASH_CANCEL_FREE_CHAIN": 1,
    "MAX_ENERGY":         3.0,
    "DETONATE_ENERGY_GAIN":  2.0,
    "ENERGY_REGEN":       0.35,
    "TRAINING_ENERGY_REGEN": 0.55,
    "NO_ENERGY_HINT_CD":  30,

    "CANCEL_WINDOW_FRAMES":  6,
    "RECOVERY_FRAMES":       8,
    "RECOVERY_MOVE_SCALE":   0.45,
    "CANCEL_BONUS_MULT":     1.40,
    "CANCEL_IFRAME_FRAMES":  4,
    "INPUT_BUFFER_FRAMES":   5,

    "DASH_PHASE_ON_MARK":    True,
    "PHASE_GRACE_FRAMES":    10,

    "SHADOW_MAX":            2,
    "SHADOW_LIFE_FRAMES":    180,
    "SHADOW_DRIFT_SPEED":    40.0,

    "SWAP_CD_FRAMES":        72,
    "SWAP_EMPTY_CD_FRAMES":  48,
    "SWAP_IMPACT_RADIUS":    90.0,
    "SWAP_TRAP_FRAMES":      72,

    "MARK_LIFE_FRAMES":      180,
    "MARK_HIT_RADIUS":       36.0,
    "DETONATE_RADIUS":       100.0,
    "DETONATE_SLIME_FRAMES": 240,
    "DETONATE_KNOCKBACK":    260.0,
    "DETONATE_STUN_FRAMES":  45,
    "DETONATE_EXEC_FRAMES":  150,

    "PERFECT_THREAT_DIST":   60.0,
    "PERFECT_BULLET_FRAMES": 24,
    "PERFECT_WORLD_SCALE":   0.25,

    "CHAIN_WINDOW_FRAMES":   150,
    "CHAIN_MULTS":           [1.0, 1.5, 2.0, 3.0],

    "DETONATE_BASE_SCORE":   200,
    "PERFECT_SWAP_SCORE":    150,
    "KILL_SCORE":            100,

    "SLIME_PLAYER_SLOW":     0.75,

    "AI_BASE_SPEED":         155.0,
    "AI_SPEED_RAMP":         0.6,
    "AI_MAX_SPEED":          300.0,
    "AI_RADIUS":             8,
    "AI_PREDICT":            0.35,
    "AI_SPAWN_INTERVAL":     14.0,
    "AI_MAX_COUNT":          6,
    "AI_SMOOTH":             3.5,
    "AI_TRAIL_LEN":          12,
    "WARN_TIME":             0.6,

    "SLIME_TRAP_FRAMES":     90,
    "TRAP_SLOW":             0.15,
    "TRAP_KILL_DIST":        32.0,

    "SPITTER_RADIUS":        16,
    "SPITTER_INTERVAL":      3.0,
    "SPITTER_WARN":          0.5,
    "SPITTER_PROJ_SPEED":    230.0,
    "SPITTER_PROJ_R":        6,
    "SPITTER_PROJ_LIFE":     6.0,
    "SPITTER_MAX":           3,
    "SPITTER_INTERVAL_MIN":  2.30,
    "SPITTER_SPEED_MAX":     295.0,
    "SPITTER_PHASE":         [0.35, 1.0],

    "WAVE_TABLE": [
        {"dur": 18.0, "spawn": 6.5, "batch": 1, "max": 3,  "spitter": 0, "spit_interval": 3.20, "spit_speed": 230.0},
        {"dur": 18.0, "spawn": 5.5, "batch": 1, "max": 4,  "spitter": 0, "spit_interval": 3.20, "spit_speed": 230.0},
        {"dur": 20.0, "spawn": 4.8, "batch": 1, "max": 5,  "spitter": 1, "spit_interval": 3.20, "spit_speed": 230.0},
        {"dur": 20.0, "spawn": 4.2, "batch": 2, "max": 6,  "spitter": 1, "spit_interval": 2.90, "spit_speed": 246.0},
        {"dur": 22.0, "spawn": 3.6, "batch": 2, "max": 7,  "spitter": 2, "spit_interval": 2.90, "spit_speed": 246.0},
        {"dur": 22.0, "spawn": 3.3, "batch": 2, "max": 8,  "spitter": 2, "spit_interval": 2.65, "spit_speed": 260.0},
        {"dur": 24.0, "spawn": 3.0, "batch": 2, "max": 9,  "spitter": 3, "spit_interval": 2.65, "spit_speed": 260.0},
        {"dur": 24.0, "spawn": 2.8, "batch": 2, "max": 10, "spitter": 3, "spit_interval": 2.45, "spit_speed": 274.0},
    ],
    "RUN_START_ENEMIES":     2,
    "WAVE_DURATION":         20.0,
    "WAVE_AI_SPEED_ADD":     14.0,

    "TRAINING_HINT_DURATION":  3.0,
    "TRAINING_COMPLETE_HOLD":  1.3,
    "STAGE_NAMES":  ["移动与冲刺", "标记与引爆", "影与换位", "取消后摇", "完美换位"],
    "STAGE_HINTS":  [
        "鼠标移动  ·  空格冲刺  ·  黏液会拖住敌人",
        "冲刺穿过敌人 = 标记  ·  再穿一次 = 引爆回能",
        "冲刺留下影  ·  SHIFT 与最近的影换位",
        "冲刺结束 6 帧内再按冲刺 = 取消后摇",
        "敌人贴近时按 SHIFT = 完美换位",
    ],
    "STAGE_DESCS":  ["活过 15 秒", "引爆 3 次", "换位黏住 2 个敌人", "连续 3 次取消成功", "完美换位 2 次"],
    "STAGE_GOALS":  [15.0, 3, 2, 3, 2],
    "STAGE_ENEMIES": [1, 2, 2, 1, 2],

    "CLEAR_HOLD_FRAMES":  60,
    "CLEAR_HOLD_FRAMES2": 90,
    "TOAST_DURATION": 1.5,

    "MECH_TAB_FADE": 0.15,
}


STAGE_NAMES_EN  = ["Move & Dash", "Mark & Detonate", "Shadow & Swap", "Cancel Recovery", "Perfect Swap"]
STAGE_DESCS_EN  = ["Survive 15 seconds", "Detonate 3 times", "Trap 2 enemies with swap",
                   "Chain 3 cancels in a row", "Perfect swap 2 times"]
MECH_LOCK_RUN = 6
MECH_STAGE_REQ = {
    0: [1, 2, 2, 3, 1, MECH_LOCK_RUN, 1],
    2: [1, MECH_LOCK_RUN, MECH_LOCK_RUN, 1],
}
CTRL_STAGE_REQ = [1, 1, 3, 1, 1, 1, 2, 1]

STAGE_HINTS_EN  = [
    "Move with mouse  ·  SPACE to dash  ·  slime slows enemies",
    "Dash through an enemy = MARK  ·  dash again = DETONATE (refund energy)",
    "Dash leaves a shadow  ·  SHIFT swaps with nearest shadow",
    "Press dash again within 6 frames after dash = cancel recovery",
    "Press SHIFT when an enemy is close = PERFECT SWAP",
]

STR_ZH = {
    "title": "SYRUP", "tagline": "黏住它们，或者被黏住",
    "training": "训练", "stage": "关卡", "run": "实战",
    "run_locked": "实战 · 未解锁", "unlock_hint": "完成全部训练后解锁",
    "run_hint": "无限模式 · 追分",
    "best_score": "最高分", "best_chain": "最高链", "best_wave": "最高波",
    "menu_hint": "↑↓ 选择  ·  ←→ 切换关卡  ·  ENTER 确认  ·  ESC 菜单  ·  F11 全屏",
    "locked": "未解锁", "paused": "PAUSED",
    "continue": "继续", "restart_run": "重开本局", "restart_stage": "重开本关",
    "back_menu": "回菜单", "exit_run": "退出",
    "controls": "操作", "goal_col": "当前关卡目标", "how_to": "怎么做",
    "progress": "进度", "score": "分数", "chain": "链", "detonate": "引爆",
    "perfect": "完美", "restart": "重开", "menu": "菜单", "seconds": "秒",
    "run_goal": "生存并追分", "max_chain": "最高链", "detonate_count": "引爆",
    "perfect_count": "完美换位", "score_detonate": "引爆分", "score_perfect": "完美分",
    "score_kill": "击杀分",
    "esc_title": "菜单",
    "mech": "游戏机制", "settings": "设置", "quit_game": "退出游戏",
    "clear_save": "清除存档", "clear_gray": "清除存档（按住 C）",
    "clear_page_title": "确认清除存档",
    "clear_desc_1": "以下数据将被永久删除：",
    "clear_desc_2": "再次按住 C 确认",
    "clear_success": "存档已清除",
    "fullscreen_title": "全屏",
    "fs_on": "开", "fs_off": "关",
    "shake_title": "震屏强度",
    "shake_0": "关", "shake_5": "弱", "shake_10": "强",
    "render_scale_title": "渲染倍率",
    "rs_names": ["自动", "720p", "1080p", "2K", "2.5K", "4K"],
    "rs_heavy": "高负载", "rs_mid": "偏高",
    "text_size_title": "文字大小",
    "text_size_std": "标准", "text_size_large": "大",
    "lang_title": "语言",
    "lang_zh": "中文", "lang_en": "English",
    "back": "返回",
    "mech_lock": "未解锁",
    "mech_lock_stage": "完成训练第 {n} 关后解锁",
    "mech_lock_run": "完成全部训练后解锁",
    "mech_tabs": ["基础规则", "操作说明", "失败条件"],
    "k_move": "鼠标移动", "k_move_d": "瞄准 / 决定冲刺方向",
    "k_lmb": "鼠标左键", "k_lmb_d": "冲刺", "k_space_d": "冲刺",
    "k_shift_d": "与最近的影换位", "k_r_d": "重开", "k_esc_d": "菜单 / 暂停",
    "k_tab_d": "练习模式", "k_escm": "ESC（菜单）", "k_escm_d": "保存并退出",
    "k_f11_d": "全屏 / 窗口（也可用 Alt+Enter）",
    "k_p_d": "暂停面板",
    "ctrl_hint": "鼠标移至条目查看说明",
    "ctrl_rows": [
        ("鼠标移动", "瞄准", "决定冲刺方向。玩家始终以鼠标所在方位为准，移动与冲刺均沿该方向进行。"),
        ("鼠标左键 / 空格", "冲刺", "沿鼠标方向高速位移一段距离，消耗一格能量。路径经过敌人时为其附加标记。"),
        ("Shift", "换位", "瞬移至距鼠标最近的一枚影所在位置，起点与终点各产生一次范围冲击。"),
        ("R", "重开", "立即重新开始当前关卡或当前一局，进度不计入存档。"),
        ("ESC", "菜单", "打开或关闭暂停菜单。菜单中可查看机制、调整设置并退出游戏。"),
        ("F11", "全屏", "在全屏与窗口之间切换，效果与 Alt+Enter 相同。"),
        ("Tab", "练习", "在训练关卡内开启练习模式，敌人不再主动追击，便于反复演练操作。"),
        ("P", "暂停", "暂停当前关卡或当前一局，再次按下即可继续。"),
    ],
    "appearance": "外观",
    "appr_hint": "左右键切换  ·  回车进入材质图鉴  ·  每项独立生效  ·  即时保存",
    "appr_sub": "材质决定颜色与拖尾形态",
    "appr_sub2": "可单独开关的特效",
    "on": "开", "off": "关",
    "skin_gallery": "材质图鉴",
    "skin_gallery_sub": "选中已解锁的材质即可使用",
    "skin_gallery_hint": "↑↓ 选择  ·  回车或点击装备  ·  ESC 返回",
    "skin_in_use": "使用中",
    "skin_default": "初始解锁",
    "skin_req_score": "最高分达到 {n} 解锁",
    "skin_req_train": "完成全部训练后解锁",
    "skin_locked": "未解锁",
}
STR_EN = {
    "title": "SYRUP", "tagline": "trap 'em or be trapped",
    "tagline_pre": "trap", "tagline_post": "'em or be trapped",
    "training": "TRAINING", "stage": "STAGE", "run": "RUN",
    "run_locked": "RUN · LOCKED", "unlock_hint": "Complete all training to unlock",
    "run_hint": "Endless · chase the score",
    "best_score": "BEST", "best_chain": "CHAIN", "best_wave": "WAVE",
    "menu_hint": "↑↓ select  ·  ←→ change stage  ·  ENTER confirm  ·  ESC menu  ·  F11 fullscreen",
    "locked": "LOCKED", "paused": "PAUSED",
    "continue": "CONTINUE", "restart_run": "RESTART", "restart_stage": "RESTART STAGE",
    "back_menu": "MENU", "exit_run": "EXIT",
    "controls": "CONTROLS", "goal_col": "CURRENT GOAL", "how_to": "HOW TO",
    "progress": "Progress", "score": "SCORE", "chain": "CHAIN", "detonate": "DETONATE",
    "perfect": "PERFECT", "restart": "Restart", "menu": "Menu", "seconds": "s",
    "run_goal": "survive & score", "max_chain": "Max Chain", "detonate_count": "Detonate",
    "perfect_count": "Perfect Swap", "score_detonate": "Detonate pts", "score_perfect": "Perfect pts",
    "score_kill": "Kill pts",
    "esc_title": "MENU",
    "mech": "MECHANICS", "settings": "SETTINGS", "quit_game": "QUIT",
    "clear_save": "CLEAR SAVE", "clear_gray": "CLEAR SAVE (hold C)",
    "clear_page_title": "CONFIRM CLEAR",
    "clear_desc_1": "The following will be permanently deleted:",
    "clear_desc_2": "Hold C again to confirm",
    "clear_success": "Save cleared",
    "fullscreen_title": "Fullscreen",
    "fs_on": "ON", "fs_off": "OFF",
    "shake_title": "Screen shake",
    "shake_0": "Off", "shake_5": "Low", "shake_10": "High",
    "render_scale_title": "Render scale",
    "rs_names": ["Auto", "720p", "1080p", "2K", "2.5K", "4K"],
    "rs_heavy": "heavy", "rs_mid": "high",
    "text_size_title": "Text size",
    "text_size_std": "Standard", "text_size_large": "Large",
    "lang_title": "Language",
    "lang_zh": "中文", "lang_en": "English",
    "back": "Back",
    "mech_lock": "LOCKED",
    "mech_lock_stage": "Unlocks after Training Stage {n}",
    "mech_lock_run": "Unlocks after all training stages",
    "mech_tabs": ["Basics", "Controls", "Fails"],
    "k_move": "Mouse", "k_move_d": "Aim / decide dash direction",
    "k_lmb": "LMB", "k_lmb_d": "Dash", "k_space_d": "Dash",
    "k_shift_d": "Swap with nearest shadow", "k_r_d": "Restart", "k_esc_d": "Menu / Pause",
    "k_tab_d": "Practice mode", "k_escm": "ESC (menu)", "k_escm_d": "Save and quit",
    "k_f11_d": "Fullscreen / window (or Alt+Enter)",
    "k_p_d": "Pause panel",
    "ctrl_hint": "Hover an entry to read its description",
    "ctrl_rows": [
        ("Mouse move", "Aim", "Sets the dash direction. The player moves and dashes toward the cursor at all times."),
        ("LMB / Space", "Dash", "Displaces the player rapidly toward the cursor, costing one energy unit. Enemies along the path become marked."),
        ("Shift", "Swap", "Teleports the player to the shadow nearest the cursor. Both endpoints release a shock that traps nearby enemies."),
        ("R", "Restart", "Restarts the current stage or run immediately. Progress from the attempt is discarded."),
        ("ESC", "Menu", "Opens or closes the pause menu, where rules, settings and quitting are available."),
        ("F11", "Fullscreen", "Toggles between fullscreen and windowed mode. Alt+Enter does the same."),
        ("Tab", "Practice", "Enables practice mode inside a training stage. Enemies stop pursuing, allowing free rehearsal."),
        ("P", "Pause", "Pauses the current stage or run. Press again to resume."),
    ],
    "appearance": "APPEARANCE",
    "appr_hint": "LEFT/RIGHT to change  ·  ENTER opens the gallery  ·  each option applies alone  ·  saved instantly",
    "appr_sub": "Material sets color and trail",
    "appr_sub2": "Effects you can toggle one by one",
    "on": "ON", "off": "OFF",
    "skin_gallery": "MATERIAL GALLERY",
    "skin_gallery_sub": "Pick any unlocked material to equip it",
    "skin_gallery_hint": "↑↓ select  ·  ENTER or click to equip  ·  ESC back",
    "skin_in_use": "IN USE",
    "skin_default": "AVAILABLE",
    "skin_req_score": "Reach {n} points to unlock",
    "skin_req_train": "Complete all training to unlock",
    "skin_locked": "LOCKED",
}


def _collect_font_candidates() -> List[str]:
    cands: List[str] = []
    if sys.platform == "win32":
        wdir = Path("C:/Windows/Fonts")
        for n in ["msyh.ttc", "msyhbd.ttc", "msyhl.ttc",
                  "Deng.ttf", "simhei.ttf", "simsun.ttc"]:
            p = wdir / n
            if p.exists():
                cands.append(str(p))
    fp = CONFIG.get("FONT_PATH", "")
    if fp:
        cands.append(fp)
    try:
        import matplotlib
        base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        for name in ["simhei.ttf", "msyh.ttc", "NotoSansCJK-Regular.ttc",
                     "SourceHanSansSC-Regular.otf", "wqy-microhei.ttc"]:
            p = base / name
            if p.exists():
                cands.append(str(p))
    except Exception:
        pass
    if sys.platform == "win32":
        sys_names = ["Microsoft YaHei", "微软雅黑", "SimHei", "黑体",
                     "Arial Unicode MS", "SimSun", "宋体"]
    elif sys.platform == "darwin":
        sys_names = ["PingFang SC", "Heiti SC", "Hiragino Sans GB",
                     "STHeiti", "Arial Unicode MS"]
    else:
        sys_names = ["WenQuanYi Micro Hei", "Noto Sans CJK SC",
                     "Source Han Sans SC", "Droid Sans Fallback",
                     "Arial Unicode MS"]
    for n in sys_names:
        try:
            p = pygame.font.match_font(n)
            if p and Path(p).exists():
                cands.append(p)
        except Exception:
            pass
    seen = set(); out = []
    for c in cands:
        if c not in seen:
            seen.add(c); out.append(c)
    return out


def _font_is_good_cjk(path: str) -> bool:
    try:
        if not pygame.freetype.get_init():
            pygame.freetype.init()
        ft = pygame.freetype.Font(path, 32)
    except Exception:
        return False
    try:
        arrs = []
        for ch in ("糖", "浆", "黏"):
            s, _ = ft.render(ch, fgcolor=(255, 255, 255))
            a = pygame.surfarray.array3d(s)
            if int(a.sum()) == 0:
                return False
            arrs.append(a)
    except Exception:
        return False
    for i in range(len(arrs)):
        for j in range(i + 1, len(arrs)):
            if arrs[i].shape == arrs[j].shape and np.array_equal(arrs[i], arrs[j]):
                return False
    return True


def _dump_cjk_fonts() -> None:
    try:
        names = sorted(pygame.font.get_fonts())
    except Exception:
        names = []
    print("--- available fonts ---")
    for n in names:
        print("  ", n)
    print("-----------------------")


def _bundled_font() -> Optional[str]:
    for name in ("wqy-microhei-subset.ttf", "wqy-microhei.ttc",
                 "wqy-microhei.ttf", "NotoSansCJK-Regular.ttc"):
        p = _resource_path("assets/fonts") / name
        if p.exists():
            return str(p)
    return None


_POEM_FONT_B64 = (
    "AAEAAAAOAIAAAwBgR1BPU0R2THUAAKU8AAAAIEdTVUJEdkx1AAClXAAAACBPUy8ypGAP/AAAAWgAAABgY21hcCjIo8kAAAJMAAAC"
    "JGdhc3AAAAAQAAClNAAAAAhnbHlm/V+UWgAABPwAAJ42aGVhZBlT8BUAAADsAAAANmhoZWEHXgdnAAABJAAAACRobXR4DBILxgAA"
    "AcgAAACEbG9jYZR5urgAAAR4AAAAhG1heHAASgGXAAABSAAAACBuYW1lKXk/pgAAozQAAAHecG9zdP+fADIAAKUUAAAAIHByZXBo"
    "BoyFAAAEcAAAAAcAAQAAAAIAxfLiYhNfDzz1AAMD6AAAAADParTLAAAAAObk9tIAEv+CA9oDTgAAAAYAAgAAAAAAAAABAAADcP+I"
    "AAAD6AASAA4D2gPoAAAAAAAAAAAAAAAAAAAAAQABAAAAQQGWAAgAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAQD3QGQAAUAAAKKAlgA"
    "AABLAooCWAAAAV4AMgEwAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAFpZRUMAwE4Ank8DcP+IAAAD6AF1AAAAAQAAAAAB+gL4"
    "AAAAIAACA+gAhABJAEEAGwA9ADIAMQApABsAHQDPAHUApAA1AKcAYwBuAG4AVgAlACoASQAoAD8AbQBbADUAHAENAEYATgDcAIAA"
    "IwBGABkAPgA0ADEAKwBXACUAVQBMAJYAHQA8ABIAiQBeAE4AUAA5AEYAHQArAEYAHAApAEMAnABDADMAkQAtAAAAAgAAAAMAAAAU"
    "AAMAAQAAABQABAIQAAAAgACAAAYAAE4ATglOC05dTpFOuk7wTxpPf1H6UlFTQ1O7VAxZDVknWSlb+Vw6XD1eBl+XX8VhD2IRYwJl"
    "Y2XlZfZmL2cJZ1BnZWo9ayJsp2yzbUFtTm1qbXd1H3UodZF29Hg0enp7EYOrhD2ITIvXjXeP2JFSkdGU9pV/leiYe5jOmN6eT///"
    "AABOAE4JTgtOXU6RTrpO8E8aT39R+lJRU0NTu1QMWQ1ZJ1kpW/lcOlw9XgZfl1/FYQ9iEWMCZWNl5WX2Zi9nCGdQZ2VqPWsibKds"
    "s21BbU5tam13dR91KHWRdvR4NHp6exGDq4Q9iEyL1413j9iRUpHRlPaVf5XomHuYzpjenk///7IBsfmx+LGnsXSxTLEXsO6wiq4Q"
    "rbqsyaxSrAKnAqbppuikGaPZo9eiD6B/oFKfCZ4InRiauJo3mieZ75kXmNGYvZXmlQKTfpNzkuaS2pK/krOLDIsEipyJOof7hbaF"
    "IHyHe/Z36HRecr9wX27mbmhrRGq8alRnwmdwZ2Fh8QABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAC4Af+FsASNAAAAAGAAoQExAbcCiANtA+EFGAZUB8cI3QprCvsMAwz7DnUPPBAfERER3hLaFB8Vsha6GHwaCRtt"
    "HTsd8h8DIDghCCJQI6Ek6CcvKDkpoSr3LH8t2y9xMVUyTDNxNW42uzi5Oec7bTz9PsM/1UE7QqlD3UV7Ru9IhUlbSghLVUxiTQ5P"
    "GwACAIT/rQNvA04AFwA8AAABMh4CBwYHBgYHBgclIiY3NjY3Ejc2NwMGFjY3Mj4CMhcWFjM0Njc2Njc2JgYHIiYmIiYjIiIjEAMG"
    "BgMMFCQcDwIJFRMhCAdm/kAnOwECEgosEAdmbQEkPSMKO0tKNwgaKxIXEAoNAwImPSIIOExMOAgZLRInBhIDSh8uMBFY1LPjMBsC"
    "BCIcLJZqAaZwGwL81RAJAgECAgEBBAN0+4dNbB8QCQIBAQEB/vL+yDFDAAABAEkBCQOgAbsAJwAAATY2FxYWFxYWFxYGJy4CIyIG"
    "BwYHBiInJiY1JjY3NjY3Njc2NjMyAv0QFCEhFhALBwEEGyEZBnRLT/sXYQUCJAkSMwIXBzBQYlAiJa0rNAGxCQEHBgsQCw8WJh4F"
    "AwUYDgYbCAQFCjAGBBgDDg0JBwQECQAAAwBBABoDpQKsACgAQwBcAAAlNjIXFhcWFhUUBgcGJicmJgYHBgcGIgYHIiYnJiMiJicm"
    "NzY2NzY3NiU2NhYyFxYWBwYHBicmBwYGBwYmJyYmJyY3NhM2NhYWFxYGBwYGJyYGBwYjIiYjIicnNzYDHgcNDhIQJR4XCwg/CAOa"
    "SDNanSMLLCEYDxMZBAQJAwIPDBQj79i4/oVCFTkbFBMEDwsGDSUTJChVBwYLFRMNBQkJDLwoFRJFCg8CEQoSFSF0LioLBicDDQMB"
    "N1DXBgkIAgYaGQ4lAwQJBAMRCQQHJAobAQMNERMMChALBwgsCQfaCwgEEhIbEA0HDxIJAgQSBQYCDAkNDRUICAEMBA0GCwcKOw4J"
    "AgYLCxAQHh0REhcAAgAb/7QDrQMQABIAWQAAATYzMhYXHgIHBicuAzU0NhM2FhcWFgcUBgcGBicmBwYGBwYXFgcGBhcWBhQOAhQH"
    "BycmJyYmNTQmEjU1BwYHBgYjIgYVFCcmJyY3NjM+Ajc3NjMyNgJVCB0TEhwmAwoJICELLyAVFu8LQQkHFwIGCBAUDSN3QJgDAwoq"
    "EgcKAgEBDgkHDw4MDAIFAQECGSNyGgYMDCczEBExaAQEIWHIK1V6NyAGAb4CBxMcEB8SQycNMDATAwMJAVAEAgYDJhQOCQQKAQcR"
    "AwEMAwIRTxUFciwqOKpISwUYEBAVFAMDI1lcOAGcDA0EAxUFBxEGFBoICyEWAQcVEQQIDQcAAAEAPf/OA6wC8wCKAAABNjYzMhYX"
    "FhYHDgIXFjY3NhYXFhYVFAYHBgYHBgcGBwYWFxYXFhYXFjY3NjY1NDc3Fx4CBgYHBgYHBicmJicmJicmJyYmNzYnJjY3NiMiBwYG"
    "BwYGFRQHBgcGFRQHBgcGBwYHBiY3Njc2Njc2NzY3NzY2NzYmBwYGBwYiJyYmNzY2MjY3NjY3NgFiAwsFByQFBQEDBg4JAgN0EA4S"
    "EAwEBAsOBQQPBwMFBAEGBQMDJA8u0xQIGQYGAgIGDwcQAgQ3ExowVi0mIB0WIhQGAwQEAgIMBRgKBFEKBgQHDSQaEAwaBhAdLiof"
    "CAMFBQwMSRARFBYTDAYFAwICBw87Cw4QEg8EBQQtBC4lGQ0DCwK+FSAeCgkOEx5iKAQBEQUFCgcECA8PCQYJEwggIBERE1oPEQoP"
    "JAMNBQwGLgkICwoNDEkeMhYHCSAFBQUHChMQFhgmRRJsBAIDA0cOTQ4BCRchFwYNRjYVEAIFHAcMFisoCwQBBwsMDF0YGCsuMSIQ"
    "GQgFAgIFHAYKCAYGCg4cFAwIBwolAAADADIACgO5ArkATQB7AJYAAAE2FxYyFhcWBgcGBgcGIhQHBhcWNzY3NjYnJj8CNhYXFhYX"
    "FgYHBhUUBgcGJjU0JicmBgcGBgcGBiMiBgcGJicmJyY2NzY0NjY3NzY2JTYWFxYXFhYGBwYmJyYmJyYGBwYHBgcGIgYHBicmIyIm"
    "JyY2NzY3Njc2NzY2JCU2NBcyFxYWFxYWFRQGBwYGJyYHBgcGJyY3NgG4DwoGCRoDBQoJCVIKCAsIDQwMSz0gDwMDBAUFGxQOExk0"
    "BgoCDAYRCRFQCwIBCgQFHA4RPQ0PEy83JAUDAwYDBwgYExUhDUABdgU4CgwTGhEWGg8NDy4aJzupHSJNeTUUCR0JGRcMAwUUAgIM"
    "Giw6Jx1RQyk9ASn+lSwSBRInFQsJBQQGFQ4SFiElKBEuKRENAV4MDgUgCgoeBgNGCwkHCg4BAQsJFgoIDA0UFAEBBAwRMRYiQQgD"
    "BAUNAwZEEwYHCgsBCxAiCgsWDQICEx8UAgMcBgcPDxkYJw9WdgMEBgUJCy4pBgMCCBkHAwMCBQQKERkKLgIHFAoZCQodDRUKCAUR"
    "BQUJB+EGCAICBQcLCA4WFg4FEAQEBQQEFgoqJx0XAAEAMQAuA7UClABNAAABNjMyFhcWBgcGBhcWFxYWFxYXFhcWFjIWFxYWFRQG"
    "Bw4DJicmJycuAicnBw4GBwYGIyI3Njc2NzY0NjU0NzY3Njc2NzY2Ab4KAwQhCg8FFyIvAgMaFy4qQDhGQhgkDwQWFREFBwwgMxYU"
    "GYZeIQwSPBcYBwgaGjQRIU0QDSQKBwICBg01Dh0+LyIWKAcDBzECiwkiDhIXHCpFBAMHBx0jNSYxFwoQCwcIDQsIBQICCw8TAQ1D"
    "ZyEOGDwJCQsMHiY2FBxICwkOBAIIETcQBx4CB1A+QCc9DAYPTQAEACn/rwO8AxgAMQBGAIsA1gAAATYWFxYyFxcHBgcGBw4CBwYG"
    "BwYHBic0JiMiBhcWBiMiBiIUJjQmNhETNzYXFjc2NgcmBgcGIyIGFxYWBwYXFjI3NjY1NSU2FxYXFhYHBgcOAiIGBwYGFxYHBjMy"
    "NzY3NhYGFCIUBgcGBwYGBwYHBiYnJjc2Njc2NzYmJycmIyI3NzY3NjY1NDY2JzQXFhcWFhUUBgcOAwcHFxYWBw4EFxYHBhUUBiMi"
    "JicmNzY1NDY3NzYiFAYGBwcGBiMiJyY3NzY3NjY3PgM3Njc2NDYDUA8VEBcHDQ0KCwIDDQYBIAMFHggMDx0CGwcFDwMCBAUFFggZ"
    "DAkBCgkFCh4VZQIQOQoMCwwCCgcDAgoHBi4IEyb+rwUdEwYGEgMDAgERJAkcGRMFBwUBAgkEBz01IwQOCBYIDzUoCgMGDAswCwcF"
    "AggKDgMCAQMGCQYIEhkMBQcXLAWuGwsLDxgbCgcSJSIPDgkWJQYDAgQIBQkNEQQWBgoiAQIDDwgCBQMJEjcXLw8tBAIDBB8ZEAUI"
    "IwUFHwoIDyIXCiQCMwQGCg4NDR8eFhwfDRI5CAwbAQIHBQUIICx9XzMVCRMOHiQBAwEBBAUFChEKBysDAgUFCw8NERdzBAQJFHQl"
    "GqIOGQ8DAh8EAxEKCCAXEAsMCQY1XQg1MyIEDwkJHREeSDYEBhEODRcYDxQNCgQHCQxkDBchFR0QBAkeAQQ6F2oODQYKDRQGBSQJ"
    "BRovQA4PAgU/FQ08CJ8xDxoKBAYIFicLDBNVST4qHD0hBhRRGDMSJgwTIx0UBAk1Cg4nGAwhRCIPB0sAAwAb/7cDzQMIAGYAfwDa"
    "AAABNjcyFhcWFhUUBwYGJyYmBwYjIgYHBhUUBiMiBgYHBhUWNjY3NjYnJzc2FhcWFhUUFgYHBgcGJyYmJyYmBhUUBgcGBgcGJyYm"
    "JyY+BTQ2NzYmBwYGBwYnJicmJjc2NzY3NjYnNhY2FgcGBgcGBicmIwYHBiMiJicnNzY2EzYXFhYVFAYHBgcGFhcWFjIfAh4CMhcW"
    "FxYWFRQGBwYGIyImJyYnJiY1NCcnJiYjIgYHBgYUBhQGBwYGIyIUIgYiFAYHBgYnJjQ2NzY1NDY3Njc2NzY3NjYCABdGMxcLCwUP"
    "DhcZDEsMCw4JBQQFGgUDAy4PFAQmOBAhCQUFCgoREx5LCwMCBBMVFggpCQMIDBoMOCMfRQYFEAQDBAoFHjcRCwIBBAktIhIPDRgQ"
    "BwEEBgMEOyuMGB0gFh8BAQgQDg4MEwUnEw0FCSAHCwwJKDAICgoxCwQDBAIKFiAbBAgrGAg8AgcVH4MdDBQqMTEECmEVERkUQgsd"
    "DxwFBxMICRcjCg0WZwgFCREJMgkNMggL1QkhIgQoChoKBAIDHQEbAQECBwcICw8QDgUJBQkBAwYPFQYFGggzEBMDAgIHBAYNFxoN"
    "DQQEBUgYDRYDECELDgkFNhMHBQUDBRgFGgwECQkELwcGHgkOE0sRCQkJBwIBBgwRDwIEGggGBQcGDQ8MFpUIBAEeDQkKCAkDAgIC"
    "DQkVCxAMCg8BYgQCATAHBxYDAgsHCxEYGggjFAknBw0UPQ0KCQ4KAwQTPxMQFhJDAwMRLBYfEw8THQUtCQYQHWIIEAYfBwsWAQIM"
    "1wgnBgMtB0ATNQsHAwgnAAAEAB3/1APGAvAAPgDYAOgA+gAAEzY0NjMWFhcWBgcOAgcGFDMyFhcWBwYCFxYUBgYmJyYnJjQ3Njc2"
    "Nz4CIyIGBwYGJyY3NjY3NjY0NzY2NyU2FhcWFhcWFjMWNBY3MhYXFgYHBicmJgcGBhcWFjc2FhcWBgcGBwYGFRQGBwYmIyIGBwYH"
    "BhcWFhcWFxYXFhYXFhYXFgYHBgYjIiYnJicmJyYmBwYiBwYHBwYjIjc2NzY2NzY2NzYuAicmJjc2FhcWMzI2NzcHBgcGJicmJicm"
    "Njc2NzY3NjY3NwcGBwYiJyYmNzY3PgI0FyYnJgYHBgcGFjMyNjc2Jgc3IwYHBgYHBhYXFhQXFjY3NvkKEgMJJwQFAwwSCEoEBQYE"
    "FgkGBggFBwQgEBQDBAUEBA4GBAUCAgEBAigSGFMBCCASOgUDFAwKJAgBRAYOEwsHCAIGDxURFA8HBQYBCBUcCycDAwsBAk4KCj8H"
    "CAcSGA0KBQ0ICkINCgYEEwcFAwQ/HgwXQlkpCRERJQMCFRMVOgkLQxktPAs6JhUEBwkZJj8xFggHBgIDDCMIPikJBBUpCw8MAwcJ"
    "RxYQAgQPAgMQDwYGBQcPMgMBBg0UEBo1EAgCAxYYERIPCgcBAgdFIQYDaRAMCwUCAgQBBgoRDwsLAowCFSUJBxQCAggTCwMDIwME"
    "AosWCAgCGwcIChMbDGEFBQgWDAgaG/7kBwQgIQUOCQsCA1MHGqZeFQUKBSkPEjwDBx8SSQgIHQUODzwRiAQGCwgPHgoEAQcFAQMJ"
    "DAoMGQsEBAMDLwQICAICGQkLFxIWDAYKCg8YAwINBQxBDw0ECDMUBxExHw8GAgMSCAcRBQcfFwoXMgk6JxIFBRkoIhsMCAICDRgI"
    "QzQUChYTDQcHCAcJCA0KHQkNAgMFBQEIDm0YBwQEBAkPBwILFhoCAwcICQYHBw8NBgZOCu8CAwILIRwHBQIMFhkSDRIBCQQFCwoU"
    "HREIAQIMAwMAAgDP/5YDNQLFABQAvgAAATY2FxYWFxYWFQYHBiYnJjQmJicmJzIWFxYWFxYWBwYGFxY2FjMyFhcWBgcGBicmBwYG"
    "BwYCFxY3NhcXJyYmNTQ2MzIWFRQXFhYXHgIXFgcGBiMiJjU0JyY3NicmBgcGBgciBgcGJyYGBw4CFAYnJiY1NCcmNDc2JjY0Njc2"
    "NzY3NxcWFhUUBhQGBgcHMzI2Nz4CJyYGBwYiDgIHBiInJicmJyY2NDc2Njc2NzcXHgIGFxY/AjQ3NjQCggIIDhESGCQbARwOKQcH"
    "FQQIFKsDHwcGHAkJAgcFAwIEGQoVHBIEAQIGBgkUGhcRBgQGEgQCQSkxCQICBxAHCUUHBQoBAQUJAgUJBygQDRQFHQQEAgMDBwkO"
    "FCtaBgQYKiI4KwkOFQYICwcHBgQCBhYOHBcECwoLBxQWFQoNDhAQZgUFCAUBAUAGCBADFRoYDwkGBwEGBAEMAwURBg0RCAwNGQUK"
    "AwRHDQEJBQJBBAICAgoSHywhJRYMDRMQBSEaFj2OAgQCJhENLhUQRgICBQcRGg0KBQcCAwQEAgUMD/75DAwKBwoEHx0kDw4bKQUF"
    "BgcyHCMKQQ0eDwwPBwYCDEQKCAcGAgcFBAEMBwUCAgUOCQsDBwQBAxYPDxAMCAUGCAURBRctUA8MCwgGIQgGFQ4sHBITEQQEpIgC"
    "AQ0BBgcEFgwJAgYOIwMBFikEAyQTMBQLCAgaKx0CBAwCTpoDAQsAAAcAdf+fA2IC+QAWACoAYQB4AJsA1wELAAABNxcWNzYWFxYU"
    "BwYHBgYnJiYnJiY1NDc2FhcWFgcGBgcGJiI0JyYmNzY0NzYWFxYWBwYGBwcGIgYiBgcHNzYWFxYWBwYGIyIHBiInJicmNzY3Njc2"
    "NzY2NzY3Njc2Njc2NCc2FxYVFAYHBiYGBwYGBwYmNTQnJjc2JTYWFxYWBwYzMjc2FxYHBgcGFxYHBgYjIi4CJyY3Njc2NgM2MhcW"
    "FhcWBwYGBwYGFxYzMhYXFhYHBgYHBiYnJiYnJgYHBgcGBiMiBgcGJjU0NjY3Njc2Njc2NzY3NiU2FhcWFgcGFAYVFBUUFhYHBgcG"
    "BiMiBgYmNCImJyYnJjYXFhY3Njc2NzY0JyYnJjY3NjQBFwMNGxAIAwYCBQYDBh0FBRcCAwuHAiMJEwcIBAsLDAgLCwcDBgSoBQsP"
    "DBkCAgkTHAYFEQYYGxopHQ8JDw0LBBYrelIbCxYcBgQOCgYQTDQOEEsDCgwJAgEhBAOeUg4GAggKGQ4cFSEFAyEJGkAUAS0DCA0O"
    "CQICBgMECgYCAQkOAwMGCwgICAkSCggCAwoCAQEL/wgIExkRBQ0VAxwHBAEEBwgQiRULAwYFCQ0SHC0sGRAUCAY3UBEpBgI2BwUP"
    "VB8aJw8MEwMDCQUEFQGNDyoLCgEEBgUJCAUJCgkdBAQLCBYJCCY1HAoCEBlVBxIGBQECAwMDAgIFCAEkCg0fAgESEAoLDhIGBQgD"
    "BBkHBhIKEFQCDQgOGRUMCQMDEAcQDhoCAhUkBwEJBR0GBRkVHQkRGBMSAgEBBwtECgMDIgwLDBcOAgIHDRgRCw1NBxUNCQYDLgcD"
    "BmAVDAQZEQgDBAcDBAINBgUIBgYFEhUGIAgBCQobHywIDQUCAxQ/DAsgGQ0GEBUPDQ0jBjAjSgEZCQYFCggXFQMqBAMEAQJQFgwS"
    "FxMKBwgRKSkbExcBC2JOEiEjAgIKBwJTJSc+HhsZBwgRBgkzFQccGhEKDxMbBTIxjolHiRQgDQwbEgMIBQ8YIh4MBAgNCAkXHhb5"
    "5EULDSQaDAMFCAACAKT/rQNEAxgARgBdAAABNjIXFhYVFBY2Njc2FhcWFjU2FhYGBwYGJyYnJiYHBgcGBgcGBwYGBwYjIicmJycH"
    "DgIHBgYHBiYnJjU0Njc2Nj8CNjY3NjYXFgcGBgcGBiIGIgcGBicmNzY3NgHUBwgbGBANSEUiHRgFBBEBBQ0BDAcNEx0aERkhMRoR"
    "CQQFBw4MERULBQUFAgIZGDAXDg1OCQcJCxIbCg+FRRwCAgcfJhMZQCQJFBwUJwxLFQkMIwUHDAICawJdCA8OHRoYBQsIBwUDCgcB"
    "CAcSDjYJBwMBAwkGAgICBQUGCg9lu1kwNg0L5+cCAwITAwIaAwQFChAEBR8GCSUPBi4jHJkoBxIrHQgGBAMVJgYFCQMCCAECQAAB"
    "ADX/uwO3AwYAtwAAATYzMhYXFhQHBgYXFhY3Njc2NhcWFhcWBgcGIicmBwYGBwYHBzc+BBcWFhcWBwYGBwYnJiQHBhUUFxYXFwcO"
    "AwcHMzI2NjU0JyYmNzY2FjMyFhcWFgcGFxYHBiInJiY1NCY0JjU0BwYHDgUuAicmNjc2Njc2Nz4DNTQmBgcOAgcGBgcGBicmNTQi"
    "JyY2NzY3PgI3NjY3NjY1NAcGBwYmJyY3NjMyNj8CNgGsBwQHNA4WBQQGAwMECQ0YEywJDRsCAgoKBgkQKy4PBgMCAwIhIGIGVRIl"
    "HCAmGAUDDBAWLxD++zk9ChQEBBMSGCQQDAoNC2hgDw0DBAcNRwUJQQsPBgMFAgcWCw4VECkNEA0EChZCUiopHx4JDgQCCxQRCQsQ"
    "LAU0DA8IDAUHUzEYEzQLCSgPJwgFAwMJHmQhLl8ODAQCAwkqAwQaHyEaCAEDBTcuLAQEAv4IFwkOFgUETw8MAwIDCQYBBgkhCQ0g"
    "BQUFDQkCDCMdEREEAwcECQsBAgkTCyEODwUJEwYCBwcHAwgRJxcTEyIpIg8PEycKByEYDAgJBh9QGCUUCxAFERUNCQglBwQKDRUH"
    "DAsFCxUuFw8FBRsiERIQEAsJDQsRSAdoBAwEAgEBAgUVEwgGGgsIBQYNCggJBAYFDxwJDxsGBQoXIB0DCxMBAQ0JHhcIARcMDj92"
    "AAAFAKf/tgNBAw4AIAAyAEgAYAClAAABNjYXFhYXFhYHBgYUBhcWBgcGBicmBwYnJiYnJyY1NDYXJgcGFRQWFxY3NjY1NDc2NjQ3"
    "NhYXFhYGBicmBgcGBicmJjU0Njc2JzYXFgcOBAcGBicnNzY2Nzc+AjQ3NhYXFhcWFxYXFhYHBgYRBgYHBhUUBgcGBwYiJyYmNTQm"
    "JzQnJicmFzIzFhYXFjc2NzYCJyY1NCYnLgInJgcGJjU0NgFHJVA8KhsVGwkLCQ0SAwUEBwUOGmMqDgUFHgUOGgq9ETY+HgEDJBsX"
    "BwYOBCoVCwsEESINEEIcFhATEx43FhW6FQ4NCQUCBQEIAgUhFxECAwwFCAQJCukVZw4SH2IuHwgJAQoHAgEDBQg0FRIHCDAEBg4Q"
    "AkImCgIFAQIRXgYSGg0JCQEJCQUNEToKPmI3HSFgAasSDQEBBQkMFxwZGQsWCA0pBwYDAwgZCAIEMQwmQh0KCQMDCAcMBmkCBAYE"
    "Dg0JDg8yDdEKAw0OKBECBgcIDAkCBQMRBgIcCAhGHCokhUWcCH0IEhsKExEoKSgvXS/NGBJ9AgEDBQQMHhQLCyQRDkf+/plLCAwN"
    "FT8GBQQDAwQXBwkjBgsoFhEFAQYiAwoKBBUYAVFmYBoUCQcKCwcEBBgNAQ4OIAAABABj/50DhQMuAJAAtgDHAP8AAAE2FxYWFxYW"
    "BwYGBwYmJyYmIyIHBhcWFxYWNzY3NhY3NjYXFhQyFxcHBgYVFAcGBwYWFxYXFhcWMzIWFxYUBwYGJyIGBwcnJiYnJiYjIgYHBgYH"
    "DgIHBicnNzY2Nzc2NzY2JyYmJyYmBgYHBgYVFAYHBgYmNTQ+Ajc3NjQiJyYmNz4DJyYnJiY3NjY3NhcmJicmBgcGBwYWMzI3NjYX"
    "FgcGIwYHBgYVFDc2NjMyFxY2NzY2AyImJyYmBhYXFjc+AiMiBgM2FxYHBhY3Njc2NjI2FxYWBwYGBwYHBgYHBycmJyYiBwYHBgYH"
    "BgYHBgYnJiY2NzY1NDc2NzY2AYlEVC4vEgsFAgc5EQwdCgYOH0k1GxkKBQMHAQ5KEQcaEwwKDQkPDwcGGhQIDQoFIDBHSSkLCAhB"
    "CAUGBgsUFiUgERconwcFPQMENAcGMwoKNRkOOBQPDxAtCSA6PxcJBwg5AwEDCAoKFxQ7EAcQCSMQEQQlHxMNCQUDAgksCAEICgIQ"
    "BgQNHyvDBCM+KxoUGgQCCAMDIUUZChwRDykeKQkGEAtUDxMIBgUIERKVEQsMCwgLChw3CwQWEgMDMZQZHQoBAgcTLUMcHTAjEhMJ"
    "AQIDCQ1MQzItLAkJCQUFBgkfEQQbGA0NDzcHBQELCkQIDy0NCgJ9Cw0IFRMNCwopfwwIBQ0IAxcLCQQPBgcBBA0DAQYFAQYGCA8N"
    "ExIICRAgDBkUCg8aFxkWBSAJBgQJCAMBDhUMCAxOCwQtKAgHHwMCHAQEDgcFCgsWBhMgOhQPBQRPCgMEBAkJFgwCBC4JBAUCBAMi"
    "HxkJOTQDDAgJCgoHEAcHHTgQQxAMBgkNNgUMAQECCAoEAi8KFQYFCRYVARMEBwoeBwQOBAMGECc+/r4GDQwECA0bNwQBJyQMAigK"
    "LRASEAMHDwsFDAkICQ8XEQkCBAIBBgsKDAwKBwUKJxQFHxwMCws1AQENFwtVBAMNFFcYKQAAAQBu/6gDtALnAIYAAAE2FjIXFxUU"
    "BgcGBwc3Njc2FxYWFxYWFRQiBwYmJyYmJyYnJgYVFBYXFhYXFhcWFxYWFx4CFxYHBgYHBgcGJicmJyYmNCY0JyYnJiYnJgciBwcO"
    "AgcHBgYjIg4DBwYnJjU0NzY3NjY3NzY3NicwIyIHBgYHBgYmJyYmNjY3Nj8CNjYBpgQZERoaCAEGAwE6OQgKGg0TGBAHCAYGHAsM"
    "SB4dEg4DBwMBDRgeGwoODjwRE0kTLkUGBD4cIhkYFxsrJQ0VLgwfCQEQCggDAQEFBAYlDRsNHwQGJyASPhQdBgE3CSMdVQ8SGgwJ"
    "BQUYQBINAgUZIQsEAhcnJDQgIAMBBQLlAgwaGhcWCRFfEwwCAQUKCgQDFA4JDhEFBQEHBRIBAgIBAwgNDRgSHCYvHQoSEjkNDikN"
    "FyMLAhADBgsMAxIcLxAXBzwHECkRBhYWEQEECwcLSxEhEB4mDREfDRIJAQENJwggGmseHzVUOwIWBwcICwIWFAgKDAoJCwYEeVQ2"
    "AAACAG7/qAOEAucAfgCYAAABNjYXFhYXFgcHNzY2NzYyFxY3NhYXFgcGBwYGJyYjIgYHFBYXFhYXFhcWFhcWFhUUBwYHBycmJyYn"
    "Jy4CJyY1NCYjIhQGBwYHBhUUBgYHBgYHBiMiNzY3NjYyNjc2Njc2NTQ3NjY3NiYHBgYHBiInJiY3NjY3Njc2NzY2NzY3NjIXFwcG"
    "BicmBwYnJicmJy4DNzY3NjYBxgQJEREKBgcBAS8fFAQFBxEXFhMSBg8QCQQDEic5LScSASkWE1AlJx8dGBEQJhkxJxAWFRQ9DCEW"
    "CS8EHwsDAhAEDykRHwoTET4TKyMiIQEBFAgEKQoWQB0pAgQfAgIDCRZaCQkSEQsGAgEFCyY/RQoFBAcESjEZDwwLDAUIEi8UH0kK"
    "CBkcHBICAQI7NEkCWgoBCggNFRkgEQICBQQGBAcCAggKGQ8JCQUBAQIKFg9VHRlOHB4UFBYICSIHDwUKGQsMChE4DiMYEEANQAYF"
    "DwsgCSEpEQMCHQMTECwGExYBAQoJGgYKSTNFDwQEAlsPCAICAyEGCQoICQoMCQcTExMGAhc1KIUTFhQgHgUDCBUIBAcEBAICBgUD"
    "BAkICBMAAwBW/6MDjAMfAA8ATwClAAABLgI+AhYXHgIGBwYmAzYWFRQGBwYUBwcGFAcGFhcWFhUUBgYmJyYiBiIHBicmNzY1NCYj"
    "IiY3NjIXFjc2NzY2JgYHBgYmNTQ2NzY3NiU2NjMyFhcWFhQXMjc2Fjc2FhcWFhUUDgInLgInJwcGFxYGBwYHBgYjIhQGBwYjIiYn"
    "JiYnJiYnJjMyFxY3NjY3NjY1NQcGBiIGBiY2NzY2NzcnJgHwIRoWBzEHCSMdFA8KDgwSzgpTEAcLBQwHCQgBCggDDR4RCgwIXAcc"
    "MwYGPlA/BAMBAwg9FxQFCgsDCwVYFxMQFQcNLEkwATMCBQkLNAQCDAcDBgYMLyQTDxQIBRgLDRIGPRUXAQIDAgcHBQICDgMEJgQQ"
    "FAobBQQIAgMsFjQrFBRBFhEMAgEIKScUHRAmGQYDB2EwKwMEASEiCxkUCgICCQcOITAQDgYBaAorDgojCQsJDxwPDRMTCQoIDRcf"
    "Hg0CCwxfFSUGBVBnDQZNEwUMDAsFDDwQKwYJDAkBDg0KBwYTBgWrCgUhCAYWXQEGBAoEAgIJCRAaDgsWBAICCBICAxEScYfcGxEI"
    "CxwMHwUPFwwJDAsNKw4dBhQsIFdTRTdIRwMEBwgFERsDCBwHCDxIAAIAJf/SA8wC6wAtAIsAAAE2FxYWFRQWFBYUFxcWFhcWFjIW"
    "FxYHBgYjIgcGJicnJiYnJyY0JyYnJicmJyYTNhYXFhYHBgYVFAYUFxYWFRQGBwYnJgYHBhUUDwIGBwYGBwYVFAYHBhUUIgYHBjc2"
    "NzY3NjY3Njc3NjY0NhcWFhcWFjYyPwI2NzYmIyIGBwcnJiY2MzI3NjY3MgGvBQgFRxgkEC4kSjosNwoLDxsTBjkQFBApJR8jEEcO"
    "JRAGHBoIAwsXGncILg4aEREFIRQWDwcLECQNBFQYOBgXBAQCAg4EAyIJGQdyFyMDAgs8NCUgBgQEBgIHFAYHDwIDCV0MHh4DAwIC"
    "CBQZTRIPFBMFFAgGAgV2IiABzgcDAkgDBR4GJQgQMSYtFA8aDgoQEwYQBhACFBUKPQ8qEQcFHzQRBhI9PgEzAgcGCy4OBDMEBR0E"
    "DAkIDBEQBhANBAEHDQgECgseIBwYPwUDCAtQChwKBHELEwsGDD5lR25LNiQ2EAkNGQQEJBQVBiAGBjs6CQcCEgsHCAkJFgQGFgEA"
    "BAAq/8QDvgL7ABgALgCUAKsAACU+AjcyFhcWFhUUFhUUBgcGJy4DJyYTNhYXFhcWFRYGBwYHBiYnJiYnJjc2EzYWFxYXFgYHBgYH"
    "BxcWFAYnJhUUFhcWFjIXFhYXFhcWMzIWFRQGBwYHBgYnJicmJicmJjU0JicmJgcGBiIHBgcOAgcGBwYHBgYHBgYHBjU0NzY2Nz4D"
    "NDY1NDY3Njc2NzY2BzUjIgcHDgIXFhYVBhY3Njc2NjU0NgFQAwE8DQ9MDQ4XDAkXDxwLIjsFDyIoHwwTKhMHAQQJDRMNDAsPQQML"
    "GQinAyALKQMDCQoMBggICQcTEitAIR4LBgcGZBIUHWEFAxglDQ8nIB8XEBonbSoNLicHBwkPFSELBxwQCQ8JCQ0OCQMCJwgGIB4s"
    "IzJUFAgKDQwMEQcFDhc4DGwmHx8SHAokAQwHAwEGDwsoJREIUwkCDwERBwcWBgcPGBIOFQwKAwk7DAsaAQ0GAgMFFQkcEwwJDQEB"
    "AwkORAIICQIBpwMDBBAXECIICyANDBEQGwoGCwgLRBkWCgcFNAYHDi0aAwIMAgQTEQMOCQ8VYDIQPgQCMwcFAgQFERNMFwwvDRIc"
    "DwoICDQFBR4THQ4DMEOaPxocNSUXIwsONgMCCBEKAwVCFQYIBBcBGBASExcHBQQICQgODywAAwBJ/6oDoAMZAGYAegDeAAABNhYX"
    "FhQHBgYVDgIVFBUGFxYWFxYWNzY2Nz4DMxYXFhcWBgcGBwYnJicnJiY0JyYmJycHBiMiBgcGFAYUBhUUBgcGBgcGJjc2NzY3NjY3"
    "NiYnJjc2MzInJjMyPgInJjY3NjYHFhY+AiYmBwYGBwYeAhUUBwcBNhYXFhYHBgcHFxYWFxYHBhUGBgcGBhQGBwYmNTQiJjY3NjYn"
    "NDUmJiMwIyIGBgcGBwYGFxYGBw4CNSYnJzc2Njc2JyYGBwYHBhcWFgcGJyYmNzY2JyYmNiY2FjYyPwI2NgJjNSAPEAIDDwEMDQMW"
    "CzUSDy4KCRADAwICBAIGAgQQBggKDjEfIzkgEwcXDBILAQEJFBcJBgQEGgwrDg5BEQgDAgMXTRQHEgQBAgcPAQECBAEDDgsEAwkE"
    "BA4KEyMCFREFEAoDPQMFFgcFAw8EBAP+ywgXGBIGCAwFAx8ZRAkMCg0BAwkMCxsQEBEHFgMPFgoBAQYSAQwDBQQHAgQEBAQIBwMN"
    "Ew8NCggICQcUAwI0BA4LBQUJAQgSDwcMBAQBBAIQBgIeDDQfCgoDAQQCfQIDCwoXAwMuCAongSgqBzIqFzcJCAMEBiIWDxAKAQIW"
    "Kh4MRxMcAwILEyYWBx4FEhk5QlAJEQYIDRA2EQoGBTkNDiYDAgIFCBxbLBBJGRALCBIPAgYUC2UhBwcaBQkG0wcSBYY0BAQBAQYH"
    "BAUOCxAZJycBYAsDEA4RERY9FgIDEwkMFRmINhYOEwcRIwwKBA8NIRoGCjNjAQNUHQuPK0tkX2ILCB4EAyMIARgmHycnnE7+AgQP"
    "BhFiLBsuXxInMBgXDQzNCQgPCRocBBkEA0kxHQAHACj/jAPAAzUAEwAnAJMAtgDJAO0BEwAAJTY3NhYXFhYHBgYjIiYnJiY1NDYn"
    "NjMyFhcWBwYXFgYnJic0NzY3NiU2FxYWFxYHBgYjIgYVFBYVFBY3NhcWMjYyFxYyFxYWFxYGBwYnJiYjIgYHBgYHBgcGFAcGBicm"
    "JyYnJiY1NDYXFhY3Njc2JycHBgYHBgcGIicmJyY2NzY3NjI0NjYjIgYHBiYnJjU1NzY3NiU2FxYXFgYHBgYHBgcGBwYGBwc3Njc2"
    "Njc2NjU0NzY2NTQ2NzYXFhUUBgcGBwYGJyYmNjc3Njc2FhcWMzIWFxYGBgcHIyImJycHBgcGJicmJyYmNzY1NDY3NhcmJicmBwYU"
    "FxYUMjc2NjMyFhUUBiMiBiIUFxY2NzY2NzY2NzY2AcgOAgZICxAHAgIbFw8KHxkNCNUGBAUWAgcJBwQGJRMbAQUHCQcB+w8TDAgE"
    "BAcFCxoZChcSBQcxIhMOBgYJIBALBgMCAgcVIxBvEwgGAwQEBQsNAxEWORcPBQ0XDBkMCAs+DSEREgMBICAkKE4lFhcQEgQDDR42"
    "wjICCwEkGkUIBR0KCRgrbUb+UA0oAQMCAwoPGwonMxkpJhEODwQDSBAKBAgnBAI2Gh8GJB4ECQ4QE4kGBgJBGiQL5y5xIhAGBx4C"
    "AigNERITDQoHCyQjFyAaBAMJERoKBAcNG7oEIy1OFgcEBgIWEj4RDhUUGyAjHg4BTREZCwQIAwQDBOIDAQEQBQYOEhocChgUEA0M"
    "CVMFHAkgdVMWFRsJDj0hCQ5rTswFDQkLDw8MCQMCBgccBQQJAgMFAgoEBwoGChAPCwYXDgUWBAkN2B42CAIMFR4PEwsJEREHHwcG"
    "BgMGDAIEJyiWRAEBDAYLEQoKCg8ODgwWFQYmEAYOBgUFBgcTEgsUCQcsCiUBFQ8MDxQcDTYpFCMjDAIDDQ5YFRIFCjoCAwEBTwMC"
    "IfAQGBMmDwoICg4SWgEBGVMoOBAqBw4RCCkMDlMoICAFCQ0CAgoOAxQOEB+DBgINDAoIDz8EDQIEGAcHCg4UCAgMEw0OChALHQEN"
    "AQMEDhEXDA4nAAQAP/++A60DBgAUACgAPQCyAAATNDYWFxYHBhcWBgcGBwYmJyY2NzYlNjYWFxYWFxYHBgYjIicmJjc2NiU2NhcW"
    "FxYyNzcHBhcWBgcGJicmJjc2FhcWFhcWDgMHBgcGBgcGBwYHBhYXFjY3NjQuAycmNh4DFBYXFhceAhcWBwYGBwYGJyYmJycHBiMi"
    "Bw4DFCIHBgYiNTQ3NjY3Njc2JicmJicmJjQzMhYXFhYVFBYzMjc3Njc3PgI0NjYyqQoTBQUFEA4HCQMKDyRABAQQDE4CgwgGJgoS"
    "JAMKEgYlDRQ7CiYCATH+LwIFCRYZDwwXFg8PAgQMCAsfDBcV9AISFxkMBQUPDAgOCxIHAwcQGw4CCwkJHSmXCwYKMA0PBwYMGAcm"
    "HxMLGh4NBgwCBR4OJw0SSBdJPjY0CgsECkghKwQyDAoFDwsFEMgKBAYFAgsOEwoHCQUFJQYCFyQFBxsJBg4UBg4IEQoHAe8DDAEG"
    "ByBVLRgUCyQFCSonFjgOUlgBARwGCR8IFx8JFFENKAQDETsIAwEDFA0NDRQUDQ4qBgcCCBM8rAkFDxEOEhE3NSI9FygSBQ0jOg4C"
    "ExENCg4EDgYvLVsaFhMSBCADNiMJDRUzGAoXDBorDwcoBwkNAwcVJCINDkogIgUYCAgDBQQCAgbMFQkMCAsSGTMcETImNQ0IGAQG"
    "KEIXDSU0D0UgJWcQAAcAbf+GA38DOQAQADYASQBeAIoAsQExAAA3NjYXFgYHBgYjIicmJic0NiU2HgIzMhYWBwYGJyYnJyYnJjU0"
    "LgI3MhcWFhcWNjc2JicmJicmNjMyFxY2NzYXFgcGFAYjIiY3NhcWMhcXFRQGBwYGJyYnJicmNzYnNhYXFgcGFAYHBgcGBiMiBwYn"
    "JiYjIgcGBgcUBgcGJyYnLgM2NzYXFjYHJgcGIgcGBhUUFjc2Njc2FhcWBwYGBwYHBxcWFjc2NjcyNjc2JyYDNhcWFxYWFxYWNjI2"
    "FhcWBwYGJyYjIxcWBwYGBwYXMjc2NzY2NzYXFhYzMhYXFgcGJicmIiYjIgcGBwYGBwYnJiYnJjYzMjY3Njc3JyYmNzYyFxYWNzYV"
    "FAcGFhQHBhcWNzY3NzY1JgYGBwYnJgYHBiIHBiYnJiY3NjY3NjYmJvULIAUGCQgDHwcCBw0IAQkBWgIVJEsEBUMJBgV+RSQJJB4X"
    "MAkIAgMEJB8cFh1aHRESIBgdigECBxcjDR4GBgICCAsMDBk28AwmHgsSEwMKCAoIDAw3HCQiDYQVQhEYCgcKAgULBRkIBAYNFQkM"
    "FBwcEwsBBQgMCQ0IBQgFDAQgQEYcBxIgEgojEA0ICgMCJQUHMgcWDQUNFR4VFwICAxENOw4HBQIVBgN8BwwlFAwHAgIDGiQHNgsS"
    "DAYVCAcMDAwaEQcbDxYNAgQRKxFAKE4bDAMGBBwCCBULEhcUFSFRdn4tEhxmDjINDB0CAQoGAygXLHQQDA4RAgQVCQYfCggFBA8I"
    "CwgGBxk3Ew0CGR8FBgwPGhwPDQsIEQICBwICOBgTBhQEWgoiAgOQCgYSCA8ZGhsTPwQMEDJEEiIcIgkFBBEOFy4OBgUjHAIjIRQG"
    "CwgOCikYFB8vCgUSBgoFCAIDCw0nGzVbBxALEhIfFQsKCAMBAw49FhwEA94FFxIaFg4TCRAqGAoYBgwVCQMHBwYGBgUBAQ0SPSgS"
    "Kw0LECAFAQYnBgYDCQYTFggFBgMLAwQBBQ8TBgUCAgcIFRUEBwUNAgYJagcDAZQHAgYSCwwUHAMHBwkLEhIIAgcGDyAMBSUPFwQB"
    "AwoEBAgSEwkFHAcWFQoBCwoLGgoDBR0IGgMDGAoHERIDBSEEEhMsCQsGBgIDAgICCQoQHgYHBQIDC1kfFgQDAQUDBwMEBgwIBQQC"
    "BwcMBwQXBgUFLikAAAMAW/+WA40DLAAXADABEwAAATYWFxYXFhYHBgYHBiYnJjQnJjMyJzQ2IzY2FhceAhcUBiMiBgcGIgYHBjU0"
    "Njc2NzY3NhcWFhcWFhUGFxY2NzY2FjMyFhcWFgYGBwYGJyYHBgYXFhcWFxc3NjYnJjMyFhcWFRQGBwYUBwYGFxYWMzIXFjY3Njc2"
    "FxYVFBYWBwYHBiYnJiYnJiYHBgYHBgcGNTY3NjY3NjQnLgI0Jjc0JicmBgcGBhYzMjc2FRQGBwYGBwYHBgcOAic0JjU0JicmJiI0"
    "Jy4CMxYXFhYzMjY3NicmJgcGBiIGBwYjIiY3Njc2NjI2Njc2NicmBwYiBwYmJyYnJjY3NjYzMjYnJicmJjY3NhcWFRQzMjYnJicm"
    "JyYCSgo3CwkLBgMBAQMIDBkVGAwVDAQCBOAJFwsDBQ0OARwIBz0NCRAmHBs2FCqBCQMNFQkGAQIJAQwDQwoMDhsJCBwJBgMEBgwP"
    "DRg8GhAHAREQCgQGCAseAQEKCCMKBg8JBxEZBAceZhgLDQgICAkLFQUBCwQJERkPQA8mcScKDgsQOhYdDBEBAQNtDwwMCBMKCQEJ"
    "AwM0BQMDAgQDGCkSChsOAwQKFSkLHxQBDAsGAhcIBQQJBQIDFg82BwUUBRMFAgMGCBEHRhAPCw8sAwIQDUEDNCoDBAYFBkAgAwgX"
    "IBYMCAUCCh+OFQYDBAMHBQEHCCgQGgkNMgEIAwIICQKrBAIFBAgHDBcWDwYLBRQWCxAaAwIFCREBCwwFHg0OGyAKCBYLCAUHMBgz"
    "pgQCARkJEBUfLTlZCAIJAwYMCgwIBQkXCggJAQQIAwEEBkYkFA0MChBHCAMeDgsKByMLCQ0QGggNO20EAwIIDBYtIA0cLw0jDhkF"
    "BAkHEnY/DwILDigLDggMBgECB3MUEQ8hFkUXEBcJCCEDAg0FAiAeDRMMBhcHEyhEkR1FEwUIAQQEDA4JHAYBJAsFAhQTARQNICMT"
    "Oy0SCAMCDzYODiAJBwsKKSAVBQVRBgsqFgYWARYMBAMFBhlBDxggAwQGBgEEER0JBw8CMl9KJycAAwA1/9ADtgL0AEMAoQDyAAAB"
    "NhYXFhY3NhYXFhUUBicmBgcVNzMXFhYHBgYnJicmBwYGBwYmJyY3NjY3NjY3NjY3NjU0JgcGBwYmJyYmNzY/AzYBNhYXFgYHBhYz"
    "MhcWFgcGBicmBwYGFjc2NzY3NhcUBwYUBg8CBgYHBgYjIi4DNzYXFjY3NjYnJgcGBwYGIyImNTQ2NzY/AjYjIgYVFAYnJicmNTQ2"
    "NzY2NTQlNjYzNhYVFBYVFzMyFhcWBwYGJycHBhQGFxY2NzYXFhYHBicmJyYGBwYGJyYGBwYHBicmJjc2NzY3NjYnJjc2BwYHBicm"
    "JjU0NjMyNzcnJjYCXgwoBwMEBQcoCgoSGhcIAXd3FBIGCwkSHD5nZWIaFgcEFCMcCwRJIiQVDQkEBQQCCQsUDQoIEAcICRApGQEC"
    "/uIPJQYDAQcLAxUWDxEECQoKESAKAwYBBAUfLgsQAQ4KTQoMAQEIAgQnGA8HOA8JBAMqJhMDAwkBAQYFITgZDxQ4PhQYOjkCBwcC"
    "JQQIGQsGKhUcCQFEBBEFCBsOARYQDQkXEwgKEhEHBw0CA5oYCxEOAwkPHg56Hg8ICBYJCRYgOQcGFw8JAgJRIw4JBAEDBw4TAwMI"
    "CgkXIggHDQ4BAQYBYxITGwsHAQEHBQUSEw4BAg4sJQESERwWEwQLFQMEDwQJCQUHEQ0QCBcDBQcCAQgVHg8MBAECBgQCBwwRCQoF"
    "DAgUFQGJBR0TDA8UHwoJCxASEQUHDhAHNzICBBspBwwQDw4KBU4ODY6NFBcdKxU2FxwBAwcGBhQRkAwIAgQgNxIaCQc4Cw8lJS5w"
    "EQgFAgIFGAoDAxUICw8nYg8FBwEPBQYaKywECBYeDAMICAoJKBcEAwQFAhIPEg4YEAYGAQIICQIIBQEIDQoKDAcgBAMQBwUFBgcM"
    "FjQLAgIHAgIWBQUSBAYeH04AAAMAHP+6A84DCQEdASwBRQAAATYWFhcWMhYVFRcWFxYGJyYGFRQGFAYXFjcyNjc+AzQ2NTQ2MzIW"
    "FxYHBgcGBwYUBgcGMzI2NzY2NzYWFRQXFhYHBgYnIgYHBgYHBgYHBhYVFBYzMjc2Njc2FxcVFAYHBhQHBhQXFhYXHgIXFhYXFgcG"
    "BgcGBgcGIyImJyYnJiIGBwYGBwYGBwYGIyI1NCYiJicmNzY2NzI3NjYnJicmJiMiBwYGFx4CNzYXFhYVFAYHBg8CBhYzMjc2FhcW"
    "BgcGJyYGFxYGBwYnJicmPgQnJjY3NjYXFjIWMzI2NzYmJyYGFRQHBycmIyIHBicmJjU0Njc2NjMzNTY3NiYjIgcGJic0Njc2NzY2"
    "NzY2FxYWFRU3PgI3Ngc3BwYHBhQXFzMyNDc2NhcmJgYHBgcGFBcWMzI2NzY3NjYnJjQnJiYBaQIJDwQHBREPHgUCDxQQBRMRAgRq"
    "EA0CAgsNCwsOBgkkBhELBQMDDAYNBQsNBjMNCi4HBhAMEAwMBhU3D0wKCwkNCSMDAhsyBQQTAw8FDRkODQcFBQYHDT4LEiIRJB9E"
    "BgYGBAYNDykMCgcIURIsQSAELx4hEhkdBQQIIhAVHAUYBgcBAQsZJAMFAgIDBAUKHDIkBwQBAgMJER8qCwgPGBkcGwICAgMBERIq"
    "DhEFFzwMDgYCAgoGExACAQUQBQgGBQkLAQ0jfS0SCBIDAy4ICQs4MmoJChASCRFGMCIIBSoPHEoJCgECAQIFCg4PGQIGDBMJEggC"
    "AgsIDhMkIwYJBAUbAw8tBQMDAhAPCggGsgkFFxAdBgICAwMIWRAKDQgCBAYFBiIDBwIBBgQIGiMiAwYYEAwDAQIHCigTGwICAw0U"
    "ESs+JQ8cCQgPGwoaIBENDxcMDSkKEw4FAwcFAwEEAwUHLgoGAQELBAUMAgIhCwchBAZFRAxNCRIaDCogPwQCGwYGHwYKJwYICQsK"
    "CR4HBxAMBAEBEgsKHgoXPx0tDw8HBAMGFSIwDwQoGAgLCAYCAgIDO2aECwgDEwQHBwwbAwsQFQYHCAoJAgIHBxENIQgJAgkPHQcO"
    "AgMPHh9LCRY5BQcRQj0qfgwEBRMKGgoVCRc9Dw0EAwMJBwULCgwNJBgGAgUGCCcHCRUbHR4WCQkIBQ0GCAgLAgQKExgTAgIbEAwC"
    "AwZUCgysFAEBBQNBGhYHEQsa4xsFDwgOGwyMHyA4DgoQDAcFBwYHBkwAAAIBDf/AAtsDAwBKAHsAAAE2FhcWFhcWFgcGBwYHBgYV"
    "BgcGFAYGBwYGBwYmJyYmNCI0JjYnJjMyFxYyNzY3NgcOAiMiBhcWBiMiJjUmNzYSJyY2MzI2NjI2FzUjIgcGJgYXFwcGFjY2FxYW"
    "FxYUBwYGJyYHBiMiBhcUBgcGMzI3NjY3NhYXFjc2NgHYMmMWDygQDAUGDAQDAQIJAQoECQkUEhMUEgwQDSsbFAsEAgQBAhAxDCIC"
    "AREQQz4LECYDAhEHERwBCwUEBQQHDQsKMRQjpR5tIwxLAxARAgMILwcnIB4LCQcGHw8QQg4IBgoBCAIBBQEDB10IC0IQFQEEBgL7"
    "CAUKCA0SDxgYL4JePj4XOmYGAhcFIhQTDQoICR8aLQcHFQgGBAEHBxAPCAMDBxkaCggYQylMMRUBVh4aFhcODrd+FAcLBBISPj4M"
    "EA8BAgwRDhQRDhECBB4HFAoJJTk3AgIYBQYFBwoCA+4AAAQARv+jA6MDIAAQAD4AYwC1AAABNjYXFhYXFgYHBiYnJicmJiU3FxYW"
    "FxYHBgYHBgcGBgcGBicmJicmJgcGIgcGBhUUBiMiJjUmNjU0NTQ2NzYXJyMmBwYWBwYGFQYyNjYXFgcGBwYGBwYGBxQWNzY3NhcW"
    "NzY2JSY2NjM2FxYWBwYUFhY3NxcWFgcGBicmJyYHBgYXFhcWBgcGFhcWBgcGBgcGIyIHBgYjIi4CNjc2Njc2NicmJyYGBwYHBicm"
    "NTQ2NzY3NzUmAZMEDBYmOwkGDA0VKg4HDRQQ/vohQC4YFD0TCwcBAQYFCBANGAYECQgFCAoJNRAMFQ4DBg8BDgoeBnkDF0UTCRcQ"
    "CAUCCC8kCRANCR4KMAQCAwIDAwcfNRoGBAMDAVQBBhYBBioUAwMDBY0eJw4LBAcKKxYRE1YTEwkDAwICAQIEBAQGCAMDFwgrCgkD"
    "AxsLDhQQMAM0JBULGgkCBAMDUh8mEiIZCQUJJKQZAQGFBQMBAxgSDioLEAwbDwYMIvIQAQEEChwlFUhrjiEaEREQBgsIDBwXCgcG"
    "BwURBgINNBMKX4wLE1skDwNUMwMXCRQUCRAXIhAGCxEaEwUCEQIBbwgEBAECBw4LBAgI6e0cHBcBGw0RIhhTBgECBA8MFhAYCw4M"
    "AwwCAxorLA8SiQMGTR0jIRIQMwktBgYNIDExCQIBBQgSR7DEBAQNCgwMFxAHFhAKCBsUAjMxAAQATv+1A5cDEgBuAIMArwDUAAAB"
    "NhYXFhYHBgYnJgYHBgYHBhcWFjc2NzcXFgYHBgYjBiMiBgcGBwYWFxYXFhYzMhYVFg4DIgcHJyYnJyYnJiYHBhUUBgcGDwIGBicm"
    "NzY3Njc2NzY3NgcGBwYGBwYGJicmJjc0Njc2Njc+Agc0JiMiBhQXFhYHBgYXFhY3NjYnJgM2FxYVFBYGFAYXFgYHBgcGBgcGFRQG"
    "IyInJiYjIg4CIicmNTQuAjc2NhcmBgcGFRYXFhQyNjY1NDYWFxYHBgYjIgYjIxcWMj4DNDYmAn0iSAcHAQcJHxENdxoPBwIEAQID"
    "BQonJw4QBBMMEBYgCAYEAgMCAgQLN7hBGwgPLAEZEi4FEA8RJSM+cm5YEwoGCCgJBgscIREzBwgJBAQTG2clBwUCAgUbGDICBCQO"
    "DAgWAjgaILEfH0dLqgMLDUUVGQURBgEFBTsEAgEDAz0qgU4PChIDAwEFBgICBQwRHAYGCAYOFyIjKRAGChcIBg0ICy+EDEUSJwEB"
    "BggjFhsdBAgCAw8UFyEODwECBio1Eg8IDgGXBAEGBhsOEQcGAwEFAgcMEg8KBgECAwIREhkOCgYBCg8YCwgGBRkUBwghCgYFBxAH"
    "EhECAhMkI0sPBAUIBQQxBgQKGBsPHAECDQMGFhxwhRoLCQICBwceCAoIDQIDFwgDHwoLLwMFBw9hDAUSBgsMGyINCgcIHwMDYhUU"
    "AeQNCAUaChQJHDMNERwDBCUaEQ0TBQUYCwcECAoaEzBoQCkfCwoPGxgEBAUKDwIBBlsWBgMEAQMEBhUXDhIgIhELBwUUmSIAAAIA"
    "3P+gAwoDIwBLAI4AAAE2MhcWFgcGFxYWNzY3NhYXFg4IFxY2NzYWMzIWBxQjIgYHBiMiBhUUBgcGBwYGBwYGJyI2NDY2NzY2NTQ3"
    "Njc2NzY3Njc2NhcWNzYeAhcWFhUUBwYXFAcGBhUGFxYGBwYGBw4CBwcnLgQnJjM2FxY2NzYSJzUnJgYHBgcGBicmNjc2AbsEBRYR"
    "BwEBAgILDQ4xFxEHBwoMQw0fBQsBCQQBQg4LERASDgEiE0kOEAkHGBIDAgQDJBMTZw0GCgscFw4kChEMAwkYCgliIUwXFwECEgwV"
    "EQwGAgcBAgIGAQsEBAICEgoHCScREwkJAioYIwUECQcnLxQGAwgCEQ9QGBYPDA0HBQIKGgK4DBgRFRcRFRIHCQoBAQULDCgMBgUH"
    "Dhg6CwMCDQUECQ0TKw4GCR0IAyQCAgsHMRUVQAEFDwYmFhAxBAIPFzcJIVqUeXQHAQcFAwQECwYLBgkLDgMGIjcDA+pgxw4FFyMc"
    "MwQCCw4BARMTERsUEggGAQIBCRoPAfSJJgQFBAYGCgoBBwYGCRgAAgCA/4gDbwM6AEUA5gAAATYzMhYVFBYVFBY3NjYzMhYVFgYH"
    "DgIjIwcGFjMyNzY3NhcWFhUUMzIWBgcGBiMmBiMiBhUUDgIVFAYmJjU0NjQ2NzYTNjcyFhUUMhcWFgcGFxY2NzYWNhcWFhUUFxYH"
    "BicmJicnBwYUIhQGBiMiBhcWNzY2FxYWFRQWFxYGBwYGBwYWFxQHBgYHBgYnJiMiJicmJicmJyY3NhcWFjc2Njc2JiYnJiYjIgYH"
    "BiIUBgcGBgcGBwYGJyc3Njc2NzY2NzY3NjY3PgIjIgcGBwYnJiY1NDY3Njc2NjMyNzc2NzY2NzY2AZQFCggDCwgMCFcKBRABEQoM"
    "LyUPDwIDAgUIBAZNFBILBgQDAQICBSMTFjoLCwgHAw0WCQkQCAQGXA4DAQIIFBgEEw0CAkMXIW4qDw4cBggbHzQVTlhMCAkICBMD"
    "AgwCASMdKzkaMxYFBAIIAgECAgECAgMMHA8LBAkLDwoBAgkgKQsEAwUOFzsOBwQCAgEBBQUlFxQ5FhcSHg0LQw4uDw8nCgsKDBkj"
    "KBEsBQoeBAcJBw0FAgQeYS8cFgkSTCoiBgNrBgMHCwYKBgYCAgUBowMECAsJEg4EBgUWEQUHFwcJBg0UGQ0EBhEEAgIEBgoFCwUM"
    "DgENDxkdGHAJBQUDCDAQEDxsPzVLAZ0CAQIBBRMYLiYbAgMFBAYFCAQEFwgGDBoSFRsLCQMCCgwLDgYqFAIBDAoDAwEMBQIKCAcN"
    "GAUcBAL7Iw5EPCEcDgcDBQoSFRIWGxUHAQEGDAkHAwwTHN6VCQcLEQ4OCCETDkYKJwwOFAEBDg0bJC4TPgsWLwUSERAhFQQOIBQW"
    "ChsFCRsFBAIBDBEaDjIZCwwIBQABACP/kQPRAzQA7AAAATYWFxYHDgI3PgIyFxYyFxYHBgYnJgcHFxYUFxYUBwYGBwYGFxYGBwYH"
    "BhUUBiMiJjU0JicmNCY0JjYWFxY2NzY3NiYjIgcGIyIGBwYGBwYGIyIGDwMnJiY3Njc2NjQmIyIGBw4DBw4CJyY2NDY2NzY3NzY2"
    "NTQmBwYHBgYVFCcmJyYmNzYmPgM/AjY3NjY3NxcWBwYWBhcWFjc2FhcWFhUUBwYGJyYHBgYVFAYWFjIWFxYVFgYjIiYnJgcGFRQH"
    "BhYzMjY2NzY3NjY1NCcmBgcGJyYmNTQ2NzY3NzY3NjY1NDYCnAYREjEIAwMCDD8mCwoTGhYKGBwLCApbQRkMDAsJCQkFCBADBAYE"
    "DA8OCicIByYqCwsZCQkvHBoPCBACAQMKCSEMAwNIBwU3AgRgBQYFAwITEw0NEAQLAwMDAQIGGwYID0IjCggUDwMCDAsrAgg6IQwi"
    "FAMCCAoRHwQFGBEEBAMPGyIlERwDAgQEBAgJFikLBAEGBQIGCRoRCggECQULERoLCQIIDiUNCgkNARQHBTcDBgUBBgUDBgSYIBUq"
    "Lw0GBANuCgsOCiQOCg4eNBUcGQoLAyoKAwwhQRlCCgEEBAsFCQcUJg4FAhAHBA8PBAsKBwkKCwwYNoGSShscDwwEBRgjCAQrBwcI"
    "HhEBBBgHBwkZLnQ/HioOLQYEJwIFPxAjKRIRDw81Dh9MKTcjERUICwZCEQsHEAgCBQ4RBjQCCFgyEU4IBwEGBwIDEQcMDgMDDBML"
    "CwMKDg8PBQkWFT4sFQYJEiMUCQgtCwcDAgYBCAYLDxcLBwQBAgUDChsjFQQUCAcJIg4kJQQLEwcIFDwwYpooGDBDEg8YHwICJgcH"
    "BAQdBggSBAUJEAgFBBMrKmoAAAIARv+SA6YDMgDPAN8AAAE2FhYXFhQHBhYXFhcyFhcWBwYmJyYGBwYGFxY2NzY2FxYWBwYiBgYH"
    "BhYWNzYWFxYXFhYVBgcGJicmIiYjIgYXFhYzMhcWFx4CMzIWFxYGBwYHBhQGJicmIiYiLgIjIiYnJiYnJgcGBwYHBhQGIyImJyY0"
    "NzY2JiMiBwYiFAcGBwYHBgYnJjc2Njc2Njc2NzY0NzYnJgYHBwYGBwYnJiYnJjY3Njc2NjMyJyYnJjQmNzY3NhcWNjc2MzI2JyYn"
    "JgYHBgYnJiY3NjY/AjYDNjYnJiMiBwYHBgYHBjMyAZcFDhIJCgIEDxkhBAUSAgYWDQ8PExAFBAUFBCUKCgsPEDcDBAYkHgEBHi8b"
    "SC0JCQwIAwEHCSQJBSNuNTEEJQpSBgMUGX8WOxMFBRYFCg4PYBQSDxQHDwoEEQk0KgQEPwwNCQkOCQUCAw4FFQQFEQcFBQQDAQIF"
    "TBoJERoXCy4OJAMCExEuDQwJEC4WDR02CAJEGSkVLgoWGBIJAQEEBxVBGE4GBgUCBQkNBAsdDQQGERMWCAUCAgIBAzcJBwkJDhIF"
    "BDUfJQIDIhAIAQEEAQIGAgQLBQYHBAMsBgMTEA8xCQsHAQEBGggdCAQBBgkCDAxrAQEzFhMIAwM8CgkhEQYEBQEBBQEFCAYECxIb"
    "CQoEDQYIDigLOA4RNwgODw0HCx8DDgkIBwEGBQoICiMiPxASCA8XBgKPtBUICxURLh8aGxVQQEoYCAgNFgoXBgIFBQwMLBESCBI1"
    "GQ0EJkgHAgwICwcXChcMCgwQDgkGDxUJFQoDBg8KKAsaAwEJDQQTGQkRGgEEDwcFAQMEGwoKFwUHLzv+mAIVKigDCBAULgUIAAUA"
    "Gf+ZA9oDKgALAHgBdQGCAZUAAAE2FhcWFgcGJy4CJzYzMhYXFgcGFjYXFhYUBiMiBgYHBhYXFhcWBiMiFRU3MhYXFhcWBgcGJgcG"
    "FxcHBgcGJicmJjc2NTY3NiY3NiYjIgcGBwYnJjc+AjU0Njc2NDY2NzY2NzcHBgYVFAYHBiY1NDY/AzY1NCU2MhcWFxYGBiMiBhUw"
    "FjI3FjYWFgcGBgcGJyYmBwYXFhcWFjMyNjc2FxYWFRQyFxYWBwYXFgYHBhcWNjc2FhcWBwYGIyInJwcGIzAHBgYHBgYiJzQnJyY0"
    "JiYnJiY2FxYyNzc1NQcGIyMXFgcGBicmJyYmBwYGBwYGJyYmJzQ2NzY3NjY3NjIWNjYXFjY2JyY2NzYnJiYjIgYHBicmJjU0NjMy"
    "Njc2Njc2JicmJyYmNTQnJg4CBwYGFRYyNjc2NhcWFxYWBw4CJyYmNzYjIgcGFgYXFgYHBgYnJiY3NjY3NjY3NjYjIgYHBicmJjc2"
    "Njc2NzY2Nzc+AxM0JiYnJwcVFxYXFjYnNjQ0MSIHBgYHBgYXFjY3Njc2AgYLIgoPCgcHChMmCd8ECAcnBAkJBQU1FhIHDggEAzsI"
    "CQIKCwMBEQUEHS8PAQIDAgwaGh0DBwUFDw0FBR4JDA4GBAEDAgcBAQIEDmsrFyUBAQEDCTMjEhkTFBETCAICCg4dFwwMGyMXMhQG"
    "BAHNDQgLEAsLBiYECjIUJxgnLhYFAwEFCg8ZKW4VRAUBCQsGBwYFBAUSCA0NIzYjCwUDBAIKFA4HVCEaDAkXFQgPIi4hIQIEBAIB"
    "ESoJGhIBEx8NGQIHBQUIFhg/DA0YFRERAwgOBAcJJx8FCBQdCwYGCAodFAIdCgoiLhQDAwwoNR0FBQ0JAQEHAwMGBAsWGxwNCwkK"
    "FRUIChcyLRUCAgcYJg4HCQUBBAQHBQodAQgRCSIuBAIICAEIBkooCgoICAkFAgsOBAkDAwUHAxAHBgMFBA8aFQkDAwcICUQIChQR"
    "CwICDh0pKxwTCCAUCCMFCgkKEA8BDg0NCQKgAQMNCQUEBAUFAQQBBBIGAu0FBwoOKA4NAwUnJS0EGwkPMhwFCgUEBRMUCgQGCBwM"
    "CwkIJhIUAQgaERIUEAQFEAQF33skJgIDDg4PNwoIQXUMCQsmGQ5wKxEbCwEFBxo4AwQ1Fx8OGjAjKBgWHAIDDgMEDAMCFggKGQkS"
    "CCssFSAjBAcGGBcaGiIGAgICAwsOEAcGAgQFBwgDBw8EBQQUBw4cBQIWCwkFBSgpEzZLMhMiBQQQAgEDChoXCgMDBBAiQjsmIgYL"
    "BQULFAkPAxUGBiEFBggIBzw8AwMPJxQIAwIIMQYDBggFCwkEAQUMDgUcAgIHCAcICAwJCwIBAgUEAxcGAgoHAwkLDAMCEgcIFAkF"
    "Bg4dFggDAhcKNRgTAwEEDxkVJi4DAQICBwEGBQIDFQgFBQsEAhMGCgUIFh0IBTAMCAQJB90kHBIIBgkNDxMaBQkBAQwOBwkJDAkG"
    "BgslGA0zFv6rEiEDAwIeHgYFBAIEIwcMBwYFDA4cPAIBBAMOKQ8AAwA+/9kDrALrADYAfAC1AAABNh8EFhQyFhYXFhYXFhcWBiMi"
    "BwYmJyYnJiIGBhQiBwYHBgYjIgcGBicmNzY2NzY2NTQ2JzYWFxYzMhYXFgYGFAYUBhUUFhcXBwYGJyYmJyYmBwYGBwYGIyImNzY3"
    "Njc2JyY3NhcWNzY2NTQmBwYGBwYmJyY3NjY3Njc2FhcWBwYUBgcHNz4CNzYXFhUUBwYGIyIGIgYmNzY1NCYHBiIHBiYnJwcGBwY3"
    "NjU2NzY3Njc2Ak0IHQwEAx0eByQ3FxoJGy0EBBQdIBMlEQ9YJhwICAwIBQweEy8IBxMQMwMDO0AjDwsbC+ICJQMECAwWBAQIHxYe"
    "HA0MAgEOHhMNCxULCiZlFxIcBwUBBBAoSSYDEigHCzkiBAYcBAYKLhYSFg0JAgQvOUXjDRgZHh0MJQwMDQ8jXwQHJygNBykGAh8U"
    "HQUPGxgLESITDQkLDBUkNCsBAQcdKyQcAgkBrQoSCTU2KCcJMjUPEggRHRkQCwUIAg1MRjYZGwkMHx0UIAkKDAMCOz8rIRyCHhMz"
    "dAIEBAMRDREYHg8uCjQGBRkIBywoEQIBBgsWBQomSAcFEAMGGyxONAYXLg8XFAsEB2oSBwQBAwULCQEMCAsNEAYIxg0FFxswFgcz"
    "FxcEAwgGBgsaGR4RCwcWFRMGHzsHBQcDBAcEAQYIJ0QyJxQCAhwrQG5TDzUAAAUANP+ZA7cDJgAoAIMAmQCtAPUAABM2FxYHBhQG"
    "FAcGBwYGFAYGFgYHBgcGJicmJyYmNTQ2MzI2Nz4EJTYXFhcWFgcOAgcGBwYHBgcGBicmJiImIicmNjc2Njc2JycHBgcHBgYHBgcG"
    "FhcWFxY3PgM3NhcWFx4DFxYGBwYGBwYmJyYmJycmNTQ2NzY2MzI3NjYlNjMyFhcWMhcWFhUUBwYmJyY0JicnNzY2FxYWFxYWBwYG"
    "IyImJyYmNCYlNjQ2MzIWFxYWBwYUBwYXFhYXFhYXHgMyFhYXFhYHDgIiBwcnJiMiJicmJyYnJiYHBgcGBwYHBgcHBgYjIjU0Njc2"
    "Njf8DwMCCwwMChsQCQgHBg4BBAskEQgDChAHAwwIBTEMBhQKMBABIh0YCBENBQIDBAkDCAsFAgYeDw0PDQUGIwQGBg0VEQkEFAIB"
    "GCsVFQcEAgIDARsgDU1rNw8vDRADBgQDBQMVBQcDAxEfIC0oQagfESAFDBQMBAYZBAcCAlf+ZgkFBy4MEAUOCQUdFRcMDhQJCIoD"
    "BwcUNQoJAQYDEggJGAYIFwoBCAoPAwQbBQcBBwUHECIUGSQhVRISKB4bBwshCAoZBAJJIQcREA8NAw+EGAcGGRwJKgYFCQ0iEgkL"
    "LyMPTwMEKhUlWRkBcRMCAhIVDgoPFDUqFwgRBSsJLwYVAQEDCSQIAwkOERk2EwsWEEUbeQMKAwwJCAwROgsVNw0GDhwdEAUGBBch"
    "CQkLBAUFDDY9IAEDEREFEBsoQlZYDQUFBQ4DGg5fBAkTDR4ZFhUIHSEeEhANBggYEwshDhgmUTOsCw8mBwoXHBASCAoMCAsOLAkF"
    "BAwOBxgXFuAGBAMEIAwNExsPFhYNEC4UCUcUCA8TBwgjAgMPBA4QCRUjH0cKCx4KGAoQBAIhCAcFEAsKCgt9IwwHHC8RKgEBEBYl"
    "ERASNSgRUAcFRBowjDMAAAcAMf+wA7YDGQAlADkAaQB8AK0AzwDpAAABPgIXFgcGBgcGBwYGFxYHBhcWFRQGBwcnJiI0JyYmNzY3"
    "NjY0JzYXFhYVFgYHBicmNTQmNCY0JjYlNhYXHgIGIgYiFAcHFxYXFhQHBgcGBwYHBgYnJgYnJiYnJiY0MjYyNzY2NzY3Ngc0IwYH"
    "BgYXFhUUNzY3NjI3NjY3JxcWMzIXFwcGBwYHBhYGBwYGBwcnJgcGJjU0JyYmIyImIyImNzYXFjY3NzU0NzYmNzYWFxcVFAcGJiIn"
    "JgcOBCIHBiYnJjc2Njc3NjMyNiU2FxYXFhYVFAcGBicmBwYnNDMyNicmJyY0AQUOFQ0BBBQHLQIBEgwcAwIHDRILFw0RBQYLDw4D"
    "CQxKAx2VIxwWEAEUBgkNBBkZEQQB9AwJBgojBgsJIAYNDQwLCAUHCAMHXBEBARAGBwsJCRIZBRINBQwLF0YeKwkHJBInKhcDFAUO"
    "AQELFgwKHasCDQ4IDCYQAwMBBgEBBwYBAjAhFwcGBgYICAU2BwQJBgMMAgIuLyUREwMBBa4EIxUdEQgfESR8bB82JUQwCgUEERAl"
    "CARZFlayYCA+/XsdEgoLDiQNChMiEBETAQMFEwEBDQsBiREdEAEEIw1cAwcfFkkEAgkTGA4HCh0FCQoKERwdHgkMZQQiBcgGDQoX"
    "GhwUCQwCAQMFFQgfCiQQFwMCBQgRDSItCRAQAgMMCQkOEwcMEAMLCg8CAgkICCxIEEILDQcQGgMFCARNCAESDBYoDAUKCgEBCA8N"
    "ObQSAgMnEUVEDDC1KXYJGCA8DQgICQICCgkJCAccEA8CAgQDBhESQEB6VMeaBggNEhcgEggIBREQBgYPCxkJCAMLGg0IKAMQIhYb"
    "Cg0HBgYpCQkSDQYDAQkIBgUtCAoVFQwAAAgAK/+9A7kDBAAbAC0AUQCAAI4AxQDVAQUAAAE2FxYWFRQGBwYVFAYjIgYjJjY2NzY2"
    "NzY2NTQ3NhYXFwcHBgYHBiYnJjc2NzYnNgcGBwYGBwcGFAcHBhQHBhQXFgcGBwYmJyY3NicmNjc2NzYlNhYXFhYXFhYXFhYXFjY3"
    "NjY3Njc2FhUUFhcWBgcGFAYHBgYHBiYnJiYnJiY3NiU2FxYHBgYHBiYnJicmBTI+BDIWFRQHBgYWNjc3JyY2MzIWFxYHBhUUBgcG"
    "JicmJyYGBgcGIyIHBgcGJyYmNTQnJicmNDYyFxYWFxYGBwYmJyYlNhYXFhYXFzc2NhYzMhYXFhUUBicmJicmBwYGJyYHBgcGBicm"
    "NzY3Njc2Nic0JiYBewUaCwQRCAtsDQkYBAEBBgMMSBAMGWkGCwwMAgQCBgsPBhEGAw8EAuUYDAMEDgkHDgUHDAUHBQUSGw8TFBEM"
    "JwgEAwMHCBFFVgFjAggOEQoBAQsXDBETKl4SCBkIBwcGAgIEBAIGBhYHByQQHW0jFSQMDAkBAf3pGy8vBgIKDA8XFCIFAgFGCBIN"
    "GwYlDBEMCzcDVBscAwECBw4yEzUSBBsNDRUODwEBCAwHMAoDDCIpFRMNBQEEoAkUEhoaDgsQCxcOGRMTAQIHDhQVFBEGMDALIBAN"
    "GQIEJhIQIC03CwcdBAUgThQODBEnNBgqIg4KBAENBAFPEBsLDRAfXREVBg99FQEICwMKcyMacR0XBw4BDxBAdDMaBAUFIA0FEnlN"
    "Hw0fBQkbDBIgDAcOHQ0wDgsICR8ZDwQCCBA4DwcFBRMDCF92MgMCCQobaFs2GQwJBgkMEgg2FxcHBAIKDXcFBx0FCAgPBQcPBAUX"
    "FAo0IiZYV2xfCxYWIA0MBQYJFSAYDBEVDiUDNBIGBw0LSQIGDg0eFQkfFDoLAwcHEQIBEBYbAQEGDAcwBxMFAgkGBwwRFCPICQ4V"
    "CgwGDhQlCgYNFhpvAwQMDh0rCwIBCgkLCAUNFhENDQcBAwcGAQUECRURDAIIFBcLCQcFAwcOEyIuAAACAFf/ggO/AuoAFQDvAAAT"
    "NhcWMzIWFxYHBiYnJicmJicmJjY0JTYXFhcXMzIWFxYHBgYnJicmFRQXFgcGBhcWMzIXHgIyHgIXFgcOAiMiJicmBxQXFgcUBgcG"
    "BwYHBicmJjU0NSY3Njc2JicmJyYGBwYHBhUWFxYXFxUGBwYHBhUUBgcGBwYnJjc2NzY2JyYmBwYHDgIHBhUUBwYGBwYmJyYnJiY2"
    "Njc2Njc2Njc2MzIUBgcGMzI3Njc3JyYnJjQ3NhYXFhY3NjY1NCYHBiMmBgcGJicmJyYGBwYGIyImNCcmJicmNjc2FhYUFxYVFBY3"
    "NjY3NicmNCcmNmMRJhgICiwCDx4KEw4QCAkcBAYaCAGyBQxSBAFDOSYDBiANCQgNGhsDCj0HAQICBQ5hHD4EFQ4oAxIdFgwtNgYG"
    "TxEcAwIDAQQGCgIHFw4IBwIDBAQFBAUPFgQHDAsOFh4BDRIKDAEOChgPNgoNCxIGAwgRMBkSAwIDGj8qJggMAxAGCCMIFRUKDAkG"
    "AggRBwRHBAM6BgkJAgMCAwQHWSojIw4ODRERDhQVDwsEBTATBwYTElgGCB0JBAgFBQUGBw0SEQwIIw8JAgoMUBwFDgIEClISJwgE"
    "CAcBAfUHDAcZBTAjCwEOEAQEHQgLGgkM9gEBDksXBwwXDwgBBgYCAwcCBw9DCQIHBjMOFgULDQcHDRAHCholDBEMAgIHjmkxHSoR"
    "KAMCCQgTKhUVXbFfCAYHDBAFBgQMDg8VBAICAgsLMDs0HyMYAgUqAwQHCwkDBw1HJVE+NwMNIRIQCCoHJzEqEA4hAQENFhkIBwYX"
    "HAcDXgQDVgsOEBUIBzkcISITFAgLFgoFBhUOBgMFPwIEAgEBASAICg4PBwUDAgwLBBUJBgQlGAwYBAcSFRMEDRYJAwIFFgMDBgQU"
    "FhUsAAAEACX/ngPEAyMAJAA4AEoBGgAAEzYyFAYUBwYHBhYWFBcWBgYHBiMiJicuAycnNzY2JyY2NjInNhYXFhYXFwcGJyY0JjQm"
    "NCcmNDc2FxYXFhcWFRQGBwYnLgI0NzQWFxYWFxYWMzI3NhYXFhcWFhUUBgcGFA4CFAYWBwYGJyYHBicmJjU0Njc2NzcnNCIHBiMi"
    "JiMiBwYGMjc2MzI1NCYnJjQnJiY3NjMyFxYyNjU0NhcWFhcWBgcGBwYHFBYXFhYXFhYXFhcWBwYGBwYGIgcGJyYnJicmIyIGFxYG"
    "BgcGBgcGBwYHBgYnJiInJyY2Jj4CNzY3NzYnJic0Njc2FxYVFDcyNzY3NjYXFjY3NjQiBgcGBicmJyYGBwYHBiY1Njc2NicmJjQu"
    "AtIDBxUOJQQBEhMEAgMMBw0PExIHCAgFFQECERAkAwIgMw2nASoOJRkHCQoTHQ4vDAQDqA4QCw4kEgoFCBgcCywI4CcLEiEJBggJ"
    "Cw4LFBQQFRIYEgkKDg4HCgQBAzMMDS0pEwkgIw0KJycBAxU5DwUeAgYDAQQHHToJBRUHCA8KAgQHChQrDwh4BQsMGwMEHRwoFBAC"
    "jB8RLwoPOwUHDxsBAQYKDxsLFyITBxpxgh0EBA8CBA8IBAQZBQ4dGAECFQ0LDwgPBgQfBAICER0PCwcIAwECBRAcEgYCBAdNHhcK"
    "CAUFBhQXAgEHCRAGCRwmEAMELgFJHwoDBQsUAgIBXwMGKQodTSoXGAkTAQELEAYNCw8RBRodGBgLCCYEBCZEzQMGBw4TEBMVJwUC"
    "BzkHChIDAhXFCgsIBA0dDxcQDAkXEwlKBiY+BAMFCSARDQYJBgEKBwcHFwwMHAIDCRwvFBIGMwgNFgcHHhsFAgwCCScEAhkYFRYI"
    "FRCcZW8bNQQFHgcHBxkRCgYKHQt4CAcCAgEYDRAnDhQVEQUHVQoHGwIDGAQHAgQZCAQBARgOFQwGCCiAHRgCBBwSAQIiDR84LRQU"
    "EgYGCRAHBiQHEQkKEUIrIatXPigWBhIYDwsPAQYOHAsLAgEHEhkNCgYGAgICBwcGEAgECBEJEh0MBwgKDAYhDQgAAAUAVf+RA5ID"
    "LAAOANkBAwEVAUsAABM2FxYXFhYXFgYGJicmJiU2FhYXFgYHBgcGFjc2MzIWFxYWBwYVFgYHBiYnJxUUBhYXFhYVFAYHBicmBgcG"
    "BwYGJyYiJiMiJjc2JyYzMjMWNjc2NDYmBgYHBgYHBgcGIjU0JyYmNSY3Njc3NjQjIgYHBiInJgYHDgIHBwYXFwcGFxYGBwYHBiYn"
    "JiYnJjYyJjc0Njc2NzY3NicmNzY2NzY3NjY3NjYzMhYXFgYUBgcGFjc2NzY1NCcmJjU0NhcWFxYWFQYHBz8CNjYnJiYjJgcGJyY0"
    "NzY3NhcmBgcGBwYGBwYGBwYWMzI2MzInJiY3NjYXFhYXHgIHDgIVFDI3NjYBNhYXFhYXFgYVBgYnJiYnJjY3NjYWFhceAgcOAhY+"
    "AhcWBwYWBwYGIwYGIgcHJyY2JyYGBwYGBwY3Njc2NDY0NzY2NTReEBYLDRkJAgMHJBgeCgMCGBgeRQUDBwcGAgIHDUcLA0IIBgEG"
    "AgERCg0aPT0OBhodDQwQDRYTCQsUMisyEQsLHQsJFAMDBQkSAgQmLRUVJARaJBUZFAUEBwgTDQkEARcJChkPDAwkAQIRDA4QFQwF"
    "BwQLDRsNCQkCAQUMEwoJCBIFCAQEAQcBAQMIFioWEh4JBQ0NGyIoDQoICQ0PAgUUAQQKBwMCAgcJJCYGBiIRHBMOCwMBEgkeHgcH"
    "BAgFDxsnExoSBQYKCRFaAjYQRhQLCAEDIAgEAgoNSAMFGQgBBAQFCw4aDAUJAQIEBQg6BQUW/pYGHwodDAQEBQEWHQUkBwYG7wEE"
    "CA0MCQ4HAgMFIAIwQCsaIwIDAQsIEiw7HxIPDgsLAQYGCA8qZQgFAQEPFyQRFUMB4wkLBQMEDBocDxcQKw8mRwICJgoJLxINEQ0G"
    "AgkGBwYMFAwCBAsFAw0BAg4NSQwEBgsSERMIBwYECSJBNjEYEAscDwQEBwoEDhYWBU0MBQcCBAkMDgQEBAYQCg4SKwcCES4bBhEH"
    "BwYIES4aDAwKGh4XCgYIDgoGBggDAwkeCBEDAxMKEw0HAgU4HxMlBQMNDQsFCAICDCAqNhwICh4YBw0KAwICBwYCAQIELw8UBgcG"
    "AwEFEBwTCgIBMjIQCgYDAggLDgMFBwoECeMDAQMPAwIGCA5ICAYCDCgMEQ0KAgIFCgQBBwgDAiQEAwUEA2wBoQMDBg8LDBAJFxkN"
    "CQE4EwwcVQMCBAsLBhMOAgIZNwcQCwoHDAkCGAsHAwIMDQ0ICAgHBAQSMWYDAQMFFiEENAMaIIYLCQAAAgBM/74DnAMEAB4AqgAA"
    "AT4DFhcWFxYGBwcOAwcGBiMiNDY0NzY2NzY/AjMyFBYUFgYVFTc2NzYXFhUUBicmBgcGBwYGFxY2NTQWNzYXFhYHBgYnJgYjIgYH"
    "BhcXNzY2MzcXFhUUBhQHBgYnJiYnJgcGBwYHBgYUBgYjIiYnJiY1NTc2MzI3Njc3NTY3Njc2JgciBwYHBicmNzYyNjc2Njc3IyIG"
    "BwYnJiYnJjY3Njc2NjU2NgEIBxcMDwoKExkSDSJRNRcMNwIDJgUIDisfPAYDDOADEREpDQkWFSE4GAcIEBFYDxMFBAMDAxQRIz8Q"
    "BQMEAxEgMiYIBQUDCAIBUlQlNzUYNw4HBicFAkUgfFGFHzwFBS8lERYUFRQNBhgaCApoKTg3AQUCAgQEDwQELBQUJiYaDA4yIycL"
    "AQEQDCMICQoIIwQCCBYeKSIMAggCbg0kJwgBBgoVDykhTzUQEysEAxMRCwkwIUwMBxWYHwgZBw43KyoEAwkOEgUoHxADAwEFBgsJ"
    "WQYDAwYEBQUKGQk4CAcBAwULEB45OxoDAgoBECIaEA0GCQYEBgUSBBAHCwYPBAMLCQ8UCxIMDREYCwoVBwgHFBU6CQ8rDgEBARQU"
    "IyIKBhcICREyOw0JBgIBKAwIBgYIDQoPIhtMAAACAJb/ngNSAyUAgQDMAAABNjMyFhUUFgYUBwYXFjYyNzY2JyYHBiInJjU0NjI2"
    "NzY2NzQ2MzIWFx4DFxYWBwYHBiMiBgcGFhcWNjc2FhcWFRQGIyYHBgcGBgcGBwYHBicmJyYmNzYnJgYGIicmBgcGBgcGFAcGBwYU"
    "IgcGNTQ3NjQ3Njc2Njc3NjY3NjU0Njc2NhcWFhcWFxYWFRQHDgMeAwcGBiMiBxQGBwYGIyImNTQmNTQmJyYnJiY1NCMmJzYXFjY3"
    "NjY3ECYHBgcGBwYmBiImNzY2AVENAQMfDggFCAcDRxoBAgMCAhIMCgwiHggqCgcDARIVEQoFBwMFQgwKAQgJAwgnEQYBBAEEAyQg"
    "GAsGBg0SVAcHBAIIAQESEwcSCQIBBQIDAwUFGhIOEg0MBw4RFQwTJiIQDQ0UBwYaIg0EGgUMBAcEEQjRHxpaQjQEAxATCwYJBgMK"
    "BQQIBQkIHgMEAQ0HBiQKCA4MCBIZDw0gBQIBAiEmOw4JBQELQFRGHgkHHgUUCwEFcALJCyIDAwUjywYICwQdBQdFAgIHBAYOCwMb"
    "FAIDFTQQDgQHCjgDAQgHCQ4QCxMECQ4vAgIHBgMBBgkbGBMBCAhDJywgQiUoChgyCw8tsB4aAgQHEQkGBBc4LSwYBhw2DgcICxAJ"
    "BAgIDiMwIAo3JEAaRxRPVCgeYgEGAQEHCQYHCRMSFQgKUuo5BY0wShYSLQUEEAYDGwoGAwUTDAwSGAoJIAUDAQECCwsKFg978AET"
    "DAEBCQMJBwYNHAcNJgAABQAd/8MDwQL/AFgAtADGASQBYAAAEz4CMzIWFxYGIyIGBhcWFRU3Njc2FhcWFgcGJgcGBgcGFAYUBjc2"
    "FxcVFAYHBiImJicnBwYHBgcGBiMiNzY3NjY3NicmBwYGJyY3NjY/AjY2NCMiJyY0BTYmNjIXFgcGFjQzMhYXFhUUBiMiBwYGFxYG"
    "BwcXFhcWFhcWFhUUBgcGBgcGBicmJyYmJyYmJyYmIyIGFRQGBwYjIgcGNzY3NjY3NjU2NjU0NjMyFxYGBwYWFxclNhcWBwYGBwYG"
    "IhQiNzY2NTQBNhYXFhYXFAYHBgcGBhcWFgcGBwc3NjYWNzYWFxYHBgYnJiYHBgYHBjU0Njc2JicmBgcGIgcGIyImNTQ2Nz4DNzcn"
    "JjU0JyY2NzYXFjY3Njc3BwYmBwYiJyc3NgU2NjMyFhcWFxY3NDc2Nzc2NTQXFhcWFRQGBwYGBwYGFRU3NjYXFhYHBgYHBgcGIicm"
    "JyYmNzQmIyc3N9EIDk4CBRwCCBYSCiwHDhgPDw4SMQkTAhEKMyUXDwYGDA4GGi8dBAkNDiYWCggONS4dAgMnBAw1Lx8HGAQDBQgl"
    "NhcMFCMUGTAxAwMHBAULCgGEAwIGHAkgDQQHHxQOCQsPBAIfGQsCBA0EAhkaCAxgKEsqDRkRJwQEEwgGIylnIhBJBAMMAwMOIgpI"
    "CQshDgIBDSskHCUBChkFCQ8IAQgGCCAY/lIJFhgZByQHCxMUCA4QKwHbHBMPEw4BCBQdDgwFBwcDAwUQETIyRxkLCx0ECwsIIAsH"
    "HQMERAgGFwwLBhsUaBEQCw1WDQ0XBhEXNFEUCQoKJw4NARATGgUJCQ4DAxQUDyQaDAcJCxP+uQEEBgQRAgEEBAYBARAjFBUFBREP"
    "HBcdEw4FFhQrGSEYDAYJDxYcLSELDQUEDAEFBgsPEAF5BAwaDQQMHgoGBw8kDwIDAwQBBgshCgUKAwIDBwgMEBINAQQaERkTCwkK"
    "IyIKCw89HxUDBBU3LTQMMwkKAwURGAYLEhELBhIRHx4NBQkHEowUrQoFES8NCQoDCAoKCCIBAQoSEg4ZGRIQCAotDBgXEAkIBQUU"
    "BwQBBAMLDEAgEVYGCQ8cCAUyCkUfCwQFDzM1OEoiFgQGEVUcD0ILCQsgG98PFRcqDSIBAh0HGRtWBQYBSgUBBgUREAwMExsMBxID"
    "Ah8OEAwNAwIICQICDQgYFBASBwMBBAMaBgcEBBwVEgYDAwkGBgYmFgwKBgcJChUFAQILKwQCFRQSAwQHAwoUHQwLAwMBBwQGCQoS"
    "RkkSEQUILS8KAQEEEyoWBAoPAwYQDQwSExAbCwoJDxQCBA0GByMZCwYBAwQIBQcLCzYFAgQBFRUAAAIAPP+eA6kDJQCRAOUAAAE2"
    "NhcWFhUUFxYHBhY2Fjc2MzIWFxYWFxYGBicmJgcGBgcGBgcHNzY2FhcWFhUUBwcXFhY2NzYWFxYWBwYGBwcnJgYnJiYHDgMiBwYG"
    "Iic0JjQnJwcGBgcGBgcGJyYmNzY2NzY2NzQ2NTY2NzYyNhY3NjY3Njc2JgcGBgcHJyYmNTQ3NjY3Mjc2NjU0MTQ2NBM2LgIHBgcG"
    "BgcGBhYzMjc2FhcWBg8CBg8CBhY3NhcWFgcGFgcGBiMmBwYjIwcGFjc2NzcVFBcWFAcGIwYHBxUUMjYzMicmMzIXFhY/AjY2AbAI"
    "BQoKHgQJEAoFHAcgMD0PFgsIBAMDCRYJF4omDQkKDgoCAzk4FSwKCiMNDQICCs0TERMOCQQCAgUJDRMRGxANsgYGDRAaCAIBDAoB"
    "DxMTLCoaOTNANBYRExwHBW0vFwYBCQEKBQYKEA8GBxkEBgMLJRAJJwQEERcRBw5FFgUHLBAMbAECCz4dKRUKEQMBAgECCl0cGwsK"
    "CAMCIjU2HgQDBB1XKwkEAgIJBwUMGzYgCw8QAwIDEiRZGQYGBwcxNzIPAkUNFxEOCQkWERQZEAQCCAMQEAUBAh4IBwMFHxQECgUG"
    "CBcHAwoPFwwCBA4RBQIJFR0MCgkCAgUUAwMkBwkWF7m5DAQCAgsSDQwREAwICwgJCAYEBgUDHAcTAwQEAgUQEQwNAwQGBQMMEAYF"
    "BiMLCSIJAwohKEVRR5cSDhYFAgIwExMCBwUFBQ0KCwkMEQsNAwgUAwEGAwcBCh0V/j6CMwUBAgQOBgkKBhgSHwgDDQ0KEhAEBA4I"
    "ExIGCyEPBAUGCBUKCQIBDAUiIQIIEAcCCwwKDB0BAgEMBSorDRcSEQ0GAQITEyoAAAUAEv/XA9YC8wBrAH4BOAFQAWYAAAE2FhYy"
    "FhQiFRQjBgcGBhQWFgYHBhY3NhYXFhcWBgcGFRQGFAcGFzIXFhQHBhUUBicmBgcGFRQGIyInJicnBwYHDgIHBjc0NzY3NjY3NjY1"
    "NBcyFxY3Njc2NicmNiIHBgYnJiY1NCcnNzY2EyYHDgMUBhYXFhYzMjY3NjYBNhceAhUVNzY2FjIWMhcWFAcGFRQGJyYOAyY2NDMy"
    "NicmDwIGBwYzMjc2NhY3NhcWFgYUDgIUBgYHBhYXHgIXFhYXFhYVFAYjIgYGBwYGJyYnLgMnJyYmBgcGBgcGFCIOBCIHBiYnJjc2"
    "NzY3NycuAicmIyIVFAYUBgcGBwYUBhQGBwYGBw4CBwY1NDc2Nzc2NzY3NjQ2NDY3Njc2NzY2Jyc3NxcWFjc2Nz4CBzQ0JiMGBwYm"
    "FQYHBgcHNzY2NzY2NTY2FzY2JyYmBwYGIgcGFhcWFhcXFjMyNgEjGj0IDBUJBAUxNSgWCRQFCA4xLxwbBgEBAwckFwkKBwgJBwUH"
    "FQ0NNQ4KDQQOCQgOBAsgFxMKIgkPAQEDJQ8kEBMHCQIDBwoIHREFAwMJDAwJCwoNFgkJDA9NVQEiDSsEEg0CCQcGBwsqCRYMASYK"
    "BgIkCScmBAwYLQcHBgYGIAkGKQgXGQoeAwQLAwIdHAYGAwIEAwkQDAwJCh8KFQgLCxgKDgwJBBgPBCoCBIASCxUFCAgKHRAMCQse"
    "HwwiDxoOGw4MDgEBMwwPEBMUDxwYFA4JBgQEEAolcSgIFRYGFgQLCwULCAMICQYPEQIDUw8NIxAPEgMFFDsUAgUSChYKDA0QBwMF"
    "BwIDCwoIBQUDDzAiCQMEAQERFQ0WAQYEAgEODiIJBgMBCEEBFgEBBw8WJg0HBQEICw4GCwUDARcCbAMCCA8iBgUBAQENBwsXQwoP"
    "BAEBBQ4DEw0IBRoHBRkEDBABBwUIDRIGCQoCAgcFBAYHGDMpIgsMIQ8MChsIDgoCAgkoEDcYGhERHgIDChIRRCwOBQQGCwcEAQIP"
    "CQYJCg0RGv78CQgDBQwXCQkQHBUKIRElIgGHFwoDEgssLAIBCAgeCAgeBwYECgUHBgcHBRkJIwggAwMFBERECAYBAwwEAwQNAxoO"
    "ExUbMwUMGhAOCBAKBRwEBTsFAxcKCwgKBQ0IAgMHFwcUDhQMGg0WCAMEIgYHBw0GDQUMBQQBBAUMCRhLNAsbHQwmCRcJCQ4cCAwi"
    "CgUMFAkVBAlXCgoZBAoNBQEDBhdAFgULFw4FIggMHR9KHA8VWSQzCAcLBwIEDwkHBWjHCBAIAhEJBQc8GA4YGQMDDwICBxEYKbwD"
    "LggEAQMEDAUDBwoPFAgNBiUAAAQAif+qA2QDHgBEAFkAdwDNAAABNhYXFhYVFAcGIicmJgYWBwY3Njc2FxYWBwYHBiYnJiYHBgcG"
    "FRQmBwYmJyYmNz4CPwI0Njc3BwYmBwcnJjU2Njc2NzYzMhYXFhcWFgcGBgcGJicmJicnBzQ+AjMyFhcWBgcGFAYHBwYHBgYjIiY3"
    "NjQ3NjYTNBcWFx4FFxYXFhYXFgcGBiInJgcGIyI3Njc2NTQmJyYmJycHBiMiJjU0JgcGBgcGBwcGBwYGIyImJyYmNzY2Nz4DNzYy"
    "FxY3Njc3JyYmNgIMEDgIBwsVCQoPEiAHEAYLDAaZKBIjFhYOEg4RFBYoVXQzUBYBAwwODhEDAygrMS8CCAMDDQwQEREREgIyEoUr"
    "CwoOVQoOEBcLAgMNEBIdFBgmFBXfHAEVCQ8tBQMSDhEhCikeAgUrBAYBBAYUDjVkJjMEAghULjQVHjYlCAYCCB4PAyQSHRcpDAoE"
    "AgccDx4aKCkpEBAEBRkPFxhNDRELCwYCARoUDAwKCwUCAgEGBh8QFAgGAwQJFh1DKAIDBhMBLgQFBgYZChYNBQQGAQk7IlAEAgcB"
    "Bgs3EgwFAwEHBwMBAQgOEQUFBAYGDg4mBgUGEAcHJSUzGhkDBAEGBRETAwshBBOuCxcHCAkKFRsZGAUGCxQZIRscKAUtHBosFA0c"
    "BQcKGgskGQQEGQQFCwkVD1MBcwsTGzQaCQsLBwgBAhIECg4vFwsGDBcUIAcDCSQZDwoGBg8DAw8REQMLBAQEFQcHNDMcFBMXBQ0N"
    "DhYcCAYFQBolBwYGDAsODAgnJiAMAAAEAF7/jQOHAzcAjQCjANgBDgAAATY2FxYzMhUUBgcGByIGFRQXFhYHBzc2Njc2FhcWFgcG"
    "BicmJgcGBhcWFxYWFxYWMh4CFxYWFxYWFAYnJgYHBiInJicmJicmIgYGFRQGBwYGBwYGBwYHBicmNjY3NjYzMjY3NjY1NDc2IyIG"
    "BwYmJyYmNTQ2NzYyPgI1NCYjIgcOAic0Njc2Njc2Njc2FhcWFhcWFhUUBgcGJicmJyYmNzYlNDYWFx4DNzYyFxYWBwYGJyYjIgYH"
    "FBY3NhYHBicmJjU0NiIGBw4DFCI3Njc2NzY2JTQXFhYHBhcWNjc2MzIWFxYHBiMiBwYmJyYjIgcGBgcGBw4CNTQ2Njc2Njc2NzY2"
    "NzY2MzICEQkUCgYGDwQICwMGKQsHAgICEhNgLDUbDgkBBgYUEg6WJRQIAQENEkgQFBYGRxIKCgwvBgUPGQkJLQwJEBkuRCEqIBEH"
    "BwodKBcXAwVjFRgaKAoBEiQcMSMDBSgTESYGCw4RfQcFDBITDggVHhI/YAYDCAkwGDEcAh4OGIIMBQ5/HRMFBSQNCQQQDAwVFjUO"
    "DAEKCv7THgcXDwYCBAkMKAkHAwECHCMbBgQ3AiIQJxgWEBIOOg0IPSEkLxQSDAMILzInIDMBDhwjDAsHAwIkAQInHQ0GDwoHJRAP"
    "DhEPGAwEDA5eIBYCAg4LGh8CBRoCBAcRHQQCBAQIAhcOAwoHKhEMBgoBFgQFEAsLDhUCBAMGCAYWEA8PDgYEBAEEAQQHCRUZUQ0Q"
    "Ei8HDAIDFgQFCRgXAgIRCgcKEkAdPDobGAYGCSMqFwwECDUHBxAXCgIRHhYmHyoXF0IJBRAiIwcGAQYGDg0LBwkMFBUKJBsKEQcL"
    "AgQGGAYJSgwEC1YDAQYFEQwICw4THQUECxUyBwUJCwp3Bx8FBAMGEgMCAgoIDRIiDRIOOAQDAwIEKiQcBwU9CgUPMh8iIhIECAYO"
    "MjUuJ1FoCxgcFxYOAgIRBQUDCRIbFQgHAgsSEhhcFg8EAwkFAQUeJwIEJAQGDB1bKBIKAAAEAE7/hQOWAzsADwBmAOABFQAABSYm"
    "NjIXFhYXFwcUBgcGJwM2NhcWFxYWBwc3NjYyNzYXFjIXFhYVFgYGJyYmBwYGBwYUBgcGBgcGBiIGIgYiBiY2Nzc2PwIHBgcGBgcH"
    "BgcGBicmJyY3Njc2NTQ2Nz4CPwM2EzY2MzIWFxcHBhQXFjc2FhYUBwYjIgYnJgYHBhQXMhcWFxYWBwYVFAcGBhUUBiMiBiYGIyIm"
    "JyYmJyYGIyIGFRQHBgYjIicmJicuAzc2Njc2JiY0JjQmBicmJjU0NjYzMicmNzY2FxYWFxYzMhYWFRQyNzY2NzY2FyYmBiYGBgcG"
    "FxYVFDc2NzY2NzY2FxYzMhYXFgcGBicmBgcGBwYXFhY3Njc2MhcWNzY2NTQCLRMTCTMTFE4OEAENECU0pAgGEhMPCwMBA1RUQz0G"
    "DR0SCgwKBAEKLC4m6BMMBwIEIAMOMw0HMggUEQ0UNwNFCyc3CQ4FEzcSEiIKIRcRDBQLChEZBQECBTcYGDVOLi4DCAZqCwoEBh8I"
    "CwYEBQgFBTgKBQsvIBINCgsSGCpEIxcIDgoJBiAHExEGBg4KBQoLEwIBCQ8WKBALEQYEBwgMBgYPAwIUCgYGBi8LDwMLCwghDRAM"
    "LwgIDxYOAwEGDBgWAQIIBAIQCBAKDRUbDgseFiQGIyAQGg8HDAQGEi8PCwkCAg0LEgMCCgcJDRIiEDUEAw4FDSQjIhcOBQcBBh8L"
    "EyUMBwYtDQ8jHhkBAzkBaAgBBQYSDgoRFQIBCwcOEAkKCAoRFg0EBwQEAgIGDhMVEwgdQAQCIRAUDwNFDS0+FRwKAwgEBAMFDAgS"
    "DgQJBwoPCgIBAgYEGAUGEAwKCA0tIAHcKBsZCw8eFQgBAgQFCQ0mBg8MAgEGEhkFAREKBAQ3EQwGD1oWEgIEDw8EBxEMBwUDBgwK"
    "BgUOCQcIBjEUFEk4BwcHHgQGEQ0ICRoFFwIDCAgLHgo7IwsJAgIEHSAoVxMIBgQDEio4JMEDAgUEEAkKEBUHBwoHAgMKEAsKAgUE"
    "EA0LDQgDAgIMAwYEAiUOAQoLBAIFBgEHeg4NAAYAUP+FA5gDRQASACQATQEgASYBOQAAEzYWFxYXFgcGIyImJyYjIiY2NDc2FhcW"
    "FhcWBwYmJyYmNTQmJhM2FhcWFhUUFhcWFAcGBwYiJyYmJyYiBicmJicmNjc2NDI0NicmNzY0JTYXFhYVFBYHBhYzMhYXFhUUBgcG"
    "JicmBjIGBgcHFxYHBgYXFhYzMjY3Njc2JicmJyY2MzI2HgIXFwcOAgcGFhcWFhcWFhcWFRQjIgYHBicmBhcWBgcGFxYWFAcGIicm"
    "BwcXFgcGBicmJjQuAycmNhcWNzY3MiYnJyYVFAYjIgcGBgcGBw4FFxYHBgYnJicmJyYmJzQnJjY3Njc2NDI3NjYXFgYGBwYWNzY3"
    "NjY1NCYjIgYHBgYnJjY3NjQyNjY3NzY2NTQ3Njc2NzYTFjYnJiIHNQcGBwYjIhcWFhcXNzY/AjZkDy8LHwoKEgsNDxAQHQsDCgmF"
    "BhAXFhsMFB0NDRMVDBcDPAYJFR0KDAUFBgYEBAkKDBYCAwYUDRAjAQEWCw4LFAEUBgMBBw4gDhcLCwwEHBYREBcPBQxWBAYJBQoM"
    "Hh4HERIHEwEJIQIEGAICAwILCwsBAg4HBxMmExgJCRQUCx0GBAIIGp0eDU8MCxgPSAkMKxEDCAYCDBcCAwcOCxYfJkcVAQEJBxoI"
    "Bw0LBBEIBQgMDg0ZN2QyAxY6LEYFCBwRRSYeBQIQHAYGBwQKEAcJChwUCwkGBAQBARA3DAc2BxkWEwYHBgkCAQIHTh4eMScFBC8T"
    "DgcFBQULDQYcCAcNBQ4JDxUMDQKKCAQIBwEnFTc4GAYKDAcFCwoSEiEgChABSQMCBAscGhwODRctDQQLugUCBwcXFycRCAgCBAgL"
    "DRYvARkFAQcKECQqOSIYDQkLCAcGCSAOERUCAhAFBhkGBgYJBwhWBQQQJBAUCBUDAwocIAoFCg4JCRgBAQMBAg8MEh4eChUWCh8B"
    "ChgxDAwGBQsDAgkIEA0KDgsTEhMUFCsHBgUHFk0FAhoFBQ0VHAkMEwcDDwsPIEQODQQaCQcICwsDEREKBwkCARgRECdKKw4TGwMC"
    "DBkBBxIvJQkERxgPGgYFEAYZNggmGgsXGAsEAQMiFAIBDBwBAQgWOgwHOQkmIBQDAikLCwgBBDIaGzMFBy4yDQgCBgcfDQ8IKwUP"
    "FgkjBAQJET0lexv9hggGBAM/DgIBEAkZEBccHgQCBQQkQAAABAA5/6gDrwMaAFAAhACbALYAAAE2MhcWFxcHBgcGBicmJgcGBxQW"
    "FhcWFRQGEgcHBgcGBwcGJjc2JicmNCcmJyYzMhcWMzY3NjY3NwcGBiYGBgcGBicmJyY3NjY3NjY3NjMyNiU2MhcWFgcGBgcGFRQX"
    "FhYVFAYHFAYHBicmJjc0NiYGIgcGBgcGBicmNjc+Ajc2NzY3Njc+Ajc2FhcWFxYGIyIGBwYmJyYnJjYnNDYXFhcXFgcGBwYGIgYH"
    "BgYHBiMiNzY3NjYDQQUsCQsUFQUGBwUJEzNBMT8BBAcEKwwBAgUDBxUeIQ8MBAMfDAoPFA0GBgIXKiAKBwYCAQERESAICioNCAkM"
    "KwoQFQxXISEqHWsTDjf+DQMFFg8EAgINGysIDBAJAQcPEhoLAwEJAkYGAQQ3CQ8SCAMBCQ0kHw5ECgwgKskYPSEDBkADBwEBChQP"
    "Qw0LChI2BQIHrgQGCxQZCAgLEgsOBy4PEBYNJwgDC1YaDxMCNwQFAxMSERIJBwEDCgMGBwEBBAUEIRIKHv7HES0bCBkJCwQFDA5K"
    "CggQCAscDA8bAQkHQIC8AwIIBgkODQkDAgcKEA4JHwkICwURDhUHFRALDw8TGy0IAwYFMBogDGpULg0QIAsQICrPA0UDByQCAwkD"
    "AgYLECIlD0sQEC05iQwWEAEBFAQHIBoODgcFAQoeDgcHWggDAQMVGwkPFwUCEC0UEwkIGQ1nNBwdAAAFAEb/hQOkAzsAEABZAJUA"
    "qwDyAAAlNhcWFxYGBwYnJicmJjU0NjcmNjYyFxYVFhYUFjc2FRQWBgcGIicmBwcVFAYHBgcGBwYHBiY3NiYmJyYmNzYWFxY2NzY2"
    "JycHBgYHBgcGJjU0NzY2NzY2NzYlNjIXFhYVFAcGBwYHBjc2NzYHBgcGBwYHBhQGBwYHBiYnJjU0Njc2Njc2NzYmIyIUBgcGBicm"
    "NTQ2NzY3NhcWFRQyFBYWBwYGIyImJyYnJiY0JTY2FxYWBwc3NhYXFgcGBicmBhUUBhYWNhYXFhYXFgYHBgYnJicmBicmBwYHBicm"
    "Jjc2NzY3NjYmIyIGJjU0NzY3NzU0NjQByC0SEQUBAwsNCSIfEAUPngULFggMFgEaEBwzBwcOCAoNEg8OChMPBwwdEgkMGQMCFhIK"
    "CBoCAyAfFgwJDQcBAQwaTAkQCQ4oFgxlNg4FAQP+eRkWEg8FChMEAgUHCAYXOAMCCg0EDhULJwQIFg0NBwgEBhMUBgMDAgMGCyUR"
    "DxYODRMoMTIJGCUMFxECAxUVDAwIEQwCFAFBEBEVFggBAR8eFgIECAgVFhsKBwPfEAcXFRAHBwYMDRUVQpJUFgYLWkMUGRAHBAQJ"
    "dVACAgEBAQMpFRkNDg8M5wsQDygPCgoOAgcWCgoPExOkCiMMBQwNByISBAIEDQcHIQcFBQcCAYt6PBIODBMMBwcKCwwJFx4HByIB"
    "AgwBAQMJDDZidwECCgMGCA0OEhENBhMGAwQOEoQLCQcICxAUK3UxExcBARc6IQwaHBArGg8GLhEbCgUHEBImJBkDCGx6TQYEAwcV"
    "ERACCgsPFRMTGegGAgMIAwYPIxUcGAUKEh0GHyFQEAEMDRQrNQEBChAODhAKAwMKGyAcAwYKBwQFBwoKJgwNAgkbAwELBAYSDhAU"
    "FQgkBwoZDwMBMTERCg8kBQIEBSYnHBQAAAQAHf+vA8wDEwAVAF8AqwD5AAATNjIXFhY3NhUUBwYGFxYGJyYmJyY0NzQ0NjYzMhYX"
    "FgYHBgYPAgYWFhcWFhcWNzYeAgYGBwYUBhQGBgcGBicmJicuAycmJgcGBwYmJyY2NzY3Njc2NjU0Nz4CNzYXFhcWFgcGBhQGFAYH"
    "BiMiBhUUBwYGFQYXFhYXMhYWFAYHBicmJyYmJyYmNzY2NzYXFhcWNjY3NjY0NzY1NCYGBwYnJiY3Njc2NiU2NjMyFhcWFBYHBzMW"
    "MxYWBwYnJgYHBzc2NzYWFxYGBwYnJgcOAiMiBgcGBicmJjU2Njc2NzY2NzY2NzYnIgcGBwYmJyY3NjY/AjaMCwcXGBUGBgQFBwMC"
    "GBsQDQkK0QQFBgwoCwkJDw8YCR8rGgViIByGLZoyHlc1BBIaBxEjIAQVDxUcMpQRDDQkWDMxLhQsGg4ODgsFEC4pHBATQQQDHAz0"
    "GiQNEAsEAgQGGw0HBhYSPQkGBQIOCxxQUBAdCggRJA1HOywQFg8DAgQHDgkBAgEaHgQKCgUXEhsLFwsJAwICCgcv/sADBgsJCwgP"
    "DAEBERIPFxEQDyQRCAIEExQVIzcJCQIKEBlDOi4gHAgINRAWFxEMBgIIFR44JxUIBwYBAgcDCAkNCwoMHAUERg0OAgIBTBcREggE"
    "AwIBCAwDGiIcAwMQIBwYUAICAQIWDAohEBMfCRwnFQUZBwUjBhUEAgsCBhITAgUFFwYRDgcEAgQGHQcFDxEfExIMBAQTDAINCxkM"
    "IgcGDRJcCAMCATwk4gIGAhALCgwUDBwkEB0HBw8EBAICBg0rHRQGAQkgHQcSIhEGBgUOERlEPycXCxUGAQIFCxMGDgYMCykIAgEF"
    "AwYFAwcHDQgHDqMJBQYKEA4QGRkBAioREAkGESsvAgIEBQcMCCEKEgYLBQUDDBYLEAENCQoJCwcLDw8KCQkKERkmAQYFBAQBCBAV"
    "Ch4CBC4wAAQAK//vA70C1QAXAGwAfwDPAAABNRcWFxYXFjIWBgcGBwYnJjU0JyYnJiYlNjYzMhYGBwYHBgYXFhYXFhcWFhcWFxYW"
    "FxYWMhQXFhYXFgcGBiMiBgcGBicmJyYnJiYjIgYVFAYHBiYnJjY2MjY3NicmJyY2JyYGBwYiJyYmNzY2NzczMhYzMhYHBgYjIiYn"
    "JicmJiU2NhYWFxYXFgcGJyYmBwYXFgYHBxcXBwYHBgYHBgcGBicmJyYmNzY3NiMiBwYHBgcGBiI1NDY3Njc3NjU0NicmBgcGIgcG"
    "JyYiNCcmNzY3AlYXKCw6EAsGDggDBRsjHg8bBxUZCf4kJhsPFg8BCAkGBgEGBhEcIgMDFh8mMU9CV25TJRgPCAECAgIfCQw2GCEo"
    "NCJCLndtRRQcKgkNCwkIDAEBCTQSJBEMEggEAwQ0DRIJDgoDAgMWWgIWFycECRcDAyMFBCQDBxEIAwEGIF8EmgsTBwUUEx0TXwMB"
    "ERUEGhgMDQcHAQYGBwoFBRABAwQGAgYFAgMDAQI1GxIODTAIZQgDDR8rDAIEPgsMChYqFwwIBhQkDRMByRUCAxUbGxMYFgwVCgso"
    "FAIGIAoREw8lEwoSHAoMHBQPEhobHCIMDw0FCA0UCgMFCwcIBgUIDAkGFBgQFQITCwoGMCsXHBIOCgIBAwsRGxgsBAsjF0MhPwIC"
    "Gw0RCQYHDxES8REUMQ0IKCMGDRkJDR0FCwMFAgQjHAcIEAkIBwUMDx0cHBAQHh0nb0QSFQkHAwUGEBI9GRs9OAREEQsLChsGBZcE"
    "BBMuPxUJFwUEBgUHChQXDAsFEQ0EAwAIAEb/qwOjAxYAGAAoAEkAWwDuAPoBCAEYAAAlNjcyFhcWFBYHBgYnJgYHBiMiJicmNjc2"
    "NzYWFxYWBwYHBgYnJjc2Nic2FQYHBgcOAhYUFxYGBwYmJyYmNCY1NDYzMjc2Njc2JzYXFhYXFgcGBiMiJicmJyYyNzYWFxYUFxYV"
    "FBY3NiQ3Njc2FhcWFgcGBicmIyIGBwYWFBcWFhcWFgcGFRQXFxYXFgYHBhQOAgcGJyY1NCYnJiY3NhY3NicmNTQmJyYmJyY0JgYH"
    "BgcGBgcGBwYHBgYHBicmNTQmJicmNz4DNzYnJzc2NzY2NzY1NCYHBgYmIiY3NgciBwYHBiYnJicmJjc2BTUjIgcUFxYXFjc2FyYj"
    "IgYHBhYWFxcnJiYHNjYiBwYGBwYGFxY+AwJDLh0SDgkNCgkJFR4gVgsLCAgnBAMFEi03BD0GDgkHB0ktExAfBgVY/woBCkwIBggC"
    "EgUHFhQZFw8PDAwTCAwNC2MXFdUJOCAUBxAbDAsLEAoYIQkFDJoNKhIUChQDBCIBCjsxCQheDgwUBAQ1FRs+GlYDAxQnIiIYDwcD"
    "CgUIBAUICQsFDREVBwsPBiwKCSQBAzwJKBAHDx0sHAIBCQoBBAMELTMVBQUCAQMFDAUBCgMECggFCQQKBAgNCBAQBQQzCwcKKCEK"
    "ERsUAwIFBAgJCwcMDSwXBwEFBgF3Eh8DCAkHCwsGWgoODQYEBQggDQwCAQPVDgUIEQsHBAYIAgEFCgoKyQgBAwgLDwkTEggEBAMG"
    "BRsJBwYIFY8EAQUKIwwOCAUEESEGAxxcDAcGFZofFhAkDQwICyQNDgkaHAYkGAYHEA4MgiIemxARCwwNIh8OBxIYIRoO4AYCBwoK"
    "CBIcCgUBDi8EAwUDAQUDIw0aGxIXCAMBOgkEAhEcEA0JK0I5IUkrERxyEAgXCyQODRYEAwUGLgUELwUGAgQVrEwaFw4DBDRKOQYB"
    "BAQHIz9NIw8PFXxPLQUPCQICBxMNFSYfEHMWaxkwEQ0MDAUEGQMCIBwGBwYQDAwNDQILDQMBBw40EAUGCQ6DHAsFAgITGgQDMwgQ"
    "LisGBwQDNicSbR1ICgcLFx5SAQEHDBEUAAAEABz/qAPKAxsAFQCPAKABAwAAJTYXFhcWFgYWBwYGJyYiJicmJjc2NBM2FhcWFBYH"
    "BycmBwYXFjc2FhcWBwYWFxYXFhYVFAYjIhUUMzIXFhYXFgYHDgIHBgYVFAYVFBcWFhcWBwYGJyYHBgcGBgcGIhQHBiInJiY0IiY3"
    "Njc2NzY2NzY2JyYHBycmJjUmNj8CNjc2JiYiIyImNjU0Njc2NhcmIycHBgcGFzI3NjY3NDc3AzY0MjY2JjIUFhYzMhYGBwYGBwYX"
    "FjMyFxYWFxYWFxYUMhQWMzIeAhcWFhUUIgYGIyImJyYnJiY1NCYmJyYmJyYnJiIHBgYHBgYiFA4CBwYnJjc2NzY2NzY2NTQ2NDY3"
    "NgEBDg4FFxcRBggGCTMFAQsGDA0EBQbgJRcHBwYPDxkrDgIBAgMFIwQEAwIOHSIHBRIYBgUVCgwKBgUGCRYWEjMSCwYMZlEmBwUH"
    "CiYhTngjGBE3BgQSDAoHCQoXBwUOF1ckCQsYAgQCAgQUFB0TCQEgIykDAgIBAQQHBhMiBSc1GA9WCxoaAwICCAgDCgsiAQwLjAkI"
    "BBIDES4EBQICBAUHCAUICQQEFRIKIhUeYyoPDBcGBRgiKw4LBAFCOgoJMA0MDA9tChMDAy0MIyMSBg4ody0NBAocFyISHxIGBQ4Y"
    "ImgkCy8YChIemA0KAwkJEhkSCRAMDQgNFBQQBQUHASwCAgYJCBAPDwIGCQECAwIDEgYJCQoFAQICAhoHBiADCAcECxQbFgsKDREJ"
    "BQYJDggDBQUEChAMEBwKDx8JAgICDwYDBggFBAgICwwNFBAGBgQcBwqdAgEICAkHBgYOGAoNFRUGAgIBGQsGCA8MBgfNBQENDRJQ"
    "AQkONQYJCwwB+QwPEAIOBx4OCQ8IDRQDBAUBGw8bHCldHQoGBg0WCxoEAQULDgwkFwsIBwdtCAQGHAICQBI0EQcUPn4fCQYHChMP"
    "DRUHAgkZERVeKQ4+AwIdBwwhOgAFACn/rgO+AxoANgCHANAA4AEUAAABNjYyFhYVFAYHBgcGFRQWFxYXFhYyFjMyFgcGBgcGBwYG"
    "JycmJicmJyYmJyYmNTQ3NxcWFjI3JTY2MhcWFgcGBwYVFBcWFRQWNzYXFhQGBwYGFQYHBgYXFjI2Njc2FxYGBwYGBwYGJyY1NCY2"
    "NDY3NjYmIyIGBwYnJjc2Njc3NTY2IyImJyY2ATYWFxYXFgYHBgYjIicmBgcGIgYHBgYXFDY2NzYVFAYHBhQGBwYUBicmJicmJjU0"
    "NzYTNjYzMhYXFzc2PwI2JgYHBiY3Njc2FzYmIwYHBg8CBhY2NzY2ATY2FxYWBwYGBwYzNjc2NzIWFxYVFAYHBgcGJycHBgcGBwYH"
    "BgYjIjY2NzY0NjY3Njc2NwKeGBYEIAYHCxMPKisVODYaBg0zBAkLAQEYGxoaFAsMGwgmBQIQHHggDQgJChMSLggL/nQtJAYLCgsF"
    "ByocAwgEDxwKCA0ZDwsBBQQCAwEECgwJIwUNEhMFCxQjEhMZEwkWAgEDAQIHIAILHR8EAzUfHwEHBggVAwgSAYUYRgwNBAMWCgcb"
    "DAcLCRMkIg8GBQMHAw0TDCkrCQMlDg0TBggGBgMRFA8KBBUMBRMEBR4gGRgCAwRCFBgYBAIXHEMHBQMXFRAWEwMCBjMVEAb+hxUX"
    "IBMEDAsOBwgIBxgaGBIJBgkPFB8kGBsMDA0JFEQMBQQtAwULGQ4PGQYJIRQLBAFLGiQZCBINDAwSCRgGAyUPJRQKBhsSCwwOAwIM"
    "CQEEDQQYAwQME30qEBENFQgKCgkvDrsWBwsKJggNBgQIAwQIFRMEBAkYDyMECQUHBgsWGTEGAQkMCiQCA1kbBR4pRRYKDB0MFAsZ"
    "IQ0KRD0TBxIMDR0NJBAQFhYjDQoRFQENBgIIBwoQ1i0dKw8OAxESCxYXzQMBChIOKwYOaAQCDEAQEQkHBAMSBgYrBwkmHAFFVXMY"
    "CwwQDgQEJSQFCg4ODBkPDhDnGAwECwgCAiAfCRwFBQkBAy4SGA0TERAfCgkCCQsCBQoPFBMRBAQPChsKDhARLUgLCQUhHy8VGQUe"
    "Dg43MR0KAAEAQ/+zA6EDEgCSAAABNhYXFhYHBgcGMzI3NjY3NhcWFxYHBgcGIyIGBwYGFjc2NzY3NjY3NxceAwcGBicmBwcGBhUU"
    "FhcWFxYyFhcWFhcWBw4CJyYGBwYnJiYnLgMnJiciBwYHBwYWMzI3Njc2FhUUBgcGFCMiBgcGBiMiJjU0NzY3NhInJgYHBhUUBiMi"
    "JyY3NjY/Az4CATsKFxUSBgUEAwIDAgILhQUNHxkICyYTHT0IBRQLBwMHCA4kQgMDHR4dEBEeBAoEAwcMOTdGHS6UHFgIBgkZFypS"
    "CxIEAkMVAwIdCR01GwUXFWBABRtCCAIDAgIEAQEFCA0vGwgEEQwKBAU2DA8WEBocBAkQCQ4GCFoTDBMLDxQfCwNOGkQoBAMDAQMG"
    "DAcXEhARDTQxAQaJCRwNChwiEgkbOhYEAwYEAQMDBQwGBQYEDQwQDxQMCAQCAwcIBBIHC4UNLAwGEggPKAwRFQgFDAIBDQYVIxEJ"
    "Dg9bTAQkUwEDBEqTMxcMKAYDBQwPJQsKC04VGhUrJx8JDisUASAFBSEOCQYHCRQiDwYnCRkNODeEEQAAAwCc/6cDTgMXACEAWgBz"
    "AAATNjMyFhUUFgcGBw4DFxYHBicmJjc0Jjc2NjU0NjU2NiU2FhcXFhYHBgYXFhYXFgcGFRQHBic0JicmJyYnJjc2FxY2NzY3NjQn"
    "JjQmJicmJgcGBwYnJiY0Nic2MzIWFxcWFgcGByImNCcuAjY0JicmNt8HAwYYDgYIBgIJBAQEBhkOGwoFAg0GCxENAQ0BPiiGFSEm"
    "LQcLBAUBAgQHLAQnMQEOAQEkIDYSBgkZMi8TEgUDBAUIAQUGLDVZHAsHBgotzQ0KCDMOFAwDCQ8YDDMUBggEAQEBAwYCSg4XBgUc"
    "CA5HHiqrQgoSMB0kDQ8XHxUHDmU2JzMbHlKYBwIFDAssEh5OtVyZDx9VBwcNEhUFBRQIEhEQMxICAQUNBRISCwufIiRzYFwLDQoB"
    "AhUIAgIZFBVDAxcLDwgzERsBNAkZBg0GAQMHBAwIAAYAQ/+wA5sDGAAZADIAWQB0AMkA4AAAJTY2FxYXFhcWFhcWFAcGBgcGIicm"
    "NTQmJyYBNhcWFgcOAhQHBgcGBiMiNzY3Njc2NzYlNhcWBwYHBhQGFRQGBwYHBgYjIjQ2NzY1NDc2NjU0NzY2Nz4CNCU2FxYVFBcW"
    "FgcGBiIUBwYGIyI3Njc2NjQ2NiU2MhcWFhUUBiMiJicmFRQXFgYHBhQWFhcWFgcGFgcGBhYPAgYmJyY3NicmJyYmBwYGBwYCFxYH"
    "BicmJjc3NjY3NjY3NicmBgcGJiY3NjY3Njc3NiU2FhUUBgcGBwYGJyY2Nz4CNDY0NjQCkwQtGBgRKTAYCQgGBggKFBELCw9PMCf+"
    "3w8bHQQaDQ1MISVYDjECDTYOD28jCAUlARskEQcDEBcGJiAHDC0eRgYCAwMHQBkxBgYbBwULDP6+GwgBEhgEDRAJCCoiZQwXGyAV"
    "BSQVDQINLx0LChQeFAxBMlwLDwUYH4AjGBkOBAMBBQMIBwMBFRYUEBMMBAICCgY/GhYrCAcMBwgiDwoNBQQIAggMCCISHwYDZwcJ"
    "JA8FBypDOyhMJf5PDDI3KiQCCEkEBwUKDSgLNRpeBgEEBQIEKBIBCwgLFh0OBgYGBwIIRiMdAT8WFxozIREaZgcjJkAJHUwSE4pM"
    "EghHNg5HGyJwLAkNOQEEHgQFHRQkCAsCBgMHRBs8BQMHBkEXFUlAFYIiCAECBRIZDxMVEwopIUgjKyIHMQYbHdYGBgYbCRAaFgQF"
    "CgQJDxIYHAQBDQcHGRoZBg4Ozw4kJRUWBR4jRBlilg0HBAUEFAkI/vsYHw0HBwgiPpY0Iw0KQRs2BgMXBggBEAsNDw4MAgYCJgc2"
    "FA88HRkDCyYDBRUKDTcHCkQHIwoAAAEAM/+0A7YDBAC4AAABNhcWNzYWFxYVFAYHBgcHBhUVFxYWFxYWMzI2NzY0Njc2NzYHBhYX"
    "FgcUBwYnJiYnJiY0JiYnJicmBwYVFAcGBgcGJycmNTQmIyIGBwcGBicmBgcGBwYGBwYmNzY2NDY3NzY3NjY0NzY2Jyc3NjYXHgIG"
    "Fg4CFRQGBwYWNjc2NjU0JjU0NzYWFxYyNjY3NjMyFhcXFgYHBwYGFxYVFBcXJyYmNzY3NicmJicmIgcHBgYiNTQ2NzYBlks6JQgM"
    "QwgGEQsWBgUFERAUER1nFAkdCg0LBQoFDAQCBwcFAhwdaRI0BwYdQwgIHQsHBQMGBQgIFhIbEgoEBSQVMyUTBggtCRAVCjINCAQD"
    "AwsbERsKCQgaCw4JAQEJBwUJCwkKBQ4FAQwQCAkEAhslP0siFRAUGQgEFAEBDwcpAQYDCAcOFAMQDBsLAgIJAgoNBAgDDhMdcBgm"
    "DQ4QBgsjAv8FEgwBAScNCwsMHwYOKzYgRkgwLigUI0khFBsJFRMnAQVGIEgIBSEzGRwdBRgHBhEIRRANKz4nAQEICRgPDAQKFB8T"
    "BQULMRItIQ0CAzQNGA0IEwMCBAcNBggbFSEMDQw/Cx4rZmuDCgcBBAcSDAk0GZkyEA9GFxUDAiIsVwYIVgYMAgEFDRASTxIeHAcg"
    "FgoPGSYhEg0FDREIFxZLIoBXGA8JCQYLBwsFEBAKCwsdAAABAJH/xwOQAscAdQAAATYXFBcWFRQGBw4CFzI2NzY2NzY2FxYWBw4E"
    "IhQXFhcWFhUUBhUUBgcGJicmJicmJiMiFxYWFxYXFhcWMzI2NzY1NBcWFxYXHgIXFgYHBgYjJiYnJiYnJiYnJicmJzQ2JyYGBwYi"
    "BiInJjU0Njc2NzYBrA4HGC0SBQUJAgUEBQ4YVQQDCREUCgMDEicaKAYtRxwIBAgVDw0NEw0OEhgxBQkKDRkbGRElUSobHxISBQgE"
    "AggDAwwGBgULFRInMi4oLTQmIxUuBAIRIwEKAwN9DwkJJAwTGT8YJGM2Ar4JBAQJDhYHJgQCXUwFGQgQYxQMAgoJFRgcCiILIwwO"
    "FxcHCxAYBQgJDQEDCBcSCwsNMScvLR8aEysjERY8GQoOCQUMLh8aDh0MChobGQsBDh8iIScZPwsHIkmBS1wGDBkPBysKEB4HLAkO"
    "Ew0AAAgALf+mA7sDHABFAFsA6wD6AQcBEwEnAWUAAAE+AzMyFhUUFBYWMzY3NhYXFhcWFhUUBwYGFxYGBwYHBgYHBgcGBicuAicm"
    "NTQ2FxY/AjY1NCYnJgYHBgcGBicmJhM2MhcWFxYWBwYGJyYmJyYmNzY2FxYlPgIWFxYWFRQHBgYHBgYHBjMyNzY3PgIXFgcGBgcG"
    "BgcGBgcGJyY3Njc2JicmJjU0PwI2JyYGBwYGBwYGBwYGBwYiJiYnJgcGIhUUBgcGJzQ3NjY3NjY3PgM3NjY3NxcWFhcWFhUUDwIG"
    "Bwc3Njc2Nic0NhcWFgcGFjM2Njc3NjYnJiYHBgYnJjYHJgYHBgYVFRcXNzY3NiYXNiYHBgYVFAcGFjc3JzYmIwYHBgYXFzMzFTYm"
    "IyIGIyIGBwYHBxcWMhY2NzYBNjYXFhYHBgcOAjMyNjYXFwcOAhUUBgYHBgYnJicmJjc2NzY3Njc3JyYHBicmBgcGBwYGIyI3Njc2"
    "NzYCVQQJAQwLEgwCAgMFHyNCTioTBgIEBQoCAhAHCQUHRA4RDgwWBAM2MRAfGwsmRiwTPQwUImwmBgkIFAgEAX8IBAoKCAQBBAcZ"
    "CwodBggDBQUaCQX+3Qw5BhgTDi8UBwQBAQcQEAgDCy45GjFGDBUNCCAnKnYWDBcPIyAdQQ8FAg4HBAsQEgQFAwM2CwsNDRQ+AgIN"
    "HAwIGzMGDwgFBkUJCQEEBgUJDSUKBwkMAgcEBgsQNSkSEA8HDAsDAwIDCScOBgcBHxEGBAIBAwcoDQEHAwEDBy0EBCgHDAaWCQML"
    "DggXFwICAgED+QEFFhYRBAYQGh//AQIEFgwGBAEBGBYCAQcICgUHJAECCAcQEBEOEwMCAc0IDAoWCBENAgEPDAEBJUgWFgIBCA4I"
    "BxQTERIRDgoEAQQeEgQPAgEODREbEQYIBw0JCjIDCx4XBC4NCAE1RFogHDNQGRwSBAEJCQUQChUIEyc3CAokAwUvCwwNEEIEBAoJ"
    "AwUFJDIIEAkGAQQQBwQUQmMdFgYLDRQCEBAECwYbAToGBwUSDAkJDA8BARACAhgLCg0DAnIJBwUEAwIfBw9AGi9ncUIeJAURCwUQ"
    "AQgQGhAKAQEXCwYGECgsKRUEAwIeBgQWBgkRECorAQILBQYQGCY9EQwQGwwjPAoWGQwDBUgFBgoFBwoLCg1OIRI9OoYtIBQNEgEB"
    "BAoKCg0SDAuQjxgYDjotE3Q5IhkUBg4VFggEBQkcEDsECgcIBRABAxwyCAECAhYqMwEBDQ4nGw+uIggHBQ8PDwsNBwICDxIOAwgF"
    "Cg4XaiUODBIEBRgXDg4LBwkJAioJAgUMLBQQAgEXFQ0BCQkVFAVIDhEHOyYhCRIPDAgHCRYNCAopQycCAQkMCQIEBw8MDTI9LwhU"
    "JBkAAAAAAAAHAFoAAwABBAkAAAC2AAAAAwABBAkAAQAaALYAAwABBAkAAgAOANAAAwABBAkAAwA8AN4AAwABBAkABAAqARoAAwAB"
    "BAkABQAaAUQAAwABBAkABgAmAV4AQwBvAHAAeQByAGkAZwBoAHQAIAAyADAAMQA4ACAAVABoAGUAIABNAGEAUwBoAGEAbgBaAGgA"
    "ZQBuAGcAIABQAHIAbwBqAGUAYwB0ACAAQQB1AHQAaABvAHIAcwAgACgAaAB0AHQAcABzADoALwAvAGcAaQB0AGgAdQBiAC4AYwBv"
    "AG0ALwBnAG8AbwBnAGwAZQBmAG8AbgB0AHMALwBtAGEAcwBoAGEAbgB6AGgAZQBuAGcAKQBNAGEAIABTAGgAYQBuACAAWgBoAGUA"
    "bgBnAFIAZQBnAHUAbABhAHIAMgAuADAAMAAzADsAWgBZAEUAQwA7AE0AYQBTAGgAYQBuAFoAaABlAG4AZwAtAFIAZQBnAHUAbABh"
    "AHIATQBhACAAUwBoAGEAbgAgAFoAaABlAG4AZwAgAFIAZQBnAHUAbABhAHIAVgBlAHIAcwBpAG8AbgAgADIALgAwADAAMwBNAGEA"
    "UwBoAGEAbgBaAGgAZQBuAGcALQBSAGUAZwB1AGwAYQByAAAAAwAAAAAAAP+cADIAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAH//wAP"
    "AAEAAAAKABwAHgABREZMVAAIAAQAAAAA//8AAAAAAAAAAQAAAAoAHAAeAAFERkxUAAgABAAAAAD//wAAAAAAAA=="
)


def _find_poem_font() -> Any:
    for rel in (CONFIG.get("POEM_FONT_PATH", "syrup_poem.ttf"),
                "assets/fonts/syrup_poem.ttf"):
        p = _resource_path(rel)
        if p.exists():
            try:
                return str(p), p.read_bytes()
            except Exception:
                return str(p), None
    try:
        return None, base64.b64decode(_POEM_FONT_B64)
    except Exception:
        return None, None


_UI_FONT_B64 = {
    "r": "AAEAAAAQAQAABAAAR1BPUyIXDC4AAYeYAAAPjEdTVUIfUxDxAAGXJAAAAy5PUy8y0BzmcgAAAYgAAABgY21hcJv0fQgAAAecAAANIGdhc3AAAAALAAGHkAAAAAhnbHlm57kj0wAAGUQAAWr2aGVhZCYjcKoAAAEMAAAANmhoZWEHpgNfAAABRAAAACRobXR4waZqCAAAAegAAAW0bG9jYcC8ZqYAABTEAAAEfm1heHADrgEQAAABaAAAACBuYW1lSNprGAABhDwAAAM0cG9zdP+4ADIAAYdwAAAAIHByZXBwAgQSAAAUvAAAAAh2aGVhBhYBvwABmlQAAAAkdm10eHMjccsAAZp4AAAEfgABAAAAAgAAXH3lB18PPPUACwPoAAAAANye6w4AAAAA5uVCMP+0/zQDywNSAAAACQACAAAAAAAAAAEAAAQk/qwAAAQ9/7T/2QPLAAEAAAAAAAAAAAAAAAAAAACcAAEAAAI+AIYACwAAAAAAAgAEACAAYABgAQAACAAAAAAABAPNAZAABQAEAooCWAAAAEsCigJYAAABXgAyAUQAAAACBgAEAQEBAQGAAAADCAFgIAAAABAAAAAASE5ZSQFAACD/HwNS/2oAyAQkAVQAAAABAAAAAAIcArYAAAAgAAECPwBQAQEAAAFpAHMBlQBNAlgAEgI/AD8DNQBEAoAAJwD9AE0BZwBBAWcAMgGuAB4CKAAjAS4AJgG4AEgBLgBXAfQATQI/ADUCPwBlAj8AOQI/AEYCPwAjAj8AVgI/ADkCPwA2Aj8AMgI/ADkBegB9AXoAQgIoACMCKAAjAigAIwGvACoDXAA4ApsACwJsAFwCVwBIArsAXAIsAFwCDwBcAq0ASALEAFwBEgBcAQ//tAJmAFwB+wBcAz4AXALhAFwC5wBIAlUAXALnAEgCZgBcAjYAOQIQABACvQBZAmkAEAOCABoCcAAXAlIABgJyADoBJgBGAf4AFwEmACICKAA+AfQAAAFaADgCZAA3AnsAWwHxADsCewA8AkIAOwFdABICfAA8AmoAWwEMAFMBDP+6AgYAWwEeAFsDmQBbAmoAWwJqADsCewBbAnwAPAF7AFsB3wA7AVEADwJlAFcCDgAKAzwAFgIEAA4CDwAKAfoALAErADEAtwAyASsAIgIoABwBZQBXAigAKgH7AFwBIwBbAlwAEgJuABICmwASA5sAEgOtABIC2AAIAQwAWwQ9AHMD2ADAA9gAuwPYAqED2ACMA9gCagPYAawD2AC7A9gCoQPYANID2ACWA9gAbgPYAg4D2ACMA9gCXgPYAlsD2ACxA9gCWwPYAMAD2AGQA9gAegPYADQD2AA0A9gBoQPYAC8D2AA0A9gANAPYAjkD2AC2A9gANAPYADQCrABGA9gByAPYAHUD2AJvA9gAZgPYAlgD2ADoA9gAUgPYAOcD2ABSA+gAigPoAIoD6AB9A+gAlgPoAJYD6ABuA+gAbgPYADAALwAmADcALwA4AC0AKwAqAC4AGwBzACwARAAwACUAPQAbACIAKQBHAEYAPgBAADAAHgA4AFoAFQAMABEAEAAlAA8AFwASABIAFQAUABcAGwAfABYAFgAnAC8AKwAhACQAOQAsAC0AfwApADgALwA3ACAAeAA3ACAAIgAjACkANgAmADEAFgAzABsAHgAVADYAOQAyADkAPAA7AEsAMwAgABQAHwCTAB0ASwBQABwAIABsABcAGABvABYAFQBfAFwAcgBqAHIAcQBmAGkAEgAfACUAKAATACUANgAhACAAJQA1ACsALwA5ADEANwAXAGgAHwA9ACgAPwAoACQAHwAcABgATgAoAB4AHgAeACcAEwBxAFQAUAAqADQAHAAuADIAdgAgAE8AQABRACwAHQAXABcAEwAPACsAKQAjABwAGwAYACwAIAAZADYANwBXACIAOAAkAB8AHQAhACAAEgAfACYAFgAXAB0AOwAeABoAGQAVABgAIQAaAA4AFgAVAB8AMAAqABYAJAAlABcALgAoALoAZgBnACYANQAyACkAPQAZACYAIgAWABYAHgAUAB4AJQAgAAwADwARACUAJQAUAA8AHQAQAAwAHQANAAsAPgAYACsAIQAjACoAIwAbAB0AMwAqACwANAApACkALgAmAB0AGwAgACEAJwApACsAMQAnACgAIwAmACkANQAVACgAHwAVABQAFwA3ACAAJAAbADUAJwCBABgAXQAvAJIAMgBjAKYALgAVABgAYgBSAB8ACAAUAA4AJAA4ABYAFQBDACIAMQA9ADEAIgAZACcAFAAmACMAKAAiACIAKgAhACgAJAApACEAJwAuAB8AIABDAA8ARACdAC8AKgAvADwAIgAoACkAKAAlABUAGAAOACUAFwAhACgAFgAcADEAKwAvAC8ALQAdABwALQAoACoALQAxABEAJAAmABIAFwAXAB8AHQAbAB8AHwAkACsAJAAoACIAJgAiAA8AGgAfABwAHgAiABYAKgAXACsALQAbAAwAFwANABQAEAA5AG0AbgBsAGEAZABeAGQAYwBdAFQAFAAGABQAIQAxADcAOAAhAB4ALAAbACMAUwAZADcAFAAZAD4AZAAAAAIAAAADAAAAFAADAAEAAAAUAAQNDAAAAzgCAAAIATgAfgC3ANcgFCAmIZMloSXGJcslzyYGMAIwDTARTgBOA04HTgtODk4UTiROKk4tTjhOO05FTkhOS05dTmBOjE6OTpFOlE6nTrpO5U7sTvBO9k77TxpPTU9PT1NPXE9/T79P3VANUE9QWlBcUUlRTVFlUWhRa1FtUXNRdlGFUY1Rs1HGUc9R+1IHUhlSIFIkUjBSNlI6Uk1SaVKgUqhTQVNDU0dTVVNhU3NTu1PNU9FT1lPjU+VT8FPzVARUDlQRVC9UfVUvVbdW21beVuBW9Fb6VwZXKFcwVzpXR1f6WJ5YqFkEWQ1ZFlknWSlZLlkxWctbWFuDW4xbmlueW7Zb+VwEXAZcD1wdXDpcPlxAXE9d5l3yXgZeJ152XpRepl8AXw9fFV8xXzpfU19iX3FfhF+XX6pfrl/DX8VgAWAOYDtgYmEPYhFiFmIYYkBiS2JTYn5i1mLlYuljAmMHYwljYmNuY4xjpWOoY9Bj4WRHZKRkzWU7ZT5lSGVMZWNlcGV0ZYdlsGW5ZeBl5WX2Zg5mL2Y+ZoJnAGcJZx9nKmcsZzpnQGdQZ19nYWdlZ39ngWeaZ5xn02flaAdoOGg8aGNqIWo9ayJrZGuLa7Vrz2wUbDRsOGynbLNsuWy/bNVs4m07bUFtRm1ObWptbm13bYhtsm4FbjJuOG7abuFvFHCucLlyBnJ5cuxzDnOHc6lzsHUfdSh1MXVMdVl1kXZ+doR27nb0dvh3C3eEd6x37Xg0eEB4bnk6ebt50nn7enp6f3qXest7EXsse358e3zWfS9+p36/fsR+yH7PftN+537tfxh/KX9uf46ABYAMgBeA/YHqgfOCcoLxgwODq4O3g9yEPYRXiEyIaIiricKJxInSieOJ5ouhi6SLrYuwi76L1YvXi+WL9Iv3jAONH40ljSiNNI13jd2N746rj2+PfY+5j8eP0Y/Uj9iP24/ej/CP/ZAAkAmQEJAUkB+Qf5DokP2RzZHPkdGU9pT6lP6VAZUulX+V6JXtlfSWRJZNllCWZJZ3lo+WlJa+lsWW9pcHl1KXXpdimHmYe5iEmJyYzpjemYia2J5Pns+e0Z8g/wH/A/8G/wn/DP8b/x///wAAACAAtwDXIBQgJiGQJaAlxiXLJc8mBTABMAowEE4ATgNOB04JTg1OFE4kTipOLU44TjpORU5ITktOXU5fToxOjk6RTpROp066TuVO7E7wTvZO+08aT01PT09TT1xPf0+/T91QDVBPUFpQXFFJUU1RZVFoUWtRbVFzUXZRhVGNUbJRxlHPUfpSBlIZUiBSJFIwUjZSOlJNUmlSn1KoU0FTQ1NHU1VTYVNzU7tTzVPRU9ZT41PlU+9T81QEVAxUEVQvVH1VL1W3VttW3lbgVvRW+lcGVyhXMFc6V0dX+lieWKhZBFkNWRZZJ1kpWS5ZMVnLW1dbg1uLW5pbnlu2W/lcBFwGXA9cHVw6XD1cQFxPXeZd8l4GXidedl6UXqZfAF8PXxVfMV85X1NfYl9xX4Rfl1+qX65fw1/FYAFgDmA7YGJhD2IPYhZiGGJAYktiU2J+YtZi5WLpYwFjB2MJY2JjbmOMY6Vjp2PQY+FkR2SkZM1lO2U+ZUhlTGVjZXBldGWHZbBluWXgZeVl9mYOZi9mPmaCZwBnCGcfZypnLGc6Z0BnUGdfZ2FnZWd/Z4FnmmecZ9Nn5WgHaDdoPGhjaiFqPWsha2Rri2u1a89sFGw0bDhsp2yzbLlsv2zVbOFtO21BbUZtTm1qbW5td22IbbJuBW4ybjhu2m7hbxRwrnC5cgZyeXLscw5zh3Opc691H3UodTF1THVZdZF2fXaEdu529Hb4dwt3hHesd+14NHhAeG55Onm7edJ5+3p6en96l3rLexF7LHt+fHt81n0vfqd+v37Dfsh+z37Tfud+7X8Yfyl/bn+OgAWADIAXgP2B6oHzgnKC8YMDg6uDt4PchD2EV4hMiGiIq4nBicSJ0onjieaLoYuki62LsIu+i9WL14vli/SL94wDjR+NJY0ojTSNd43dje+Oq49uj32PuY/Hj9GP1I/Yj9uP3o/wj/2QAJAJkBCQFJAfkH+Q6JD9kc2Rz5HRlPaU+pT+lQGVLpV/leiV7ZX0lkSWTZZQlmSWd5aPlpSWvpbFlvaXB5dSl16XYph5mHuYhJic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AAAAAAAA//YAAAAAAAAAAP/XAAAAAP+c/+z/sP/2/7r/2f+v/+z/9v/s/+wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/7AAAAAD/3AAA/+L/7f/YAAAAAAAAAAD/xf/s/+z/2QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAATAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/Yf/YAAD/xQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//UAAP/rAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+z/7f/Z/9n/2f/YAAD/2f/2/8QAAP/tAAAAAAAAAAAAAP/Z/9n/7f/Y/9gAAAAAAAAAAAAAAAAAAAAAAAAAAP+d/8X/sf/t/7H/2f+cAAAAAAAA/9cAAAAUAAAAAAAAAAAAAAAAAAAAAAAA/+v+/wAAAAAAAAAAAAAAAAAAAAD/4wAA//H/2P/2/+v/9v/XAAAAAP/s//YAAAAAAAAAAAAAAAAAAP/s/+wAAP/2AAAAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAD//wAA/+v/9v/rAAAAAP///+z/7AAAAAAAAAAAAAAAAAAAAAAAAAAA//YAAP////8AAAAAAAAAAAAAAAAAAAAC/+wAAAAAAAAAAAAAAAAAAAAU/9n/Zv+wAAD/sP/tAAAAAP/F/8X/xP+x/+0AAP/Z////7P/F/8b/xQAAAAD/7QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/2AAAAAAAAAAAAAAAAAAAAAAAAAAAAAP//AAAAAAAAAAAAAAAAAAAAAAAA/+0AAAAAAAAAAAAAAAAAAAAAAAD/sf/YAAD/2AAAAAAAAP/s/+z/7AAAAAAAAAAAAAAAAAAAAAAAAP/ZAAAAAAAB/9gAAAAAAAAAAAAA//8AAP///9j/c/+vAAD/mwAAAAEAAP/E/8T/w//YAAAAAP/X////7f/X/9j/1//EAAAAAAAA/+wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIABQAiACgAAAArAC0ABwAwADsACgBiAGIAFgBpAGkAFwACABcAIgAiAAMAJAAkAAQAJQAlAAUAJgAmAAYAJwAnAAcAKAAoAAgAKwArAAkALAAsAAoALQAtAAsAMAAwAAUAMQAxAAEAMgAyAAUAMwAzAAwANAA0AA0ANQA1AA4ANgA2AA8ANwA3AAIAOAA4ABAAOQA5AAoAOgA6ABEAOwA7ABIAYgBiAAsAaQBpAAMAAQADAGkAAgAAAAAAAAAAAAIAAAAAAAAAAAANAAAADQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAgAAAAAAAAAAAAAAAOAAAAAwAAAAAAAAADAAAAAAATAAAAAAAAAAAAAwAAAAMAAAAbAAQABQAGAAcAAQAIAA8AAAAAAAAAAAAAAAAAEAAAABQAFAAUAAkAFQASABwAEQASAAoAHQAdABQAHgAUAB0AFgALABcADAAYABoADAAfAAAAAAAAAAAAGQAAAAAACgAJAAkACQAJAAkADgASAA0AAgRyAAQAAASOBOAAEQAhAAAAAAAAAAAAAP/E/+v/w//2//YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/2f/sAAAAAP/F/+v/xP/2AAD/2P/sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/FAAD/2AAAAAD/7AAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFQAAABUAKAAoABUAAQAAAAD//wAV/+0AAwABAD3/4//tAAH/2f/t/+3/7f/tAAEAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/GAAD/2f/2AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACkAA//sAAAAAAAAAAAAAAAAAAAAAgACAAAAAAAAAAAAAAAAAAAAAAAAAAAAFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/ZAAAAAAAAAAAAAP/sAAAAAAAAAAD/7P/sAAD/7AAAAAD/7AAAAAAAAP////YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/t//YAAAAAAAAAAAAAAAAAAAAA/+wAAAAAAAAAAAAAAAAAAAAAAAD/dQAAAAAAAAAAAAAAAAAAAAAAAP/tAAD/7QAAAAAAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/pgAAAAAAAgAAAAD/z//tAAEAAAAAAAAAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAD/7f/2AAAAAP/F/+v/xP/tAAAAAP/sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/YAAD/7QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/2QAAAAAAAP/ZAAAAAAAAAAD/pgAAAAAAAAAAAAD/3f/2AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/2QAAAAAAAP/tAAAAAAAAAAD/zgAAAAAAAAAAAAD/4gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIABABCAEMAAABGAEcAAgBJAFsABABkAGgAFwABAEMAJgABAAAAAAACAAMAAAAEAAUABgAHAAgABAAEAAEAAQAJAAoACwAMAA0ADgAPAAcADgAQAAAAAAAAAAAAAAAA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ATAArgLTAPEAeACcAJ4AnACSAJQAlgEwAK4AUABQAFABuABQAFACQwEaAkMBKQFdAO0AUABQAiMBIgH9AAAC0wD9AsUA9ABMAO4ATADuAIoAigB9AJYAlgBnAGcBpQA0AG8AiQAvAHYAcQA4AF0AXgAyACcAMAAyACwAJQA5AC4ALwAtAHgApgBwAHQAdQAoADoAQgAqADQAKwA5ADAALAAqADIAMAAyADMAPAAqACIAKQAjADQAKABKADYAPQApACgAMgAyAGsALgAsACQAJwAtACgAKgAvADkAPQA0AD8AMwAzABgAQgAvACwALwAvAFEANAAgAC8AXwAoAFQALABdAI8AKQBtAB8ALAAlAGkAJABJABoAIQArACgALgCDAGIAXwBeAGIAVwAgADIAKwApADkAIwBbADcAKwAwADMAeQA9ADAAJwArACsANAAmACgAIwAlACAAMgAsACAAPAAvAGIAXgBhAF4AYgAwAG8ALwAoACUAGwAoAHMALwA4AGIAJwBlADEAOAA8ADEAMgApADAAMAAsAC4AJgAlACoAJAAxACYAMAArADAASwBWAC8AMQAkADQANQAqADIAMwArAC8ANgAlAC4ALQAmADcAOQA1AC0ANwApACsALwAvACgAMgAhACgAJgAlAG0AdQAwAGcAXABcACMAUQBdACoANwArADIALwAyAC8ALgAuACkAMQA0ACkAZQAzAC4AOgAuACkAIgAxAC4AEQAvACgALwAuAEEAIAAmADAAIAA8AEcALQBNADEAJgAuAEQAJAAhAB0AIgBBACMAKgAwADMALAAsACQALgAnACYAMwA1ADEAKQA3ACoAdwB5AGMALwBnAC0AVwA5ACwAIwBlACMAaAA/ADUARAAwAEgALAAwAC0AIgBuABYAKwAmACQALQAtACQAIgAkADkANAAsAFcALgA1ACkAPgAoADkAMAA3ACoALQApAGYAFQAuAGcANQAnACAAdgAkADkALAAsACsALQAuACwAMQAzADEAYgBjADUAHwAoACQAMQAyADsAQAA+ACkAMQArADEAMgA9ACIAMgBGADEAMwBeAB0AJQAhACkAIgAxADIARwBGAD8AOgAmADIAKQBHAC8APwA4ADAANAArADIARABQADEAKgAkACoAKQAsADUALwApAC8AMQAfAF0APAAkAC4AYwAnACwATgBXADEANABeAGoAPQBeACEAXgBwADMAJgAfAC4AVAAyAAA=",
    "s": "AAEAAAAQAQAABAAAR1BPUyPaDhwAAYPUAAAPjEdTVUIfUxDxAAGTYAAAAy5PUy8y0OTmMgAAAYgAAABgY21hcJv0fQgAAAecAAANIGdhc3AAAAALAAGDzAAAAAhnbHlmgrm43wAAGUQAAWcoaGVhZCY9cHUAAAEMAAAANmhoZWEHwAN5AAABRAAAACRobXR4yIZmcgAAAegAAAW0bG9jYUsI8hoAABTEAAAEfm1heHADrgEMAAABaAAAACBuYW1lScRr3wABgGwAAANAcG9zdP+4ADIAAYOsAAAAIHByZXBwAgQSAAAUvAAAAAh2aGVhBjEBrwABlpAAAAAkdm10eGx7bWAAAZa0AAAEfgABAAAAAgAACevNp18PPPUACwPoAAAAANye6vMAAAAA5uVCMf+s/yQD7QNHAAAACQACAAAAAAAAAAEAAAQk/qwAAARU/6z/3APtAAEAAAAAAAAAAAAAAAAAAACcAAEAAAI+AIIACwAAAAAAAgAEACAAYABgAQAACAAAAAAABAPNAlgABQAEAooCWAAAAEsCigJYAAABXgAyAUQAAAACBgAEAQEBAQGAAAADCAFgIAAAABAAAAAASE5ZSQEAACD/HwNS/2oAyAQkAVQAAAABAAAAAAIcArYAAAAgAAECPwBQAQEAAAFvAGoBnAA3AlgADwJJADgDPABAAoAAHADtADcBfwA8AX8AJAHDAB4COgAfAUAAIAG4AEQBQABQAfQAQwJJAC4CSQBhAkkANQJJAEQCSQAdAkkAUgJJADICSQA2AkkALAJJADEBiwB2AYsANwI6AB8COgAfAjoAHwG7ACcDWAAqAsEABgJ+AFICWgA/AsQAUgIwAFICFwBSArIAPwLUAFIBJwBSAST/rAKDAFICCQBSA2AAUgLvAFIC6gA/Am0AUgLqAD8CfgBSAj4ANwIfABIC0ABPAp8ADgOkABUCmQASAoAABAKBADYBPgBGAfsAEQE+ABoCOgA8AfQAAAGUADwCaAAuAn8ATwHyADICfwAyAkcAMgFjAA8CgQAyAnYATwEYAEUBGP/FAigATwEqAE4DqABPAnYATwJrADICfwBPAoAAMgGKAE8B5gA1AV8ADQJxAEsCMQAGA1sAEgI3AAoCMgAGAhYAMAFMACYA0gAyAUwAGgI6ABwBbwBQAjoAIwIJAFIBXwBOAnQADwKFAA8CpwAPA7gADwPJAA8DBgADARsATwRUAGgD2AC+A9gAyAPYAqID2ACTA9gCggPYAZwD2ACgA9gCoAPYANAD2ACOA9gAZAPYAikD2ACTA9gCXQPYAlYD2ACYA9gCYgPYAJgD2AF5A9gAZgPYADQD2AA0A9gBlQPYADED2AA0A9gANAPYAiED2ACiA9gANAPYADQCpQBCA9gBvQPYAGYD2AJCA9gAYQPYAl0D2ADSA9gARQPYANID2ABFA+gAigPoAIoD6AB9A+gAlgPoAJYD6ABuA+gAbgPYADAAMAAqADoANAA9ADEALwAtADEAGwBqACUAMgA0ACUALQAfACMALABDADQAMwA9ADMAGQAyAE8AFQAUABcAGAAoAAoAEAAQABQADgAKABIADwAQABUAEQAbACwAHgAdABoANQAsADEAcgAoACgAHQAxABMAbwA7AB4AIwAXABYAPwArADEAGAAsABgAIAANADQAOQAwADoAPwA1ADgANQAdABAALwCHABkAMwBHABoAIABfACAAEgBhAA0AHQBVAFAAZgBcAGUAZQBcAGAAHgAkACIALQAhADQAPgAiAB8AHQAuACwALQA2ACkANQAdAF0AHgA7ACEAQwAmABsAJwAcACMASgAiAB4AGgAXAB4AFABxAEoARgArACQAFwAtAC4AbgA2AEsAPwBWACsAGwAZABQAHAAbABwAHwAfAB8AGgAcACkAHAAQADMAMQBRABgANQAlACIAJQAiACQAHAAkACMAIQAfACQASQAlACEAIQAgAB8AHgAkABsAIwASAB0ALgAzACAAJAAnABkAJAArAKgAWwBjACYANwA4AC4ALAAcACYAIgAXABgAIAAVACYAKwAmABUADQAOAC0AKgAeAA4AFQAPAAsAFQAMAA4ANwAZACkAKAApACwAHgAYABwANAApACcALQAmACgAKwAjABsAIAAfACEAIgAlACsALAAjACUAIwAkACsALAAcAC8AHAAfAB0AIgA3ACkAKQAkADkAHwB4ACIAXAAzAIUAQABZAJ4AMgAYABsAWABGABkAGQAXABMAKgBGABoAFgA8ACwARQA6AC8ALQAsACwAFAAuACYAJwAnACQAKAAkACoAJgAoACAAJQA2ACoAHABBAAwARACWADQAJQAxAEAALgAqACcAKwAyAB4AIgAdACwAGQAgACcAFwAdADoAPgA3AEAALgAvAC0AOgA7ADsAOQAzAB8AIQAiABcAJAAfACwALAAsADQAKgAeACoAKAAoACIAKAAiABEAHwAeACEAJAAjAB0AMAAYADIAMgApABoAGQAZABgAEABAAGMAYwBhAF8AVgBaAF0AYwBYAE0AHAAPACQAIAA0AC0APAAlAB4AKwARACIASwAZADgAGAAdADcAXwAAAAIAAAADAAAAFAADAAEAAAAUAAQNDAAAAzgCAAAIATgAfgC3ANcgFCAmIZMloSXGJcslzyYGMAIwDTARTgBOA04HTgtODk4UTiROKk4tTjhOO05FTkhOS05dTmBOjE6OTpFOlE6nTrpO5U7sTvBO9k77TxpPTU9PT1NPXE9/T79P3VANUE9QWlBcUUlRTVFlUWhRa1FtUXNRdlGFUY1Rs1HGUc9R+1IHUhlSIFIkUjBSNlI6Uk1SaVKgUqhTQVNDU0dTVVNhU3NTu1PNU9FT1lPjU+VT8FPzVARUDlQRVC9UfVUvVbdW21beVuBW9Fb6VwZXKFcwVzpXR1f6WJ5YqFkEWQ1ZFlknWSlZLlkxWctbWFuDW4xbmlueW7Zb+VwEXAZcD1wdXDpcPlxAXE9d5l3yXgZeJ152XpRepl8AXw9fFV8xXzpfU19iX3FfhF+XX6pfrl/DX8VgAWAOYDtgYmEPYhFiFmIYYkBiS2JTYn5i1mLlYuljAmMHYwljYmNuY4xjpWOoY9Bj4WRHZKRkzWU7ZT5lSGVMZWNlcGV0ZYdlsGW5ZeBl5WX2Zg5mL2Y+ZoJnAGcJZx9nKmcsZzpnQGdQZ19nYWdlZ39ngWeaZ5xn02flaAdoOGg8aGNqIWo9ayJrZGuLa7Vrz2wUbDRsOGynbLNsuWy/bNVs4m07bUFtRm1ObWptbm13bYhtsm4FbjJuOG7abuFvFHCucLlyBnJ5cuxzDnOHc6lzsHUfdSh1MXVMdVl1kXZ+doR27nb0dvh3C3eEd6x37Xg0eEB4bnk6ebt50nn7enp6f3qXest7EXsse358e3zWfS9+p36/fsR+yH7PftN+537tfxh/KX9uf46ABYAMgBeA/YHqgfOCcoLxgwODq4O3g9yEPYRXiEyIaIiricKJxInSieOJ5ouhi6SLrYuwi76L1YvXi+WL9Iv3jAONH40ljSiNNI13jd2N746rj2+PfY+5j8eP0Y/Uj9iP24/ej/CP/ZAAkAmQEJAUkB+Qf5DokP2RzZHPkdGU9pT6lP6VAZUulX+V6JXtlfSWRJZNllCWZJZ3lo+WlJa+lsWW9pcHl1KXXpdimHmYe5iEmJyYzpjemYia2J5Pns+e0Z8g/wH/A/8G/wn/DP8b/x///wAAACAAtwDXIBQgJiGQJaAlxiXLJc8mBTABMAowEE4ATgNOB04JTg1OFE4kTipOLU44TjpORU5ITktOXU5fToxOjk6RTpROp066TuVO7E7wTvZO+08aT01PT09TT1xPf0+/T91QDVBPUFpQXFFJUU1RZVFoUWtRbVFzUXZRhVGNUbJRxlHPUfpSBlIZUiBSJFIwUjZSOlJNUmlSn1KoU0FTQ1NHU1VTYVNzU7tTzVPRU9ZT41PlU+9T81QEVAxUEVQvVH1VL1W3VttW3lbgVvRW+lcGVyhXMFc6V0dX+lieWKhZBFkNWRZZJ1kpWS5ZMVnLW1dbg1uLW5pbnlu2W/lcBFwGXA9cHVw6XD1cQFxPXeZd8l4GXidedl6UXqZfAF8PXxVfMV85X1NfYl9xX4Rfl1+qX65fw1/FYAFgDmA7YGJhD2IPYhZiGGJAYktiU2J+YtZi5WLpYwFjB2MJY2JjbmOMY6Vjp2PQY+FkR2SkZM1lO2U+ZUhlTGVjZXBldGWHZbBluWXgZeVl9mYOZi9mPmaCZwBnCGcfZypnLGc6Z0BnUGdfZ2FnZWd/Z4FnmmecZ9Nn5WgHaDdoPGhjaiFqPWsha2Rri2u1a89sFGw0bDhsp2yzbLlsv2zVbOFtO21BbUZtTm1qbW5td22IbbJuBW4ybjhu2m7hbxRwrnC5cgZyeXLscw5zh3Opc691H3UodTF1THVZdZF2fXaEdu529Hb4dwt3hHesd+14NHhAeG55Onm7edJ5+3p6en96l3rLexF7LHt+fHt81n0vfqd+v37Dfsh+z37Tfud+7X8Yfyl/bn+OgAWADIAXgP2B6oHzgnKC8YMDg6uDt4PchD2EV4hMiGiIq4nBicSJ0onjieaLoYuki62LsIu+i9WL14vli/SL94wDjR+NJY0ojTSNd43dje+Oq49uj32PuY/Hj9GP1I/Yj9uP3o/wj/2QAJAJkBCQFJAfkH+Q6JD9kc2Rz5HRlPaU+pT+lQGVLpV/leiV7ZX0lkSWTZZQlmSWd5aPlpSWvpbFlvaXB5dSl16XYph5mHuYhJic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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/oAAAAAP/cAAD/4v/0/9gAAAAAAAAAAP/M/+z/7P/oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP9w/9gAAP/MAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/7gAA/+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/6P/0/+D/6P/o/9gAAP/g//L/xAAA//QAAAAAAAAAAAAA/+D/4P/0/9z/2AAAAAAAAAAAAAAAAAAAAAAAAAAA/6T/1P/A//T/uP/g/5wAAAAAAAD/0AAAABQAAAAAAAAAAAAAAAAAAAAAAAD/5P8cAAAAAAAAAAAAAAAAAAAAAP/sAAD/8//Y//b/5v/y/9AAAAAA/+z/9gAAAAAAAAAAAAAAAAAA/+z/7AAA//oAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAP/wAAD/5P/y/+QAAAAA//j/7P/sAAAAAAAAAAAAAAAAAAAAAAAAAAD/9gAA//j/+AAAAAAAAAAAAAAAAAAAABj/7AAAAAAAAAAAAAAAAAAAABT/6P9t/7AAAP+w//QAAAAA/8z/zP/E/8D/9AAA/+j/+P/s/8z/3P/MAAAAAP/0AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//oAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//gAAAAAAAAAAAAAAAAAAAAAAAD/9AAAAAAAAAAAAAAAAAAAAAAAAP+4/9oAAP/YAAAAAAAA/+z/7P/sAAAAAAAAAAAAAAAAAAAAAAAA/+gAAAAAABD/2AAAAAAAAAAAAAD/8AAA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AKsCxQCuADEA0gAxANIAigCKAH0AlgCWAGcAZwGaADIAXgB/ACwAZwBsADgATQBPAB8AKwAuACsAKgAgAC0AOAAtAC4AagCVAGAAcABvACMAOAAwACEAIQAqACwAIQAoADAALQAnAC0AMQAyAC0AKwAnACsAMAAiADgALwA5AD0AGgAwADAAXwArACsAIgApACkAJwAhAC0ARQA7ADIAOwAzAC8AEQBAACwAKwAsAC0AQQAyABYALQBWACcAQgApAFMAgwAkAGYAGwAqAB0AWwAeAEAAIQAjAB4AKgAsAHQAUQBRAFQAUwBLAB0AMAAqACUANwAeAFMAMQAhACsALgBpADIALgAhACUAJQA1ACwALgAjACsAKAA0ADAAHwBBADMAWwBVAFgAWgBaADUAYwAyAC4AHAAmAC0AaQAtAD4AWgAeAF0AMwA2ADwALgAtACkANQAtACYALwApAB8ALQAqADUAHwA0ACQAMQA7AEMALAAuAB8ANAA2ACsALgAzACsAKgA0ACoALQAvACkANQA3ADgALAAzACIAKQAuACYAJgAtAB8AJwAlACgAZQBpAC4AWwBSAFIAJgBIAFYAIAA6ACoALgAuACIALAAsACYAKAAtAC0AJgBaADEAKwA4AB0AMgAaAC0ALAALACkAJQAsACsANQAZAB8ALgAVACkANgAtADcALQAgACsARAAmABgAIQAgADQAGwAqAC0AMQAsACsAIwArAC8AKAAxADMALwAlADUAKgBqAGsAVgAtAF4ALQBNAC8ALAAcAFsAIQBbACwALgA7ADAAPQAmAC8AKwAeAGEAKAArACkAMQAvACwAMAAfAB4ANwAzACgATAApAC8AKAAqACwAMAAtADMAKwApACsAYwAQAC4AWwAxACAAHgBmABcAOQAoACsAKgApACwALAAxAC8ALQBXAFgAMQAZACMAHgAtADAANwA6ADgAKAAvAC4AIwAwADEAGgAtADwALwAxAFQAGQAhAB4AJgAiAC0ALgA7ADoANwA4ACMALwAoADUALAA2ACoAMQAxACgALgA8AE8AKwAoACEAIQAkACMAMQAgABwAIgAqABYAUwArACEAKABZACMAKwBJAFUAMAAyAFEAXgA1AFcAJwBWAGQAKwApAB0AMABSACYAAA==",
    "h": "AAEAAAAQAQAABAAAR1BPUyS8DxkAAXzkAAAPjEdTVUIgCxFjAAGMcAAAAzZPUy8y0azmUgAAAYgAAABgY21hcJv0fQgAAAecAAANIGdhc3AAAAALAAF83AAAAAhnbHlmHTYjnQAAGUQAAWAqaGVhZCZLcCoAAAEMAAAANmhoZWEHzQOGAAABRAAAACRobXR4ynZiUQAAAegAAAW0bG9jYdSHfSIAABTEAAAEfm1heHADrQELAAABaAAAACBuYW1lSwNtPgABeXAAAANKcG9zdP+4ADIAAXy8AAAAIHByZXBwAgQSAAAUvAAAAAh2aGVhBhsBugABj6gAAAAkdm10eHDzcRgAAY/MAAAEfgABAAAAAgAArdwU8V8PPPUACwPoAAAAANye6pIAAAAA5uVCMf+o/y8D/gNSAAEACQACAAAAAAAAAAEAAAQk/qwAAARg/6j/3QP+AAEAAAAAAAAAAAAAAAAAAACcAAEAAAI+AIEACgAAAAAAAgAEACAAYABgAQAACAAAAAAABAPNAyAABQAEAooCWAAAAEsCigJYAAABXgAyAUQAAAACBgAEAQEBAQGAAAADCAFgIAAAABAAAAAASE5ZSQEgACD/HwNS/2oAyAQkAVQAAAABAAAAAAIcArYAAAAgAAECPwBQAQEAAAF0AGUBoAAsAlgADgJOADUDQAA+AoAAFwDlACwBjAA5AYwAHAHOAB4CQwAdAUkAHQG4AEIBSQBNAfUAPgJOACoCTgBgAk4AMwJOAEQCTgAaAk4ATwJOAC4CTgA3Ak4AKQJOAC0BlAByAZQAMgJDAB0CQwAdAkMAHQHBACYDVgAjAtUAAwKIAE0CWwA6AskATQIyAE0CGwBNArUAOgLcAE0BMgBNAS7/qAKSAE0CEABNA3IATQL3AE0C6wA6AnoATQLrADoCigBNAkIANwInABIC2gBKAroADQO1ABICrgAPApgAAwKJADUBSwBGAfkADgFLABYCQwA7AfQAAAGxAD4CagApAoEASQHzAC0CgQAtAkoALQFnAA4ChAAtAnwASQEeAD4BHv/LAjkASQEwAEgDrwBJAnwASQJrAC0CgQBJAoIALQGRAEkB6gAyAWYADQJ3AEUCQwAFA2sAEQJRAAkCRAAFAiUAMgFdACEA4AAyAV0AFgJDABsBdABNAkMAHwIQAE0BfQBIAoAADgKQAA4CrQAOA8cADgPXAA4DHgAAASMASQRgAGID2AC9A9gAlQPYAowD2ABzA9gCYQPYAZYD2AC1A9gCkAPYAM8D2ACKA9gAZgPYAkQD2ABzA9gCRgPYAlgD2ACOA9gCVgPYAJMD2AFgA9gASAPYACoD2AAqA9gBkAPYACwD2AAqA9gAKgPYAh0D2ACOA9gAKgPYACoCoQBAA9gBrgPYAHoD2AJJA9gAegPYAlAD2ADUA9gAQgPYANQD2ABCA+gAigPoAIoD6AB9A+gAlgPoAJYD6ABuA+gAbgPYADYALgBBADwANgBFAC4AMgAxADQAGABlAB4ALgA3ACAARQAcACIAKwBCADoAPwBEADYAEgArAE8ADwAUABAAEAAfAAgADgANAAsADAAQABQAFwARAAgADwAmACMAGQAWACcAMQAxADoAawAuACkAGgArABUAaQA4AB8AKQAbABQARQA3ADgAGQA6ABcAJAAZAEMAOQAyADgAQwA4AEIAMwAWAB8AKgB/AA8AOwBNABIAIgBbACEADgBeACEAFABSAFUAYwBWAGEAYABbAFkACwArACQAKAAdACQAOgAiACkAIwArAC8AJAAsACEAPgAXAFkAFgAzABwAPgApABgAFwAaABkAUQAiABIADwAPABYADwBtAEgARwA2ABsAEAA2AC8AYwAuAEcAPwBdABsAFgARACAAEgATABgAFwAcABcAEwAVACcAFgARADcAMQBTAA8AQAApACAAJQAiACEAIwAoACMAIwAdACMAQQAjAB8AHgAgAB8AGgAoABwAJAASABQANgAyABoAKwAdABAAIQAhAKIAWABcACEAOgA6ADgANQAaACsAJAAUABQAGQAjAB8AHgAcABYAEQALACoAIwAXABIAFAAOAAoAFwALAAwANQAQAC0AKAAsACsAFQAMABoAMQAmACUAKgAkACUALgAeABgAGgAmAB4ANQAjACkAKQAfACEAGgAhACcAJQALACQAGAAYABwAGgA6ACcALQAjACcAHwBwAB4AVwAkAIcAPABYAJQAMQAQABcAVgBFABwAEAAMAAcAIAA/ABgAEwA5ADEAPAA7AC4AJQAgACwADgAjAC4APQAwACkAMQAvAC8AMAAyACcALgA1ACMAJABDAA8ATACLADoAGgArAD4AKwAnACEAKwAmABsAHQAMACMAFAAaABsAEQAQAEEAOgA4AEEAQgAwAC8AOAA7ADwAOwAtABwAFAAaAAsAIgAdACYALAAqADIAHwAfACQAJgAlACUAIgAaAAkAGgAaABsAHgAaABcAMgASADMAOQAhABEAEQARABoAEQBIAFsAXQBbAFsAUABPAFUAUwBGAEIAFAAIABUAFAA7AD4APwAlABsAMwAPAB8AUAAHAEMAFQAZAC8AWgAAAAIAAAADAAAAFAADAAEAAAAUAAQNDAAAAzgCAAAIATgAfgC3ANcgFCAmIZMloSXGJcslzyYGMAIwDTARTgBOA04HTgtODk4UTiROKk4tTjhOO05FTkhOS05dTmBOjE6OTpFOlE6nTrpO5U7sTvBO9k77TxpPTU9PT1NPXE9/T79P3VANUE9QWlBcUUlRTVFlUWhRa1FtUXNRdlGFUY1Rs1HGUc9R+1IHUhlSIFIkUjBSNlI6Uk1SaVKgUqhTQVNDU0dTVVNhU3NTu1PNU9FT1lPjU+VT8FPzVARUDlQRVC9UfVUvVbdW21beVuBW9Fb6VwZXKFcwVzpXR1f6WJ5YqFkEWQ1ZFlknWSlZLlkxWctbWFuDW4xbmlueW7Zb+VwEXAZcD1wdXDpcPlxAXE9d5l3yXgZeJ152XpRepl8AXw9fFV8xXzpfU19iX3FfhF+XX6pfrl/DX8VgAWAOYDtgYmEPYhFiFmIYYkBiS2JTYn5i1mLlYuljAmMHYwljYmNuY4xjpWOoY9Bj4WRHZKRkzWU7ZT5lSGVMZWNlcGV0ZYdlsGW5ZeBl5WX2Zg5mL2Y+ZoJnAGcJZx9nKmcsZzpnQGdQZ19nYWdlZ39ngWeaZ5xn02flaAdoOGg8aGNqIWo9ayJrZGuLa7Vrz2wUbDRsOGynbLNsuWy/bNVs4m07bUFtRm1ObWptbm13bYhtsm4FbjJuOG7abuFvFHCucLlyBnJ5cuxzDnOHc6lzsHUfdSh1MXVMdVl1kXZ+doR27nb0dvh3C3eEd6x37Xg0eEB4bnk6ebt50nn7enp6f3qXest7EXsse358e3zWfS9+p36/fsR+yH7PftN+537tfxh/KX9uf46ABYAMgBeA/YHqgfOCcoLxgwODq4O3g9yEPYRXiEyIaIiricKJxInSieOJ5ouhi6SLrYuwi76L1YvXi+WL9Iv3jAONH40ljSiNNI13jd2N746rj2+PfY+5j8eP0Y/Uj9iP24/ej/CP/ZAAkAmQEJAUkB+Qf5DokP2RzZHPkdGU9pT6lP6VAZUulX+V6JXtlfSWRJZNllCWZJZ3lo+WlJa+lsWW9pcHl1KXXpdimHmYe5iEmJyYzpjemYia2J5Pns+e0Z8g/wH/A/8G/wn/DP8b/x///wAAACAAtwDXIBQgJiGQJaAlxiXLJc8mBTABMAowEE4ATgNOB04JTg1OFE4kTipOLU44TjpORU5ITktOXU5fToxOjk6RTpROp066TuVO7E7wTvZO+08aT01PT09TT1xPf0+/T91QDVBPUFpQXFFJUU1RZVFoUWtRbVFzUXZRhVGNUbJRxlHPUfpSBlIZUiBSJFIwUjZSOlJNUmlSn1KoU0FTQ1NHU1VTYVNzU7tTzVPRU9ZT41PlU+9T81QEVAxUEVQvVH1VL1W3VttW3lbgVvRW+lcGVyhXMFc6V0dX+lieWKhZBFkNWRZZJ1kpWS5ZMVnLW1dbg1uLW5pbnlu2W/lcBFwGXA9cHVw6XD1cQFxPXeZd8l4GXidedl6UXqZfAF8PXxVfMV85X1NfYl9xX4Rfl1+qX65fw1/FYAFgDmA7YGJhD2IPYhZiGGJAYktiU2J+YtZi5WLpYwFjB2MJY2JjbmOMY6Vjp2PQY+FkR2SkZM1lO2U+ZUhlTGVjZXBldGWHZbBluWXgZeVl9mYOZi9mPmaCZwBnCGcfZypnLGc6Z0BnUGdfZ2FnZWd/Z4FnmmecZ9Nn5WgHaDdoPGhjaiFqPWsha2Rri2u1a89sFGw0bDhsp2yzbLlsv2zVbOFtO21BbUZtTm1qbW5td22IbbJuBW4ybjhu2m7hbxRwrnC5cgZyeXLscw5zh3Opc691H3UodTF1THVZdZF2fXaEdu529Hb4dwt3hHesd+14NHhAeG55Onm7edJ5+3p6en96l3rLexF7LHt+fHt81n0vfqd+v37Dfsh+z37Tfud+7X8Yfyl/bn+OgAWADIAXgP2B6oHzgnKC8YMDg6uDt4PchD2EV4hMiGiIq4nBicSJ0onjieaLoYuki62LsIu+i9WL14vli/SL94wDjR+NJY0ojTSNd43dje+Oq49uj32PuY/Hj9GP1I/Yj9uP3o/wj/2QAJAJkBCQFJAfkH+Q6JD9kc2Rz5HRlPaU+pT+lQGVLpV/leiV7ZX0lkSWTZZQlmSWd5aPlpSWvpbFlvaXB5dSl16XYph5mHuYhJic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/+z/7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/mAAAAAP/cAAD/4v/4/9gAAAAAAAAAAP/Q/+z/7P/vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP93/9gAAP/QAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/6gAA/9oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/5v/4/+T/7//v/9gAAP/k//D/xAAA//gAAAAAAAAAAAAA/+T/5P/4/97/2AAAAAAAAAAAAAAAAAAAAAAAAAAA/6j/2//H//j/vP/k/5wAAAAAAAD/zAAAABQAAAAAAAAAAAAAAAAAAAAAAAD/4P8rAAAAAAAAAAAAAAAAAAAAAP/xAAD/9P/Y//b/4//w/8wAAAAA/+z/9gAAAAAAAAAAAAAAAAAA/+z/7AAA//wAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAP/pAAD/4P/w/+AAAAAA//T/7P/sAAAAAAAAAAAAAAAAAAAAAAAAAAD/9gAA//T/9AAAAAAAAAAAAAAAAAAAACP/7AAAAAAAAAAAAAAAAAAAABT/7/9x/7AAAP+w//gAAAAA/9D/0P/E/8f/+AAA/+//9P/s/9D/5//QAAAAAP/4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//wAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//QAAAAAAAAAAAAAAAAAAAAAAAD/+AAAAAAAAAAAAAAAAAAAAAAAAP+8/9sAAP/YAAAAAAAA/+z/7P/sAAAAAAAAAAAAAAAAAAAAAAAA/+8AAAAAABf/2AAAAAAAAAAAAAD/6QAA//T/2P9d/6QAAP+QAAAADAAA/8T/xP+4/9gAAAAA/8z/9P/4/8z/2P/M/8QAAAAAAAD/7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAFACIAKAAAACsALQAHADAAOwAKAGIAYgAWAGkAaQAXAAIAFwAiACIAAwAkACQABAAlACUABQAmACYABgAnACcABwAoACgACAArACsACQAsACwACgAtAC0ACwAwADAABQAxADEAAQAyADIABQAzADMADAA0ADQADQA1ADUADgA2ADYADwA3ADcAAgA4ADgAEAA5ADkACgA6ADoAEQA7ADsAEgBiAGIACwBpAGkAAwABAAMAaQACAAAAAAAAAAAAAgAAAAAAAAAAAA0AAAANAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgACAAAAAAAAAAAAAAAA4AAAADAAAAAAAAAAMAAAAAABMAAAAAAAAAAAADAAAAAwAAABsABAAFAAYABwABAAgADwAAAAAAAAAAAAAAAAAQAAAAFAAUABQACQAVABIAHAARABIACgAdAB0AFAAeABQAHQAWAAsAFwAMABgAGgAMAB8AAAAAAAAAAAAZAAAAAAAKAAkACQAJAAkACQAOABIADQACBHIABAAABI4E4AARACEAAAAAAAAAAAAA/8T/4P+t//D/8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/k/+wAAAAA/9D/1f/E//YAAP/Y/+wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9sAAP/YAAAAAP/sAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAKwAoACgAIAAXAAYAAP/pACD/+AAvABcASP/u//gAEv/v//3/+P/4//gAEgAvAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+cAAP/v//D/+gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPwAv/+wAAAAAAAAAAAAAAAAAAAAjACMAAAAAAAAAAAAAAAAAAAAAAAAAAAA3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+8AAAAAAAAAAAAA/+wAAAAAAAAAAP/s/+wAAP/yAAAAAP/sAAAAAAAA//T/8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//j//AAAAAAAAAAAAAAAAAAAAAD/7AAAAAAAAAAAAAD/+gAAAAAAAP+LAAAAAAAAAAAAAAAAAAAAAAAA//gAAP/4AAAAAAAAAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYAAP+gAAAAAAAjAAAAAP/X//gADAAAAAAAAAAAAAAAFAAAAAAAAAAAAAAAAAAAAAAAAP/4//YAAAAA/9D/4P/E//gAAAAA/+wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAAAAAAAAAAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9gAAP/4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/vAAAAAAAA/+8AAAAAAAAAAP+sAAAAAAAAAAAAAP/a//YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/vAAAAAAAA//gAAAAAAAAAAP/IAAAAAAAAAAAAAP/cAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAEAEIAQwAAAEYARwACAEkAWwAEAGQAaAAXAAEAQwAmAAEAAAAAAAIAAwAAAAQABQAGAAcACAAEAAQAAQABAAkACgALAAwADQAOAA8ABwAOABAAAAAAAAAAAAAAAAAAAAAAAAUACAADAAUACAABAAMAaQANAAAAAAAAAAAADQAAAA4ADwAAAAoAAAAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAdAB0AAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAaAAYACwABAAcAAAAAAAAAAwAAAAAAAAAQAAAAEQARABEAEgATABQAFQAMABQAFgAeAB4AEQAfABEAHgAXABgAGwAIAAkAAgAIACAAAAAAABkAAAAcAAAAAAAWABIAEgASABIAEgAAABQACgACAQAABAAAARoBWgAIAA8AAAAAAAAAPAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACMARAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+oACMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/Q/9gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/2P+oAAAAAAAAAAAAAQALAAMACAAJAAsADQAPACAAPABcAGAAawACAAoAAwADAAQACAAIAAQACwALAAUADQANAAYADwAPAAYAIAAgAAEAPAA8AAIAXABcAAMAYABgAAcAawBrAAYAAQAiAEkAAQAJAAQACQAJAAkABAAJAAkACwAJAAkACQAJAAQACQAEAAkAAAAGAAAABwAMAAAACAAAAAAAAAAAAAAAAAAAAA0AAAAFAAUABQAAAA4AAgAAAAMAAgAKAAAAAAAFAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJAAoAAAAAAAAAAAAAAAEAAgABAAAACgCCAYAABERGTFQAGmN5cmwALGdyZWsAPmxhdG4AUAAEAAAAAP//AAQAAAABAAYACgAEAAAAAP//AAQAAAACAAcACwAEAAAAAP//AAQAAAADAAgADAAKAAFDQVQgABgAAP//AAQAAAAEAAkADQAA//8ABQAAAAQABQAJAA0ADmNhbHQAVmxpZ2EAXGxpZ2EAYmxpZ2EAcGxpZ2EAfmxvY2wAjHZlcnQAknZlcnQAmHZlcnQAqHZlcnQAuHZydDIAyHZydDIAznZydDIA3nZydDIA7gAAAAEACAAAAAEAAQAAAAUAAQACAAMABAAGAAAABQABAAIAAwAEAAUAAAAFAAEAAgADAAQABwAAAAEAAAAAAAEACQAAAAYACQAKAAsADAANAA8AAAAGAAkACgALAAwADQAOAAAABgAJAAoACwAMAA0AEAAAAAEAEQAAAAYAEQASABMAFAAVABcAAAAGABEAEgATABQAFQAWAAAABgARABIAEwAUABUAGAAbADgAdgB2AHYAdgB2AHYAdgC6ARgBGAEYARgBGAEYARgBGAEYARgBGAEYARgBGAEYARgBbgGcAAYAAAACAAoAHgADAAAAAgC+ACgAAQC+AAEAAAAZAAMAAAACABoAFAABABoAAQAAABkAAQABAGAAAQABAC0ABAAAAAEACAABADYAAQAIAAUADAAUABwAIgAoAGcAAwBHAEoAaAADAEcATQBmAAIARwBkAAIASgBlAAIATQABAAEARwAGAAAAAgAKACwAAwAAAAEAHAAGADwAQgBIAE4ASABOAAEAAAAaAAEAAQAiAAMAAAABABoABQAgACYALAAmACwAAQAAABoAAQABAE0AAQABAEoAAQABAEMAAQABAEIAAQAAAAEACAACACgAEQBxAG4AcABzAHcAeQCAAIEAggCDAIQAhQCIAIkAiwCNAI8AAQARAGsAbQBvAHIAdgB4AHoAewB8AH0AfgB/AIYAhwCKAIwAjgAEAAAAAQAIAAEAHgACAAoAFAABAAQAYgACAGAAAQAEAGMAAgBgAAEAAgAtAE0AAQAAAAEACAACAAoAAgBpAGoAAQACACIATQAAAAEAAAH0/gwAAAPoAAD/xQQjAAAAAQAAAAAAAAAAAAAAAAABA+gAbANSAJwAWgCcAD8AkgCSAFoAWgBaAFoBIgKyAeUCpgB+AJIAnACSAJIAnACcAJIAnACRAJIBLwEvAQUBaQEFAJAAkwCcAJwAkgCcAJwAnACSAJwAnACcAJwAnACcAJwAkgCcAJIAnACSAJwAnACcAJwAnACcAJwAWgBaAFoAnAPDAGMBLQBaASwAWgEsAFYBLABaAFMAUwBaAFoBLAEsASwBLAEsASwBLAC2ATYBNgE2ATYBNgE2AFoAWgBaAcQBqwEkAJwAWgBTAFYAVgBTAFYAnABaAqYAkgEvAK0CsgCeAG4AnABZAJwAkgCQAGEBLwCtAEYARgBGAa4ARgBGAh0BGgITAScBNwCnAEYARgH9AQQB6gAAArIAoAK6AKMALgDWAC4A1wCKAIoAfQCWAJYAZwBnAYkAPgBhAG8ANgBjAGYARABMAE8AGwA2ADoANgA8ACoANAA/ADUAOgBlAJAAXgBiAGUAMQBEADYAKQAoADYANQAgACkALgA0ACwALQA1AD0AMgAtADEALwA6ACcALgAlAEgARQBGADwAPABgADYANwArADQAMwAzACoAOQBDAEcAPgBFAD8AOQA5AEAANgA2ADkAOQA/ADYANQA5AFMAMwA5AB4ATwCAACgAYAAnADMAIwBZAC4APAA0ACgAIAA0ADgAcQBPAFYATwBNAFYAJgA6ADgALQBDADoAUAA8ACoAMwA2AGcAOgA6ADcAMQArADUALAAzACwALQAvADgAOwAfAEQANgBUAE0AUgBQAFMAOQBXADUANAA+ACYAMABhADEARABSAEAAWAA4ADIAOQAtAC8AKQA5ACkAJQAxACsAOQAwAC0AOwAlADoAJgA3ADMAQwA2AD0AJgBAAD8AOgA4AD8ANAAwAEAANAAyADQALABBAEMAPgAyAD0ALQAzADgAMQAwADgAKQA5AC8ANQBgAGYAOgBWAFAATgAyAEgATgAsAD0ANgA5ADgAJAA3ADgAJwA0ADYANwAvAFIAJgAtAEIAPAA2ACQANwA1ACcANAAuADYAMgA0ACQAJgA6AA8AKgA4ADkAOQA4ADMANQBDADEAHwAtACoALwA3ADYANgA9ADMANQAtADUANAA0ADkAOwA7AC8APQAyAGQAZgBSADkAXAA7AEoALAA4ACgAUgAtAFYAOAA6AD0AOgBFADQAOQAzACUAXQArADYAMgAxACwALQAwACYAIQA9ADgAMQBLAC8ALwAwADIAOQAyADIAOQA2ACsAMQBWADQAOgBYADMAJwA4AF0AIAA6ADMAKwA2ADMAOAA4ACwAOQA3AFAATwA6ACAALAAlADAAOAA6AEMALQA0ADUAPAAyADwAOwAeADkAOgA7AD0AUQAhADkAJQAvAC4ANwA6ADcANAA3ADkALgA5ADwANAA2ADUALAA5ADUAMQA4ADoARwAsADYAJwA2ADYANgA7ACQAIQApACkAIABOACoAKwAwAFMAMAA1AEcATgA7ADwATwBaADcAVAAwAE0AXwA2AC8AMQBAAFAAJAAA",
}
_UI_FONT_DEC: Dict[str, Optional[bytes]] = {}

def _ui_font_bytes(weight: str):
    b = _UI_FONT_DEC.get(weight)
    if b is None:
        try:
            b = base64.b64decode(_UI_FONT_B64.get(weight, ""))
        except Exception:
            b = None
        if not b:
            b = None
        _UI_FONT_DEC[weight] = b
    return b


def _ui_font_ready() -> bool:
    for w in ("r", "s", "h"):
        if not _ui_font_bytes(w):
            return False
    return True


def _find_cjk_font() -> Optional[str]:
    fp = CONFIG.get("FONT_PATH", "")
    if fp and Path(fp).exists() and _font_is_good_cjk(fp):
        return fp
    for path in _collect_font_candidates():
        if path and Path(path).exists() and _font_is_good_cjk(path):
            return path
    bundled = _bundled_font()
    if bundled and _font_is_good_cjk(bundled):
        print(f"[font] using bundled font: {bundled}")
        return bundled
    return None


class FTFont:
    _CACHE_LIMIT = 800
    _ADV_LIMIT = 400

    def __init__(self, path, size: int, bold: bool = False,
                 weight: Optional[str] = None) -> None:
        self.ft = pygame.freetype.Font(path, size)
        if bold:
            self.ft.style = pygame.freetype.STYLE_STRONG
        self.size = size
        self.path = path
        self.bold = bold
        self.weight = weight
        self._cache: "OrderedDict[Tuple, pygame.Surface]" = OrderedDict()
        self._cw: Dict[str, int] = {}
        self._adv: Dict[Tuple, List[float]] = {}
        self._glyph_cache: "OrderedDict[Tuple, Tuple[pygame.Surface, int]]" = OrderedDict()

    def glyph(self, ch: str, color: Tuple[int, int, int]) -> Tuple[pygame.Surface, int]:
        key = (ch, tuple(color))
        got = self._glyph_cache.get(key)
        if got is not None:
            self._glyph_cache.move_to_end(key)
            return got
        try:
            s, _r = self.ft.render(ch, fgcolor=color)
            s = s.convert_alpha()
        except Exception:
            s = self._render_raw(ch, color, None)
        off = None
        try:
            m = self.ft.get_metrics(ch)
            if m and m[0]:
                off = int(round(float(m[0][3])))
        except Exception:
            off = None
        if off is None:
            off = s.get_height()
        got = (s, off)
        if len(self._glyph_cache) >= FTFont._CACHE_LIMIT:
            self._glyph_cache.popitem(last=False)
        self._glyph_cache[key] = got
        return got

    def render(self, text: Any, antialias: bool = True,
               color: Tuple[int, int, int] = (255, 255, 255),
               bgcolor: Optional[Tuple[int, int, int]] = None) -> pygame.Surface:
        text = str(text)
        key = (text, tuple(color) if color else None,
               tuple(bgcolor) if bgcolor else None)
        surf = self._cache.get(key)
        if surf is None:
            surf = self._render_raw(text, color, bgcolor)
            if len(self._cache) >= self._CACHE_LIMIT:
                self._cache.popitem(last=False)
            self._cache[key] = surf
        else:
            self._cache.move_to_end(key)
        return TextSurf(surf, _cur_scale())

    def char_w(self, ch: str) -> float:
        try:
            s = round(float(_cur_scale()), 4)
        except Exception:
            s = 1.0
        key = (ch, s)
        w = self._cw.get(key)
        if w is None:
            try:
                m = self.ft.get_metrics(ch)
                w = (m[0][4] if m and m[0] else 0) / (s if s else 1.0)
            except Exception:
                w = self.render(ch, True, (255, 255, 255)).get_width()
            self._cw[key] = w
        return w

    def advances(self, text: str) -> List[float]:
        try:
            s = round(float(_cur_scale()), 4)
        except Exception:
            s = 1.0
        key = (text, s)
        v = self._adv.get(key)
        if v is not None:
            return v
        v = None
        try:
            m = self.ft.get_metrics(text)
            if m and len(m) == len(text):
                sc = s if s else 1.0
                v = [(mm[4] if mm else 0) / sc for mm in m]
        except Exception:
            v = None
        if v is None:
            v = [self.char_w(c) for c in text]
        if len(self._adv) >= self._ADV_LIMIT:
            self._adv.clear()
        self._adv[key] = v
        return v

    def _render_raw(self, text: str,
                    color: Tuple[int, int, int],
                    bgcolor: Optional[Tuple[int, int, int]]) -> pygame.Surface:
        try:
            s, _ = self.ft.render(text, fgcolor=color, bgcolor=bgcolor)
            return s.convert_alpha()
        except Exception:
            pass
        try:
            pieces: List[Tuple[pygame.Surface, int]] = []
            total_w = 0
            for ch in text:
                try:
                    s, _ = self.ft.render(ch, fgcolor=color, bgcolor=bgcolor)
                    pieces.append((s, total_w))
                    total_w += s.get_width()
                except Exception:
                    total_w += max(3, self.size // 3)
            h = max(1, self.size + 4)
            out = pygame.Surface((max(1, total_w), h), pygame.SRCALPHA)
            for s, x in pieces:
                out.blit(s, (x, 0))
            return out.convert_alpha()
        except Exception:
            return pygame.Surface((1, max(1, self.size + 4)), pygame.SRCALPHA).convert_alpha()



_REAL_DRAW = pygame.draw

_SCALE_GETTER = lambda: 1.0
_NO_SCALE = False
_VIEW_OX = 0.0
_VIEW_OY = 0.0
_S_CACHE = None
_O_CACHE = None


def _invalidate_view_cache() -> None:
    global _S_CACHE, _O_CACHE
    _S_CACHE = None
    _O_CACHE = None


def _set_view_offset(ox: float, oy: float) -> None:
    global _VIEW_OX, _VIEW_OY
    _VIEW_OX, _VIEW_OY = float(ox), float(oy)
    _invalidate_view_cache()


def _view_offset() -> Tuple[float, float]:
    if _NO_SCALE:
        return 0.0, 0.0
    return _VIEW_OX, _VIEW_OY


def _set_scale_getter(fn) -> None:
    global _SCALE_GETTER
    _SCALE_GETTER = fn
    _invalidate_view_cache()


class _no_scale:

    def __enter__(self):
        global _NO_SCALE
        self._old = _NO_SCALE
        _NO_SCALE = True
        _invalidate_view_cache()
        return self

    def __exit__(self, *a):
        global _NO_SCALE
        _NO_SCALE = self._old
        _invalidate_view_cache()
        return False


def _raw(surf):
    if isinstance(surf, ScaledSurf):
        return surf._surf
    if isinstance(surf, TextSurf):
        return object.__getattribute__(surf, "_surf")
    return surf


def _cur_scale() -> float:
    try:
        return 1.0 if _NO_SCALE else float(_SCALE_GETTER())
    except Exception:
        return 1.0


class TextSurf:

    __slots__ = ("_surf", "_s")

    def __init__(self, surf: pygame.Surface, s: float) -> None:
        object.__setattr__(self, "_surf", surf)
        object.__setattr__(self, "_s", float(s) if s else 1.0)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_surf"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_surf"), name, value)

    def get_width(self) -> float:
        return object.__getattribute__(self, "_surf").get_width() / self._s

    def get_height(self) -> float:
        return object.__getattribute__(self, "_surf").get_height() / self._s

    def get_size(self):
        w, h = object.__getattribute__(self, "_surf").get_size()
        s = self._s
        return (w / s, h / s)

    def get_rect(self, **kwargs):
        w, h = object.__getattribute__(self, "_surf").get_size()
        s = self._s
        r = pygame.Rect(0, 0, int(round(w / s)), int(round(h / s)))
        for k, v in kwargs.items():
            setattr(r, k, v)
        return r

    def copy(self) -> "TextSurf":
        return TextSurf(object.__getattribute__(self, "_surf").copy(), self._s)


_FILM_DITH = (0.0, 0.020, -0.014, 0.009, -0.021, 0.015, -0.007, 0.018)


def _film_hsv(h: float, s: float, v: float) -> Tuple[int, int, int]:
    h = h - math.floor(h)
    i = int(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = i % 6
    if i == 0:
        c = (v, t, p)
    elif i == 1:
        c = (q, v, p)
    elif i == 2:
        c = (p, v, t)
    elif i == 3:
        c = (p, q, v)
    elif i == 4:
        c = (t, p, v)
    else:
        c = (v, p, q)
    return (int(c[0] * 255.0), int(c[1] * 255.0), int(c[2] * 255.0))


class ScaledSurf:

    __slots__ = ("_surf",)

    def __init__(self, surf: pygame.Surface) -> None:
        object.__setattr__(self, "_surf", surf)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_surf"), name)

    def __setattr__(self, name, value):
        if name == "_surf":
            object.__setattr__(self, "_surf", value)
        else:
            setattr(object.__getattribute__(self, "_surf"), name, value)

    def blit(self, src, dest, *args, **kwargs):
        s = _SCALE_GETTER()
        real = object.__getattribute__(self, "_surf")
        ox, oy = _view_offset()
        if s != 1.0 or ox or oy:
            if isinstance(dest, pygame.Rect):
                dest = (dest.x * s + ox, dest.y * s + oy)
            elif isinstance(dest, (tuple, list)):
                if len(dest) == 2:
                    dest = (dest[0] * s + ox, dest[1] * s + oy)
                elif len(dest) == 4:
                    dest = pygame.Rect(dest[0] * s + ox, dest[1] * s + oy, dest[2], dest[3])
        return real.blit(_raw(src), dest, *args, **kwargs)


class _ScaledDraw:

    @staticmethod
    def _s() -> float:
        global _S_CACHE
        v = _S_CACHE
        if v is None:
            v = 1.0 if _NO_SCALE else _SCALE_GETTER()
            _S_CACHE = v
        return v

    @staticmethod
    def _w(width: int, s: float) -> int:
        if width == 0:
            return 0
        return max(1, int(round(width * s)))

    @classmethod
    def _off(cls):
        global _O_CACHE
        v = _O_CACHE
        if v is None:
            v = _view_offset()
            _O_CACHE = v
        return v

    @classmethod
    def circle(cls, surf, color, center, radius, width=0):
        s = cls._s(); ox, oy = cls._off()
        return _REAL_DRAW.circle(_raw(surf), color,
                                  (center[0] * s + ox, center[1] * s + oy),
                                  max(1, radius * s), cls._w(width, s))

    @classmethod
    def rect(cls, surf, color, rect, width=0, **kw):
        s = cls._s(); ox, oy = cls._off()
        r = pygame.Rect(rect[0] * s + ox, rect[1] * s + oy,
                        rect[2] * s, rect[3] * s)
        return _REAL_DRAW.rect(_raw(surf), color, r, cls._w(width, s), **kw)

    @classmethod
    def line(cls, surf, color, start, end, width=1):
        s = cls._s(); ox, oy = cls._off()
        return _REAL_DRAW.line(_raw(surf), color,
                                (start[0] * s + ox, start[1] * s + oy),
                                (end[0] * s + ox, end[1] * s + oy), cls._w(width, s))

    @classmethod
    def lines(cls, surf, color, closed, points, width=1):
        s = cls._s(); ox, oy = cls._off()
        pts = [(p[0] * s + ox, p[1] * s + oy) for p in points]
        return _REAL_DRAW.lines(_raw(surf), color, closed, pts, cls._w(width, s))

    @classmethod
    def polygon(cls, surf, color, points, width=0):
        s = cls._s(); ox, oy = cls._off()
        pts = [(p[0] * s + ox, p[1] * s + oy) for p in points]
        return _REAL_DRAW.polygon(_raw(surf), color, pts, cls._w(width, s))

    @classmethod
    def arc(cls, surf, color, rect, start_angle, stop_angle, width=1):
        s = cls._s(); ox, oy = cls._off()
        r = pygame.Rect(rect[0] * s + ox, rect[1] * s + oy,
                        rect[2] * s, rect[3] * s)
        return _REAL_DRAW.arc(_raw(surf), color, r, start_angle, stop_angle,
                               cls._w(width, s))

    @classmethod
    def ellipse(cls, surf, color, rect, width=0):
        s = cls._s(); ox, oy = cls._off()
        r = pygame.Rect(rect[0] * s + ox, rect[1] * s + oy,
                        rect[2] * s, rect[3] * s)
        return _REAL_DRAW.ellipse(_raw(surf), color, r, cls._w(width, s))

    @classmethod
    def aaline(cls, surf, color, start, end, blend=1):
        s = cls._s(); ox, oy = cls._off()
        return _REAL_DRAW.aaline(_raw(surf), color,
                                  (start[0] * s + ox, start[1] * s + oy),
                                  (end[0] * s + ox, end[1] * s + oy), blend)


def _make_aura(size: int, peak: int, ring_at: float, ring_w: float,
               tail: int) -> np.ndarray:
    xx, yy = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    ring = np.exp(-((r - ring_at) / max(1e-3, ring_w)) ** 2)
    amb = np.clip(1.0 - r, 0.0, 1.0) ** 3.0 * float(tail)
    return np.clip(ring * peak + amb, 0, 255).astype(np.uint8)


def _make_radial(size: int, peak_alpha: int, falloff: float = 2.0) -> np.ndarray:
    xx, yy = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    return np.clip((1.0 - np.clip(d, 0, 1)) ** falloff * peak_alpha, 0, 255).astype(np.uint8)


def _tint_alpha(color, alpha: np.ndarray) -> pygame.Surface:
    W, H = alpha.shape
    rgb = np.zeros((W, H, 3), dtype=np.uint8)
    rgb[..., 0] = color[0]; rgb[..., 1] = color[1]; rgb[..., 2] = color[2]
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.surfarray.blit_array(surf, rgb)
    pa = pygame.surfarray.pixels_alpha(surf)
    pa[:] = alpha
    del pa
    return surf.convert_alpha()


def _make_beep(freq: float, dur: float, vol: float) -> pygame.mixer.Sound:
    sr = 44100
    n = int(sr * dur)
    t = np.arange(n) / sr
    env = np.exp(-t * 8)
    wave = np.sin(2 * np.pi * freq * t) * env * vol
    snd = np.int16(wave * 32767)
    stereo = np.stack([snd, snd], axis=1).copy()
    return pygame.sndarray.make_sound(stereo)


class Game:
    def __init__(self) -> None:
        _enable_dpi_awareness()
        pygame.init()
        pygame.freetype.init()
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        self.W, self.H = W, H
        self.fullscreen = bool(CONFIG["START_FULLSCREEN"])
        self.window_scale = float(CONFIG["WINDOW_SCALE"])
        self._vignette_merged = False
        self.vignette = None
        self.static_bg = None

        pygame.draw = _ScaledDraw
        _set_scale_getter(lambda: self.scale)

        self.desktop_w, self.desktop_h = self._query_desktop_size()
        self.window_scale = float(CONFIG["WINDOW_SCALE"])
        self._pending_frames = 0
        self._resize_target = None
        self._resize_win = None
        self._snapshot = None
        self._snap_tick = 0
        self._create_display(self.fullscreen)

        pygame.display.set_caption("糖浆 / SYRUP")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.anim_t = 0.0

        cjk_path = _find_cjk_font()
        self.font_path = cjk_path
        self._ui_font_cache = {}
        self.use_cjk = _ui_font_ready() or cjk_path is not None
        if _ui_font_ready():
            pass
        elif self.use_cjk:
            print(f"[font] using CJK font: {cjk_path}")
        else:
            print("!! 未找到中文字体，界面已降级为英文。")
            print("   请在 CONFIG['FONT_PATH'] 手动指定一个 .ttf / .otf / .ttc 文件。")
            _dump_cjk_fonts()
        self.zh_available = bool(self.use_cjk)

        self.f_big   = self._mkfont(self._fs(54), "s")
        self.f_med   = self._mkfont(self._fs(22), "s")
        self.f_small = self._mkfont(self._fs(14), "s")
        self.f_tag   = self._mkfont(self._fs(CONFIG["MENU_TAG_SIZE"]), "s")
        self.f_tiny  = self._mkfont(self._fs(11), "s")
        self.f_menu  = self._mkfont(self._fs(CONFIG["FONT_MENU"]), "s")
        self.f_over  = self._mkfont(self._fs(68), "h")
        self.f_chain = self._mkfont(self._fs(32), "h")
        self._poem_cache = {}
        self._poem_fonts = {}
        self.poem_font_path, self._poem_font_bytes = _find_poem_font()
        self.f_title = self._mkfont(self._fs(62), "h")
        self.f_head  = self._mkfont(self._fs(CONFIG["FONT_HEAD"]), "s")

        self.save_data = load_save(CONFIG["SAVE_PATH"], CONFIG["SAVE_VERSION"])
        self._apply_lang(str(self.save_data.get("lang", "en")))
        try:
            saved = int(self.save_data.get("body_size", CONFIG["FONT_BODY_STD"]))
            if saved not in (CONFIG["FONT_BODY_STD"], CONFIG["FONT_BODY_LARGE"]):
                saved = CONFIG["FONT_BODY_STD"]
        except Exception:
            saved = CONFIG["FONT_BODY_STD"]
        self.body_size = saved
        self.f_body = self._mkfont(self._fs(self.body_size), "r")

        try:
            sk = int(self.save_data.get("skin", 0))
        except Exception:
            sk = 0
        self.skin = sk if 0 <= sk < len(CONFIG["SKINS"]) else 0
        self.fx_trail = int(self.save_data.get("fx_trail", 0)) % len(CONFIG["TRAIL_STYLES"])
        self.fx_afterimage = bool(self.save_data.get("fx_afterimage", True))
        self.fx_energy_glow = bool(self.save_data.get("fx_energy_glow", False))
        self.fx_detonate_self = bool(self.save_data.get("fx_detonate_self", False))
        self.fx_swap_ghost = bool(self.save_data.get("fx_swap_ghost", False))
        self.fx_poem = bool(self.save_data.get("fx_poem", True))
        self.appear_sel = 0
        self.appear_open = False
        self.gallery_sel = 0
        self.gallery_open = False
        self._film_tmp = None
        if not self._skin_unlocked(self.skin):
            self.skin = self._skin_cycle(1)
            if not self._skin_unlocked(self.skin):
                self.skin = 0
            self.save_data["skin"] = self.skin

        self._tracked_cache: Dict[Any, List[pygame.Surface]] = {}
        self._big_font_cache: Dict[Tuple[int, int], FTFont] = {}
        self._trap_cache: Dict[Any, pygame.Surface] = {}
        self._logo_cache: Dict[float, List[pygame.Surface]] = {}
        self._mech_wrap_cache: Dict[Tuple[int, int], List[Tuple[str, int]]] = {}

        self._build_scaled_assets()

        self.snd_ok = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.snd_complete = _make_beep(880, 0.16, 0.35)
            self.snd_cancel   = _make_beep(1240, 0.07, 0.22)
            self.snd_detonate = _make_beep(560, 0.14, 0.30)
            self.snd_ok = True
        except Exception:
            self.snd_ok = False

        self.mode = "MENU"
        self.menu_sel = 0
        self.menu_stage = int(self.save_data["training_unlocked_stage"])
        self.c_hold_frames = 0
        self.c_hold2_frames = 0
        self.paused = False
        self.pause_sel = 0
        self.gameover_sel = 0
        self.stage = 1
        self.fade_timer = 0.0
        self.shake_level = 1.0
        self.toast_timer = 0.0
        self.toast_text = ""

        self._reset_esc_state()
        self._mech_wrap_cache: Dict[Tuple[int, int], List[Tuple[str, int]]] = {}

        self._init_tweens()

        self._build_icon()

        self._setup_game()

    def _init_tweens(self) -> None:
        rects = self._menu_options_rects()
        init_y = float(rects[self.menu_sel][1])
        self.menu_sel_y = ValueTween(init_y, CONFIG["UI_TWEEN_NORMAL"], ease_out_back)

        self.esc_anim = ValueTween(0.0, 0.18, ease_out_cubic)

        self.energy_tween = ValueTween(CONFIG["MAX_ENERGY"], CONFIG["UI_TWEEN_NORMAL"], ease_out_cubic)
        self.swap_cd_tween = ValueTween(1.0, CONFIG["UI_TWEEN_NORMAL"], ease_out_cubic)
        self.chain_bar_tween = ValueTween(1.0, CONFIG["UI_TWEEN_FAST"], ease_out_cubic)

        self.gameover_anim = ValueTween(0.0, CONFIG["UI_TWEEN_SLOW"], ease_out_back)
        self.stage_complete_anim = ValueTween(0.0, CONFIG["UI_TWEEN_SLOW"], ease_out_back)

        gr = self._gameover_options_rects()
        self.gameover_sel_x = ValueTween(float(gr[0][0]), CONFIG["UI_TWEEN_NORMAL"], ease_out_back)

    def mouse_pos(self):
        x, y = pygame.mouse.get_pos()
        s = self.scale
        ox, oy = _view_offset()
        x = (x - ox) / s if s != 1.0 else (x - ox)
        y = (y - oy) / s if s != 1.0 else (y - oy)
        return (x, y)

    def ev_pos(self, pos):
        s = self.scale
        return (pos[0] / s, pos[1] / s) if s != 1.0 else (pos[0], pos[1])

    def _fs(self, size: float) -> int:
        return max(1, int(round(size * self.scale)))

    def _query_desktop_size(self) -> Tuple[float, float]:
        W, H = self.W, self.H
        try:
            if sys.platform == "win32":
                import ctypes
                u = ctypes.windll.user32
                for a, b in ((76, 77), (0, 1)):
                    try:
                        w = int(u.GetSystemMetrics(a)); h = int(u.GetSystemMetrics(b))
                        if w > 0 and h > 0:
                            return float(w), float(h)
                    except Exception:
                        continue
        except Exception:
            pass
        try:
            info = pygame.display.Info()
            dw, dh = float(info.current_w), float(info.current_h)
            if dw > 0 and dh > 0:
                return dw, dh
        except Exception:
            pass
        try:
            modes = pygame.display.list_modes()
            if modes:
                return float(modes[0][0]), float(modes[0][1])
        except Exception:
            pass
        return float(W), float(H)

    def _compute_scale(self, fullscreen: bool) -> float:
        W, H = self.W, self.H

        try:
            fw, fh = CONFIG.get("FORCE_RENDER_SIZE", [0, 0]) or [0, 0]
            fw, fh = int(fw), int(fh)
            if fw > 0 and fh > 0:
                return max(0.25, min(fw / W, fh / H))
        except Exception:
            pass

        rt = getattr(self, "_resize_target", None)
        if rt is not None and not fullscreen:
            return max(0.4, min(float(rt), float(CONFIG["RENDER_MAX_SCALE"])))

        dw, dh = getattr(self, "desktop_w", None), getattr(self, "desktop_h", None)
        if not dw or not dh or dw <= 0 or dh <= 0:
            try:
                info = pygame.display.Info()
                dw, dh = float(info.current_w), float(info.current_h)
            except Exception:
                dw, dh = float(W), float(H)
            if dw <= 0 or dh <= 0:
                dw, dh = float(W), float(H)

        user = float(CONFIG["WINDOW_SCALE"])
        if fullscreen:
            s = min(dw / W, dh / H)
        else:
            fit = float(CONFIG["WINDOW_SCREEN_FIT"])
            s = min(user, min(dw * fit / W, dh * fit / H))
            s = math.floor(s * 4.0) / 4.0

        preset = float(CONFIG.get("RENDER_SCALE_PRESET", 0.0) or 0.0)
        if preset > 0:
            s = preset
        rt = getattr(self, "_resize_target", None)
        if rt is not None and not fullscreen:
            s = float(rt)
        lo = 1.0 if fullscreen else 0.4
        return max(lo, min(float(s), float(CONFIG["RENDER_MAX_SCALE"])))

    def _queue_resize(self, w: int, h: int) -> None:
        if self.fullscreen or w <= 0 or h <= 0:
            return
        try:
            real = pygame.display.set_mode((w, h), pygame.RESIZABLE)
            self.screen = ScaledSurf(real)
            self.win_w, self.win_h = int(w), int(h)
        except Exception:
            return
        self._stretch_last_frame(int(w), int(h))
        self._resize_win = (int(w), int(h))
        self._apply_viewport(int(w), int(h))
        s = max(0.4, min(w / self.W, h / self.H))
        self._resize_target = s
        self._pending_frames = int(CONFIG["RESIZE_SETTLE_FRAMES"])

    def _stretch_last_frame(self, w: int, h: int) -> None:
        snap = getattr(self, "_snapshot", None)
        if snap is None:
            return
        try:
            real = _raw(self.screen)
            real.blit(pygame.transform.smoothscale(snap, (w, h)), (0, 0))
            pygame.display.flip()
        except Exception:
            pass

    def _consume_resize(self) -> None:
        if getattr(self, "_pending_frames", 0) <= 0:
            return
        self._pending_frames -= 1
        if self._pending_frames > 0:
            return
        self._pending_frames = 0
        try:
            self._apply_fullscreen(False)
        finally:
            self._resize_win = None
            self._resize_target = None

    def _intended_window_size(self, fullscreen: bool) -> Tuple[int, int]:
        dw, dh = self._desktop_size()
        if fullscreen:
            return int(dw), int(dh)
        if getattr(self, "_resize_win", None):
            return self._resize_win
        user = float(CONFIG["WINDOW_SCALE"])
        fit = float(CONFIG["WINDOW_SCREEN_FIT"])
        h = min(float(CONFIG["VIEWPORT_BASE_H"]) * user, dh * fit)
        w = h * (float(dw) / max(1.0, float(dh)))
        return int(round(w)), int(round(h))

    def _apply_viewport(self, target_w: int, target_h: int) -> None:
        if not CONFIG.get("ADAPTIVE_VIEWPORT", True):
            self.W, self.H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
            return
        ar = float(target_w) / max(1.0, float(target_h))
        base_h = float(CONFIG["VIEWPORT_BASE_H"])
        lw = base_h * ar
        lh = base_h
        w_min = float(CONFIG["VIEWPORT_W_MIN"]); w_max = float(CONFIG["VIEWPORT_W_MAX"])
        if lw > w_max:
            lw = w_max; lh = lw / ar
        elif lw < w_min:
            lw = w_min; lh = lw / ar
        lw = int(round(lw)); lh = int(round(lh))
        CONFIG["WIDTH"] = lw
        CONFIG["HEIGHT"] = lh
        self.W, self.H = lw, lh

    def _create_display(self, fullscreen: bool) -> None:
        self.fullscreen = bool(fullscreen)
        tw0, th0 = self._intended_window_size(self.fullscreen)
        self._apply_viewport(tw0, th0)
        W, H = self.W, self.H
        target = self._compute_scale(self.fullscreen)
        if self.fullscreen and CONFIG.get("FULLSCREEN_BORDERLESS", True):
            try:
                os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
            except Exception:
                pass
            flags = pygame.NOFRAME
        elif self.fullscreen:
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            flags = pygame.FULLSCREEN
        else:
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            flags = pygame.RESIZABLE

        dw = dh = 0
        if self.fullscreen:
            dw, dh = self._desktop_size()
            dw, dh = int(dw), int(dh)

        cands = [target] + [x for x in (2.5, 2.0, 1.5, 1.25, 1.0) if x < target]
        real = None
        for sc in cands:
            if self.fullscreen and dw > 0 and dh > 0:
                tw, th = dw, dh
                try:
                    real = pygame.display.set_mode((tw, th), flags)
                    self.scale = sc
                    pw, ph = int(round(W * sc)), int(round(H * sc))
                    break
                except Exception:
                    for fb in (pygame.FULLSCREEN, None):
                        try:
                            real = pygame.display.set_mode(
                                (tw, th), fb if fb is not None else flags)
                            self.scale = sc
                            pw, ph = int(round(W * sc)), int(round(H * sc))
                            break
                        except Exception:
                            continue
                    if real is not None:
                        break
                    tw2, th2 = int(round(W * sc)), int(round(H * sc))
                    try:
                        real = pygame.display.set_mode((tw2, th2), flags)
                        self.scale = sc
                        pw, ph = tw2, th2
                        break
                    except Exception:
                        continue
            else:
                tw, th = int(round(W * sc)), int(round(H * sc))
                try:
                    real = pygame.display.set_mode((tw, th), flags)
                    self.scale = sc
                    pw, ph = tw, th
                    break
                except Exception:
                    continue
        if real is None:
            self.scale = 1.0
            pw, ph = W, H
            try:
                real = pygame.display.set_mode((pw, ph), flags)
            except Exception:
                real = pygame.display.set_mode((pw, ph))

        if real.get_width() > 0 and real.get_height() > 0:
            if self.fullscreen:
                dw2, dh2 = self._desktop_size()
                if (real.get_width() < int(dw2) - 1 or real.get_height() < int(dh2) - 1):
                    for fb in (pygame.FULLSCREEN, pygame.FULLSCREEN | pygame.SCALED):
                        try:
                            alt = pygame.display.set_mode((int(dw2), int(dh2)), fb)
                        except Exception:
                            continue
                        if alt.get_width() > real.get_width():
                            real = alt
                        if real.get_width() >= int(dw2) - 1:
                            break
                self._apply_viewport(real.get_width(), real.get_height())
                W, H = self.W, self.H
                sc2 = max(0.25, min(real.get_width() / float(W),
                                    real.get_height() / float(H)))
                self.scale = sc2
                pw, ph = int(round(W * sc2)), int(round(H * sc2))
                if pw < real.get_width():
                    self.scale = (real.get_width() / float(W)
                                  + real.get_height() / float(H)) / 2.0
                    pw = int(real.get_width())
                if ph < real.get_height():
                    self.scale = (real.get_width() / float(W)
                                  + real.get_height() / float(H)) / 2.0
                    ph = int(real.get_height())
                dw3, dh3 = self._desktop_size()
                if (real.get_width() < int(dw3) - 1
                        or real.get_height() < int(dh3) - 1):
                    _force_window_full(dw3, dh3)
            else:
                sc2 = min(real.get_width() / float(W), real.get_height() / float(H))
                sc2 = max(0.25, min(sc2, float(CONFIG["RENDER_MAX_SCALE"])))
                if abs(sc2 - self.scale) > 1e-6:
                    self.scale = sc2
                    pw, ph = int(round(W * sc2)), int(round(H * sc2))
        self.screen = ScaledSurf(real)
        self.pw, self.ph = pw, ph
        self.win_w, self.win_h = real.get_width(), real.get_height()
        _set_view_offset((self.win_w - pw) / 2.0, (self.win_h - ph) / 2.0)
        self.fx = ScaledSurf(pygame.Surface((pw, ph), pygame.SRCALPHA).convert_alpha())

    def _desktop_size(self) -> Tuple[float, float]:
        dw, dh = getattr(self, "desktop_w", 0), getattr(self, "desktop_h", 0)
        if dw and dh and dw > 0 and dh > 0:
            return float(dw), float(dh)
        try:
            info = pygame.display.Info()
            dw, dh = float(info.current_w), float(info.current_h)
            if dw > 0 and dh > 0:
                return dw, dh
        except Exception:
            pass
        return float(self.W), float(self.H)

    def _build_scaled_assets(self) -> None:
        s = self.scale
        W, H = self.W, self.H

        self.glow_player  = _tint_alpha(self.pcol, _make_aura(
            int(CONFIG["GLOW_SIZE_P"] * s), CONFIG["GLOW_PEAK_P"],
            CONFIG["GLOW_RING_AT_P"], CONFIG["GLOW_RING_W_P"], CONFIG["GLOW_TAIL_P"]))
        self.glow_threat  = _tint_alpha(CONFIG["C_THREAT"], _make_aura(
            int(CONFIG["GLOW_SIZE_T"] * s), CONFIG["GLOW_PEAK_T"],
            CONFIG["GLOW_RING_AT_T"], CONFIG["GLOW_RING_W_T"], CONFIG["GLOW_TAIL_T"]))
        self.glow_spitter = _tint_alpha(CONFIG["C_SPITTER"], _make_aura(
            int(CONFIG["GLOW_SIZE_S"] * s), CONFIG["GLOW_PEAK_S"],
            CONFIG["GLOW_RING_AT_S"], CONFIG["GLOW_RING_W_S"], CONFIG["GLOW_TAIL_S"]))

        pw, ph = int(round(W * s)), int(round(H * s))
        vig = np.zeros((pw, ph), dtype=np.uint8)
        xx, yy = np.mgrid[0:pw, 0:ph].astype(np.float32)
        d = np.sqrt(((xx - pw / 2) / (pw / 2)) ** 2 + ((yy - ph / 2) / (ph / 2)) ** 2)
        vig[:] = np.clip((d - 0.75) * 340, 0, 170).astype(np.uint8)
        self.vignette = _tint_alpha(CONFIG["VIGNETTE"], vig)

        self._vignette_merged = (s >= float(CONFIG["VIGNETTE_MERGE_SCALE"]))
        self.static_bg = self._build_static_bg()
        self._logo_cache.clear()
        self._tracked_cache.clear()
        self._big_font_cache.clear()
        self._mech_wrap_cache.clear()

    def _apply_fullscreen(self, fullscreen: bool) -> None:
        self._create_display(fullscreen)
        self._rebuild_fonts()
        self._build_scaled_assets()
        self._build_icon()

    def _mkfont(self, size: int, weight: str = "s", bold: bool = False) -> FTFont:
        key = (weight, int(size), bool(bold))
        cache = getattr(self, "_ui_font_cache", None)
        if cache is None:
            cache = self._ui_font_cache = {}
        f = cache.get(key)
        if f is not None:
            return f
        f = None
        data = _ui_font_bytes(weight)
        if data:
            try:
                f = FTFont(io.BytesIO(bytes(data)), int(size), bold, weight)
            except Exception:
                f = None
        if f is None:
            f = FTFont(self.font_path, int(size), bold or weight != "r", weight)
        cache[key] = f
        return f

    def _rebuild_fonts(self) -> None:
        self.f_big   = self._mkfont(self._fs(54), "s")
        self.f_med   = self._mkfont(self._fs(22), "s")
        self.f_small = self._mkfont(self._fs(14), "s")
        self.f_tag   = self._mkfont(self._fs(CONFIG["MENU_TAG_SIZE"]), "s")
        self.f_tiny  = self._mkfont(self._fs(11), "s")
        self.f_menu  = self._mkfont(self._fs(CONFIG["FONT_MENU"]), "s")
        self.f_over  = self._mkfont(self._fs(68), "h")
        self.f_chain = self._mkfont(self._fs(32), "h")
        self.f_title = self._mkfont(self._fs(62), "h")
        self.f_head  = self._mkfont(self._fs(CONFIG["FONT_HEAD"]), "s")
        self.f_body  = self._mkfont(self._fs(self.body_size), "r")
        self.poem_glyphs = []
        self._poem_cache = {}

    def _build_static_bg(self) -> pygame.Surface:
        ww = int(getattr(self, "win_w", 0) or self.pw)
        wh = int(getattr(self, "win_h", 0) or self.ph)
        bg = pygame.Surface((ww, wh))
        bg.fill(CONFIG["BG"])
        s = self.scale
        step = max(4, int(round(CONFIG["GRID_STEP"] * s)))
        ox = int(round((ww - self.pw) / 2.0))
        oy = int(round((wh - self.ph) / 2.0))
        with _no_scale():
            x = ox % step - step
            while x <= ww:
                pygame.draw.line(bg, CONFIG["GRID"], (x, 0), (x, wh))
                x += step
            y = oy % step - step
            while y <= wh:
                pygame.draw.line(bg, CONFIG["GRID"], (0, y), (ww, y))
                y += step
            if getattr(self, "_vignette_merged", False) and self.vignette is not None:
                bg.blit(_raw(self.vignette) if isinstance(self.vignette, ScaledSurf)
                        else self.vignette, (ox, oy))
        return bg.convert()

    def _rebuild_body_font(self) -> None:
        self.f_body = self._mkfont(self._fs(self.body_size), "r")
        self._mech_wrap_cache.clear()

    def _apply_lang(self, lang: str) -> None:
        lang = str(lang or "en").lower()
        if lang not in ("zh", "en"):
            lang = "en"
        if lang == "zh" and not getattr(self, "zh_available", False):
            lang = "en"
        self.lang = lang
        self.use_cjk = (lang == "zh")
        self.S = STR_ZH if self.use_cjk else STR_EN
        if hasattr(self, "save_data"):
            self.save_data["lang"] = lang
        for attr in ("_mech_wrap_cache", "_tracked_cache", "_mech_line_cache"):
            if hasattr(self, attr):
                setattr(self, attr, {})

    def _build_icon(self) -> None:
        try:
            old_s = self.scale
            try:
                self.scale = 1.0
                with _no_scale():
                    ico = pygame.Surface((64, 64), pygame.SRCALPHA)
                    self._draw_logo(ico, 32, 32, scale=0.40, alpha=255)
            finally:
                self.scale = old_s
            pygame.display.set_icon(ico)
        except Exception:
            pass

    def _write_save(self) -> None:
        if self.mode == "RUN":
            total = self.score_detonate + self.score_perfect + self.score_kill
            sd = self.save_data
            sd["best_score"] = max(sd["best_score"], total)
            sd["best_chain"] = max(sd["best_chain"], self.chain_max)
            sd["best_wave"] = max(sd["best_wave"], self.wave)
            sd["best_time"] = max(sd["best_time"], self.t)
        sd = self.save_data
        sd["body_size"] = self.body_size
        sd["lang"] = self.lang
        sd["skin"] = self.skin
        sd["fx_trail"] = self.fx_trail
        sd["fx_afterimage"] = bool(self.fx_afterimage)
        sd["fx_energy_glow"] = bool(self.fx_energy_glow)
        sd["fx_detonate_self"] = bool(self.fx_detonate_self)
        sd["fx_swap_ghost"] = bool(self.fx_swap_ghost)
        sd["fx_poem"] = bool(self.fx_poem)
        save_now(CONFIG["SAVE_PATH"], sd)

    def _finalize_run(self) -> None:
        if self._finalized: return
        self._finalized = True
        sd = self.save_data
        total = self.score_detonate + self.score_perfect + self.score_kill
        sd["best_score"] = max(sd["best_score"], total)
        sd["best_chain"] = max(sd["best_chain"], self.chain_max)
        sd["best_wave"] = max(sd["best_wave"], self.wave)
        sd["best_time"] = max(sd["best_time"], self.t)
        sd["total_detonate"] = int(sd["total_detonate"]) + self.detonate_count
        sd["total_perfect"] = int(sd["total_perfect"]) + self.perfect_count
        sd["total_kill"] = int(sd["total_kill"]) + self.kill_count
        sd["total_runs"] = int(sd["total_runs"]) + 1
        sd["body_size"] = self.body_size
        save_now(CONFIG["SAVE_PATH"], sd)

    def _clear_save(self) -> None:
        self.save_data = dict(SAVE_DEFAULTS)
        self.save_data["version"] = CONFIG["SAVE_VERSION"]
        self.save_data["body_size"] = self.body_size
        self.save_data["lang"] = getattr(self, "lang", "en")
        save_now(CONFIG["SAVE_PATH"], self.save_data)
        self._apply_lang(self.save_data.get("lang", "en"))
        self.menu_stage = 1
        self.c_hold_frames = 0
        self.c_hold2_frames = 0
        self.toast_text = self.S["clear_success"]
        self.toast_timer = CONFIG["TOAST_DURATION"]

    def _quit_program(self) -> None:
        if self.mode == "RUN" and not self._finalized:
            self._finalize_run()
        self._write_save()
        pygame.quit()
        sys.exit()

    def _reset_esc_state(self) -> None:
        self.esc_open = False
        self.esc_page = "ROOT"
        self.esc_sel = 0
        self.esc_sub_sel = 0
        self.esc_mech_tab = 0
        self.esc_mech_scroll = 0.0
        self.esc_mech_max_scroll = 0.0
        self.esc_mech_fade = 0.0
        self.esc_ctrl_hover = -1
        self.c_hold_frames = 0
        self.c_hold2_frames = 0

    def _back_to_menu(self) -> None:
        if self.mode == "RUN" and not self._finalized:
            self._finalize_run()
        self._write_save()
        self.mode = "MENU"
        self.menu_sel = 0
        self.menu_stage = int(self.save_data["training_unlocked_stage"])
        self.paused = False
        self.pause_sel = 0
        self.game_over = False
        self.particles = []
        self.rings = []
        self.slashes = []
        self.popups = []
        self.projectiles = []
        self._reset_esc_state()
        self.menu_sel_y.snap(float(self._menu_options_rects()[0][1]))
        self.esc_anim.snap(0.0)
        self.appear_open = False
        self._start_fade()

    def _start_fade(self) -> None:
        self.fade_timer = CONFIG["TRANSITION_DURATION"]

    def _tick_fade(self, dt: float) -> None:
        if self.fade_timer > 0:
            self.fade_timer = max(0.0, self.fade_timer - dt)

    def _add_trauma(self, amount: float) -> None:
        self.trauma = min(CONFIG["SHAKE_MAX_TRAUMA"], self.trauma + amount)

    def _shake_offset(self) -> Tuple[float, float]:
        t = self.trauma
        if t <= 0 or self.shake_level <= 0:
            return 0.0, 0.0
        amp = (t ** 2) * CONFIG["SHAKE_MAX_OFFSET"] * self.shake_level
        at = self.anim_t * 60.0
        ox = math.sin(at * 0.06) * amp + math.sin(at * 0.17) * amp * 0.4
        oy = math.cos(at * 0.08) * amp + math.cos(at * 0.19) * amp * 0.4
        return ox, oy

    def _add_hitstop(self, frames: int) -> None:
        self.hitstop_frames = max(self.hitstop_frames, frames)

    def _marks_on(self) -> bool:
        return self.mode == "RUN" or (self.mode == "TRAINING" and self.stage >= 2)
    @property
    def pcol(self) -> Tuple[int, int, int]:
        return tuple(CONFIG["SKINS"][self.skin]["color"])

    @property
    def pskin(self) -> dict:
        return CONFIG["SKINS"][self.skin]

    def _skin_text_color(self, i: int, default):
        sk = CONFIG["SKINS"][i]
        if sk.get("top"):
            return tuple(sk.get("gold", (231, 190, 112)))
        try:
            col = tuple(sk["color"])
        except Exception:
            return default
        r, g, b = float(col[0]), float(col[1]), float(col[2])
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if lum >= 140.0:
            return (int(r), int(g), int(b))
        k = 140.0 / max(1.0, lum)
        return (int(min(255, r * k)), int(min(255, g * k)), int(min(255, b * k)))

    @property
    def trail_style(self) -> str:
        m = CONFIG["TRAIL_STYLES"][self.fx_trail]
        if m == "材质":
            return str(self.pskin["trail"])
        if m == "线":
            return "line"
        return "off"

    def _skin_glyph(self, i: int, rad: int, t: float = 0.0) -> pygame.Surface:
        s = max(0.001, float(self.scale))
        old_g = _SCALE_GETTER
        _set_scale_getter(lambda: 1.0)
        side = max(4, int(round(rad * 2 * s)))
        surf = pygame.Surface((side, side), pygame.SRCALPHA)
        try:
            col = self._skin_text_color(i, CONFIG["G_80"])
        except Exception:
            col = tuple(CONFIG["G_80"])
        sk = CONFIG["SKINS"][i] if 0 <= i < len(CONFIG["SKINS"]) else {}
        kind = str(sk.get("body", ""))
        c = side / 2.0
        R = rad * s
        rr = R * 0.70
        lw = max(1, int(round(R * 0.15)))
        if kind == "drip":
            pygame.draw.circle(surf, (*col, 255), (c, c), max(1, int(round(rr))), lw)
            pygame.draw.circle(surf, (*col, 205), (c, c + rr + R * 0.20),
                               max(1, int(round(R * 0.16))))
        elif kind == "spec":
            for k in (-1, 0, 1):
                pygame.draw.circle(surf, (*col, 235 if k == 0 else 145),
                                   (c + k * rr * 0.66, c),
                                   max(1, int(round(R * (0.29 if k == 0 else 0.19)))))
        elif kind == "iris":
            pygame.draw.circle(surf, (*col, 255), (c, c), max(1, int(round(rr))), lw)
            for k in range(3):
                a0 = k * (2.0 * math.pi / 3.0) + 0.45
                cc2 = tuple(self._shift_hue(col, -0.17 * k))
                pygame.draw.arc(surf, (*cc2, 225),
                                (c - rr, c - rr, rr * 2, rr * 2),
                                a0, a0 + 0.80, lw)
        elif kind == "film":
            pygame.draw.circle(surf, (*col, 255), (c, c), max(1, int(round(rr))), lw)
            pygame.draw.circle(surf, (*col, 175), (c - rr * 0.36, c - rr * 0.36),
                               max(1, int(round(R * 0.13))))
        elif kind == "poem":
            inkg = (104, 126, 168)
            gold = tuple(sk.get("gold", (216, 178, 108)))
            br = 0.5 + 0.5 * math.sin(t * 1.7)
            ss = 4
            big = side * ss
            bs = pygame.Surface((big, big), pygame.SRCALPHA)
            bc = big / 2.0
            RB = R * ss
            pr = RB * 0.48
            for li, (lb, la, lwv) in enumerate(
                    ((0.34, int(18 + 20 * br), 0.26),
                     (0.16, int(36 + 26 * br), 0.14),
                     (0.06, int(74 + 32 * br), 0.06))):
                ws = pygame.Surface((big, big), pygame.SRCALPHA)
                npts = 40
                pts = []
                for k in range(npts):
                    a = k * (2.0 * math.pi / npts)
                    w1 = math.sin(a * 3.0 + t * (0.80 + 0.22 * li))
                    w2 = math.sin(a * 5.0 - t * (0.50 + 0.30 * li) + li * 1.7)
                    rad2 = pr + RB * lwv * (1.0 + 0.55 * w1 * w1 + 0.28 * w2)
                    pts.append((bc + math.cos(a) * rad2,
                                bc + math.sin(a) * rad2))
                pygame.draw.polygon(ws, (*inkg, 255), pts)
                ws.set_alpha(la)
                bs.blit(ws, (0, 0))
            head = -t * 0.62
            span = 2.45
            npt = 46
            for k in range(npt + 1):
                f = k / float(npt)
                ang = head + f * span
                lift = 0.5 + 0.5 * math.sin(f * 7.4 + t * 2.1)
                dry = math.sin(f * 12.0 + t * 1.3) > 0.74
                wd = RB * (0.15 + 0.11 * lift) * (0.28 if dry else 1.0)
                rad2 = pr * (1.0 + 0.05 * math.sin(f * 4.0))
                aa = int(24 + 176 * (1.0 - f) ** 0.85)
                pygame.draw.circle(bs, (*inkg, aa),
                                   (bc + math.cos(ang) * rad2,
                                    bc + math.sin(ang) * rad2),
                                   max(1, int(round(wd))))
            for q in range(2):
                ang = -t * (0.85 + 0.26 * q) + q * 2.25
                rr2 = pr * (1.14 + 0.07 * q)
                for d in range(3):
                    aa2 = ang + d * 0.26 * (1 if q % 2 == 0 else -1)
                    al = int((176 - 56 * q) * (1.0 - 0.36 * d))
                    pygame.draw.circle(bs, (*inkg, max(0, al)),
                                       (bc + math.cos(aa2) * rr2,
                                        bc + math.sin(aa2) * rr2),
                                       max(1, int(round(RB * 0.105
                                                        * (1.0 - 0.24 * d)))))
            sweep = -t * 1.05
            for k in range(14):
                f = k / 13.0
                ang = sweep + f * 0.90
                rad2 = pr - RB * 0.24
                aa = int(104 * (1.0 - f) ** 1.30)
                pygame.draw.circle(bs, (*gold, aa),
                                   (bc + math.cos(ang) * rad2,
                                    bc + math.sin(ang) * rad2),
                                   max(1, int(round(RB * 0.062
                                                    * (1.0 - 0.40 * f)))))
            rim = RB * 0.78
            pygame.draw.circle(bs, (*col, int(126 + 58 * br)), (bc, bc),
                               max(1, int(round(rim))),
                               max(1, int(round(RB * 0.095))))
            pygame.draw.circle(bs, (*gold, int(70 + 52 * br)), (bc, bc),
                               max(1, int(round(rim))),
                               max(1, int(round(RB * 0.035))))
            pygame.draw.circle(bs, (*col, int(150 + 62 * br)),
                               (bc, bc), max(1, int(round(RB * 0.17))))
            mk = pygame.Surface((big, big), pygame.SRCALPHA)
            steps = 22
            for k in range(steps, 0, -1):
                f = k / float(steps)
                aa = int(round(255.0 * min(1.0, max(0.0, (1.0 - f) / 0.38))))
                pygame.draw.circle(mk, (255, 255, 255, aa), (bc, bc),
                                   max(1, int(round(RB * 1.18 * f))))
            bs.blit(mk, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(pygame.transform.smoothscale(bs, (side, side)), (0, 0))

        else:
            pygame.draw.circle(surf, (*col, 255), (c, c), max(1, int(round(rr))), lw)
        _set_scale_getter(old_g)
        return surf

    def _skin_label(self, i: int) -> str:
        sk = CONFIG["SKINS"][i]
        base = sk["name"] if self.use_cjk else sk["en"]
        if sk.get("top"):
            base = base + (" ◆ 极" if self.use_cjk else " ◆ MAX")
        return base

    def _skin_unlocked(self, i: int) -> bool:
        sk = CONFIG["SKINS"][i] if 0 <= i < len(CONFIG["SKINS"]) else {}
        if CONFIG.get("SKIN_UNLOCK_ALL"):
            return True
        req = sk.get("req")
        if not req:
            return True
        try:
            kind, val = req[0], req[1]
        except Exception:
            return True
        if kind == "train":
            return bool(self.save_data.get("training_done", False))
        if kind == "score":
            try:
                return int(self.save_data.get("best_score", 0)) >= int(val)
            except Exception:
                return False
        return True

    def _skin_req_text(self, i: int) -> str:
        sk = CONFIG["SKINS"][i] if 0 <= i < len(CONFIG["SKINS"]) else {}
        req = sk.get("req")
        if not req:
            return self.S["skin_default"]
        try:
            kind, val = req[0], req[1]
        except Exception:
            return ""
        if kind == "train":
            return self.S["skin_req_train"]
        return self.S["skin_req_score"].replace("{n}", str(int(val)))

    def _ink_index(self) -> int:
        for i, sk in enumerate(CONFIG["SKINS"]):
            if sk.get("poem"):
                return i
        return len(CONFIG["SKINS"]) - 1

    def _skin_cycle(self, d: int) -> int:
        n = len(CONFIG["SKINS"])
        if n <= 0:
            return 0
        i = self.skin
        for _ in range(n):
            i = (i + d) % n
            if self._skin_unlocked(i):
                return i
        return self.skin if self._skin_unlocked(self.skin) else 0

    def _fx_label(self, i: int) -> str:
        return (CONFIG["FX_NAMES"][i] if self.use_cjk
                else CONFIG["FX_NAMES_EN"][i])

    def _shadows_on(self) -> bool:
        return self.mode == "RUN" or (self.mode == "TRAINING" and self.stage >= 3)
    def _cancel_on(self) -> bool:
        return self.mode == "RUN" or (self.mode == "TRAINING" and self.stage >= 4)
    def _perfect_on(self) -> bool:
        return self.mode == "RUN" or (self.mode == "TRAINING" and self.stage >= 5)

    def _setup_game(self) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        self.player_pos = np.array([W / 2, H / 2], dtype=np.float64)
        self.player_prev_pos = self.player_pos.copy()
        self.player_vel = np.zeros(2, dtype=np.float64)
        self.aim_dir = np.array([1.0, 0.0])
        self.player_trail: List[np.ndarray] = []
        self.afterimages: List[Dict[str, Any]] = []
        self.sword_qi: List[Dict[str, Any]] = []
        self.poem_glyphs: List[Dict[str, Any]] = []
        self.poem_line: int = 0
        self.poem_pos: int = 0

        self.player_state = "IDLE"
        self.state_frame = 0
        self.dash_dir = np.array([1.0, 0.0])
        self.dash_total_frames = CONFIG["DASH_FRAMES"]
        self.dash_hits: Set[int] = set()
        self.phase_grace_indices: Set[int] = set()
        self.phase_grace_timer = 0
        self.iframe_frames = 0
        self.did_cancel_this_backswing = False
        self.consecutive_cancels = 0

        self.buf_dash = 0
        self.buf_swap = 0
        self.free_cancel_left = int(CONFIG["DASH_CANCEL_FREE_CHAIN"])
        self.no_energy_cd = 0

        self.shadows: List[Dict[str, Any]] = []
        self.swap_cd_frames = 0
        self.energy = CONFIG["MAX_ENERGY"]

        self.chain_count = 0
        self.chain_timer = 0
        self.chain_break_flash = 0
        self.chain_max = 0
        self.discovered = set()

        self.score_detonate = 0
        self.score_perfect = 0
        self.score_kill = 0
        self.detonate_count = 0
        self.perfect_count = 0
        self.kill_count = 0

        self.bullet_time_frames = 0
        self.invert_frames = 0

        self.frame = 0
        self.t = 0.0
        self.trauma = 0.0
        self.hitstop_frames = 0
        self.death_slowmo_timer = 0.0
        self.lives = int(CONFIG["RUN_LIVES"])

        self.rings: List[Dict[str, Any]] = []
        self.popups: List[Dict[str, Any]] = []
        self.particles: List[Dict[str, Any]] = []
        self.slashes: List[Dict[str, Any]] = []
        self.slimes: List[Dict[str, Any]] = []

        self.ai_positions: List[np.ndarray] = []
        self.ai_velocities: List[np.ndarray] = []
        self.ai_trails: List[List[np.ndarray]] = []
        self.ai_marks: List[int] = []
        self.ai_trap_frames: List[int] = []
        self.ai_stun_frames: List[int] = []
        self.ai_exec_frames: List[int] = []
        self.ai_flash_frames: List[int] = []
        self.pending_spawns: List[Dict[str, Any]] = []

        self.spitters: List[Dict[str, Any]] = []
        self.projectiles: List[Dict[str, Any]] = []

        self.wave = 1
        self.wave_flash = 0.0
        self.ai_spawn_timer = CONFIG["AI_SPAWN_INTERVAL"]
        self.game_over = False
        self.flash = 0.0
        self.practice_mode = False
        self._finalized = False

        self.paused = False
        self.pause_sel = 0
        self.gameover_sel = 0
        if getattr(self, "gameover_sel_x", None) is not None:
            self.gameover_sel_x.snap(float(self._gameover_options_rects()[0][0]))

        self._reset_esc_state()

        self.stage_progress = 0
        self.hint_timer = 0.0
        self.stage_complete_timer = 0.0
        self.stage_complete_flash = 0.0

        self.energy_tween.snap(CONFIG["MAX_ENERGY"])
        self.swap_cd_tween.snap(1.0)
        self.chain_bar_tween.snap(1.0)
        self.gameover_anim.snap(0.0)
        self.stage_complete_anim.snap(0.0)

        if self.mode == "TRAINING":
            n = CONFIG["STAGE_ENEMIES"][self.stage - 1]
            for _ in range(n):
                self._spawn_enemy_away()
            self.hint_timer = CONFIG["TRAINING_HINT_DURATION"]
        else:
            for _ in range(max(1, int(CONFIG["RUN_START_ENEMIES"]))):
                self._spawn_enemy_away()

    def _wave_cfg(self, wave: int) -> dict:
        tbl = CONFIG["WAVE_TABLE"]
        if not tbl:
            return {"dur": CONFIG["WAVE_DURATION"], "spawn": CONFIG["AI_SPAWN_INTERVAL"],
                    "batch": 1, "max": CONFIG["AI_MAX_COUNT"], "spitter": 0}
        i = max(0, wave - 1)
        if i >= len(tbl):
            last = dict(tbl[-1])
            over = i - len(tbl) + 1
            last["spawn"] = max(2.0, last["spawn"] * (0.90 ** over))
            last["max"] = min(12, last["max"] + over)
            last["batch"] = min(3, last["batch"] + over // 3)
            base_iv = float(last.get("spit_interval") or CONFIG["SPITTER_INTERVAL"])
            base_sp = float(last.get("spit_speed") or CONFIG["SPITTER_PROJ_SPEED"])
            last["spit_interval"] = max(CONFIG["SPITTER_INTERVAL_MIN"],
                                        base_iv * (0.95 ** over))
            last["spit_speed"] = min(CONFIG["SPITTER_SPEED_MAX"],
                                     base_sp + 12.0 * over)
            return last
        return tbl[i]

    def _spit_interval(self, wave: int) -> float:
        v = self._wave_cfg(wave).get("spit_interval")
        return float(v) if v else float(CONFIG["SPITTER_INTERVAL"])

    def _spit_speed(self, wave: int) -> float:
        v = self._wave_cfg(wave).get("spit_speed")
        return float(v) if v else float(CONFIG["SPITTER_PROJ_SPEED"])

    def _next_wave_in(self) -> float:
        tbl = CONFIG["WAVE_TABLE"]
        if not tbl:
            return CONFIG["WAVE_DURATION"] - (self.t % CONFIG["WAVE_DURATION"])
        acc = 0.0
        for row in tbl:
            acc += float(row["dur"])
            if self.t < acc:
                return acc - self.t
        d = float(tbl[-1]["dur"])
        return d - ((self.t - acc) % d)

    def _wave_intro_line(self) -> str:
        wc = self._wave_cfg(self.wave)
        bits = []
        pv = self._wave_cfg(self.wave - 1) if self.wave > 1 else None
        mx = int(wc.get("max", CONFIG["AI_MAX_COUNT"]))
        if pv is None:
            bits.append((f"敌人上限 {mx}" if self.use_cjk else f"ENEMY CAP {mx}"))
        elif mx > int(pv.get("max", 0)):
            bits.append((f"敌人上限 {mx}" if self.use_cjk else f"ENEMY CAP {mx}"))
        sp = min(int(wc.get("spitter", 0)), CONFIG["SPITTER_MAX"])
        sp_prev = min(int(pv.get("spitter", 0)), CONFIG["SPITTER_MAX"]) if pv else 0
        if sp > sp_prev:
            bits.append((f"新增喷浆口 ×{sp - sp_prev}" if self.use_cjk
                         else f"+{sp - sp_prev} SPITTER"))
        iv = self._spit_interval(self.wave)
        iv_prev = self._spit_interval(self.wave - 1) if self.wave > 1 else iv
        if sp > 0 and iv < iv_prev - 1e-6:
            bits.append("炮台攻速 ↑" if self.use_cjk else "FIRE RATE UP")
        spd = self._spit_speed(self.wave)
        spd_prev = self._spit_speed(self.wave - 1) if self.wave > 1 else spd
        if sp > 0 and spd > spd_prev + 1e-6:
            bits.append("弹速 ↑" if self.use_cjk else "BOLT SPEED UP")
        bt = int(wc.get("batch", 1))
        if bt > 1 and (pv is None or bt > int(pv.get("batch", 1))):
            bits.append("成组出现" if self.use_cjk else "IN GROUPS")
        return "   ·   ".join(bits) if bits else ("" if self.use_cjk else "")

    def _wave_of_time(self, t: float) -> int:
        tbl = CONFIG["WAVE_TABLE"]
        if not tbl:
            return int(t / CONFIG["WAVE_DURATION"]) + 1
        acc = 0.0
        for i, row in enumerate(tbl):
            acc += float(row["dur"])
            if t < acc:
                return i + 1
        extra = int((t - acc) // float(tbl[-1]["dur"])) + 1
        return len(tbl) + extra

    def _spawn_enemy_away(self) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        pos = np.array([W / 2, H / 2], dtype=np.float64)
        for _ in range(60):
            ang = float(np.random.uniform(0, 2 * np.pi))
            r = float(np.random.uniform(280, 380))
            pos = np.array([W / 2 + math.cos(ang) * r, H / 2 + math.sin(ang) * r])
            pos[0] = float(np.clip(pos[0], 60, W - 60))
            pos[1] = float(np.clip(pos[1], 60, H - 60))
            if vlen(pos - self.player_pos) > 260:
                break
        self.ai_positions.append(pos)
        self.ai_velocities.append(np.zeros(2))
        self.ai_trails.append([])
        self.ai_marks.append(0)
        self.ai_trap_frames.append(0)
        self.ai_stun_frames.append(0)
        self.ai_exec_frames.append(0)
        self.ai_flash_frames.append(0)

    def _in_slime_mask(self, pts: np.ndarray) -> np.ndarray:
        if not self.slimes or len(pts) == 0:
            return np.zeros(len(pts), dtype=bool)
        mask = np.zeros(len(pts), dtype=bool)
        for s in self.slimes:
            d = pts - s["pos"]
            r2 = s["radius"] ** 2
            mask |= (d * d).sum(axis=1) < r2
        return mask

    def _pick_spawn_pos(self) -> np.ndarray:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        edge = int(np.random.randint(4)); m = 44
        if edge == 0: return np.array([np.random.uniform(m, W - m), m], dtype=np.float64)
        if edge == 1: return np.array([np.random.uniform(m, W - m), H - m], dtype=np.float64)
        if edge == 2: return np.array([m, np.random.uniform(m, H - m)], dtype=np.float64)
        return np.array([W - m, np.random.uniform(m, H - m)], dtype=np.float64)

    def _burst(self, pos, color, count=20, speed=260.0, life=0.55) -> None:
        for _ in range(count):
            ang = float(np.random.uniform(0, 2 * np.pi))
            spd = float(np.random.uniform(0.25, 1.0)) * speed
            self.particles.append({
                "pos": pos.copy(), "vel": np.array([math.cos(ang), math.sin(ang)]) * spd,
                "life": life, "maxlife": life, "color": color,
            })

    def _ring(self, pos, max_r, color, width=2, life=0.5) -> None:
        self.rings.append({"pos": pos.copy(), "max_r": max_r, "color": color,
                           "width": width, "life": life, "maxlife": life})

    def _popup(self, pos, text, color=(255, 255, 255)) -> None:
        self.popups.append({"pos": pos.copy(), "text": text, "color": color,
                            "life": 0.8, "maxlife": 0.8})

    def _slash(self, pos, direction) -> None:
        self.slashes.append({"pos": pos.copy(), "dir": direction.copy(),
                             "life": 0.30, "maxlife": 0.30})

    def _play(self, snd) -> None:
        if self.snd_ok:
            try: snd.play()
            except Exception: pass

    def try_dash(self) -> bool:
        if self.player_state in ("DASHING", "RECOVERY"): return False
        free = (self.mode == "TRAINING" and self.stage == 4)
        is_cancel = (self.player_state == "BACKSWING")
        cancel_free = (is_cancel and CONFIG["DASH_CANCEL_FREE"]
                       and self.free_cancel_left > 0)
        if not free and not cancel_free and self.energy < CONFIG["DASH_COST"]:
            if self.no_energy_cd <= 0:
                self.no_energy_cd = CONFIG["NO_ENERGY_HINT_CD"]
                self._popup(self.player_pos + np.array([0, -34]),
                            "无能量" if self.use_cjk else "NO ENERGY",
                            CONFIG["C_THREAT"])
            return False

        if self._shadows_on():
            if len(self.shadows) >= CONFIG["SHADOW_MAX"]:
                self.shadows.pop(0)
            self.shadows.append({
                "pos": self.player_pos.copy(),
                "drift_dir": -self.aim_dir.copy(),
                "frames_left": CONFIG["SHADOW_LIFE_FRAMES"],
            })

        if not free and not cancel_free:
            self.energy -= CONFIG["DASH_COST"]
        if cancel_free:
            self.free_cancel_left -= 1
        else:
            self.free_cancel_left = int(CONFIG["DASH_CANCEL_FREE_CHAIN"])
        self._update_aim()
        self.dash_dir = self.aim_dir.copy()
        self.dash_total_frames = CONFIG["DASH_FRAMES"]
        self.dash_hits = set()
        self.phase_grace_indices = set()
        self.phase_grace_timer = 0

        if is_cancel:
            self.dash_total_frames = int(CONFIG["DASH_FRAMES"] * CONFIG["CANCEL_BONUS_MULT"])
            self.iframe_frames = CONFIG["CANCEL_IFRAME_FRAMES"]
            self.did_cancel_this_backswing = True
            self.consecutive_cancels += 1
            if self.mode == "RUN" and "cancel" not in self.discovered:
                self.discovered.add("cancel")
                self._popup(self.player_pos + np.array([0, -52]),
                            "取消后摇" if self.use_cjk else "CANCEL", self.pcol)
            self._burst(self.player_pos, self.pcol, 12, 220)
            self._ring(self.player_pos, 44, self.pcol, 2, 0.3)
            self._play(self.snd_cancel)
            self._add_hitstop(CONFIG["HITSTOP_CANCEL"])
            if self.mode == "TRAINING" and self.stage == 4:
                self.stage_progress = self.consecutive_cancels
                self._check_stage_goal()

        self.player_state = "DASHING"
        self.state_frame = 0
        return True

    def try_swap(self) -> bool:
        if not self._shadows_on(): return False
        if self.swap_cd_frames > 0: return False

        if not self.shadows:
            self.swap_cd_frames = CONFIG["SWAP_EMPTY_CD_FRAMES"]
            self._ring(self.player_pos, 44, CONFIG["G_60"], 1, 0.3)
            self._popup(self.player_pos + np.array([0, -30]),
                        "空放" if self.use_cjk else "whiff", CONFIG["G_60"])
            return True

        mx, my = self.mouse_pos()
        mouse = np.array([mx, my], dtype=np.float64)
        best_i = min(range(len(self.shadows)),
                     key=lambda i: vlen(self.shadows[i]["pos"] - mouse))
        target = self.shadows[best_i]
        old_pos = self.player_pos.copy()
        new_pos = target["pos"].copy()

        if self.fx_swap_ghost:
            self.afterimages.append({
                "pos": old_pos.copy(),
                "life": float(self.pskin["ai_life"]) * 2.2,
                "maxlife": float(self.pskin["ai_life"]) * 2.2})
            if self.pskin.get("poem"):
                try:
                    d = new_pos - old_pos
                    ln = vlen(d)
                    dv = d / ln if ln > 1e-6 else self.aim_dir
                except Exception:
                    dv = self.aim_dir
                self._spawn_sword_qi(dv, 2, 1.35, 0.46, old_pos)
        self.player_pos = new_pos
        self.player_vel = np.zeros(2)
        target["pos"] = old_pos

        perfect = False
        if self._perfect_on():
            for i, ap in enumerate(self.ai_positions):
                to_p = old_pos - ap
                dn = vlen(to_p)
                if dn < 1e-3: continue
                to_p_n = to_p / dn
                if dn < CONFIG["PERFECT_THREAT_DIST"] and \
                   float(np.dot(self.ai_velocities[i], to_p_n)) > 15.0:
                    perfect = True; break

        self._ring(old_pos, CONFIG["SWAP_IMPACT_RADIUS"], self.pcol, 3, 0.5)
        self._ring(new_pos, CONFIG["SWAP_IMPACT_RADIUS"], self.pcol, 3, 0.5)
        self._burst(old_pos, self.pcol, 10, 200)
        self._burst(new_pos, self.pcol, 10, 200)

        trapped_any = False
        for i, ap in enumerate(self.ai_positions):
            d1 = vlen(ap - old_pos)
            d2 = vlen(ap - new_pos)
            if d1 < CONFIG["SWAP_IMPACT_RADIUS"] or d2 < CONFIG["SWAP_IMPACT_RADIUS"]:
                self.ai_trap_frames[i] = max(self.ai_trap_frames[i], CONFIG["SWAP_TRAP_FRAMES"])
                trapped_any = True

        self.swap_cd_frames = CONFIG["SWAP_CD_FRAMES"]

        if self.player_state in ("BACKSWING", "RECOVERY"):
            self.iframe_frames = max(self.iframe_frames, CONFIG["CANCEL_IFRAME_FRAMES"])
        self.player_state = "IDLE"
        self.state_frame = 0
        self.did_cancel_this_backswing = False

        if trapped_any and self.mode == "TRAINING" and self.stage == 3:
            self.stage_progress += 1
            self._check_stage_goal()

        if perfect:
            if self.mode == "RUN" and "perfect" not in self.discovered:
                self.discovered.add("perfect")
                self._popup(self.player_pos + np.array([0, -72]),
                            "完美换位" if self.use_cjk else "PERFECT SWAP", self.pcol)
            self.bullet_time_frames = CONFIG["PERFECT_BULLET_FRAMES"]
            self.invert_frames = 1
            self.perfect_count += 1
            self.score_perfect += CONFIG["PERFECT_SWAP_SCORE"]
            for i in [j for j in range(len(self.ai_marks)) if self.ai_marks[j] > 0]:
                self._do_detonate(i)
            self._ring(self.player_pos, 220, (255, 255, 255), 3, 0.6)
            self._popup(self.player_pos + np.array([0, -46]),
                        "见影" if self.use_cjk else "PERFECT", (255, 255, 255))
            self._add_trauma(0.7)
            self._add_hitstop(CONFIG["HITSTOP_PERFECT"])
            if self.mode == "TRAINING" and self.stage == 5:
                self.stage_progress += 1
                self._check_stage_goal()
        return True

    def _do_detonate(self, i: int) -> None:
        if i >= len(self.ai_positions): return
        pos = self.ai_positions[i].copy()
        self.ai_marks[i] = 0
        self.detonate_count += 1
        self.energy = min(CONFIG["MAX_ENERGY"],
                          self.energy + CONFIG["DETONATE_ENERGY_GAIN"])

        kb = pos - self.player_pos
        kn = vlen(kb)
        if kn > 1e-3: kb = kb / kn
        else: kb = np.array([1.0, 0.0])
        self.ai_velocities[i] = kb * CONFIG["DETONATE_KNOCKBACK"]
        self.ai_stun_frames[i] = CONFIG["DETONATE_STUN_FRAMES"]
        self.ai_exec_frames[i] = (CONFIG["DETONATE_STUN_FRAMES"]
                                  + CONFIG["DETONATE_EXEC_FRAMES"])
        self.ai_flash_frames[i] = 6

        if self.chain_timer <= 0: self.chain_count = 0
        self.chain_count += 1
        self.chain_timer = CONFIG["CHAIN_WINDOW_FRAMES"]
        self.chain_max = max(self.chain_max, self.chain_count)
        if self.mode == "RUN" and self.chain_count >= 2 and "chain" not in self.discovered:
            self.discovered.add("chain")
            self._popup(pos + np.array([0, -52]),
                        f"连锁 ×{self.chain_count}" if self.use_cjk
                        else f"CHAIN x{self.chain_count}", self.pcol)

        idx = min(self.chain_count - 1, len(CONFIG["CHAIN_MULTS"]) - 1)
        mult = CONFIG["CHAIN_MULTS"][idx]
        gained = int(CONFIG["DETONATE_BASE_SCORE"] * mult)
        self.score_detonate += gained

        self.slimes.append({"pos": pos, "age": 0.0,
                            "life": CONFIG["DETONATE_SLIME_FRAMES"] / 60.0,
                            "radius": CONFIG["DETONATE_RADIUS"], "is_burst": True})

        self._burst(pos, CONFIG["C_THREAT"], 24, 400)
        self._burst(pos, (255, 255, 255), 10, 300)
        self._ring(pos, CONFIG["DETONATE_RADIUS"], CONFIG["C_THREAT"], 3, 0.6)
        mult_str = f"x{mult}" if mult > 1 else ""
        self._popup(pos + np.array([0, -30]), f"+{gained} {mult_str}".strip(), CONFIG["C_THREAT"])
        self._play(self.snd_detonate)
        self._add_trauma(0.5)
        self._add_hitstop(CONFIG["HITSTOP_DETONATE"])
        if self.fx_detonate_self:
            self._ring(self.player_pos, 56, self.pcol, 2, 0.45)
            self._burst(self.player_pos, self.pcol, 14, 260)
            self._burst(self.player_pos, self.pskin.get("ink", (72, 92, 130)), 24, 330)
            if self.pskin.get("poem"):
                self._spawn_sword_qi(self.dash_dir, 3, 1.15, 0.42)
            if self.fx_poem and self.pskin.get("poem"):
                self._spawn_poem(self.player_pos, 3)

        if self.mode == "TRAINING" and self.stage == 2:
            self.stage_progress += 1
            self._check_stage_goal()

    def _check_dash_hits(self, prev_pos, curr_pos) -> None:
        if not self._marks_on(): return
        for i in range(len(self.ai_positions)):
            if i in self.dash_hits: continue
            p = self.ai_positions[i]
            AB = curr_pos - prev_pos; AP = p - prev_pos
            AB2 = float(AB[0] * AB[0] + AB[1] * AB[1])
            if AB2 < 1e-6:
                dist = vlen(AP)
            else:
                t = max(0.0, min(1.0, float(AP[0] * AB[0] + AP[1] * AB[1]) / AB2))
                closest = prev_pos + AB * t
                dist = vlen(p - closest)
            if dist < CONFIG["MARK_HIT_RADIUS"]:
                self.dash_hits.add(i)
                self.ai_flash_frames[i] = 8
                self._slash(p, self.dash_dir)
                if self.ai_marks[i] > 0:
                    self._do_detonate(i)
                else:
                    self.ai_marks[i] = CONFIG["MARK_LIFE_FRAMES"]
                    self._ring(p, 34, CONFIG["C_MARK"], 2, 0.35)
                    self._popup(p + np.array([0, -24]),
                                "标记" if self.use_cjk else "MARK", CONFIG["C_MARK"])

    def _kill_ai(self, i: int) -> None:
        pos = self.ai_positions[i].copy()
        self.score_kill += CONFIG["KILL_SCORE"]
        self.kill_count += 1
        self._burst(pos, CONFIG["C_THREAT"], 22, 340)
        self._ring(pos, 80, CONFIG["C_THREAT"], 3, 0.5)
        self._popup(pos + np.array([0, -30]), f"+{CONFIG['KILL_SCORE']}", CONFIG["C_THREAT"])
        self.ai_positions.pop(i); self.ai_velocities.pop(i); self.ai_trails.pop(i)
        self.ai_marks.pop(i); self.ai_trap_frames.pop(i); self.ai_stun_frames.pop(i)
        self.ai_exec_frames.pop(i); self.ai_flash_frames.pop(i)
        def fix(s: Set[int]) -> Set[int]:
            return {j - 1 if j > i else j for j in s if j != i}
        self.dash_hits = fix(self.dash_hits)
        self.phase_grace_indices = fix(self.phase_grace_indices)

    def _death_collision(self, arr: np.ndarray) -> bool:
        if len(arr) == 0: return False
        if self.player_state == "DASHING" and CONFIG["DASH_PHASE_ON_MARK"]:
            exempt = self.dash_hits
        elif self.phase_grace_timer > 0:
            exempt = self.phase_grace_indices
        else:
            exempt = set()
        exempt |= {i for i in range(len(self.ai_trap_frames))
                   if self.ai_trap_frames[i] > 0 or self.ai_exec_frames[i] > 0}

        prev = self.player_prev_pos
        curr = self.player_pos
        AB = curr - prev
        AB2 = float(AB[0] * AB[0] + AB[1] * AB[1])
        N = len(arr)
        DR = CONFIG["DEATH_RADIUS"]

        if AB2 < 1e-6:
            for i in range(N):
                if i in exempt: continue
                if vlen(arr[i] - curr) < DR:
                    return True
            return False

        AP = arr - prev
        t = np.clip((AP[:, 0] * AB[0] + AP[:, 1] * AB[1]) / AB2, 0.0, 1.0)
        closest = prev[None, :] + t[:, None] * AB[None, :]
        dist = np.linalg.norm(arr - closest, axis=1)
        for i in range(N):
            if i in exempt: continue
            if dist[i] < DR:
                return True
        return False

    def _check_stage_goal(self) -> None:
        if self.mode != "TRAINING": return
        if self.stage_complete_timer > 0: return
        goal = CONFIG["STAGE_GOALS"][self.stage - 1]
        if self.stage_progress >= goal:
            self.stage_complete_timer = CONFIG["TRAINING_COMPLETE_HOLD"]
            self.stage_complete_flash = 1.0
            self.stage_complete_anim.snap(0.0)
            self.stage_complete_anim.set_target(1.0, CONFIG["UI_TWEEN_SLOW"], ease_out_back)
            self._play(self.snd_complete)
            self._ring(self.player_pos, 240, self.pcol, 3, 1.0)
            self._burst(self.player_pos, self.pcol, 30, 400)
            self._start_fade()

            st = self.stage
            sd = self.save_data
            new_unlocked = 5 if st >= 5 else (st + 1)
            sd["training_unlocked_stage"] = max(int(sd["training_unlocked_stage"]), new_unlocked)
            if st >= 5:
                sd["training_done"] = True
            save_now(CONFIG["SAVE_PATH"], sd)

    def _die(self, source: str = "threat") -> None:
        if self.mode == "TRAINING":
            self._on_stage_fail()
            return
        if self.lives > 1:
            self.lives -= 1
            self._respawn()
            return
        self.game_over = True
        self.flash = 1.0
        self._add_trauma(1.0)
        self.death_slowmo_timer = CONFIG["DEATH_SLOWMO_DURATION"]
        self.gameover_anim.snap(0.0)
        if source == "projectile":
            self._burst(self.player_pos, CONFIG["C_SPITTER"], 24, 300)
        else:
            self._burst(self.player_pos, CONFIG["C_THREAT"], 40, 420)
            self._burst(self.player_pos, (255, 255, 255), 12, 300)
        self._finalize_run()

    def _respawn(self) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        R = float(CONFIG["RESPAWN_CLEAR_RADIUS"])

        self.player_pos = np.array([W / 2, H / 2], dtype=np.float64)
        self.player_prev_pos = self.player_pos.copy()
        self.player_vel = np.zeros(2)
        self.player_state = "IDLE"
        self.state_frame = 0
        self.dash_hits = set()
        self.phase_grace_indices = set()
        self.phase_grace_timer = 0
        self.buf_dash = 0
        self.buf_swap = 0
        self.shadows = []

        self.iframe_frames = int(CONFIG["RESPAWN_IFRAMES"])
        self.energy = CONFIG["MAX_ENERGY"]
        self.chain_count = 0
        self.chain_timer = 0

        cleared = 0
        keep = [i for i, ap in enumerate(self.ai_positions)
                if vlen(ap - self.player_pos) > R]
        for i in reversed(range(len(self.ai_positions))):
            if i not in keep:
                pos = self.ai_positions[i]
                self._burst(pos, CONFIG["C_THREAT"], 14, 260)
                self._ring(pos, 60, CONFIG["C_THREAT"], 2, 0.4)
                self.ai_positions.pop(i); self.ai_velocities.pop(i)
                self.ai_trails.pop(i); self.ai_marks.pop(i)
                self.ai_trap_frames.pop(i); self.ai_stun_frames.pop(i)
                self.ai_exec_frames.pop(i); self.ai_flash_frames.pop(i)
                cleared += 1
        self.pending_spawns = [sp for sp in self.pending_spawns
                               if vlen(sp["pos"] - self.player_pos) > R]
        self.projectiles = [p for p in self.projectiles
                            if vlen(p["pos"] - self.player_pos) > R]

        self.flash = 0.8
        self._add_trauma(0.8)
        self._add_hitstop(int(CONFIG["RESPAWN_HITSTOP"]))
        self.death_slowmo_timer = float(CONFIG["RESPAWN_SLOWMO"])
        self._ring(self.player_pos, 200, self.pcol, 3, 0.7)
        self._burst(self.player_pos, self.pcol, 30, 380)
        self._popup(self.player_pos + np.array([0, -46]),
                    f"{self.lives}" if not self.use_cjk else f"剩 {self.lives} 命",
                    CONFIG["C_PLAYER"])

    def _on_stage_fail(self) -> None:
        self.stage_complete_flash = 0.5
        self._burst(self.player_pos, CONFIG["C_THREAT"], 24, 300)
        self._start_fade()
        self._setup_game()

    def _open_esc(self) -> None:
        if self.mode == "MENU":
            self.esc_open = True
            self.esc_page = "ROOT"
            self.esc_sel = 0
            self.esc_sub_sel = 0
            self.c_hold_frames = 0
            self.c_hold2_frames = 0
            self.esc_anim.set_target(1.0, 0.18, ease_out_cubic)
        elif not self.game_over:
            self.esc_open = True
            self.esc_page = "ROOT"
            self.esc_sel = 0
            self.esc_sub_sel = 0
            self.paused = False
            self.c_hold_frames = 0
            self.c_hold2_frames = 0
            self.esc_anim.set_target(1.0, 0.18, ease_out_cubic)
        else:
            self._back_to_menu()

    def _esc_back(self) -> None:
        self.c_hold_frames = 0
        self.c_hold2_frames = 0
        if self.esc_page == "ROOT":
            self.esc_anim.set_target(0.0, 0.12, ease_out_cubic)
        elif self.esc_page in ("MECHANICS", "SETTINGS"):
            self.esc_page = "ROOT"
            self.esc_sel = 0
            self.esc_sub_sel = 0
        elif self.esc_page == "CLEAR_CONFIRM":
            self.esc_page = "SETTINGS"
            self.esc_sub_sel = 0

    def _esc_root_options(self) -> List[Tuple[str, str]]:
        if self.mode == "MENU":
            return [
                (self.S["mech"], "mech"),
                (self.S["settings"], "settings"),
                (self.S["quit_game"], "quit"),
            ]
        else:
            return [
                (self.S["continue"], "resume"),
                (self.S["restart_run"] if self.mode == "RUN" else self.S["restart_stage"], "restart"),
                (self.S["mech"], "mech"),
                (self.S["settings"], "settings"),
                (self.S["exit_run"], "menu"),
            ]

    def _esc_confirm_root(self) -> None:
        opts = self._esc_root_options()
        if self.esc_sel >= len(opts): return
        _, action = opts[self.esc_sel]
        if action == "resume":
            self.esc_anim.set_target(0.0, 0.12, ease_out_cubic)
        elif action == "restart":
            if self.mode == "RUN" and not self._finalized:
                self._finalize_run()
            self.esc_open = False
            self.esc_anim.snap(0.0)
            self._start_fade()
            self._setup_game()
        elif action == "mech":
            self.esc_page = "MECHANICS"
            self.esc_sel = 0
            self.esc_mech_tab = 0
            self.esc_mech_scroll = 0.0
            self.esc_mech_fade = CONFIG["MECH_TAB_FADE"]
        elif action == "settings":
            self.esc_page = "SETTINGS"
            self.esc_sub_sel = 0
        elif action == "menu":
            self._back_to_menu()
        elif action == "quit":
            self._quit_program()

    def _settings_count(self) -> int:
        return len(self._esc_settings_rects())

    def _settings_adjust(self, delta: int) -> None:
        if self.esc_sub_sel == 1:
            levels = [0.0, 1.0, 1.5, 2.0, 2.5, 3.0]
            cur = float(CONFIG.get("RENDER_SCALE_PRESET", 0.0) or 0.0)
            try:
                idx = levels.index(round(cur, 1))
            except ValueError:
                idx = 0
            idx = max(0, min(len(levels) - 1, idx + delta))
            new_s = levels[idx]
            if new_s != cur:
                CONFIG["RENDER_SCALE_PRESET"] = new_s
                self._apply_fullscreen(self.fullscreen)
        elif self.esc_sub_sel == 2:
            levels = [0.0, 0.5, 1.0]
            try:
                idx = levels.index(round(self.shake_level, 1))
            except ValueError:
                idx = 2
            idx = max(0, min(2, idx + delta))
            self.shake_level = levels[idx]
        elif self.esc_sub_sel == 3:
            sizes = [CONFIG["FONT_BODY_STD"], CONFIG["FONT_BODY_LARGE"]]
            try:
                idx = sizes.index(self.body_size)
            except ValueError:
                idx = 0
            idx = max(0, min(len(sizes) - 1, idx + delta))
            new_size = sizes[idx]
            if new_size != self.body_size:
                self.body_size = new_size
                self.save_data["body_size"] = new_size
                self._rebuild_body_font()
        elif self.esc_sub_sel == 4:
            langs = ["en", "zh"]
            if not getattr(self, "zh_available", False):
                return
            try:
                idx = langs.index(self.lang)
            except ValueError:
                idx = 0
            idx = (idx + delta) % len(langs)
            if langs[idx] != self.lang:
                self._apply_lang(langs[idx])
                self._write_save()

    def _settings_confirm(self) -> None:
        last = len(self._esc_settings_rects()) - 1
        if self.esc_sub_sel == 0:
            self._apply_fullscreen(not self.fullscreen)
        elif self.esc_sub_sel == last:
            self.esc_page = "ROOT"
            self.esc_sel = 0
            self.esc_sub_sel = 0
            self.c_hold_frames = 0

    def _on_esc_key(self, e) -> None:
        if self.esc_page == "ROOT":
            n = len(self._esc_root_options())
            if e.key == pygame.K_UP:
                self.esc_sel = (self.esc_sel - 1) % n
            elif e.key == pygame.K_DOWN:
                self.esc_sel = (self.esc_sel + 1) % n
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._esc_confirm_root()
        elif self.esc_page == "SETTINGS":
            n = self._settings_count()
            if e.key == pygame.K_UP:
                self.esc_sub_sel = (self.esc_sub_sel - 1) % n
                self.c_hold_frames = 0
            elif e.key == pygame.K_DOWN:
                self.esc_sub_sel = (self.esc_sub_sel + 1) % n
                self.c_hold_frames = 0
            elif e.key == pygame.K_LEFT:
                self._settings_adjust(-1)
            elif e.key == pygame.K_RIGHT:
                self._settings_adjust(1)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._settings_confirm()
        elif self.esc_page == "MECHANICS":
            tabs = len(self.S["mech_tabs"])
            if e.key == pygame.K_UP:
                self.esc_mech_tab = (self.esc_mech_tab - 1) % tabs
                self.esc_mech_scroll = 0.0
                self.esc_mech_fade = CONFIG["MECH_TAB_FADE"]
            elif e.key == pygame.K_DOWN:
                self.esc_mech_tab = (self.esc_mech_tab + 1) % tabs
                self.esc_mech_scroll = 0.0
                self.esc_mech_fade = CONFIG["MECH_TAB_FADE"]

    def _on_esc_click(self, pos) -> None:
        if self.esc_page == "ROOT":
            rects = self._esc_root_rects()
            for i, r in enumerate(rects):
                if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                    self.esc_sel = i
                    self._esc_confirm_root()
                    return
        elif self.esc_page == "SETTINGS":
            rects = self._esc_settings_rects()
            for i, r in enumerate(rects):
                if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                    self.esc_sub_sel = i
                    last = len(rects) - 1
                    if i == 0 or i == last:
                        self._settings_confirm()
                    elif i in (1, 2, 3, 4):
                        self._settings_adjust(-1 if pos[0] < r[0] + r[2] // 2 else 1)
                    return
        elif self.esc_page == "MECHANICS":
            for i, r in enumerate(self._esc_mech_tab_rects()):
                if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                    if self.esc_mech_tab != i:
                        self.esc_mech_tab = i
                        self.esc_mech_scroll = 0.0
                        self.esc_mech_fade = CONFIG["MECH_TAB_FADE"]
                    return

    def _sync_esc_hover(self, pos) -> None:
        if self.esc_page == "ROOT":
            rects = self._esc_root_rects()
            for i, r in enumerate(rects):
                if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                    self.esc_sel = i; return
        elif self.esc_page == "SETTINGS":
            rects = self._esc_settings_rects()
            for i, r in enumerate(rects):
                if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                    if self.esc_sub_sel != i:
                        self.esc_sub_sel = i
                        self.c_hold_frames = 0
                    return

    def _esc_root_rects(self) -> List[Tuple[int,int,int,int]]:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        opts = self._esc_root_options()
        n = len(opts)
        cx = W // 2
        start_y = H // 2 - (n * 50) // 2
        return [(cx - 200, start_y + i * 50, 400, 42) for i in range(n)]

    def _esc_has_clear(self) -> bool:
        return self.mode == "MENU"

    def _esc_settings_geom(self):
        H = CONFIG["HEIGHT"]
        n = 7 if self._esc_has_clear() else 6
        top = 172
        bottom_limit = H - 62
        avail = max(120, bottom_limit - top)
        gap = 10
        back_gap = 14
        row_h = min(48, max(30, (avail - back_gap - (n - 1) * gap) // n))
        total = n * row_h + (n - 1) * gap + back_gap
        start_y = int(top + max(0, (avail - total) // 2))
        return n, start_y, row_h, gap, back_gap

    def _esc_settings_rects(self) -> List[Tuple[int,int,int,int]]:
        W = CONFIG["WIDTH"]
        cx = W // 2
        n, start_y, row_h, gap, back_gap = self._esc_settings_geom()
        out = [(cx - 300, start_y + i * (row_h + gap), 600, row_h) for i in range(n - 1)]
        by = start_y + (n - 1) * (row_h + gap) + back_gap
        out.append((cx - 200, by, 400, min(row_h, 42)))
        return out

    def _esc_mech_tab_rects(self) -> List[Tuple[int,int,int,int]]:
        tabs = self.S["mech_tabs"]
        n = len(tabs)
        x = 80
        y0 = 160
        return [(x, y0 + i * 56, 200, 44) for i in range(n)]

    def _mech_ctrl_geom(self):
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        cx0 = 360
        cw = W - cx0 - 60
        cy0 = 150
        row_h = 40
        gap = 6
        bottom = H - 150
        return cx0, cw, cy0, row_h, gap, bottom

    def _mech_ctrl_rects(self) -> List[Tuple[int,int,int,int]]:
        cx0, cw, cy0, row_h, gap, _b = self._mech_ctrl_geom()
        n = len(self.S["ctrl_rows"])
        return [(cx0, cy0 + i * (row_h + gap), cw, row_h) for i in range(n)]

    def _update_esc_hover(self) -> None:
        if not self.esc_open or self.esc_page != "MECHANICS" or self.esc_mech_tab != 1:
            self.esc_ctrl_hover = -1
            return
        mx, my = self.mouse_pos()
        cy = my + self.esc_mech_scroll
        self.esc_ctrl_hover = -1
        for i, r in enumerate(self._mech_ctrl_rects()):
            if r[0] <= mx <= r[0]+r[2] and r[1] <= cy <= r[1]+r[3]:
                self.esc_ctrl_hover = -1 if self._ctrl_row_locked(i) else i
                return

    def _draw_mech_controls(self, cx0: int, cw: int, H: int, a: float, y_off: int) -> None:
        rows = self.S["ctrl_rows"]
        rects = self._mech_ctrl_rects()
        hov = self.esc_ctrl_hover
        btn_w = 150
        scr = int(self.esc_mech_scroll)
        _cx, _cw, _cy0, _rh, _g, bottom = self._mech_ctrl_geom()
        for i, (key, word, _desc) in enumerate(rows):
            r = rects[i]
            ry = r[1] - scr + y_off
            if ry + r[3] > bottom + y_off or ry < 140 + y_off:
                continue
            active = (i == hov)
            locked = self._ctrl_row_locked(i)
            if locked:
                lk = max(11.0, r[3] * 0.42)
                self._draw_padlock(r[0] + 18, ry + (r[3] - lk * 1.32) / 2, lk,
                                   CONFIG["G_40"], a)
                req = CTRL_STAGE_REQ[i] if i < len(CTRL_STAGE_REQ) else 1
                lt = self.f_body.render(self._mech_lock_text(req), True,
                                        CONFIG["G_40"]).copy()
                lt.set_alpha(int(255 * a))
                self.screen.blit(lt, (r[0] + 18 + int(lk * 1.6),
                                      ry + (r[3] - lt.get_height()) // 2))
                continue
            if active:
                pygame.draw.rect(self.screen, CONFIG["G_20"], (r[0], ry, r[2], r[3]))
            kc = CONFIG["C_PLAYER"] if active else CONFIG["G_80"]
            ks = self.f_body.render(key, True, kc).copy()
            ks.set_alpha(int(255 * a))
            self.screen.blit(ks, (r[0] + 18, ry + (r[3] - ks.get_height()) // 2))
            br = (r[0] + r[2] - btn_w - 4, ry + 5, btn_w, r[3] - 10)
            pygame.draw.rect(self.screen, CONFIG["G_20"], br)
            bc = CONFIG["C_PLAYER"] if active else CONFIG["G_40"]
            pygame.draw.rect(self.screen, bc, br, 2 if active else 1)
            ws = self.f_med.render(word, True, kc).copy()
            ws.set_alpha(int(255 * a))
            self.screen.blit(ws, ws.get_rect(center=(br[0] + br[2] // 2, br[1] + br[3] // 2)))
        if 0 <= hov < len(rows):
            dy = bottom + 16 + y_off
            pygame.draw.line(self.screen, CONFIG["G_20"], (cx0, dy - 12), (cx0 + cw, dy - 12))
            for line in self._wrap_text(rows[hov][2], self.f_body, cw)[:3]:
                s = self.f_body.render(line, True, CONFIG["G_60"]).copy()
                s.set_alpha(int(255 * a))
                self.screen.blit(s, (cx0, dy))
                dy += CONFIG["BODY_LINE_H"]

    def handle_events(self) -> None:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self._quit_program()

            if e.type == pygame.VIDEORESIZE:
                self._queue_resize(e.w, e.h)
                continue

            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_F11, pygame.K_f) and (pygame.key.get_mods() & pygame.KMOD_ALT or e.key == pygame.K_F11):
                    self._apply_fullscreen(not self.fullscreen)
                    continue
                if self.appear_open and self.gallery_open:
                    self._on_gallery_key(e)
                elif self.appear_open:
                    self._on_appear_key(e)
                elif e.key == pygame.K_ESCAPE:
                    if self.esc_open:
                        if self.esc_anim.target < 0.5:
                            self.esc_anim.set_target(1.0, 0.18, ease_out_cubic)
                        else:
                            self._esc_back()
                    else:
                        self._open_esc()
                elif self.esc_open:
                    self._on_esc_key(e)
                elif e.key == pygame.K_p:
                    if self.mode in ("TRAINING", "RUN") and not self.game_over:
                        self.paused = not self.paused
                        if self.paused: self.pause_sel = 0
                elif self.paused:
                    self._on_pause_key(e)
                elif self.mode == "MENU":
                    self._on_menu_key(e)
                elif self.game_over:
                    self._on_gameover_key(e)
                else:
                    self._on_play_key(e)

            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    if self.appear_open and self.gallery_open:
                        self._on_gallery_click(*self.ev_pos(e.pos))
                    elif self.appear_open:
                        self._on_appear_click(*self.ev_pos(e.pos))
                    elif self.esc_open:
                        self._on_esc_click(self.ev_pos(e.pos))
                    elif self.paused:
                        self._on_pause_click(self.ev_pos(e.pos))
                    elif self.mode == "MENU":
                        self._on_menu_click(self.ev_pos(e.pos))
                    elif self.game_over:
                        self._on_gameover_click(self.ev_pos(e.pos))
                    else:
                        if not self.try_dash():
                            self.buf_dash = CONFIG["INPUT_BUFFER_FRAMES"]
                elif e.button == 4 and self.esc_open and self.esc_page == "MECHANICS":
                    self.esc_mech_scroll = max(0.0, self.esc_mech_scroll - 40)
                elif e.button == 5 and self.esc_open and self.esc_page == "MECHANICS":
                    self.esc_mech_scroll = min(self.esc_mech_max_scroll, self.esc_mech_scroll + 40)

            if e.type == pygame.MOUSEMOTION:
                if self.esc_open:
                    self._sync_esc_hover(self.ev_pos(e.pos))
                elif self.paused:
                    self._sync_pause_hover(self.ev_pos(e.pos))
                elif self.mode == "MENU":
                    self._sync_menu_hover(self.ev_pos(e.pos))
                elif self.game_over:
                    self._sync_gameover_hover(self.ev_pos(e.pos))

    def _on_play_key(self, e) -> None:
        if e.key == pygame.K_SPACE:
            if not self.try_dash(): self.buf_dash = CONFIG["INPUT_BUFFER_FRAMES"]
        elif e.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            if not self.try_swap(): self.buf_swap = CONFIG["INPUT_BUFFER_FRAMES"]
        elif e.key == pygame.K_r:
            self._start_fade()
            self._setup_game()
        elif e.key == pygame.K_TAB:
            self.practice_mode = not self.practice_mode

    def _gameover_options_rects(self) -> List[Tuple[int, int, int, int]]:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        bw, bh, gap = 200, 52, 20
        total = bw * 2 + gap
        x0 = int(W / 2 - total / 2)
        y = int(H / 2 + 128)
        return [(x0, y, bw, bh), (x0 + bw + gap, y, bw, bh)]

    def _sync_gameover_hover(self, pos) -> None:
        for i, r in enumerate(self._gameover_options_rects()):
            if r[0] <= pos[0] <= r[0] + r[2] and r[1] <= pos[1] <= r[1] + r[3]:
                if self.gameover_sel != i:
                    self.gameover_sel = i
                    self.gameover_sel_x.set_target(
                        float(self._gameover_options_rects()[i][0]),
                        CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
                return

    def _gameover_confirm(self) -> None:
        self.gameover_anim.snap(0.0)
        if self.gameover_sel == 0:
            self._start_fade()
            self._setup_game()
        else:
            self._back_to_menu()

    def _on_gameover_click(self, pos) -> None:
        for i, r in enumerate(self._gameover_options_rects()):
            if r[0] <= pos[0] <= r[0] + r[2] and r[1] <= pos[1] <= r[1] + r[3]:
                self.gameover_sel = i
                self.gameover_sel_x.set_target(float(r[0]),
                                               CONFIG["UI_TWEEN_FAST"], ease_out_cubic)
                self._gameover_confirm()
                return

    def _on_gameover_key(self, e) -> None:
        if e.key == pygame.K_r:
            self.gameover_anim.snap(0.0)
            self._start_fade()
            self._setup_game()
        elif e.key in (pygame.K_LEFT, pygame.K_UP):
            self.gameover_sel = (self.gameover_sel - 1) % 2
            self.gameover_sel_x.set_target(
                float(self._gameover_options_rects()[self.gameover_sel][0]),
                CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
        elif e.key in (pygame.K_RIGHT, pygame.K_DOWN):
            self.gameover_sel = (self.gameover_sel + 1) % 2
            self.gameover_sel_x.set_target(
                float(self._gameover_options_rects()[self.gameover_sel][0]),
                CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
        elif e.key in (pygame.K_1, pygame.K_KP1):
            self.gameover_sel = 0; self._gameover_confirm()
        elif e.key in (pygame.K_2, pygame.K_KP2):
            self.gameover_sel = 1; self._gameover_confirm()
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._gameover_confirm()

    def _on_pause_key(self, e) -> None:
        if e.key == pygame.K_UP:
            self.pause_sel = (self.pause_sel - 1) % 3
        elif e.key == pygame.K_DOWN:
            self.pause_sel = (self.pause_sel + 1) % 3
        elif e.key in (pygame.K_1, pygame.K_KP1):
            self.pause_sel = 0; self._pause_confirm()
        elif e.key in (pygame.K_2, pygame.K_KP2):
            self.pause_sel = 1; self._pause_confirm()
        elif e.key in (pygame.K_3, pygame.K_KP3):
            self.pause_sel = 2; self._pause_confirm()
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._pause_confirm()

    def _pause_confirm(self) -> None:
        if self.pause_sel == 0:
            self.paused = False
        elif self.pause_sel == 1:
            if self.mode == "RUN" and not self._finalized:
                self._finalize_run()
            self.paused = False
            self._start_fade()
            self._setup_game()
        elif self.pause_sel == 2:
            self._back_to_menu()

    def _pause_options_rects(self) -> List[Tuple[int, int, int, int]]:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        cx = W // 2
        cy = H - 110
        return [(cx - 340 + i * 230, cy, 210, 34) for i in range(3)]

    def _on_pause_click(self, pos) -> None:
        for i, r in enumerate(self._pause_options_rects()):
            if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                self.pause_sel = i
                self._pause_confirm()
                return

    def _sync_pause_hover(self, pos) -> None:
        for i, r in enumerate(self._pause_options_rects()):
            if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                self.pause_sel = i
                return

    def _menu_sel_target_y(self) -> float:
        return float(self._menu_options_rects()[self.menu_sel][1])

    def _on_menu_key(self, e) -> None:
        if e.key == pygame.K_UP:
            self.menu_sel = (self.menu_sel - 1) % 3
            self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                       CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
        elif e.key == pygame.K_DOWN:
            self.menu_sel = (self.menu_sel + 1) % 3
            self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                       CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
        elif e.key == pygame.K_LEFT and self.menu_sel == 0:
            self.menu_stage = max(1, self.menu_stage - 1)
        elif e.key == pygame.K_RIGHT and self.menu_sel == 0:
            unlocked = int(self.save_data["training_unlocked_stage"])
            self.menu_stage = min(unlocked, self.menu_stage + 1)
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._menu_confirm()
        elif e.key in (pygame.K_1, pygame.K_KP1):
            self.menu_sel = 0
            self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                       CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
            self._menu_confirm()
        elif e.key in (pygame.K_2, pygame.K_KP2):
            self.menu_sel = 1
            self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                       CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
            self._menu_confirm()
        elif e.key in (pygame.K_3, pygame.K_KP3):
            self.menu_sel = 2
            self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                       CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
            self._menu_confirm()

    def _menu_confirm(self) -> None:
        if self.menu_sel == 0:
            self.mode = "TRAINING"
            self.stage = self.menu_stage
            self._start_fade()
            self._setup_game()
        elif self.menu_sel == 1:
            if bool(self.save_data.get("training_done", False)):
                self.mode = "RUN"
                self._start_fade()
                self._setup_game()
        elif self.menu_sel == 2:
            self.appear_open = True
            self.appear_sel = 0

    def _menu_row_metrics(self) -> Tuple[int, int]:
        try:
            lh = float(self.f_menu.render("训", True, CONFIG["G_80"]).get_height())
        except Exception:
            lh = 35.0
        return int(round(lh + 20)), int(CONFIG["MENU_ROW_GAP"])

    def _menu_block_offset(self) -> float:
        row_h, gap = self._menu_row_metrics()
        rows_h = row_h * 3 + gap * 2
        origin = float(CONFIG["MENU_BLOCK_ORIGIN"])
        block_h = (float(CONFIG["MENU_ROW_Y0"]) + rows_h + 95.0) - origin
        H = CONFIG["HEIGHT"]
        free = H - float(CONFIG["MENU_BOTTOM_RESERVE"])
        top = (H - block_h) / 2.0
        lo = float(CONFIG["MENU_BLOCK_TOP_MIN"])
        hi = max(lo, free - block_h)
        return max(lo, min(top, hi)) - origin

    def _menu_options_rects(self) -> List[Tuple[int, int, int, int]]:
        row_h, gap = self._menu_row_metrics()
        W = CONFIG["WIDTH"]
        y0 = int(round(CONFIG["MENU_ROW_Y0"] + self._menu_block_offset()))
        w = int(min(CONFIG["MENU_ROW_W"], W * CONFIG["MENU_ROW_W_MAXF"]))
        return [(W // 2 - w // 2, y0 + i * (row_h + gap), w, row_h)
                for i in range(3)]

    def _sync_menu_hover(self, pos) -> None:
        for i, r in enumerate(self._menu_options_rects()):
            if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                if self.menu_sel != i:
                    self.menu_sel = i
                    self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                               CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
                return

    def _on_menu_click(self, pos) -> None:
        for i, r in enumerate(self._menu_options_rects()):
            if r[0] <= pos[0] <= r[0]+r[2] and r[1] <= pos[1] <= r[1]+r[3]:
                if i == 0:
                    if pos[0] < CONFIG["WIDTH"] // 2 - 40:
                        self.menu_stage = max(1, self.menu_stage - 1)
                    elif pos[0] > CONFIG["WIDTH"] // 2 + 40:
                        unlocked = int(self.save_data["training_unlocked_stage"])
                        self.menu_stage = min(unlocked, self.menu_stage + 1)
                    else:
                        self.menu_sel = 0
                        self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                                   CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
                        self._menu_confirm()
                else:
                    self.menu_sel = i
                    self.menu_sel_y.set_target(self._menu_sel_target_y(),
                                               CONFIG["UI_TWEEN_NORMAL"], ease_out_back)
                    self._menu_confirm()
                return

    def update(self, dt: float) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        self.frame += 1
        self._tick_fade(dt)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        if self.appear_open:
            self.anim_t = (self.anim_t + dt) % 3600.0
            return

        if self.mode == "MENU":
            self.anim_t = (self.anim_t + dt) % 3600.0
            return
        if self.paused or self.esc_open:
            return

        if self.hitstop_frames > 0:
            self.hitstop_frames -= 1
            return

        if self.trauma > 0:
            self.trauma = max(0.0, self.trauma - CONFIG["SHAKE_DECAY"] * dt)

        if self.stage_complete_timer > 0:
            self.stage_complete_timer -= dt
            for p in self.particles:
                p["pos"] = p["pos"] + p["vel"] * dt
                p["vel"] = p["vel"] * (1.0 - 3.0 * dt); p["life"] -= dt
            self.particles = [p for p in self.particles if p["life"] > 0]
            for r in self.rings: r["life"] -= dt
            self.rings = [r for r in self.rings if r["life"] > 0]
            for sl in self.slashes: sl["life"] -= dt
            self.slashes = [sl for sl in self.slashes if sl["life"] > 0]
            if self.stage_complete_timer <= 0:
                if self.mode == "TRAINING":
                    self.stage += 1
                    if self.stage > 5:
                        self.mode = "MENU"
                        self.menu_sel = 0
                        self.menu_stage = int(self.save_data["training_unlocked_stage"])
                    else:
                        self._start_fade()
                        self._setup_game()
            return

        if self.hint_timer > 0: self.hint_timer -= dt
        if self.wave_flash > 0: self.wave_flash = max(0.0, self.wave_flash - dt * 0.7)

        if self.bullet_time_frames > 0:
            self.bullet_time_frames -= 1
            world_scale = CONFIG["PERFECT_WORLD_SCALE"]
        else:
            world_scale = 1.0

        if self.swap_cd_frames > 0: self.swap_cd_frames -= 1
        if self.no_energy_cd > 0: self.no_energy_cd -= 1
        if self.iframe_frames > 0: self.iframe_frames -= 1
        if self.chain_timer > 0:
            self.chain_timer -= 1
            if self.chain_timer == 0 and self.chain_count >= 3:
                self.chain_break_flash = 18
        if self.chain_break_flash > 0: self.chain_break_flash -= 1
        if self.invert_frames > 0: self.invert_frames -= 1
        if self.phase_grace_timer > 0:
            self.phase_grace_timer -= 1
            if self.phase_grace_timer <= 0:
                self.phase_grace_indices = set()

        if self.buf_dash > 0:
            self.buf_dash -= 1
            if self.buf_dash > 0 and self.try_dash(): self.buf_dash = 0
        if self.buf_swap > 0:
            self.buf_swap -= 1
            if self.buf_swap > 0 and self.try_swap(): self.buf_swap = 0

        alive = []
        for s in self.shadows:
            s["frames_left"] -= 1
            if s["frames_left"] > 0:
                s["pos"] = s["pos"] + s["drift_dir"] * CONFIG["SHADOW_DRIFT_SPEED"] * (1.0 / 60.0)
                alive.append(s)
        self.shadows = alive

        for i in range(len(self.ai_marks)):
            if self.ai_marks[i] > 0: self.ai_marks[i] -= 1
        for i in range(len(self.ai_trap_frames)):
            if self.ai_trap_frames[i] > 0: self.ai_trap_frames[i] -= 1
        for i in range(len(self.ai_exec_frames)):
            if self.ai_exec_frames[i] > 0: self.ai_exec_frames[i] -= 1
        for i in range(len(self.ai_flash_frames)):
            if self.ai_flash_frames[i] > 0: self.ai_flash_frames[i] -= 1

        self.player_prev_pos = self.player_pos.copy()

        self._update_aim()

        if self.player_state == "IDLE":
            self._player_idle(dt)
        elif self.player_state == "DASHING":
            self._player_dashing()
        elif self.player_state == "BACKSWING":
            self.state_frame += 1
            if self.state_frame >= CONFIG["CANCEL_WINDOW_FRAMES"]:
                self.player_state = "RECOVERY"; self.state_frame = 0
                if not self.did_cancel_this_backswing:
                    self.consecutive_cancels = 0
                    if self.mode == "TRAINING" and self.stage == 4:
                        self.stage_progress = 0
            self._player_drift()
        elif self.player_state == "RECOVERY":
            self.state_frame += 1
            if self.state_frame >= CONFIG["RECOVERY_FRAMES"]:
                self.player_state = "IDLE"; self.state_frame = 0
            self._player_drift()

        self.player_trail.append(self.player_pos.copy())
        maxlen = max(CONFIG["PLAYER_TRAIL_LEN"], int(self.pskin["tlen"]))
        if len(self.player_trail) > maxlen:
            self.player_trail.pop(0)

        if self.player_state == "DASHING" and self.frame % 2 == 0:
            self.afterimages.append({
                "pos": self.player_pos.copy(),
                "life": float(self.pskin["ai_life"]),
                "maxlife": float(self.pskin["ai_life"])})
        if (self.player_state == "DASHING" and self.fx_poem
                and self.pskin.get("poem") and self.frame % 4 == 0):
            self._spawn_poem(self.player_pos, 1)
        if (self.player_state == "DASHING" and self.fx_afterimage
                and self.pskin.get("poem") and self.frame % 3 == 0):
            self._spawn_sword_qi(self.dash_dir, 1)
        self._update_poem(dt)
        for im in self.afterimages:
            im["life"] -= dt
        if self.afterimages:
            self.afterimages = [im for im in self.afterimages if im["life"] > 0]
            cap = int(self.pskin["ai_n"]) * 6
            if len(self.afterimages) > cap:
                self.afterimages = self.afterimages[-cap:]
        for q in self.sword_qi:
            q["life"] -= dt
        if self.sword_qi:
            self.sword_qi = [q for q in self.sword_qi if q["life"] > 0]
            if len(self.sword_qi) > int(CONFIG["QI_CAP"]):
                self.sword_qi = self.sword_qi[-int(CONFIG["QI_CAP"]):]

        for s in self.slimes: s["age"] += dt
        self.slimes = [s for s in self.slimes if s["age"] < s["life"]]

        self.t += dt

        if self.mode == "TRAINING":
            if self.stage == 1:
                self.stage_progress = self.t
                self._check_stage_goal()
        else:
            new_wave = self._wave_of_time(self.t)
            if new_wave > self.wave:
                self.wave = new_wave
                self.wave_flash = 1.0
                iv_new = self._spit_interval(self.wave)
                for sp in self.spitters:
                    sp["timer"] = min(float(sp["timer"]), iv_new)

            wc = self._wave_cfg(self.wave)
            want_sp = int(wc.get("spitter", 0))
            iv_now = self._spit_interval(self.wave)
            while len(self.spitters) < min(want_sp, CONFIG["SPITTER_MAX"]):
                placed = False
                for _ in range(40):
                    p = np.array([np.random.uniform(80, W - 80),
                                  np.random.uniform(80, H - 80)], dtype=np.float64)
                    if vlen(p - self.player_pos) < 260: continue
                    if all(vlen(p - sp["pos"]) > 200 for sp in self.spitters):
                        lo, hi = CONFIG["SPITTER_PHASE"]
                        self.spitters.append({"pos": p, "timer": iv_now * np.random.uniform(lo, hi)})
                        placed = True
                        break
                if not placed: break

            self.ai_spawn_timer -= dt
            total = len(self.ai_positions) + len(self.pending_spawns)
            cap = int(wc.get("max", CONFIG["AI_MAX_COUNT"]))
            if self.ai_spawn_timer <= 0 and total < cap:
                self.ai_spawn_timer = float(wc.get("spawn", CONFIG["AI_SPAWN_INTERVAL"]))
                n = int(wc.get("batch", 1))
                for k in range(min(n, cap - total)):
                    pos = self._pick_spawn_pos()
                    if k > 0:
                        a = np.random.uniform(0, 2 * np.pi)
                        pos = pos + np.array([math.cos(a), math.sin(a)]) * np.random.uniform(60, 140)
                        pos[0] = float(np.clip(pos[0], 44, W - 44))
                        pos[1] = float(np.clip(pos[1], 44, H - 44))
                    self.pending_spawns.append({"pos": pos,
                                                "timer": CONFIG["WARN_TIME"],
                                                "total": CONFIG["WARN_TIME"]})

        still = []
        for sp in self.pending_spawns:
            sp["timer"] -= dt
            if sp["timer"] <= 0:
                self.ai_positions.append(sp["pos"].copy())
                self.ai_velocities.append(np.zeros(2)); self.ai_trails.append([])
                self.ai_marks.append(0); self.ai_trap_frames.append(0)
                self.ai_stun_frames.append(0); self.ai_exec_frames.append(0)
                self.ai_flash_frames.append(0)
                self._burst(sp["pos"], CONFIG["C_THREAT"], 10, 200)
            else:
                still.append(sp)
        self.pending_spawns = still

        sim_dt = dt * world_scale
        if self.ai_positions:
            arr = np.stack(self.ai_positions)
            vel = np.stack(self.ai_velocities)
            N = len(arr)

            if self.mode == "TRAINING":
                speed = CONFIG["AI_BASE_SPEED"]
            else:
                cap = CONFIG["AI_MAX_SPEED"] + (self.wave - 1) * CONFIG["WAVE_AI_SPEED_ADD"]
                speed = min(CONFIG["AI_BASE_SPEED"] + self.t * CONFIG["AI_SPEED_RAMP"]
                            + (self.wave - 1) * CONFIG["WAVE_AI_SPEED_ADD"], cap)

            pred = self.player_pos + self.player_vel * CONFIG["AI_PREDICT"]
            to_p = pred - arr
            dist_arr = np.maximum(np.linalg.norm(to_p, axis=1, keepdims=True), 1e-3)
            desired = to_p / dist_arr * speed
            in_slime = self._in_slime_mask(arr)
            a_alpha = 1.0 - math.exp(-CONFIG["AI_SMOOTH"] * sim_dt)

            for i in range(N):
                if self.ai_stun_frames[i] > 0:
                    self.ai_stun_frames[i] -= 1
                    vel[i] = vel[i] * 0.88
                    continue
                trapped = False
                if self.ai_trap_frames[i] > 0:
                    trapped = True
                elif in_slime[i]:
                    self.ai_trap_frames[i] = CONFIG["SLIME_TRAP_FRAMES"]
                    trapped = True
                d = desired[i]
                if trapped: d = d * CONFIG["TRAP_SLOW"]
                vel[i] = vel[i] + (d - vel[i]) * a_alpha

            arr = arr + vel * sim_dt
            self.ai_positions = [arr[i] for i in range(N)]
            self.ai_velocities = [vel[i] for i in range(N)]
            for i in range(len(self.ai_trails)):
                self.ai_trails[i].append(arr[i].copy())
                if len(self.ai_trails[i]) > CONFIG["AI_TRAIL_LEN"]:
                    self.ai_trails[i].pop(0)

            if self.iframe_frames <= 0 and self._death_collision(arr):
                self._die("threat"); return

            d_player = np.linalg.norm(arr - self.player_pos, axis=1)
            killed = [i for i in range(len(self.ai_positions))
                      if (self.ai_trap_frames[i] > 0
                          or (self.ai_exec_frames[i] > 0
                              and self.ai_stun_frames[i] <= 0))
                      and d_player[i] < CONFIG["TRAP_KILL_DIST"]]
            for i in reversed(killed): self._kill_ai(i)

            if self.mode == "TRAINING":
                n_want = CONFIG["STAGE_ENEMIES"][self.stage - 1]
                while len(self.ai_positions) < n_want:
                    self._spawn_enemy_away()

        sp_interval = self._spit_interval(self.wave) if self.mode != "TRAINING" else CONFIG["SPITTER_INTERVAL"]
        sp_speed = self._spit_speed(self.wave) if self.mode != "TRAINING" else CONFIG["SPITTER_PROJ_SPEED"]
        for sp in self.spitters:
            sp["timer"] -= sim_dt
            if sp["timer"] <= 0:
                sp["timer"] = sp_interval
                d = self.player_pos - sp["pos"]
                dd = vlen(d)
                if dd > 1.0: d = d / dd
                self.projectiles.append({"pos": sp["pos"].copy(),
                                         "vel": d * sp_speed,
                                         "life": CONFIG["SPITTER_PROJ_LIFE"]})
                self._ring(sp["pos"], 40, CONFIG["C_SPITTER"], 2, 0.35)
                self._burst(sp["pos"], CONFIG["C_SPITTER"], 6, 150)

        alive_p = []
        for p in self.projectiles:
            p["pos"] = p["pos"] + p["vel"] * sim_dt
            p["life"] -= sim_dt
            if p["life"] <= 0: continue
            if not (-40 < p["pos"][0] < W + 40 and -40 < p["pos"][1] < H + 40): continue
            if self.iframe_frames <= 0 and vlen(p["pos"] - self.player_pos) < CONFIG["SPITTER_PROJ_R"] + 12:
                self._die("projectile"); return
            alive_p.append(p)
        self.projectiles = alive_p

        for p in self.particles:
            p["pos"] = p["pos"] + p["vel"] * sim_dt
            p["vel"] = p["vel"] * (1.0 - 3.0 * sim_dt)
            p["life"] -= sim_dt
        self.particles = [p for p in self.particles if p["life"] > 0]
        for r in self.rings: r["life"] -= sim_dt
        self.rings = [r for r in self.rings if r["life"] > 0]
        for sl in self.slashes: sl["life"] -= sim_dt
        self.slashes = [sl for sl in self.slashes if sl["life"] > 0]
        for pop in self.popups:
            pop["pos"] = pop["pos"] + np.array([0.0, -46.0]) * sim_dt
            pop["life"] -= sim_dt
        self.popups = [p for p in self.popups if p["life"] > 0]

        if self.flash > 0: self.flash = max(0.0, self.flash - dt * 2.5)
        if self.stage_complete_flash > 0:
            self.stage_complete_flash = max(0.0, self.stage_complete_flash - dt * 1.8)

        if self.mode == "TRAINING":
            regen = CONFIG["TRAINING_ENERGY_REGEN"]
        else:
            regen = CONFIG["ENERGY_REGEN"]
        if regen > 0.0:
            self.energy = min(CONFIG["MAX_ENERGY"], self.energy + regen * dt)

    def _update_gameover(self, dt: float) -> None:
        self.frame += 1
        self._tick_fade(dt)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        if self.trauma > 0:
            self.trauma = max(0.0, self.trauma - CONFIG["SHAKE_DECAY"] * dt)

        if self.death_slowmo_timer > 0:
            self.death_slowmo_timer -= dt
            wdt = dt * CONFIG["DEATH_SLOWMO_SCALE"]
        else:
            wdt = dt
            if self.gameover_anim.target < 0.5 and self.gameover_anim.value < 0.01:
                self.gameover_anim.set_target(1.0, CONFIG["UI_TWEEN_SLOW"], ease_out_back)

        for p in self.particles:
            p["pos"] = p["pos"] + p["vel"] * wdt
            p["vel"] = p["vel"] * (1.0 - 3.0 * wdt); p["life"] -= wdt
        self.particles = [p for p in self.particles if p["life"] > 0]
        for r in self.rings: r["life"] -= wdt
        self.rings = [r for r in self.rings if r["life"] > 0]
        for sl in self.slashes: sl["life"] -= wdt
        self.slashes = [sl for sl in self.slashes if sl["life"] > 0]
        if self.flash > 0: self.flash = max(0.0, self.flash - dt * 2.5)

    def _update_aim(self) -> None:
        mx, my = self.mouse_pos()
        to_m = np.array([mx - self.player_pos[0], my - self.player_pos[1]])
        d = vlen(to_m)
        if d > 4.0:
            self.aim_dir = to_m / d

    def _player_idle(self, dt: float) -> None:
        mx, my = self.mouse_pos()
        to_m = np.array([mx - self.player_pos[0], my - self.player_pos[1]])
        d = vlen(to_m)
        if d > 4.0:
            self.aim_dir = to_m / d
            tv = self.aim_dir * CONFIG["PLAYER_SPEED"]
        else:
            tv = np.zeros(2)
        alpha = 1.0 - math.exp(-CONFIG["PLAYER_SMOOTH"] * dt)
        self.player_vel += (tv - self.player_vel) * alpha
        slow = CONFIG["SLIME_PLAYER_SLOW"] if self._in_slime_mask(self.player_pos[None, :])[0] else 1.0
        self.player_pos = self.player_pos + self.player_vel * dt * slow
        self._clamp_player()

    def _player_drift(self) -> None:
        dt = 1.0 / 60.0
        scale = float(CONFIG["RECOVERY_MOVE_SCALE"])
        if scale > 0.0:
            mx, my = self.mouse_pos()
            to_m = np.array([mx - self.player_pos[0], my - self.player_pos[1]])
            dn = vlen(to_m)
            if dn > 4.0:
                steer = (to_m / dn) * CONFIG["PLAYER_SPEED"] * scale
                a = 1.0 - math.exp(-CONFIG["PLAYER_SMOOTH"] * dt)
                self.player_vel += (steer - self.player_vel) * a
            slow = CONFIG["SLIME_PLAYER_SLOW"] \
                if self._in_slime_mask(self.player_pos[None, :])[0] else 1.0
            self.player_pos = self.player_pos + self.player_vel * dt * slow
        else:
            self.player_pos = self.player_pos + self.player_vel * dt * 0.15
        self.player_vel = self.player_vel * 0.90
        self._clamp_player()

    def _player_dashing(self) -> None:
        prev = self.player_pos.copy()
        step = self.dash_dir * (CONFIG["DASH_SPEED"] / 60.0)
        self.player_pos = self.player_pos + step
        self._clamp_player()
        self._check_dash_hits(prev, self.player_pos)
        self.state_frame += 1
        if self.state_frame >= self.dash_total_frames:
            if CONFIG["DASH_PHASE_ON_MARK"] and self.dash_hits:
                self.phase_grace_indices = set(self.dash_hits)
                self.phase_grace_timer = CONFIG["PHASE_GRACE_FRAMES"]
            if self._cancel_on():
                self.player_state = "BACKSWING"
                self.did_cancel_this_backswing = False
            else:
                self.player_state = "IDLE"
            self.state_frame = 0

    def _clamp_player(self) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]; m = CONFIG["PLAYER_MARGIN"]
        self.player_pos[0] = float(np.clip(self.player_pos[0], m, W - m))
        self.player_pos[1] = float(np.clip(self.player_pos[1], m, H - m))

    def _stage_goal_line(self) -> str:
        st = self.stage
        goal = CONFIG["STAGE_GOALS"][st - 1]
        desc = (CONFIG["STAGE_DESCS"][st - 1] if self.use_cjk else STAGE_DESCS_EN[st - 1])
        if st == 1:
            prog = f"{self.stage_progress:.1f} / {goal:.0f}"
        else:
            prog = f"{int(self.stage_progress)} / {int(goal)}"
        return f"{desc}   {prog}"

    def _draw_top_goal(self, W: int, H: int) -> None:
        if self.mode == "TRAINING":
            line = self._stage_goal_line()
        else:
            nxt = self._next_wave_in()
            line = (f"WAVE {self.wave:02d}   ·   下一波 {nxt:.0f}s"
                    if self.use_cjk else
                    f"WAVE {self.wave:02d}  ·  NEXT IN {nxt:.0f}s")
        if self.hint_timer > 0:
            a = 1.0
            if self.hint_timer < CONFIG["TOPGOAL_FADE"]:
                a = self.hint_timer / CONFIG["TOPGOAL_FADE"]
            base = self.f_med.render(line, True, CONFIG["G_80"])
            surf = base.copy(); surf.set_alpha(int(230 * a))
            self.screen.blit(surf, surf.get_rect(center=(W // 2, 58)))
        else:
            surf = self.f_tiny.render(line, True, CONFIG["G_60"])
            self.screen.blit(surf, surf.get_rect(center=(W // 2, 22)))

    def _cursor_hovering_clickable(self, mx: int, my: int) -> bool:
        if self.esc_open:
            if self.esc_page == "ROOT":
                for r in self._esc_root_rects():
                    if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
                        return True
            elif self.esc_page == "SETTINGS":
                for r in self._esc_settings_rects():
                    if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
                        return True
            elif self.esc_page == "MECHANICS":
                for r in self._esc_mech_tab_rects():
                    if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
                        return True
                if self.esc_mech_tab == 1:
                    for r in self._mech_ctrl_rects():
                        if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
                            return True
        elif self.mode == "MENU":
            for r in self._menu_options_rects():
                if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
                    return True
        elif self.paused:
            for r in self._pause_options_rects():
                if r[0] <= mx <= r[0]+r[2] and r[1] <= my <= r[1]+r[3]:
                    return True
        return False

    def _draw_cursor(self) -> None:
        mx, my = self.mouse_pos()
        if self.esc_open or self.mode == "MENU" or self.paused or self.game_over:
            if self._cursor_hovering_clickable(mx, my):
                radius, col, thick = 15, self.pcol, 2
            else:
                radius, col, thick = 9, CONFIG["G_80"], 1
        elif self.iframe_frames > 0:
            radius, col, thick = 12, (255, 255, 255), 2
        elif self.player_state == "DASHING":
            frac = self.state_frame / max(1, self.dash_total_frames)
            radius = int(10 + 9 * frac)
            col, thick = self.pcol, 2
        elif self.energy < CONFIG["DASH_COST"]:
            radius, col, thick = 6, CONFIG["G_60"], 1
        else:
            radius, col, thick = 10, self.pcol, 1

        pygame.draw.circle(self.screen, col, (mx, my), radius, thick)
        pygame.draw.line(self.screen, col, (mx - radius - 5, my), (mx - 3, my), 1)
        pygame.draw.line(self.screen, col, (mx + 3, my), (mx + radius + 5, my), 1)
        pygame.draw.line(self.screen, col, (mx, my - radius - 5), (mx, my - 3), 1)
        pygame.draw.line(self.screen, col, (mx, my + radius + 5), (mx, my + 3), 1)
        pygame.draw.circle(self.screen, col, (mx, my), 1)

    def _draw_fade(self, W: int, H: int) -> None:
        if self.fade_timer > 0:
            a = int(230 * (self.fade_timer / CONFIG["TRANSITION_DURATION"]))
            ov = pygame.Surface((self.pw, self.ph))
            ov.fill((0, 0, 0)); ov.set_alpha(a)
            self.screen.blit(ov, (0, 0))

    def _shift_hue(self, col, t: float) -> Tuple[int, int, int]:
        r, g, b = [float(c) / 255.0 for c in col]
        mx, mn = max(r, g, b), min(r, g, b)
        d = mx - mn
        if d < 1e-6:
            return tuple(int(c) for c in col)
        if mx == r:   h = ((g - b) / d) % 6.0
        elif mx == g: h = (b - r) / d + 2.0
        else:         h = (r - g) / d + 4.0
        h = (h / 6.0 + t) % 1.0
        s = 0.0 if mx == 0 else d / mx
        v = mx
        i = int(h * 6.0); f = h * 6.0 - i
        p = v * (1.0 - s); q = v * (1.0 - f * s); u = v * (1.0 - (1.0 - f) * s)
        tab = [(v, u, p), (q, v, p), (p, v, u), (p, q, v), (u, p, v), (v, p, q)]
        rr, gg, bb = tab[i % 6]
        return (int(rr * 255), int(gg * 255), int(bb * 255))

    def _smooth_path(self, pts, sub=3):
        m = len(pts)
        if m < 3:
            return [(float(q[0]), float(q[1])) for q in pts]
        P = np.asarray(pts, dtype=np.float64).reshape(m, 2)
        idx = np.arange(m - 1)
        p0 = P[np.maximum(idx - 1, 0)]
        p1 = P[idx]
        p2 = P[idx + 1]
        p3 = P[np.minimum(idx + 2, m - 1)]
        p1b = p1[None, :, :]
        c0 = (p2 - p0)[None, :, :]
        c1 = (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3)[None, :, :]
        c2 = (-p0 + 3.0 * p1 - 3.0 * p2 + p3)[None, :, :]
        ts = np.arange(sub, dtype=np.float64) / float(sub)
        t1 = ts[:, None, None]
        t2 = t1 * t1
        t3 = t2 * t1
        pts_out = 0.5 * (2.0 * p1b + c0 * t1 + c1 * t2 + c2 * t3)
        A = np.concatenate(
            (pts_out.transpose(1, 0, 2).reshape((m - 1) * sub, 2),
             P[m - 1:]))
        n = A.shape[0]
        if n > 4:
            for _ in range(2):
                K = A.copy()
                A[2:n - 2] = (K[1:n - 3] + 2.0 * K[2:n - 2] + K[3:n - 1]) * 0.25
        return A.tolist()

    def _ribbon(self, sp, wf, cf, af, segs=18, off=0.0, wmul=1.0, feather=2):
        n = len(sp)
        if n < 2:
            return
        step = 1
        if segs is not None and segs > 0:
            step = max(1, int(math.ceil((n - 1) / float(segs))))
        items = []
        i = 0
        while i + step <= n - 1:
            j = i + step
            tm = (i + j) * 0.5 / float(n - 1)
            a = int(af(tm))
            if float(wf(tm)) > 0.05 and a >= 3:
                qua = []
                ok = True
                for k in (i, j):
                    t = k / float(n - 1)
                    px, py = sp[k]
                    qa = sp[max(0, k - 1)]
                    qb = sp[min(n - 1, k + 1)]
                    dx = qb[0] - qa[0]
                    dy = qb[1] - qa[1]
                    ln = math.hypot(dx, dy)
                    if ln < 0.001:
                        ok = False
                        break
                    nx, ny = -dy / ln, dx / ln
                    hwc = float(wf(t)) * 0.5
                    oc = hwc * off
                    hw = hwc * wmul
                    qua.append((px + nx * (oc + hw), py + ny * (oc + hw)))
                    qua.append((px + nx * (oc - hw), py + ny * (oc - hw)))
                if ok:
                    poly = [qua[0], qua[1], qua[3], qua[2]]
                    items.append((poly, cf(tm), a))
            i = j
        if feather > 0:
            for (poly, col, a) in items:
                cx = (poly[0][0] + poly[1][0] + poly[2][0] + poly[3][0]) * 0.25
                cy = (poly[0][1] + poly[1][1] + poly[2][1] + poly[3][1]) * 0.25
                for k in range(feather, 0, -1):
                    aa = int(a * (0.34 / k))
                    if aa < 3:
                        continue
                    ext = []
                    for (x, y) in poly:
                        vx, vy = x - cx, y - cy
                        L = math.hypot(vx, vy)
                        if L < 0.001:
                            ext.append((x, y))
                        else:
                            ext.append((x + vx / L * 1.1 * k,
                                        y + vy / L * 1.1 * k))
                    pygame.draw.polygon(self.fx, (*col, aa), ext)
        for (poly, col, a) in items:
            pygame.draw.polygon(self.fx, (*col, a), poly)

    @staticmethod
    def _hval(i: float, salt: float = 0.0) -> float:
        v = math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
        return v - math.floor(v)

    def _trail_ink(self, sp, alpha: float, fade: float, w: float) -> None:
        n = len(sp)
        if n < 2:
            return
        m = float(n - 1)
        moon = self.pcol
        inkc = self.pskin.get("ink", (72, 92, 130))
        indigo = self.pskin.get("indigo", (88, 142, 202))
        def wetness(t):
            return 0.50 + 0.50 * (t ** 0.70)
        def drymod(t):
            if t > 0.62:
                return 1.0
            s = 0.5 + 0.5 * math.sin(t * m * 0.45 + 0.40)
            return 0.70 + 0.30 * s
        def pressf(t):
            oi = t * m
            return (0.56 + 0.30 * (0.5 + 0.5 * math.sin(oi * 0.85 + 0.35))
                    + 0.14 * (0.5 + 0.5 * math.sin(oi * 2.30 + 1.10)))
        def widthf(t):
            return max(0.5, w * pressf(t) * (0.36 + 0.74 * t) * (0.60 + 0.40 * drymod(t)))
        def massf(t):
            return alpha * (t ** fade) * wetness(t)
        self._ribbon(sp, lambda t: max(0.5, w * pressf(t) * (0.40 + 0.82 * t) * 1.75),
                     lambda t: inkc, lambda t: massf(t) * 0.62, segs=18, feather=2)
        self._ribbon(sp, widthf, lambda t: moon,
                     lambda t: massf(t) * drymod(t), segs=20, feather=1)
        gold = self.pskin.get("gold", (216, 178, 108))
        for i in range(2, n, 9):
            t = i / m
            if self._hval(i, 17.3) < 0.66:
                continue
            a = int(massf(t) * 0.60 * (0.40 + 0.60 * self._hval(i, 7.1)))
            if a < 4:
                continue
            self._soft_dot(sp[i][0], sp[i][1],
                           0.60 + self._hval(i, 5.9) * 1.15, gold, a, 1)
        for i in range(0, n, 14):
            t = i / m
            px, py = sp[i]
            qa = sp[max(0, i - 1)]; qb = sp[min(n - 1, i + 1)]
            dx = qb[0] - qa[0]; dy = qb[1] - qa[1]
            ln = math.hypot(dx, dy)
            if ln < 0.001:
                continue
            nx, ny = -dy / ln, dx / ln
            hw = widthf(t) * 0.5
            r1 = self._hval(i, 1.7); r2 = self._hval(i, 5.3)
            if t > 0.70:
                a = int(massf(t) * 0.22 * (t - 0.70) / 0.30)
                if a > 2:
                    self._soft_dot(px + nx * hw * (1.12 + r1 * 1.6),
                                   py + ny * hw * (1.12 + r1 * 1.6), 1.0 + r2 * 2.6, inkc, a, 0)
                    self._soft_dot(px - nx * hw * (1.12 + r2 * 1.6),
                                   py - ny * hw * (1.12 + r2 * 1.6), 1.0 + r1 * 2.6, inkc, a, 0)
            elif t < 0.62:
                f = (0.62 - t) / 0.62
                a = int(massf(t) * 0.46 * (0.35 + 0.65 * r1))
                if a > 2:
                    for sd in (1.0, -1.0):
                        L = f * (1.4 + r1 * 4.2) * sd
                        self._soft_dot(px + nx * (hw + L), py + ny * (hw + L),
                                       0.7 + r2 * 1.4, inkc, int(a * (0.45 + 0.55 * r2)), 0)
        for i in range(1, n, 16):
            t = i / m
            if self._hval(i, 9.1) < 0.40:
                continue
            a = int(massf(t) * 0.58)
            if a < 3:
                continue
            self._soft_dot(sp[i][0], sp[i][1],
                           0.8 + self._hval(i, 2.6) * 2.0 * t, inkc, a, 1)
        for i in range(2, n, 21):
            t = i / m
            if self._hval(i, 13.7) < 0.62:
                continue
            a = int(massf(t) * 0.70)
            if a < 3:
                continue
            self._soft_dot(sp[i][0], sp[i][1],
                           0.7 + self._hval(i, 6.1) * 1.5, indigo, a, 1)
        ex, ey = sp[-1]
        self._soft_dot(ex, ey, w * 0.23 + 1.3, moon, int(alpha * 0.95), 1)
        sx, sy = sp[0]
        for k in range(6):
            ang = k * (2.0 * math.pi / 6.0) + 0.62
            d = 1.8 + self._hval(k + 3, 7.7) * 6.2
            a = int(alpha * 0.07 * (1.0 - k / 6.0))
            if a < 3:
                continue
            self._soft_dot(sx + math.cos(ang) * d, sy + math.sin(ang) * d,
                           0.9 + self._hval(k, 4.4) * 2.2, inkc, a, 0)

    def _walk(self, sp, step):
        if isinstance(sp, np.ndarray):
            xl = sp[:, 0].tolist()
            yl = sp[:, 1].tolist()
        else:
            xl = [q[0] for q in sp]
            yl = [q[1] for q in sp]
        out = []
        acc = 0.0
        n = len(xl)
        for i in range(1, n):
            acc += math.hypot(xl[i] - xl[i - 1], yl[i] - yl[i - 1])
            if acc >= step:
                acc = 0.0
                out.append((xl[i], yl[i], i / float(n - 1)))
        return out

    def _soft_quad(self, quad, col, a):
        cx = sum(q[0] for q in quad) / float(len(quad))
        cy = sum(q[1] for q in quad) / float(len(quad))
        pygame.draw.polygon(self.fx, (*col, a), quad)
        for k in (1, 2):
            aa = int(a * (0.46 / k))
            if aa < 3: break
            pts = []
            for (x, y) in quad:
                vx, vy = x - cx, y - cy
                ln = math.hypot(vx, vy)
                if ln < 0.001:
                    pts.append((x, y))
                else:
                    pts.append((x + vx / ln * 1.15 * k, y + vy / ln * 1.15 * k))
            pygame.draw.polygon(self.fx, (*col, aa), pts)

    def _soft_dot(self, x, y, r, col, a, feather=2):
        r = max(1.0, float(r))
        cx, cy = int(round(x)), int(round(y))
        ri = int(round(r))
        for k in range(feather, 0, -1):
            aa = int(a * (0.42 / k))
            if aa < 3: continue
            pygame.draw.circle(self.fx, (*col, aa), (cx, cy), ri + k)
        pygame.draw.circle(self.fx, (*col, a), (cx, cy), ri)

    def _soft_ring(self, x, y, r, col, a):
        r = int(max(1, round(r)))
        cx, cy = int(round(x)), int(round(y))
        for k in (1, -1, 0):
            aa = a if k == 0 else int(a * 0.36)
            if aa < 3: continue
            pygame.draw.circle(self.fx, (*col, aa), (cx, cy), max(1, r + k), 1)

    def _crescent(self, x, y, r, a0, a1, wmax, col, a, head=0.42, feather=1) -> None:
        span = a1 - a0
        n = max(7, int(abs(span) * 12))
        hd = min(0.92, max(0.06, float(head)))
        for k in range(n + 1):
            f = k / float(n)
            if f <= hd:
                e = (f / hd) ** 0.60
            else:
                d = 1.0 - hd
                e = (max(0.0, 1.0 - (f - hd) / d)) ** 1.35 if d > 1e-6 else 0.0
            aa = int(a * e)
            if aa < 3:
                continue
            ang = a0 + span * f
            self._soft_dot(x + math.cos(ang) * r, y + math.sin(ang) * r,
                           max(0.55, wmax * e), col, aa, feather)

    def _soft_line(self, p0, p1, wd, col, a, feather=2):
        wd = max(1, int(wd))
        for k in range(feather, 0, -1):
            aa = int(a * (0.40 / k))
            if aa < 3: continue
            pygame.draw.line(self.fx, (*col, aa), p0, p1, wd + 2 * k)
        pygame.draw.line(self.fx, (*col, a), p0, p1, wd)

    def _trail_color(self, t: float) -> Tuple[int, int, int]:
        if self.pskin.get("hue"):
            return self._shift_hue(self.pcol, -0.20 * t)
        return self.pcol

    def _draw_player_trail(self) -> None:
        st = self.trail_style
        if st == "off":
            return
        sk = self.pskin
        raw = self.player_trail[-int(sk["tlen"]):]
        if len(raw) < 2:
            return
        alpha = float(sk["talpha"]); fade = float(sk["tfade"]); w = float(sk["twidth"])
        m = len(raw)
        sp = self._smooth_path(raw, 3)
        n = len(sp)
        if n < 2:
            return
        if st == "line":
            self._ribbon(sp, lambda t: max(0.6, w * t),
                         lambda t: self._trail_color(t),
                         lambda t: 170 * (t ** fade), segs=7)
        elif st == "ribbon":
            self._ribbon(sp, lambda t: max(0.6, w * t),
                         lambda t: self._trail_color(t),
                         lambda t: alpha * (t ** fade), segs=7)
        elif st == "syrup":
            self._ribbon(sp, lambda t: max(0.6, w * (0.30 + 1.05 * t)),
                         lambda t: self._trail_color(t),
                         lambda t: alpha * (t ** fade), segs=7)
            sag = float(self.pskin.get("sag", 7.0))
            for (gx, gy, t) in self._walk(sp, 15.0):
                if t > 0.66:
                    continue
                a = int(alpha * (t ** fade) * 0.75)
                if a < 4:
                    continue
                self._soft_dot(gx, gy + (1.0 - t) * sag, 0.8 + 1.8 * t,
                               self._trail_color(t), a)
            hx, hy = sp[-1]
            ha = int(alpha * 0.95)
            self._soft_dot(hx, hy, w * 0.34 + 1.0, self._trail_color(1.0), ha)
        elif st == "mercury":
            for (bx, by, t) in self._walk(sp, 5.0):
                a = int(alpha * (t ** fade))
                if a < 4:
                    continue
                rr = max(1.0, 0.6 + w * 0.62 * t)
                self._soft_dot(bx, by, rr, self._trail_color(t), a)
                if t > 0.62:
                    self._soft_dot(bx - rr / 3.0, by - rr / 3.0, max(1.0, rr / 3.0),
                                   (255, 255, 255), min(255, a // 3))
        elif st == "oil":
            self._trail_oil(sp, alpha, fade, w)
        elif st == "bubble":
            rise = float(self.pskin.get("rise", 9.0))
            for (bx, by, t) in self._walk(sp, 6.5):
                a = int(alpha * (t ** fade))
                if a < 4:
                    continue
                wob = math.sin(t * m * 1.9) * (1.0 - t) * 3.0
                rr = max(1.0, 1.2 + w * 0.55 * t + math.sin(t * m * 2.3) * 1.2)
                self._soft_ring(bx + wob, by - (1.0 - t) * rise, rr,
                                self._trail_color(t), a)
                if rr > 3:
                    self._soft_dot(bx + wob - rr / 3.0, by - (1.0 - t) * rise - rr / 3.0,
                                   1.0, (255, 255, 255), min(255, a // 2))
        elif st == "ink":
            self._trail_ink(sp, alpha, fade, w)

    def _trail_oil(self, sp, alpha: float, fade: float, w: float) -> None:
        n = len(sp)
        if n < 2:
            return
        sk = self.pskin
        spread = float(sk.get("spread", 0.55))
        span = float(sk.get("hue_span", 0.94))
        sheen = float(sk.get("sheen", 0.62))
        dark = tuple(sk.get("film_dark", (26, 24, 46)))
        base_a = float(sk.get("film_base_a", 0.55))
        cycles = float(sk.get("film_cycles", 2.6))
        chue = float(sk.get("film_cross_hue", 0.70))
        drift = float(sk.get("film_drift", 0.34))
        silver = float(sk.get("film_silver", 0.08))
        cross = float(sk.get("film_cross", 1.7))
        head = float(sk.get("film_head", 0.34))
        gpix = float(sk.get("film_grid", 2.2))
        stepw = float(sk.get("film_step", 7.0))
        edge = float(sk.get("film_edge", 0.60))
        sat = float(sk.get("film_sat", 0.80))
        at = float(self.anim_t)

        def envf(t):
            e = math.exp(-((t - 0.38) ** 2) / (2 * 0.34 ** 2))
            tp = min(1.0, t / 0.16)
            tp = tp * tp * (3.0 - 2.0 * tp)
            return (0.60 + spread * e) * tp

        def af(t):
            return alpha * (0.24 + 0.76 * (t ** fade))

        self._ribbon(sp, lambda t: max(0.5, w * envf(t)),
                     lambda t: dark, lambda t: af(t) * base_a,
                     segs=max(10, int(n / 3)), feather=3)

        xs = [p[0] for p in sp]
        ys = [p[1] for p in sp]
        mrg = w * 1.6 + 10.0
        bx0, bx1 = min(xs) - mrg, max(xs) + mrg
        by0, by1 = min(ys) - mrg, max(ys) + mrg
        s = max(0.001, float(self.scale))
        ox, oy = _view_offset()
        iw = int(math.ceil((bx1 - bx0) * s))
        ih = int(math.ceil((by1 - by0) * s))
        if iw < 4 or ih < 4 or iw > 1600 or ih > 1600:
            return
        tmp = getattr(self, "_film_tmp", None)
        if tmp is None or tmp.get_width() != iw or tmp.get_height() != ih:
            tmp = pygame.Surface((iw, ih), pygame.SRCALPHA)
            self._film_tmp = tmp
        else:
            tmp.fill((0, 0, 0, 0))

        cum = [0.0]
        for q in range(1, n):
            cum.append(cum[-1] + math.hypot(sp[q][0] - sp[q - 1][0],
                                            sp[q][1] - sp[q - 1][1]))
        total = cum[-1]
        if total < 1.0:
            return
        step_arc = max(2.0, stepw)
        cnt = int(total / step_arc) + 1
        if cnt > 120:
            cnt = 120
        pts = []
        j = 0
        for ci in range(cnt + 1):
            tgt = ci / float(cnt) * total
            while j < n - 2 and cum[j + 1] < tgt:
                j += 1
            if j > n - 2:
                j = n - 2
            seg = cum[j + 1] - cum[j]
            f = 0.0 if seg <= 1e-6 else (tgt - cum[j]) / seg
            f = max(0.0, min(1.0, f))
            px = sp[j][0] + (sp[j + 1][0] - sp[j][0]) * f
            py = sp[j][1] + (sp[j + 1][1] - sp[j][1]) * f
            qa = sp[max(0, j)]
            qb = sp[min(n - 1, j + 2)]
            dx = qb[0] - qa[0]
            dy = qb[1] - qa[1]
            ln = math.hypot(dx, dy)
            if ln < 0.001:
                continue
            nx, ny = -dy / ln, dx / ln
            t = tgt / total
            hw = w * envf(t) * 0.5
            pts.append((px, py, nx, ny, hw, t))
        if len(pts) < 2:
            return

        hwm = sum(p[4] for p in pts) / float(len(pts))
        N = int(hwm * 2.0 * s / gpix)
        N = max(4, min(24, N))
        pvs = []
        c1s = []
        s1s = []
        c2s = []
        s2s = []
        v0s = []
        v1s = []
        for jj in range(N):
            vm = -1.0 + 2.0 * (jj + 0.5) / N
            av = abs(vm)
            pvs.append(0.0 if av >= 1.0 else (1.0 - av ** cross) ** 0.55)
            b1 = vm * 1.3
            b2 = -vm * 2.0
            c1s.append(math.cos(b1))
            s1s.append(math.sin(b1))
            c2s.append(math.cos(b2))
            s2s.append(math.sin(b2))
            v0s.append(-1.0 + 2.0 * jj / N - 0.035)
            v1s.append(-1.0 + 2.0 * (jj + 1) / N + 0.035)

        cache = getattr(self, "_hue_cache", None)
        if cache is None:
            cache = {}
            self._hue_cache = cache
        pcol = self.pcol
        pmx, pmn = max(pcol), min(pcol)
        pd = pmx - pmn
        if pd < 1e-6:
            bh = 0.0
        else:
            pr, pg, pb = pcol
            if pmx == pr:
                bh = ((pg - pb) / pd) % 6.0
            elif pmx == pg:
                bh = (pb - pr) / pd + 2.0
            else:
                bh = (pr - pg) / pd + 4.0
            bh /= 6.0
        dd1 = at * drift * 1.4
        dd2 = -at * drift * 0.9
        old_fx = self.fx
        self.fx = tmp
        try:
            with _no_scale():
                for k in range(len(pts) - 1):
                    A = pts[k]
                    B = pts[k + 1]
                    tm = (A[5] + B[5]) * 0.5
                    a_base = af(tm) * sheen
                    if a_base < 3.0:
                        continue
                    a1 = (A[0] + B[0]) * 0.0155 + (A[1] + B[1]) * 0.0120 + dd1
                    a2 = (A[0] + B[0]) * 0.0085 - (A[1] + B[1]) * 0.0145 + dd2
                    sa1 = math.sin(a1)
                    ca1 = math.cos(a1)
                    sa2 = math.sin(a2)
                    ca2 = math.cos(a2)
                    bu = head + (1.0 - head) * tm
                    ax, ay, anx, any_, ahw, _t = A
                    bx2, by2, bnx, bny, bhw, _t2 = B
                    ex = bx2 - ax
                    ey = by2 - ay
                    el = math.hypot(ex, ey)
                    if el > 1e-6:
                        ov = 0.9 / s
                        bx2 = bx2 + ex / el * ov
                        by2 = by2 + ey / el * ov
                    for jj in range(N):
                        pv = pvs[jj]
                        if pv <= 0.0:
                            continue
                        wv = (0.5 + 0.5 * (sa1 * c1s[jj] + ca1 * s1s[jj])) * 0.55
                        wv += (0.5 + 0.5 * (sa2 * c2s[jj] + ca2 * s2s[jj])) * 0.45
                        ph = (cycles * bu * (0.70 + 0.58 * wv) + chue * (1.0 - pv)
                              + _FILM_DITH[((k >> 2) * 3 + jj * 5) & 7])
                        frac = ph - math.floor(ph)
                        ck = int(frac * 255.0)
                        col = cache.get(ck)
                        if col is None:
                            col = _film_hsv(bh + frac * span, sat, 1.0)
                            cache[ck] = col
                        inten = 0.42 + 0.58 * (0.5 - 0.5 * math.cos(6.2831853 * ph))
                        kv = a_base * inten * (pv ** edge) * 0.00392157
                        if kv < 0.015:
                            continue
                        if silver > 0.0:
                            fw = frac if frac < 0.5 else 1.0 - frac
                            if fw < silver:
                                kk2 = 1.0 - fw / silver
                                col = tuple(int(c + (255 - c) * 0.55 * kk2)
                                            for c in col)
                        if kv > 0.85:
                            kv = 0.85
                        av0 = ahw * v0s[jj]
                        av1 = ahw * v1s[jj]
                        bv0 = bhw * v0s[jj]
                        bv1 = bhw * v1s[jj]
                        poly = [
                            ((ax + anx * av0 - bx0) * s, (ay + any_ * av0 - by0) * s),
                            ((ax + anx * av1 - bx0) * s, (ay + any_ * av1 - by0) * s),
                            ((bx2 + bnx * bv1 - bx0) * s, (by2 + bny * bv1 - by0) * s),
                            ((bx2 + bnx * bv0 - bx0) * s, (by2 + bny * bv0 - by0) * s),
                        ]
                        pygame.draw.polygon(
                            tmp, (int(col[0] * kv), int(col[1] * kv), int(col[2] * kv), 255),
                            poly)
        finally:
            self.fx = old_fx
        dx0 = int(round(bx0 * s + ox))
        dy0 = int(round(by0 * s + oy))
        try:
            _raw(self.fx).blit(tmp, (dx0, dy0), None, pygame.BLEND_RGBA_ADD)
        except Exception:
            _raw(self.fx).blit(tmp, (dx0, dy0))

    def _draw_afterimages(self) -> None:
        sk = self.pskin
        kind = str(sk.get("ai", "solid"))
        for im in self.afterimages:
            lt = im["life"] / im["maxlife"]
            a = int(130 * lt * lt)
            if a < 3: continue
            ix, iy = int(im["pos"][0]), int(im["pos"][1])
            if kind == "shrink":
                rr = int(11 * (1.0 - 0.45 * (1.0 - lt)))
                pygame.draw.circle(self.fx, (*self.pcol, a), (ix, iy), rr, 2)
                if lt > 0.35:
                    pygame.draw.circle(self.fx, (*self.pcol, a // 3), (ix, iy + rr // 2), 2)
            elif kind == "bead":
                rr = max(1, int(2 + 7 * lt))
                pygame.draw.circle(self.fx, (*self.pcol, a), (ix, iy), rr)
                pygame.draw.circle(self.fx, (255, 255, 255, min(255, a // 2)),
                                   (ix - rr // 3, iy - rr // 3), max(1, rr // 3))
            elif kind == "iris":
                pygame.draw.circle(self.fx, (*self._shift_hue(self.pcol, -0.22 * (1.0 - lt)), a), (ix, iy), 11, 2)
            elif kind == "grow":
                rr = int(9 + 7 * (1.0 - lt))
                pygame.draw.circle(self.fx, (*self.pcol, a), (ix, iy), rr, 1)
                pygame.draw.circle(self.fx, (255, 255, 255, min(255, a // 3)),
                                   (ix - rr // 3, iy - rr // 3), 1)
            elif kind == "poem":
                gold = self.pskin.get("gold", (216, 178, 108))
                inkc = self.pskin.get("ink", (72, 92, 130))
                rr = int(11 * (0.74 + 0.26 * lt))
                pygame.draw.circle(self.fx, (*inkc, min(255, int(a * 1.15))), (ix, iy), rr + 2)
                pygame.draw.circle(self.fx, (*self.pcol, a), (ix, iy), rr, 2)
                if a > 34:
                    pygame.draw.circle(self.fx, (*gold, int(a * 0.60)), (ix, iy), rr + 3, 1)
            elif kind == "bleed":
                for k in range(7):
                    ang = k * (2.0 * math.pi / 7.0) + (1.0 - lt) * 2.1
                    dist = (1.0 - lt) * (5.0 + 4.5 * self._hval(k, 1.3))
                    ox = ix + math.cos(ang) * dist
                    oy = iy + math.sin(ang) * dist
                    aa = int(a * (0.50 - 0.055 * k) * (0.45 + 0.55 * self._hval(k, 3.7)))
                    if aa < 3: continue
                    self._soft_dot(ox, oy, 1.0 + (1.0 - lt) * 3.1 * (0.35 + self._hval(k, 2.2)),
                                   self.pcol, aa, 1)
                self._soft_dot(ix, iy, 3.0 + (1.0 - lt) * 4.0, self.pcol, int(a * 0.85), 1)
                self._soft_ring(ix, iy, 10 + 6 * (1.0 - lt), self.pcol, int(a * 0.55))
            else:
                pygame.draw.circle(self.fx, (*self.pcol, a), (ix, iy), 11, 2)

    def _spawn_sword_qi(self, direction, n: int = 1,
                        spread: float = 0.0, life: float = 0.34,
                        pos=None) -> None:
        try:
            base = math.atan2(float(direction[1]), float(direction[0]))
        except Exception:
            base = 0.0
        src = self.player_pos if pos is None else pos
        for k in range(int(n)):
            off = 0.0
            if n > 1:
                off = (k - (n - 1) / 2.0) * spread
            self.sword_qi.append({
                "pos": src.copy(),
                "ang": base + off,
                "life": float(life), "maxlife": float(life)})
        if len(self.sword_qi) > int(CONFIG["QI_CAP"]):
            self.sword_qi = self.sword_qi[-int(CONFIG["QI_CAP"]):]

    def _draw_sword_qi(self) -> None:
        if not self.sword_qi:
            return
        gold = self.pskin.get("gold", (216, 178, 108))
        moon = self.pcol
        inkc = self.pskin.get("ink", (72, 92, 130))
        for q in self.sword_qi:
            lt = q["life"] / q["maxlife"]
            u = 1.0 - lt
            a = int(float(CONFIG["QI_ALPHA"]) * lt * (0.45 + 0.55 * lt))
            if a < 4:
                continue
            x = float(q["pos"][0]) + math.cos(q["ang"]) * (2.0 + 9.0 * u)
            y = float(q["pos"][1]) + math.sin(q["ang"]) * (2.0 + 9.0 * u)
            r = 11.6 + float(CONFIG["QI_GROW"]) * u
            wd = float(CONFIG["QI_WD"]) * (1.0 - 0.50 * u)
            self._crescent(x, y, r, q["ang"] - 0.92, q["ang"] + 0.92,
                           wd, inkc, int(a * 0.85), 0.50, 0)
            self._crescent(x, y, r, q["ang"] - 0.86, q["ang"] + 0.86,
                           wd * 0.72, moon, a, 0.46, 1)
            self._crescent(x, y, r + wd * 0.62, q["ang"] - 0.62, q["ang"] + 0.62,
                           wd * 0.34, gold, int(a * 0.92), 0.42, 0)

    def _poem_next_char(self) -> str:
        lines = CONFIG["POEM_LINES"]
        ln = lines[self.poem_line % len(lines)]
        ch = ln[self.poem_pos % len(ln)]
        self.poem_pos += 1
        if self.poem_pos >= len(ln):
            self.poem_pos = 0
            self.poem_line += 1
        return ch

    def _poem_blur(self, s, k):
        w, h = s.get_width(), s.get_height()
        k = max(2, int(k))
        if w < 8 or h < 8:
            return s
        sw, sh = max(2, w // k), max(2, h // k)
        d = pygame.transform.smoothscale(s, (sw, sh))
        return pygame.transform.smoothscale(d, (w, h))

    def _poem_glyph(self, ch):
        sc = max(0.001, float(self.scale))
        key = (ch, round(sc, 3))
        got = self._poem_cache.get(key)
        if got is not None:
            return got
        col = self.pskin.get("poem_col", (124, 156, 206))
        ss = max(2, int(CONFIG["POEM_SS"]))
        pad = max(1, int(CONFIG["POEM_SOFT_PAD"]))
        size = max(6, int(round(self._fs(int(CONFIG["POEM_FS"])) * ss)))
        f = self._poem_fonts.get(size)
        if f is None:
            data = getattr(self, "_poem_font_bytes", None)
            if data:
                try:
                    f = FTFont(io.BytesIO(bytes(data)), size, False)
                except Exception:
                    f = None
            if f is None and self.poem_font_path:
                try:
                    f = FTFont(str(self.poem_font_path), size, False)
                except Exception:
                    f = None
            if f is None:
                f = self.f_small
            self._poem_fonts[size] = f
        raw = _raw(f.render(ch, True, col)).convert_alpha()
        bw, bh = raw.get_width(), raw.get_height()
        tw = max(2, int(round(bw / float(ss))))
        th = max(2, int(round(bh / float(ss))))
        sharp = pygame.transform.smoothscale(raw, (tw, th))
        soft = self._poem_blur(sharp, int(CONFIG["POEM_BLUR"]))
        out = pygame.Surface((tw + pad * 2, th + pad * 2), pygame.SRCALPHA)
        halo = soft.copy()
        halo.set_alpha(int(255 * float(CONFIG["POEM_HALO"])))
        out.blit(halo, (pad - 1, pad + 1))
        core = sharp.copy()
        core.set_alpha(int(255 * float(CONFIG["POEM_SHARP"])))
        out.blit(core, (pad, pad))
        post = int(CONFIG["POEM_POST"])
        if post > 1:
            out = self._poem_blur(out, post)
        got = (out, float(tw + pad * 2), float(th + pad * 2))
        self._poem_cache[key] = got
        return got

    def _spawn_poem(self, pos, n: int = 1) -> None:
        sc = max(0.001, float(self.scale))
        for _ in range(int(n)):
            ch = self._poem_next_char()
            surf, gw, gh = self._poem_glyph(ch)
            self.poem_glyphs.append({
                "s": surf.copy(),
                "x": float(pos[0]) + (self._hval(self.frame, 3.3) - 0.5) * 30.0,
                "y": float(pos[1]) - 25.0 - self._hval(self.frame, 4.4) * 12.0,
                "vx": (self._hval(self.frame, 1.1) - 0.5) * 15.0,
                "vy": -13.0 - self._hval(self.frame, 2.2) * 16.0,
                "life": 1.15, "maxlife": 1.15,
                "w": gw / sc, "h": gh / sc})
        if len(self.poem_glyphs) > 28:
            self.poem_glyphs = self.poem_glyphs[-28:]

    def _update_poem(self, dt: float) -> None:
        if not self.poem_glyphs:
            return
        out = []
        for g in self.poem_glyphs:
            g["life"] -= dt
            if g["life"] <= 0:
                continue
            g["x"] += g["vx"] * dt
            g["y"] += g["vy"] * dt
            g["vy"] *= (1.0 - 1.7 * dt)
            out.append(g)
        self.poem_glyphs = out

    def _draw_poem(self) -> None:
        peak = float(self.pskin.get("poem_a", 84))
        for g in self.poem_glyphs:
            lt = g["life"] / g["maxlife"]
            a = int(peak * min(1.0, (1.0 - lt) * 6.5) * (lt ** 0.85))
            if a < 4:
                continue
            bx = g["x"] - g["w"] * 0.5
            by = g["y"] - g["h"] * 0.5
            g["s"].set_alpha(a)
            self.fx.blit(g["s"], (bx, by))

    def _draw_debug(self, W: int, H: int) -> None:
        if CONFIG["DEBUG_ANIM"]:
            x = (self.anim_t * 60.0) % (W + 120) - 60
            pygame.draw.circle(self.screen, (255, 255, 0), (int(round(x)), H // 2 - 100), 18)
            pygame.draw.circle(self.screen, (255, 255, 0), (int(round(x)), H // 2 - 100), 18, 1)
        if CONFIG["SHOW_FPS"]:
            fps = self.clock.get_fps()
            surf = self.f_tiny.render(f"{fps:5.1f} FPS", True, CONFIG["G_60"])
            self.screen.blit(surf, (W - surf.get_width() - 16, H - 22))

    @staticmethod
    def _ss_draw(w: int, h: int, ss: int, draw_fn):
        w = max(2, int(w)); h = max(2, int(h))
        big = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)
        draw_fn(big, ss)
        return pygame.transform.smoothscale(big, (w, h))

    def _logo_variants(self, scale: float) -> List[pygame.Surface]:
        key = round(float(scale), 4)
        vs = self._logo_cache.get(key)
        if vs is None:
            ss = int(CONFIG["LOGO_SS"])
            st = int(CONFIG["SUBPIX_STEPS"])
            vs = [self._render_logo(scale, ss, i / st) for i in range(st)]
            self._logo_cache[key] = vs
        return vs

    def _draw_player_body(self, px, py):
        if self.fx_energy_glow and self.energy >= CONFIG["MAX_ENERGY"] - 0.001:
            gp = 0.5 + 0.5 * math.sin(self.anim_t * 2 * math.pi * 0.9)
            for k in range(3):
                rr = 11.4 + k * 0.55 + 0.5 * gp
                aa = int((52 - k * 14) * (0.55 + 0.45 * gp))
                if aa < 5:
                    continue
                pygame.draw.circle(self.fx, (*self.pcol, aa),
                                   (px, py), int(round(rr)), 1)
        kind = str(self.pskin.get("body", ""))
        bs = 1.0
        if kind == "drip":
            ph = 0.5 + 0.5 * math.sin(self.anim_t * 2.0 * math.pi * 0.55)
            dl = 12.4 + 2.0 * ph
            pygame.draw.line(self.fx, (*self.pcol, 150),
                             (px, py + 11.6), (px, py + dl), 2)
            pygame.draw.circle(self.fx, (*self.pcol, 170), (px, py + dl + 1.4), 2)
        elif kind == "spec":
            pygame.draw.arc(self.fx, (255, 255, 255),
                            (px - 11.4, py - 11.4, 22.8, 22.8), math.radians(160), math.radians(230), 2)
        elif kind == "iris":
            bs = float(CONFIG["IRIS_BODY_SCALE"])
        elif kind == "film":
            br = 11.3 + 0.7 * math.sin(self.anim_t * 2.0 * math.pi * 0.8)
            pygame.draw.circle(self.fx, (*self.pcol, 85), (px, py), int(br), 1)
            pygame.draw.circle(self.fx, (255, 255, 255, 120),
                               (px - 5, py - 6), 2)
        elif kind == "poem":
            gold = self.pskin.get("gold", (216, 178, 108))
            inkc = self.pskin.get("ink", (72, 92, 130))
            indigo = self.pskin.get("indigo", (88, 142, 202))
            ph = self.anim_t * 2.0 * math.pi * 0.7
            for k in range(3):
                aa = 30 - k * 9
                if aa < 4:
                    continue
                self._soft_dot(px, py, 15.4 + k * 2.6, indigo, aa, 0)
            for k in range(3):
                base = 9.6 + k * 0.45 + 0.5 * math.sin(ph + k * 0.9)
                aa = 34 - k * 10
                if aa < 4:
                    continue
                for s in range(20):
                    ang = s * (2.0 * math.pi / 20.0) + k * 0.15
                    wob = math.sin(ang * 3.0 + ph * 0.8 + k * 1.7)
                    rr = base + wob * 0.45
                    self._soft_dot(px + math.cos(ang) * rr, py + math.sin(ang) * rr,
                                   1.2 + 0.3 * k, inkc,
                                   int(aa * (0.55 + 0.45 * (0.5 + 0.5 * wob))), 0)
            for k in range(4):
                a0 = k * (math.pi / 2.0) + ph * 0.32
                a1 = a0 + 0.50
                pygame.draw.arc(self.fx, (*gold, 70),
                                (px - 11.3, py - 11.3, 22.6, 22.6), a0 - 0.04, a1 + 0.04, 1)
                pygame.draw.arc(self.fx, (*gold, 150),
                                (px - 10.5, py - 10.5, 21.0, 21.0), a0, a1, 2)
                pygame.draw.line(self.fx, (*gold, 115),
                                 (px + math.cos(a1) * 10.5, py + math.sin(a1) * 10.5),
                                 (px + math.cos(a1) * 8.7, py + math.sin(a1) * 8.7), 1)
                self._soft_dot(px + math.cos(a0) * 10.5, py + math.sin(a0) * 10.5,
                               1.15, gold, 95, 0)
                am = a0 + 0.25 + math.pi / 4.0
                pygame.draw.arc(self.fx, (*indigo, 52),
                                (px - 11.4, py - 11.4, 22.8, 22.8), am - 0.30, am + 0.30, 1)
            for s in range(30):
                ang = s * (2.0 * math.pi / 30.0)
                wob = math.sin(ang * 3.0 + ph * 1.15)
                rr = 9.6 + 0.7 * wob
                dens = 0.5 + 0.5 * math.sin(ang * 2.0 + ph * 1.15)
                sz = 0.85 + 1.3 * dens
                aa = int((110 + 95 * dens) * (0.72 + 0.28 * (0.5 + 0.5 * wob)))
                if aa < 6: continue
                self._soft_dot(px + math.cos(ang) * rr, py + math.sin(ang) * rr,
                               sz, self.pcol if dens > 0.45 else indigo, aa, 1)
            full = 1.0 if self.energy >= CONFIG["MAX_ENERGY"] - 0.001 else 0.0
            spin = ph * (0.62 + 0.60 * full)
            for k in range(3):
                ang = spin + k * (2.0 * math.pi / 3.0)
                rd = 13.3 + 0.5 * math.sin(ph * 1.4 + k * 2.1)
                br2 = 0.62 + 0.38 * math.sin(ph * 1.9 + k * 1.6)
                aa = int((88 + 82 * br2) * (0.74 + 0.26 * full))
                self._crescent(px, py, rd, ang - 0.70, ang + 0.70,
                               1.70 * (0.68 + 0.32 * br2), gold, aa, 0.42, 1)
                self._crescent(px, py, rd + 1.10, ang - 0.52, ang + 0.52,
                               0.80, self.pcol, int(aa * 0.58), 0.42, 0)
            if full > 0.0:
                pygame.draw.circle(self.fx, (*indigo, 42),
                                   (px, py), int(round(14.2)), 1)
            sweep = (self.anim_t * 0.62) % 1.0
            sa = sweep * 2.0 * math.pi
            self._crescent(px, py, 11.7, sa - 0.58, sa + 0.58, 2.30,
                           gold, 122, 0.40, 1)
            self._crescent(px, py, 12.9, sa - 0.44, sa + 0.44, 0.90,
                           self.pcol, 104, 0.40, 0)
        ir = max(4, int(round(10 * bs)))
        rr = 12
        if kind == "iris":
            for k in range(6):
                a0 = k * (math.pi / 3.0) + self.anim_t * 0.5
                pygame.draw.arc(self.fx, (*self._shift_hue(self.pcol, -0.16 * (k / 5.0)), 205),
                                (px - rr, py - rr, rr * 2, rr * 2), a0, a0 + 0.72, 2)
            ga = math.radians(148.0 + 6.0 * math.sin(self.anim_t * 0.8))
            pygame.draw.arc(self.fx, (255, 255, 255, 130),
                            (px - rr, py - rr, rr * 2, rr * 2), ga, ga + 1.25, 2)
        else:
            pygame.draw.circle(self.fx, self.pcol, (px, py), rr, 2)
        pygame.draw.circle(self.fx, CONFIG["BG"], (px, py), ir)
        pygame.draw.circle(self.fx, (self.pskin.get("gold", (255, 255, 255))
                                     if str(self.pskin.get("body", "")) == "poem"
                                     else (255, 255, 255)), (px, py), 3)

    def _render_logo(self, scale: float, ss: int, sub_off: float = 0.0) -> pygame.Surface:
        segs = int(CONFIG["LOGO_BEZ_SEGMENTS"])
        base_w, base_h = 120.0, 160.0
        disp_w = max(6, int(round(base_w * scale)))
        disp_h = max(6, int(round(base_h * scale)))
        col = self.pcol
        off_ss = sub_off * float(ss)

        def draw_fn(big, s):
            sc = scale * float(s)
            col_a = (col[0], col[1], col[2], 255)

            tx, ty = 26.0, -33.0
            tsz = float(CONFIG["LOGO_SHADOW_SIZE"])
            tang = math.radians(float(CONFIG["LOGO_SHADOW_ROT"]))
            ca, sa = math.cos(tang), math.sin(tang)
            tri = []
            for px, py in ((0.0, -tsz), (-tsz * 0.866, tsz * 0.5), (tsz * 0.866, tsz * 0.5)):
                tri.append((tx + px * ca - py * sa, ty + px * sa + py * ca))

            ctrl_l = (-20.0, -18.0)
            ctrl_r = (20.0, -18.0)
            xs = [0.0, -22.0, 22.0, ctrl_l[0], ctrl_r[0],
                  -22.0, 22.0,
                  -3.5, 3.5]
            xs += [q[0] for q in tri]
            cx_logic = (min(xs) + max(xs)) * 0.5
            ox = (base_w * 0.5 - cx_logic) * sc
            oy = 55.0 * sc + off_ss

            def T(lx, ly):
                return (ox + lx * sc, oy + ly * sc)

            lw = max(1, int(round(2.0 * sc)))

            top = (0.0, -40.0)
            bl = (-22.0, 4.0)
            ctrl_l = (-20.0, -18.0)
            left_pts = []
            for i in range(segs + 1):
                t = i / segs
                x = (1-t)**2 * top[0] + 2*(1-t)*t * ctrl_l[0] + t**2 * bl[0]
                y = (1-t)**2 * top[1] + 2*(1-t)*t * ctrl_l[1] + t**2 * bl[1]
                left_pts.append(T(x, y))

            ccx, ccy, rr = 0.0, 4.0, 22.0
            arc_pts = []
            for i in range(segs + 1):
                t = i / segs
                a = math.pi * (1.0 - t)
                arc_pts.append(T(ccx + rr * math.cos(a), ccy + rr * math.sin(a)))

            br = (22.0, 4.0)
            ctrl_r = (20.0, -18.0)
            right_pts = []
            for i in range(segs + 1):
                t = i / segs
                x = (1-t)**2 * br[0] + 2*(1-t)*t * ctrl_r[0] + t**2 * top[0]
                y = (1-t)**2 * br[1] + 2*(1-t)*t * ctrl_r[1] + t**2 * top[1]
                right_pts.append(T(x, y))

            pygame.draw.lines(big, col_a, False, left_pts + arc_pts + right_pts, lw)

            sy0, sy1 = 26.0, 52.0
            seg_n = 12
            for i in range(seg_n):
                t0 = i / seg_n
                t1 = (i + 1) / seg_n
                y0 = sy0 + (sy1 - sy0) * t0
                y1 = sy0 + (sy1 - sy0) * t1
                w = max(1, int(round((2.0 - t0 * 1.2) * sc)))
                pygame.draw.line(big, col_a, T(0.0, y0), T(0.0, y1), w)

            for dy, rr_, aa0 in [(62.0, 3.5, 180), (74.0, 2.5, 110), (84.0, 1.5, 60)]:
                q = T(0.0, dy)
                pygame.draw.circle(big, (col[0], col[1], col[2], aa0),
                                   (int(round(q[0])), int(round(q[1]))),
                                   max(1, int(round(rr_ * sc))))

            tpts = [(int(round(T(q[0], q[1])[0])), int(round(T(q[0], q[1])[1])))
                    for q in tri]
            if CONFIG["LOGO_SHADOW_FILL"] > 0:
                pygame.draw.polygon(big, (col[0], col[1], col[2],
                                          int(CONFIG["LOGO_SHADOW_FILL"])), tpts)
            pygame.draw.polygon(big, (col[0], col[1], col[2],
                                      int(CONFIG["LOGO_SHADOW_ALPHA"])),
                                tpts, max(1, int(round(1.5 * sc))))

        with _no_scale():
            out = self._ss_draw(disp_w, disp_h + 1, ss, draw_fn)
        return out.convert_alpha()

    def _draw_logo(self, surface, cx, cy, scale=1.0, alpha=255) -> None:
        img_scale = scale * self.scale
        vs = self._logo_variants(img_scale)
        off = breath_wave(self.anim_t * CONFIG["LOGO_ANIM_HZ"],
                          CONFIG["ANIM_DWELL"],
                          CONFIG["ANIM_WAVE"]) * CONFIG["ANIM_LOGO_BREATH_AMP"] * scale
        self._blit_shifted(surface, vs,
                           cx - 60.0 * scale, cy - 55.0 * scale + off, alpha)

    def _draw_tracked_text(self, surface, text: str, font: FTFont,
                           center_x: int, y: int, spacing: int,
                           color: Tuple[int, int, int], alpha: int = 255) -> None:
        surfs: List[Tuple[pygame.Surface, int]] = []
        total_w = 0
        for ch in text:
            s = font.render(ch, True, color)
            surfs.append((s, total_w))
            total_w += s.get_width() + spacing
        if surfs:
            total_w -= spacing
        x0 = center_x - total_w // 2
        for s, dx in surfs:
            if alpha < 255:
                tmp = s.copy(); tmp.set_alpha(alpha)
                surface.blit(tmp, (x0 + dx, y))
            else:
                surface.blit(s, (x0 + dx, y))

    @staticmethod
    def _blit_shifted(dst: pygame.Surface, variants: List[pygame.Surface],
                      x: float, y: float, alpha: float = 255.0) -> None:
        iy = math.floor(y)
        frac = y - iy
        n = len(variants)
        idx = int(frac * n) % n
        img = variants[idx]
        if alpha >= 255.0:
            dst.blit(img, (int(x), int(iy)))
        else:
            t = img.copy()
            t.set_alpha(int(alpha))
            dst.blit(t, (int(x), int(iy)))

    def _big_font(self, font: FTFont, mul: int) -> FTFont:
        key = (id(font), mul)
        f = self._big_font_cache.get(key)
        if f is None:
            f = self._mkfont(max(4, int(font.size * mul)),
                             getattr(font, "weight", None) or "s", font.bold)
            self._big_font_cache[key] = f
        return f

    def _tracked_variants(self, text: str, font: FTFont, spacing: int,
                          color: Tuple[int, int, int],
                          space_extra: int = 0) -> List[pygame.Surface]:
        key = (text, id(font), spacing, tuple(color), round(float(self.scale), 4),
               int(space_extra))
        cached = self._tracked_cache.get(key)
        if cached is not None:
            return cached
        mul = int(CONFIG["SUBPIX_STEPS"])
        sc = self.scale if self.scale > 0 else 1.0
        big = self._big_font(font, mul)
        items = [big.glyph(ch, color) for ch in text]
        sp_big = int(round(spacing * sc * mul))
        se_big = int(round(space_extra * sc * mul))
        asc = max((b for _, b in items), default=1)
        desc = max((g.get_height() - b for g, b in items), default=1)
        total_big = (sum(g.get_width() for g, _ in items)
                     + sp_big * max(0, len(items) - 1)
                     + se_big * sum(1 for ch in text if ch == " "))
        h_big = max(1, asc + desc)
        line = pygame.Surface((max(1, total_big), h_big), pygame.SRCALPHA)
        x = 0
        for i, (g, b) in enumerate(items):
            line.blit(g, (x, asc - b))
            x += g.get_width() + sp_big + (se_big if text[i] == " " else 0)
        w = max(1, int(round(line.get_width() / mul)))
        h = max(1, int(round(line.get_height() / mul)) + 1)
        out = []
        for i in range(mul):
            canvas = pygame.Surface((max(1, line.get_width()),
                                     max(1, line.get_height() + mul)), pygame.SRCALPHA)
            canvas.blit(line, (0, i))
            out.append(pygame.transform.smoothscale(canvas, (w, h)).convert_alpha())
        self._tracked_cache[key] = out
        return out

    def _menu_title_line(self) -> List[pygame.Surface]:
        return self._tracked_variants("SYRUP", self.f_title, 14, (235, 240, 248))

    def _trap_mark(self, h_px: float, color: Tuple[int, int, int]) -> pygame.Surface:
        key = (int(round(float(h_px) * 4.0)), tuple(color))
        got = self._trap_cache.get(key)
        if got is not None:
            return got
        ss = 4
        H = max(8, int(round(float(h_px) * ss)))
        W = max(8, int(round(H * 1.06)))
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        lw = max(1, int(round(H * 0.085)))
        cx = W * 0.5
        base_y = H * 0.94
        hinge_y = H * 0.74
        bw = W * 0.30
        _REAL_DRAW.line(surf, color, (cx - bw, base_y), (cx + bw, base_y), lw)
        _REAL_DRAW.line(surf, color, (cx, base_y), (cx, hinge_y), lw)
        for sign in (-1.0, 1.0):
            p0 = (cx, hinge_y)
            tip = (cx + sign * W * 0.34, H * 0.18)
            ctrl = (cx + sign * W * 0.50, H * 0.74)
            pts = []
            n = 28
            for i in range(n + 1):
                t = i / float(n)
                mt = 1.0 - t
                pts.append((mt * mt * p0[0] + 2 * mt * t * ctrl[0] + t * t * tip[0],
                            mt * mt * p0[1] + 2 * mt * t * ctrl[1] + t * t * tip[1]))
            _REAL_DRAW.lines(surf, color, False, pts, lw)
            tl = H * 0.14
            for t in CONFIG["MENU_TAG_ICON_TEETH"]:
                mt = 1.0 - t
                px = mt * mt * p0[0] + 2 * mt * t * ctrl[0] + t * t * tip[0]
                py = mt * mt * p0[1] + 2 * mt * t * ctrl[1] + t * t * tip[1]
                tx = 2 * mt * (ctrl[0] - p0[0]) + 2 * t * (tip[0] - ctrl[0])
                ty = 2 * mt * (ctrl[1] - p0[1]) + 2 * t * (tip[1] - ctrl[1])
                ln = math.hypot(tx, ty) or 1.0
                nx, ny = -ty / ln, tx / ln
                dx, dy = cx - px, H * 0.30 - py
                if nx * dx + ny * dy < 0.0:
                    nx, ny = -nx, -ny
                _REAL_DRAW.line(surf, color, (px, py),
                                 (px + nx * tl, py + ny * tl), lw)
        rr = max(1, int(round(H * 0.05)))
        _REAL_DRAW.circle(surf, color, (int(round(cx)), int(round(hinge_y))), rr)
        oh = max(1, int(round(H / float(ss))))
        ow = max(1, int(round(W / float(ss))))
        out = pygame.transform.smoothscale(surf, (ow, oh)).convert_alpha()
        self._trap_cache[key] = out
        return out

    def _menu_tagline_line(self) -> List[pygame.Surface]:
        text = self.S["tagline"]
        if self.use_cjk:
            return self._tracked_variants(text, self.f_tag,
                                          int(CONFIG["MENU_TAG_TRACK_CJK"]),
                                          CONFIG["G_60"])
        sc = self.scale if self.scale > 0 else 1.0
        try:
            tw = self._menu_title_line()[0].get_width() / sc
        except Exception:
            tw = 0.0
        cap = tw * float(CONFIG["MENU_TAG_MAX_RATIO"])
        plan = [(int(a), int(b)) for a, b in CONFIG["MENU_TAG_TRACK_LATIN"]]
        for sp, se in plan[:-1]:
            line = self._tagline_line(sp, se)
            if tw <= 0 or line[0].get_width() / sc <= cap:
                return line
        sp, se = plan[-1]
        return self._tagline_line(sp, se)

    def _tagline_line(self, sp: int, se: int) -> List[pygame.Surface]:
        col = CONFIG["G_60"]
        pre = self.S.get("tagline_pre")
        post = self.S.get("tagline_post")
        if not CONFIG["MENU_TAG_ICON"] or not pre or not post:
            return self._tracked_variants(self.S["tagline"], self.f_tag, sp, col, se)
        key = ("tag", sp, se, round(float(self.scale), 4), tuple(col))
        got = self._tracked_cache.get(key)
        if got is not None:
            return got
        mul = int(CONFIG["SUBPIX_STEPS"])
        sc = self.scale if self.scale > 0 else 1.0
        big = self._big_font(self.f_tag, mul)
        sp_big = int(round(sp * sc * mul))
        se_big = int(round(se * sc * mul))

        items_a = [big.glyph(ch, col) for ch in pre]
        items_b = [big.glyph(ch, col) for ch in post]
        asc = max([b for _, b in items_a] + [b for _, b in items_b] + [1])
        desc = max([g.get_height() - b for g, b in items_a]
                   + [g.get_height() - b for g, b in items_b] + [1])
        h_txt = asc + desc

        def seg(s, items):
            total = (sum(g.get_width() for g, _ in items)
                     + sp_big * max(0, len(items) - 1)
                     + se_big * sum(1 for ch in s if ch == " "))
            line = pygame.Surface((max(1, total), h_txt), pygame.SRCALPHA)
            x = 0
            for i, (g, bb) in enumerate(items):
                line.blit(g, (x, asc - bb))
                x += g.get_width() + sp_big + (se_big if s[i] == " " else 0)
            return line

        a = seg(pre, items_a)
        b = seg(post, items_b)
        cap_h = float(big.glyph("H", col)[0].get_height())
        icon_h = cap_h * float(CONFIG["MENU_TAG_ICON_SCALE"])
        pad = int(round(icon_h * float(CONFIG["MENU_TAG_ICON_PAD"])))
        icon = self._trap_mark(icon_h, col)
        iw, ih = icon.get_size()
        icon_top = asc - cap_h * 0.5 - icon_h * 0.5
        y0 = min(0.0, icon_top)
        oy = -y0
        h_big = int(math.ceil(max(h_txt, icon_top + ih) - y0))
        w_big = int(a.get_width() + pad + iw + pad + b.get_width())
        canvas = pygame.Surface((max(1, w_big), max(1, h_big)), pygame.SRCALPHA)
        canvas.blit(a, (0, int(round(oy))))
        canvas.blit(icon, (a.get_width() + pad, int(round(oy + icon_top))))
        canvas.blit(b, (a.get_width() + pad + iw + pad, int(round(oy))))
        w = max(1, int(round(canvas.get_width() / mul)))
        h = max(1, int(round(canvas.get_height() / mul)) + 1)
        out = []
        for i in range(mul):
            c = pygame.Surface((max(1, canvas.get_width()),
                                max(1, canvas.get_height() + mul)), pygame.SRCALPHA)
            c.blit(canvas, (0, i))
            out.append(pygame.transform.smoothscale(c, (w, h)).convert_alpha())
        self._tracked_cache[key] = out
        return out

    def draw(self) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        _invalidate_view_cache()
        if getattr(self, "_pending_frames", 0) > 0 and not self.fullscreen:
            rw = getattr(self, "_resize_win", None)
            w = rw[0] if rw else self.win_w
            h = rw[1] if rw else self.win_h
            self._stretch_last_frame(int(w), int(h))
            return
        _raw(self.screen).blit(self.static_bg, (0, 0))

        if self.mode == "MENU":
            if self.appear_open and self.gallery_open:
                self._draw_gallery(W, H)
                self._draw_cursor()
                self._draw_debug(W, H)
                pygame.display.flip()
                return
            if self.appear_open:
                self._draw_appear(W, H)
                self._draw_cursor()
                self._draw_debug(W, H)
                pygame.display.flip()
                return
            self._draw_menu()
            if self.esc_open or self.esc_anim.value > 0.001:
                self._draw_esc_panel(W, H)
            if self.toast_timer > 0:
                self._draw_toast(W, H)
            self._draw_cursor()
            self._draw_fade(W, H)
            self._draw_debug(W, H)
            pygame.display.flip()
            return

        self.fx.fill((0, 0, 0, 0))

        for s in self.slimes:
            lt = 1.0 - s["age"] / s["life"]
            r = int(s["radius"] * (0.75 + 0.25 * lt))
            cx, cy = int(s["pos"][0]), int(s["pos"][1])
            col = CONFIG["SLIME_COLOR"]
            pygame.draw.circle(self.fx, (*col, int(30 * lt)), (cx, cy), r)
            pygame.draw.circle(self.fx, (*col, int(70 * lt)), (cx, cy), max(1, r * 2 // 3))
            pygame.draw.circle(self.fx, (*col, int(110 * lt)), (cx, cy), max(1, r // 3))

        for trail in self.ai_trails:
            n = len(trail)
            for i in range(1, n):
                t = i / n
                pygame.draw.line(self.fx, (*CONFIG["C_THREAT"], int(160 * t * t)),
                                 (int(trail[i-1][0]), int(trail[i-1][1])),
                                 (int(trail[i][0]), int(trail[i][1])), max(1, int(6 * t)))
        self._draw_player_trail()
        self._draw_sword_qi()
        if self.fx_afterimage:
            self._draw_afterimages()


        for sp in self.pending_spawns:
            prog = sp["timer"] / sp["total"]
            r = int(12 + 52 * prog); a = int(70 + 185 * (1.0 - prog))
            x, y = int(sp["pos"][0]), int(sp["pos"][1])
            pygame.draw.circle(self.fx, (*CONFIG["C_THREAT"], a), (x, y), r, 2)
            pygame.draw.circle(self.fx, (*CONFIG["C_THREAT"], min(255, a + 40)), (x, y), 3)

        _gs = self.scale if self.scale > 0 else 1.0
        if CONFIG["GLOW_ENABLE_THREAT"]:
            gw, gh = self.glow_threat.get_size()
            hw, hh = gw / (2.0 * _gs), gh / (2.0 * _gs)
            for ap in self.ai_positions:
                self.fx.blit(self.glow_threat, (ap[0] - hw, ap[1] - hh))
        px, py = int(self.player_pos[0]), int(self.player_pos[1])
        if CONFIG["GLOW_ENABLE_PLAYER"]:
            gw, gh = self.glow_player.get_size()
            hw, hh = gw / (2.0 * _gs), gh / (2.0 * _gs)
            self.fx.blit(self.glow_player,
                         (self.player_pos[0] - hw, self.player_pos[1] - hh))
        if CONFIG["GLOW_ENABLE_SPITTER"]:
            gw, gh = self.glow_spitter.get_size()
            hw, hh = gw / (2.0 * _gs), gh / (2.0 * _gs)
            for sp in self.spitters:
                self.fx.blit(self.glow_spitter, (sp["pos"][0] - hw, sp["pos"][1] - hh))

        for p in self.projectiles:
            px2, py2 = int(p["pos"][0]), int(p["pos"][1])
            vx, vy = p["vel"]; nrm = math.hypot(vx, vy) + 1e-6
            pygame.draw.line(self.fx, (*CONFIG["C_SPITTER"], 160),
                             (int(px2 - vx / nrm * 22), int(py2 - vy / nrm * 22)), (px2, py2), 3)

        for r in self.rings:
            tt = r["life"] / r["maxlife"]
            pygame.draw.circle(self.fx, (*r["color"], int(240 * tt)),
                               (int(r["pos"][0]), int(r["pos"][1])),
                               int(r["max_r"] * (1.0 - tt)), r["width"])

        for sl in self.slashes:
            tt = sl["life"] / sl["maxlife"]
            a = int(230 * tt)
            sx, sy = sl["pos"]; dx, dy = sl["dir"]
            nrm = math.hypot(dx, dy) + 1e-6; dx, dy = dx / nrm, dy / nrm
            length = 46 * (0.5 + 0.5 * tt)
            p1 = (int(sx - dx * length), int(sy - dy * length))
            p2 = (int(sx + dx * length), int(sy + dy * length))
            pygame.draw.line(self.fx, (255, 255, 255, a), p1, p2, 3)
            pygame.draw.line(self.fx, (*CONFIG["C_MARK"], a // 2), p1, p2, 1)

        for p in self.particles:
            lt = p["life"] / p["maxlife"]
            pygame.draw.circle(self.fx, (*p["color"], int(255 * lt)),
                               (int(p["pos"][0]), int(p["pos"][1])), max(1, int(3.5 * lt)))

        for s in self.shadows:
            sx, sy = int(s["pos"][0]), int(s["pos"][1])
            lt = s["frames_left"] / CONFIG["SHADOW_LIFE_FRAMES"]
            a = int(160 * (0.35 + 0.65 * lt))
            ang = math.atan2(s["drift_dir"][1], s["drift_dir"][0])
            sz = 11
            pts = [(sx + math.cos(ang + k * (2 * math.pi / 3) + math.pi / 2) * sz,
                    sy + math.sin(ang + k * (2 * math.pi / 3) + math.pi / 2) * sz) for k in range(3)]
            sh = pygame.Surface((int(sz * 3 * self.scale), int(sz * 3 * self.scale)), pygame.SRCALPHA)
            lp = [(p[0] - sx + sz * 3 // 2, p[1] - sy + sz * 3 // 2) for p in pts]
            pygame.draw.polygon(sh, (*self.pcol, a), lp, 2)
            self.fx.blit(sh, (sx - sz * 3 // 2, sy - sz * 3 // 2))

        for sp in self.spitters:
            x, y = int(sp["pos"][0]), int(sp["pos"][1]); r = CONFIG["SPITTER_RADIUS"]
            pts = [(x + math.cos(math.pi / 6 + k * math.pi / 3) * r,
                    y + math.sin(math.pi / 6 + k * math.pi / 3) * r) for k in range(6)]
            charge = 1.0 - min(1.0, sp["timer"] / CONFIG["SPITTER_WARN"])
            base = CONFIG["C_SPITTER"]
            bright = tuple(min(255, int(c * (0.5 + 0.5 * charge))) for c in base)
            pygame.draw.polygon(self.fx, bright, pts, 2)
            pygame.draw.circle(self.fx, base, (x, y), int(4 + 6 * (1.0 - charge)))
        for p in self.projectiles:
            pygame.draw.circle(self.fx, CONFIG["C_SPITTER"],
                               (int(p["pos"][0]), int(p["pos"][1])), CONFIG["SPITTER_PROJ_R"])

        stun_pulse_phase = self.anim_t * 2 * math.pi * CONFIG["ANIM_STUN_PULSE_HZ"]
        stun_star_phase  = self.anim_t * 2 * math.pi * CONFIG["ANIM_STUN_STAR_HZ"]
        trap_rot_phase   = self.anim_t * 2 * math.pi * CONFIG["ANIM_TRAP_ROT_HZ"]

        for i, ap in enumerate(self.ai_positions):
            x, y = int(ap[0]), int(ap[1])
            base_color = CONFIG["C_THREAT"]
            if self.ai_flash_frames[i] > 0:
                base_color = (255, 255, 255)
            pygame.draw.circle(self.fx, base_color, (x, y), CONFIG["AI_RADIUS"])
            if self.ai_marks[i] > 0:
                pygame.draw.circle(self.fx, CONFIG["C_MARK"], (x, y), CONFIG["AI_RADIUS"] + 5, 2)
                pygame.draw.circle(self.fx, CONFIG["C_MARK"], (x, y), 2)
            if self.ai_stun_frames[i] > 0:
                pulse = int(CONFIG["AI_RADIUS"] + 8 + 4 * math.sin(stun_pulse_phase))
                pygame.draw.circle(self.fx, CONFIG["C_SPITTER"], (x, y), pulse, 1)
                for k in range(4):
                    ang2 = stun_star_phase + k * math.pi / 2
                    r2 = CONFIG["AI_RADIUS"] + 12
                    tx = x + math.cos(ang2) * r2; ty = y + math.sin(ang2) * r2
                    pygame.draw.line(self.fx, CONFIG["C_SPITTER"], (tx - 3, ty), (tx + 3, ty), 1)
                    pygame.draw.line(self.fx, CONFIG["C_SPITTER"], (tx, ty - 3), (tx, ty + 3), 1)
            if (self.ai_trap_frames[i] > 0
                    or (self.ai_exec_frames[i] > 0 and self.ai_stun_frames[i] <= 0)):
                a0 = trap_rot_phase
                rr = CONFIG["AI_RADIUS"] + 10
                box = (x - rr, y - rr, rr * 2, rr * 2)
                pygame.draw.arc(self.fx, CONFIG["C_THREAT"], box, a0, a0 + 2.2, 2)
                pygame.draw.arc(self.fx, CONFIG["C_THREAT"], box,
                                a0 + math.pi, a0 + math.pi + 2.2, 2)

        self._draw_player_body(px, py)
        if self.fx_poem:
            self._draw_poem()
        if self.iframe_frames > 0:
            segments = 12
            for k in range(segments):
                ang_a = k * (2 * math.pi / segments)
                ang_b = ang_a + (2 * math.pi / segments) * 0.5
                pygame.draw.arc(self.fx, (255, 255, 255),
                                (px - 15, py - 15, 30, 30), ang_a, ang_b, 2)

        if self.player_state == "BACKSWING":
            frac = self.state_frame / max(1, CONFIG["CANCEL_WINDOW_FRAMES"])
            radius = int(15 + 4 * frac); alpha = int(220 * (1.0 - frac))
            rng = pygame.Surface((int(80 * self.scale), int(80 * self.scale)), pygame.SRCALPHA)
            pygame.draw.circle(rng, (*self.pcol, alpha), (40, 40), radius, 2)
            self.fx.blit(rng, (px - 40, py - 40))

        for pop in self.popups:
            t = pop["life"] / pop["maxlife"]
            alpha = int(255 * min(1.0, t * 1.6))
            base = self.f_small.render(pop["text"], True, pop["color"])
            surf = base.copy(); surf.set_alpha(alpha)
            self.fx.blit(surf, (int(pop["pos"][0]) - surf.get_width() // 2, int(pop["pos"][1])))

        ox, oy = self._shake_offset()
        self.screen.blit(self.fx, (ox, oy))
        if not self._vignette_merged:
            self.screen.blit(self.vignette, (0, 0))

        self._draw_hud(W, H)
        self._draw_top_goal(W, H)

        if self.mode == "TRAINING" and self.hint_timer > 0:
            self._draw_training_hint(W, H)

        if self.mode == "RUN" and self.wave_flash > 0:
            self._draw_wave_banner(W, H)
        if self.practice_mode:
            self._draw_practice_panel(W, H)

        if self.game_over and self.death_slowmo_timer <= 0:
            a = min(1.0, max(0.0, self.gameover_anim.value))
            if a > 0.001:
                total = self.score_detonate + self.score_perfect + self.score_kill
                ov = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
                ov.fill((11, 15, 20, int(215 * a)))
                self.screen.blit(ov, (0, 0))
                dy = int((1.0 - a) * 24)
                t1 = self.f_over.render(f"{total}", True, (235, 240, 248)).copy()
                t1.set_alpha(int(255 * a))
                self.screen.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 110 + dy)))
                rows = [
                    (self.S["max_chain"], f"{self.chain_max}", (255, 255, 255)),
                    (self.S["detonate_count"], f"{self.detonate_count}", CONFIG["C_THREAT"]),
                    (self.S["perfect_count"], f"{self.perfect_count}", CONFIG["C_PLAYER"]),
                    (self.S["score_detonate"], f"{self.score_detonate}", CONFIG["G_60"]),
                    (self.S["score_perfect"], f"{self.score_perfect}", CONFIG["G_60"]),
                    (self.S["score_kill"], f"{self.score_kill}", CONFIG["G_60"]),
                ]
                y0 = H // 2 - 20 + dy
                for i, (lb, vv, cl) in enumerate(rows):
                    ls = self.f_small.render(lb, True, CONFIG["G_60"]).copy(); ls.set_alpha(int(255 * a))
                    vs = self.f_med.render(vv, True, cl).copy(); vs.set_alpha(int(255 * a))
                    self.screen.blit(ls, (W // 2 - 130, y0 + i * 24 + 3))
                    self.screen.blit(vs, (W // 2 + 20, y0 + i * 24))
                grects = self._gameover_options_rects()
                gsel_x = float(self.gameover_sel_x.value)
                gsel_w = float(grects[0][2])
                gsel_h = float(grects[0][3])
                gsel_y = float(grects[0][1])
                ghi = pygame.Surface(((int(gsel_w * self.scale)), int((gsel_h * self.scale))),
                                    pygame.SRCALPHA)
                ghi.fill((*CONFIG["G_20"], int(255 * a)))
                self.screen.blit(ghi, (int(round(gsel_x)), int(round(gsel_y + dy))))
                pygame.draw.rect(self.screen, CONFIG["C_PLAYER"],
                                 (int(round(gsel_x)), int(round(gsel_y + dy + 6)),
                                  4, int(gsel_h - 12)))
                gperiod = 1.0 / max(0.01, CONFIG["ANIM_MENU_SWEEP_HZ"])
                gphase = (self.anim_t % gperiod) / gperiod
                gsx = gphase * (gsel_w + 200) - 100
                if 0 < gsx < gsel_w:
                    pygame.draw.line(self.screen, CONFIG["C_PLAYER"],
                                     (int(round(gsel_x + gsx)), int(round(gsel_y + dy + 6))),
                                     (int(round(gsel_x + gsx)),
                                      int(round(gsel_y + dy + gsel_h - 6))), 1)

                for i, glabel in enumerate([self.S["restart"], self.S["menu"]]):
                    grx = grects[i][0]
                    selected = (i == self.gameover_sel)
                    col = CONFIG["C_PLAYER"] if selected else CONFIG["G_80"]
                    gsrf = self.f_med.render(glabel, True, col).copy()
                    gsrf.set_alpha(int(255 * a))
                    self.screen.blit(gsrf, gsrf.get_rect(
                        center=(grx + grects[i][2] // 2,
                                grects[i][1] + grects[i][3] // 2 + dy)))

                t3 = self.f_tiny.render(
                    "鼠标点击  ·  ←→ 选择  ·  ENTER 确认  ·  R 重开" if self.use_cjk
                    else "click  ·  ←→ select  ·  ENTER confirm  ·  R restart",
                    True, CONFIG["G_40"]).copy()
                t3.set_alpha(int(255 * a))
                self.screen.blit(t3, t3.get_rect(center=(W // 2, H // 2 + 208 + dy)))

        if self.paused:
            self._draw_pause_panel(W, H)

        if self.esc_open or self.esc_anim.value > 0.001:
            self._draw_esc_panel(W, H)

        if self.flash > 0:
            fs = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
            fs.fill((255, 107, 74, int(self.flash * 110)))
            self.screen.blit(fs, (0, 0))

        if self.stage_complete_flash > 0:
            cf = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
            cf.fill((34, 211, 238, int(self.stage_complete_flash * 70)))
            self.screen.blit(cf, (0, 0))
        if self.stage_complete_timer > 0:
            a = min(1.0, max(0.0, self.stage_complete_anim.value))
            if a > 0.001:
                txt = "完成" if self.use_cjk else "CLEAR"
                ok = self.f_big.render(txt, True, CONFIG["C_PLAYER"]).copy()
                ok.set_alpha(int(255 * a))
                dy = int((1.0 - a) * 20)
                self.screen.blit(ok, ok.get_rect(center=(W // 2, H // 2 - 40 + dy)))

        if self.invert_frames > 0:
            inv = pygame.Surface((self.pw, self.ph)); inv.fill((255, 255, 255))
            inv.blit(_raw(self.screen), (0, 0), special_flags=pygame.BLEND_RGB_SUB)
            inv = inv.convert()
            self.screen.blit(inv, (0, 0))

        if self.toast_timer > 0:
            self._draw_toast(W, H)

        self._draw_cursor()
        self._draw_fade(W, H)
        self._draw_debug(W, H)
        pygame.display.flip()
        self._maybe_snapshot()

    def _maybe_snapshot(self) -> None:
        if self.fullscreen:
            return
        self._snap_tick = (getattr(self, "_snap_tick", 0) + 1) % 8
        if self._snap_tick != 0:
            return
        try:
            self._snapshot = _raw(self.screen).copy()
        except Exception:
            self._snapshot = None

    def _draw_toast(self, W: int, H: int) -> None:
        a = min(1.0, self.toast_timer / 0.5)
        alpha = int(220 * a)
        s = self.f_med.render(self.toast_text, True, CONFIG["C_PLAYER"])
        t = s.copy(); t.set_alpha(alpha)
        self.screen.blit(t, t.get_rect(center=(W // 2, H - 160)))

    def _mech_lines_locked(self, tab: int) -> List[Tuple[str, str, int]]:
        req = MECH_STAGE_REQ.get(tab)
        out = []
        si = -1
        for text, kind in self._mech_lines_for_tab(tab):
            if kind == "head":
                si += 1
            r = req[si] if (req and 0 <= si < len(req)) else 1
            out.append((text, kind, int(r)))
        return out

    def _mech_visible(self, req: int) -> bool:
        if bool(self.save_data.get("training_done", False)):
            return True
        return int(req) <= int(self.save_data.get("training_unlocked_stage", 1))

    def _mech_lock_text(self, req: int) -> str:
        if int(req) >= MECH_LOCK_RUN:
            return self.S["mech_lock_run"]
        return self.S["mech_lock_stage"].replace("{n}", str(int(req)))

    def _ctrl_row_locked(self, i: int) -> bool:
        reqs = CTRL_STAGE_REQ
        if i >= len(reqs):
            return False
        return not self._mech_visible(reqs[i])

    def _draw_padlock(self, x: float, y: float, s: float, col, alpha: float) -> None:
        try:
            w = max(4.0, float(s))
            lw = max(1, int(round(w * 0.11)))
            sh = w * 0.46
            pygame.draw.arc(self.screen, col,
                            (x + w * 0.22, y, w * 0.56, sh * 2.0), 0, math.pi, lw)
            bh = w * 0.54
            bx = x
            by = y + sh
            pygame.draw.rect(self.screen, col, (bx, by, w, bh), lw)
            hw = max(1, int(round(w * 0.10)))
            pygame.draw.line(self.screen, col,
                             (bx + w * 0.5, by + bh * 0.30),
                             (bx + w * 0.5, by + bh * 0.78), hw)
        except Exception:
            pass

    def _mech_lines_for_tab(self, tab: int) -> List[Tuple[str, str]]:
        if tab == 1:
            return []
        dash_cost = CONFIG["DASH_COST"]
        dash_cost_str = str(int(dash_cost)) if float(dash_cost).is_integer() else f"{dash_cost:g}"
        lives = int(CONFIG["RUN_LIVES"])

        if not self.use_cjk:
            if tab == 0:
                return [
                    ("Field and Units", "head"),
                    ("The player controls a single circular unit that moves freely inside the field. Two hostile unit types exist: Hunters and Spitters. Hunters spawn from the field edge and pursue the player continuously, predicting their movement. Spitters appear from the third wave onward, remain stationary, and periodically fire bolts toward the player.", "body"),
                    ("", "body"),
                    ("Core Loop", "head"),
                    ("Dashing consumes one energy unit. When energy is depleted, dashing becomes unavailable. Detonation is the only means of recovering energy: each enemy detonated refunds " + dash_cost_str + " energy unit. The core of this game is therefore not evasion, but deliberately approaching, detonating, and withdrawing.", "body"),
                    ("", "body"),
                    ("Mark and Detonate", "head"),
                    ("Passing through a Hunter during a dash applies a Mark, shown as a white ring. Dashing through a marked target again triggers a Detonation: the target is knocked back and coated in slime, " + dash_cost_str + " energy unit is refunded, and score is awarded.", "body"),
                    ("", "body"),
                    ("Shadow and Swap", "head"),
                    ("Each dash leaves a Shadow at its starting point, shown as a cyan triangle. Pressing Shift teleports the player to the Shadow nearest the cursor. Upon teleporting, both the origin and the destination release a shock that coats nearby enemies in slime.", "body"),
                    ("", "body"),
                    ("Slime", "head"),
                    ("Enemies coated in slime move significantly slower. The player is slowed by the same amount while standing in slime and should avoid being immobilized by the slime they have laid down.", "body"),
                    ("", "body"),
                    ("Lives and Waves", "head"),
                    ("In Run mode the player holds " + str(lives) + " lives. Each failure consumes one life; the player then respawns at the centre of the field with brief invulnerability, and nearby enemies and bolts are cleared. When all lives are spent, the run ends. Difficulty rises with each wave: the enemy cap increases, the spawn interval shortens, and Spitters become more numerous, fire faster, and launch faster bolts.", "body"),
                    ("", "body"),
                    ("Training Mode", "head"),
                    ("Training mode imposes no life limit. A stage resets immediately upon failure and may be retried at any time. It exists to build each of the operations above one at a time.", "body"),
                ]
            return [
                ("Direct Contact with a Hunter", "head"),
                ("Contact with any Hunter results in failure. The target already passed through during the current dash is excluded.", "body"),
                ("", "body"),
                ("Struck by a Bolt", "head"),
                ("Being hit by a bolt fired from a Spitter results in failure.", "body"),
                ("", "body"),
                ("All Lives Spent", "head"),
                ("In Run mode, each of the above failures consumes one life. The run ends once all " + str(lives) + " lives have been spent.", "body"),
                ("", "body"),
                ("Training Mode", "head"),
                ("Training mode imposes no life limit. A failure resets the current stage immediately, and the stage may be retried without penalty.", "body"),
            ]
        if tab == 0:
            return [
                ("场地与单位", "head"),
                ("玩家操控一枚可在场地内自由移动的圆形单位。场地内存在两类敌方单位：追猎者与喷浆口。追猎者自场地边缘出现，持续追击玩家，并对其移动位置进行预判。喷浆口自第三波起出现，位置固定，定期向玩家所在方向发射弹丸。", "body"),
                ("", "body"),
                ("核心循环", "head"),
                ("冲刺消耗一格能量，能量耗尽时无法发动冲刺。引爆是恢复能量的唯一途径：每引爆一名敌人，返还 " + dash_cost_str + " 格能量。因此本作的核心并非规避，而是主动接近、完成引爆、随即撤离。", "body"),
                ("", "body"),
                ("标记与引爆", "head"),
                ("冲刺路径经过追猎者时，将为其附加标记，以白色圆环表示。对已标记的目标再次发动冲刺并穿过其所在位置，即触发引爆：目标被击退并陷入黏液，同时返还 " + dash_cost_str + " 格能量并累计得分。", "body"),
                ("", "body"),
                ("影与换位", "head"),
                ("每次冲刺都会在起点留下一枚「影」，以青色三角表示。按下 Shift 键后，玩家瞬移至距鼠标最近的影所在位置。瞬移时，起点与终点各产生一次范围冲击，使范围内敌人陷入黏液。", "body"),
                ("", "body"),
                ("黏液", "head"),
                ("陷入黏液的敌人移动速度显著下降。玩家自身处于黏液中时同样会被减速，应避免被自身铺设的黏液限制移动。", "body"),
                ("", "body"),
                ("生命与波次", "head"),
                ("实战模式下玩家拥有 " + str(lives) + " 条命。每发生一次失败即消耗一条命，随后玩家于场地中央复活并获得短暂无敌，附近的敌人与弹丸将被清除。生命耗尽时本局结束。难度随波次推进而提升：敌人数量上限提高，生成间隔缩短，喷浆口数量增加，其攻击间隔缩短且弹丸速度提升。", "body"),
                ("", "body"),
                ("训练模式", "head"),
                ("训练模式不设生命限制。发生失败时本关立即重置，可随时重新尝试。训练模式用于逐项掌握上述操作。", "body"),
            ]
        return [
            ("与追猎者发生直接接触", "head"),
            ("玩家与任一追猎者发生接触即判定失败。本次冲刺路径中已经穿过的目标除外。", "body"),
            ("", "body"),
            ("被弹丸命中", "head"),
            ("被喷浆口发射的弹丸命中即判定失败。", "body"),
            ("", "body"),
            ("生命耗尽", "head"),
            ("实战模式下，每发生一次上述失败即消耗一条生命。全部 " + str(lives) + " 条生命耗尽时，本局结束。", "body"),
            ("", "body"),
            ("训练模式", "head"),
            ("训练模式不设生命限制。发生失败时本关立即重置，可随时重新尝试。", "body"),
        ]

    def _wrap_text(self, text: str, font: FTFont, max_w: int) -> List[str]:
        if not text: return [""]
        adv = font.advances(text)
        out = []
        cur = ""
        cur_w = 0.0
        i = 0
        for ch in text:
            a = adv[i] if i < len(adv) else font.char_w(ch)
            i += 1
            if cur and cur_w + a > max_w:
                out.append(cur)
                cur = ch
                cur_w = a
            else:
                cur = cur + ch
                cur_w += a
        if cur: out.append(cur)
        return out

    def _draw_esc_panel(self, W: int, H: int) -> None:
        a = max(0.0, min(1.0, self.esc_anim.value))
        if a < 0.001:
            return
        alpha_bg = int(225 * a)
        y_off = int((1.0 - a) * 14)

        ov = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
        ov.fill((11, 15, 20, alpha_bg))
        self.screen.blit(ov, (0, 0))

        self._draw_logo(self.screen, 90, 90 + y_off, scale=0.45, alpha=int(140 * a))

        if self.esc_page == "ROOT":
            t = self.f_big.render(self.S["esc_title"], True, CONFIG["G_80"]).copy()
            t.set_alpha(int(255 * a))
            self.screen.blit(t, t.get_rect(center=(W // 2, 140 + y_off)))
            pygame.draw.line(self.screen, CONFIG["G_20"], (W // 2 - 240, 180 + y_off), (W // 2 + 240, 180 + y_off))

            opts = self._esc_root_options()
            rects = self._esc_root_rects()
            for i, ((label, _), r) in enumerate(zip(opts, rects)):
                rr = (r[0], r[1] + y_off, r[2], r[3])
                selected = (i == self.esc_sel)
                if selected:
                    pygame.draw.rect(self.screen, CONFIG["G_20"], rr)
                    pygame.draw.rect(self.screen, CONFIG["C_PLAYER"], (rr[0], rr[1], 4, rr[3]))
                col = CONFIG["C_PLAYER"] if selected else CONFIG["G_80"]
                s = self.f_med.render(label, True, col).copy()
                s.set_alpha(int(255 * a))
                self.screen.blit(s, s.get_rect(center=(rr[0] + rr[2] // 2, rr[1] + rr[3] // 2)))

            hint = self.f_tiny.render(
                "↑↓ 选择  ·  ENTER 确认  ·  ESC 关闭" if self.use_cjk
                else "↑↓ select  ·  ENTER confirm  ·  ESC close",
                True, CONFIG["G_60"]).copy()
            hint.set_alpha(int(255 * a))
            self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 40)))

        elif self.esc_page == "MECHANICS":
            tabs = self.S["mech_tabs"]
            tab_rects = self._esc_mech_tab_rects()
            for i, (name, r) in enumerate(zip(tabs, tab_rects)):
                active = (i == self.esc_mech_tab)
                if active:
                    pygame.draw.rect(self.screen, CONFIG["G_20"], r)
                    pygame.draw.rect(self.screen, CONFIG["C_PLAYER"], (r[0], r[1], 3, r[3]))
                col = CONFIG["C_PLAYER"] if active else CONFIG["G_60"]
                s = self.f_head.render(name, True, col).copy()
                s.set_alpha(int(255 * a))
                self.screen.blit(s, (r[0] + 16, r[1] + 8))

            sep_x = 320
            pygame.draw.line(self.screen, CONFIG["G_20"], (sep_x, 140), (sep_x, H - 60))

            cx0 = sep_x + 40
            cy0 = 150
            cw = W - cx0 - 60

            lines = self._mech_lines_locked(self.esc_mech_tab)
            line_h = CONFIG["BODY_LINE_H"]
            para_gap = CONFIG["BODY_PARA_GAP"]

            if self.esc_mech_tab == 1:
                _cx, _cw, _cy0, _rh, _g, _bt = self._mech_ctrl_geom()
                n_rows = len(self.S["ctrl_rows"])
                view_h = _bt - _cy0
                total_h = n_rows * (_rh + _g) - _g
                self.esc_mech_max_scroll = max(0.0, total_h - view_h)
            else:
                total_h = 0
                for text, kind, req in lines:
                    if not text:
                        total_h += para_gap; continue
                    if kind == "head":
                        total_h += line_h + 6
                    else:
                        body = text if self._mech_visible(req) else self._mech_lock_text(req)
                        wrapped = self._wrap_text(body, self.f_body, cw)
                        total_h += line_h * len(wrapped) + 4
                self.esc_mech_max_scroll = max(0.0, total_h - (H - cy0 - 60))
            if self.esc_mech_scroll > self.esc_mech_max_scroll:
                self.esc_mech_scroll = self.esc_mech_max_scroll

            tab_fade = CONFIG["MECH_TAB_FADE"]
            tab_a = 1.0
            if self.esc_mech_fade > 0:
                tab_a = 1.0 - self.esc_mech_fade / tab_fade
                tab_a = max(0.4, min(1.0, tab_a))
            content_y_off = int((1.0 - tab_a) * 8) + y_off
            final_a = a * tab_a

            if self.esc_mech_tab == 1:
                self._draw_mech_controls(cx0, cw, H, final_a, content_y_off)

            y = cy0 - int(self.esc_mech_scroll) + content_y_off
            for text, kind, req in lines:
                if not text:
                    y += para_gap; continue
                vis = self._mech_visible(req)
                if kind == "head":
                    hcol = CONFIG["C_PLAYER"] if vis else CONFIG["G_40"]
                    indent = 0
                    if not vis:
                        lk = max(10.0, line_h * 0.5)
                        self._draw_padlock(cx0, y + (line_h - lk * 1.32) * 0.5,
                                           lk, CONFIG["G_40"], final_a)
                        indent = int(lk * 1.5)
                    s = self.f_head.render(text, True, hcol).copy()
                    s.set_alpha(int(255 * final_a))
                    self.screen.blit(s, (cx0 + indent, y))
                    y += line_h + 6
                    pygame.draw.line(self.screen, CONFIG["G_20"],
                                     (cx0, y - 3), (cx0 + min(cw, s.get_width() + indent + 24), y - 3))
                else:
                    body = text if vis else self._mech_lock_text(req)
                    wrapped = self._wrap_text(body, self.f_body, cw)
                    for wi, w in enumerate(wrapped):
                        if 0 < y < H - 20:
                            s = self.f_body.render(w, True,
                                                   CONFIG["G_80"] if vis else CONFIG["G_40"]).copy()
                            s.set_alpha(int(255 * final_a))
                            indent = 0
                            if not vis and wi == 0:
                                lk = max(9.0, CONFIG["BODY_LINE_H"] * 0.46)
                                self._draw_padlock(cx0, y + (line_h - lk * 1.32) * 0.4,
                                                   lk, CONFIG["G_40"], final_a)
                                indent = int(lk * 1.6)
                            self.screen.blit(s, (cx0 + indent, y))
                        y += line_h
                    y += 4

            if self.esc_mech_max_scroll > 0:
                tip = self.f_tiny.render("滚轮滚动" if self.use_cjk else "scroll",
                                         True, CONFIG["G_40"]).copy()
                tip.set_alpha(int(255 * a))
                self.screen.blit(tip, (W - tip.get_width() - 30, H - 40))

            if self.esc_mech_tab == 1:
                hint_txt = self.S["ctrl_hint"]
            else:
                hint_txt = ("↑↓ / 点击切换标签   ·   ESC 返回" if self.use_cjk
                            else "↑↓ / click to switch tabs   ·   ESC back")
            hint = self.f_tiny.render(hint_txt, True, CONFIG["G_60"]).copy()
            hint.set_alpha(int(255 * a))
            self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 20)))

        elif self.esc_page == "SETTINGS":
            t = self.f_big.render(self.S["settings"], True, CONFIG["G_80"]).copy()
            t.set_alpha(int(255 * a))
            self.screen.blit(t, t.get_rect(center=(W // 2, 110 + y_off)))
            pygame.draw.line(self.screen, CONFIG["G_20"], (W // 2 - 240, 148 + y_off), (W // 2 + 240, 148 + y_off))

            rects = self._esc_settings_rects()
            n, _sy, _rh, _gap, _bg = self._esc_settings_geom()
            last = n - 1
            clear_idx = 5 if self._esc_has_clear() else -1

            fs_txt = self.S["fs_on"] if self.fullscreen else self.S["fs_off"]
            res = f"{int(self.pw)}x{int(self.ph)}"
            rs_vals = [0.0, 1.0, 1.5, 2.0, 2.5, 3.0]
            cur_rs = float(CONFIG.get("RENDER_SCALE_PRESET", 0.0) or 0.0)
            try:
                ridx = rs_vals.index(round(cur_rs, 1))
            except ValueError:
                ridx = 0
            rs_txt = self.S["rs_names"][min(ridx, len(self.S["rs_names"]) - 1)]
            if ridx == 0:
                rs_txt = f"{rs_txt} ({int(self.pw)}x{int(self.ph)})"
            px = self.pw * self.ph
            if px > 5_800_000:
                rs_txt += " \u00b7 " + self.S["rs_heavy"]
            elif px > 3_700_000:
                rs_txt += " \u00b7 " + self.S["rs_mid"]
            levels = [0.0, 0.5, 1.0]
            try:
                sidx = levels.index(round(self.shake_level, 1))
            except ValueError:
                sidx = 2
            shake_txt = [self.S["shake_0"], self.S["shake_5"], self.S["shake_10"]][sidx]
            size_names = [self.S["text_size_std"], self.S["text_size_large"]]
            size_vals = [CONFIG["FONT_BODY_STD"], CONFIG["FONT_BODY_LARGE"]]
            try:
                tsidx = size_vals.index(self.body_size)
            except ValueError:
                tsidx = 0
            lang_txt = self.S["lang_zh"] if self.lang == "zh" else self.S["lang_en"]
            if not getattr(self, "zh_available", False):
                lang_txt = self.S["lang_en"]

            titles = [
                self.S["fullscreen_title"],
                self.S["render_scale_title"],
                self.S["shake_title"],
                self.S["text_size_title"],
                self.S["lang_title"],
            ]
            vals = [
                f"{fs_txt}   \u00b7   {res}",
                f"\u25c0  {rs_txt}  \u25b6",
                f"\u25c0  {shake_txt}  \u25b6",
                f"\u25c0  {size_names[tsidx]}  \u25b6",
                f"\u25c0  {lang_txt}  \u25b6",
            ]
            if clear_idx >= 0:
                titles.append(self.S["clear_gray"])
                vals.append("")

            pad = 24
            for i, r0 in enumerate(rects):
                rr = (r0[0], r0[1] + y_off, r0[2], r0[3])
                selected = (self.esc_sub_sel == i)
                if i == last:
                    if selected:
                        pygame.draw.rect(self.screen, CONFIG["G_20"], rr)
                        pygame.draw.rect(self.screen, CONFIG["C_PLAYER"], (rr[0], rr[1], 4, rr[3]))
                    lbl = self.f_med.render(self.S["back"], True,
                                            CONFIG["C_PLAYER"] if selected else CONFIG["G_80"]).copy()
                    lbl.set_alpha(int(255 * a))
                    self.screen.blit(lbl, lbl.get_rect(center=(rr[0] + rr[2] // 2, rr[1] + rr[3] // 2)))
                    continue
                if selected:
                    pygame.draw.rect(self.screen, CONFIG["G_20"], rr)
                    pygame.draw.rect(self.screen, CONFIG["C_PLAYER"], (rr[0], rr[1], 4, rr[3]))
                if i == clear_idx:
                    lcol = CONFIG["C_THREAT"] if selected else CONFIG["G_60"]
                    ls = self.f_med.render(self.S["clear_gray"], True, lcol).copy()
                    ls.set_alpha(int(255 * a))
                    self.screen.blit(ls, (rr[0] + pad, rr[1] + (rr[3] - ls.get_height()) // 2))
                    bar_w = rr[2] - 48
                    bar_x = rr[0] + 24
                    bar_y = rr[1] + rr[3] - 8
                    pygame.draw.rect(self.screen, CONFIG["G_20"], (bar_x, bar_y, bar_w, 3))
                    if selected and self.c_hold_frames > 0:
                        frac = min(1.0, self.c_hold_frames / CONFIG["CLEAR_HOLD_FRAMES"])
                        pygame.draw.rect(self.screen, CONFIG["C_THREAT"],
                                         (bar_x, bar_y, int(bar_w * frac), 3))
                    continue
                vcol = CONFIG["C_PLAYER"] if selected else CONFIG["G_80"]
                vs = self._fit_font_render(vals[i], vcol, max(60.0, rr[2] * 0.62)).copy()
                vs.set_alpha(int(255 * a))
                max_lbl = rr[2] - pad * 2 - vs.get_width() - 18
                ls = self._fit_font_render(titles[i], vcol, max(40.0, max_lbl)).copy()
                ls.set_alpha(int(255 * a))
                self.screen.blit(ls, (rr[0] + pad, rr[1] + (rr[3] - ls.get_height()) // 2))
                self.screen.blit(vs, (rr[0] + rr[2] - pad - vs.get_width(),
                                      rr[1] + (rr[3] - vs.get_height()) // 2))

            keys = pygame.key.get_pressed()
            if clear_idx >= 0 and self.esc_sub_sel == clear_idx and keys[pygame.K_c]:
                self.c_hold_frames += 1
                if self.c_hold_frames >= CONFIG["CLEAR_HOLD_FRAMES"]:
                    self.esc_page = "CLEAR_CONFIRM"
                    self.c_hold_frames = 0
                    self.c_hold2_frames = 0
            else:
                self.c_hold_frames = 0

            hint = self.f_tiny.render(
                "↑↓ 选择  ·  ←→ 调整  ·  ENTER 确认  ·  ESC 返回" if self.use_cjk
                else "↑↓ select  ·  ←→ adjust  ·  ENTER confirm  ·  ESC back",
                True, CONFIG["G_60"]).copy()
            hint.set_alpha(int(255 * a))
            self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

        elif self.esc_page == "CLEAR_CONFIRM":
            t = self.f_big.render(self.S["clear_page_title"], True, CONFIG["C_THREAT"]).copy()
            t.set_alpha(int(255 * a))
            self.screen.blit(t, t.get_rect(center=(W // 2, 90 + y_off)))
            pygame.draw.line(self.screen, CONFIG["G_20"], (W // 2 - 300, 130 + y_off), (W // 2 + 300, 130 + y_off))

            sd = self.save_data
            rows = [
                (self.S["best_score"], f"{int(sd['best_score'])}"),
                (self.S["best_chain"], f"{int(sd['best_chain'])}"),
                (self.S["best_wave"], f"{int(sd['best_wave'])}"),
                (self.S["stage"], f"STAGE {int(sd['training_unlocked_stage'])} / 5"),
                (self.S["detonate_count"], f"{int(sd['total_detonate'])}"),
                (self.S["perfect_count"], f"{int(sd['total_perfect'])}"),
                ("击杀" if self.use_cjk else "Total kills", f"{int(sd['total_kill'])}"),
                ("总局数" if self.use_cjk else "Total runs", f"{int(sd['total_runs'])}"),
            ]
            y0 = 160 + y_off
            for i, (lb, vv) in enumerate(rows):
                ls = self.f_body.render(lb, True, CONFIG["G_60"]).copy(); ls.set_alpha(int(255 * a))
                vs = self.f_body.render(vv, True, CONFIG["G_80"]).copy(); vs.set_alpha(int(255 * a))
                self.screen.blit(ls, (W // 2 - 260, y0 + i * 30))
                self.screen.blit(vs, (W // 2 + 260 - vs.get_width(), y0 + i * 30))

            bar_w = 400
            bar_x = W // 2 - bar_w // 2
            bar_y = H - 130
            lbl2 = self.f_body.render(self.S["clear_desc_2"], True, CONFIG["C_THREAT"]).copy()
            lbl2.set_alpha(int(255 * a))
            self.screen.blit(lbl2, lbl2.get_rect(center=(W // 2, bar_y - 28)))
            pygame.draw.rect(self.screen, CONFIG["G_20"], (bar_x, bar_y, bar_w, 5))
            keys = pygame.key.get_pressed()
            if keys[pygame.K_c]:
                self.c_hold2_frames += 1
                frac = min(1.0, self.c_hold2_frames / CONFIG["CLEAR_HOLD_FRAMES2"])
                pygame.draw.rect(self.screen, CONFIG["C_THREAT"],
                                 (bar_x, bar_y, int(bar_w * frac), 5))
                if self.c_hold2_frames >= CONFIG["CLEAR_HOLD_FRAMES2"]:
                    self._clear_save()
                    self.esc_page = "SETTINGS"
                    self.esc_sub_sel = 0
                    self.c_hold2_frames = 0
            else:
                self.c_hold2_frames = 0

            hint = self.f_tiny.render("ESC 取消" if self.use_cjk else "ESC cancel",
                                      True, CONFIG["G_60"]).copy()
            hint.set_alpha(int(255 * a))
            self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 40)))

    def _pause_controls(self) -> List[Tuple[str, str]]:
        return [
            (self.S["k_move"], self.S["k_move_d"]),
            (self.S["k_lmb"],  self.S["k_lmb_d"]),
            ("SPACE",          self.S["k_space_d"]),
            ("SHIFT",          self.S["k_shift_d"]),
            ("R",              self.S["k_r_d"]),
            ("ESC / P",        self.S["k_esc_d"]),
            ("TAB",            self.S["k_tab_d"]),
            ("F11",            self.S["k_f11_d"]),
        ]

    def _draw_pause_panel(self, W: int, H: int) -> None:
        ov = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
        ov.fill((11, 15, 20, 218))
        self.screen.blit(ov, (0, 0))

        ttl = self.f_big.render(self.S["paused"], True, CONFIG["G_80"])
        self.screen.blit(ttl, ttl.get_rect(center=(W // 2, 70)))

        panel_top = 110
        options = [
            self.S["continue"],
            self.S["restart_run"] if self.mode == "RUN" else self.S["restart_stage"],
            self.S["exit_run"],
        ]
        rects = self._pause_options_rects()
        last_opt_bottom = max(r[1] + r[3] for r in rects)
        panel_bot = last_opt_bottom + 10

        if self.mode == "TRAINING":
            mid_x = W // 2
            lx = mid_x - 470
            ly = panel_top
            hdr = self.f_small.render(self.S["goal_col"], True, CONFIG["G_60"])
            self.screen.blit(hdr, (lx, ly)); ly += 26
            st = self.stage
            name = CONFIG["STAGE_NAMES"][st-1] if self.use_cjk else STAGE_NAMES_EN[st-1]
            s_surf = self.f_med.render(f"STAGE {st} · {name}", True, CONFIG["C_PLAYER"])
            self.screen.blit(s_surf, (lx, ly)); ly += 34
            goal_desc = CONFIG["STAGE_DESCS"][st-1] if self.use_cjk else STAGE_DESCS_EN[st-1]
            g_surf = self.f_small.render(f"{self.S['progress']}: {goal_desc}", True, CONFIG["G_80"])
            self.screen.blit(g_surf, (lx, ly)); ly += 28
            hdr2 = self.f_small.render(self.S["how_to"], True, CONFIG["G_60"])
            self.screen.blit(hdr2, (lx, ly)); ly += 22
            hint_src = CONFIG["STAGE_HINTS"][st-1] if self.use_cjk else STAGE_HINTS_EN[st-1]
            for p in hint_src.split("·"):
                p = p.strip()
                if not p: continue
                h_surf = self.f_tiny.render("· " + p, True, CONFIG["G_80"])
                self.screen.blit(h_surf, (lx, ly)); ly += 18

            pygame.draw.line(self.screen, CONFIG["G_20"],
                             (mid_x, panel_top - 10), (mid_x, panel_bot))
            rx = mid_x + 40
        else:
            rx = W // 2 - 170

        ry = panel_top
        hdr = self.f_small.render(self.S["controls"], True, CONFIG["G_60"])
        self.screen.blit(hdr, (rx, ry)); ry += 28
        for key, desc in self._pause_controls():
            k_surf = self.f_small.render(key, True, CONFIG["C_PLAYER"])
            self.screen.blit(k_surf, (rx, ry))
            d_surf = self.f_tiny.render(desc, True, CONFIG["G_80"])
            self.screen.blit(d_surf, (rx + 130, ry + 3))
            ry += 22

        for i, (label, r) in enumerate(zip(options, rects)):
            rx2, ry2, rw, rh = r
            selected = (i == self.pause_sel)
            if selected:
                pygame.draw.rect(self.screen, CONFIG["G_20"], (rx2, ry2, rw, rh))
                pygame.draw.rect(self.screen, CONFIG["C_PLAYER"], (rx2, ry2, 4, rh))
            col = CONFIG["C_PLAYER"] if selected else CONFIG["G_80"]
            srf = self.f_med.render(label, True, col)
            self.screen.blit(srf, srf.get_rect(center=(rx2 + rw // 2, ry2 + rh // 2)))

        hint = self.f_tiny.render(
            "P / ESC 关闭  ·  ↑↓ / 1·2·3 选择" if self.use_cjk
            else "P / ESC close  ·  ↑↓ / 1·2·3 select",
            True, CONFIG["G_60"])
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

    def _fit_font_render(self, text: str, color, max_w: float, prefer=None):
        order = [prefer or self.f_med, self.f_small, self.f_tiny]
        for f in order:
            s = f.render(text, True, color)
            if s.get_width() <= max_w:
                return s
        return self.f_tiny.render(
            self._fit_text(self.f_tiny, text, max_w), True, color)

    def _fit_text(self, font: FTFont, text: str, max_w: float) -> str:
        if max_w <= 0:
            return ""
        if font.render(text, True, (255, 255, 255)).get_width() <= max_w:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.render(text[:mid] + "…", True, (255, 255, 255)).get_width() <= max_w:
                lo = mid
            else:
                hi = mid - 1
        return (text[:lo] + "…") if lo > 0 else ""

    def _appear_rows(self) -> int:
        return len(CONFIG["FX_NAMES"]) + 1

    def _appear_rects(self) -> List[Tuple[int, int, int, int]]:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        rh = 46
        n = self._appear_rows()
        y0 = H // 2 - (n * (rh + 10)) // 2 + 20
        return [(W // 2 - 300, y0 + i * (rh + 10), 600, rh) for i in range(n)]

    def _appear_value(self, i: int) -> str:
        if i == 0:
            return self._skin_label(self.skin)
        if i == 1:
            return (CONFIG["TRAIL_STYLES"] if self.use_cjk
                    else CONFIG["TRAIL_STYLES_EN"])[self.fx_trail]
        if i == 2:
            return self.S["on"] if self.fx_afterimage else self.S["off"]
        if i == 3:
            return self.S["on"] if self.fx_energy_glow else self.S["off"]
        if i == 4:
            return self.S["on"] if self.fx_detonate_self else self.S["off"]
        if i == 5:
            return self.S["on"] if self.fx_swap_ghost else self.S["off"]
        if i == 6:
            if not self._skin_unlocked(self._ink_index()):
                return self.S["skin_locked"]
            return self.S["on"] if self.fx_poem else self.S["off"]
        return self.S["back"]

    def _appear_step(self, i: int, d: int) -> None:
        if i == 0:
            self.skin = self._skin_cycle(d)
            self.save_data["skin"] = self.skin
        elif i == 1:
            self.fx_trail = (self.fx_trail + d) % len(CONFIG["TRAIL_STYLES"])
            self.save_data["fx_trail"] = self.fx_trail
        elif i == 2:
            self.fx_afterimage = not self.fx_afterimage
            self.save_data["fx_afterimage"] = self.fx_afterimage
        elif i == 3:
            self.fx_energy_glow = not self.fx_energy_glow
            self.save_data["fx_energy_glow"] = self.fx_energy_glow
        elif i == 4:
            self.fx_detonate_self = not self.fx_detonate_self
            self.save_data["fx_detonate_self"] = self.fx_detonate_self
        elif i == 5:
            self.fx_swap_ghost = not self.fx_swap_ghost
            self.save_data["fx_swap_ghost"] = self.fx_swap_ghost
        elif i == 6:
            if not self._skin_unlocked(self._ink_index()):
                return
            self.fx_poem = not self.fx_poem
            self.save_data["fx_poem"] = self.fx_poem
        if 0 <= i <= 6:
            save_now(CONFIG["SAVE_PATH"], self.save_data)

    def _on_appear_key(self, e) -> None:
        n = self._appear_rows()
        if e.key == pygame.K_UP:
            self.appear_sel = (self.appear_sel - 1) % n
        elif e.key == pygame.K_DOWN:
            self.appear_sel = (self.appear_sel + 1) % n
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            d = -1 if e.key == pygame.K_LEFT else 1
            if self.appear_sel < n - 1:
                self._appear_step(self.appear_sel, d)
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self.appear_sel == n - 1:
                self.appear_open = False
            elif self.appear_sel == 0:
                self.gallery_open = True
                self.gallery_sel = self.skin
            else:
                self._appear_step(self.appear_sel, 1)
        elif e.key == pygame.K_ESCAPE:
            self.appear_open = False

    def _on_appear_click(self, mx: float, my: float) -> None:
        n = self._appear_rows()
        rects = self._appear_rects()
        for i, r in enumerate(rects):
            if r[0] <= mx <= r[0] + r[2] and r[1] <= my <= r[1] + r[3]:
                if i == n - 1:
                    self.appear_open = False
                    return
                self.appear_sel = i
                if i == 0:
                    self.gallery_open = True
                    self.gallery_sel = self.skin
                else:
                    self._appear_step(i, 1)
                return

    def _draw_appear(self, W: int, H: int) -> None:
        ov = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
        ov.fill((11, 15, 20, 205))
        self.screen.blit(ov, (0, 0))

        t = self.f_head.render(self.S["appearance"], True, (235, 240, 248))
        self.screen.blit(t, t.get_rect(center=(W // 2, 100)))
        sub = self.f_small.render(self.S["appr_sub"], True, CONFIG["G_60"])
        self.screen.blit(sub, sub.get_rect(center=(W // 2, 126)))

        rects = self._appear_rects()
        n = self._appear_rows()
        for i, r in enumerate(rects):
            sel = (i == self.appear_sel)
            bg = pygame.Surface((int(r[2] * self.scale), int(r[3] * self.scale)),
                                pygame.SRCALPHA)
            bg.fill((*CONFIG["G_20"], 235))
            self.screen.blit(bg, (r[0], r[1]))
            if sel:
                pygame.draw.rect(self.screen, CONFIG["C_PLAYER"],
                                 (r[0], r[1] + 6, 4, r[3] - 12))
            if i == n - 1:
                lb = self.f_med.render(self.S["back"], True,
                                       CONFIG["C_PLAYER"] if sel else CONFIG["G_80"])
                self.screen.blit(lb, lb.get_rect(center=(r[0] + r[2] // 2,
                                                         r[1] + r[3] // 2)))
                continue
            name = self._fx_label(i)
            lc = (self._skin_text_color(self.skin, CONFIG["G_80"])
                  if i == 0 else (CONFIG["C_PLAYER"] if sel else CONFIG["G_80"]))
            lb = self.f_med.render(name, True, lc)
            self.screen.blit(lb, (r[0] + 24, r[1] + (r[3] - lb.get_height()) // 2))

            val = self._appear_value(i)
            plock = (i == 6 and not self._skin_unlocked(self._ink_index()))
            if i == 0:
                vc = self._skin_text_color(self.skin, CONFIG["G_80"])
            elif plock:
                vc = CONFIG["G_60"]
            else:
                vc = CONFIG["G_80"] if sel else CONFIG["G_60"]
            vs = self.f_med.render(val, True, vc)
            vx = r[0] + r[2] - 24
            pad = 20
            if i == 0:
                cv = self.f_small.render("›", True, CONFIG["G_60"])
                vx -= cv.get_width()
                self.screen.blit(cv, (vx, r[1] + (r[3] - cv.get_height()) // 2))
                vx -= pad // 2
                vx -= vs.get_width()
                self.screen.blit(vs, (vx, r[1] + (r[3] - vs.get_height()) // 2))
            elif plock:
                vx -= vs.get_width()
                self.screen.blit(vs, (vx, r[1] + (r[3] - vs.get_height()) // 2))
                self._draw_padlock(r[0] + 24 + lb.get_width() + 14,
                                   r[1] + r[3] / 2.0 - 8, 16, CONFIG["G_60"], 1.0)
            else:
                ar_s = self.f_small.render("▶", True, CONFIG["G_60"])
                al_s = self.f_small.render("◀", True, CONFIG["G_60"])
                vx -= ar_s.get_width()
                self.screen.blit(ar_s, (vx, r[1] + (r[3] - ar_s.get_height()) // 2))
                vx -= pad // 2
                vx -= vs.get_width()
                self.screen.blit(vs, (vx, r[1] + (r[3] - vs.get_height()) // 2))
                vx -= pad // 2
                vx -= al_s.get_width()
                self.screen.blit(al_s, (vx, r[1] + (r[3] - al_s.get_height()) // 2))

            if i == 0:
                dr = 7
                dot = self._skin_glyph(self.skin, dr, self.anim_t)
                self.screen.blit(dot, (r[0] + 24 + lb.get_width() + 14,
                                       r[1] + (r[3] - dr * 2) // 2))

        hint = self.f_tiny.render(self.S["appr_hint"], True, CONFIG["G_40"])
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

    def _skin_preview(self, i: int, rad: float, dyn: bool) -> pygame.Surface:
        s = max(0.001, float(self.scale))
        k = max(0.5, rad / 12.0)
        s2 = s * k
        wl = float(CONFIG["PV_W"])
        hl = float(CONFIG["PV_H"])
        surf = pygame.Surface((max(6, int(wl * s2)), max(6, int(hl * s2))),
                              pygame.SRCALPHA)
        old_g = _SCALE_GETTER
        old_off = _view_offset()
        old_skin = self.skin
        old_fx = self.fx
        cx = float(CONFIG["PV_CX"])
        cy = hl * 0.5
        _set_view_offset(0.0, 0.0)
        _set_scale_getter(lambda: s2)
        self.skin = i
        self.fx = surf
        old_t = self.anim_t
        if not dyn:
            self.anim_t = float(CONFIG["PV_FREEZE_T"])
        try:
            if dyn:
                pts = []
                for q in range(54):
                    u = q / 53.0
                    pts.append((cx - u * float(CONFIG["PV_TRAIL"]),
                                cy + math.sin(u * 5.0 + self.anim_t * 1.05)
                                * 4.2 * (0.30 + 0.70 * u)))
                self._trail_ink(pts, 235.0, 0.58, 3.2)
            self._draw_player_body(cx, cy)
            if dyn:
                for q in range(3):
                    phk = (self.anim_t * 0.40 + q * 0.34) % 1.0
                    ga = int(225 * (1.0 - phk) * min(1.0, phk * 5.0))
                    if ga < 6:
                        continue
                    ln = CONFIG["POEM_LINES"][q % len(CONFIG["POEM_LINES"])]
                    ch = ln[q % len(ln)]
                    try:
                        gs, gw, gh = self._poem_glyph(ch)
                    except Exception:
                        continue
                    gx = (cx + float(CONFIG["PV_GLYPH"]) + math.sin(phk * 6.0 + q * 1.7) * 2.0) * s2
                    gy = (cy - 6.0 - phk * 18.0) * s2
                    gg = gs.copy()
                    gg.set_alpha(ga)
                    surf.blit(gg, (gx - gw * 0.5, gy - gh * 0.5))
        finally:
            self.fx = old_fx
            self.skin = old_skin
            self.anim_t = old_t
            _set_scale_getter(old_g)
            _set_view_offset(old_off[0], old_off[1])
        return surf

    def _gallery_rows(self) -> int:
        return len(CONFIG["SKINS"]) + 1

    def _gallery_rects(self) -> List[Tuple[int, int, int, int]]:
        W = CONFIG["WIDTH"]
        rh = 76
        n = self._gallery_rows()
        y0 = 132
        return [(W // 2 - 330, y0 + i * (rh + 10), 660, rh) for i in range(n)]

    def _on_gallery_key(self, e) -> None:
        n = self._gallery_rows()
        if e.key == pygame.K_UP:
            self.gallery_sel = (self.gallery_sel - 1) % n
        elif e.key == pygame.K_DOWN:
            self.gallery_sel = (self.gallery_sel + 1) % n
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            d = -1 if e.key == pygame.K_LEFT else 1
            self.gallery_sel = max(0, min(n - 2, self.gallery_sel + d))
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self.gallery_sel == n - 1:
                self.gallery_open = False
            elif self._skin_unlocked(self.gallery_sel):
                self.skin = self.gallery_sel
                self.save_data["skin"] = self.skin
                save_now(CONFIG["SAVE_PATH"], self.save_data)
        elif e.key == pygame.K_ESCAPE:
            self.gallery_open = False

    def _on_gallery_click(self, mx: float, my: float) -> None:
        n = self._gallery_rows()
        for i, r in enumerate(self._gallery_rects()):
            if r[0] <= mx <= r[0] + r[2] and r[1] <= my <= r[1] + r[3]:
                if i == n - 1:
                    self.gallery_open = False
                    return
                self.gallery_sel = i
                if self._skin_unlocked(i):
                    self.skin = i
                    self.save_data["skin"] = self.skin
                    save_now(CONFIG["SAVE_PATH"], self.save_data)
                return

    def _draw_gallery(self, W: int, H: int) -> None:
        ov = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
        ov.fill((11, 15, 20, 212))
        self.screen.blit(ov, (0, 0))

        t = self.f_head.render(self.S["skin_gallery"], True, (235, 240, 248))
        self.screen.blit(t, t.get_rect(center=(W // 2, 72)))
        sub = self.f_small.render(self.S["skin_gallery_sub"], True, CONFIG["G_60"])
        self.screen.blit(sub, sub.get_rect(center=(W // 2, 100)))

        rects = self._gallery_rects()
        n = self._gallery_rows()
        rad = 16.0
        for i, r in enumerate(rects):
            bg = pygame.Surface((int(r[2] * self.scale), int(r[3] * self.scale)),
                                pygame.SRCALPHA)
            bg.fill((*CONFIG["G_20"], 235))
            self.screen.blit(bg, (r[0], r[1]))
            sel = (i == self.gallery_sel)
            unlocked = self._skin_unlocked(i)
            if not unlocked:
                dk = pygame.Surface((int(r[2] * self.scale),
                                     int(r[3] * self.scale)), pygame.SRCALPHA)
                dk.fill((6, 8, 12, 120))
                self.screen.blit(dk, (r[0], r[1]))
            if i == n - 1:
                lb = self.f_med.render(self.S["back"], True,
                                       CONFIG["C_PLAYER"] if sel else CONFIG["G_80"])
                self.screen.blit(lb, lb.get_rect(center=(r[0] + r[2] // 2,
                                                         r[1] + r[3] // 2)))
                continue
            top = bool(CONFIG["SKINS"][i].get("top"))
            if sel:
                pygame.draw.rect(self.screen, CONFIG["C_PLAYER"],
                                 (r[0], r[1] + 6, 4, r[3] - 12))
            pv = self._skin_preview(i, rad, top and unlocked)
            if not unlocked:
                pv.set_alpha(78)
            hl = float(CONFIG["PV_H"]) * max(0.5, rad / 12.0)
            self.screen.blit(pv, (r[0] + 18, r[1] + (r[3] - hl) / 2.0))
            nc = self._skin_text_color(i, CONFIG["G_80"]) if unlocked else CONFIG["G_60"]
            lb = self.f_med.render(self._skin_label(i), True, nc)
            self.screen.blit(lb, (r[0] + 112, r[1] + 18))
            if not unlocked:
                st = self.f_small.render(self._skin_req_text(i), True, CONFIG["G_60"])
                self.screen.blit(st, (r[0] + 112, r[1] + 46))
                self._draw_padlock(r[0] + r[2] - 46, r[1] + r[3] / 2.0 - 11,
                                   22, CONFIG["G_60"], 1.0)
            elif i == self.skin:
                st = self.f_small.render(self.S["skin_in_use"], True, nc)
                self.screen.blit(st, (r[0] + 112, r[1] + 46))
                mk = self.f_small.render("●", True, nc)
                self.screen.blit(mk, (r[0] + r[2] - 46,
                                      r[1] + r[3] / 2.0 - mk.get_height() / 2.0))
            else:
                st = self.f_small.render(self._skin_req_text(i), True, CONFIG["G_60"])
                self.screen.blit(st, (r[0] + 112, r[1] + 46))

        hint = self.f_tiny.render(self.S["skin_gallery_hint"], True, CONFIG["G_40"])
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 26)))

    def _draw_menu(self) -> None:
        W, H = CONFIG["WIDTH"], CONFIG["HEIGHT"]
        S = self.S
        breath = breath_wave(self.anim_t * CONFIG["ANIM_MENU_BREATH_HZ"],
                             CONFIG["ANIM_DWELL"],
                             CONFIG["ANIM_WAVE"]) * CONFIG["ANIM_MENU_BREATH_AMP"]

        off = self._menu_block_offset()
        self._draw_logo(self.screen, W // 2, CONFIG["MENU_LOGO_Y"] + off,
                        scale=CONFIG["MENU_LOGO_SCALE"], alpha=255)

        sc = self.scale if self.scale > 0 else 1.0
        title_line = self._menu_title_line()
        title_y = CONFIG["MENU_TITLE_Y"] + off + breath
        self._blit_shifted(self.screen, title_line,
                           W / 2 - (title_line[0].get_width() / sc) / 2, title_y)

        tag_line = self._menu_tagline_line()
        tag_y = CONFIG["MENU_TAG_Y"] + off + breath * 0.6
        self._blit_shifted(self.screen, tag_line,
                           W / 2 - (tag_line[0].get_width() / sc) / 2, tag_y)

        div_w = int(min(400, W * 0.34))
        pygame.draw.line(self.screen, CONFIG["G_20"],
                         (W // 2 - div_w // 2, int(CONFIG["MENU_DIV_Y"] + off)),
                         (W // 2 + div_w // 2, int(CONFIG["MENU_DIV_Y"] + off)))

        rects = self._menu_options_rects()

        sel_y = self.menu_sel_y.value
        sel_h = float(rects[0][3])
        sel_x = float(rects[0][0])
        sel_w = float(rects[0][2])
        hi = pygame.Surface((int(sel_w * self.scale), int(sel_h * self.scale)), pygame.SRCALPHA)
        hi.fill((*CONFIG["G_20"], 255))
        self.screen.blit(hi, (int(round(sel_x)), int(round(sel_y))))
        bar_x = sel_x
        bar_h = sel_h - 12
        pygame.draw.rect(self.screen, CONFIG["C_PLAYER"],
                         (int(round(bar_x)), int(round(sel_y + 6)), 4, int(bar_h)))

        period = 1.0 / max(0.01, CONFIG["ANIM_MENU_SWEEP_HZ"])
        phase = (self.anim_t % period) / period
        sweep_x = phase * (sel_w + 200) - 100
        if 0 < sweep_x < sel_w:
            pygame.draw.line(self.screen, CONFIG["C_PLAYER"],
                             (int(round(sel_x + sweep_x)), int(round(sel_y + 6))),
                             (int(round(sel_x + sweep_x)), int(round(sel_y + sel_h - 6))), 1)

        r = rects[0]
        unlocked = int(self.save_data["training_unlocked_stage"])
        sub_txt = (CONFIG["STAGE_NAMES"][self.menu_stage - 1] if self.use_cjk
                   else STAGE_NAMES_EN[self.menu_stage - 1]) if self.menu_stage <= unlocked else S["locked"]
        col = CONFIG["C_PLAYER"] if self.menu_sel == 0 else CONFIG["G_80"]
        lbl = self.f_menu.render(S["training"], True, col)
        lbl_y = r[1] + (r[3] - lbl.get_height()) // 2
        self.screen.blit(lbl, (r[0] + 24, lbl_y))
        sc = CONFIG["G_80"] if self.menu_sel == 0 else CONFIG["G_60"]

        pad = 20
        ar_s = (self.f_med.render("▶", True, CONFIG["C_PLAYER"])
                if self.menu_stage < unlocked else None)
        al_s = (self.f_med.render("◀", True, CONFIG["C_PLAYER"])
                if self.menu_stage > 1 else None)
        stage_surf = self.f_med.render(f"{S['stage']} {self.menu_stage} / 5", True, CONFIG["G_80"])
        x = r[0] + r[2] - pad
        mid_y = lambda sf: r[1] + (r[3] - sf.get_height()) // 2
        if ar_s is not None:
            x -= ar_s.get_width()
            self.screen.blit(ar_s, (x, mid_y(ar_s)))
            x -= 10
        x -= stage_surf.get_width()
        self.screen.blit(stage_surf, (x, mid_y(stage_surf)))
        if al_s is not None:
            x -= 10 + al_s.get_width()
            self.screen.blit(al_s, (x, mid_y(al_s)))

        s2_x = r[0] + 24 + lbl.get_width() + 14
        max_w = x - s2_x - 12
        if max_w > 24:
            s2 = self.f_tiny.render(self._fit_text(self.f_tiny, sub_txt, max_w), True, sc)
            self.screen.blit(s2, (s2_x, r[1] + (r[3] - s2.get_height()) // 2))

        r = rects[1]
        run_ok = bool(self.save_data.get("training_done", False))
        if run_ok:
            col = CONFIG["C_PLAYER"] if self.menu_sel == 1 else CONFIG["G_80"]
            lbl = self.f_menu.render(S["run"], True, col)
            lbl_y = r[1] + (r[3] - lbl.get_height()) // 2
            self.screen.blit(lbl, (r[0] + 24, lbl_y))
            sc = CONFIG["G_80"] if self.menu_sel == 1 else CONFIG["G_60"]
            s2_x = r[0] + 24 + lbl.get_width() + 14
            max_w = (r[0] + r[2] - 20) - s2_x - 12
            s2 = self.f_tiny.render(self._fit_text(self.f_tiny, S["run_hint"], max_w), True, sc)
            self.screen.blit(s2, (s2_x, r[1] + (r[3] - s2.get_height()) // 2))
        else:
            lbl = self.f_menu.render(S["run_locked"], True, CONFIG["G_40"])
            lbl_y = r[1] + (r[3] - lbl.get_height()) // 2
            self.screen.blit(lbl, (r[0] + 24, lbl_y))
            s2_x = r[0] + 24 + lbl.get_width() + 14
            max_w = (r[0] + r[2] - 20) - s2_x - 12
            s2 = self.f_tiny.render(self._fit_text(self.f_tiny, S["unlock_hint"], max_w),
                                    True, CONFIG["G_40"])
            self.screen.blit(s2, (s2_x, r[1] + (r[3] - s2.get_height()) // 2))

        r = rects[2]
        col = CONFIG["C_PLAYER"] if self.menu_sel == 2 else CONFIG["G_80"]
        lbl = self.f_menu.render(S["appearance"], True, col)
        lbl_y = r[1] + (r[3] - lbl.get_height()) // 2
        self.screen.blit(lbl, (r[0] + 24, lbl_y))
        sc2 = CONFIG["G_80"] if self.menu_sel == 2 else CONFIG["G_60"]
        s2_x = r[0] + 24 + lbl.get_width() + 14
        dot_r = 7
        dot = self._skin_glyph(self.skin, dot_r, self.anim_t)
        max_w = (r[0] + r[2] - 20) - s2_x - 12 - (dot_r * 2 + 10)
        nm = self._skin_label(self.skin)
        nc = self._skin_text_color(self.skin, sc2)
        s3 = self.f_small.render(self._fit_text(self.f_small, nm, max_w), True, nc)
        self.screen.blit(s3, (s2_x, r[1] + (r[3] - s3.get_height()) // 2))
        self.screen.blit(dot, (s2_x + s3.get_width() + 10,
                               r[1] + (r[3] - dot_r * 2) // 2))

        sd = self.save_data
        bests = [
            (S["best_score"], f"{int(sd['best_score'])}"),
            (S["best_chain"], f"{int(sd['best_chain'])}"),
            (S["best_wave"],  f"{int(sd['best_wave'])}"),
        ]
        sy = rects[2][1] + rects[2][3]
        stat_y = min(sy + 58, H - 118)
        bw = int(min(200, W * 0.20)); bx0 = W // 2 - (bw * len(bests)) // 2
        for i, (lb, vv) in enumerate(bests):
            cx = bx0 + i * bw + bw // 2
            l_s = self.f_tiny.render(lb, True, CONFIG["G_40"])
            v_s = self.f_med.render(vv, True, CONFIG["G_80"])
            self.screen.blit(l_s, l_s.get_rect(center=(cx, stat_y)))
            self.screen.blit(v_s, v_s.get_rect(center=(cx, stat_y + 26)))

        hint = self.f_tiny.render(S["menu_hint"], True, CONFIG["G_40"])
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 24)))

    def _draw_training_hint(self, W: int, H: int) -> None:
        stage = self.stage
        if stage < 1 or stage > 5: return
        name = CONFIG["STAGE_NAMES"][stage - 1] if self.use_cjk else STAGE_NAMES_EN[stage - 1]
        hint = CONFIG["STAGE_HINTS"][stage - 1] if self.use_cjk else STAGE_HINTS_EN[stage - 1]
        a = min(1.0, self.hint_timer / 0.5) if self.hint_timer < 0.5 else 1.0
        alpha = int(230 * a)
        b1 = self.f_med.render(f"STAGE {stage} · {name}", True, CONFIG["C_PLAYER"])
        b2 = self.f_small.render(hint, True, CONFIG["G_80"])
        t1 = b1.copy(); t1.set_alpha(alpha)
        t2 = b2.copy(); t2.set_alpha(alpha)
        self.screen.blit(t1, t1.get_rect(center=(W // 2, 150)))
        self.screen.blit(t2, t2.get_rect(center=(W // 2, 182)))

    def _draw_wave_banner(self, W: int, H: int) -> None:
        t = self.wave_flash
        a = min(1.0, t / 0.25) if t < 0.25 else 1.0
        a = min(a, min(1.0, (1.4 - t) / 0.4) if t > 1.0 else 1.0)
        alpha = int(230 * max(0.0, min(1.0, a)))
        if alpha <= 2: return
        dy = int((1.0 - min(1.0, t / 0.25)) * -14)
        t1 = self.f_big.render(f"WAVE {self.wave:02d}", True, CONFIG["C_THREAT"])
        t2 = self.f_small.render(self._wave_intro_line(), True, CONFIG["G_80"])
        s1 = t1.copy(); s1.set_alpha(alpha)
        s2 = t2.copy(); s2.set_alpha(alpha)
        self.screen.blit(s1, s1.get_rect(center=(W // 2, 190 + dy)))
        self.screen.blit(s2, s2.get_rect(center=(W // 2, 236 + dy)))

    def _draw_hud(self, W: int, H: int) -> None:
        if self.mode == "TRAINING":
            st = self.stage
            goal = CONFIG["STAGE_GOALS"][st - 1]
            if st == 1:
                prog = f"{self.stage_progress:.1f} / {goal:.0f} {self.S['seconds']}"
            else:
                prog = f"{int(self.stage_progress)} / {int(goal)}"
            h1 = self.f_small.render(f"STAGE {st}", True, CONFIG["C_PLAYER"])
            h2 = self.f_med.render(prog, True, CONFIG["G_80"])
            self.screen.blit(h1, (32, 20))
            self.screen.blit(h2, (32, 40))
        else:
            total = self.score_detonate + self.score_perfect + self.score_kill
            score_surf = self.f_big.render(f"{total}", True, CONFIG["G_80"])
            self.screen.blit(score_surf, (32, 20))
            sub = self.f_tiny.render(f"{self.t:5.1f}{self.S['seconds']}", True, CONFIG["G_60"])
            self.screen.blit(sub, (36, 84))

        if self._marks_on() and self.chain_count > 0 and self.chain_timer > 0:
            idx = min(self.chain_count - 1, len(CONFIG["CHAIN_MULTS"]) - 1)
            mult = CONFIG["CHAIN_MULTS"][idx]
            cs = self.f_chain.render(f"CHAIN  x{self.chain_count}   ×{mult}", True, (255, 255, 255))
            self.screen.blit(cs, cs.get_rect(center=(W // 2, 110)))
            bw = 240; bx = W // 2 - bw // 2
            frac = self.chain_bar_tween.value
            pygame.draw.rect(self.screen, CONFIG["G_20"], (bx, 138, bw, 2))
            pygame.draw.rect(self.screen, (255, 255, 255), (bx, 138, int(bw * frac), 2))
        elif self.chain_break_flash > 0:
            alpha = int(255 * (self.chain_break_flash / 18))
            base = self.f_chain.render("CHAIN  BREAK", True, CONFIG["C_THREAT"])
            surf = base.copy(); surf.set_alpha(alpha)
            self.screen.blit(surf, surf.get_rect(center=(W // 2, 110)))

        n_threat = len(self.ai_positions) + len(self.pending_spawns) + len(self.projectiles)
        cnt = self.f_med.render(f"{n_threat:02d}", True, CONFIG["C_THREAT"])
        self.screen.blit(cnt, (W - cnt.get_width() - 32, 22))
        tl = self.f_tiny.render("THREATS", True, CONFIG["G_60"])
        self.screen.blit(tl, (W - tl.get_width() - 32, 52))

        bx = 32
        GAP = 6
        e_val = self.energy_tween.value
        empty = e_val < CONFIG["DASH_COST"] - 1e-6
        blink = 0.5 + 0.5 * math.sin(self.anim_t * 2.0 * math.pi * 1.6)

        y = H - 44
        ey = y

        swap_y = None
        if self._shadows_on():
            swap_y = y - GAP - 11
            y = swap_y - GAP

        lives_y = None
        if self.mode == "RUN":
            lives_y = y - 9
            y = lives_y - GAP

        warn_y = y - 11

        sw, sh, sg = 26, 5, 4
        for i in range(int(CONFIG["MAX_ENERGY"])):
            sx = bx + i * (sw + sg)
            pygame.draw.rect(self.screen, CONFIG["G_20"], (sx, ey, sw, sh))
            fill = min(1.0, max(0.0, e_val - i))
            if fill > 0:
                col = CONFIG["C_PLAYER"]
                if empty:
                    col = tuple(int(round(a + (b - a) * blink))
                                for a, b in zip(CONFIG["C_PLAYER"], CONFIG["C_THREAT"]))
                pygame.draw.rect(self.screen, col,
                                 (sx, ey, int(round(sw * fill)), sh))

        if swap_y is not None:
            lbl = self.f_tiny.render("SWAP", True, CONFIG["G_60"])
            self.screen.blit(lbl, (bx, swap_y))
            cw = 120
            bar_x = bx + 42
            bar_y = swap_y + (11 - 3) // 2
            pygame.draw.rect(self.screen, CONFIG["G_20"], (bar_x, bar_y, cw, 3))
            cf = max(0.0, min(1.0, self.swap_cd_tween.value))
            pygame.draw.rect(self.screen, CONFIG["C_PLAYER"] if cf >= 0.999 else CONFIG["G_60"],
                             (bar_x, bar_y, int(round(cw * cf)), 3))

        if lives_y is not None:
            n = int(CONFIG["RUN_LIVES"])
            for i in range(n):
                sx = bx + i * 14
                alive_i = i < self.lives
                col = CONFIG["C_PLAYER"] if alive_i else CONFIG["G_20"]
                pygame.draw.rect(self.screen, col, (sx, lives_y, 9, 9))
                if alive_i:
                    pygame.draw.rect(self.screen, CONFIG["G_20"], (sx, lives_y, 9, 9), 1)
            lbl = self.f_tiny.render("命" if self.use_cjk else "LIVES", True, CONFIG["G_60"])
            self.screen.blit(lbl, (bx + n * 14 + 6, lives_y - 1))

        if empty:
            warn = self.f_tiny.render("无能量" if self.use_cjk else "NO ENERGY",
                                      True, CONFIG["C_THREAT"])
            warn.set_alpha(int(140 + 115 * blink))
            self.screen.blit(warn, (bx, warn_y))

    def _draw_practice_panel(self, W: int, H: int) -> None:
        ft = self.f_tiny.render(
            f"FRAME {self.frame:6d}   STATE {self.player_state:8s} F{self.state_frame:02d}",
            True, CONFIG["G_80"])
        self.screen.blit(ft, (W // 2 - ft.get_width() // 2, H - 60))

        if self.player_state == "BACKSWING":
            frac = self.state_frame / max(1, CONFIG["CANCEL_WINDOW_FRAMES"])
            bw = 300; bx = W // 2 - bw // 2; by = H - 42
            pygame.draw.rect(self.screen, CONFIG["G_20"], (bx, by, bw, 8))
            pygame.draw.rect(self.screen, CONFIG["C_PLAYER"], (bx, by, int(bw * (1 - frac)), 8))

        cw = 260; bx = W - cw - 32; by = 90
        pygame.draw.rect(self.screen, CONFIG["G_20"], (bx, by, cw, 3))
        if self.chain_timer > 0:
            frac = self.chain_bar_tween.value
            pygame.draw.rect(self.screen, (255, 255, 255), (bx, by, int(cw * frac), 3))

    def run(self) -> None:
        while True:
            raw_dt = self.clock.tick(CONFIG["FPS"]) / 1000.0
            self.anim_t += raw_dt
            dt = min(raw_dt, 1.0 / 30.0)

            self.handle_events()
            self._consume_resize()

            self.menu_sel_y.update(raw_dt)
            self.esc_anim.update(raw_dt)
            self.energy_tween.set_target(self.energy, CONFIG["UI_TWEEN_NORMAL"], ease_out_cubic)
            self.energy_tween.update(raw_dt)
            if self.swap_cd_frames > 0:
                target = 1.0 - self.swap_cd_frames / CONFIG["SWAP_CD_FRAMES"]
            else:
                target = 1.0
            self.swap_cd_tween.set_target(target, CONFIG["UI_TWEEN_NORMAL"], ease_out_cubic)
            self.swap_cd_tween.update(raw_dt)
            if self.chain_timer > 0:
                chain_frac = self.chain_timer / CONFIG["CHAIN_WINDOW_FRAMES"]
            else:
                chain_frac = 0.0
            self.chain_bar_tween.set_target(chain_frac, CONFIG["UI_TWEEN_FAST"], ease_out_cubic)
            self.chain_bar_tween.update(raw_dt)
            self.gameover_anim.update(raw_dt)
            self.gameover_sel_x.update(raw_dt)
            self.stage_complete_anim.update(raw_dt)

            if self.esc_open and self.esc_anim.target < 0.5 and self.esc_anim.value < 0.005:
                self.esc_open = False
                self.esc_anim.snap(0.0)

            if self.esc_open:
                self.frame += 1
                self._tick_fade(raw_dt)
                if self.esc_mech_fade > 0:
                    self.esc_mech_fade = max(0.0, self.esc_mech_fade - raw_dt)
                self._update_esc_hover()
                if self.toast_timer > 0:
                    self.toast_timer = max(0.0, self.toast_timer - raw_dt)
                self.draw()
                continue

            if self.paused:
                self._tick_fade(raw_dt)
                self.draw()
                continue

            if self.mode == "MENU":
                self.frame += 1
                self._tick_fade(raw_dt)
                if self.toast_timer > 0:
                    self.toast_timer = max(0.0, self.toast_timer - raw_dt)
                self.draw()
                continue

            if not self.game_over:
                self.update(dt)
            else:
                self._update_gameover(dt)

            self.draw()


if __name__ == "__main__":
    Game().run()