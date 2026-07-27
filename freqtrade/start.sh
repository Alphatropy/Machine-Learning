#!/usr/bin/env bash
#
# start.sh — Arranca la estrategia AlphatropyMomentum en freqtrade.
#
# Uso:
#   ./start.sh              # modo papel (dry-run) — seguro, sin dinero real
#   ./start.sh backtest     # backtest sobre datos históricos ya descargados
#   ./start.sh live         # trading REAL (pide confirmación explícita)
#
# Requiere freqtrade instalado y user_data/config.json configurado
# (copiá user_data/config.example.json y poné tus API keys). Ver SETUP.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/user_data/config.json"
STRATEGY="AlphatropyMomentum"
STRATEGY_PATH="${SCRIPT_DIR}/user_data/strategies"
MODE="${1:-dryrun}"

# --- Comprobaciones previas -------------------------------------------------
if ! command -v freqtrade >/dev/null 2>&1; then
    echo "❌ freqtrade no está instalado o no está en el PATH."
    echo "   Instalación: https://www.freqtrade.io/en/stable/installation/ (o ver SETUP.md)"
    exit 1
fi

if [[ ! -f "${CONFIG}" ]]; then
    echo "❌ No se encontró ${CONFIG}"
    echo "   Copiá el ejemplo y agregá tus API keys:"
    echo "     cp ${SCRIPT_DIR}/user_data/config.example.json ${CONFIG}"
    exit 1
fi

COMMON=(--config "${CONFIG}" --strategy "${STRATEGY}" --strategy-path "${STRATEGY_PATH}")

# --- Modos ------------------------------------------------------------------
case "${MODE}" in
    dryrun|dry-run|dry)
        echo "🧪 Modo PAPEL (dry-run) — datos reales, dinero ficticio."
        exec freqtrade trade "${COMMON[@]}" --dry-run
        ;;
    backtest|backtesting)
        echo "📈 Backtest sobre datos históricos descargados."
        exec freqtrade backtesting "${COMMON[@]}"
        ;;
    live|real)
        echo "🔴 ATENCIÓN: vas a operar con DINERO REAL."
        read -r -p "   Escribí 'SI' para continuar: " ans
        if [[ "${ans}" != "SI" ]]; then
            echo "   Cancelado."
            exit 0
        fi
        exec freqtrade trade "${COMMON[@]}"
        ;;
    *)
        echo "Uso: ./start.sh [dryrun|backtest|live]"
        exit 1
        ;;
esac
