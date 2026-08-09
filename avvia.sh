#!/usr/bin/env bash
# ============================================================================
#  avvia.sh — avvia OsmoTetra da riga di comando (senza interfaccia grafica)
# ============================================================================
#  Uso:
#     ./avvia.sh [FREQUENZA_MHz] [DEVICE_ARGS]
#  Esempi:
#     ./avvia.sh 390.5                      # chiavetta USB automatica
#     ./avvia.sh 390.5 rtl=0                # prima chiavetta
#     ./avvia.sh 390.5 rtl_tcp=192.168.64.1:1234   # chiavetta via rete (VM)
#
#  Avvia in sottofondo il flowgraph e receiver1udp, poi apre telive in QUESTO
#  terminale. Quando esci da telive (o premi Ctrl+C) ferma tutto.
#
#  Variabili utili:
#     OSMOTETRA_HOME   dove sono i sorgenti compilati (default: ~/telive2)
#     OSMOTETRA_GAIN   guadagno RF in dB (default: 38)
#     OSMOTETRA_PPM    correzione in ppm (default: 0)
#     OSMOTETRA_PYTHON interprete con GNU Radio (default: python3)
# ============================================================================
set -euo pipefail

FREQ_MHZ="${1:-390.5}"
DEVICE_ARGS="${2:-}"
GAIN="${OSMOTETRA_GAIN:-38}"
PPM="${OSMOTETRA_PPM:-0}"
GR_PYTHON="${OSMOTETRA_PYTHON:-python3}"

HERE="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="${OSMOTETRA_HOME:-$HOME/telive2}"
OSMO_SRC="$HOME_DIR/osmo-tetra-sq5bpf-2/src"
TELIVE_DIR="$HOME_DIR/telive-2"
FLOWGRAPH="$HERE/osmotetra_rx.py"

LOG_DIR="$HOME_DIR/logs"
mkdir -p "$LOG_DIR"

# --- controlli preliminari --------------------------------------------------
for f in "$FLOWGRAPH" "$OSMO_SRC/receiver1udp" "$OSMO_SRC/tetra-rx" "$TELIVE_DIR/telive"; do
  if [ ! -e "$f" ]; then
    echo "[ERRORE] Manca: $f"
    echo "         Esegui prima l'installazione:  ./install.sh"
    exit 1
  fi
done

FREQ_HZ="$(awk "BEGIN{printf \"%.0f\", $FREQ_MHZ*1000000}")"

RX_PID=""
DEMOD_PID=""
cleanup() {
  echo
  echo "[avvia] fermo la catena…"
  [ -n "$DEMOD_PID" ] && kill -TERM -- "-$DEMOD_PID" 2>/dev/null || true
  [ -n "$RX_PID" ]    && kill -TERM -- "-$RX_PID"    2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 1) flowgraph headless (in sottofondo) ----------------------------------
echo "[avvia] flowgraph: canale ${FREQ_MHZ} MHz, guadagno ${GAIN} dB, dispositivo '${DEVICE_ARGS:-auto}'"
setsid "$GR_PYTHON" "$FLOWGRAPH" \
  --freq "$FREQ_HZ" --gain "$GAIN" --ppm "$PPM" --device-args "$DEVICE_ARGS" \
  >"$LOG_DIR/flowgraph.log" 2>&1 &
RX_PID=$!

# --- 2) aspetta l'SDR: XMLRPC pronto, o il flowgraph è morto (niente radio) --
echo -n "[avvia] attendo il ricevitore SDR"
for _ in $(seq 1 80); do
  if ! kill -0 "$RX_PID" 2>/dev/null; then
    echo " — non partito."
    echo "----------------------------------------------------------------"
    cat "$LOG_DIR/flowgraph.log"
    echo "----------------------------------------------------------------"
    echo "[ERRORE] Il flowgraph si è chiuso: di solito manca la radio."
    exit 1
  fi
  if (exec 3<>/dev/tcp/127.0.0.1/42000) 2>/dev/null; then exec 3>&- 3<&-; echo " ok."; break; fi
  echo -n "."
  sleep 0.25
done

# --- 3) receiver1udp (socat | simdemod3_telive.py | tetra-rx) ---------------
echo "[avvia] ricevitore: socat | simdemod3_telive.py | tetra-rx  →  telive"
setsid bash -c 'cd "$1" && exec ./receiver1udp 1' _ "$OSMO_SRC" \
  >"$LOG_DIR/receiver.log" 2>&1 &
DEMOD_PID=$!
sleep 1

# --- 4) telive in QUESTO terminale ------------------------------------------
export PATH="$PATH:/tetra/bin"
export TETRA_OUTDIR=/tetra/in
export TETRA_LOGFILE=/tetra/log/telive.log
export TETRA_PORT=7379
export TETRA_GR_XMLRPC_URL="http://127.0.0.1:42000/"
export TETRA_RX_BASEBAND_AUTOCORRECT=0
export TETRA_AUTO_TUNE=0

echo "[avvia] apro telive (premi ? per l'aiuto, q per uscire)"
echo "        log: $LOG_DIR/flowgraph.log  e  $LOG_DIR/receiver.log"
sleep 1
( cd "$TELIVE_DIR" && ./telive )
