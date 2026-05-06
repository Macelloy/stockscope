"""
StockScope – Teknisk Analyse App
"""

import threading
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.properties import StringProperty, NumericProperty, ListProperty

# ─── Color palette ────────────────────────────────────────────────────────────
BG_DARK     = (0.05, 0.07, 0.12, 1)
BG_CARD     = (0.09, 0.12, 0.19, 1)
BG_INPUT    = (0.12, 0.16, 0.25, 1)
ACCENT      = (0.22, 0.82, 0.64, 1)
ACCENT2     = (0.18, 0.65, 0.95, 1)
TEXT_MAIN   = (0.92, 0.95, 1.0,  1)
TEXT_SUB    = (0.55, 0.62, 0.75, 1)
RED         = (0.95, 0.35, 0.40, 1)
GREEN       = (0.22, 0.85, 0.55, 1)
YELLOW      = (0.98, 0.80, 0.20, 1)
BORDER      = (0.20, 0.28, 0.42, 1)

# ─── Technical Analysis ───────────────────────────────────────────────────────
def compute_rsi(prices, period=14):
    delta = prices.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

def compute_macd(prices, fast=12, slow=26, signal=9):
    ema_fast   = prices.ewm(span=fast).mean()
    ema_slow   = prices.ewm(span=slow).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram

def compute_bollinger(prices, period=20, std_dev=2):
    sma   = prices.rolling(period).mean()
    std   = prices.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower

def compute_stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low   = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(d_period).mean()
    return k, d

def compute_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_ema200(prices):
    return prices.ewm(span=200).mean()

def fetch_and_analyze(ticker):
    t   = yf.Ticker(ticker)
    df  = t.history(period="1y")
    if df.empty:
        return None, "Fant ingen data for ticker: " + ticker

    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    cur   = close.iloc[-1]

    # 1. RSI
    rsi_series = compute_rsi(close)
    rsi = rsi_series.iloc[-1]

    # 2. MACD
    macd_line, signal_line, histogram = compute_macd(close)
    macd_val  = macd_line.iloc[-1]
    sig_val   = signal_line.iloc[-1]
    hist_val  = histogram.iloc[-1]

    # 3. Bollinger Bands
    bb_upper, bb_mid, bb_lower = compute_bollinger(close)
    bbu = bb_upper.iloc[-1]
    bbm = bb_mid.iloc[-1]
    bbl = bb_lower.iloc[-1]
    bb_pct = (cur - bbl) / (bbu - bbl) * 100 if (bbu - bbl) != 0 else 50

    # 4. Stochastic
    stoch_k, stoch_d = compute_stochastic(high, low, close)
    sk = stoch_k.iloc[-1]
    sd = stoch_d.iloc[-1]

    # 5. ATR
    atr_val = compute_atr(high, low, close).iloc[-1]
    atr_pct = atr_val / cur * 100

    # 6. EMA 200 trend
    ema200 = compute_ema200(close).iloc[-1]
    ema50  = close.ewm(span=50).mean().iloc[-1]
    ema20  = close.ewm(span=20).mean().iloc[-1]

    # Price change
    prev = close.iloc[-2]
    chg  = cur - prev
    chg_pct = chg / prev * 100

    info_name = ""
    try:
        info = t.fast_info
        info_name = getattr(info, "long_name", ticker)
    except:
        info_name = ticker

    return {
        "ticker": ticker.upper(),
        "name": info_name,
        "price": cur,
        "change": chg,
        "change_pct": chg_pct,
        "currency": getattr(t.fast_info, "currency", "USD"),
        "rsi": rsi,
        "macd": macd_val,
        "macd_signal": sig_val,
        "macd_hist": hist_val,
        "bb_upper": bbu,
        "bb_mid": bbm,
        "bb_lower": bbl,
        "bb_pct": bb_pct,
        "stoch_k": sk,
        "stoch_d": sd,
        "atr": atr_val,
        "atr_pct": atr_pct,
        "ema200": ema200,
        "ema50": ema50,
        "ema20": ema20,
        "above_ema200": cur > ema200,
        "close_history": close.tolist()[-60:],
    }, None

# ─── UI Helpers ───────────────────────────────────────────────────────────────
class ColoredBox(Widget):
    def __init__(self, color=BG_CARD, radius=12, **kwargs):
        super().__init__(**kwargs)
        self._color  = color
        self._radius = radius
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._color)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[self._radius])

