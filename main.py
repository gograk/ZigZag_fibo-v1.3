#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIGZAG_FIBO BY GOGRAK — Android APK UI (Kivy)
Versi v6: responsif penuh (auto-scale ke semua layar Android).
Semua logika sinyal ada di bot_core.py (tidak diubah).
Icon murni dari View/Shape — tanpa font, dijamin tampil semua Android.
"""

import threading
from datetime import datetime, timezone

# ── Kivy config SEBELUM import kivy lainnya ──────────────
from kivy.config import Config
Config.set('graphics', 'width',  '400')
Config.set('graphics', 'height', '800')
Config.set('kivy',     'window_icon', '')

from kivy.app         import App
from kivy.uix.boxlayout  import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label      import Label
from kivy.uix.button     import Button
from kivy.uix.widget     import Widget
from kivy.clock          import Clock
from kivy.core.window    import Window
from kivy.graphics       import Color, Rectangle, RoundedRectangle, Line, Ellipse

Window.clearcolor = (0.04, 0.04, 0.07, 1)

import bot_core as bot

APP_TITLE = "ZIGZAG_FIBO BY GOGRAK"

# ════════════════════════════════════════════════════════
#  RESPONSIVE SCALE  —  SP = scale-factor (1.0 @ 400 px lebar)
# ════════════════════════════════════════════════════════
def _sp():
    """Hitung scale factor berdasarkan lebar layar aktual."""
    return max(0.72, min(1.60, Window.width / 400.0))

# ── Notification ─────────────────────────────────────────
def _send_android_notif(title, body):
    try:
        from plyer import notification
        notification.notify(title=title, message=body,
                            app_name=APP_TITLE, timeout=5)
    except Exception:
        pass

bot.notify_callback = _send_android_notif

# ════════════════════════════════════════════════════════
#  STATUS TRACKING
# ════════════════════════════════════════════════════════
_sig_status = {}

def _sig_key(sig):
    return f"{sig['ts']}|{sig['tf']}|{sig['type']}|{sig['entry']:.3f}"

def _refresh_statuses():
    with bot.S.lock:
        trades  = dict(bot.S.active_trades)
        signals = list(bot.S.signals_today)
        price   = bot.S.price

    for sig in signals:
        key = _sig_key(sig)
        if key in _sig_status and _sig_status[key] in ("WIN", "LOSS"):
            continue
        matched = None
        for tid, t in trades.items():
            if (t.get('ts') == sig['ts'] and t['tf'] == sig['tf']
                    and t['type'] == sig['type']
                    and abs(t['entry'] - sig['entry']) < 0.01):
                matched = t; break
        if matched:
            if matched.get('be_done'):
                _sig_status[key] = "WIN"
            elif price > 0:
                if sig['type'] == 'sell' and price >= sig['sl']:
                    _sig_status[key] = "LOSS"
                elif sig['type'] == 'buy' and price <= sig['sl']:
                    _sig_status[key] = "LOSS"
                else:
                    _sig_status.setdefault(key, "OPEN")
        else:
            _sig_status.setdefault(key, "PENDING")

# ════════════════════════════════════════════════════════
#  WIDGET HELPERS
# ════════════════════════════════════════════════════════
def lbl(text, size=13, bold=False, color=(1, 1, 1, 1),
        halign='left', valign='middle', **kw):
    sp = _sp()
    l = Label(text=text, font_size=size * sp, bold=bold, color=color,
               halign=halign, valign=valign,
               size_hint_y=None, markup=True, **kw)
    l.bind(texture_size=l.setter('size'))
    return l

def _add_bg(widget, color, radius=0):
    with widget.canvas.before:
        Color(*color)
        if radius:
            widget._bg = RoundedRectangle(pos=widget.pos,
                                           size=widget.size,
                                           radius=[radius * _sp()])
        else:
            widget._bg = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                size=lambda w, v: setattr(w._bg, 'size', v))

def h_sep(height=1, color=(0.14, 0.16, 0.21, 1)):
    w = Widget(size_hint_y=None, height=height)
    _add_bg(w, color)
    return w

def section_title(text):
    sp = _sp()
    box = BoxLayout(size_hint_y=None, height=int(28 * sp), padding=[0, 4])
    l = Label(text=f"[b]{text}[/b]", font_size=11 * sp,
               color=(0.55, 0.55, 0.55, 1),
               markup=True, halign='left', valign='middle', size_hint_y=None)
    l.bind(texture_size=l.setter('size'))
    box.add_widget(l)
    return box

def pill_btn(text, active=False, width=None):
    sp = _sp()
    w  = int((width or 60) * sp)
    btn = Button(text=text,
                 size_hint=(None, None),
                 size=(w, int(30 * sp)),
                 font_size=int(11 * sp),
                 bold=active,
                 background_normal='',
                 background_color=(0, 0, 0, 0))
    gold = (1, 0.78, 0, 1)
    dim  = (0.18, 0.20, 0.26, 1)
    _add_bg(btn, gold if active else dim, radius=14)
    btn.color = (0.05, 0.05, 0.08, 1) if active else (0.7, 0.7, 0.7, 1)
    return btn

# ════════════════════════════════════════════════════════
#  CUSTOM ICONS (murni Shape — tidak butuh font)
# ════════════════════════════════════════════════════════
def _icon_grid(parent, color):
    """3×3 grid icon untuk tab Dashboard."""
    with parent.canvas:
        Color(*color)
        for r in range(3):
            for c in range(3):
                Rectangle(pos=(parent.x + c*7 + 3, parent.y + r*7 + 3),
                          size=(5, 5))
    def _redraw(w, *_):
        w.canvas.clear()
        with w.canvas:
            Color(*color)
            for r2 in range(3):
                for c2 in range(3):
                    Rectangle(pos=(w.x + c2*7 + 3, w.y + r2*7 + 3),
                              size=(5, 5))
    parent.bind(pos=_redraw, size=_redraw)

def _icon_bars(parent, color):
    """Bar-chart icon untuk tab Sinyal."""
    heights = [8, 14, 10, 18, 12]
    def _draw(w, *_):
        w.canvas.clear()
        with w.canvas:
            Color(*color)
            for i, h in enumerate(heights):
                Rectangle(pos=(w.x + i * 6 + 2, w.y + 2), size=(4, h))
    parent.bind(pos=_draw, size=_draw)
    _draw(parent)

def _icon_zigzag(parent, color):
    """ZigZag line icon untuk tab Fibo."""
    def _draw(w, *_):
        w.canvas.clear()
        with w.canvas:
            Color(*color)
            pts = [w.x+2, w.y+6, w.x+8, w.y+18, w.x+14, w.y+4,
                   w.x+20, w.y+16, w.x+26, w.y+8]
            Line(points=pts, width=2)
    parent.bind(pos=_draw, size=_draw)
    _draw(parent)

# ════════════════════════════════════════════════════════
#  BOTTOM NAV
# ════════════════════════════════════════════════════════
class BottomNav(BoxLayout):
    def __init__(self, on_switch, **kw):
        sp = _sp()
        super().__init__(orientation='horizontal',
                         size_hint_y=None, height=int(62 * sp), **kw)
        _add_bg(self, (0.07, 0.08, 0.12, 1))
        self._on_switch = on_switch
        self._btns      = {}
        self._icons     = {}

        items = [
            ('dashboard', _icon_grid,   'Dashboard'),
            ('sinyal',    _icon_bars,   'Sinyal'),
            ('fibo',      _icon_zigzag, 'Fibo'),
        ]

        for key, icon_fn, label_text in items:
            col = BoxLayout(orientation='vertical', padding=[0, int(6*sp)])

            icon_w = Widget(size_hint=(None, None),
                            size=(int(28*sp), int(28*sp)))
            icon_fn(icon_w, (0.4, 0.4, 0.4, 1))

            icon_row = BoxLayout(size_hint_y=None, height=int(28*sp))
            icon_row.add_widget(Widget())
            icon_row.add_widget(icon_w)
            icon_row.add_widget(Widget())

            txt_l = lbl(label_text, size=9, halign='center',
                        color=(0.45, 0.45, 0.45, 1))
            col.add_widget(icon_row)
            col.add_widget(txt_l)

            btn = Button(background_color=(0,0,0,0), background_normal='')
            btn.add_widget(col)
            btn.bind(on_press=lambda b, k=key: self._tap(k))
            self._btns[key]  = (btn, icon_w, txt_l, icon_fn)
            self.add_widget(btn)

        self._set_active('dashboard')

    def _tap(self, key):
        self._set_active(key)
        self._on_switch(key)

    def set_active(self, key):
        self._set_active(key)

    def _set_active(self, key):
        gold = (1, 0.78, 0, 1)
        dim  = (0.38, 0.38, 0.38, 1)
        for k, (btn, icon_w, txt_l, icon_fn) in self._btns.items():
            c = gold if k == key else dim
            icon_fn(icon_w, c)
            txt_l.color = c

# ════════════════════════════════════════════════════════
#  TAB: DASHBOARD
# ════════════════════════════════════════════════════════
class DashTab(ScrollView):
    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        sp   = _sp()
        root = BoxLayout(orientation='vertical',
                         padding=[int(14*sp), int(10*sp)],
                         spacing=int(10*sp), size_hint_y=None)
        root.bind(minimum_height=root.setter('height'))

        # ── Price Card ────────────────────────────────
        card_h = int(140 * sp)
        price_box = BoxLayout(orientation='vertical', spacing=int(4*sp),
                               size_hint_y=None, height=card_h,
                               padding=[0, int(10*sp)])
        _add_bg(price_box, (0.09, 0.11, 0.16, 1), radius=10)

        self.ws_lbl    = lbl("HARGA LIVE", size=11,
                              color=(0.25, 0.85, 0.85, 1), halign='center')
        self.sym_lbl   = lbl("XAUUSD", size=12,
                              color=(0.55, 0.55, 0.55, 1), halign='center')
        self.price_lbl = lbl("—", size=34, bold=True,
                              color=(1, 1, 1, 1), halign='center')
        self.chg_lbl   = lbl("", size=13, halign='center')

        for w in (self.ws_lbl, self.sym_lbl, self.price_lbl, self.chg_lbl):
            price_box.add_widget(w)
        root.add_widget(price_box)

        # ── RSI ───────────────────────────────────────
        root.add_widget(section_title("RSI-14 per Timeframe"))
        rsi_box = BoxLayout(size_hint_y=None, height=int(58*sp),
                             padding=[int(6*sp), int(4*sp)], spacing=2)
        _add_bg(rsi_box, (0.09, 0.11, 0.16, 1), radius=10)

        self.rsi_cells = {}
        for tf in bot.TIMEFRAMES:
            col = BoxLayout(orientation='vertical', spacing=2)
            name_l = lbl(bot.TF_LABEL[tf], size=10,
                          color=(0.5, 0.5, 0.5, 1), halign='center')
            val_l  = lbl("—", size=14, bold=True,
                          halign='center', color=(1, 1, 1, 1))
            col.add_widget(name_l)
            col.add_widget(val_l)
            self.rsi_cells[tf] = val_l
            rsi_box.add_widget(col)
        root.add_widget(rsi_box)

        # ── Stats ─────────────────────────────────────
        root.add_widget(section_title("Statistik Sesi"))
        stats_grid = BoxLayout(orientation='vertical',
                                size_hint_y=None, spacing=1)
        stats_grid.bind(minimum_height=stats_grid.setter('height'))
        _add_bg(stats_grid, (0.09, 0.11, 0.16, 1), radius=10)

        self.stat_labels = {}
        for key, title in [("signal", "Total Sinyal"), ("win", "Win (TP1)"),
                            ("wr",    "Win Rate"),     ("pnl", "PnL Harian"),
                            ("dd",    "Max Drawdown"), ("uptime", "Uptime")]:
            row = BoxLayout(size_hint_y=None, height=int(34*sp),
                             padding=[int(12*sp), 0])
            _add_bg(row, (0.09, 0.11, 0.16, 1))
            lbl_t = lbl(title, size=12, color=(0.6, 0.6, 0.6, 1))
            lbl_v = lbl("—",   size=13, bold=True, color=(1, 1, 1, 1),
                         halign='right')
            row.add_widget(lbl_t)
            row.add_widget(lbl_v)
            self.stat_labels[key] = lbl_v
            stats_grid.add_widget(row)
            stats_grid.add_widget(h_sep())
        root.add_widget(stats_grid)

        # ── Activity Log ──────────────────────────────
        root.add_widget(section_title("Log Aktivitas"))
        log_box = BoxLayout(orientation='vertical',
                             size_hint_y=None, spacing=0,
                             padding=[int(12*sp), int(6*sp)])
        log_box.bind(minimum_height=log_box.setter('height'))
        _add_bg(log_box, (0.09, 0.11, 0.16, 1), radius=10)
        self.log_box = log_box
        root.add_widget(log_box)

        # ── WS status bar ─────────────────────────────
        self.ws_bar = BoxLayout(size_hint_y=None, height=int(28*sp),
                                 padding=[int(12*sp), 0])
        _add_bg(self.ws_bar, (0.07, 0.08, 0.12, 1))
        self.ws_status = lbl("WS: --", size=10,
                              color=(0.4, 0.4, 0.4, 1))
        self.ws_bar.add_widget(self.ws_status)
        root.add_widget(self.ws_bar)

        self.add_widget(root)

    def refresh(self):
        with bot.S.lock:
            price    = bot.S.price
            prev     = bot.S.prev_price
            rsi_d    = dict(bot.S.rsi)
            total    = bot.S.total_signals
            wins     = bot.S.wins
            dpnl     = bot.S.daily_pnl
            dd       = bot.S.max_dd
            start    = bot.S.start_time
            ws_ok    = bot.S.ws_connected

        # Price
        if price > 0:
            chg  = price - prev
            sign = "+" if chg >= 0 else ""
            col  = (0.2, 0.9, 0.4, 1) if chg >= 0 else (0.9, 0.3, 0.3, 1)
            self.price_lbl.text  = f"{price:.3f}"
            self.chg_lbl.text    = f"{sign}{chg:.3f}"
            self.chg_lbl.color   = col

        # WS indicator
        if ws_ok:
            self.ws_lbl.text  = "LIVE  •"
            self.ws_lbl.color = (0.2, 0.9, 0.5, 1)
        else:
            self.ws_lbl.text  = "OFFLINE  ○"
            self.ws_lbl.color = (0.9, 0.3, 0.3, 1)

        # RSI cells
        for tf in bot.TIMEFRAMES:
            r   = rsi_d.get(tf, 0)
            lbl_w = self.rsi_cells[tf]
            if r == 0:
                lbl_w.text  = "—"
                lbl_w.color = (0.5, 0.5, 0.5, 1)
            else:
                lbl_w.text = f"{r:.0f}"
                if r >= 70:
                    lbl_w.color = (0.95, 0.35, 0.35, 1)
                elif r <= 30:
                    lbl_w.color = (0.3, 0.85, 0.45, 1)
                else:
                    lbl_w.color = (0.85, 0.85, 0.85, 1)

        # Stats
        wr  = f"{round(wins/total*100)}%" if total else "—"
        up  = datetime.now(timezone.utc) - start
        up_str = str(up).split('.')[0]
        pnl_str = (f"+{dpnl:.2f}" if dpnl >= 0 else f"{dpnl:.2f}")
        dd_str  = f"{dd:.2f}"
        self.stat_labels["signal"].text = str(total)
        self.stat_labels["win"].text    = str(wins)
        self.stat_labels["wr"].text     = wr
        self.stat_labels["pnl"].text    = pnl_str
        self.stat_labels["pnl"].color   = ((0.2,0.9,0.4,1) if dpnl>=0
                                           else (0.9,0.3,0.3,1))
        self.stat_labels["dd"].text     = dd_str
        self.stat_labels["uptime"].text = up_str

        # Log
        logs = list(bot._log_buf)
        self.log_box.clear_widgets()
        if not logs:
            self.log_box.add_widget(
                lbl("Belum ada aktivitas.", size=11,
                    color=(0.4, 0.4, 0.4, 1)))
        for line in reversed(logs[-6:]):
            self.log_box.add_widget(
                lbl(line, size=10, color=(0.55, 0.65, 0.75, 1)))

        # WS status bar
        ws_txt = "WebSocket: Connected" if ws_ok else "WebSocket: Offline (REST fallback)"
        self.ws_status.text  = ws_txt
        self.ws_status.color = ((0.3,0.9,0.5,1) if ws_ok
                                else (0.9,0.5,0.3,1))

# ════════════════════════════════════════════════════════
#  TAB: SINYAL
# ════════════════════════════════════════════════════════
_STATUS_CFG = {
    "WIN":     ((0.15, 0.65, 0.30, 1), "WIN"),
    "LOSS":    ((0.75, 0.15, 0.15, 1), "LOSS"),
    "OPEN":    ((0.75, 0.45, 0.05, 1), "OPEN"),
    "PENDING": ((0.18, 0.20, 0.28, 1), "PENDING"),
}

class SinyalTab(BoxLayout):
    def __init__(self, **kw):
        sp = _sp()
        super().__init__(orientation='vertical',
                         padding=[0, 0], spacing=0, **kw)

        # Filter row
        filter_row = BoxLayout(size_hint_y=None, height=int(48*sp),
                                padding=[int(10*sp), int(8*sp)],
                                spacing=int(6*sp))
        _add_bg(filter_row, (0.07, 0.09, 0.13, 1))

        self._active_filter = "ALL"
        self._filter_btns   = {}
        for f in ("ALL","OPEN","WIN","LOSS","PENDING"):
            btn = pill_btn(f, active=(f == "ALL"), width=58)
            btn.bind(on_press=lambda b, flt=f: self._set_filter(flt))
            self._filter_btns[f] = btn
            filter_row.add_widget(btn)
        self.add_widget(filter_row)

        count_row = BoxLayout(size_hint_y=None, height=int(26*sp),
                               padding=[int(12*sp), 2])
        self.count_lbl = lbl("0 sinyal", size=10,
                              color=(0.45, 0.45, 0.45, 1))
        count_row.add_widget(self.count_lbl)
        self.add_widget(count_row)

        sv = ScrollView(size_hint=(1, 1))
        self.sig_box = BoxLayout(orientation='vertical', spacing=int(6*sp),
                                  size_hint_y=None,
                                  padding=[int(10*sp), int(4*sp)])
        self.sig_box.bind(minimum_height=self.sig_box.setter('height'))
        sv.add_widget(self.sig_box)
        self.add_widget(sv)

    def _set_filter(self, flt):
        self._active_filter = flt
        gold = (1, 0.78, 0, 1)
        dim  = (0.18, 0.20, 0.26, 1)
        sp   = _sp()
        for f, btn in self._filter_btns.items():
            btn.canvas.before.clear()
            _add_bg(btn, gold if f == flt else dim, radius=14)
            btn.color = ((0.05, 0.05, 0.08, 1) if f == flt
                         else (0.7, 0.7, 0.7, 1))
        self.refresh()

    def refresh(self):
        sp = _sp()
        with bot.S.lock:
            signals = list(bot.S.signals_today)
            price   = bot.S.price

        flt = self._active_filter
        filtered = []
        for sig in reversed(signals):
            key = _sig_key(sig)
            st  = _sig_status.get(key, "PENDING")
            if flt == "ALL" or st == flt:
                filtered.append((sig, st))

        self.count_lbl.text = f"{len(filtered)} sinyal ditemukan"
        self.sig_box.clear_widgets()

        if not filtered:
            empty = lbl("Belum ada sinyal.", size=12,
                        color=(0.4, 0.4, 0.4, 1), halign='center')
            self.sig_box.add_widget(empty)
            return

        for sig, st in filtered[:40]:
            col_bg, st_text = _STATUS_CFG.get(st, ((0.12,0.13,0.18,1), st))
            card = BoxLayout(orientation='vertical',
                             size_hint_y=None, height=int(90*sp),
                             padding=[int(10*sp), int(6*sp)], spacing=2)
            _add_bg(card, (0.10, 0.12, 0.17, 1), radius=8)

            emo  = "S" if sig['type'] == 'sell' else "B"
            t_col = (0.95,0.30,0.30,1) if sig['type']=='sell' else (0.25,0.85,0.45,1)
            top = BoxLayout(size_hint_y=None, height=int(24*sp))

            l1 = lbl(f"[b]{emo}ELL[/b]" if sig['type']=='sell'
                     else f"[b]BUY[/b]",
                     size=13, bold=True, color=t_col)
            l2 = lbl(f"  {sig['tf']}  {sig.get('area','')}",
                     size=11, color=(0.7,0.7,0.7,1))
            st_lbl = lbl(f"[b]{st_text}[/b]", size=10, bold=True,
                          color=col_bg, halign='right')
            top.add_widget(l1); top.add_widget(l2); top.add_widget(st_lbl)
            card.add_widget(top)

            row2 = BoxLayout(size_hint_y=None, height=int(20*sp))
            row2.add_widget(lbl(f"Entry: {sig['entry']:.3f}", size=11,
                                color=(0.85,0.85,0.85,1)))
            row2.add_widget(lbl(f"SL: {sig['sl']:.3f}", size=11,
                                color=(0.9,0.35,0.35,1)))
            row2.add_widget(lbl(f"TP1: {sig['tp1']:.3f}", size=11,
                                color=(0.3,0.85,0.45,1)))
            card.add_widget(row2)

            # Unrealized P&L if open
            if st == "OPEN" and price > 0:
                unr = bot.calc_unrealized(
                    {"type": sig['type'], "entry": sig['entry']}, price)
                sign = "+" if unr >= 0 else ""
                unr_col = (0.2,0.9,0.4,1) if unr >= 0 else (0.9,0.3,0.3,1)
                card.add_widget(lbl(f"P&L: {sign}{unr:.2f}", size=11,
                                    color=unr_col))

            ts_lbl = lbl(sig.get('ts',''), size=9,
                          color=(0.35,0.35,0.45,1))
            card.add_widget(ts_lbl)
            self.sig_box.add_widget(card)

# ════════════════════════════════════════════════════════
#  TAB: FIBO
# ════════════════════════════════════════════════════════
_FIBO_ROWS = [
    (2.414, "SL S2",   (0.85, 0.25, 0.25, 1)),
    (2.236, "SELL",    (0.95, 0.30, 0.30, 1)),
    (2.000, "SELL",    (0.95, 0.30, 0.30, 1)),
    (1.786, "SL S1",   (0.85, 0.25, 0.25, 1)),
    (1.618, "SELL",    (0.95, 0.30, 0.30, 1)),
    (1.500, "SELL",    (0.95, 0.30, 0.30, 1)),
    (1.000, "HIGH",    (0.85, 0.85, 0.85, 1)),
    (0.500, "MID",     (0.80, 0.80, 0.80, 1)),
    (0.000, "LOW",     (0.85, 0.85, 0.85, 1)),
    (-0.500, "BUY",   (0.25, 0.85, 0.45, 1)),
    (-0.618, "BUY",   (0.25, 0.85, 0.45, 1)),
    (-0.786, "SL B1", (0.25, 0.70, 0.30, 1)),
    (-1.000, "BUY",   (0.25, 0.85, 0.45, 1)),
    (-1.236, "BUY",   (0.25, 0.85, 0.45, 1)),
    (-1.414, "SL B2", (0.25, 0.70, 0.30, 1)),
]

class FiboTab(BoxLayout):
    def __init__(self, **kw):
        sp = _sp()
        super().__init__(orientation='vertical',
                         padding=[0, 0], spacing=0, **kw)

        # TF Filter
        tf_row = BoxLayout(size_hint_y=None, height=int(48*sp),
                            padding=[int(10*sp), int(8*sp)], spacing=int(5*sp))
        _add_bg(tf_row, (0.07, 0.09, 0.13, 1))

        self._active_tf  = "5min"
        self._tf_btns    = {}
        for tf in bot.TIMEFRAMES:
            label = bot.TF_LABEL[tf]
            btn   = pill_btn(label, active=(tf == "5min"), width=52)
            btn.bind(on_press=lambda b, t=tf: self._set_tf(t))
            self._tf_btns[tf] = btn
            tf_row.add_widget(btn)
        self.add_widget(tf_row)

        # Info bar (High / Low)
        info_row = BoxLayout(size_hint_y=None, height=int(30*sp),
                              padding=[int(12*sp), 2])
        _add_bg(info_row, (0.08, 0.10, 0.14, 1))
        self.hl_lbl = lbl("H: —   L: —", size=11,
                           color=(0.55, 0.55, 0.55, 1))
        info_row.add_widget(self.hl_lbl)
        self.add_widget(info_row)

        # Level list
        sv = ScrollView(size_hint=(1, 1))
        self.lv_box = BoxLayout(orientation='vertical', spacing=0,
                                 size_hint_y=None,
                                 padding=[int(10*sp), int(4*sp)])
        self.lv_box.bind(minimum_height=self.lv_box.setter('height'))
        sv.add_widget(self.lv_box)
        self.add_widget(sv)

    def _set_tf(self, tf):
        self._active_tf = tf
        gold = (1, 0.78, 0, 1)
        dim  = (0.18, 0.20, 0.26, 1)
        for t, btn in self._tf_btns.items():
            btn.canvas.before.clear()
            _add_bg(btn, gold if t == tf else dim, radius=14)
            btn.color = ((0.05,0.05,0.08,1) if t == tf
                         else (0.7,0.7,0.7,1))
        self.refresh()

    def refresh(self):
        sp = _sp()
        tf = self._active_tf
        with bot.S.lock:
            d = bot.S.fibo.get(tf, {})
            price = bot.S.price

        self.lv_box.clear_widgets()

        if not d:
            self.hl_lbl.text = "H: —   L: —"
            self.lv_box.add_widget(
                lbl("Data belum tersedia. Menunggu...", size=12,
                    color=(0.4, 0.4, 0.4, 1), halign='center'))
            return

        high   = d.get('high', 0)
        low    = d.get('low', 0)
        levels = d.get('levels', {})
        self.hl_lbl.text = (f"H: {high:.3f}   L: {low:.3f}   "
                            f"[color=ffaa00]{bot.TF_LABEL[tf]}[/color]")

        row_h = int(34 * sp)
        for lv, lname, col in _FIBO_ROWS:
            px = levels.get(lv)
            if px is None:
                continue

            row = BoxLayout(size_hint_y=None, height=row_h,
                             padding=[int(8*sp), 0], spacing=int(6*sp))

            # Highlight active price zone
            is_near = price > 0 and abs(price - px) < (high - low) * 0.015
            bg_col  = (0.18, 0.20, 0.28, 1) if is_near else (0.09, 0.11, 0.16, 1)
            _add_bg(row, bg_col)

            lv_str  = f"{lv:+.3f}".replace("+", " ")
            lname_l = lbl(f"{lname}", size=11, bold=True, color=col)
            lv_l    = lbl(lv_str,    size=10, color=(0.5,0.5,0.5,1))
            px_l    = lbl(f"{px:.3f}", size=13, bold=True, color=col,
                          halign='right')

            # Distance indicator
            dist = price - px if price > 0 else 0
            dsign = "+" if dist >= 0 else ""
            dist_l = lbl(f"{dsign}{dist:.1f}" if price > 0 else "",
                          size=10, color=(0.5,0.5,0.5,1), halign='right')

            row.add_widget(lname_l)
            row.add_widget(lv_l)
            row.add_widget(Widget())
            row.add_widget(px_l)
            row.add_widget(dist_l)
            self.lv_box.add_widget(row)
            self.lv_box.add_widget(h_sep())

# ════════════════════════════════════════════════════════
#  HEADER BAR (per-tab)
# ════════════════════════════════════════════════════════
class HeaderBar(BoxLayout):
    def __init__(self, title, subtitle="", **kw):
        sp = _sp()
        super().__init__(orientation='vertical',
                         size_hint_y=None, height=int(56*sp),
                         padding=[int(16*sp), int(6*sp)], **kw)
        _add_bg(self, (0.07, 0.08, 0.13, 1))

        row1 = BoxLayout(size_hint_y=None, height=int(26*sp))
        t_lbl = lbl(f"[b]{title}[/b]", size=14, bold=True,
                     color=(1, 0.78, 0, 1))
        row1.add_widget(t_lbl)

        # Live clock on the right
        self.clock_lbl = lbl("", size=10,
                              color=(0.4, 0.4, 0.4, 1), halign='right')
        row1.add_widget(self.clock_lbl)
        self.add_widget(row1)

        if subtitle:
            self.add_widget(lbl(subtitle, size=10,
                                color=(0.4, 0.4, 0.4, 1)))

        Clock.schedule_interval(self._tick, 1)

    def _tick(self, *_):
        self.clock_lbl.text = datetime.now().strftime("%H:%M:%S")

# ════════════════════════════════════════════════════════
#  ROOT WIDGET
# ════════════════════════════════════════════════════════
class RootWidget(BoxLayout):
    def __init__(self, **kw):
        sp = _sp()
        super().__init__(orientation='vertical', spacing=0, **kw)
        _add_bg(self, (0.04, 0.04, 0.07, 1))

        self._header_host = BoxLayout(orientation='vertical',
                                       size_hint_y=None,
                                       height=int(56*sp))
        self._headers = {
            'dashboard': HeaderBar("ZIGZAG FIBO", "XAUUSD by GOGRAK"),
            'sinyal':    HeaderBar("SINYAL",      "ZigZag Fibonacci"),
            'fibo':      HeaderBar("FIBO LEVELS", "ZigZag Extension"),
        }

        self.content = BoxLayout(orientation='vertical')
        self.nav     = BottomNav(on_switch=self._switch)

        self.add_widget(self._header_host)
        self.add_widget(self.content)
        self.add_widget(self.nav)

        self.dash_tab   = DashTab()
        self.sinyal_tab = SinyalTab()
        self.fibo_tab   = FiboTab()

        self._switch('dashboard')

        bot.ui_update_callback = self._schedule_refresh
        Clock.schedule_interval(self._refresh_all, 1)

    def _switch(self, tab):
        self._current_tab = tab
        self.content.clear_widgets()
        self._header_host.clear_widgets()
        self._header_host.add_widget(self._headers[tab])
        views = {
            'dashboard': self.dash_tab,
            'sinyal':    self.sinyal_tab,
            'fibo':      self.fibo_tab,
        }
        self.content.add_widget(views[tab])
        self.nav.set_active(tab)

    def _schedule_refresh(self):
        Clock.schedule_once(self._refresh_all, 0)

    def _refresh_all(self, *_):
        _refresh_statuses()
        self.dash_tab.refresh()
        self.sinyal_tab.refresh()
        self.fibo_tab.refresh()

# ════════════════════════════════════════════════════════
#  APP
# ════════════════════════════════════════════════════════
class ZigzagFiboApp(App):
    def build(self):
        self.title = APP_TITLE
        root = RootWidget()
        threading.Thread(target=bot.start_bot,
                         daemon=True, name="bot_start").start()
        return root


if __name__ == "__main__":
    ZigzagFiboApp().run()
