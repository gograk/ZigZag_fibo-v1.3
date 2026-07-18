#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIGZAG_FIBO BY GOGRAK — Android APK UI (Kivy)
Versi v6-fix14: live chart + confidence meter + alarm + streak + full bug fix.
"""

import threading
from collections import deque
from datetime import datetime, timezone

# ── Kivy config SEBELUM import kivy lainnya ──────────────
from kivy.config import Config
Config.set('graphics', 'width',  '400')
Config.set('graphics', 'height', '800')
Config.set('kivy',     'window_icon', '')

from kivy.app             import App
from kivy.uix.boxlayout   import BoxLayout
from kivy.uix.scrollview  import ScrollView
from kivy.uix.label       import Label
from kivy.uix.button      import Button
from kivy.uix.widget      import Widget
from kivy.uix.textinput   import TextInput
from kivy.clock           import Clock
from kivy.core.window     import Window
from kivy.graphics        import (Color, Rectangle, RoundedRectangle,
                                   Line, Ellipse)

Window.clearcolor = (0.04, 0.04, 0.08, 1)

import bot_core as bot

APP_TITLE = "ZIGZAG_FIBO BY GOGRAK"

# ── Price history for mini chart ──────────────────────────
_price_history = deque(maxlen=80)

# ── Win/Loss streak ───────────────────────────────────────
_streak = {"count": 0, "type": ""}   # type = "WIN" | "LOSS" | ""

# ── Price alarm ───────────────────────────────────────────
_alarm = {"level": 0.0, "active": False, "triggered": False}

# ════════════════════════════════════════════════════════
#  RESPONSIVE SCALE  —  SP = scale-factor (1.0 @ 400 px lebar)
# ════════════════════════════════════════════════════════
def _sp():
    return max(0.72, min(1.65, Window.width / 400.0))

def dp(val):
    return max(1, int(val * _sp()))

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
#  STATUS TRACKING + STREAK
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

    # ── Hitung streak ─────────────────────────────────────
    results = []
    for sig in signals:
        st = _sig_status.get(_sig_key(sig))
        if st in ("WIN", "LOSS"):
            results.append(st)
    if results:
        last = results[-1]
        cnt  = sum(1 for _ in (r for r in reversed(results)
                               if r == last) for _ in [None])
        # simpler: count from end
        cnt = 0
        for r in reversed(results):
            if r == last: cnt += 1
            else: break
        _streak["count"] = cnt
        _streak["type"]  = last
    else:
        _streak["count"] = 0
        _streak["type"]  = ""

# ════════════════════════════════════════════════════════
#  COLOR PALETTE — premium dark theme
# ════════════════════════════════════════════════════════
C_BG          = (0.04, 0.04, 0.08, 1)
C_SURFACE     = (0.09, 0.10, 0.16, 1)
C_SURFACE_ALT = (0.11, 0.13, 0.19, 1)
C_HEADER      = (0.06, 0.07, 0.12, 1)
C_BORDER      = (0.16, 0.18, 0.26, 1)
C_GOLD        = (1.00, 0.80, 0.20, 1)
C_GOLD_DIM    = (0.55, 0.44, 0.11, 1)
C_TEXT        = (0.92, 0.93, 0.95, 1)
C_TEXT_2      = (0.58, 0.60, 0.68, 1)
C_TEXT_3      = (0.35, 0.37, 0.46, 1)
C_GREEN       = (0.18, 0.90, 0.52, 1)
C_RED         = (0.95, 0.32, 0.32, 1)
C_CYAN        = (0.22, 0.88, 0.90, 1)
C_NAV_INACTIVE= (0.35, 0.37, 0.46, 1)

# ════════════════════════════════════════════════════════
#  WIDGET HELPERS
# ════════════════════════════════════════════════════════
def lbl(text, size=13, bold=False, color=C_TEXT,
        halign='left', valign='middle', **kw):
    l = Label(text=text, font_size=size * _sp(), bold=bold, color=color,
               halign=halign, valign=valign,
               size_hint_y=None, markup=True, **kw)
    # height = texture height; text_size tracks widget width → halign/valign work
    l.bind(
        texture_size=lambda inst, ts: setattr(inst, 'height', ts[1]),
        width=lambda inst, w:  setattr(inst, 'text_size', (w, None))
    )
    return l

def _add_bg(widget, color, radius=0):
    with widget.canvas.before:
        c_inst = Color(*color)
        widget._bg_color = c_inst          # store for in-place updates
        if radius:
            r = radius * _sp()
            widget._bg = RoundedRectangle(pos=widget.pos, size=widget.size,
                                           radius=[r, r, r, r])
        else:
            widget._bg = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                size=lambda w, v: setattr(w._bg, 'size', v))

def h_sep(height=1, color=C_BORDER):
    w = Widget(size_hint_y=None, height=max(1, height))
    _add_bg(w, color)
    return w

def section_title(text):
    box = BoxLayout(size_hint_y=None, height=dp(32), padding=[dp(2), dp(6)])
    l = Label(text=f"[b]{text}[/b]", font_size=10 * _sp(),
               color=C_TEXT_3, markup=True, halign='left', valign='middle',
               size_hint_y=None)
    l.bind(texture_size=lambda inst, ts: setattr(inst, 'height', ts[1]),
           width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
    box.add_widget(l)
    return box

def pill_btn(text, active=False, width=None):
    w   = dp(width or 60)
    btn = Button(text=text, size_hint=(None, None), size=(w, dp(28)),
                 font_size=int(10 * _sp()), bold=active,
                 background_normal='', background_color=(0, 0, 0, 0))
    _add_bg(btn, C_GOLD if active else (0.14, 0.16, 0.23, 1), radius=12)
    btn.color = (0.06, 0.06, 0.10, 1) if active else C_TEXT_2
    return btn

# ════════════════════════════════════════════════════════
#  MINI CHART ─ live line chart of recent price history
# ════════════════════════════════════════════════════════
class MiniChart(Widget):
    """Canvas-drawn line chart, no external library needed."""

    def __init__(self, **kw):
        super().__init__(size_hint_y=None, height=dp(96), **kw)
        self._prices = []
        self.bind(pos=self._draw, size=self._draw)

    def update(self, prices):
        self._prices = list(prices)
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 10 or h < 10:
            return

        pad = dp(8)
        prices = self._prices

        with self.canvas:
            # ── background card ──────────────────────────
            Color(*C_SURFACE)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[dp(10), dp(10), dp(10), dp(10)])

            if len(prices) < 2:
                Color(*C_TEXT_3)
                # placeholder label not possible in canvas; leave empty
                return

            mn, mx = min(prices), max(prices)
            rng = (mx - mn) if mx != mn else 1.0

            # ── subtle grid lines ─────────────────────────
            Color(*(0.13, 0.15, 0.23, 1))
            for i in range(1, 3):
                gy = self.y + pad + (h - 2*pad) * i / 2
                Line(points=[self.x + pad, gy,
                              self.x + w - pad, gy], width=0.6)

            # ── compute points ────────────────────────────
            n   = len(prices)
            pts = []
            for i, p in enumerate(prices):
                px = self.x + pad + (w - 2*pad) * i / (n - 1)
                py = self.y + pad + (h - 2*pad) * (p - mn) / rng
                pts.extend([px, py])

            is_up = prices[-1] >= prices[0]
            lc    = C_GREEN if is_up else C_RED

            # ── price line ───────────────────────────────
            Color(*lc)
            Line(points=pts, width=1.8)

            # ── last-price dot ────────────────────────────
            dot = dp(6)
            lx, ly = pts[-2], pts[-1]
            # halo
            Color(lc[0], lc[1], lc[2], 0.28)
            Ellipse(pos=(lx - dot, ly - dot), size=(dot*2, dot*2))
            # solid dot
            Color(*lc)
            Ellipse(pos=(lx - dot/2, ly - dot/2), size=(dot, dot))

            # ── min/max markers ───────────────────────────
            Color(*C_TEXT_3)
            # drawn as thin horizontal dashes at min and max y
            Line(points=[self.x + pad, self.y + pad,
                          self.x + pad + dp(6), self.y + pad], width=0.8)
            Line(points=[self.x + pad, self.y + h - pad,
                          self.x + pad + dp(6), self.y + h - pad], width=0.8)

# ════════════════════════════════════════════════════════
#  CONFIDENCE SCORE  (0 – 98)
# ════════════════════════════════════════════════════════
def _calc_confidence(sig):
    """RSI alignment + extension quality → integer 20–98."""
    score = 50

    with bot.S.lock:
        rsi_val = bot.S.rsi.get(sig['tf'], 0)

    if rsi_val > 0:
        if sig['type'] == 'sell':
            if rsi_val >= 70:   score += 25
            elif rsi_val >= 60: score += 12
            else:               score -= 12
        else:
            if rsi_val <= 30:   score += 25
            elif rsi_val <= 40: score += 12
            else:               score -= 12

    area = sig.get('area', '').lower()
    if any(k in area for k in ('2.4', '2.2', '2.0', '1.6', '-1.2', '-1.4')):
        score += 18
    elif area:
        score += 7

    return max(20, min(98, score))

# ════════════════════════════════════════════════════════
#  NAV BUTTON — icon + label drawn directly on canvas
# ════════════════════════════════════════════════════════
class NavButton(Button):
    _BAR_RATIOS = [0.42, 0.75, 0.55, 0.95, 0.65]
    _ZZ_XS      = [0.02, 0.27, 0.52, 0.77, 0.98]
    _ZZ_YS      = [0.28, 0.88, 0.14, 0.74, 0.34]

    def __init__(self, icon_type, label_text, **kw):
        super().__init__(background_normal='', background_color=(0,0,0,0), **kw)
        self._icon_type  = icon_type
        self._icon_color = list(C_NAV_INACTIVE)
        self._label_text = label_text
        self._is_active  = False
        self.bind(pos=self._redraw, size=self._redraw)

    def set_active(self, active):
        self._is_active  = active
        self._icon_color = list(C_GOLD if active else C_NAV_INACTIVE)
        self._redraw()

    def _redraw(self, *_):
        if self.width < 4 or self.height < 4:
            return

        w, h   = self.width, self.height
        bx, by = self.x, self.y

        icon_sz = min(dp(22), w * 0.45)
        lbl_h   = dp(14)
        pad_top = dp(8)

        ix = bx + (w - icon_sz) / 2
        iy = by + h - pad_top - icon_sz
        lx = bx
        ly = by + dp(5)

        c = self._icon_color
        self.canvas.after.clear()
        with self.canvas.after:
            Color(*c)
            if self._icon_type == 'grid':
                dot = icon_sz / 4.5
                gap = (icon_sz - dot * 3) / 3.5
                for r in range(3):
                    for col in range(3):
                        Rectangle(pos=(ix + col*(dot+gap), iy + r*(dot+gap)),
                                  size=(dot, dot))

            elif self._icon_type == 'bars':
                n    = len(self._BAR_RATIOS)
                bw   = icon_sz / (n * 1.55)
                bgap = bw * 0.55
                ox   = ix + (icon_sz - (bw*n + bgap*(n-1))) / 2
                for i, hr in enumerate(self._BAR_RATIOS):
                    Rectangle(pos=(ox + i*(bw+bgap), iy),
                               size=(bw, icon_sz * hr))

            elif self._icon_type == 'zigzag':
                pts = []
                for xr, yr in zip(self._ZZ_XS, self._ZZ_YS):
                    pts += [ix + xr*icon_sz, iy + yr*icon_sz]
                Line(points=pts, width=max(1.5, icon_sz*0.07))

        # Nav label — size & pos set explicitly every redraw; NO texture binding
        if not hasattr(self, '_nav_lbl'):
            self._nav_lbl = Label(
                text=self._label_text, font_size=8.5*_sp(),
                halign='center', valign='middle', size_hint=(None, None))
            self.add_widget(self._nav_lbl)

        self._nav_lbl.font_size = 8.5 * _sp()
        self._nav_lbl.color     = self._icon_color
        self._nav_lbl.bold      = self._is_active
        self._nav_lbl.size      = (w, lbl_h)
        self._nav_lbl.text_size = (w, lbl_h)   # required for halign='center'
        self._nav_lbl.pos       = (lx, ly)

# ════════════════════════════════════════════════════════
#  BOTTOM NAV
# ════════════════════════════════════════════════════════
class BottomNav(BoxLayout):
    def __init__(self, on_switch, **kw):
        super().__init__(orientation='horizontal',
                         size_hint_y=None, height=dp(64), **kw)
        _add_bg(self, C_HEADER)
        with self.canvas.before:
            Color(*C_BORDER)
            self._top_line = Rectangle(pos=self.pos, size=(self.width, 1))
        self.bind(pos =lambda w, v: setattr(w._top_line, 'pos', v),
                  size=lambda w, v: setattr(w._top_line, 'size', (v[0], 1)))

        self._on_switch = on_switch
        self._nav_btns  = {}

        for key, icon_type, label_text in [
            ('dashboard', 'grid',   'Dashboard'),
            ('sinyal',    'bars',   'Sinyal'),
            ('fibo',      'zigzag', 'Fibo'),
        ]:
            btn = NavButton(icon_type=icon_type, label_text=label_text)
            btn.bind(on_press=lambda b, k=key: self._tap(k))
            self._nav_btns[key] = btn
            self.add_widget(btn)

        self._set_active('dashboard')

    def _tap(self, key):
        self._set_active(key)
        self._on_switch(key)

    def set_active(self, key):
        self._set_active(key)

    def _set_active(self, key):
        for k, btn in self._nav_btns.items():
            btn.set_active(k == key)

# ════════════════════════════════════════════════════════
#  TAB: DASHBOARD
# ════════════════════════════════════════════════════════
class DashTab(ScrollView):
    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        root = BoxLayout(orientation='vertical',
                         padding=[dp(14), dp(12)],
                         spacing=dp(10), size_hint_y=None)
        root.bind(minimum_height=root.setter('height'))

        # ── Price Card ─────────────────────────────────
        price_box = BoxLayout(orientation='vertical', spacing=dp(3),
                               size_hint_y=None, height=dp(164),
                               padding=[dp(16), dp(10)])
        _add_bg(price_box, C_SURFACE, radius=12)

        live_row = BoxLayout(size_hint_y=None, height=dp(20))
        self.ws_lbl = lbl("● LIVE", size=9.5, color=C_GREEN,
                           halign='center', bold=True)
        live_row.add_widget(self.ws_lbl)

        # streak badge — right side of live row
        self.streak_lbl = lbl("", size=9, color=C_GOLD, halign='right')
        live_row.add_widget(self.streak_lbl)
        price_box.add_widget(live_row)

        self.sym_lbl   = lbl("XAUUSD", size=11, color=C_TEXT_3, halign='center')
        self.price_lbl = lbl("—", size=36, bold=True, color=C_TEXT, halign='center')
        self.chg_lbl   = lbl("", size=12.5, halign='center')

        price_box.add_widget(self.sym_lbl)
        price_box.add_widget(self.price_lbl)
        price_box.add_widget(self.chg_lbl)
        root.add_widget(price_box)

        # ── Mini Chart ─────────────────────────────────
        root.add_widget(section_title("Live Chart — XAUUSD"))
        chart_card = BoxLayout(orientation='vertical', size_hint_y=None,
                                padding=[dp(6), dp(6)])
        chart_card.bind(minimum_height=chart_card.setter('height'))
        _add_bg(chart_card, C_SURFACE, radius=12)
        self._chart = MiniChart()
        chart_card.add_widget(self._chart)

        # chart bottom row: high / low labels
        self._chart_meta = lbl("Menunggu data harga...", size=8.5,
                                color=C_TEXT_3, halign='center')
        chart_card.add_widget(self._chart_meta)
        chart_card.height = dp(96) + dp(20) + dp(12)
        root.add_widget(chart_card)

        # ── RSI ────────────────────────────────────────
        root.add_widget(section_title("RSI-14 per Timeframe"))
        rsi_box = BoxLayout(size_hint_y=None, height=dp(60),
                             padding=[dp(8), dp(6)], spacing=2)
        _add_bg(rsi_box, C_SURFACE, radius=12)
        self.rsi_cells = {}
        for tf in bot.TIMEFRAMES:
            col = BoxLayout(orientation='vertical', spacing=dp(2))
            name_l = lbl(bot.TF_LABEL[tf], size=9, color=C_TEXT_3, halign='center')
            val_l  = lbl("—", size=13.5, bold=True, halign='center', color=C_TEXT)
            col.add_widget(name_l)
            col.add_widget(val_l)
            self.rsi_cells[tf] = val_l
            rsi_box.add_widget(col)
        root.add_widget(rsi_box)

        # ── Stats ──────────────────────────────────────
        root.add_widget(section_title("Statistik Sesi"))
        stats_outer = BoxLayout(orientation='vertical',
                                 size_hint_y=None, spacing=0, padding=[0, 0])
        stats_outer.bind(minimum_height=stats_outer.setter('height'))
        _add_bg(stats_outer, C_SURFACE, radius=12)
        self.stat_labels = {}
        stat_rows = [
            ("signal", "Total Sinyal"),
            ("win",    "Win (TP1)"),
            ("wr",     "Win Rate"),
            ("pnl",    "PnL Harian"),
            ("dd",     "Max Drawdown"),
            ("uptime", "Uptime"),
        ]
        for i, (key, title) in enumerate(stat_rows):
            row_bg = C_SURFACE_ALT if i % 2 == 0 else C_SURFACE
            row = BoxLayout(size_hint_y=None, height=dp(36), padding=[dp(14), 0])
            _add_bg(row, row_bg)
            lbl_t = lbl(title, size=11.5, color=C_TEXT_2)
            lbl_v = lbl("—",   size=12.5, bold=True, color=C_TEXT, halign='right')
            row.add_widget(lbl_t)
            row.add_widget(lbl_v)
            self.stat_labels[key] = lbl_v
            stats_outer.add_widget(row)
            if i < len(stat_rows) - 1:
                stats_outer.add_widget(h_sep())
        root.add_widget(stats_outer)

        # ── Price Alarm ────────────────────────────────
        root.add_widget(section_title("🔔 Alarm Harga"))
        alarm_card = BoxLayout(size_hint_y=None, height=dp(52),
                                padding=[dp(12), dp(10)], spacing=dp(8))
        _add_bg(alarm_card, C_SURFACE, radius=12)

        self._alarm_input = TextInput(
            hint_text="Masukkan level harga...",
            size_hint=(1, None), height=dp(32),
            font_size=int(11 * _sp()),
            background_color=(0.12, 0.14, 0.20, 1),
            foreground_color=C_TEXT,
            hint_text_color=list(C_TEXT_3),
            cursor_color=list(C_GOLD),
            multiline=False, input_filter='float',
            padding=[dp(8), dp(6)])
        alarm_set_btn = Button(
            text="SET", size_hint=(None, None), size=(dp(48), dp(32)),
            font_size=int(10 * _sp()), bold=True,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(alarm_set_btn, C_GOLD, radius=8)
        alarm_set_btn.color = (0.06, 0.06, 0.10, 1)
        alarm_set_btn.bind(on_press=self._set_alarm)

        alarm_clr_btn = Button(
            text="CLR", size_hint=(None, None), size=(dp(48), dp(32)),
            font_size=int(10 * _sp()), bold=False,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(alarm_clr_btn, (0.18, 0.20, 0.30, 1), radius=8)
        alarm_clr_btn.color = C_TEXT_2
        alarm_clr_btn.bind(on_press=self._clear_alarm)

        alarm_card.add_widget(self._alarm_input)
        alarm_card.add_widget(alarm_set_btn)
        alarm_card.add_widget(alarm_clr_btn)
        root.add_widget(alarm_card)

        self.alarm_status = lbl("Alarm: tidak aktif", size=9.5,
                                 color=C_TEXT_3, halign='center')
        root.add_widget(self.alarm_status)

        # ── Activity Log ───────────────────────────────
        root.add_widget(section_title("Log Aktivitas"))
        log_outer = BoxLayout(orientation='vertical', size_hint_y=None,
                               spacing=0, padding=[dp(12), dp(8)])
        log_outer.bind(minimum_height=log_outer.setter('height'))
        _add_bg(log_outer, C_SURFACE, radius=12)
        self.log_box = log_outer
        root.add_widget(log_outer)

        # ── WS status bar ──────────────────────────────
        self.ws_bar = BoxLayout(size_hint_y=None, height=dp(30),
                                 padding=[dp(14), 0])
        _add_bg(self.ws_bar, C_HEADER)
        self.ws_status = lbl("WS: --", size=9.5, color=C_TEXT_3, halign='center')
        self.ws_bar.add_widget(self.ws_status)
        root.add_widget(self.ws_bar)

        self.add_widget(root)

        # ── Popup overlay for alarm ─────────────────────
        self._popup_lbl = None

    # ── Alarm handlers ────────────────────────────────
    def _set_alarm(self, *_):
        txt = self._alarm_input.text.strip()
        try:
            level = float(txt)
        except ValueError:
            self.alarm_status.text  = "❌ Masukkan angka yang valid"
            self.alarm_status.color = C_RED
            return
        _alarm["level"]     = level
        _alarm["active"]    = True
        _alarm["triggered"] = False
        self.alarm_status.text  = f"🔔 Alarm aktif @ {level:.3f}"
        self.alarm_status.color = C_GOLD

    def _clear_alarm(self, *_):
        _alarm["active"]    = False
        _alarm["triggered"] = False
        _alarm["level"]     = 0.0
        self._alarm_input.text  = ""
        self.alarm_status.text  = "Alarm: tidak aktif"
        self.alarm_status.color = C_TEXT_3

    def _show_alarm_popup(self, level):
        """Float a brief notification banner inside the scroll view."""
        _send_android_notif("⚡ Alarm XAUUSD",
                            f"Harga mendekati {level:.3f}!")
        # Update status label as the inline alert
        self.alarm_status.text  = f"⚡ ALARM TRIGGERED @ {level:.3f}!"
        self.alarm_status.color = C_RED

    # ── Refresh ───────────────────────────────────────
    def refresh(self):
        with bot.S.lock:
            price  = bot.S.price
            prev   = bot.S.prev_price
            rsi_d  = dict(bot.S.rsi)
            total  = bot.S.total_signals
            wins   = bot.S.wins
            dpnl   = bot.S.daily_pnl
            dd     = bot.S.max_dd
            start  = bot.S.start_time
            ws_ok  = bot.S.ws_connected

        # Price history for chart
        if price > 0:
            if not _price_history or _price_history[-1] != price:
                _price_history.append(price)
            self._chart.update(_price_history)
            if len(_price_history) >= 2:
                mn = min(_price_history); mx = max(_price_history)
                self._chart_meta.text = (
                    f"H: [b]{mx:.3f}[/b]  L: [b]{mn:.3f}[/b]"
                    f"  ({len(_price_history)} ticks)")
            # Check alarm
            if (_alarm["active"] and not _alarm["triggered"]
                    and abs(price - _alarm["level"]) < 0.5):
                _alarm["triggered"] = True
                self._show_alarm_popup(_alarm["level"])

        # Price display
        if price > 0 and prev > 0:
            chg  = price - prev
            sign = "+" if chg >= 0 else ""
            col  = C_GREEN if chg >= 0 else C_RED
            self.price_lbl.text = f"{price:.3f}"
            self.chg_lbl.text   = f"{sign}{chg:.3f}"
            self.chg_lbl.color  = col
        elif price > 0:
            self.price_lbl.text = f"{price:.3f}"

        # WS indicator
        if ws_ok:
            self.ws_lbl.text  = "● LIVE"
            self.ws_lbl.color = C_GREEN
        else:
            self.ws_lbl.text  = "○ OFFLINE"
            self.ws_lbl.color = C_RED

        # Streak badge
        cnt  = _streak["count"]
        stype = _streak["type"]
        if cnt >= 2 and stype == "WIN":
            self.streak_lbl.text  = f"🔥 {cnt} Win"
            self.streak_lbl.color = C_GREEN
        elif cnt >= 2 and stype == "LOSS":
            self.streak_lbl.text  = f"❄️ {cnt} Loss"
            self.streak_lbl.color = C_RED
        else:
            self.streak_lbl.text = ""

        # RSI cells
        for tf in bot.TIMEFRAMES:
            r     = rsi_d.get(tf, 0)
            lbl_w = self.rsi_cells[tf]
            if r == 0:
                lbl_w.text = "—"; lbl_w.color = C_TEXT_3
            else:
                lbl_w.text = f"{r:.0f}"
                lbl_w.color = (C_RED if r >= 70 else
                               C_GREEN if r <= 30 else C_TEXT)

        # Stats
        wr      = f"{round(wins/total*100)}%" if total else "—"
        up      = datetime.now(timezone.utc) - start
        up_str  = str(up).split('.')[0]
        pnl_str = f"+{dpnl:.2f}" if dpnl >= 0 else f"{dpnl:.2f}"
        self.stat_labels["signal"].text  = str(total)
        self.stat_labels["win"].text     = str(wins)
        self.stat_labels["wr"].text      = wr
        self.stat_labels["pnl"].text     = pnl_str
        self.stat_labels["pnl"].color    = C_GREEN if dpnl >= 0 else C_RED
        self.stat_labels["dd"].text      = f"{dd:.2f}"
        self.stat_labels["uptime"].text  = up_str

        # Log
        logs = list(bot._log_buf)
        self.log_box.clear_widgets()
        if not logs:
            self.log_box.add_widget(
                lbl("Belum ada aktivitas.", size=10.5,
                    color=C_TEXT_3, halign='center'))
        for line in reversed(logs[-6:]):
            self.log_box.add_widget(
                lbl(line, size=9.5, color=(0.50, 0.65, 0.80, 1)))

        # WS bar
        ws_txt = ("WebSocket: Connected" if ws_ok
                  else "WebSocket: Offline (REST fallback)")
        self.ws_status.text  = ws_txt
        self.ws_status.color = C_GREEN if ws_ok else (0.90, 0.55, 0.30, 1)

# ════════════════════════════════════════════════════════
#  TAB: SINYAL
# ════════════════════════════════════════════════════════
_STATUS_CFG = {
    "WIN":     ((0.18, 0.78, 0.38, 1), "WIN ✓"),
    "LOSS":    ((0.88, 0.25, 0.25, 1), "LOSS ✗"),
    "OPEN":    ((0.90, 0.58, 0.08, 1), "OPEN"),
    "PENDING": ((0.40, 0.42, 0.52, 1), "PENDING"),
}

class SinyalTab(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', padding=[0,0], spacing=0, **kw)

        filter_row = BoxLayout(size_hint_y=None, height=dp(50),
                                padding=[dp(10), dp(10)], spacing=dp(6))
        _add_bg(filter_row, C_HEADER)
        self._active_filter = "ALL"
        self._filter_btns   = {}
        for f in ("ALL", "OPEN", "WIN", "LOSS", "PENDING"):
            btn = pill_btn(f, active=(f == "ALL"), width=54)
            btn.bind(on_press=lambda b, flt=f: self._set_filter(flt))
            self._filter_btns[f] = btn
            filter_row.add_widget(btn)
        self.add_widget(filter_row)

        count_row = BoxLayout(size_hint_y=None, height=dp(28),
                               padding=[dp(14), dp(4)])
        _add_bg(count_row, C_BG)
        self.count_lbl = lbl("0 sinyal", size=10, color=C_TEXT_3)
        count_row.add_widget(self.count_lbl)
        self.add_widget(count_row)

        sv = ScrollView(size_hint=(1, 1))
        self.sig_box = BoxLayout(orientation='vertical', spacing=dp(6),
                                  size_hint_y=None, padding=[dp(12), dp(6)])
        self.sig_box.bind(minimum_height=self.sig_box.setter('height'))
        sv.add_widget(self.sig_box)
        self.add_widget(sv)

    def _set_filter(self, flt):
        self._active_filter = flt
        for f, btn in self._filter_btns.items():
            active = (f == flt)
            if hasattr(btn, '_bg_color'):
                btn._bg_color.rgba = C_GOLD if active else (0.14, 0.16, 0.23, 1)
            btn.color = (0.06, 0.06, 0.10, 1) if active else C_TEXT_2
            btn.bold  = active
        self.refresh()

    def refresh(self):
        with bot.S.lock:
            signals = list(bot.S.signals_today)
            price   = bot.S.price

        flt      = self._active_filter
        filtered = []
        for sig in reversed(signals):
            key = _sig_key(sig)
            st  = _sig_status.get(key, "PENDING")
            if flt == "ALL" or st == flt:
                filtered.append((sig, st))

        self.count_lbl.text = f"{len(filtered)} sinyal ditemukan"
        self.sig_box.clear_widgets()

        if not filtered:
            self.sig_box.add_widget(
                lbl("Belum ada sinyal.", size=12,
                    color=C_TEXT_3, halign='center'))
            return

        for sig, st in filtered[:40]:
            col_bg, st_text = _STATUS_CFG.get(st, ((0.14, 0.15, 0.20, 1), st))
            has_pnl  = (st == "OPEN" and price > 0)
            conf     = _calc_confidence(sig)
            # height: top(24) + sep(1) + row2(22) + conf(18) + [pnl(16)] + ts(14)
            # + padding(16) + spacing*n
            card_h   = dp(120) if has_pnl else dp(104)
            card     = BoxLayout(orientation='vertical',
                                 size_hint_y=None, height=card_h,
                                 padding=[dp(12), dp(8)], spacing=dp(3))
            _add_bg(card, C_SURFACE, radius=10)

            # ── row 1: direction | tf+area | status ───
            t_col = C_RED if sig['type'] == 'sell' else C_GREEN
            top   = BoxLayout(size_hint_y=None, height=dp(24))
            dir_txt = "[b]SELL ▼[/b]" if sig['type'] == 'sell' else "[b]BUY ▲[/b]"
            top.add_widget(lbl(dir_txt, size=13, bold=True, color=t_col))
            top.add_widget(lbl(f"  {sig['tf']}  {sig.get('area','')}",
                               size=10.5, color=C_TEXT_2))
            top.add_widget(lbl(f"[b]{st_text}[/b]", size=9.5, bold=True,
                               color=col_bg, halign='right'))
            card.add_widget(top)

            card.add_widget(h_sep(color=(0.14, 0.16, 0.24, 1)))

            # ── row 2: entry | sl | tp1 ───────────────
            row2 = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
            row2.add_widget(lbl(f"Entry: [b]{sig['entry']:.3f}[/b]",
                                size=10.5, color=C_TEXT))
            row2.add_widget(lbl(f"SL: {sig['sl']:.3f}", size=10.5, color=C_RED))
            row2.add_widget(lbl(f"TP1: {sig['tp1']:.3f}", size=10.5,
                                color=C_GREEN, halign='right'))
            card.add_widget(row2)

            # ── P&L row (OPEN only) ───────────────────
            if has_pnl:
                unr     = bot.calc_unrealized(
                    {"type": sig['type'], "entry": sig['entry']}, price)
                sign    = "+" if unr >= 0 else ""
                unr_col = C_GREEN if unr >= 0 else C_RED
                card.add_widget(lbl(f"Unrealized P&L: [b]{sign}{unr:.2f}[/b]",
                                    size=10.5, color=unr_col))

            # ── Confidence bar ─────────────────────────
            conf_col  = (C_GREEN if conf >= 70 else
                         C_GOLD  if conf >= 50 else C_RED)
            conf_row  = BoxLayout(size_hint_y=None, height=dp(18),
                                   spacing=dp(6))
            conf_lbl  = lbl(f"Confidence [b]{conf}%[/b]", size=8.5,
                             color=conf_col, size_hint_x=None, width=dp(110))
            bar_outer = BoxLayout(size_hint=(1, None), height=dp(6))
            _add_bg(bar_outer, (0.10, 0.12, 0.20, 1), radius=3)
            bar_fill  = BoxLayout(size_hint=(conf / 100, 1))
            _add_bg(bar_fill, conf_col, radius=3)
            bar_outer.add_widget(bar_fill)
            conf_row.add_widget(conf_lbl)
            conf_row.add_widget(bar_outer)
            card.add_widget(conf_row)

            # ── Timestamp ─────────────────────────────
            card.add_widget(lbl(sig.get('ts', ''), size=9, color=C_TEXT_3))

            self.sig_box.add_widget(card)

# ════════════════════════════════════════════════════════
#  TAB: FIBO
# ════════════════════════════════════════════════════════
_FIBO_ROWS = [
    (2.414, "SL S2",  (0.85, 0.25, 0.25, 1)),
    (2.236, "SELL",   C_RED),
    (2.000, "SELL",   C_RED),
    (1.786, "SL S1",  (0.85, 0.25, 0.25, 1)),
    (1.618, "SELL",   C_RED),
    (1.500, "SELL",   C_RED),
    (1.000, "HIGH",   C_TEXT),
    (0.500, "MID",    C_TEXT_2),
    (0.000, "LOW",    C_TEXT),
    (-0.500, "BUY",   C_GREEN),
    (-0.618, "BUY",   C_GREEN),
    (-0.786, "SL B1", (0.18, 0.72, 0.35, 1)),
    (-1.000, "BUY",   C_GREEN),
    (-1.236, "BUY",   C_GREEN),
    (-1.414, "SL B2", (0.18, 0.72, 0.35, 1)),
]

class FiboTab(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', padding=[0,0], spacing=0, **kw)

        tf_row = BoxLayout(size_hint_y=None, height=dp(50),
                            padding=[dp(10), dp(10)], spacing=dp(5))
        _add_bg(tf_row, C_HEADER)
        self._active_tf = "5min"
        self._tf_btns   = {}
        for tf in bot.TIMEFRAMES:
            btn = pill_btn(bot.TF_LABEL[tf], active=(tf == "5min"), width=50)
            btn.bind(on_press=lambda b, t=tf: self._set_tf(t))
            self._tf_btns[tf] = btn
            tf_row.add_widget(btn)
        self.add_widget(tf_row)

        info_row = BoxLayout(size_hint_y=None, height=dp(32),
                              padding=[dp(14), dp(4)])
        _add_bg(info_row, C_BG)
        self.hl_lbl = lbl("H: —   L: —", size=10.5, color=C_TEXT_2)
        info_row.add_widget(self.hl_lbl)
        self.add_widget(info_row)

        sv = ScrollView(size_hint=(1, 1))
        self.lv_box = BoxLayout(orientation='vertical', spacing=0,
                                 size_hint_y=None, padding=[dp(10), dp(4)])
        self.lv_box.bind(minimum_height=self.lv_box.setter('height'))
        sv.add_widget(self.lv_box)
        self.add_widget(sv)

    def _set_tf(self, tf):
        self._active_tf = tf
        for t, btn in self._tf_btns.items():
            active = (t == tf)
            if hasattr(btn, '_bg_color'):
                btn._bg_color.rgba = C_GOLD if active else (0.14, 0.16, 0.23, 1)
            btn.color = (0.06, 0.06, 0.10, 1) if active else C_TEXT_2
        self.refresh()

    def refresh(self):
        tf = self._active_tf
        with bot.S.lock:
            d     = bot.S.fibo.get(tf, {})
            price = bot.S.price

        self.lv_box.clear_widgets()

        if not d:
            self.hl_lbl.text = "H: —   L: —"
            self.lv_box.add_widget(
                lbl("Data belum tersedia. Menunggu...", size=11.5,
                    color=C_TEXT_3, halign='center'))
            return

        high   = d.get('high', 0)
        low    = d.get('low', 0)
        levels = d.get('levels', {})
        tf_tag = f"[color=ffcc33]{bot.TF_LABEL[tf]}[/color]"
        self.hl_lbl.text = f"H: {high:.3f}   L: {low:.3f}   {tf_tag}"

        row_h = dp(36)
        for i, (lv, lname, col) in enumerate(_FIBO_ROWS):
            px = levels.get(lv)
            if px is None:
                continue

            is_near = price > 0 and abs(price - px) < (high - low) * 0.015
            row_bg  = ((0.16, 0.19, 0.28, 1) if is_near else
                       (C_SURFACE_ALT if i % 2 == 0 else C_SURFACE))

            row = BoxLayout(size_hint_y=None, height=row_h,
                             padding=[dp(10), 0], spacing=dp(6))
            _add_bg(row, row_bg)

            lv_str = f"{lv:+.3f}".replace("+", " ")
            row.add_widget(lbl(f"[b]{lname}[/b]", size=11, bold=True, color=col))
            row.add_widget(lbl(lv_str, size=9.5, color=C_TEXT_3))
            row.add_widget(Widget())  # spacer
            row.add_widget(lbl(f"{px:.3f}", size=13, bold=True,
                               color=col, halign='right'))

            dist   = price - px if price > 0 else 0
            dsign  = "+" if dist >= 0 else ""
            row.add_widget(lbl(f"{dsign}{dist:.1f}" if price > 0 else "",
                               size=9.5, color=C_TEXT_3, halign='right'))

            self.lv_box.add_widget(row)
            self.lv_box.add_widget(h_sep())

# ════════════════════════════════════════════════════════
#  HEADER BAR
# ════════════════════════════════════════════════════════
class HeaderBar(BoxLayout):
    def __init__(self, title, subtitle="", **kw):
        super().__init__(orientation='vertical',
                         size_hint_y=None, height=dp(58),
                         padding=[dp(16), dp(8)], **kw)
        _add_bg(self, C_HEADER)
        with self.canvas.after:
            Color(*C_BORDER)
            self._bot_line = Rectangle(pos=(self.x, self.y),
                                        size=(self.width, 1))
        self.bind(
            pos =lambda w, v: setattr(w._bot_line, 'pos', (v[0], v[1])),
            size=lambda w, v: setattr(w._bot_line, 'size', (v[0], 1)))

        row1 = BoxLayout(size_hint_y=None, height=dp(26))
        row1.add_widget(lbl(f"[b]{title}[/b]", size=14.5, bold=True, color=C_GOLD))
        self.clock_lbl = lbl("", size=10, color=C_TEXT_3, halign='right')
        row1.add_widget(self.clock_lbl)
        self.add_widget(row1)

        if subtitle:
            self.add_widget(lbl(subtitle, size=9.5, color=C_TEXT_3))

        Clock.schedule_interval(self._tick, 1)
        self._tick()

    def _tick(self, *_):
        self.clock_lbl.text = datetime.now().strftime("%H:%M:%S")

# ════════════════════════════════════════════════════════
#  ROOT WIDGET
# ════════════════════════════════════════════════════════
class RootWidget(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', spacing=0, **kw)
        _add_bg(self, C_BG)

        self._header_host = BoxLayout(orientation='vertical',
                                       size_hint_y=None, height=dp(58))
        self._headers = {
            'dashboard': HeaderBar("ZIGZAG FIBO",  "XAUUSD by GOGRAK"),
            'sinyal':    HeaderBar("SINYAL",        "ZigZag Fibonacci"),
            'fibo':      HeaderBar("FIBO LEVELS",   "ZigZag Extension"),
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
        tab = getattr(self, '_current_tab', 'dashboard')
        # Always refresh current tab; refresh others less often
        self.dash_tab.refresh()
        if tab in ('sinyal',):
            self.sinyal_tab.refresh()
        if tab in ('fibo',):
            self.fibo_tab.refresh()
        # Refresh non-active tabs every 5 seconds via a counter
        if not hasattr(self, '_slow_tick'):
            self._slow_tick = 0
        self._slow_tick += 1
        if self._slow_tick >= 5:
            self._slow_tick = 0
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