class CardLayout(BoxLayout):
    def __init__(self, bg=BG_CARD, radius=14, padding_val=dp(14),
                 spacing_val=dp(8), **kwargs):
        super().__init__(**kwargs)
        self.padding  = [padding_val] * 4
        self.spacing  = spacing_val
        self.bind(pos=self._redraw, size=self._redraw)
        self._bg     = bg
        self._radius = radius

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bg)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[self._radius])
            Color(*BORDER)
            Line(rounded_rectangle=[self.x, self.y,
                                     self.width, self.height,
                                     self._radius], width=1)

def mk_label(text, size=14, color=TEXT_MAIN, bold=False, halign="left", **kw):
    l = Label(text=text, font_size=sp(size), color=color,
              bold=bold, halign=halign, **kw)
    l.bind(size=lambda inst, v: setattr(inst, "text_size", v))
    return l

# ─── Gauge Widget ──────────────────────────────────────────────────────────────
class GaugeMini(Widget):
    """A tiny horizontal gauge bar."""
    def __init__(self, value=50, min_val=0, max_val=100,
                 zones=None, **kwargs):
        super().__init__(**kwargs)
        self.value   = value
        self.min_val = min_val
        self.max_val = max_val
        self.zones   = zones or [
            (0,   30,  RED),
            (30,  70,  YELLOW),
            (70, 100,  GREEN),
        ]
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.clear()
        w, h = self.size
        x, y = self.pos
        r    = dp(4)
        with self.canvas:
            # background track
            Color(0.15, 0.20, 0.30, 1)
            RoundedRectangle(pos=(x, y + h*0.35),
                             size=(w, h * 0.3), radius=[r])
            # fill
            norm  = (self.value - self.min_val) / (self.max_val - self.min_val)
            norm  = max(0, min(1, norm))
            fill_w = norm * w
            # pick colour based on zone
            fc = ACCENT
            for z_lo, z_hi, zc in self.zones:
                span = self.max_val - self.min_val
                if self.min_val + z_lo/100*span <= self.value <= self.min_val + z_hi/100*span:
                    fc = zc
            Color(*fc)
            RoundedRectangle(pos=(x, y + h*0.35),
                             size=(fill_w, h * 0.3), radius=[r])
            # pointer
            px = x + fill_w
            Color(1, 1, 1, 0.9)
            RoundedRectangle(pos=(px - dp(3), y + h*0.15),
                             size=(dp(6), h * 0.7), radius=[dp(3)])

# ─── Indicator Card ───────────────────────────────────────────────────────────
class IndicatorCard(CardLayout):
    def __init__(self, title, value_text, subtitle, gauge_val=None,
                 signal_text="", signal_color=TEXT_MAIN, **kwargs):
        super().__init__(orientation="vertical",
                         size_hint_y=None, height=dp(110), **kwargs)
        # Row 1: title + signal badge
        row1 = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(22), spacing=dp(6))
        row1.add_widget(mk_label(title, size=10, color=TEXT_SUB,
                                  size_hint_x=1))
        if signal_text:
            badge = CardLayout(bg=(signal_color[0]*0.2,
                                   signal_color[1]*0.2,
                                   signal_color[2]*0.2, 1),
                               radius=6, padding_val=dp(4),
                               spacing_val=0,
                               size_hint_x=None, size_hint_y=None,
                               width=dp(72), height=dp(20))
            badge.add_widget(mk_label(signal_text, size=9,
                                       color=signal_color, bold=True,
                                       halign="center"))
            row1.add_widget(badge)
        self.add_widget(row1)

        # Value
        self.add_widget(mk_label(value_text, size=22, color=TEXT_MAIN,
                                  bold=True, size_hint_y=None,
                                  height=dp(32)))

        # Gauge
        if gauge_val is not None:
            gauge = GaugeMini(value=gauge_val, size_hint_y=None, height=dp(20))
            self.add_widget(gauge)
        else:
            self.add_widget(Widget(size_hint_y=None, height=dp(20)))

        # Subtitle
        self.add_widget(mk_label(subtitle, size=9, color=TEXT_SUB))

