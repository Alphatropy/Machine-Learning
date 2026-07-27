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

## Notes

- **Timeframe:** `1h` by default; `startup_candle_count = 200` warms up the
  slowest indicators (EMA200 / MACD / ADX).
- **Repainting:** `process_only_new_candles = True` and closed-candle
  crossovers avoid intra-candle repainting.
- ⚠️ **Not financial advice.** Backtest and dry-run before risking real funds.
  Past performance does not guarantee future results.
