#!/usr/bin/env bash
# ============================================================================
#  install.sh — installazione automatica di OsmoTetra
# ============================================================================
#  Catena completa di SQ5BPF: osmo-tetra-sq5bpf-2 + codec vocale ETSI +
#  telive-2, con decifratura vocale a CHIAVE NOTA. In più: il lanciatore
#  grafico di OsmoTetra e la voce nel menu applicazioni.
#
#  Testato su Ubuntu 24.04 (x86) e 25.10 (ARM64/x86).
#
#  Uso:   ./install.sh          (come UTENTE NORMALE, non con sudo)
#         chiede la password sudo solo per apt e per creare /tetra.
#
#  DISCLAIMER: la decifratura funziona solo con chiave GIÀ NOTA; questi
#  strumenti non craccano il TETRA. Usalo solo dove consentito dalla legge.
# ============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Impostazioni
# ---------------------------------------------------------------------------
OSMO_REPO="https://github.com/sq5bpf/osmo-tetra-sq5bpf-2.git"
TELIVE_REPO="https://github.com/sq5bpf/telive-2.git"

OSMOTETRA_HOME="${OSMOTETRA_HOME:-$HOME/telive2}"
OSMO_DIR="$OSMOTETRA_HOME/osmo-tetra-sq5bpf-2"
TELIVE_DIR="$OSMOTETRA_HOME/telive-2"

HERE="$(cd "$(dirname "$0")" && pwd)"
NANOHTTP_PATCH="$HERE/patches/telive2-nanohttp-to-socket.diff"

ETSI_URL="http://www.etsi.org/deliver/etsi_en/300300_300399/30039502/01.03.01_60/en_30039502v010301p0.zip"
ETSI_MD5="a8115fe68ef8f8cc466f4192572a1e3e"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

JOBS="$(nproc)"
COMPAT_CFLAGS=""

LOG_DIR="$OSMOTETRA_HOME/logs"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_DIR/install.log") 2>&1
echo "==== install.sh — $(date '+%Y-%m-%d %H:%M:%S') ===="

step() { echo; echo "============================================================"; echo " $*"; echo "============================================================"; }
info() { echo "  -> $*"; }

# ---------------------------------------------------------------------------
# Compatibilità compilatore (GCC 13/14/15): riporta a warning i costrutti C
# "vecchi" di SQ5BPF che GCC recente tratta come errore. Tiene solo i flag che
# il gcc locale accetta.
# ---------------------------------------------------------------------------
detect_compat_cflags() {
  local cc="${CC:-cc}" out="" f tmp
  tmp="$(mktemp -d)"
  printf 'int main(void){return 0;}\n' > "$tmp/probe.c"
  for f in -std=gnu17 \
           -Wno-error=implicit-int -Wno-error=implicit-function-declaration \
           -Wno-error=int-conversion -Wno-error=incompatible-pointer-types \
           -Wno-error=return-mismatch -Wno-error=declaration-missing-parameter-type \
           -Wno-error=old-style-definition; do
    "$cc" "$f" -c "$tmp/probe.c" -o "$tmp/probe.o" >/dev/null 2>&1 && out="$out $f"
  done
  rm -rf "$tmp"
  echo "${out# }"
}

inject_cflags() {
  local mk="$1"
  [ -f "$mk" ] || return 0
  [ -n "$COMPAT_CFLAGS" ] || return 0
  grep -q -- '-std=gnu17' "$mk" && return 0
  sed -i "0,/^CFLAGS[[:space:]]*=/s//& ${COMPAT_CFLAGS} /" "$mk"
  info "Compatibilità compilatore applicata a $(basename "$(dirname "$mk")")/$(basename "$mk")"
}

# telive_receiver.h usa time_t senza includere <time.h>: sulle glibc recenti
# la build fallisce con "unknown type name 'time_t'".
patch_telive_includes() {
  local h="$TELIVE_DIR/telive_receiver.h"
  [ -f "$h" ] || return 0
  grep -q '#include <time.h>' "$h" && return 0
  if grep -q '#include <stdint.h>' "$h"; then
    sed -i 's|#include <stdint.h>|#include <stdint.h>\n#include <time.h>|' "$h"
  else
    sed -i '1i #include <time.h>' "$h"
  fi
  info "Aggiunto #include <time.h> a telive_receiver.h"
}