# ─── Mini Sparkline ───────────────────────────────────────────────────────────
class Sparkline(Widget):
    def __init__(self, data, color=ACCENT, **kwargs):
        super().__init__(**kwargs)
        self.data  = data
        self._color = color
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.clear()
        if len(self.data) < 2:
            return
        w, h = self.width, self.height
        x0, y0 = self.pos
        mn, mx = min(self.data), max(self.data)
        rng = mx - mn or 1
        pts = []
        for i, v in enumerate(self.data):
            px = x0 + i / (len(self.data) - 1) * w
            py = y0 + (v - mn) / rng * h
            pts += [px, py]
        with self.canvas:
            Color(*self._color, 0.85)
            Line(points=pts, width=dp(1.5))

# ─── Main Screen ─────────────────────────────────────────────────────────────
class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.spacing = 0
        self._draw_bg()
        self._build_header()
        self._build_search()
        self._build_scroll()

    def _draw_bg(self):
        with self.canvas.before:
            Color(*BG_DARK)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg_rect, "pos", self.pos),
                  size=lambda *_: setattr(self._bg_rect, "size", self.size))

    def _build_header(self):
        hdr = BoxLayout(orientation="horizontal",
                        size_hint_y=None, height=dp(58),
                        padding=[dp(16), dp(10), dp(16), dp(6)])
        with hdr.canvas.before:
            Color(*BG_CARD)
            self._hdr_rect = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *_: setattr(self._hdr_rect, "pos", hdr.pos),
                 size=lambda *_: setattr(self._hdr_rect, "size", hdr.size))

        logo_lbl = mk_label("📈 StockScope", size=18, color=ACCENT,
                             bold=True, size_hint_x=1)
        hdr.add_widget(logo_lbl)
        sub = mk_label("Teknisk Analyse", size=10, color=TEXT_SUB,
                        halign="right", size_hint_x=None, width=dp(100))
        hdr.add_widget(sub)
        self.add_widget(hdr)

    def _build_search(self):
        row = BoxLayout(orientation="horizontal",
                        size_hint_y=None, height=dp(60),
                        padding=[dp(12), dp(8), dp(12), dp(8)],
                        spacing=dp(8))

        self.ticker_input = TextInput(
            hint_text="Ticker (f.eks. AAPL, EQNR.OL, ^GSPC)",
            font_size=sp(14), multiline=False,
            background_color=BG_INPUT,
            foreground_color=TEXT_MAIN,
            hint_text_color=TEXT_SUB,
            cursor_color=ACCENT,
            padding=[dp(12), dp(10), dp(12), dp(10)],
            size_hint_x=1,
        )
        self.ticker_input.bind(on_text_validate=self._on_search)

        search_btn = Button(
            text="Analyser",
            font_size=sp(13),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=BG_DARK,
            size_hint_x=None, width=dp(90),
        )
        with search_btn.canvas.before:
            Color(*ACCENT)
            self._btn_rect = RoundedRectangle(
                pos=search_btn.pos, size=search_btn.size, radius=[dp(10)])
        search_btn.bind(
            pos=lambda *_: setattr(self._btn_rect, "pos", search_btn.pos),
            size=lambda *_: setattr(self._btn_rect, "size", search_btn.size),
            on_press=self._on_search,
        )

        row.add_widget(self.ticker_input)
        row.add_widget(search_btn)
        self.add_widget(row)

    def _build_scroll(self):
        self.scroll = ScrollView(size_hint=(1, 1))
        self.content = BoxLayout(orientation="vertical",
                                  size_hint_y=None, spacing=dp(10),
                                  padding=[dp(12), dp(4), dp(12), dp(20)])
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.add_widget(self.scroll)

        self._show_placeholder()

    def _show_placeholder(self):
        self.content.clear_widgets()
        lbl = mk_label(
            "Skriv inn en ticker og trykk «Analyser»\n\n"
            "Eksempler:\n"
            "  AAPL   – Apple\n"
            "  EQNR.OL – Equinor (Oslo Børs)\n"
            "  ^GSPC  – S&P 500\n"
            "  EURUSD=X – EUR/USD",
            size=13, color=TEXT_SUB, halign="center",
            size_hint_y=None, height=dp(200),
        )
        self.content.add_widget(lbl)

    def _on_search(self, *_):
        ticker = self.ticker_input.text.strip().upper()
        if not ticker:
            return
        self._show_loading()
        thread = threading.Thread(target=self._do_fetch, args=(ticker,))
        thread.daemon = True
        thread.start()

    def _show_loading(self):
        self.content.clear_widgets()
        lbl = mk_label("⏳ Laster data…", size=15, color=TEXT_SUB,
                        halign="center", size_hint_y=None, height=dp(60))
        self.content.add_widget(lbl)

    def _do_fetch(self, ticker):
        data, err = fetch_and_analyze(ticker)
        Clock.schedule_once(lambda dt: self._update_ui(data, err), 0)

    def _update_ui(self, data, err):
        self.content.clear_widgets()
        if err or data is None:
            msg = err or "Ukjent feil"
            self.content.add_widget(
                mk_label(f"❌  {msg}", size=13, color=RED,
                          halign="center", size_hint_y=None, height=dp(60)))
            return
        self._build_result(data)

    def _build_result(self, d):
        c = self.content

        # ── Price header card ─────────────────────────────────────────────
        price_card = CardLayout(orientation="vertical",
                                bg=BG_CARD, radius=16,
                                padding_val=dp(16), spacing_val=dp(4),
                                size_hint_y=None, height=dp(130))
        row_name = BoxLayout(orientation="horizontal",
                              size_hint_y=None, height=dp(22))
        row_name.add_widget(mk_label(d["ticker"], size=14, color=ACCENT,
                                      bold=True, size_hint_x=None,
                                      width=dp(80)))
        row_name.add_widget(mk_label(d.get("name", ""), size=11,
                                      color=TEXT_SUB, size_hint_x=1))
        price_card.add_widget(row_name)

        chg_color = GREEN if d["change"] >= 0 else RED
        chg_sym   = "▲" if d["change"] >= 0 else "▼"
        price_str = f"{d['price']:.2f} {d['currency']}"
        price_card.add_widget(mk_label(price_str, size=28, bold=True,
                                        color=TEXT_MAIN,
                                        size_hint_y=None, height=dp(40)))
        chg_str = (f"{chg_sym} {abs(d['change']):.2f}"
                   f"  ({d['change_pct']:+.2f}%)")
        price_card.add_widget(mk_label(chg_str, size=13, color=chg_color,
                                        bold=True, size_hint_y=None,
                                        height=dp(22)))

        # sparkline
        spark_color = GREEN if d["change"] >= 0 else RED
        spark = Sparkline(data=d["close_history"], color=spark_color,
                          size_hint=(1, None), height=dp(30))
        price_card.add_widget(spark)
        c.add_widget(price_card)

        # ── EMA Trend banner ──────────────────────────────────────────────
        trend_up = d["above_ema200"]
        trend_color = GREEN if trend_up else RED
        trend_text  = "📈  Over EMA200 – BULLISH trend" if trend_up else \
                      "📉  Under EMA200 – BEARISH trend"
        banner = CardLayout(orientation="horizontal",
                             bg=(trend_color[0]*0.12,
                                  trend_color[1]*0.12,
                                  trend_color[2]*0.12, 1),
                             radius=10, padding_val=dp(10),
                             spacing_val=0,
                             size_hint_y=None, height=dp(40))
        banner.add_widget(mk_label(trend_text, size=12,
                                    color=trend_color, bold=True,
                                    halign="center"))
        c.add_widget(banner)

        # ── Section title ─────────────────────────────────────────────────
        c.add_widget(mk_label("6 TEKNISKE INDIKATORER", size=10,
                               color=TEXT_SUB, bold=True,
                               size_hint_y=None, height=dp(24)))

        # ── 2-column grid ─────────────────────────────────────────────────
        grid = GridLayout(cols=2, spacing=dp(8),
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        # 1. RSI
        rsi = d["rsi"]
        if rsi < 30:
            r_sig, r_col = "OVERSOLGT 🟢", GREEN
        elif rsi > 70:
            r_sig, r_col = "OVERKJØPT 🔴", RED
        else:
            r_sig, r_col = "NØYTRAL", YELLOW
        grid.add_widget(IndicatorCard(
            title="RSI (14)",
            value_text=f"{rsi:.1f}",
            subtitle=f"Sone: 30 = oversolgt · 70 = overkjøpt",
            gauge_val=rsi,
            signal_text=r_sig.split()[0],
            signal_color=r_col,
        ))

        # 2. MACD
        macd_bull = d["macd"] > d["macd_signal"]
        m_sig, m_col = ("BULLISH", GREEN) if macd_bull else ("BEARISH", RED)
        grid.add_widget(IndicatorCard(
            title="MACD (12/26/9)",
            value_text=f"{d['macd']:.3f}",
            subtitle=f"Signal: {d['macd_signal']:.3f}  Hist: {d['macd_hist']:+.3f}",
            signal_text=m_sig,
            signal_color=m_col,
        ))

        # 3. Bollinger Bands
        bb = d["bb_pct"]
        if bb > 80:
            bb_sig, bb_col = "OVERKJØPT", RED
        elif bb < 20:
            bb_sig, bb_col = "OVERSOLGT", GREEN
        else:
            bb_sig, bb_col = "MIDTSONE", YELLOW
        grid.add_widget(IndicatorCard(
            title="Bollinger Bands (20,2)",
            value_text=f"{bb:.0f}%B",
            subtitle=f"Øvre: {d['bb_upper']:.2f} · Nedre: {d['bb_lower']:.2f}",
            gauge_val=bb,
            signal_text=bb_sig,
            signal_color=bb_col,
        ))

        # 4. Stochastic
        sk, sd = d["stoch_k"], d["stoch_d"]
        if sk < 20:
            s_sig, s_col = "OVERSOLGT", GREEN
        elif sk > 80:
            s_sig, s_col = "OVERKJØPT", RED
        else:
            s_sig, s_col = "NØYTRAL", YELLOW
        grid.add_widget(IndicatorCard(
            title="Stokastisk (14,3)",
            value_text=f"K:{sk:.0f}  D:{sd:.0f}",
            subtitle="Under 20 = oversolgt · Over 80 = overkjøpt",
            gauge_val=sk,
            signal_text=s_sig,
            signal_color=s_col,
        ))

        # 5. ATR
        grid.add_widget(IndicatorCard(
            title="ATR (14) – Volatilitet",
            value_text=f"{d['atr']:.2f}",
            subtitle=f"{d['atr_pct']:.2f}% av kurs · {'Høy vol.' if d['atr_pct']>3 else 'Lav vol.'}",
            signal_text="HØY VOL" if d["atr_pct"] > 3 else "LAV VOL",
            signal_color=RED if d["atr_pct"] > 3 else GREEN,
        ))

        # 6. EMA 200 / 50 / 20
        ema_color = GREEN if d["above_ema200"] else RED
        cross = "Gyllen kryss ✨" if d["ema20"] > d["ema50"] else "Dødskryss 💀"
        grid.add_widget(IndicatorCard(
            title="EMA 20 / 50 / 200",
            value_text=f"{d['ema200']:.2f}",
            subtitle=f"EMA50: {d['ema50']:.2f} · EMA20: {d['ema20']:.2f}  {cross}",
            signal_text="OVER" if d["above_ema200"] else "UNDER",
            signal_color=ema_color,
        ))

        c.add_widget(grid)

        # ── Summary ───────────────────────────────────────────────────────
        bull_count = sum([
            rsi < 50,
            macd_bull,
            bb < 50,
            sk < 50,
            d["above_ema200"],
            d["ema20"] > d["ema50"],
        ])
        bear_count = 6 - bull_count
        if bull_count >= 4:
            summary_color = GREEN
            summary_icon  = "📈"
            summary_text  = f"Totalt signal: BULLISH ({bull_count}/6)"
        elif bear_count >= 4:
            summary_color = RED
            summary_icon  = "📉"
            summary_text  = f"Totalt signal: BEARISH ({bear_count}/6)"
        else:
            summary_color = YELLOW
            summary_icon  = "⚖️"
            summary_text  = f"Totalt signal: BLANDET ({bull_count} bull / {bear_count} bear)"

        sum_card = CardLayout(
            orientation="horizontal",
            bg=(summary_color[0]*0.15, summary_color[1]*0.15,
                 summary_color[2]*0.15, 1),
            radius=12, padding_val=dp(14), spacing_val=dp(8),
            size_hint_y=None, height=dp(56),
        )
        sum_card.add_widget(mk_label(summary_icon, size=22,
                                      size_hint_x=None, width=dp(32)))
        sum_card.add_widget(mk_label(summary_text, size=13,
                                      color=summary_color, bold=True))
        c.add_widget(sum_card)

        # disclaimer
        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        c.add_widget(mk_label(
            f"⚠️  Kun til informasjon. Ikke investeringsrådgivning.\nOppdatert: {ts}",
            size=9, color=TEXT_SUB, halign="center",
            size_hint_y=None, height=dp(36),
        ))

# ─── App ─────────────────────────────────────────────────────────────────────
class StockScopeApp(App):
    def build(self):
        Window.clearcolor = BG_DARK
        self.title = "StockScope"
        return MainScreen()

if __name__ == "__main__":
    StockScopeApp().run()
