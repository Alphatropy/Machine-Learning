# Guía de conexión a Binance — AlphatropyMomentum

Guía paso a paso para conectar la estrategia `AlphatropyMomentum` a Binance
con [Freqtrade](https://github.com/freqtrade/freqtrade).

> **Concepto clave:** la conexión al exchange **no** está en el código de la
> estrategia (`.py`), está en el `config.json`. La misma estrategia corre en
> modo papel o real solo cambiando ese archivo.
>
> ```
> Estrategia (.py)  ─►  config.json (API keys)  ─►  freqtrade  ─►  Binance API
>    [la lógica]         [la conexión]              [el motor]     [el exchange]
> ```

---

## Paso 1 — Instalar freqtrade

**Opción Docker (recomendada):**
```bash
git clone https://github.com/freqtrade/freqtrade.git
cd freqtrade
docker compose pull
```

**Opción nativa (pip + TA-Lib):**
```bash
git clone https://github.com/freqtrade/freqtrade.git
cd freqtrade
./setup.sh -i
```

## Paso 2 — Crear las API Keys en Binance

1. Binance → **Account → API Management → Create API**.
2. Permisos — activá **solo**:
   - ✅ Enable Reading
   - ✅ Enable Spot & Margin Trading
   - ❌ **Enable Withdrawals** → **NUNCA**. El bot no lo necesita; es tu principal protección.
3. **Restringí por IP** (Restrict access to trusted IPs) con la IP de tu servidor.
4. Copiá la **API Key** y el **Secret** (el secret se muestra una sola vez).

> ⚠️ Región: `binance.com` (global) y `binance.us` (EE.UU.) son distintos.
> En el config el `name` cambia (`binance` vs `binanceus`).

## Paso 3 — Configurar las keys

```bash
cp user_data/config.example.json user_data/config.json
```

Editá la sección `exchange` en `user_data/config.json`:

```json
"exchange": {
    "name": "binance",
    "key": "TU_API_KEY",
    "secret": "TU_SECRET",
    "pair_whitelist": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
},
"stake_currency": "USDT",
"dry_run": true
```

> 🔒 `config.json` con tus keys reales queda **fuera de git** (ya está en
> `.gitignore`). Nunca lo subas al repo.

## Paso 4 — Probar la conexión (sin dinero real)

```bash
# Verifica que las keys y los pares funcionan
freqtrade test-pairlist --config user_data/config.json

# Arranca en modo PAPEL (datos reales de Binance, dinero ficticio)
freqtrade trade --config user_data/config.json --strategy AlphatropyMomentum
```

Si arranca y analiza velas sin errores de autenticación → conexión OK.
(O usá el script incluido: `./start.sh`.)

## Paso 5 — Pasar a real (solo cuando estés seguro)

Orden seguro: **backtest → dry-run varias semanas → real con poco dinero**.

En `config.json`:
```json
"dry_run": false,
"stake_amount": 20
```

Empezá con un `stake_amount` chico (ej. 20 USDT por operación).

---

⚠️ **No es asesoría financiera.** Probá con backtest y dry-run antes de
arriesgar fondos reales. El rendimiento pasado no garantiza resultados futuros.
