#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════╗
║        ZIGZAG_FIBO — XAUUSD Trading Bot      ║
║  ZigZag + Fibonacci Extension Signal Engine  ║
╚══════════════════════════════════════════════╝
Fibo selalu ditarik HIGH → LOW
  price(level) = LOW + level × (HIGH − LOW)
  Level  0   = Swing LOW
  Level  1   = Swing HIGH
  Level  >1  = Ekstensi ATAS HIGH  → SELL zone
  Level  <0  = Ekstensi BAWAH LOW  → BUY zone

bot_core.py — semua logika sinyal, TIDAK ada rich/termux UI.
Notifikasi Android dikirim lewat callback `notify_callback` yang
diset oleh main.py (Kivy).
"""

import json, time, os, sys, math, threading, ssl
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque

try:
    import requests
    import websocket
except ImportError:
    print("Install dulu: pip install requests websocket-client")
    sys.exit(1)

# ════════════════════════════════════════════════════════
#  KONFIGURASI
# ════════════════════════════════════════════════════════
TELEGRAM_TOKEN   = "8907814401:AAE8wgnmQMH7wGcQNJKY3YONAwGTI3xggS8"
TELEGRAM_CHAT_ID = "1887080016"
SYMBOL           = "XAU/USD"
SYMBOL_DISPLAY   = "XAUUSD"

_API_KEYS = [
    "af83933c49b64422a4c88a1efa4c7cb4",
    "9cf2234751db4b5d9f85ffd675ba1e57",
    "6fd950cafc684803ab3bf20eafe79133",
    "7d5f90b345324348a209852f371ecaac",
    "be3604e5a0264ad388b0fad4764f05cf",
    "3d80acd7c3a94fd189846f1be02bfd6b",
    "d810102731a0449abab08ebf7a796a92",
    "63570e8b46774f4e9f3fe230bb1150c3",
    "8b884e6396a54072b0e4b328a7f89c19",
    "b2c8d498c4d045eba97fbfa8288ff62c",
]

class _KeyManager:
    _LIMIT_CODES = {429}
    _LIMIT_MSGS  = ("too many","limit","credit","quota","exceeded","upgrade","api_calls_limit")

    def __init__(self, keys):
        self._keys    = list(keys)
        self._idx     = 0
        self._lock    = threading.Lock()
        self._bad     = set()
        self._rotated = 0

    @property
    def key(self):
        with self._lock:
            return self._keys[self._idx]

    @property
    def label(self):
        with self._lock:
            total  = len(self._keys)
            active = total - len(self._bad)
            return f"KEY {self._idx+1}/{total}  (active:{active}  rotated:{self._rotated})"

    def is_limit_response(self, resp_json, status_code):
        if status_code in self._LIMIT_CODES:
            return True
        code = str(resp_json.get("code",""))
        msg  = str(resp_json.get("message","")).lower()
        return code in ("429","403") or any(k in msg for k in self._LIMIT_MSGS)

    def rotate(self):
        with self._lock:
            self._bad.add(self._idx)
            for offset in range(1, len(self._keys)):
                nxt = (self._idx + offset) % len(self._keys)
                if nxt not in self._bad:
                    self._idx = nxt
                    self._rotated += 1
                    _log(f"[KEY] Rotate → key {self._idx+1}")
                    return True
            _log("[KEY] ⚠ Semua API key habis kredit!")
            return False

    def mark_ok(self):
        with self._lock:
            self._bad.discard(self._idx)

_KM = _KeyManager(_API_KEYS)

TIMEFRAMES = ["5min","15min","30min","1h","4h"]
TF_LABEL   = {"5min":"5M","15min":"15M","30min":"30M","1h":"1H","4h":"4H"}

ZZ_LOOKBACK = 5

SELL_A1 = [1.500, 1.618]
SELL_A2 = [2.000, 2.236]
BUY_A1  = [-0.500,-0.618]
BUY_A2  = [-1.000,-1.236]
SL_SELL = {1.500:1.786, 1.618:1.786, 2.000:2.414, 2.236:2.414}
SL_BUY  = {-0.500:-0.786,-0.618:-0.786,-1.000:-1.414,-1.236:-1.414}
ALL_LV  = SELL_A1+SELL_A2+BUY_A1+BUY_A2+[1.786,2.414,-0.786,-1.414,0.0,0.5,1.0]

TOUCH_TOL = 0.0003
MIN_SWING = {"5min":5.0,"15min":8.0,"30min":12.0,"1h":18.0,"4h":30.0}
UPD_INTVL = 300
SPARK_LEN = 20

# ════════════════════════════════════════════════════════
#  CALLBACK HOOK — diset oleh main.py (Kivy)
# ════════════════════════════════════════════════════════
notify_callback = None   # fn(title: str, body: str)
ui_update_callback = None  # fn() — dipanggil setiap ada update data

def _notify(title, body):
    if notify_callback:
        try:
            notify_callback(title, body)
        except Exception:
            pass

def _ui_update():
    if ui_update_callback:
        try:
            ui_update_callback()
        except Exception:
            pass

# ════════════════════════════════════════════════════════
#  STATE GLOBAL
# ════════════════════════════════════════════════════════
class State:
    def __init__(self):
        self.lock          = threading.Lock()
        self.price         = 0.0
        self.prev_price    = 0.0
        self.price_hist    = deque(maxlen=SPARK_LEN)
        self.fibo          = {}
        self.triggered     = defaultdict(set)
        self.signals_today = []
        self.active_trades = {}
        self.rsi           = {}
        self.total_signals = 0
        self.wins          = 0
        self.daily_pnl     = 0.0
        self.weekly_pnl    = 0.0
        self.monthly_pnl   = 0.0
        self.peak_pnl      = 0.0
        self.max_dd        = 0.0
        self.pnl_log       = []
        self.start_time    = datetime.now(timezone.utc)
        self.last_upd_id   = 0
        self.ws_connected  = False
        self.focus_tf      = "5min"

S = State()

# ════════════════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════════════════
_log_buf = deque(maxlen=8)
def _log(msg):
    _log_buf.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ════════════════════════════════════════════════════════
#  TELEGRAM
# ════════════════════════════════════════════════════════
def tg_send(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":cid,"text":text,"parse_mode":"HTML"},
            timeout=10
        )
        return r.json()
    except Exception as e:
        _log(f"[TG] {e}")
        return {}

def tg_get_updates():
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset":S.last_upd_id+1,"timeout":20},
            timeout=25
        )
        return r.json().get("result",[])
    except:
        return []

def tg_set_commands():
    cmds = [
        {"command":"start",   "description":"Mulai bot & info"},
        {"command":"status",  "description":"Harga live + RSI semua TF"},
        {"command":"levels",  "description":"Level Fibo semua TF"},
        {"command":"signals", "description":"Sinyal hari ini"},
        {"command":"stats",   "description":"Statistik sesi"},
        {"command":"pnl",     "description":"PnL harian/mingguan/bulanan"},
        {"command":"help",    "description":"Daftar perintah"},
    ]
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands",
            json={"commands":cmds},timeout=10)
    except:
        pass

# ════════════════════════════════════════════════════════
#  TWELVEDATA REST
# ════════════════════════════════════════════════════════
def fetch_ohlc(tf, limit=300):
    for attempt in range(len(_API_KEYS)):
        try:
            r = requests.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol":SYMBOL,"interval":tf,"outputsize":limit,
                        "apikey":_KM.key,"format":"JSON"},
                timeout=30
            )
            d = r.json()
            if _KM.is_limit_response(d, r.status_code):
                _log(f"[FETCH] key {_KM._idx+1} limit → rotate")
                if not _KM.rotate():
                    return None
                continue
            if d.get("status")=="ok" and "values" in d:
                _KM.mark_ok()
                vals = list(reversed(d["values"]))
                return {
                    "times":  [v["datetime"] for v in vals],
                    "highs":  [float(v["high"])  for v in vals],
                    "lows":   [float(v["low"])   for v in vals],
                    "closes": [float(v["close"]) for v in vals],
                }
            _log(f"[FETCH {tf}] {d.get('message','err')}")
            return None
        except Exception as e:
            _log(f"[FETCH {tf}] {e}")
            return None
    return None

# ════════════════════════════════════════════════════════
#  ZIGZAG
# ════════════════════════════════════════════════════════
def calc_zigzag(highs, lows, lb=ZZ_LOOKBACK):
    n, swings, prev = len(highs), [], None
    for i in range(lb, n-lb):
        sh = all(highs[i]>=highs[i-j] for j in range(1,lb+1)) and \
             all(highs[i]>=highs[i+j] for j in range(1,lb+1))
        sl = all(lows[i] <=lows[i-j]  for j in range(1,lb+1)) and \
             all(lows[i] <=lows[i+j]  for j in range(1,lb+1))
        if sh and not sl and prev!='H': swings.append((i,highs[i],'H')); prev='H'
        elif sl and not sh and prev!='L': swings.append((i,lows[i],'L')); prev='L'
    return swings

def last_swing_hl(swings):
    lh = ll = None
    for idx, price, t in reversed(swings):
        if t=='H' and lh is None: lh=(idx,price)
        if t=='L' and ll is None: ll=(idx,price)
        if lh and ll: break
    return lh, ll

# ════════════════════════════════════════════════════════
#  FIBONACCI  —  SELALU HIGH → LOW
# ════════════════════════════════════════════════════════
def fp(level, high, low):
    return round(low + level*(high-low), 3)

def build_levels(high, low):
    return {lv: fp(lv, high, low) for lv in ALL_LV}

# ════════════════════════════════════════════════════════
#  RSI-14
# ════════════════════════════════════════════════════════
def calc_rsi(closes, period=14):
    if len(closes) < period+1:
        return 50.0
    deltas = [closes[i]-closes[i-1] for i in range(1,len(closes))]
    gains  = [d if d>0 else 0 for d in deltas[-period:]]
    losses = [-d if d<0 else 0 for d in deltas[-period:]]
    ag, al = sum(gains)/period, sum(losses)/period
    if al==0: return 100.0
    return round(100 - 100/(1+ag/al), 1)

# ════════════════════════════════════════════════════════
#  UPDATE FIBO PER TF
# ════════════════════════════════════════════════════════
def update_tf(tf):
    label = TF_LABEL[tf]
    data  = fetch_ohlc(tf)
    if not data: return
    swings = calc_zigzag(data["highs"], data["lows"])
    if len(swings)<2: _log(f"[{label}] swing<2"); return
    lh, ll = last_swing_hl(swings)
    if not lh or not ll: _log(f"[{label}] no H/L"); return
    hi, lo = lh[1], ll[1]
    min_pts = MIN_SWING.get(tf, 10.0)
    if hi-lo < min_pts:
        _log(f"[{label}] swing {hi-lo:.2f} < min {min_pts} → skip"); return
    levels  = build_levels(hi, lo)
    rsi_val = calc_rsi(data["closes"])
    with S.lock:
        old = S.fibo.get(tf,{})
        S.fibo[tf] = {
            "high":hi,"low":lo,
            "high_time":data["times"][lh[0]],
            "low_time": data["times"][ll[0]],
            "levels":levels,
            "updated":datetime.now().strftime("%H:%M:%S")
        }
        S.rsi[tf] = rsi_val
        if old.get("high")!=hi or old.get("low")!=lo:
            S.triggered[tf].clear()
            _log(f"[{label}] NEW swing H={hi:.2f} L={lo:.2f}")
        else:
            _log(f"[{label}] H={hi:.2f} L={lo:.2f} RSI={rsi_val}")
    _ui_update()

def fibo_update_loop():
    while True:
        for tf in TIMEFRAMES:
            update_tf(tf)
            time.sleep(2)
        time.sleep(UPD_INTVL)

# ════════════════════════════════════════════════════════
#  SPARKLINE
# ════════════════════════════════════════════════════════
BLOCKS = " ▁▂▃▄▅▆▇█"

def make_sparkline(prices):
    if len(prices)<2: return "─"*SPARK_LEN
    mn, mx = min(prices), max(prices)
    rng = mx-mn or 1
    chars = []
    for p in list(prices)[-SPARK_LEN:]:
        idx = int((p-mn)/rng*(len(BLOCKS)-1))
        chars.append(BLOCKS[idx])
    return "".join(chars)

# ════════════════════════════════════════════════════════
#  PnL
# ════════════════════════════════════════════════════════
def calc_unrealized(trade, cur_price):
    entry = trade["entry"]
    if trade["type"]=="buy":
        return round((cur_price-entry)*100, 2)
    return round((entry-cur_price)*100, 2)

def update_pnl(delta):
    with S.lock:
        S.daily_pnl   += delta
        S.weekly_pnl  += delta
        S.monthly_pnl += delta
        peak = S.peak_pnl
        total = S.daily_pnl
        if total > peak: S.peak_pnl = total
        dd = peak-total
        if dd > S.max_dd: S.max_dd = dd
        S.pnl_log.append((datetime.now(timezone.utc), delta))

# ════════════════════════════════════════════════════════
#  FORMAT PETA FIBO LENGKAP
# ════════════════════════════════════════════════════════
def fibo_map_tg(levels, trig_lv):
    def q(lv): return f"<code>{levels.get(lv,0):.3f}</code>"
    def m(lv): return "  ◀ <b>ENTRY</b>" if abs(lv-trig_lv)<0.001 else ""
    return (
        f"┌── AREA SELL 2 ──────────┐\n"
        f"│🛑 SL    {q(2.414)}\n"
        f"│🔴 SELL  {q(2.236)}{m(2.236)}\n"
        f"│🔴 SELL  {q(2.000)}{m(2.0)}\n│\n"
        f"├── AREA SELL 1 ──────────┤\n"
        f"│🛑 SL    {q(1.786)}\n"
        f"│🔴 SELL  {q(1.618)}{m(1.618)}\n"
        f"│🔴 SELL  {q(1.500)}{m(1.5)}\n│\n"
        f"├── ZONA TP ──────────────┤\n"
        f"│🏁 HIGH  {q(1.000)}\n"
        f"│🎯 MID   {q(0.500)}\n"
        f"│🏁 LOW   {q(0.000)}\n│\n"
        f"├── AREA BUY 1 ───────────┤\n"
        f"│🟢 BUY   {q(-0.500)}{m(-0.5)}\n"
        f"│🟢 BUY   {q(-0.618)}{m(-0.618)}\n"
        f"│🛑 SL    {q(-0.786)}\n│\n"
        f"├── AREA BUY 2 ───────────┤\n"
        f"│🟢 BUY   {q(-1.000)}{m(-1.0)}\n"
        f"│🟢 BUY   {q(-1.236)}{m(-1.236)}\n"
        f"│🛑 SL    {q(-1.414)}\n"
        f"└─────────────────────────┘"
    )

# ════════════════════════════════════════════════════════
#  SIGNAL DETECTION
# ════════════════════════════════════════════════════════
def check_signals(price):
    with S.lock:
        snap = {tf:dict(d) for tf,d in S.fibo.items() if d}

    for tf, d in snap.items():
        levels = d["levels"]
        label  = TF_LABEL[tf]

        for area_name, area_lvs in [("Area 1",SELL_A1),("Area 2",SELL_A2)]:
            for lv in area_lvs:
                if lv not in levels: continue
                lv_p = levels[lv]
                tol  = lv_p*TOUCH_TOL
                key  = f"sell_{lv}"
                with S.lock:
                    if key in S.triggered[tf]: continue
                if abs(price-lv_p)<=tol and price>=lv_p-tol:
                    with S.lock:
                        S.triggered[tf].add(key)
                    sl  = levels.get(SL_SELL[lv], lv_p+30)
                    tp1 = levels.get(0.5, 0)
                    tp2 = levels.get(0.0, 0)
                    _emit_sell(label, area_name, lv, lv_p, sl, tp1, tp2, levels, tf)

        for area_name, area_lvs in [("Area 1",BUY_A1),("Area 2",BUY_A2)]:
            for lv in area_lvs:
                if lv not in levels: continue
                lv_p = levels[lv]
                tol  = abs(lv_p)*TOUCH_TOL
                key  = f"buy_{lv}"
                with S.lock:
                    if key in S.triggered[tf]: continue
                if abs(price-lv_p)<=tol and price<=lv_p+tol:
                    with S.lock:
                        S.triggered[tf].add(key)
                    sl  = levels.get(SL_BUY[lv], lv_p-30)
                    tp1 = levels.get(0.5, 0)
                    tp2 = levels.get(1.0, 0)
                    _emit_buy(label, area_name, lv, lv_p, sl, tp1, tp2, levels, tf)

        with S.lock:
            tc = dict(S.active_trades)
        for tid, t in tc.items():
            if t.get("be_done") or t.get("closed") or t["tf"]!=label: continue
            if t["type"]=="sell" and price<=t["tp1"]:
                with S.lock:
                    if tid in S.active_trades:
                        S.active_trades[tid]["be_done"]=True
                _emit_breakeven(label,"sell",t["entry"],t["tp1"])
                update_pnl(abs(t["entry"]-t["tp1"])*100)
                with S.lock: S.wins+=1
            elif t["type"]=="buy" and price>=t["tp1"]:
                with S.lock:
                    if tid in S.active_trades:
                        S.active_trades[tid]["be_done"]=True
                _emit_breakeven(label,"buy",t["entry"],t["tp1"])
                update_pnl(abs(t["tp1"]-t["entry"])*100)
                with S.lock: S.wins+=1

# ════════════════════════════════════════════════════════
#  EMIT SIGNALS
# ════════════════════════════════════════════════════════
def _emit_sell(tf, area, lv, price, sl, tp1, tp2, levels, raw_tf):
    ts   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    fmap = fibo_map_tg(levels, lv)
    msg  = (
        f"🔴 <b>SELL — {SYMBOL_DISPLAY}</b>  |  <b>{tf}</b>\n"
        f"⏰ {ts}\n"
        f"📍 <b>Sell {area}</b>  (Fibo {lv})\n\n"
        f"{fmap}\n\n"
        f"{'─'*27}\n"
        f"💰 Entry : <code>{price:.3f}</code>\n"
        f"🎯 TP1   : <code>{tp1:.3f}</code>\n"
        f"🎯 TP2   : <code>{tp2:.3f}</code>\n"
        f"🛑 SL    : <code>{sl:.3f}</code>\n"
        f"{'─'*27}\n"
        f"⚡ TP1 tercapai → geser SL ke <code>{price:.3f}</code>"
    )
    tg_send(msg)
    _notify(f"🔴 SELL {SYMBOL_DISPLAY} {tf}", f"Entry {price:.3f}  SL {sl:.3f}")
    sig = {"ts":ts,"tf":tf,"type":"sell","area":area,"entry":price,"sl":sl,"tp1":tp1,"tp2":tp2}
    tid = f"{raw_tf}_sell_{lv}_{int(time.time())}"
    with S.lock:
        S.signals_today.append(sig)
        S.total_signals += 1
        S.active_trades[tid] = {**sig,"be_done":False,"closed":False,"pnl":0,"raw_tf":raw_tf}
    _log(f"[SELL] {tf} {area} entry={price:.2f} SL={sl:.2f}")
    _ui_update()

def _emit_buy(tf, area, lv, price, sl, tp1, tp2, levels, raw_tf):
    ts   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    fmap = fibo_map_tg(levels, lv)
    msg  = (
        f"🟢 <b>BUY — {SYMBOL_DISPLAY}</b>  |  <b>{tf}</b>\n"
        f"⏰ {ts}\n"
        f"📍 <b>Buy {area}</b>  (Fibo {lv})\n\n"
        f"{fmap}\n\n"
        f"{'─'*27}\n"
        f"💰 Entry : <code>{price:.3f}</code>\n"
        f"🎯 TP1   : <code>{tp1:.3f}</code>\n"
        f"🎯 TP2   : <code>{tp2:.3f}</code>\n"
        f"🛑 SL    : <code>{sl:.3f}</code>\n"
        f"{'─'*27}\n"
        f"⚡ TP1 tercapai → geser SL ke <code>{price:.3f}</code>"
    )
    tg_send(msg)
    _notify(f"🟢 BUY {SYMBOL_DISPLAY} {tf}", f"Entry {price:.3f}  SL {sl:.3f}")
    sig = {"ts":ts,"tf":tf,"type":"buy","area":area,"entry":price,"sl":sl,"tp1":tp1,"tp2":tp2}
    tid = f"{raw_tf}_buy_{lv}_{int(time.time())}"
    with S.lock:
        S.signals_today.append(sig)
        S.total_signals += 1
        S.active_trades[tid] = {**sig,"be_done":False,"closed":False,"pnl":0,"raw_tf":raw_tf}
    _log(f"[BUY]  {tf} {area} entry={price:.2f} SL={sl:.2f}")
    _ui_update()

def _emit_breakeven(tf, direction, entry, tp1):
    ts  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    emo = "🟢" if direction=="buy" else "🔴"
    msg = (
        f"{emo} <b>⚡ TRAILING STOP — BREAKEVEN</b>  |  <b>{tf}</b>\n"
        f"⏰ {ts}\n"
        f"{'─'*27}\n"
        f"✅ TP1 tercapai!\n\n"
        f"📌 TP1  : <code>{tp1:.3f}</code>\n"
        f"🔁 Geser SL ke : <code>{entry:.3f}</code>\n\n"
        f"🛡 Trade aman — tidak akan balik loss!"
    )
    tg_send(msg)
    _notify("⚡ BREAKEVEN", f"{tf} {direction.upper()} TP1={tp1:.3f}")
    _log(f"[BE] {tf} {direction} TP1={tp1:.2f}")

# ════════════════════════════════════════════════════════
#  DAILY SUMMARY
# ════════════════════════════════════════════════════════
def daily_summary_loop():
    sent_today = None
    while True:
        now = datetime.now(timezone.utc)
        if now.hour==0 and now.minute==0 and sent_today!=now.date():
            sent_today = now.date()
            _send_daily_summary()
        time.sleep(30)

def _send_daily_summary():
    with S.lock:
        total = S.total_signals
        wins  = S.wins
        dpnl  = S.daily_pnl
        wpnl  = S.weekly_pnl
        mpnl  = S.monthly_pnl
        dd    = S.max_dd
        sigs  = list(S.signals_today)
        S.daily_pnl=0.0; S.signals_today.clear()
        S.total_signals=0; S.wins=0; S.max_dd=0.0; S.peak_pnl=0.0
    wr = f"{round(wins/total*100)}%" if total else "—"
    def fmt(v): return f"+{v:.2f}" if v>=0 else f"{v:.2f}"
    ts = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    sig_lines=""
    for s in sigs[-5:]:
        emo="🟢" if s["type"]=="buy" else "🔴"
        sig_lines+=f"  {emo} {s['tf']} {s['type'].upper()} {s['area']} entry <code>{s['entry']:.3f}</code>\n"
    if not sig_lines: sig_lines="  — tidak ada sinyal\n"
    msg=(
        f"📋 <b>RINGKASAN HARIAN — {SYMBOL_DISPLAY}</b>\n"
        f"📅 {ts}\n"
        f"{'─'*28}\n"
        f"📊 Total Sinyal  : <b>{total}</b>\n"
        f"✅ Win (TP1)     : <b>{wins}</b>  ({wr})\n"
        f"💹 Max Drawdown  : <code>{dd:.2f}</code>\n\n"
        f"<b>PnL Ringkasan:</b>\n"
        f"  Harian   : <code>{fmt(dpnl)}</code>\n"
        f"  Mingguan : <code>{fmt(wpnl)}</code>\n"
        f"  Bulanan  : <code>{fmt(mpnl)}</code>\n\n"
        f"<b>5 Sinyal Terakhir:</b>\n{sig_lines}"
        f"{'─'*28}\n"
        f"🤖 ZIGZAG_FIBO Bot"
    )
    tg_send(msg)

# ════════════════════════════════════════════════════════
#  TELEGRAM COMMAND HANDLER
# ════════════════════════════════════════════════════════
def _cmd_start(cid):
    tg_send(
        f"🤖 <b>ZIGZAG_FIBO BOT</b>\n\n"
        f"Trading bot XAUUSD dengan ZigZag + Fibonacci.\n"
        f"Fibo selalu ditarik <b>HIGH → LOW</b>.\n\n"
        f"<b>Commands:</b>\n"
        f"/status  — harga live + RSI\n"
        f"/levels  — level Fibo semua TF\n"
        f"/signals — sinyal hari ini\n"
        f"/stats   — statistik sesi\n"
        f"/pnl     — PnL harian/mingguan/bulanan\n"
        f"/help    — bantuan", chat_id=cid)

def _cmd_status(cid):
    with S.lock:
        price=S.price; hist=list(S.price_hist)
        rsi_d=dict(S.rsi); ws_ok=S.ws_connected
    spark=make_sparkline(hist)
    trend="▲" if len(hist)>=2 and hist[-1]>hist[-2] else "▼"
    lines=[f"📡 <b>STATUS — {SYMBOL_DISPLAY}</b>\n",
           f"💰 <b>{price:.3f}</b>  {trend}",
           f"📈 <code>{spark}</code>\n",
           f"<b>RSI-14:</b>"]
    for tf in TIMEFRAMES:
        r=rsi_d.get(tf,0)
        bar="█"*int(r/10)+"░"*(10-int(r/10))
        tag="OB" if r>70 else ("OS" if r<30 else "  ")
        lines.append(f"  {TF_LABEL[tf]}  <code>{bar}</code>  {r:.1f} {tag}")
    lines.append(f"\n🔌 WS: {'✅ Connected' if ws_ok else '❌ Offline'}")
    tg_send("\n".join(lines), chat_id=cid)

def _cmd_levels(cid):
    with S.lock:
        snap={tf:dict(d) for tf,d in S.fibo.items() if d}
    msg=f"📐 <b>LEVEL FIBO — {SYMBOL_DISPLAY}</b>\n"
    for tf in TIMEFRAMES:
        d=snap.get(tf)
        if not d: continue
        lv=d["levels"]; lb=TF_LABEL[tf]
        msg+=(
            f"\n<b>── {lb} ──</b>  H:<code>{d['high']:.3f}</code>  L:<code>{d['low']:.3f}</code>\n"
            f"  🛑S2 SL <code>{lv.get(2.414,0):.3f}</code>\n"
            f"  🔴S2    <code>{lv.get(2.236,0):.3f}</code> / <code>{lv.get(2.000,0):.3f}</code>\n"
            f"  🛑S1 SL <code>{lv.get(1.786,0):.3f}</code>\n"
            f"  🔴S1    <code>{lv.get(1.618,0):.3f}</code> / <code>{lv.get(1.500,0):.3f}</code>\n"
            f"  🏁HIGH  <code>{lv.get(1.000,0):.3f}</code>\n"
            f"  🎯MID   <code>{lv.get(0.500,0):.3f}</code>\n"
            f"  🏁LOW   <code>{lv.get(0.000,0):.3f}</code>\n"
            f"  🟢B1    <code>{lv.get(-0.500,0):.3f}</code> / <code>{lv.get(-0.618,0):.3f}</code>\n"
            f"  🛑B1 SL <code>{lv.get(-0.786,0):.3f}</code>\n"
            f"  🟢B2    <code>{lv.get(-1.000,0):.3f}</code> / <code>{lv.get(-1.236,0):.3f}</code>\n"
            f"  🛑B2 SL <code>{lv.get(-1.414,0):.3f}</code>\n"
        )
    tg_send(msg, chat_id=cid)

def _cmd_signals(cid):
    with S.lock: sigs=list(S.signals_today)
    if not sigs: tg_send("📭 Belum ada sinyal hari ini.", chat_id=cid); return
    msg=f"📋 <b>SINYAL HARI INI — {SYMBOL_DISPLAY}</b>\n\n"
    for s in sigs[-10:]:
        emo="🟢" if s["type"]=="buy" else "🔴"
        msg+=(f"{emo} <b>{s['tf']}</b> {s['type'].upper()} {s['area']}\n"
              f"   Entry:<code>{s['entry']:.3f}</code>  "
              f"SL:<code>{s['sl']:.3f}</code>  "
              f"TP1:<code>{s['tp1']:.3f}</code>\n"
              f"   {s['ts']}\n\n")
    tg_send(msg, chat_id=cid)

def _cmd_stats(cid):
    with S.lock:
        total=S.total_signals; wins=S.wins
        dpnl=S.daily_pnl; dd=S.max_dd
        up=datetime.now(timezone.utc)-S.start_time
    wr=f"{round(wins/total*100)}%" if total else "—"
    pnl_str=f"+{dpnl:.2f}" if dpnl>=0 else f"{dpnl:.2f}"
    tg_send(
        f"📊 <b>STATISTIK SESI</b>\n"
        f"{'─'*22}\n"
        f"⏱ Uptime        : {str(up).split('.')[0]}\n"
        f"📡 Total Sinyal  : <b>{total}</b>\n"
        f"✅ Win (TP1)     : <b>{wins}</b>  ({wr})\n"
        f"💹 PnL Harian    : <code>{pnl_str}</code>\n"
        f"📉 Max Drawdown  : <code>{dd:.2f}</code>",
        chat_id=cid)

def _cmd_pnl(cid):
    with S.lock:
        dpnl=S.daily_pnl; wpnl=S.weekly_pnl; mpnl=S.monthly_pnl
    def fmt(v): return f"+{v:.2f}" if v>=0 else f"{v:.2f}"
    tg_send(
        f"💹 <b>PnL RINGKASAN — {SYMBOL_DISPLAY}</b>\n"
        f"{'─'*22}\n"
        f"Harian   : <code>{fmt(dpnl)}</code>\n"
        f"Mingguan : <code>{fmt(wpnl)}</code>\n"
        f"Bulanan  : <code>{fmt(mpnl)}</code>",
        chat_id=cid)

def telegram_poll_loop():
    tg_set_commands()
    while True:
        try:
            updates=tg_get_updates()
            for upd in updates:
                uid=upd.get("update_id",0)
                with S.lock:
                    if uid<=S.last_upd_id: continue
                    S.last_upd_id=uid
                msg=upd.get("message",{})
                txt=msg.get("text","").strip().lower().split("@")[0]
                cid=str(msg.get("chat",{}).get("id",""))
                if   txt=="/start":   _cmd_start(cid)
                elif txt=="/status":  _cmd_status(cid)
                elif txt=="/levels":  _cmd_levels(cid)
                elif txt=="/signals": _cmd_signals(cid)
                elif txt=="/stats":   _cmd_stats(cid)
                elif txt=="/pnl":     _cmd_pnl(cid)
                elif txt in ("/help","/?"):
                    _cmd_start(cid)
        except Exception as e:
            _log(f"[POLL] {e}")
        time.sleep(2)

# ════════════════════════════════════════════════════════
#  WEBSOCKET TWELVEDATA
# ════════════════════════════════════════════════════════
def on_open(ws):
    with S.lock: S.ws_connected=True
    ws.send(json.dumps({"action":"subscribe","params":{"symbols":SYMBOL}}))
    _log("[WS] Connected & subscribed")
    _ui_update()

def on_message(ws, raw):
    try:
        data=json.loads(raw)
        event=data.get("event","")
        if event=="price":
            p=float(data.get("price",0))
            if p>0:
                with S.lock:
                    S.prev_price=S.price
                    S.price=p
                    S.price_hist.append(p)
                check_signals(p)
                _ui_update()
        elif event=="subscribe-status":
            _log(f"[WS] {data.get('status')} {data.get('symbol','')}")
    except Exception as e:
        _log(f"[WS msg] {e}")

def on_error(ws, err):
    with S.lock: S.ws_connected=False
    _log(f"[WS err] {err}")
    _ui_update()

def on_close(ws, code, msg):
    with S.lock: S.ws_connected=False
    _log("[WS] Closed, reconnect 5s...")
    _ui_update()
    time.sleep(5)
    _start_ws()

def _fetch_rest_price():
    """Ambil harga terkini via REST (fallback saat WS offline)."""
    try:
        r = requests.get(
            "https://api.twelvedata.com/price",
            params={"symbol": SYMBOL, "apikey": _KM.key},
            timeout=10,
        )
        d = r.json()
        p = float(d.get("price", 0))
        if p > 0:
            with S.lock:
                S.prev_price = S.price
                S.price = p
                S.price_hist.append(p)
            check_signals(p)
            _ui_update()
    except Exception as e:
        _log(f"[REST price] {e}")

def _rest_price_fallback_loop():
    """Polling REST setiap 5 detik jika WS offline."""
    while True:
        time.sleep(5)
        with S.lock:
            ws_ok = S.ws_connected
        if not ws_ok:
            _fetch_rest_price()

def _start_ws():
    url = f"wss://ws.twelvedata.com/v1/quotes/price?apikey={_KM.key}"
    ws  = websocket.WebSocketApp(
        url,
        on_open=on_open, on_message=on_message,
        on_error=on_error, on_close=on_close,
    )
    ws.run_forever(
        ping_interval=30,
        ping_timeout=10,
        sslopt={"cert_reqs": ssl.CERT_NONE},   # fix SSL cert error Android
    )

# ════════════════════════════════════════════════════════
#  STARTUP MESSAGE
# ════════════════════════════════════════════════════════
def send_startup():
    ts=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    tg_send(
        f"🤖 <b>ZIGZAG_FIBO BOT — AKTIF</b>\n"
        f"⏰ {ts}\n"
        f"{'─'*26}\n"
        f"📊 Indikator : ZigZag + Fibonacci\n"
        f"💱 Pair      : {SYMBOL_DISPLAY}\n"
        f"⏱ Timeframe : 5M · 15M · 30M · 1H · 4H\n"
        f"📐 Fibo arah : HIGH → LOW\n\n"
        f"<b>Zona Sinyal:</b>\n"
        f"🔴 Sell Area 1  Fibo 1.500 / 1.618  SL→1.786\n"
        f"🔴 Sell Area 2  Fibo 2.000 / 2.236  SL→2.414\n"
        f"🟢 Buy  Area 1  Fibo -0.500/-0.618  SL→-0.786\n"
        f"🟢 Buy  Area 2  Fibo -1.000/-1.236  SL→-1.414\n"
        f"{'─'*26}\n"
        f"✅ Live monitoring aktif!\n"
        f"Ketik /help untuk daftar perintah."
    )

# ════════════════════════════════════════════════════════
#  START BOT (dipanggil oleh main.py)
# ════════════════════════════════════════════════════════
def _initial_fetch():
    """Fetch data awal semua TF di background — tidak memblokir startup."""
    _log("[BOT] Fetch data awal di background...")
    for tf in TIMEFRAMES:
        update_tf(tf)
        time.sleep(1)
    _log("[BOT] Fetch data awal selesai.")
    _ui_update()

def start_bot():
    """Jalankan semua thread background; kirim Telegram langsung tanpa delay."""
    # 1. Kirim notif Telegram SEGERA — tidak perlu tunggu fetch data
    threading.Thread(target=send_startup, daemon=True, name="startup_tg").start()

    # 2. Fetch data awal secara paralel di background
    threading.Thread(target=_initial_fetch,              daemon=True, name="init_fetch").start()

    # 3. Semua thread operasional
    threading.Thread(target=fibo_update_loop,            daemon=True, name="fibo").start()
    threading.Thread(target=daily_summary_loop,          daemon=True, name="daily").start()
    threading.Thread(target=telegram_poll_loop,          daemon=True, name="tg_poll").start()
    threading.Thread(target=_start_ws,                   daemon=True, name="ws").start()
    threading.Thread(target=_rest_price_fallback_loop,   daemon=True, name="rest_price").start()
    _log("[BOT] Semua thread berjalan.")
