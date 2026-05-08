"""
╔══════════════════════════════════════════════════════════════╗
║  ⚡ FOREX SIGNALS PRO — Twelve Data API                     ║
║  Velas OHLC reales + RSI + MACD + Bollinger + Estocástico   ║
║  Soporte/Resistencia + Acción de Precio + Patrones Velas    ║
║                                                              ║
║  SETUP:                                                      ║
║  1. Regístrate gratis en: https://twelvedata.com             ║
║  2. Copia tu API Key abajo (línea API_KEY = "...")           ║
║  3. pip install kivy  →  ejecutar en Pydroid 3              ║
╚══════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════
#  ⚙️  CONFIGURACIÓN — EDITA AQUÍ
# ══════════════════════════════
API_KEY   = "TU_API_KEY_AQUI"    # ← pega tu key de twelvedata.com
TIMEFRAME = "15min"              # 1min 5min 15min 30min 1h 4h 1day
CANDLES   = 60                   # velas a descargar por par
# ══════════════════════════════

import json, threading, datetime, math
from urllib.request import urlopen, Request
from urllib.error   import URLError

from kivy.app                    import App
from kivy.uix.screenmanager      import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout          import BoxLayout
from kivy.uix.scrollview         import ScrollView
from kivy.uix.label              import Label
from kivy.uix.button             import Button
from kivy.uix.widget             import Widget
from kivy.graphics               import (Color, Rectangle, RoundedRectangle,
                                          Line, Ellipse, Triangle)
from kivy.clock                  import Clock, mainthread
from kivy.core.window            import Window
from kivy.metrics                import dp

Window.clearcolor = (0.03, 0.05, 0.09, 1)

# ─── Paleta ───────────────────────────────────
BG     = (0.03, 0.05, 0.09, 1)
CARD   = (0.07, 0.10, 0.16, 1)
CARD2  = (0.09, 0.13, 0.20, 1)
CARD3  = (0.05, 0.08, 0.13, 1)
GREEN  = (0.05, 0.88, 0.52, 1)
RED    = (1.00, 0.25, 0.38, 1)
GOLD   = (1.00, 0.78, 0.18, 1)
BLUE   = (0.22, 0.58, 1.00, 1)
PURPLE = (0.68, 0.40, 1.00, 1)
CYAN   = (0.10, 0.85, 0.95, 1)
WHITE  = (1.00, 1.00, 1.00, 1)
GRAY   = (0.48, 0.54, 0.65, 1)
BORDER = (0.12, 0.18, 0.28, 1)
WARN   = (1.00, 0.65, 0.10, 1)

# ─── Pares Forex ──────────────────────────────
PAIRS = [
    ("EUR/USD", "Major"), ("GBP/USD", "Major"),
    ("USD/JPY", "Major"), ("USD/CHF", "Major"),
    ("AUD/USD", "Major"), ("USD/CAD", "Major"),
    ("NZD/USD", "Major"), ("EUR/GBP", "Cross"),
    ("EUR/JPY", "Cross"), ("GBP/JPY", "Cross"),
]

# ══════════════════════════════════════════════
#  📡  TWELVE DATA API
# ══════════════════════════════════════════════

class TwelveDataAPI:
    BASE = "https://api.twelvedata.com"

    @staticmethod
    def _get(url, timeout=10):
        try:
            req = Request(url, headers={"User-Agent": "ForexSignalsPro/2.0"})
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def get_ohlc(cls, symbol, interval=TIMEFRAME, outputsize=CANDLES):
        """Descarga velas OHLC reales del par"""
        url = (f"{cls.BASE}/time_series"
               f"?symbol={symbol}&interval={interval}"
               f"&outputsize={outputsize}&apikey={API_KEY}")
        data = cls._get(url)
        if "values" not in data:
            return []
        candles = []
        for v in reversed(data["values"]):   # más antiguo → más reciente
            try:
                candles.append({
                    "t": v["datetime"],
                    "o": float(v["open"]),
                    "h": float(v["high"]),
                    "l": float(v["low"]),
                    "c": float(v["close"]),
                })
            except (KeyError, ValueError):
                pass
        return candles

    @classmethod
    def fetch_pair_async(cls, symbol, callback):
        def worker():
            candles = cls.get_ohlc(symbol)
            Clock.schedule_once(lambda dt: callback(symbol, candles), 0)
        threading.Thread(target=worker, daemon=True).start()


# ══════════════════════════════════════════════
#  🧠  ANÁLISIS TÉCNICO COMPLETO
# ══════════════════════════════════════════════

class TA:
    """Technical Analysis — todos los indicadores calculados sobre OHLC real"""

    # ── Medias ──────────────────────────────────
    @staticmethod
    def sma(closes, n):
        if len(closes) < n:
            return closes[-1] if closes else 0.0
        return sum(closes[-n:]) / n

    @staticmethod
    def ema(closes, n):
        if not closes:
            return 0.0
        k, v = 2 / (n + 1), closes[0]
        for p in closes[1:]:
            v = p * k + v * (1 - k)
        return v

    # ── RSI ─────────────────────────────────────
    @classmethod
    def rsi(cls, closes, n=14):
        if len(closes) < n + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i-1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        ag = sum(gains[-n:]) / n
        al = sum(losses[-n:]) / n
        if al == 0:
            return 100.0
        rs = ag / al
        return round(100 - 100 / (1 + rs), 2)

    # ── MACD ────────────────────────────────────
    @classmethod
    def macd(cls, closes, fast=12, slow=26, signal=9):
        if len(closes) < slow:
            return 0.0, 0.0, 0.0
        macd_line   = cls.ema(closes, fast) - cls.ema(closes, slow)
        # Señal sobre los últimos valores del MACD
        macd_series = []
        for i in range(slow, len(closes) + 1):
            macd_series.append(cls.ema(closes[:i], fast) - cls.ema(closes[:i], slow))
        signal_line = cls.ema(macd_series, signal) if len(macd_series) >= signal else macd_series[-1]
        histogram   = macd_line - signal_line
        return round(macd_line, 6), round(signal_line, 6), round(histogram, 6)

    # ── Bollinger Bands ─────────────────────────
    @classmethod
    def bollinger(cls, closes, n=20, k=2.0):
        if len(closes) < n:
            c = closes[-1]
            return c, c, c
        window = closes[-n:]
        mid    = sum(window) / n
        std    = math.sqrt(sum((x - mid)**2 for x in window) / n)
        return round(mid - k * std, 6), round(mid, 6), round(mid + k * std, 6)

    # ── Estocástico ─────────────────────────────
    @classmethod
    def stochastic(cls, candles, k_period=14, d_period=3):
        if len(candles) < k_period:
            return 50.0, 50.0
        ks = []
        for i in range(k_period - 1, len(candles)):
            window = candles[i - k_period + 1 : i + 1]
            lo  = min(c["l"] for c in window)
            hi  = max(c["h"] for c in window)
            rng = hi - lo
            k_val = ((candles[i]["c"] - lo) / rng * 100) if rng > 0 else 50.0
            ks.append(k_val)
        k = round(ks[-1], 2)
        d = round(sum(ks[-d_period:]) / min(d_period, len(ks)), 2)
        return k, d

    # ── Soporte / Resistencia ───────────────────
    @classmethod
    def support_resistance(cls, candles, lookback=20):
        """
        Detecta niveles S/R por pivotes locales (fractal de 2 velas).
        Devuelve (soporte, resistencia) más relevantes.
        """
        if len(candles) < 5:
            closes = [c["c"] for c in candles]
            return min(closes), max(closes)

        highs  = [c["h"] for c in candles[-lookback:]]
        lows   = [c["l"] for c in candles[-lookback:]]
        closes = [c["c"] for c in candles[-lookback:]]

        pivot_highs, pivot_lows = [], []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                pivot_highs.append(highs[i])
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                pivot_lows.append(lows[i])

        curr = closes[-1]
        res  = min((h for h in pivot_highs if h > curr), default=max(highs))
        sup  = max((l for l in pivot_lows  if l < curr), default=min(lows))
        return round(sup, 6), round(res, 6)

    # ── Acción de Precio ────────────────────────
    @classmethod
    def price_action(cls, candles):
        """
        Evalúa acción de precio:
        - Rango de la vela actual vs promedio
        - Posición del cierre dentro del rango
        - Momentum de 3 velas
        Devuelve ('FUERTE_ALCISTA'|'FUERTE_BAJISTA'|'DÉBIL'|'NEUTRO', descripción)
        """
        if len(candles) < 5:
            return "NEUTRO", "Datos insuficientes"

        last   = candles[-1]
        body   = abs(last["c"] - last["o"])
        rng    = last["h"] - last["l"]
        ratio  = body / rng if rng > 0 else 0

        # Rango promedio de las últimas 10 velas
        avg_rng = sum(c["h"] - c["l"] for c in candles[-10:]) / 10
        big_bar = rng > avg_rng * 1.3

        # Posición del cierre (0=mínimo, 1=máximo)
        close_pos = (last["c"] - last["l"]) / rng if rng > 0 else 0.5

        # Momentum últimas 3 velas
        momentum = sum(1 if c["c"] > c["o"] else -1 for c in candles[-3:])

        if big_bar and close_pos > 0.65 and momentum > 0:
            return "FUERTE_ALCISTA", f"Barra expansiva alcista ({ratio:.0%} cuerpo)"
        elif big_bar and close_pos < 0.35 and momentum < 0:
            return "FUERTE_BAJISTA", f"Barra expansiva bajista ({ratio:.0%} cuerpo)"
        elif close_pos > 0.7:
            return "ALCISTA", "Cierre en zona alta"
        elif close_pos < 0.3:
            return "BAJISTA", "Cierre en zona baja"
        else:
            return "NEUTRO", "Indecisión"

    # ── Patrones de Velas ───────────────────────
    @classmethod
    def candlestick_patterns(cls, candles):
        """
        Detecta los 10 patrones más importantes.
        Devuelve lista de (nombre, tipo_señal, descripción)
        tipo_señal: 'BULLISH' | 'BEARISH' | 'REVERSAL'
        """
        patterns = []
        if len(candles) < 3:
            return patterns

        c0 = candles[-1]   # vela actual
        c1 = candles[-2]   # vela anterior
        c2 = candles[-3]   # dos atrás

        body0  = c0["c"] - c0["o"]
        body1  = c1["c"] - c1["o"]
        rng0   = c0["h"] - c0["l"]
        rng1   = c1["h"] - c1["l"]
        upper0 = c0["h"] - max(c0["c"], c0["o"])
        lower0 = min(c0["c"], c0["o"]) - c0["l"]

        # ── DOJI ──
        if rng0 > 0 and abs(body0) / rng0 < 0.1:
            patterns.append(("🕯 Doji", "REVERSAL",
                              "Indecisión — posible reversión"))

        # ── HAMMER (Martillo) ──
        if (body0 > 0 and lower0 > abs(body0) * 2 and
                upper0 < abs(body0) * 0.5 and body1 < 0):
            patterns.append(("🔨 Hammer", "BULLISH",
                              "Martillo — reversión alcista"))

        # ── SHOOTING STAR ──
        if (body0 < 0 and upper0 > abs(body0) * 2 and
                lower0 < abs(body0) * 0.5 and body1 > 0):
            patterns.append(("⭐ Shooting Star", "BEARISH",
                              "Estrella fugaz — reversión bajista"))

        # ── BULLISH ENGULFING ──
        if (body1 < 0 and body0 > 0 and
                c0["o"] <= c1["c"] and c0["c"] >= c1["o"] and
                abs(body0) > abs(body1)):
            patterns.append(("📈 Engulfing Alcista", "BULLISH",
                              "Envolvente — continuación alcista"))

        # ── BEARISH ENGULFING ──
        if (body1 > 0 and body0 < 0 and
                c0["o"] >= c1["c"] and c0["c"] <= c1["o"] and
                abs(body0) > abs(body1)):
            patterns.append(("📉 Engulfing Bajista", "BEARISH",
                              "Envolvente — continuación bajista"))

        # ── MORNING STAR (3 velas) ──
        if len(candles) >= 3:
            body2 = c2["c"] - c2["o"]
            if (body2 < 0 and abs(body1) < abs(body2) * 0.3
                    and body0 > 0 and c0["c"] > (c2["o"] + c2["c"]) / 2):
                patterns.append(("🌅 Morning Star", "BULLISH",
                                  "Estrella mañanera — reversión alcista"))

        # ── EVENING STAR ──
        if len(candles) >= 3:
            body2 = c2["c"] - c2["o"]
            if (body2 > 0 and abs(body1) < abs(body2) * 0.3
                    and body0 < 0 and c0["c"] < (c2["o"] + c2["c"]) / 2):
                patterns.append(("🌆 Evening Star", "BEARISH",
                                  "Estrella vespertina — reversión bajista"))

        # ── SPINNING TOP ──
        if (rng0 > 0 and abs(body0) / rng0 < 0.25 and
                upper0 > abs(body0) * 0.5 and lower0 > abs(body0) * 0.5):
            patterns.append(("🔄 Spinning Top", "REVERSAL",
                              "Trompo — indecisión fuerte"))

        # ── MARUBOZU (cuerpo completo sin mechas) ──
        if (rng0 > 0 and abs(body0) / rng0 > 0.92):
            tipo = "BULLISH" if body0 > 0 else "BEARISH"
            nombre = "🟢 Marubozu Alcista" if body0 > 0 else "🔴 Marubozu Bajista"
            patterns.append((nombre, tipo,
                              "Cuerpo completo — momentum fuerte"))

        # ── INSIDE BAR ──
        if (c0["h"] < c1["h"] and c0["l"] > c1["l"]):
            patterns.append(("📦 Inside Bar", "REVERSAL",
                              "Compresión — breakout inminente"))

        return patterns

    # ══════════════════════════════════════════
    #  SEÑAL MAESTRA — combina todo
    # ══════════════════════════════════════════
    @classmethod
    def master_signal(cls, candles):
        """
        Combina RSI + MACD + Bollinger + Estocástico + S/R +
        Acción de precio + Patrones → señal final con confianza %
        """
        if len(candles) < 10:
            return {
                "signal": "NEUTRAL", "confidence": 0,
                "rsi": 50, "macd": (0,0,0),
                "boll": (0,0,0), "stoch": (50,50),
                "support": 0, "resistance": 0,
                "price_action": ("NEUTRO", "—"),
                "patterns": [], "score_detail": {}
            }

        closes   = [c["c"] for c in candles]
        curr     = closes[-1]

        rsi_v               = cls.rsi(closes)
        macd_l, macd_s, macd_h = cls.macd(closes)
        boll_lo, boll_mid, boll_hi = cls.bollinger(closes)
        stoch_k, stoch_d    = cls.stochastic(candles)
        sup, res            = cls.support_resistance(candles)
        pa_signal, pa_desc  = cls.price_action(candles)
        patterns            = cls.candlestick_patterns(candles)

        # ── Sistema de puntuación ──────────────
        score   = 0
        details = {}

        # RSI (peso 2)
        if rsi_v < 30:
            score += 2;  details["RSI"] = f"+2 (sobreventa {rsi_v})"
        elif rsi_v < 40:
            score += 1;  details["RSI"] = f"+1 (débil {rsi_v})"
        elif rsi_v > 70:
            score -= 2;  details["RSI"] = f"-2 (sobrecompra {rsi_v})"
        elif rsi_v > 60:
            score -= 1;  details["RSI"] = f"-1 (fuerte {rsi_v})"
        else:
            details["RSI"] = f"0 (neutro {rsi_v})"

        # MACD histograma (peso 2)
        if macd_h > 0 and macd_l > macd_s:
            score += 2;  details["MACD"] = "+2 (cruce alcista)"
        elif macd_h > 0:
            score += 1;  details["MACD"] = "+1 (histograma positivo)"
        elif macd_h < 0 and macd_l < macd_s:
            score -= 2;  details["MACD"] = "-2 (cruce bajista)"
        elif macd_h < 0:
            score -= 1;  details["MACD"] = "-1 (histograma negativo)"
        else:
            details["MACD"] = "0 (neutro)"

        # Bollinger (peso 2)
        if curr < boll_lo:
            score += 2;  details["Bollinger"] = "+2 (bajo banda inferior)"
        elif curr < boll_mid:
            score += 1;  details["Bollinger"] = "+1 (bajo media)"
        elif curr > boll_hi:
            score -= 2;  details["Bollinger"] = "-2 (sobre banda superior)"
        elif curr > boll_mid:
            score -= 1;  details["Bollinger"] = "-1 (sobre media)"
        else:
            details["Bollinger"] = "0 (en media)"

        # Estocástico (peso 2)
        if stoch_k < 20 and stoch_d < 20:
            score += 2;  details["Estocástico"] = f"+2 (sobreventa {stoch_k})"
        elif stoch_k < 35:
            score += 1;  details["Estocástico"] = f"+1 (débil {stoch_k})"
        elif stoch_k > 80 and stoch_d > 80:
            score -= 2;  details["Estocástico"] = f"-2 (sobrecompra {stoch_k})"
        elif stoch_k > 65:
            score -= 1;  details["Estocástico"] = f"-1 (fuerte {stoch_k})"
        else:
            details["Estocástico"] = f"0 (neutro {stoch_k})"

        # Acción de precio (peso 2)
        if pa_signal == "FUERTE_ALCISTA":
            score += 2;  details["Price Action"] = f"+2 ({pa_desc})"
        elif pa_signal == "ALCISTA":
            score += 1;  details["Price Action"] = f"+1 ({pa_desc})"
        elif pa_signal == "FUERTE_BAJISTA":
            score -= 2;  details["Price Action"] = f"-2 ({pa_desc})"
        elif pa_signal == "BAJISTA":
            score -= 1;  details["Price Action"] = f"-1 ({pa_desc})"
        else:
            details["Price Action"] = f"0 ({pa_desc})"

        # Soporte / Resistencia (peso 1)
        mid_sr = (sup + res) / 2 if (sup and res) else curr
        if curr < mid_sr:
            score += 1;  details["S/R"] = f"+1 (bajo S/R medio)"
        elif curr > mid_sr:
            score -= 1;  details["S/R"] = f"-1 (sobre S/R medio)"

        # Patrones de velas (peso 1 por patrón)
        for name, ptype, _ in patterns:
            if ptype == "BULLISH":
                score += 1;  details[f"Patrón:{name}"] = "+1 (alcista)"
            elif ptype == "BEARISH":
                score -= 1;  details[f"Patrón:{name}"] = "-1 (bajista)"

        # ── Decisión final ────────────────────
        max_score = 12 + len(patterns)
        pct = min(99, int(abs(score) / max_score * 100)) if max_score > 0 else 50

        if score >= 3:
            signal = "BUY"
        elif score <= -3:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        confidence = max(30, pct + (score * 3 if signal != "NEUTRAL" else 0))
        confidence = min(confidence, 99)

        return {
            "signal":      signal,
            "confidence":  confidence,
            "score":       score,
            "rsi":         rsi_v,
            "macd":        (macd_l, macd_s, macd_h),
            "boll":        (boll_lo, boll_mid, boll_hi),
            "stoch":       (stoch_k, stoch_d),
            "support":     sup,
            "resistance":  res,
            "price_action": (pa_signal, pa_desc),
            "patterns":    patterns,
            "score_detail": details,
            "curr":        curr,
        }


# ══════════════════════════════════════════════
#  📊  WIDGET — GRÁFICO DE VELAS REAL
# ══════════════════════════════════════════════

class CandleChart(Widget):
    def __init__(self, candles=None, boll=None, support=0, resistance=0, **kw):
        super().__init__(**kw)
        self.candles    = candles or []
        self.boll       = boll
        self.support    = support
        self.resistance = resistance
        self.bind(size=self._draw, pos=self._draw)

    def update(self, candles, boll, support, resistance):
        self.candles    = candles
        self.boll       = boll
        self.support    = support
        self.resistance = resistance
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        cs = self.candles
        if not cs or self.width <= 2 or self.height <= 2:
            return

        highs  = [c["h"] for c in cs]
        lows   = [c["l"] for c in cs]
        mn     = min(lows)
        mx     = max(highs)
        rng    = mx - mn or 0.0001

        # Ampliar rango si hay Bollinger
        if self.boll:
            mn = min(mn, self.boll[0])
            mx = max(mx, self.boll[2])
            rng = mx - mn or 0.0001

        def py(price):
            return self.y + 4 + ((price - mn) / rng) * (self.height - 8)

        n    = len(cs)
        pad  = dp(2)
        cw   = (self.width - pad * 2) / n - 1
        cw   = max(cw, 1)

        with self.canvas:
            # Fondo
            Color(0.05, 0.08, 0.13, 1)
            Rectangle(pos=self.pos, size=self.size)

            # ── Bollinger Bands ──
            if self.boll:
                blo, bmid, bhi = self.boll
                # Relleno entre bandas
                Color(0.22, 0.58, 1.00, 0.06)
                Rectangle(pos=(self.x, py(blo)),
                           size=(self.width, py(bhi) - py(blo)))
                # Línea superior
                Color(0.22, 0.58, 1.00, 0.5)
                Line(points=[self.x, py(bhi), self.x + self.width, py(bhi)],
                     width=0.8, dash_length=4, dash_offset=4)
                # Media
                Color(0.22, 0.58, 1.00, 0.8)
                Line(points=[self.x, py(bmid), self.x + self.width, py(bmid)],
                     width=0.7, dash_length=6, dash_offset=3)
                # Línea inferior
                Color(0.22, 0.58, 1.00, 0.5)
                Line(points=[self.x, py(blo), self.x + self.width, py(blo)],
                     width=0.8, dash_length=4, dash_offset=4)

            # ── Soporte / Resistencia ──
            if self.support:
                Color(0.05, 0.88, 0.52, 0.7)
                Line(points=[self.x, py(self.support),
                              self.x + self.width, py(self.support)],
                     width=1.0, dash_length=5, dash_offset=3)
            if self.resistance:
                Color(1.00, 0.25, 0.38, 0.7)
                Line(points=[self.x, py(self.resistance),
                              self.x + self.width, py(self.resistance)],
                     width=1.0, dash_length=5, dash_offset=3)

            # ── Velas ──
            for i, c in enumerate(cs):
                x = self.x + pad + i * (cw + 1)
                bull = c["c"] >= c["o"]
                col  = GREEN if bull else RED
                Color(*col)

                # Mecha
                mid = x + cw / 2
                Line(points=[mid, py(c["l"]), mid, py(c["h"])], width=0.9)

                # Cuerpo
                top = py(max(c["c"], c["o"]))
                bot = py(min(c["c"], c["o"]))
                h   = max(top - bot, 1)
                if bull:
                    Color(*GREEN, 0.9)
                else:
                    Color(*RED, 0.9)
                Rectangle(pos=(x, bot), size=(cw, h))


# ══════════════════════════════════════════════
#  🃏  TARJETA DE PAR — COMPLETA
# ══════════════════════════════════════════════

class Card(BoxLayout):
    def __init__(self, radius=10, bg=None, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*(bg or CARD))
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=lambda *a: setattr(self._r, 'pos', self.pos),
                  size=lambda *a: setattr(self._r, 'size', self.size))


class StrengthBar(Widget):
    def __init__(self, value=50, signal="NEUTRAL", **kw):
        super().__init__(**kw)
        self.value  = value
        self.signal = signal
        self.bind(size=self._d, pos=self._d)

    def set(self, value, signal):
        self.value  = value
        self.signal = signal
        self._d()

    def _d(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*BORDER)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[3])
            w = max(4, self.width * self.value / 100)
            c = GREEN if self.signal == "BUY" else (RED if self.signal == "SELL" else GOLD)
            Color(*c)
            RoundedRectangle(pos=self.pos, size=(w, self.height), radius=[3])


class PairCard(Card):
    def __init__(self, symbol, category, **kw):
        super().__init__(
            orientation='vertical', padding=dp(10), spacing=dp(5),
            size_hint_y=None, height=dp(390), bg=CARD, **kw)
        self.symbol   = symbol
        self.category = category
        self.candles  = []
        self.analysis = {}
        self._build()

    def _build(self):
        # ── Header ──
        h1 = BoxLayout(size_hint_y=None, height=dp(28))
        self._sym_lbl   = self._lbl(self.symbol, 15, WHITE, bold=True, sx=0.35, ha='left')
        self._cat_lbl   = self._lbl(self.category, 9, BLUE, sx=0.20, ha='center')
        self._price_lbl = self._lbl("Cargando…", 13, GOLD, sx=0.45, ha='right')
        h1.add_widget(self._sym_lbl)
        h1.add_widget(self._cat_lbl)
        h1.add_widget(self._price_lbl)
        self.add_widget(h1)

        # ── Señal maestra ──
        h2 = BoxLayout(size_hint_y=None, height=dp(28))
        self._sig_lbl  = self._lbl("◆  NEUTRAL", 14, GOLD, bold=True, sx=0.38, ha='left')
        self._conf_lbl = self._lbl("Confianza: —", 10, GRAY, sx=0.32, ha='center')
        self._tf_lbl   = self._lbl(TIMEFRAME, 10, CYAN, sx=0.30, ha='right')
        h2.add_widget(self._sig_lbl)
        h2.add_widget(self._conf_lbl)
        h2.add_widget(self._tf_lbl)
        self.add_widget(h2)

        # Barra de confianza
        self._bar = StrengthBar(size_hint_y=None, height=dp(5))
        self.add_widget(self._bar)

        # ── Gráfico de velas ──
        self._chart = CandleChart(size_hint_y=None, height=dp(90))
        self.add_widget(self._chart)

        # ── Indicadores fila 1: RSI + Stoch ──
        r3 = BoxLayout(size_hint_y=None, height=dp(20))
        self._rsi_lbl   = self._lbl("RSI: —", 9, GRAY, sx=0.25, ha='left')
        self._stk_lbl   = self._lbl("Stoch: —", 9, GRAY, sx=0.30, ha='center')
        self._macd_lbl  = self._lbl("MACD: —", 9, GRAY, sx=0.45, ha='right')
        r3.add_widget(self._rsi_lbl)
        r3.add_widget(self._stk_lbl)
        r3.add_widget(self._macd_lbl)
        self.add_widget(r3)

        # ── Bollinger ──
        r4 = BoxLayout(size_hint_y=None, height=dp(18))
        self._boll_lbl = self._lbl("Bollinger: —", 9, BLUE, sx=1.0, ha='left')
        r4.add_widget(self._boll_lbl)
        self.add_widget(r4)

        # ── S/R ──
        r5 = BoxLayout(size_hint_y=None, height=dp(18))
        self._sup_lbl = self._lbl("Soporte: —", 9, GREEN, sx=0.5, ha='left')
        self._res_lbl = self._lbl("Resistencia: —", 9, RED, sx=0.5, ha='right')
        r5.add_widget(self._sup_lbl)
        r5.add_widget(self._res_lbl)
        self.add_widget(r5)

        # ── Acción de Precio ──
        r6 = BoxLayout(size_hint_y=None, height=dp(18))
        self._pa_lbl = self._lbl("Price Action: —", 9, GOLD, sx=1.0, ha='left')
        r6.add_widget(self._pa_lbl)
        self.add_widget(r6)

        # ── Patrones ──
        self._pat_box = BoxLayout(
            orientation='vertical', size_hint_y=None, height=dp(0), spacing=dp(1))
        self.add_widget(self._pat_box)

        # ── Score detail (pequeño) ──
        r7 = BoxLayout(size_hint_y=None, height=dp(16))
        self._score_lbl = self._lbl("Score: —", 8, GRAY, sx=1.0, ha='left')
        r7.add_widget(self._score_lbl)
        self.add_widget(r7)

    # helper Label
    def _lbl(self, text, fs, color, bold=False, sx=1.0, ha='left', va='middle'):
        l = Label(text=text, font_size=dp(fs), color=color, bold=bold,
                  size_hint_x=sx, halign=ha, valign=va)
        l.bind(size=l.setter('text_size'))
        return l

    @mainthread
    def update(self, candles):
        self.candles  = candles
        a             = TA.master_signal(candles)
        self.analysis = a

        curr = a.get("curr", 0)
        sym  = self.symbol
        # Formateo de precio
        fmt = f"{curr:.3f}" if "JPY" in sym else f"{curr:.5f}"
        self._price_lbl.text = fmt

        # Señal
        sig   = a["signal"]
        conf  = a["confidence"]
        score = a.get("score", 0)
        icon  = "▲" if sig == "BUY" else ("▼" if sig == "SELL" else "◆")
        sc    = GREEN if sig == "BUY" else (RED if sig == "SELL" else GOLD)
        self._sig_lbl.text  = f"{icon}  {sig}"
        self._sig_lbl.color = sc
        self._conf_lbl.text = f"Confianza: {conf}%"
        self._bar.set(conf, sig)

        # RSI
        rsi = a["rsi"]
        rc  = RED if rsi > 70 else (GREEN if rsi < 30 else GRAY)
        self._rsi_lbl.text  = f"RSI: {rsi}"
        self._rsi_lbl.color = rc

        # Estocástico
        k, d = a["stoch"]
        sc2  = RED if k > 80 else (GREEN if k < 20 else GRAY)
        self._stk_lbl.text  = f"Stoch K:{k} D:{d}"
        self._stk_lbl.color = sc2

        # MACD
        ml, ms, mh = a["macd"]
        mc  = GREEN if mh > 0 else RED
        self._macd_lbl.text  = f"MACD H:{mh:+.5f}"
        self._macd_lbl.color = mc

        # Bollinger
        blo, bmid, bhi = a["boll"]
        self._boll_lbl.text = (f"Boll  Lo:{blo:.5f}  "
                                f"Mid:{bmid:.5f}  Hi:{bhi:.5f}")

        # S/R
        sup, res = a["support"], a["resistance"]
        self._sup_lbl.text = f"Soporte: {sup:.5f}"
        self._res_lbl.text = f"Resistencia: {res:.5f}"

        # Price Action
        pa_sig, pa_desc = a["price_action"]
        pac = GREEN if "ALCISTA" in pa_sig else (RED if "BAJISTA" in pa_sig else GOLD)
        self._pa_lbl.text  = f"PA: {pa_sig}  •  {pa_desc}"
        self._pa_lbl.color = pac

        # Patrones de velas
        patterns = a["patterns"]
        self._pat_box.clear_widgets()
        ph = dp(16) * len(patterns) if patterns else 0
        self._pat_box.height = ph
        for pname, ptype, pdesc in patterns:
            pc = GREEN if ptype == "BULLISH" else (RED if ptype == "BEARISH" else GOLD)
            pl = Label(text=f"{pname}  •  {pdesc}",
                       font_size=dp(8.5), color=pc,
                       size_hint_y=None, height=dp(15),
                       halign='left', valign='middle')
            pl.bind(size=pl.setter('text_size'))
            self._pat_box.add_widget(pl)

        # Ajustar altura total de la card
        base_h = dp(265)
        self.height = base_h + ph

        # Score
        detail_str = "  |  ".join(list(a["score_detail"].values())[:3])
        self._score_lbl.text = f"Score:{score:+d}  •  {detail_str}"

        # Actualizar gráfico
        self._chart.update(candles, a["boll"], a["support"], a["resistance"])


# ══════════════════════════════════════════════
#  📱  PANTALLA PRINCIPAL
# ══════════════════════════════════════════════

class MainScreen(Screen):
    REFRESH_SEC = 60   # Twelve Data free: 800 req/día → ~1 req/min por par

    def __init__(self, **kw):
        super().__init__(**kw)
        self._cards   = {}
        self._loading = set()
        self._filter  = "All"
        self._build_ui()
        Clock.schedule_once(lambda dt: self._load_all(), 1)
        Clock.schedule_interval(lambda dt: self._load_all(), self.REFRESH_SEC * len(PAIRS))

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        # ── Top bar ──
        tb = Card(orientation='horizontal', padding=(dp(14), dp(8)),
                  spacing=dp(8), size_hint_y=None, height=dp(54), bg=CARD2, radius=0)
        logo = Label(text="⚡ Forex Signals PRO", font_size=dp(17),
                     bold=True, color=GOLD, size_hint_x=0.55,
                     halign='left', valign='middle')
        logo.bind(size=logo.setter('text_size'))
        self._status = Label(text="Iniciando…", font_size=dp(9),
                             color=WARN, size_hint_x=0.45,
                             halign='right', valign='middle')
        self._status.bind(size=self._status.setter('text_size'))
        tb.add_widget(logo)
        tb.add_widget(self._status)
        root.add_widget(tb)

        # ── API key warning si no está configurada ──
        if API_KEY == "TU_API_KEY_AQUI":
            warn = BoxLayout(size_hint_y=None, height=dp(30),
                             padding=(dp(10), dp(2)))
            with warn.canvas.before:
                Color(0.5, 0.2, 0.0, 1)
                self._wr = Rectangle(pos=warn.pos, size=warn.size)
            warn.bind(pos=lambda *a: setattr(self._wr, 'pos', warn.pos),
                      size=lambda *a: setattr(self._wr, 'size', warn.size))
            wl = Label(
                text="⚠  Configura tu API KEY de twelvedata.com en la línea 22 del código",
                font_size=dp(9), color=WARN, halign='left', valign='middle')
            wl.bind(size=wl.setter('text_size'))
            warn.add_widget(wl)
            root.add_widget(warn)

        # ── Info bar ──
        ib = BoxLayout(size_hint_y=None, height=dp(22), padding=(dp(12), 0))
        with ib.canvas.before:
            Color(0.05, 0.08, 0.13, 1)
            self._ibr = Rectangle(pos=ib.pos, size=ib.size)
        ib.bind(pos=lambda *a: setattr(self._ibr, 'pos', ib.pos),
                size=lambda *a: setattr(self._ibr, 'size', ib.size))
        il = Label(
            text=f"API: twelvedata.com  •  Timeframe: {TIMEFRAME}  •  {CANDLES} velas OHLC reales",
            font_size=dp(8.5), color=GRAY, halign='left', valign='middle')
        il.bind(size=il.setter('text_size'))
        ib.add_widget(il)
        root.add_widget(ib)

        # ── Filtros ──
        fb = BoxLayout(size_hint_y=None, height=dp(40),
                       padding=(dp(8), dp(4)), spacing=dp(5))
        with fb.canvas.before:
            Color(*CARD2)
            self._fbr = Rectangle(pos=fb.pos, size=fb.size)
        fb.bind(pos=lambda *a: setattr(self._fbr, 'pos', fb.pos),
                size=lambda *a: setattr(self._fbr, 'size', fb.size))

        self._fbtns = {}
        for f in ["All", "BUY", "SELL", "Major", "Cross"]:
            b = Button(text=f, font_size=dp(10), size_hint_x=None, width=dp(54),
                       background_normal='', background_color=(0,0,0,0))
            b.bind(on_press=lambda btn, fl=f: self._set_filter(fl))
            self._fbtns[f] = b
            fb.add_widget(b)
        self._upd_fbtns("All")

        rb = Button(text="↻ Refresh", font_size=dp(10),
                    size_hint_x=None, width=dp(80),
                    background_normal='', background_color=BLUE)
        rb.bind(on_press=lambda *_: self._load_all())
        fb.add_widget(rb)
        root.add_widget(fb)

        # ── Scroll de tarjetas ──
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self._cbox = BoxLayout(orientation='vertical', spacing=dp(8),
                               padding=(dp(8), dp(8)), size_hint_y=None)
        self._cbox.bind(minimum_height=self._cbox.setter('height'))
        scroll.add_widget(self._cbox)
        root.add_widget(scroll)

        # ── Bottom ──
        bot = BoxLayout(size_hint_y=None, height=dp(36))
        with bot.canvas.before:
            Color(*CARD2)
            self._bbr = Rectangle(pos=bot.pos, size=bot.size)
        bot.bind(pos=lambda *a: setattr(self._bbr, 'pos', bot.pos),
                 size=lambda *a: setattr(self._bbr, 'size', bot.size))
        self._time_lbl = Label(text="", font_size=dp(9), color=GRAY)
        bot.add_widget(self._time_lbl)
        root.add_widget(bot)

        self.add_widget(root)

        # Crear tarjetas
        for sym, cat in PAIRS:
            card = PairCard(sym, cat)
            self._cards[sym] = card
            self._cbox.add_widget(card)

        Clock.schedule_interval(self._tick, 1)

    def _load_all(self):
        self._set_status("⟳ Descargando velas OHLC reales…", WARN)
        for sym, _ in PAIRS:
            if sym not in self._loading:
                self._loading.add(sym)
                TwelveDataAPI.fetch_pair_async(sym, self._on_candles)

    @mainthread
    def _on_candles(self, symbol, candles):
        self._loading.discard(symbol)
        if candles and symbol in self._cards:
            self._cards[symbol].update(candles)
        if not self._loading:
            now = datetime.datetime.utcnow()
            self._set_status(
                f"✓ {len(PAIRS)} pares actualizados  •  {now.strftime('%H:%M:%S')} UTC",
                GREEN)
            self._apply_filter()

    def _set_filter(self, flt):
        self._filter = flt
        self._upd_fbtns(flt)
        self._apply_filter()

    def _apply_filter(self):
        flt = self._filter
        for sym, cat in PAIRS:
            card = self._cards[sym]
            a    = card.analysis
            sig  = a.get("signal", "NEUTRAL")
            show = True
            if flt == "BUY"   and sig  != "BUY":   show = False
            if flt == "SELL"  and sig  != "SELL":   show = False
            if flt == "Major" and cat  != "Major":  show = False
            if flt == "Cross" and cat  != "Cross":  show = False
            card.opacity     = 1 if show else 0
            card.height      = card.height if show else 0
            card.size_hint_y = None

    def _upd_fbtns(self, active):
        for n, b in self._fbtns.items():
            if n == active:
                b.color            = (0.03, 0.05, 0.09, 1)
                b.background_color = GOLD
            else:
                b.color            = GRAY
                b.background_color = BORDER

    def _set_status(self, text, color):
        self._status.text  = text
        self._status.color = color

    def _tick(self, dt):
        now = datetime.datetime.utcnow()
        self._time_lbl.text = f"UTC  {now.strftime('%H:%M:%S')}  •  twelvedata.com  •  {TIMEFRAME}"


# ══════════════════════════════════════════════
#  🚀  APP
# ══════════════════════════════════════════════

class ForexSignalsProApp(App):
    def build(self):
        self.title = "Forex Signals PRO"
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(MainScreen(name="main"))
        return sm


if __name__ == "__main__":
    ForexSignalsProApp().run()
