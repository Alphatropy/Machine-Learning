# Freqtrade — AlphatropyMomentum Strategy

A custom [Freqtrade](https://github.com/freqtrade/freqtrade) trading strategy
(`user_data/strategies/AlphatropyMomentum.py`) built on the **IStrategy V3**
interface.

## Idea

Trend-following with a **momentum-pullback** entry:

1. **Regime filter** — only trade with the dominant trend
   (`EMA_fast > EMA_slow`, price above `EMA200`, `ADX` above threshold).
2. **Pullback entry** — buy the dip *inside* the uptrend: RSI crossing back up
   from oversold, price below the Bollinger mid-band, MACD confirming, volume
   above its 20-period average.
3. **Exit** — momentum exhaustion (RSI overbought crossing down / MACD
   roll-over) or a short-term trend break, backed by a **trailing stop**, an
   **ROI table**, and a **volatility-scaled custom stoploss**.

Optional shorting (`can_short`) mirrors the logic for futures configs.

## Hyperoptable parameters

Every meaningful threshold is exposed via `IntParameter` / `DecimalParameter` /
`BooleanParameter`, so behaviour can be tuned rather than hard-coded:

| Space  | Parameters |
|--------|------------|
| `buy`  | `ema_fast`, `ema_slow`, `adx_threshold`, `buy_rsi`, `volume_factor`, `require_macd` |
| `sell` | `sell_rsi`, `use_ema_exit` |

## Usage

Assuming Freqtrade is installed and this repo's `freqtrade/` folder is used as
the `user_data` parent (or copy the strategy into your own `user_data/strategies/`):

```bash
# 1. Download historical data
freqtrade download-data --exchange binance \
    --pairs BTC/USDT ETH/USDT --timeframes 1h --days 365

# 2. Backtest
freqtrade backtesting --strategy AlphatropyMomentum \
    --timeframe 1h --timerange 20240101-

# 3. Hyperopt (optimise entry/exit/ROI/stoploss)
freqtrade hyperopt --strategy AlphatropyMomentum \
    --hyperopt-loss SharpeHyperOptLoss \
    --spaces buy sell roi stoploss --epochs 200

# 4. Dry-run (paper trading)
freqtrade trade --strategy AlphatropyMomentum --dry-run
```

## Futures / leverage

The strategy also supports **futures with leverage and short trades**:

- Use `user_data/config.futures.example.json` (`trading_mode: futures`,
  `margin_mode: isolated`, `:USDT` perpetual pairs).
- `can_short` is **auto-enabled** when the config runs in futures mode, so the
  mirrored short logic activates without editing the strategy.
- The `leverage()` callback returns a conservative default (`leverage_num`,
  3x) capped by the exchange maximum per pair. Adjust `leverage_num` to taste.

```bash
# Backtest on futures (download futures data first with --trading-mode futures)
freqtrade download-data --exchange binance --trading-mode futures \
    --pairs BTC/USDT:USDT ETH/USDT:USDT --timeframes 1h --days 365
freqtrade backtesting --strategy AlphatropyMomentum \
    --config user_data/config.futures.example.json --timeframe 1h
```

> ⚠️ **Do not** use leverage > 1 with a strategy that hasn't first shown
> positive results in live spot trading. Start dry-run → spot → futures.

## Notes

- **Timeframe:** `1h` by default; `startup_candle_count = 200` warms up the
  slowest indicators (EMA200 / MACD / ADX).
- **Repainting:** `process_only_new_candles = True` and closed-candle
  crossovers avoid intra-candle repainting.
- ⚠️ **Not financial advice.** Backtest and dry-run before risking real funds.
  Past performance does not guarantee future results.
