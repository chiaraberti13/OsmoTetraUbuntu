#!/bin/bash
# ============================================================================
#  avvia_macos.command — avvia OsmoTetra su macOS (doppio clic o da Terminale)
# ============================================================================
#  Uso:
#     doppio clic sul file, oppure:
#     ./avvia_macos.command [FREQUENZA_MHz] [DEVICE_ARGS]
#  Esempi:
#     ./avvia_macos.command 390.5           # chiavetta USB automatica
#     ./avvia_macos.command 390.5 rtl=0     # prima chiavetta
#
#  Apre telive in questa finestra del Terminale; il flowgraph e il ricevitore
#  girano in sottofondo (log in ~/telive2/logs/). Chiudi telive con 'q' o
#  Ctrl+C: si ferma tutto.
# ============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
[ -f "$HERE/osmotetra.env" ] && source "$HERE/osmotetra.env"

FREQ_MHZ="${1:-390.5}"
DEVICE_ARGS="${2:-}"
GAIN="${OSMOTETRA_GAIN:-38}"
PPM="${OSMOTETRA_PPM:-0}"
GR_PYTHON="${OSMOTETRA_PYTHON:-python3}"
HOME_DIR="${OSMOTETRA_HOME:-$HOME/telive2}"
OSMO_SRC="$HOME_DIR/osmo-tetra-sq5bpf-2/src"
TELIVE_DIR="$HOME_DIR/telive-2"
FLOWGRAPH="$HOME_DIR/osmotetra_rx.py"
TETRA_ROOT="${TETRA_ROOT:-$HOME/tetra}"
BIN_DIR="${OSMOTETRA_BIN:-$HOME_DIR/bin}"
LOG_DIR="$HOME_DIR/logs"; mkdir -p "$LOG_DIR"

# ingrandisci la finestra del Terminale: telive vuole 203x60
# (\033 = ESC in ottale: funziona anche col printf del bash 3.2 di macOS)
printf '\033[8;60;203t'

for f in "$FLOWGRAPH" "$OSMO_SRC/receiver1udp" "$OSMO_SRC/tetra-rx" "$TELIVE_DIR/telive"; do
  if [ ! -e "$f" ]; then
    echo "[ERRORE] manca: $f"
    echo "         esegui prima:  ./install_macos.sh"
    echo "Premi Invio per chiudere."; read -r _; exit 1
  fi
done

FREQ_HZ="$(awk "BEGIN{printf \"%.0f\", $FREQ_MHZ*1000000}")"

# python3 usato da receiver1udp/simdemod3 deve avere GNU Radio: lo forziamo
# con un piccolo shim in PATH che punta all'interprete di MacPorts.
SHIM="$LOG_DIR/pyshim"; mkdir -p "$SHIM"
ln -sf "$GR_PYTHON" "$SHIM/python3"

RX_PID=""; DEMOD_PID=""
cleanup() {
  echo; echo "[avvia] fermo la catena…"
  [ -n "$DEMOD_PID" ] && kill "$DEMOD_PID" 2>/dev/null || true
  [ -n "$RX_PID" ] && kill "$RX_PID" 2>/dev/null || true
  # macOS non ha setsid: chiudo i figli della pipeline per nome (best-effort)
  pkill -x socat 2>/dev/null || true
  pkill -f simdemod3_telive.py 2>/dev/null || true
  pkill -x tetra-rx 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 1) flowgraph headless --------------------------------------------------
echo "[avvia] flowgraph: canale ${FREQ_MHZ} MHz, guadagno ${GAIN} dB, dispositivo '${DEVICE_ARGS:-auto}'"
"$GR_PYTHON" "$FLOWGRAPH" \
  --freq "$FREQ_HZ" --gain "$GAIN" --ppm "$PPM" --device-args "$DEVICE_ARGS" \
  >"$LOG_DIR/flowgraph.log" 2>&1 &
RX_PID=$!

# --- 2) aspetta l'SDR: XMLRPC pronto, o il flowgraph è morto ----------------
echo -n "[avvia] attendo il ricevitore SDR"
ok=0
for _ in $(seq 1 80); do
  if ! kill -0 "$RX_PID" 2>/dev/null; then
    echo " — non partito."
    echo "----------------------------------------------------------------"
    cat "$LOG_DIR/flowgraph.log"
    echo "----------------------------------------------------------------"
    echo "[ERRORE] il flowgraph si è chiuso: di solito manca la radio, oppure"
    echo "         il device-args è sbagliato. Prova ./avvia_macos.command 390.5 rtl=0"
    echo "Premi Invio per chiudere."; read -r _; exit 1
  fi
  if nc -z 127.0.0.1 42000 >/dev/null 2>&1; then ok=1; echo " ok."; break; fi
  echo -n "."; sleep 0.25
done
[ "$ok" = 1 ] || { echo " timeout."; exit 1; }

# --- 3) receiver1udp (socat | simdemod3_telive.py | tetra-rx) ---------------
echo "[avvia] ricevitore: socat | simdemod3_telive.py | tetra-rx → telive"
( cd "$OSMO_SRC" && PATH="$SHIM:$PATH" ./receiver1udp 1 ) >"$LOG_DIR/receiver.log" 2>&1 &
DEMOD_PID=$!
sleep 1

# --- 4) telive in questa finestra ------------------------------------------
export PATH="$BIN_DIR:$PATH"
export TETRA_OUTDIR="$TETRA_ROOT/in"
export TETRA_LOGFILE="$TETRA_ROOT/log/telive.log"
export TETRA_PORT=7379
export TETRA_GR_XMLRPC_URL="http://127.0.0.1:42000/"
export TETRA_RX_BASEBAND_AUTOCORRECT=0
export TETRA_AUTO_TUNE=0

echo "[avvia] apro telive (? = aiuto, q = esci).  Log: $LOG_DIR/"
sleep 1
( cd "$TELIVE_DIR" && ./telive )
