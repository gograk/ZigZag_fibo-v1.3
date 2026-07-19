#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIGZAG_FIBO BY GOGRAK — Android APK UI (Kivy) v6-fix15
Dashboard redesigned to match web reference layout exactly.
"""

import threading
from collections import deque
from datetime import datetime, timezone

from kivy.config import Config
Config.set('graphics', 'width',  '400')
Config.set('graphics', 'height', '800')
Config.set('kivy',     'window_icon', '')

from kivy.app            import App
from kivy.uix.boxlayout  import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label      import Label
from kivy.uix.button     import Button
from kivy.uix.widget     import Widget
from kivy.uix.textinput  import TextInput
from kivy.clock          import Clock
from kivy.core.window    import Window
from kivy.core.text      import Label as CoreLabel
from kivy.graphics       import (Color, Rectangle, RoundedRectangle,
                                  Line, Ellipse)

Window.clearcolor = (0.04, 0.04, 0.08, 1)

import bot_core as bot

APP_TITLE = "ZIGZAG_FIBO BY GOGRAK"

# ════════════════════════════════════════════════════════
#  GLOBAL STATE
# ════════════════════════════════════════════════════════
_price_history = deque(maxlen=200)  # raw tick prices

class _OHLCBar:
    def __init__(self, price, ts_min):
        self.o = self.h = self.l = self.c = price
        self.ts = ts_min
    def update(self, p):
        self.h = max(self.h, p)
        self.l = min(self.l, p)
        self.c = p

_candle_bars = deque(maxlen=80)
_current_bar = None

def _push_tick(price):
    """Call each price tick to maintain OHLC 1-min candles."""
    global _current_bar
    now_min = int(datetime.now().timestamp() // 60)
    if _current_bar is None or _current_bar.ts != now_min:
        if _current_bar is not None:
            _candle_bars.append((_current_bar.o, _current_bar.h,
                                  _current_bar.l, _current_bar.c))
        _current_bar = _OHLCBar(price, now_min)
    else:
        _current_bar.update(price)

_streak = {"count": 0, "type": ""}
_alarm  = {"level": 0.0, "active": False, "triggered": False}

# ════════════════════════════════════════════════════════
#  RESPONSIVE SCALE
# ════════════════════════════════════════════════════════
def _sp():
    return max(0.72, min(1.65, Window.width / 400.0))

def dp(val):
    return max(1, int(val * _sp()))

# ── Notification ─────────────────────────────────────
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

    results = []
    for sig in signals:
        st = _sig_status.get(_sig_key(sig))
        if st in ("WIN", "LOSS"):
            results.append(st)
    if results:
        last = results[-1]
        cnt  = 0
        for r in reversed(results):
            if r == last: cnt += 1
            else: break
        _streak["count"] = cnt
        _streak["type"]  = last
    else:
        _streak["count"] = 0
        _streak["type"]  = ""

# ════════════════════════════════════════════════════════
#  COLOR PALETTE
# ════════════════════════════════════════════════════════
C_BG          = (0.04, 0.04, 0.08, 1)
C_SURFACE     = (0.08, 0.09, 0.13, 1)
C_SURFACE_2   = (0.06, 0.07, 0.11, 1)
C_SURFACE_ALT = (0.10, 0.11, 0.17, 1)
C_HEADER      = (0.04, 0.05, 0.09, 1)
C_BORDER      = (0.14, 0.16, 0.24, 1)
C_BORDER_DIM  = (0.10, 0.11, 0.17, 1)
C_GOLD        = (1.00, 0.80, 0.20, 1)
C_GOLD_DIM    = (0.55, 0.44, 0.11, 1)
C_TEXT        = (0.92, 0.93, 0.95, 1)
C_TEXT_2      = (0.58, 0.60, 0.68, 1)
C_TEXT_3      = (0.32, 0.34, 0.44, 1)
C_GREEN       = (0.16, 0.88, 0.50, 1)
C_RED         = (0.95, 0.32, 0.32, 1)
C_AMBER       = (1.00, 0.70, 0.10, 1)
C_CONSOLE_BG  = (0.03, 0.06, 0.03, 1)
C_CONSOLE_TXT = (0.20, 0.88, 0.28, 1)

# ════════════════════════════════════════════════════════
#  WIDGET HELPERS
# ════════════════════════════════════════════════════════
def lbl(text, size=13, bold=False, color=C_TEXT,
        halign='left', valign='middle', **kw):
    l = Label(text=text, font_size=size * _sp(), bold=bold, color=color,
               halign=halign, valign=valign,
               size_hint_y=None, markup=True, **kw)
    l.bind(
        texture_size=lambda inst, ts: setattr(inst, 'height', ts[1]),
        width=lambda inst, w:  setattr(inst, 'text_size', (w, None))
    )
    return l

def _add_bg(widget, color, radius=0):
    with widget.canvas.before:
        c_inst = Color(*color)
        widget._bg_color = c_inst
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

def spacer(h=8):
    return Widget(size_hint_y=None, height=dp(h))

def pill_btn(text, active=False, width=None, height=28):
    w   = dp(width or 60)
    btn = Button(text=text, size_hint=(None, None),
                 size=(w, dp(height)),
                 font_size=int(10 * _sp()), bold=active,
                 background_normal='', background_color=(0, 0, 0, 0))
    _add_bg(btn, C_GOLD if active else (0.12, 0.14, 0.21, 1), radius=4)
    btn.color = (0.06, 0.06, 0.10, 1) if active else C_TEXT_2
    return btn

def card(padding=None, spacing=6, radius=10, color=None, **kw):
    """Vertical BoxLayout with background card styling."""
    p = padding or [dp(14), dp(12)]
    c = BoxLayout(orientation='vertical',
                  size_hint_y=None, spacing=dp(spacing),
                  padding=p, **kw)
    c.bind(minimum_height=c.setter('height'))
    _add_bg(c, color or C_SURFACE, radius=radius)
    return c

# ════════════════════════════════════════════════════════
#  CANVAS TEXT  (CoreLabel → Texture → Rectangle)
# ════════════════════════════════════════════════════════
def _cl_tex(text, font_size=9, color=(1, 1, 1, 1), bold=False):
    cl = CoreLabel(text=str(text), font_size=int(font_size),
                   color=color, bold=bold)
    cl.refresh()
    return cl.texture

def _draw_text(canvas, x, y, text,
               font_size=9, color=(1, 1, 1, 1),
               bold=False, anchor='center'):
    tex = _cl_tex(text, font_size=font_size, color=color, bold=bold)
    if not tex:
        return
    tw, th = tex.size
    if anchor == 'center':
        px, py = x - tw / 2, y - th / 2
    elif anchor == 'right':
        px, py = x - tw,     y - th / 2
    elif anchor == 'left':
        px, py = x,           y - th / 2
    else:
        px, py = x - tw / 2, y - th / 2
    with canvas:
        Color(1, 1, 1, 1)
        Rectangle(texture=tex, pos=(px, py), size=(tw, th))

# ════════════════════════════════════════════════════════
#  TREND BAR CHART  (gold bars from tick history)
# ════════════════════════════════════════════════════════
class TrendBars(Widget):
    def __init__(self, **kw):
        super().__init__(size_hint_y=None, height=dp(40), **kw)
        self.bind(pos=self._draw, size=self._draw)

    def update(self):
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 10: return
        ticks = list(_price_history)
        if len(ticks) < 2:
            return
        n = min(len(ticks), 80)
        ticks = ticks[-n:]
        mn = min(ticks); mx = max(ticks)
        rng = (mx - mn) if mx != mn else 1.0

        bar_w  = w / n
        gap    = max(1, bar_w * 0.18)
        bw     = max(2, bar_w - gap)
        with self.canvas:
            for i, p in enumerate(ticks):
                norm   = (p - mn) / rng
                bar_h  = max(dp(3), norm * (h - dp(4)))
                alpha  = 0.5 + norm * 0.5
                Color(1.0, 0.75, 0.10, alpha)
                Rectangle(pos=(self.x + i * bar_w, self.y + dp(2)),
                          size=(bw, bar_h))

# ════════════════════════════════════════════════════════
#  CONFIDENCE SCORE
# ════════════════════════════════════════════════════════
def _calc_confidence(sig):
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
#  CANDLE CHART  (OHLC + Fibonacci lines + zigzag)
# ════════════════════════════════════════════════════════
_FIBO_CHART_DEFS = [
    (2.236, C_RED,              "SELL Area(2)"),
    (1.786, (0.88, 0.28, 0.28, 1), "SL SELL(1.786)"),
    (1.618, C_RED,              "SELL Area(1.618)"),
    (1.500, C_RED,              "SELL Area(1.5)"),
    (1.000, C_TEXT,             "Swing HIGH(1.00)"),
    (0.500, (0.55, 0.57, 0.68, 1), "MID Zone(0.500)"),
    (0.000, C_TEXT,             "Swing LOW(0.000)"),
    (-0.500, C_GREEN,           "BUY Area(-0.5)"),
    (-0.618, C_GREEN,           "BUY Area(-0.618)"),
    (-1.000, (0.18, 0.72, 0.35, 1), "BUY Area(-1)"),
    (-1.236, C_GREEN,           "BUY Area(-2)"),
]

class CandleChart(Widget):
    def __init__(self, **kw):
        super().__init__(size_hint_y=None, height=dp(280), **kw)
        self._candles   = []
        self._fibo      = {}
        self._price_now = 0
        self._tf_label  = "15MIN"
        self.bind(pos=self._draw, size=self._draw)

    def update(self, candles, fibo, price, tf='15min'):
        self._candles   = list(candles)
        self._fibo      = dict(fibo)
        self._price_now = price
        self._tf_label  = bot.TF_LABEL.get(tf, '15MIN').upper()
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 40 or h < 40:
            return

        PAD_L = dp(44)
        PAD_R = dp(72)
        PAD_T = dp(20)
        PAD_B = dp(20)

        cw = w - PAD_L - PAD_R
        ch = h - PAD_T - PAD_B
        cx = self.x + PAD_L
        cy = self.y + PAD_B

        candles = self._candles
        fibo    = self._fibo
        price   = self._price_now
        ticks   = list(_price_history)

        # ── price range ──────────────────────────────────
        all_p = []
        for o_, h_, l_, c_ in candles:
            all_p.extend([h_, l_])
        for lv, px in fibo.items():
            if px: all_p.append(px)
        if price > 0:
            all_p.append(price)
        for p in ticks[-30:]:
            all_p.append(p)

        # background
        with self.canvas:
            Color(0.05, 0.06, 0.10, 1)
            Rectangle(pos=self.pos, size=self.size)

        if len(all_p) < 2:
            _draw_text(self.canvas, self.x + w / 2, self.y + h / 2,
                       "Menunggu data chart...",
                       font_size=int(10 * _sp()), color=C_TEXT_3)
            return

        mn = min(all_p); mx = max(all_p)
        rng = mx - mn
        if rng < 0.1: rng = 1.0
        mn -= rng * 0.07
        mx += rng * 0.07
        rng = mx - mn

        def ty(p):
            return cy + (p - mn) / rng * ch
        def tx(i, n):
            return cx + i / max(n - 1, 1) * cw

        with self.canvas:
            # ── grid lines ─────────────────────────────
            Color(0.09, 0.11, 0.17, 1)
            for i in range(5):
                gy = cy + ch * i / 4
                Line(points=[cx, gy, cx + cw, gy], width=0.5)

            # ── fibonacci dashed lines ──────────────────
            for ratio, col, _ in _FIBO_CHART_DEFS:
                px = fibo.get(ratio)
                if not px:
                    continue
                fy = ty(px)
                if fy < cy - dp(4) or fy > cy + ch + dp(4):
                    continue
                Color(col[0], col[1], col[2], 0.38)
                xx = cx
                while xx < cx + cw:
                    ex = min(xx + dp(5), cx + cw)
                    Line(points=[xx, fy, ex, fy], width=0.7)
                    xx += dp(10)

            # ── current price dashed line ───────────────
            if price > 0 and mn <= price <= mx:
                py_ = ty(price)
                Color(0.96, 0.76, 0.10, 0.75)
                xx = cx
                while xx < cx + cw:
                    ex = min(xx + dp(6), cx + cw)
                    Line(points=[xx, py_, ex, py_], width=1.0)
                    xx += dp(11)

            # ── OHLC candles ────────────────────────────
            n = len(candles)
            if n > 0:
                n_show = min(n, 50)
                shown  = list(candles)[-n_show:]
                nc     = len(shown)
                body_w = max(dp(2), cw / nc * 0.52)

                for i, (o_, h_, l_, c_) in enumerate(shown):
                    bx_   = tx(i, nc)
                    bull  = c_ >= o_
                    col   = C_GREEN if bull else C_RED
                    oy_   = ty(o_); cy_  = ty(c_)
                    hy_   = ty(h_); ly_  = ty(l_)
                    b_top = max(oy_, cy_)
                    b_bot = min(oy_, cy_)
                    b_h   = max(dp(1), b_top - b_bot)
                    Color(*col)
                    Line(points=[bx_, ly_, bx_, hy_],
                         width=max(0.8, body_w * 0.14))
                    Color(col[0], col[1], col[2], 0.90)
                    Rectangle(pos=(bx_ - body_w / 2, b_bot),
                               size=(body_w, b_h))

            # ── zigzag / price line ─────────────────────
            nt = len(ticks)
            if nt >= 2:
                t_show = ticks[-min(nt, 120):]
                nts    = len(t_show)
                Color(1.0, 0.78, 0.0, 0.88)
                pts = []
                for i, p in enumerate(t_show):
                    pts.extend([cx + i / max(nts - 1, 1) * cw,
                                 ty(p)])
                if len(pts) >= 4:
                    Line(points=pts, width=1.6)

        # ── Y-axis price labels ─────────────────────────
        fs_sm = int(7.5 * _sp())
        for i in range(5):
            p_val = mn + rng * i / 4
            gy    = cy + ch * i / 4
            _draw_text(self.canvas, cx - dp(3), gy,
                       f"{p_val:.1f}",
                       font_size=fs_sm, color=C_TEXT_3, anchor='right')

        # ── Chart title (top-left) ──────────────────────
        _draw_text(self.canvas, cx + dp(4), cy + ch + dp(10),
                   f"CHART {self._tf_label}",
                   font_size=int(8 * _sp()), color=C_TEXT_3, anchor='left')

        # ── Fibonacci right-side labels ─────────────────
        fs_fi = int(7 * _sp())
        lx_base = cx + cw + dp(4)
        for ratio, col, label in _FIBO_CHART_DEFS:
            px = fibo.get(ratio)
            if not px:
                continue
            fy = ty(px)
            if fy < cy - dp(4) or fy > cy + ch + dp(4):
                continue
            _draw_text(self.canvas, lx_base + dp(34), fy,
                       label, font_size=fs_fi,
                       color=(col[0], col[1], col[2], 0.88),
                       anchor='center')

        # ── Current price box (right) ───────────────────
        if price > 0 and mn <= price <= mx:
            py_  = ty(price)
            bx_l = cx + cw + dp(2)
            bw_  = dp(40); bh_ = dp(14)
            with self.canvas:
                Color(0.12, 0.10, 0.04, 1)
                Rectangle(pos=(bx_l, py_ - bh_ / 2), size=(bw_, bh_))
                Color(0.95, 0.75, 0.10, 0.9)
                Line(rectangle=[bx_l, py_ - bh_ / 2, bw_, bh_], width=0.8)
            _draw_text(self.canvas, bx_l + bw_ / 2, py_,
                       f"{price:.2f}", font_size=int(8 * _sp()),
                       color=(0.95, 0.75, 0.10, 1), anchor='center')

# ════════════════════════════════════════════════════════
#  RSI BAR ROW
# ════════════════════════════════════════════════════════
class RsiRow(BoxLayout):
    """Single timeframe RSI row with horizontal bar."""

    def __init__(self, tf_label, **kw):
        super().__init__(orientation='horizontal',
                         size_hint_y=None, height=dp(28),
                         spacing=dp(6), **kw)
        # TF label
        self._tf_lbl = Label(
            text=tf_label, font_size=int(10 * _sp()),
            color=C_TEXT_2, bold=True,
            size_hint=(None, 1), width=dp(32),
            halign='left', valign='middle')
        self._tf_lbl.bind(size=lambda w, v: setattr(
            w, 'text_size', v))

        # bar container
        self._bar_outer = Widget(size_hint=(1, None), height=dp(8))
        _add_bg(self._bar_outer, (0.10, 0.12, 0.20, 1), radius=3)
        self._bar_fill  = Widget(size_hint=(None, None),
                                  height=dp(8), width=0)
        _add_bg(self._bar_fill, C_GREEN, radius=3)
        self._bar_outer.add_widget(self._bar_fill)
        self._bar_outer.bind(pos=self._reposition,
                              size=self._reposition)

        # value + tag
        self._val_lbl = Label(
            text="—", font_size=int(10 * _sp()),
            color=C_TEXT, bold=True,
            size_hint=(None, 1), width=dp(46),
            halign='right', valign='middle')
        self._val_lbl.bind(size=lambda w, v: setattr(
            w, 'text_size', v))

        self.add_widget(self._tf_lbl)
        self.add_widget(self._bar_outer)
        self.add_widget(self._val_lbl)

        self._rsi_val = 0

    def _reposition(self, *_):
        self._bar_fill.pos  = self._bar_outer.pos
        self._bar_fill.height = self._bar_outer.height
        self._bar_fill.width  = (self._bar_outer.width
                                  * self._rsi_val / 100.0)

    def set_rsi(self, val):
        self._rsi_val = max(0, min(100, val))
        # color
        if val <= 30:
            col = C_RED;   tag = f"[color=ff5252]{val:.1f}\n[b]OS[/b][/color]"
        elif val >= 70:
            col = C_RED;   tag = f"[color=ff5252]{val:.1f}\n[b]OB[/b][/color]"
        elif val >= 50:
            col = C_GREEN; tag = f"{val:.1f}"
        else:
            col = C_AMBER; tag = f"{val:.1f}"

        if hasattr(self._bar_fill, '_bg_color'):
            self._bar_fill._bg_color.rgba = col
        self._val_lbl.markup = True
        self._val_lbl.text   = tag
        self._val_lbl.color  = col
        self._reposition()

# ════════════════════════════════════════════════════════
#  BOTTOM PANEL  (RSI + Console)
# ════════════════════════════════════════════════════════
class BottomPanel(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='horizontal',
                         size_hint_y=None, height=dp(210),
                         **kw)
        _add_bg(self, C_HEADER)
        with self.canvas.before:
            Color(*C_BORDER)
            self._top_sep = Rectangle(
                pos=(self.x, self.y + self.height - 1),
                size=(self.width, 1))
        self.bind(
            pos =lambda w, v: setattr(
                w._top_sep, 'pos', (v[0], v[1] + w.height - 1)),
            size=lambda w, v: setattr(
                w._top_sep, 'size', (v[0], 1)))

        # ── RSI panel (left 46%) ─────────────────────
        rsi_wrap = BoxLayout(orientation='vertical',
                             size_hint=(0.46, 1),
                             padding=[dp(10), dp(8)],
                             spacing=dp(3))

        # header row
        rsi_hdr = BoxLayout(size_hint_y=None, height=dp(22))
        rsi_hdr.add_widget(Label(
            text="[b]RSI-14 MULTI-TIMEFRAME[/b]",
            font_size=int(9.5 * _sp()), color=C_TEXT_2,
            markup=True, halign='left', valign='middle',
            size_hint=(1, 1), text_size=(1, None)))
        rsi_wrap.add_widget(rsi_hdr)

        self._rsi_rows = {}
        for tf in bot.TIMEFRAMES:
            row = RsiRow(bot.TF_LABEL[tf])
            self._rsi_rows[tf] = row
            rsi_wrap.add_widget(row)

        self.add_widget(rsi_wrap)

        # divider
        div = Widget(size_hint=(None, 1), width=dp(1))
        _add_bg(div, C_BORDER)
        self.add_widget(div)

        # ── Console panel (right 54%) ─────────────────
        con_wrap = BoxLayout(orientation='vertical',
                             size_hint=(0.54, 1),
                             padding=[dp(8), dp(6)],
                             spacing=dp(4))

        # header with LIVE badge
        con_hdr = BoxLayout(size_hint_y=None, height=dp(22),
                             spacing=dp(6))
        con_hdr.add_widget(Label(
            text="[b]AKTIVITAS LIVE BOT[/b]",
            font_size=int(9.5 * _sp()), color=C_TEXT_2,
            markup=True, halign='left', valign='middle',
            size_hint=(1, 1), text_size=(1, None)))
        live_badge = Button(
            text="LIVE CONSOLE", size_hint=(None, None),
            size=(dp(74), dp(18)),
            font_size=int(8 * _sp()), bold=True,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(live_badge, (0.10, 0.22, 0.10, 1), radius=3)
        live_badge.color = C_CONSOLE_TXT
        con_hdr.add_widget(live_badge)
        con_wrap.add_widget(con_hdr)

        # console box (dark terminal)
        self._console = BoxLayout(
            orientation='vertical', size_hint=(1, 1),
            padding=[dp(6), dp(4)], spacing=dp(2))
        _add_bg(self._console, C_CONSOLE_BG, radius=4)
        con_wrap.add_widget(self._console)

        self.add_widget(con_wrap)

    def refresh(self):
        # RSI
        with bot.S.lock:
            rsi_d  = dict(bot.S.rsi)
            ws_ok  = bot.S.ws_connected

        for tf, row in self._rsi_rows.items():
            v = rsi_d.get(tf, 0)
            if v > 0:
                row.set_rsi(v)

        # Console log
        logs = list(bot._log_buf)
        self._console.clear_widgets()
        shown = (logs[-7:] if logs
                 else ["[sistema aktif]"])
        for line in reversed(shown):
            l = Label(
                text=line, font_size=int(8.5 * _sp()),
                color=C_CONSOLE_TXT, halign='left',
                valign='top', markup=False,
                size_hint=(1, None))
            l.bind(
                texture_size=lambda w, ts: setattr(w, 'height', ts[1]),
                width=lambda w, wv: setattr(w, 'text_size', (wv, None)))
            self._console.add_widget(l)

# ════════════════════════════════════════════════════════
#  TAB BAR  (4 text tabs — DASHBOARD / SINYAL / FIBO / LOG)
# ════════════════════════════════════════════════════════
class TabBar(BoxLayout):
    TABS = [
        ('dashboard', 'DASHBOARD'),
        ('sinyal',    'SINYAL HARI INI'),
        ('fibo',      'LEVEL FIBO'),
        ('settings',  'LOG & SETTINGS'),
    ]

    def __init__(self, on_switch, **kw):
        super().__init__(orientation='horizontal',
                         size_hint_y=None, height=dp(44), **kw)
        _add_bg(self, C_HEADER)
        with self.canvas.before:
            Color(*C_BORDER)
            self._top_line = Rectangle(
                pos=(self.x, self.y + self.height - 1),
                size=(self.width, 1))
        self.bind(
            pos =lambda w, v: setattr(
                w._top_line, 'pos', (v[0], v[1] + w.height - 1)),
            size=lambda w, v: setattr(
                w._top_line, 'size', (v[0], 1)))

        self._on_switch = on_switch
        self._btns      = {}
        self._active    = 'dashboard'

        for key, label in self.TABS:
            btn = Button(
                text=label,
                font_size=int(8.5 * _sp()),
                bold=False,
                background_normal='',
                background_color=(0, 0, 0, 0),
                color=C_TEXT_3)
            btn.bind(on_press=lambda b, k=key: self._tap(k))
            self._btns[key] = btn
            self.add_widget(btn)

        self._set_active('dashboard')

    def _tap(self, key):
        self._set_active(key)
        self._on_switch(key)

    def set_active(self, key):
        self._set_active(key)

    def _set_active(self, key):
        self._active = key
        for k, btn in self._btns.items():
            active = (k == key)
            btn.bold  = active
            btn.color = C_TEXT if active else C_TEXT_3
            # underline via canvas.after
            btn.canvas.after.clear()
            if active:
                with btn.canvas.after:
                    Color(*C_GOLD)
                    Rectangle(pos=(btn.x, btn.y),
                               size=(btn.width, dp(2)))
            btn.bind(
                pos =lambda b, v: _tab_underline(b, b == self._btns.get(self._active)),
                size=lambda b, v: _tab_underline(b, b == self._btns.get(self._active)))

def _tab_underline(btn, active):
    btn.canvas.after.clear()
    if active:
        with btn.canvas.after:
            Color(*C_GOLD)
            Rectangle(pos=(btn.x, btn.y), size=(btn.width, dp(2)))

# ════════════════════════════════════════════════════════
#  HEADER BAR
# ════════════════════════════════════════════════════════
class HeaderBar(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='horizontal',
                         size_hint_y=None, height=dp(56),
                         padding=[dp(12), dp(8)], spacing=dp(8), **kw)
        _add_bg(self, C_HEADER)
        with self.canvas.after:
            Color(*C_BORDER)
            self._bot_line = Rectangle(
                pos=(self.x, self.y), size=(self.width, 1))
        self.bind(
            pos =lambda w, v: setattr(
                w._bot_line, 'pos', (v[0], v[1])),
            size=lambda w, v: setattr(
                w._bot_line, 'size', (v[0], 1)))

        # ── Logo icon (gold chart bars) ───────────────
        logo_box = BoxLayout(size_hint=(None, 1), width=dp(34))
        self._logo = Widget(size_hint=(None, None),
                            size=(dp(28), dp(28)))
        self._logo.bind(pos=self._draw_logo, size=self._draw_logo)
        logo_box.add_widget(Widget())  # centering spacers
        logo_box.add_widget(self._logo)
        logo_box.add_widget(Widget())
        self.add_widget(logo_box)

        # ── Title block ───────────────────────────────
        title_col = BoxLayout(orientation='vertical',
                               size_hint=(1, 1),
                               spacing=dp(1))
        row1 = BoxLayout(orientation='horizontal',
                          size_hint_y=None, height=dp(22),
                          spacing=dp(6))
        self._title_lbl = Label(
            text="[b]ZIGZAG_FIBO[/b]", markup=True,
            font_size=int(14 * _sp()), color=C_TEXT,
            size_hint=(None, 1), halign='left', valign='middle')
        self._title_lbl.bind(
            texture_size=lambda w, ts: setattr(w, 'width', ts[0] + dp(4)))
        ver_lbl = Label(
            text="v1.3", font_size=int(9 * _sp()),
            color=C_TEXT_2, size_hint=(None, 1),
            halign='left', valign='middle')
        ver_lbl.bind(
            texture_size=lambda w, ts: setattr(w, 'width', ts[0] + dp(2)))
        # WEB pill
        web_pill = Button(
            text="WEB", size_hint=(None, None),
            size=(dp(30), dp(16)),
            font_size=int(7 * _sp()), bold=True,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(web_pill, (0.12, 0.22, 0.36, 1), radius=3)
        web_pill.color = (0.40, 0.75, 1.00, 1)

        row1.add_widget(self._title_lbl)
        row1.add_widget(ver_lbl)
        row1.add_widget(web_pill)
        row1.add_widget(Widget())

        sub_lbl = Label(
            text="XAUUSD Trading Engine · Swing Fibonacci",
            font_size=int(8 * _sp()), color=C_TEXT_3,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(14))
        sub_lbl.bind(size=lambda w, v: setattr(w, 'text_size', v))

        title_col.add_widget(row1)
        title_col.add_widget(sub_lbl)
        self.add_widget(title_col)

        # ── Right indicators ──────────────────────────
        right_col = BoxLayout(orientation='vertical',
                               size_hint=(None, 1), width=dp(92),
                               spacing=dp(4))
        # Feed pill
        self._feed_btn = Button(
            text="Feed: SIMULATOR",
            size_hint=(None, None), size=(dp(90), dp(20)),
            font_size=int(7.5 * _sp()), bold=False,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(self._feed_btn, (0.10, 0.13, 0.20, 1), radius=4)
        with self._feed_btn.canvas.before:
            Color(*C_BORDER)
            self._feed_border = RoundedRectangle(
                pos=self._feed_btn.pos,
                size=self._feed_btn.size,
                radius=[dp(4)] * 4)
        self._feed_btn.bind(
            pos =lambda w, v: setattr(w._feed_border, 'pos', v),
            size=lambda w, v: setattr(w._feed_border, 'size', v))
        self._feed_btn.color = C_TEXT_2

        # WS indicator
        self._ws_row = BoxLayout(orientation='horizontal',
                                  size_hint=(None, None),
                                  size=(dp(90), dp(16)),
                                  spacing=dp(4))
        self._ws_dot = Label(text="●", font_size=int(8 * _sp()),
                              color=C_GREEN, size_hint=(None, 1),
                              width=dp(14))
        self._ws_lbl = Label(text="WS STREAMS",
                              font_size=int(8 * _sp()),
                              color=C_TEXT_2, size_hint=(1, 1),
                              halign='left', valign='middle')
        self._ws_lbl.bind(size=lambda w, v: setattr(w, 'text_size', v))
        self._ws_row.add_widget(self._ws_dot)
        self._ws_row.add_widget(self._ws_lbl)

        right_col.add_widget(Widget())
        right_col.add_widget(self._feed_btn)
        right_col.add_widget(self._ws_row)
        right_col.add_widget(Widget())
        self.add_widget(right_col)

        # clock
        Clock.schedule_interval(self._tick, 1)
        self._tick()

    def _draw_logo(self, *_):
        w = self._logo
        w.canvas.clear()
        sz  = min(w.width, w.height)
        bars = [0.5, 0.85, 0.55, 1.0, 0.70, 0.40, 0.75]
        bw   = sz / (len(bars) * 1.55)
        bgap = bw * 0.5
        total_w = bw * len(bars) + bgap * (len(bars) - 1)
        ox = w.x + (w.width - total_w) / 2
        oy = w.y + (w.height - sz) / 2
        with w.canvas:
            for i, hr in enumerate(bars):
                bh = sz * hr
                Color(1.0, 0.78, 0.10, 0.9)
                Rectangle(pos=(ox + i * (bw + bgap),
                               oy + sz - bh),
                          size=(bw, bh))

    def _tick(self, *_):
        pass  # clock removed from header (no lbl here)

    def refresh(self, ws_ok):
        col = C_GREEN if ws_ok else C_RED
        self._ws_dot.color = col
        self._ws_lbl.text  = "WS STREAMS" if ws_ok else "WS OFFLINE"
        self._ws_lbl.color = col

# ════════════════════════════════════════════════════════
#  DASHBOARD TAB
# ════════════════════════════════════════════════════════
class DashTab(ScrollView):
    def __init__(self, **kw):
        super().__init__(size_hint=(1, 1), **kw)
        root = BoxLayout(orientation='vertical',
                         padding=[dp(12), dp(10)],
                         spacing=dp(10), size_hint_y=None)
        root.bind(minimum_height=root.setter('height'))

        # ════════════════════════════════════════════
        #  1. GOLD SPOT PRICE CARD
        # ════════════════════════════════════════════
        pcard = BoxLayout(orientation='vertical',
                          size_hint_y=None,
                          padding=[dp(14), dp(10)],
                          spacing=dp(4))
        pcard.bind(minimum_height=pcard.setter('height'))
        _add_bg(pcard, C_SURFACE, radius=10)

        # row: GOLD SPOT XAU/USD + SIMULATING
        top_row = BoxLayout(size_hint_y=None, height=dp(24),
                             spacing=dp(6))
        gs_lbl = Label(text="GOLD SPOT", font_size=int(9.5 * _sp()),
                        color=C_TEXT_2, bold=True,
                        size_hint=(None, 1), halign='left',
                        valign='middle')
        gs_lbl.bind(texture_size=lambda w, ts: setattr(
            w, 'width', ts[0] + dp(2)))
        # XAU/USD tag
        xu_tag = Button(text="XAU/USD",
                         size_hint=(None, None), size=(dp(50), dp(18)),
                         font_size=int(8 * _sp()),
                         background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(xu_tag, (0.14, 0.17, 0.26, 1), radius=3)
        xu_tag.color = C_TEXT_2

        self.ws_lbl = Label(text="● SIMULATING",
                             font_size=int(9 * _sp()),
                             color=C_GREEN, bold=True,
                             size_hint=(1, 1),
                             halign='right', valign='middle')
        self.ws_lbl.bind(size=lambda w, v: setattr(
            w, 'text_size', v))

        top_row.add_widget(gs_lbl)
        top_row.add_widget(xu_tag)
        top_row.add_widget(self.ws_lbl)
        pcard.add_widget(top_row)

        # price + change
        price_row = BoxLayout(size_hint_y=None, height=dp(54),
                               spacing=dp(8))
        self.price_lbl = Label(
            text="—", font_size=int(40 * _sp()),
            color=C_RED, bold=True,
            size_hint=(None, 1), halign='left', valign='middle')
        self.price_lbl.bind(
            texture_size=lambda w, ts: setattr(w, 'width', ts[0] + dp(6)))
        self.chg_lbl = Label(
            text="", font_size=int(12 * _sp()),
            color=C_RED, size_hint=(None, 1),
            halign='left', valign='middle')
        self.chg_lbl.bind(
            texture_size=lambda w, ts: setattr(w, 'width', ts[0] + dp(4)))
        price_row.add_widget(self.price_lbl)
        price_row.add_widget(self.chg_lbl)
        price_row.add_widget(Widget())
        pcard.add_widget(price_row)

        # trend label row
        trend_row = BoxLayout(size_hint_y=None, height=dp(16))
        trend_row.add_widget(Label(
            text="RECENT TREND", font_size=int(8 * _sp()),
            color=C_TEXT_3, halign='left', valign='middle',
            size_hint=(None, 1), width=dp(90)))
        trend_row.add_widget(Widget())
        self.streak_lbl = Label(
            text="TICK STREAK", font_size=int(8 * _sp()),
            color=C_TEXT_3, halign='right', valign='middle',
            size_hint=(None, 1), width=dp(90))
        trend_row.add_widget(self.streak_lbl)
        pcard.add_widget(trend_row)

        # trend bars
        self._trend = TrendBars()
        pcard.add_widget(self._trend)
        root.add_widget(pcard)

        # ════════════════════════════════════════════
        #  2. STATISTIK SESI BOT
        # ════════════════════════════════════════════
        root.add_widget(spacer(4))
        scard = BoxLayout(orientation='vertical',
                          size_hint_y=None,
                          padding=[dp(14), dp(12)],
                          spacing=dp(8))
        scard.bind(minimum_height=scard.setter('height'))
        _add_bg(scard, C_SURFACE, radius=10)

        # section header
        shdr = BoxLayout(size_hint_y=None, height=dp(24),
                          spacing=dp(6))
        shdr.add_widget(Label(
            text="[b]STATISTIK SESI BOT[/b]",
            font_size=int(11 * _sp()), color=C_GOLD,
            markup=True, size_hint=(1, 1),
            halign='left', valign='middle'))
        scard.add_widget(shdr)

        scard.add_widget(h_sep(color=C_BORDER_DIM))

        # 2×2 stat grid
        grid = BoxLayout(orientation='horizontal',
                          size_hint_y=None, height=dp(100),
                          spacing=dp(1))
        left_col  = BoxLayout(orientation='vertical',
                               size_hint=(1, 1), spacing=dp(1))
        right_col = BoxLayout(orientation='vertical',
                               size_hint=(1, 1), spacing=dp(1))

        self.stat_labels = {}

        def stat_cell(key, title, val_color=C_TEXT):
            cell = BoxLayout(orientation='vertical',
                              size_hint=(1, 1),
                              padding=[dp(4), dp(6)])
            tl = Label(text=title,
                        font_size=int(8 * _sp()),
                        color=C_TEXT_3, markup=True,
                        size_hint=(1, None), height=dp(12),
                        halign='left', valign='middle')
            tl.bind(size=lambda w, v: setattr(w, 'text_size', v))
            vl = Label(text="—",
                        font_size=int(22 * _sp()),
                        color=val_color, bold=True,
                        size_hint=(1, None), height=dp(32),
                        halign='left', valign='middle')
            vl.bind(size=lambda w, v: setattr(w, 'text_size', v))
            sl = Label(text="",
                        font_size=int(8 * _sp()),
                        color=C_TEXT_3,
                        size_hint=(1, None), height=dp(12),
                        halign='left', valign='middle')
            sl.bind(size=lambda w, v: setattr(w, 'text_size', v))
            cell.add_widget(tl)
            cell.add_widget(vl)
            cell.add_widget(sl)
            self.stat_labels[key]          = vl
            self.stat_labels[key + '_sub'] = sl
            return cell

        left_col.add_widget(stat_cell(
            'wr',  'WIN RATE (TP1)',  val_color=C_GREEN))
        left_col.add_widget(h_sep(color=C_BORDER_DIM))
        left_col.add_widget(stat_cell(
            'dd',  'MAX DRAWDOWN',    val_color=C_RED))

        right_col.add_widget(stat_cell(
            'pnl', 'PROFIT & LOSS (PnL)', val_color=C_RED))
        right_col.add_widget(h_sep(color=C_BORDER_DIM))
        right_col.add_widget(stat_cell(
            'up',  'BOT UPTIME',      val_color=C_GREEN))

        grid.add_widget(left_col)
        grid.add_widget(Widget(size_hint=(None, 1), width=dp(1)))
        grid.add_widget(right_col)
        scard.add_widget(grid)

        scard.add_widget(h_sep(color=C_BORDER_DIM))

        # Winning streak row
        streak_row = BoxLayout(size_hint_y=None, height=dp(38),
                                padding=[dp(4), dp(6)],
                                spacing=dp(8))
        streak_info = BoxLayout(orientation='vertical',
                                 size_hint=(1, 1))
        streak_info.add_widget(Label(
            text="WINNING STREAK",
            font_size=int(8 * _sp()), color=C_TEXT_3,
            size_hint=(1, None), height=dp(14),
            halign='left', valign='middle'))
        streak_info.add_widget(Label(
            text="Streak berturut-turut harian",
            font_size=int(8 * _sp()), color=C_TEXT_3,
            size_hint=(1, None), height=dp(14),
            halign='left', valign='middle'))
        self._streak_badge = Button(
            text="—",
            size_hint=(None, None), size=(dp(64), dp(26)),
            font_size=int(9 * _sp()), bold=True,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(self._streak_badge, (0.10, 0.22, 0.12, 1), radius=5)
        self._streak_badge.color = C_GREEN

        streak_row.add_widget(streak_info)
        streak_row.add_widget(self._streak_badge)
        scard.add_widget(streak_row)

        root.add_widget(scard)

        # ════════════════════════════════════════════
        #  3. ALARM BATAS HARGA
        # ════════════════════════════════════════════
        root.add_widget(spacer(4))
        acard = BoxLayout(orientation='vertical',
                          size_hint_y=None,
                          padding=[dp(14), dp(12)],
                          spacing=dp(8))
        acard.bind(minimum_height=acard.setter('height'))
        _add_bg(acard, C_SURFACE, radius=10)

        ahdr = BoxLayout(size_hint_y=None, height=dp(24))
        ahdr.add_widget(Label(
            text="[b]ALARM BATAS HARGA[/b]",
            font_size=int(11 * _sp()), color=C_TEXT,
            markup=True, halign='left', valign='middle',
            size_hint=(1, 1)))
        acard.add_widget(ahdr)

        ainput_row = BoxLayout(size_hint_y=None, height=dp(36),
                                spacing=dp(8))
        self._alarm_input = TextInput(
            hint_text="0",
            size_hint=(1, None), height=dp(36),
            font_size=int(13 * _sp()),
            background_color=(0.10, 0.12, 0.18, 1),
            foreground_color=C_TEXT,
            hint_text_color=list(C_TEXT_3),
            cursor_color=list(C_GOLD),
            multiline=False, input_filter='float',
            padding=[dp(10), dp(8)])

        alarm_btn = Button(
            text="AKTIF",
            size_hint=(None, None), size=(dp(62), dp(36)),
            font_size=int(11 * _sp()), bold=True,
            background_normal='', background_color=(0, 0, 0, 0))
        _add_bg(alarm_btn, C_GOLD, radius=6)
        alarm_btn.color = (0.05, 0.05, 0.09, 1)
        alarm_btn.bind(on_press=self._set_alarm)

        ainput_row.add_widget(self._alarm_input)
        ainput_row.add_widget(alarm_btn)
        acard.add_widget(ainput_row)

        self.alarm_status = Label(
            text="Belum ada alarm aktif",
            font_size=int(9.5 * _sp()), color=C_TEXT_3,
            halign='left', valign='middle',
            size_hint_y=None, height=dp(18))
        self.alarm_status.bind(
            size=lambda w, v: setattr(w, 'text_size', v))
        acard.add_widget(self.alarm_status)

        root.add_widget(acard)

        # ════════════════════════════════════════════
        #  4. LIVE FIBONACCI ZIGZAG PLOTTER
        # ════════════════════════════════════════════
        root.add_widget(spacer(4))
        ccard = BoxLayout(orientation='vertical',
                          size_hint_y=None,
                          padding=[dp(10), dp(10)],
                          spacing=dp(8))
        ccard.bind(minimum_height=ccard.setter('height'))
        _add_bg(ccard, C_SURFACE, radius=10)

        # chart header row
        chdr = BoxLayout(size_hint_y=None, height=dp(26),
                          spacing=dp(6))
        chdr.add_widget(Label(
            text="[b]LIVE FIBONACCI ZIGZAG PLOTTER[/b]",
            font_size=int(10.5 * _sp()), color=C_TEXT,
            markup=True, size_hint=(1, 1),
            halign='left', valign='middle'))

        # TF pills
        self._active_tf  = '15min'
        self._tf_pill_btns = {}
        tf_row = BoxLayout(size_hint=(None, 1),
                            width=dp(148), spacing=dp(3))
        for tf in bot.TIMEFRAMES:
            p = Button(
                text=bot.TF_LABEL[tf],
                size_hint=(None, None),
                size=(dp(26), dp(22)),
                font_size=int(8.5 * _sp()), bold=False,
                background_normal='', background_color=(0, 0, 0, 0))
            active = (tf == '15min')
            _add_bg(p, C_GOLD if active else (0.11, 0.13, 0.21, 1),
                     radius=3)
            p.color = (0.05, 0.05, 0.08, 1) if active else C_TEXT_3
            p.bind(on_press=lambda b, t=tf: self._set_chart_tf(t))
            self._tf_pill_btns[tf] = p
            tf_row.add_widget(p)

        chdr.add_widget(tf_row)
        ccard.add_widget(chdr)

        self._chart = CandleChart()
        ccard.add_widget(self._chart)

        root.add_widget(ccard)

        root.add_widget(spacer(6))
        self.add_widget(root)
        self._popup_lbl = None

    # ── Alarm ─────────────────────────────────────────
    def _set_alarm(self, *_):
        txt = self._alarm_input.text.strip()
        try:
            level = float(txt)
        except ValueError:
            self.alarm_status.text  = "Masukkan angka yang valid"
            self.alarm_status.color = C_RED
            return
        _alarm["level"]     = level
        _alarm["active"]    = True
        _alarm["triggered"] = False
        self.alarm_status.text  = f"Alarm aktif @ {level:.3f}"
        self.alarm_status.color = C_GOLD

    def _set_chart_tf(self, tf):
        self._active_tf = tf
        for t, btn in self._tf_pill_btns.items():
            active = (t == tf)
            if hasattr(btn, '_bg_color'):
                btn._bg_color.rgba = (C_GOLD if active
                                      else (0.11, 0.13, 0.21, 1))
            btn.color = ((0.05, 0.05, 0.08, 1) if active
                          else C_TEXT_3)
        self.refresh()

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
            fibo_d = dict(bot.S.fibo.get(self._active_tf, {}))

        # ── price history ────────────────────────────
        if price > 0:
            if not _price_history or _price_history[-1] != price:
                _price_history.append(price)
                _push_tick(price)

        # ── alarm check ──────────────────────────────
        if (price > 0 and _alarm["active"]
                and not _alarm["triggered"]
                and abs(price - _alarm["level"]) < 0.5):
            _alarm["triggered"] = True
            _send_android_notif("ALARM XAUUSD",
                                f"Harga mendekati {_alarm['level']:.3f}!")
            self.alarm_status.text  = f"ALARM! Harga @ {price:.3f}"
            self.alarm_status.color = C_RED

        # ── WS / price display ───────────────────────
        if ws_ok:
            self.ws_lbl.text  = "● SIMULATING"
            self.ws_lbl.color = C_GREEN
        else:
            self.ws_lbl.text  = "○ OFFLINE"
            self.ws_lbl.color = C_RED

        if price > 0:
            self.price_lbl.text = f"{price:.2f}"
            if prev > 0:
                chg   = price - prev
                sign  = "+" if chg >= 0 else ""
                col   = C_GREEN if chg >= 0 else C_RED
                self.price_lbl.color = col
                self.chg_lbl.text    = f"{'▲' if chg>=0 else '▼'}{sign}{chg:.2f}"
                self.chg_lbl.color   = col

        # trend bars
        self._trend.update()

        # streak badge
        cnt   = _streak["count"]
        stype = _streak["type"]
        if cnt >= 1 and stype == "WIN":
            self._streak_badge.text = f"+ {cnt} WIN"
            if hasattr(self._streak_badge, '_bg_color'):
                self._streak_badge._bg_color.rgba = (0.10, 0.22, 0.12, 1)
            self._streak_badge.color = C_GREEN
        elif cnt >= 1 and stype == "LOSS":
            self._streak_badge.text = f"- {cnt} LOSS"
            if hasattr(self._streak_badge, '_bg_color'):
                self._streak_badge._bg_color.rgba = (0.25, 0.08, 0.08, 1)
            self._streak_badge.color = C_RED
        else:
            self._streak_badge.text = "—"

        # stats
        wr      = f"{round(wins/total*100)}%" if total else "—"
        up      = datetime.now(timezone.utc) - start
        up_str  = str(up).split('.')[0]
        pnl_str = (f"+${dpnl:.2f}" if dpnl >= 0 else f"-${abs(dpnl):.2f}")
        dd_str  = f"${dd:.2f}"

        self.stat_labels["wr"].text         = wr
        self.stat_labels["wr"].color        = C_GREEN
        self.stat_labels["wr_sub"].text     = f"1 dari {total} sinyal"

        self.stat_labels["pnl"].text        = pnl_str
        self.stat_labels["pnl"].color       = C_GREEN if dpnl >= 0 else C_RED
        self.stat_labels["pnl_sub"].text    = "Skala 1:100 leverage"

        self.stat_labels["dd"].text         = dd_str
        self.stat_labels["dd"].color        = C_RED
        self.stat_labels["dd_sub"].text     = "Floating peak draw"

        self.stat_labels["up"].text         = up_str
        self.stat_labels["up"].color        = C_GREEN
        self.stat_labels["up_sub"].text     = "Operational loop"

        # chart
        candles = list(_candle_bars)
        if _current_bar:
            candles.append((_current_bar.o, _current_bar.h,
                             _current_bar.l, _current_bar.c))
        fibo_levels = fibo_d.get('levels', {})
        self._chart.update(candles, fibo_levels, price, self._active_tf)

# ════════════════════════════════════════════════════════
#  SINYAL TAB
# ════════════════════════════════════════════════════════
_STATUS_CFG = {
    "WIN":     ((0.18, 0.78, 0.38, 1), "WIN ✓"),
    "LOSS":    ((0.88, 0.25, 0.25, 1), "LOSS ✗"),
    "OPEN":    ((0.90, 0.58, 0.08, 1), "OPEN"),
    "PENDING": ((0.40, 0.42, 0.52, 1), "PENDING"),
}

class SinyalTab(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', spacing=0, **kw)

        filter_row = BoxLayout(size_hint_y=None, height=dp(50),
                                padding=[dp(10), dp(10)],
                                spacing=dp(6))
        _add_bg(filter_row, C_HEADER)
        self._active_filter = "ALL"
        self._filter_btns   = {}
        for f in ("ALL", "OPEN", "WIN", "LOSS", "PENDING"):
            btn = pill_btn(f, active=(f == "ALL"), width=52)
            btn.bind(on_press=lambda b, flt=f: self._set_filter(flt))
            self._filter_btns[f] = btn
            filter_row.add_widget(btn)
        self.add_widget(filter_row)

        count_row = BoxLayout(size_hint_y=None, height=dp(28),
                               padding=[dp(14), dp(4)])
        _add_bg(count_row, C_BG)
        self.count_lbl = lbl("0 sinyal", size=11, color=C_TEXT_3)
        count_row.add_widget(self.count_lbl)
        self.add_widget(count_row)

        sv = ScrollView(size_hint=(1, 1))
        self.sig_box = BoxLayout(orientation='vertical', spacing=dp(6),
                                  size_hint_y=None,
                                  padding=[dp(12), dp(6)])
        self.sig_box.bind(minimum_height=self.sig_box.setter('height'))
        sv.add_widget(self.sig_box)
        self.add_widget(sv)

    def _set_filter(self, flt):
        self._active_filter = flt
        for f, btn in self._filter_btns.items():
            active = (f == flt)
            if hasattr(btn, '_bg_color'):
                btn._bg_color.rgba = C_GOLD if active else (0.12, 0.14, 0.21, 1)
            btn.color = (0.05, 0.05, 0.08, 1) if active else C_TEXT_2
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
            col_bg, st_text = _STATUS_CFG.get(
                st, ((0.14, 0.15, 0.20, 1), st))
            has_pnl = (st == "OPEN" and price > 0)
            conf    = _calc_confidence(sig)
            card_h  = dp(140) if has_pnl else dp(122)
            c_box   = BoxLayout(orientation='vertical',
                                size_hint_y=None, height=card_h,
                                padding=[dp(12), dp(8)],
                                spacing=dp(3))
            _add_bg(c_box, C_SURFACE, radius=10)

            t_col   = C_RED if sig['type'] == 'sell' else C_GREEN
            top_row = BoxLayout(size_hint_y=None, height=dp(24))
            dir_txt = ("[b]SELL ▼[/b]" if sig['type'] == 'sell'
                       else "[b]BUY ▲[/b]")
            top_row.add_widget(
                lbl(dir_txt, size=13, bold=True, color=t_col))
            top_row.add_widget(
                lbl(f"  {sig['tf']}  {sig.get('area','')}",
                    size=10.5, color=C_TEXT_2))
            top_row.add_widget(
                lbl(f"[b]{st_text}[/b]", size=9.5, bold=True,
                    color=col_bg, halign='right'))
            c_box.add_widget(top_row)

            c_box.add_widget(h_sep(color=(0.12, 0.14, 0.22, 1)))

            row2 = BoxLayout(size_hint_y=None, height=dp(22),
                              spacing=dp(4))
            row2.add_widget(
                lbl(f"Entry: [b]{sig['entry']:.3f}[/b]",
                    size=10.5, color=C_TEXT))
            row2.add_widget(
                lbl(f"SL: {sig['sl']:.3f}", size=10.5, color=C_RED))
            row2.add_widget(
                lbl(f"TP1: {sig['tp1']:.3f}", size=10.5,
                    color=C_GREEN, halign='right'))
            c_box.add_widget(row2)

            if has_pnl:
                unr = bot.calc_unrealized(
                    {"type": sig['type'], "entry": sig['entry']}, price)
                sign    = "+" if unr >= 0 else ""
                unr_col = C_GREEN if unr >= 0 else C_RED
                c_box.add_widget(
                    lbl(f"Unrealized P&L: [b]{sign}{unr:.2f}[/b]",
                        size=10.5, color=unr_col))

            conf_col = (C_GREEN if conf >= 70 else
                        C_AMBER if conf >= 50 else C_RED)
            conf_row = BoxLayout(size_hint_y=None, height=dp(20),
                                  spacing=dp(6))
            conf_row.add_widget(
                lbl(f"Confidence [b]{conf}%[/b]", size=10,
                    color=conf_col, size_hint_x=None, width=dp(116)))
            bar_out = BoxLayout(size_hint=(1, None), height=dp(6))
            _add_bg(bar_out, (0.10, 0.12, 0.20, 1), radius=3)
            bar_fill = BoxLayout(size_hint=(conf / 100, 1))
            _add_bg(bar_fill, conf_col, radius=3)
            bar_out.add_widget(bar_fill)
            conf_row.add_widget(bar_out)
            c_box.add_widget(conf_row)

            c_box.add_widget(
                lbl(sig.get('ts', ''), size=9, color=C_TEXT_3))
            self.sig_box.add_widget(c_box)

# ════════════════════════════════════════════════════════
#  FIBO TAB
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
        super().__init__(orientation='vertical', spacing=0, **kw)

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
                                 size_hint_y=None,
                                 padding=[dp(10), dp(4)])
        self.lv_box.bind(minimum_height=self.lv_box.setter('height'))
        sv.add_widget(self.lv_box)
        self.add_widget(sv)

    def _set_tf(self, tf):
        self._active_tf = tf
        for t, btn in self._tf_btns.items():
            active = (t == tf)
            if hasattr(btn, '_bg_color'):
                btn._bg_color.rgba = C_GOLD if active else (0.12, 0.14, 0.21, 1)
            btn.color = (0.05, 0.05, 0.08, 1) if active else C_TEXT_2
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
                lbl("Data belum tersedia. Menunggu...",
                    size=11.5, color=C_TEXT_3, halign='center'))
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
            is_near = (price > 0 and
                       abs(price - px) < (high - low) * 0.015)
            row_bg  = ((0.16, 0.19, 0.28, 1) if is_near else
                       (C_SURFACE_ALT if i % 2 == 0 else C_SURFACE))

            row = BoxLayout(size_hint_y=None, height=row_h,
                             padding=[dp(10), 0], spacing=dp(6))
            _add_bg(row, row_bg)

            lv_str = f"{lv:+.3f}".replace("+", " ")
            row.add_widget(lbl(f"[b]{lname}[/b]", size=11,
                               bold=True, color=col))
            row.add_widget(lbl(lv_str, size=9.5, color=C_TEXT_3))
            row.add_widget(Widget())
            row.add_widget(lbl(f"{px:.3f}", size=13, bold=True,
                               color=col, halign='right'))
            dist  = price - px if price > 0 else 0
            dsign = "+" if dist >= 0 else ""
            row.add_widget(lbl(
                f"{dsign}{dist:.1f}" if price > 0 else "",
                size=9.5, color=C_TEXT_3, halign='right'))

            self.lv_box.add_widget(row)
            self.lv_box.add_widget(h_sep())

# ════════════════════════════════════════════════════════
#  LOG & SETTINGS TAB
# ════════════════════════════════════════════════════════
class LogSettingsTab(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', spacing=0, **kw)

        hdr = BoxLayout(size_hint_y=None, height=dp(44),
                         padding=[dp(14), dp(10)])
        _add_bg(hdr, C_HEADER)
        hdr.add_widget(Label(
            text="[b]LOG & SETTINGS[/b]",
            font_size=int(12 * _sp()), color=C_TEXT,
            markup=True, halign='left', valign='middle',
            size_hint=(1, 1)))
        self.add_widget(hdr)

        sv = ScrollView(size_hint=(1, 1))
        wrap = BoxLayout(orientation='vertical',
                          size_hint_y=None,
                          padding=[dp(12), dp(10)],
                          spacing=dp(10))
        wrap.bind(minimum_height=wrap.setter('height'))

        # Log section
        log_title = BoxLayout(size_hint_y=None, height=dp(30))
        log_title.add_widget(Label(
            text="[b]AKTIVITAS LOG[/b]",
            font_size=int(10.5 * _sp()), color=C_TEXT_2,
            markup=True, halign='left', valign='middle',
            size_hint=(1, 1)))
        wrap.add_widget(log_title)

        log_outer = BoxLayout(orientation='vertical',
                               size_hint_y=None,
                               spacing=0, padding=[dp(12), dp(8)])
        log_outer.bind(minimum_height=log_outer.setter('height'))
        _add_bg(log_outer, C_SURFACE, radius=10)
        self._log_box = log_outer
        wrap.add_widget(log_outer)

        # Settings section
        s_title = BoxLayout(size_hint_y=None, height=dp(30))
        s_title.add_widget(Label(
            text="[b]INFORMASI BOT[/b]",
            font_size=int(10.5 * _sp()), color=C_TEXT_2,
            markup=True, halign='left', valign='middle',
            size_hint=(1, 1)))
        wrap.add_widget(s_title)

        info_card = BoxLayout(orientation='vertical',
                               size_hint_y=None,
                               padding=[dp(14), dp(10)],
                               spacing=dp(6))
        info_card.bind(minimum_height=info_card.setter('height'))
        _add_bg(info_card, C_SURFACE, radius=10)

        self._info_labels = {}
        for key, label in [
            ('version',  'Versi'),
            ('symbol',   'Simbol'),
            ('ws_status','WebSocket'),
            ('leverage', 'Leverage'),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(30))
            row.add_widget(lbl(label, size=11, color=C_TEXT_2))
            vl = lbl("—", size=11.5, bold=True, color=C_TEXT,
                      halign='right')
            row.add_widget(vl)
            self._info_labels[key] = vl
            info_card.add_widget(row)
            info_card.add_widget(h_sep(color=C_BORDER_DIM))

        self._info_labels['version'].text  = "v6-fix15"
        self._info_labels['symbol'].text   = "XAUUSD (Gold Spot)"
        self._info_labels['leverage'].text = "1:100"

        wrap.add_widget(info_card)

        # footer
        footer = lbl(
            "[color=444466]© 2026 ZigZag Fibo v1.3 · by GOGRAK · "
            "XAUUSD Swing Fibonacci Trading Bot[/color]",
            size=8, color=C_TEXT_3, halign='center')
        wrap.add_widget(spacer(10))
        wrap.add_widget(footer)

        sv.add_widget(wrap)
        self.add_widget(sv)

    def refresh(self):
        with bot.S.lock:
            ws_ok = bot.S.ws_connected

        self._info_labels['ws_status'].text  = (
            "Connected" if ws_ok else "Offline (REST)")
        self._info_labels['ws_status'].color = (
            C_GREEN if ws_ok else C_RED)

        logs = list(bot._log_buf)
        self._log_box.clear_widgets()
        if not logs:
            self._log_box.add_widget(
                lbl("Belum ada aktivitas.", size=11,
                    color=C_TEXT_3, halign='center'))
        for line in reversed(logs[-14:]):
            self._log_box.add_widget(
                lbl(line, size=10.5,
                    color=(0.50, 0.65, 0.80, 1)))

# ════════════════════════════════════════════════════════
#  ROOT WIDGET
# ════════════════════════════════════════════════════════
class RootWidget(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation='vertical', spacing=0, **kw)
        with self.canvas.before:
            Color(*C_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        # ── Header ────────────────────────────────────
        self._header = HeaderBar()
        self.add_widget(self._header)

        # ── Content area ──────────────────────────────
        self._content = BoxLayout(orientation='vertical',
                                   size_hint=(1, 1))
        self.add_widget(self._content)

        # ── Tab bar ───────────────────────────────────
        self._tabbar = TabBar(on_switch=self._switch)
        self.add_widget(self._tabbar)

        # ── Bottom panel (RSI + Console) ─────────────
        self._bottom = BottomPanel()
        self.add_widget(self._bottom)

        # ── Tab views ─────────────────────────────────
        self.dash_tab     = DashTab()
        self.sinyal_tab   = SinyalTab()
        self.fibo_tab     = FiboTab()
        self.settings_tab = LogSettingsTab()

        self._switch('dashboard')

        bot.ui_update_callback = self._schedule_refresh
        Clock.schedule_interval(self._refresh_all, 1)

    def _switch(self, tab):
        self._current_tab = tab
        self._content.clear_widgets()
        views = {
            'dashboard': self.dash_tab,
            'sinyal':    self.sinyal_tab,
            'fibo':      self.fibo_tab,
            'settings':  self.settings_tab,
        }
        self._content.add_widget(views[tab])
        self._tabbar.set_active(tab)

    def _schedule_refresh(self):
        Clock.schedule_once(self._refresh_all, 0)

    def _refresh_all(self, *_):
        _refresh_statuses()
        tab = getattr(self, '_current_tab', 'dashboard')

        with bot.S.lock:
            ws_ok = bot.S.ws_connected

        self._header.refresh(ws_ok)

        # Always refresh dashboard (for chart + stats) and bottom panel
        self.dash_tab.refresh()
        self._bottom.refresh()

        if tab == 'sinyal':
            self.sinyal_tab.refresh()
        elif tab == 'fibo':
            self.fibo_tab.refresh()
        elif tab == 'settings':
            self.settings_tab.refresh()

        # Background refresh every 5s
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
