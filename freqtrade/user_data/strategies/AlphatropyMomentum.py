# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
AlphatropyMomentum
==================

A custom Freqtrade strategy that combines trend-following with a momentum
pullback entry. The idea is simple and robust:

  1. Only trade in the direction of the dominant trend (EMA structure + ADX).
  2. Enter on a *pullback* inside that trend, when short-term momentum (RSI)
     turns back up from an oversold dip and MACD confirms.
  3. Exit when momentum becomes exhausted (RSI overbought / MACD roll-over)
     or the short-term trend breaks, with a trailing stop and ROI table as
     safety nets.

Every threshold that meaningfully affects behaviour is exposed as a
hyperoptable parameter so the strategy can be tuned with:

    freqtrade hyperopt --strategy AlphatropyMomentum \
        --hyperopt-loss SharpeHyperOptLoss --spaces buy sell roi stoploss

Author: Diego Reyes (Alphatropy)
Interface: Freqtrade IStrategy V3
"""
from datetime import datetime
from functools import reduce

import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
)


class AlphatropyMomentum(IStrategy):
    """Trend-following momentum pullback strategy (long, optional short)."""

    INTERFACE_VERSION = 3

    # Spot markets by default. Set to True (and use a futures config) to allow shorts.
    can_short: bool = False

    # ------------------------------------------------------------------ #
    # Core configuration                                                 #
    # ------------------------------------------------------------------ #
    timeframe = "1h"

    # Minimal ROI: take profit sooner the longer a trade is open.
    # Keys are minutes since the trade opened.
    minimal_roi = {
        "0": 0.08,
        "120": 0.04,
        "360": 0.02,
        "720": 0.0,
    }

    # Hard stoploss. Trailing stop (below) tightens this once in profit.
    stoploss = -0.10

    # Trailing stop: lock in gains once the trade is comfortably positive.
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.035
    trailing_only_offset_is_reached = True

    # Only evaluate signals on a closed candle to avoid repainting.
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Enough history for the slowest indicator (EMA 200 / ADX / MACD warm-up).
    startup_candle_count: int = 200

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC",
    }

    # ------------------------------------------------------------------ #
    # Hyperopt parameters                                                #
    # ------------------------------------------------------------------ #
    # Trend / regime filter
    ema_fast = IntParameter(8, 30, default=21, space="buy", optimize=True)
    ema_slow = IntParameter(40, 120, default=50, space="buy", optimize=True)
    adx_threshold = IntParameter(15, 40, default=25, space="buy", optimize=True)

    # Momentum entry
    buy_rsi = IntParameter(20, 45, default=35, space="buy", optimize=True)
    volume_factor = DecimalParameter(
        0.5, 2.5, default=1.0, decimals=1, space="buy", optimize=True
    )
    require_macd = BooleanParameter(default=True, space="buy", optimize=True)

    # Momentum exit
    sell_rsi = IntParameter(60, 85, default=72, space="sell", optimize=True)
    use_ema_exit = BooleanParameter(default=True, space="sell", optimize=True)

    # ------------------------------------------------------------------ #
    # Indicators                                                         #
    # ------------------------------------------------------------------ #
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- Trend structure ---
        # Compute EMAs across the full optimisation range so hyperopt can pick
        # any period without recomputing indicators per trial.
        for period in self.ema_fast.range:
            dataframe[f"ema_fast_{period}"] = ta.EMA(dataframe, timeperiod=period)
        for period in self.ema_slow.range:
            dataframe[f"ema_slow_{period}"] = ta.EMA(dataframe, timeperiod=period)

        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        # --- Trend strength ---
        dataframe["adx"] = ta.ADX(dataframe)

        # --- Momentum ---
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # --- Volatility (Bollinger Bands via qtpylib) ---
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["bb_upper"] = bollinger["upper"]

        # --- Volume baseline ---
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        return dataframe

    # ------------------------------------------------------------------ #
    # Entry logic                                                        #
    # ------------------------------------------------------------------ #
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = dataframe[f"ema_fast_{self.ema_fast.value}"]
        ema_slow = dataframe[f"ema_slow_{self.ema_slow.value}"]

        # ---- LONG ----
        long_conditions = [
            # Bullish structure: fast EMA above slow EMA, price above long trend.
            ema_fast > ema_slow,
            dataframe["close"] > dataframe["ema200"],
            # Trend has strength, not chop.
            dataframe["adx"] > self.adx_threshold.value,
            # Momentum turning back up from a pullback dip.
            qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value),
            # Confirm we are buying a dip, not chasing: price near/below mid band.
            dataframe["close"] < dataframe["bb_mid"],
            # Liquidity filter.
            dataframe["volume"] > dataframe["volume_mean"] * self.volume_factor.value,
            dataframe["volume"] > 0,
        ]
        if self.require_macd.value:
            long_conditions.append(dataframe["macd"] > dataframe["macdsignal"])

        dataframe.loc[
            reduce(lambda a, b: a & b, long_conditions), ["enter_long", "enter_tag"]
        ] = (1, "momentum_pullback_long")

        # ---- SHORT (only when enabled on futures) ----
        if self.can_short:
            short_conditions = [
                ema_fast < ema_slow,
                dataframe["close"] < dataframe["ema200"],
                dataframe["adx"] > self.adx_threshold.value,
                qtpylib.crossed_below(dataframe["rsi"], 100 - self.buy_rsi.value),
                dataframe["close"] > dataframe["bb_mid"],
                dataframe["volume"]
                > dataframe["volume_mean"] * self.volume_factor.value,
                dataframe["volume"] > 0,
            ]
            if self.require_macd.value:
                short_conditions.append(dataframe["macd"] < dataframe["macdsignal"])

            dataframe.loc[
                reduce(lambda a, b: a & b, short_conditions),
                ["enter_short", "enter_tag"],
            ] = (1, "momentum_pullback_short")

        return dataframe

    # ------------------------------------------------------------------ #
    # Exit logic                                                         #
    # ------------------------------------------------------------------ #
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = dataframe[f"ema_fast_{self.ema_fast.value}"]

        # ---- Exit LONG ----
        long_exits = [
            dataframe["volume"] > 0,
            (
                # Momentum exhausted: RSI overbought crossing down.
                qtpylib.crossed_below(dataframe["rsi"], self.sell_rsi.value)
                # or MACD rolls over.
                | qtpylib.crossed_below(dataframe["macd"], dataframe["macdsignal"])
            ),
        ]
        if self.use_ema_exit.value:
            # Short-term trend break as an additional exit trigger.
            long_exits.append(
                qtpylib.crossed_below(dataframe["close"], ema_fast)
                | qtpylib.crossed_below(dataframe["rsi"], self.sell_rsi.value)
                | qtpylib.crossed_below(dataframe["macd"], dataframe["macdsignal"])
            )

        dataframe.loc[
            reduce(lambda a, b: a & b, long_exits), ["exit_long", "exit_tag"]
        ] = (1, "momentum_exhausted_long")

        # ---- Exit SHORT ----
        if self.can_short:
            short_exits = [
                dataframe["volume"] > 0,
                (
                    qtpylib.crossed_above(dataframe["rsi"], 100 - self.sell_rsi.value)
                    | qtpylib.crossed_above(dataframe["macd"], dataframe["macdsignal"])
                ),
            ]
            if self.use_ema_exit.value:
                short_exits.append(
                    qtpylib.crossed_above(dataframe["close"], ema_fast)
                    | qtpylib.crossed_above(dataframe["macd"], dataframe["macdsignal"])
                )

            dataframe.loc[
                reduce(lambda a, b: a & b, short_exits), ["exit_short", "exit_tag"]
            ] = (1, "momentum_exhausted_short")

        return dataframe

    # ------------------------------------------------------------------ #
    # Risk management: volatility-scaled custom stoploss                 #
    # ------------------------------------------------------------------ #
    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        """
        Tighten the stop once a trade is meaningfully in profit.

        Returns a stoploss relative to *current_rate* (negative value). The
        engine always keeps the tighter of this and the static ``stoploss``.
        """
        # Give the trade room to breathe until it clears the first ROI step.
        if current_profit < 0.02:
            return self.stoploss

        # Once above +2%, ratchet the stop up toward break-even and beyond.
        # e.g. at +5% profit, protect roughly +2.5%.
        return max(-0.10, -(current_profit * 0.5))