# libxml2 2.14 (Ubuntu 25.10) ha rimosso il modulo nanohttp che telive-2 usa
# per l'XMLRPC verso il flowgraph: senza, telive non compila. Se nanohttp non
# c'è, applichiamo la patch che lo sostituisce con una POST via socket POSIX.
maybe_patch_nanohttp() {
  local tmp
  tmp="$(mktemp -d)"
  cat > "$tmp/p.c" <<'EOF'
#include <libxml/nanohttp.h>
int main(void){ xmlNanoHTTPInit(); return 0; }
EOF
  # SC2046 volontario: xml2-config stampa più flag che DEVONO essere separati.
  # shellcheck disable=SC2046
  if cc "$tmp/p.c" $(xml2-config --cflags --libs 2>/dev/null) -o "$tmp/p" >/dev/null 2>&1; then
    info "libxml2 con nanohttp: nessuna patch necessaria."
    rm -rf "$tmp"; return 0
  fi
  rm -rf "$tmp"
  info "libxml2 senza nanohttp (>= 2.14): applico la patch socket a telive-2."
  if [ ! -f "$NANOHTTP_PATCH" ]; then
    echo "ATTENZIONE: patch nanohttp non trovata ($NANOHTTP_PATCH): la build di telive potrebbe fallire."
    return 0
  fi
  # idempotente: se già applicata (patch inversa applicabile), non rifare.
  if patch -p1 -R --dry-run -d "$TELIVE_DIR" < "$NANOHTTP_PATCH" >/dev/null 2>&1; then
    info "Patch nanohttp già applicata."
  elif patch -p1 -N -d "$TELIVE_DIR" < "$NANOHTTP_PATCH"; then
    info "Patch nanohttp applicata."
  else
    echo "ERRORE: la patch nanohttp non si applica pulita. Vedi patches/README.md."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# 0) Controlli
# ---------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
  echo "ERRORE: non lanciarmi con sudo/root. Eseguimi come utente normale:  ./install.sh"
  exit 1
fi
step "0) Sistema"
if ! grep -qiE 'ubuntu|debian' /etc/os-release 2>/dev/null; then
  echo "ATTENZIONE: distribuzione non Ubuntu/Debian: proseguo ma apt potrebbe non funzionare."
fi
info "Utente: $(id -un)   Core: $JOBS   Arch: $(uname -m)   Home OsmoTetra: $OSMOTETRA_HOME"

# ---------------------------------------------------------------------------
# 1) Dipendenze
# ---------------------------------------------------------------------------
step "1) Dipendenze (apt)"
sudo apt-get update
sudo apt-get install -y \
  build-essential gcc make git pkg-config patch unzip wget ca-certificates \
  libosmocore-dev libncurses-dev libxml2-dev \
  librtlsdr-dev rtl-sdr libusb-1.0-0-dev \
  socat alsa-utils sox vorbis-tools \
  gnuradio gr-osmosdr python3-pyqt5 \
  fonts-noto-color-emoji
info "Dipendenze installate."
COMPAT_CFLAGS="$(detect_compat_cflags)"
[ -n "$COMPAT_CFLAGS" ] && info "Flag compat compilatore: $COMPAT_CFLAGS"

# ---------------------------------------------------------------------------
# 2) Sorgenti
# ---------------------------------------------------------------------------
step "2) Sorgenti (osmo-tetra-sq5bpf-2 e telive-2)"
clone_or_update() {
  local url="$1" dir="$2"
  if [ -d "$dir/.git" ]; then info "Aggiorno $dir"; git -C "$dir" pull --ff-only || true
  else info "Clono $url"; git clone --depth 1 "$url" "$dir"; fi
}
clone_or_update "$OSMO_REPO" "$OSMO_DIR"
clone_or_update "$TELIVE_REPO" "$TELIVE_DIR"

# ---------------------------------------------------------------------------
# 3) osmo receiver (tetra-rx)
# ---------------------------------------------------------------------------
step "3) Compilo l'osmo receiver (tetra-rx)"
inject_cflags "$OSMO_DIR/src/Makefile"
make -C "$OSMO_DIR/src" -j"$JOBS"
[ -x "$OSMO_DIR/src/tetra-rx" ] && info "OK: tetra-rx" || { echo "ERRORE: tetra-rx non compilato"; exit 1; }

# ---------------------------------------------------------------------------
# 4) Codec vocale ETSI (cdecoder / sdecoder)
# ---------------------------------------------------------------------------
step "4) Codec vocale ETSI"
PATCHDIR="$OSMO_DIR/etsi_codec-patches"
ZIP="$PATCHDIR/etsi_tetra_codec.zip"
check_md5() { [ "$(md5sum "$1" | awk '{print $1}')" = "$ETSI_MD5" ]; }
got=0
info "Scarico il codec da ETSI…"
if wget -q -U "$UA" -O "$ZIP" "$ETSI_URL" && check_md5 "$ZIP"; then got=1
else
  info "ETSI non raggiungibile: provo il mirror archive.org…"
  wget -q -U "$UA" -O "$ZIP" "https://web.archive.org/web/2id_/$ETSI_URL" && check_md5 "$ZIP" && got=1 || true
fi
if [ "$got" -eq 1 ]; then
  info "Zip ETSI verificato."
  sed -i 's/\[ ! -f $LOCAL_FILE \]/false/g; s/print "MD5sum/echo "MD5sum/g' "$PATCHDIR/download_and_patch.sh"
else
  info "Pre-download non riuscito: lo script scaricherà da solo."
  sed -i 's/\[ ! -f $LOCAL_FILE \]/true/g; s/wget -O/wget -U "Mozilla\/5.0" -O/g; s/print "MD5sum/echo "MD5sum/g' "$PATCHDIR/download_and_patch.sh"
fi
( cd "$PATCHDIR" && sh ./download_and_patch.sh )
inject_cflags "$OSMO_DIR/codec/c-code/Makefile"
make -C "$OSMO_DIR/codec/c-code" -j"$JOBS"
[ -x "$OSMO_DIR/codec/c-code/cdecoder" ] && [ -x "$OSMO_DIR/codec/c-code/sdecoder" ] \
  && info "OK: cdecoder e sdecoder" || { echo "ERRORE: codec non compilato"; exit 1; }

# ---------------------------------------------------------------------------
# 5) telive
# ---------------------------------------------------------------------------
step "5) Compilo telive"
inject_cflags "$TELIVE_DIR/Makefile"
patch_telive_includes
maybe_patch_nanohttp
make -C "$TELIVE_DIR" -j"$JOBS"
[ -x "$TELIVE_DIR/telive" ] && info "OK: telive" || { echo "ERRORE: telive non compilato"; exit 1; }

# ---------------------------------------------------------------------------
# 6) /tetra e binari nel PATH
# ---------------------------------------------------------------------------
step "6) /tetra e binari"
sudo mkdir -p /tetra
sudo chown "$(id -un):$(id -gn)" /tetra
mkdir -p /tetra/in /tetra/out /tetra/log /tetra/tmp /tetra/bin
touch /tetra/log/telive.log
cp -v "$TELIVE_DIR"/bin/* /tetra/bin/ 2>/dev/null || true
cp -v "$OSMO_DIR/codec/c-code/cdecoder" "$OSMO_DIR/codec/c-code/sdecoder" /tetra/bin/
cp -v "$TELIVE_DIR/telive" /tetra/bin/
chmod +x /tetra/bin/* || true
if ! grep -q '/tetra/bin' "$HOME/.bashrc" 2>/dev/null; then
  printf '\n# OsmoTetra: decoder vocali TETRA\nexport PATH="$PATH:/tetra/bin"\n' >> "$HOME/.bashrc"
  info "Aggiunto /tetra/bin a ~/.bashrc (riapri il terminale o: source ~/.bashrc)"
fi

# ---------------------------------------------------------------------------
# 7) Lanciatore OsmoTetra + voce nel menu
# ---------------------------------------------------------------------------
step "7) Lanciatore grafico e voce di menu"
install -m 0755 "$HERE/osmotetra_rx.py"       "$OSMOTETRA_HOME/osmotetra_rx.py"
install -m 0755 "$HERE/osmotetra_launcher.py" "$OSMOTETRA_HOME/osmotetra_launcher.py"
install -m 0644 "$HERE/osmotetra_i18n.py"     "$OSMOTETRA_HOME/osmotetra_i18n.py"
install -m 0755 "$HERE/avvia.sh"              "$OSMOTETRA_HOME/avvia.sh"
install -m 0755 "$HERE/osmotetra"             "$OSMOTETRA_HOME/osmotetra"

# comando 'osmotetra': un wrapper che imposta OSMOTETRA_HOME ed esegue il
# dispatcher (pannello / avvia / spettro / monitor / chiavi / stop).
BIN="$HOME/.local/bin"; mkdir -p "$BIN"
cat > "$BIN/osmotetra" <<EOF
#!/usr/bin/env bash
export OSMOTETRA_HOME="$OSMOTETRA_HOME"
exec "$OSMOTETRA_HOME/osmotetra" "\$@"
EOF
chmod +x "$BIN/osmotetra"

APPS="$HOME/.local/share/applications"; mkdir -p "$APPS"
cat > "$APPS/osmotetra.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OsmoTetra
Comment=Ricevitore TETRA (telive) — lanciatore
Exec=$BIN/osmotetra
Terminal=false
Categories=HamRadio;Network;Utility;
EOF
update-desktop-database "$APPS" >/dev/null 2>&1 || true
info "Lanciatore: comando 'osmotetra' e voce «OsmoTetra» nel menu."

# ---------------------------------------------------------------------------
# Fine
# ---------------------------------------------------------------------------
cat <<EOF

============================================================
 Installazione OsmoTetra completata!
============================================================

Tutto è in:  $OSMOTETRA_HOME
   osmo-tetra-sq5bpf-2/   telive-2/   logs/   + lanciatore

COME USARLO — un solo comando, 'osmotetra':
   osmotetra                apre il PANNELLO (menu «OsmoTetra» o questo comando)
   osmotetra avvia 390.5    avvia tutto da terminale (spettro + telive)
   osmotetra spettro 390.5  apre solo la finestra dello spettro
   osmotetra monitor 390.5  avvia solo telive (senza spettro)
   osmotetra chiavi         inserisci le chiavi di decifratura (interfaccia)
   osmotetra stop           ferma tutto        osmotetra aiuto   la guida

Se 'osmotetra' non viene trovato subito, riapri il terminale
(oppure:  source ~/.bashrc) — serve per avere ~/.local/bin nel PATH.

Chiavetta in una macchina virtuale? Lasciala al sistema ospitante con
   rtl_tcp -a 0.0.0.0 -p 1234
e nel campo Dispositivo scrivi:  rtl_tcp=INDIRIZZO:1234

Log: $LOG_DIR/install.log
============================================================
EOF
