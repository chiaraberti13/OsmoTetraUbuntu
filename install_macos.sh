#!/usr/bin/env bash
# ============================================================================
#  install_macos.sh — installazione di OsmoTetra su macOS (Apple Silicon, M1…M4)
# ============================================================================
#  Variante NATIVA per macOS: niente macchina virtuale. Usa MacPorts per
#  gnuradio e gr-osmosdr (su Homebrew gr-osmosdr è rotto) e compila libosmocore
#  dai sorgenti (il port MacPorts è troppo vecchio per clang recente).
#
#  Prerequisito (una tantum): Xcode Command Line Tools.
#      xcode-select --install
#  MacPorts, se manca, lo installa in automatico questo script (dai sorgenti
#  ufficiali; serve solo la toolchain di Xcode). Non devi scaricare nulla a mano.
#
#  Uso:   ./install_macos.sh        (come utente normale; chiede la password
#                                    sudo per 'port' e per creare le cartelle)
#
#  NOTA: è una variante NUOVA e non ancora collaudata su ogni macchina. Se un
#  passo di build fallisce, copiami l'errore: si sistema come abbiamo fatto su
#  Ubuntu. La catena di segnale e il decoder sono gli stessi, provati, di SQ5BPF.
#
#  DISCLAIMER: la decifratura funziona solo con chiave GIÀ NOTA; questi
#  strumenti non craccano il TETRA. Usalo solo dove consentito dalla legge.
# ============================================================================
set -euo pipefail

OSMO_REPO="https://github.com/sq5bpf/osmo-tetra-sq5bpf-2.git"
TELIVE_REPO="https://github.com/sq5bpf/telive-2.git"

OSMOTETRA_HOME="${OSMOTETRA_HOME:-$HOME/telive2}"
OSMO_DIR="$OSMOTETRA_HOME/osmo-tetra-sq5bpf-2"
TELIVE_DIR="$OSMOTETRA_HOME/telive-2"
TETRA_ROOT="${TETRA_ROOT:-$HOME/tetra}"     # su macOS stiamo nella home, non in /tetra
BIN_DIR="$OSMOTETRA_HOME/bin"

HERE="$(cd "$(dirname "$0")" && pwd)"
NANOHTTP_PATCH="$HERE/patches/telive2-nanohttp-to-socket.diff"

ETSI_URL="http://www.etsi.org/deliver/etsi_en/300300_300399/30039502/01.03.01_60/en_30039502v010301p0.zip"
ETSI_MD5="a8115fe68ef8f8cc466f4192572a1e3e"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

PREFIX="/opt/local"                          # MacPorts
export PATH="$PREFIX/bin:$PREFIX/sbin:$PATH"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
GMAKE="$PREFIX/bin/gmake"
COMPAT_CFLAGS=""

LOG_DIR="$OSMOTETRA_HOME/logs"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_DIR/install_macos.log") 2>&1
echo "==== install_macos.sh — $(date '+%Y-%m-%d %H:%M:%S') ===="

step() { echo; echo "============================================================"; echo " $*"; echo "============================================================"; }
info() { echo "  -> $*"; }
die()  { echo "ERRORE: $*" >&2; exit 1; }

# BSD sed vuole un argomento per -i; GNU no. Qui siamo su macOS: sed -i ''.
sedi() { sed -i '' "$@"; }
md5of() { md5 -q "$1"; }

# MacPorts assente: lo installiamo dai sorgenti ufficiali (bastano gli Xcode
# CLT, già presenti). Evita il download manuale del .pkg.
install_macports_from_source() {
  step "MacPorts non trovato: lo installo dai sorgenti (una tantum)"
  command -v curl >/dev/null 2>&1 || die "manca 'curl' per scaricare MacPorts."
  local tmp url srcdir
  tmp="$(mktemp -d)"
  info "Cerco l'ultima versione di macports-base su GitHub…"
  url="$(curl -fsSL https://api.github.com/repos/macports/macports-base/releases/latest \
        | awk -F'"' '/browser_download_url/ && /\.tar\.bz2"/{print $4; exit}')"
  [ -n "$url" ] || die "non trovo il tarball di MacPorts (rete/API GitHub). Installa MacPorts a mano da https://www.macports.org/install.php e rilancia."
  info "Scarico:  $url"
  curl -fSL "$url" -o "$tmp/macports.tar.bz2" || die "download di MacPorts fallito."
  tar xjf "$tmp/macports.tar.bz2" -C "$tmp" || die "estrazione di MacPorts fallita."
  srcdir="$(find "$tmp" -maxdepth 1 -type d -name 'MacPorts-*' | head -1)"
  [ -n "$srcdir" ] || die "sorgenti MacPorts non trovati dopo l'estrazione."
  info "Compilo e installo MacPorts (chiede la password sudo)…"
  # qui si usa il 'make' di sistema (GNU make dei CLT): gmake non esiste ancora.
  ( cd "$srcdir" && ./configure && make && sudo make install ) \
    || die "build/installazione di MacPorts fallita."
  rm -rf "$tmp"
  export PATH="/opt/local/bin:/opt/local/sbin:$PATH"
  hash -r 2>/dev/null || true
  command -v port >/dev/null 2>&1 || die "MacPorts installato ma 'port' non è nel PATH."
  info "Sincronizzo l'albero dei port (primo selfupdate: può volerci qualche minuto)…"
  sudo port -v selfupdate || die "port selfupdate fallito: riprova con una rete stabile."
  # rendi 'port' disponibile anche nelle sessioni future
  if ! grep -q '/opt/local/bin' "$HOME/.zshrc" 2>/dev/null; then
    printf '\n# MacPorts\nexport PATH="/opt/local/bin:/opt/local/sbin:$PATH"\n' >> "$HOME/.zshrc"
  fi
  info "MacPorts pronto."
}

# libosmocore aggiornata, compilata dai sorgenti in un prefisso LOCALE (non
# tocca /opt/local). Al decoder serve solo la libreria CORE, che su macOS
# compila pulita; talloc/gnutls li ha già messi MacPorts. Il port 'osmocore'
# di MacPorts è fermo alla 1.3.0 e non regge clang-19.
OSMOCORE_PREFIX="$OSMOTETRA_HOME/osmocore"
build_libosmocore() {
  export PKG_CONFIG_PATH="$OSMOCORE_PREFIX/lib/pkgconfig:$PKG_CONFIG_PATH"
  if pkg-config --exists libosmocore 2>/dev/null; then
    info "libosmocore già presente ($(pkg-config --modversion libosmocore))."
    return 0
  fi
  step "Compilo libosmocore dai sorgenti (in $OSMOCORE_PREFIX)"
  local src="$OSMOTETRA_HOME/src-libosmocore"
  if [ -d "$src/.git" ]; then
    git -C "$src" checkout -- . 2>/dev/null || true
    git -C "$src" pull --ff-only || true
  else
    git clone --depth 1 https://github.com/osmocom/libosmocore.git "$src"
  fi
  (
    cd "$src"
    # su macOS i tool GNU libtool sono prefissati con 'g' (glibtoolize)
    LIBTOOLIZE=glibtoolize autoreconf -fi
    PKG_CONFIG_PATH="/opt/local/lib/pkgconfig" \
    CFLAGS="-Wno-error=implicit-function-declaration -Wno-error=int-conversion -Wno-error=incompatible-pointer-types" \
      ./configure --prefix="$OSMOCORE_PREFIX" --disable-doc --disable-pcsc
    "$GMAKE" -j"$JOBS"
    "$GMAKE" install
  ) || die "build di libosmocore fallita (vedi l'output qui sopra)."
  info "libosmocore $(pkg-config --modversion libosmocore 2>/dev/null) installata."
}

# ---------------------------------------------------------------------------
# 0) Prerequisiti
# ---------------------------------------------------------------------------
step "0) Controllo prerequisiti (macOS, Xcode CLT, MacPorts)"
[ "$(uname -s)" = "Darwin" ] || die "questo installer è per macOS. Su Linux usa ./install.sh"
info "macOS $(sw_vers -productVersion 2>/dev/null)  ·  arch $(uname -m)  ·  core $JOBS"

xcode-select -p >/dev/null 2>&1 || die "mancano gli Xcode Command Line Tools. Esegui:  xcode-select --install"

if ! command -v port >/dev/null 2>&1; then
  install_macports_from_source
fi

# ---------------------------------------------------------------------------
# 1) Dipendenze via MacPorts
# ---------------------------------------------------------------------------
step "1) Dipendenze (MacPorts) — può richiedere parecchio la prima volta"
sudo port -N selfupdate || info "selfupdate saltato (offline?)"
# Dipendenze generiche + gli strumenti per compilare libosmocore dai sorgenti
# (autoconf/automake/libtool/talloc): il port 'osmocore' di MacPorts è vecchio
# (1.3.0) e non compila con clang recente, quindi la libreria la costruiamo noi.
sudo port -N install \
  gnuradio rtl-sdr \
  socat gmake pkgconfig ncurses libxml2 sox wget \
  autoconf automake libtool autoconf-archive talloc gnutls
# gr-osmosdr SOLO con RTL-SDR, SENZA UHD/USRP: l'UHD dipende da 'tecla', che su
# Apple Silicon non compila (e non ci serve). +rtlsdr abilita la chiavetta.
# Un tentativo precedente può aver iniziato la build con +uhd: MacPorts allora
# rifiuta le nuove varianti finché non si pulisce la build parziale.
sudo port -N clean gr-osmosdr 2>/dev/null || true
sudo port -N install gr-osmosdr +rtlsdr -uhd
info "Pacchetti MacPorts installati."

[ -x "$GMAKE" ] || die "gmake non trovato dopo l'installazione MacPorts."

# libosmocore dai sorgenti (il port MacPorts è troppo vecchio per clang-19).
build_libosmocore
pkg-config --exists libosmocore || die "libosmocore non trovata dopo la build dai sorgenti."

# Flag di compatibilità del compilatore (clang): teniamo solo quelli accettati.
detect_compat_cflags() {
  local cc="cc" out="" f tmp
  tmp="$(mktemp -d)"
  printf 'int main(void){return 0;}\n' > "$tmp/probe.c"
  for f in -std=gnu17 \
           -Wno-error=implicit-int -Wno-error=implicit-function-declaration \
           -Wno-error=int-conversion -Wno-error=incompatible-pointer-types \
           -Wno-error=deprecated-non-prototype -Wno-error=deprecated-declarations; do
    "$cc" "$f" -c "$tmp/probe.c" -o "$tmp/probe.o" >/dev/null 2>&1 && out="$out $f"
  done
  rm -rf "$tmp"; echo "${out# }"
}
COMPAT_CFLAGS="$(detect_compat_cflags)"
info "Flag compat clang: ${COMPAT_CFLAGS:-nessuno}"

# ---------------------------------------------------------------------------
# 2) Sorgenti
# ---------------------------------------------------------------------------
step "2) Sorgenti (osmo-tetra-sq5bpf-2 e telive-2)"
clone_or_update() {
  local url="$1" dir="$2"
  if [ -d "$dir/.git" ]; then
    info "Aggiorno $dir"
    git -C "$dir" checkout -- . 2>/dev/null || true   # scarta le patch macOS precedenti
    git -C "$dir" pull --ff-only || true
  else
    info "Clono $url"; git clone --depth 1 "$url" "$dir"
  fi
}
clone_or_update "$OSMO_REPO" "$OSMO_DIR"
clone_or_update "$TELIVE_REPO" "$TELIVE_DIR"

# ---------------------------------------------------------------------------
# 3) Adattamenti macOS ai sorgenti del decoder
# ---------------------------------------------------------------------------
step "3) Adatto il decoder a macOS (2 piccole modifiche)"
# 3a) tuntap.c usa /dev/net/tun (Linux). Su macOS il TUN (dati a pacchetto
#     SNDCP) non serve per il monitoraggio voce/SDS: stub che lo disabilita.
cat > "$OSMO_DIR/src/tuntap.c" <<'EOF'
/* macOS: nessun /dev/net/tun. Il TUN (dati a pacchetto) non serve per il
 * monitoraggio voce/SDS; stub che disabilita la funzione. */
int tun_alloc(char *dev) { (void)dev; return -1; }
EOF
info "tuntap.c → stub (TUN disabilitato)"
# 3b) linux/limits.h → limits.h
sedi 's|#include <linux/limits.h>|#include <limits.h>|' \
  "$OSMO_DIR/src/lower_mac/tetra_lower_mac.c"
info "linux/limits.h → limits.h"

inject_cflags() {
  # BSD sed non accetta l'indirizzo di riga 0: la riga top-level 'CFLAGS=' è
  # unica (le varianti tipo 'debug: CFLAGS :=' non iniziano con CFLAGS), quindi
  # una semplice sostituzione sull'ancora ^CFLAGS= è sufficiente e sicura.
  local mk="$1"; [ -f "$mk" ] || return 0; [ -n "$COMPAT_CFLAGS" ] || return 0
  grep -q -- '-std=gnu17' "$mk" && return 0
  sedi "s/^CFLAGS[[:space:]]*=/&${COMPAT_CFLAGS} /" "$mk"
  info "compat cflags → $(basename "$(dirname "$mk")")/$(basename "$mk")"
}

# ---------------------------------------------------------------------------
# 4) Build del decoder (tetra-rx) — solo i target che servono
# ---------------------------------------------------------------------------
step "4) Compilo il decoder (tetra-rx)"
inject_cflags "$OSMO_DIR/src/Makefile"
"$GMAKE" -C "$OSMO_DIR/src" -j"$JOBS" tetra-rx float_to_bits
[ -x "$OSMO_DIR/src/tetra-rx" ] && info "OK: tetra-rx" || die "tetra-rx non compilato"

# ---------------------------------------------------------------------------
# 5) Codec vocale ETSI (cdecoder / sdecoder)
# ---------------------------------------------------------------------------
step "5) Codec vocale ETSI"
PATCHDIR="$OSMO_DIR/etsi_codec-patches"
ZIP="$PATCHDIR/etsi_tetra_codec.zip"
got=0
info "Scarico il codec da ETSI…"
if wget -q -U "$UA" -O "$ZIP" "$ETSI_URL" && [ "$(md5of "$ZIP")" = "$ETSI_MD5" ]; then got=1
else
  info "ETSI non raggiungibile: provo il mirror archive.org…"
  wget -q -U "$UA" -O "$ZIP" "https://web.archive.org/web/2id_/$ETSI_URL" \
    && [ "$(md5of "$ZIP")" = "$ETSI_MD5" ] && got=1 || true
fi
# lo script del codec usa md5sum/print: adattiamolo a macOS (md5, echo)
sedi 's/md5sum/md5 -r/g; s/print "MD5sum/echo "MD5sum/g' "$PATCHDIR/download_and_patch.sh" || true
if [ "$got" -eq 1 ]; then
  info "Zip ETSI verificato."
  sedi 's/\[ ! -f $LOCAL_FILE \]/false/g' "$PATCHDIR/download_and_patch.sh"
else
  info "Pre-download non riuscito: lo script scaricherà da solo."
  sedi 's/\[ ! -f $LOCAL_FILE \]/true/g; s/wget -O/wget -U "Mozilla\/5.0" -O/g' "$PATCHDIR/download_and_patch.sh"
fi
( cd "$PATCHDIR" && sh ./download_and_patch.sh )
inject_cflags "$OSMO_DIR/codec/c-code/Makefile"
"$GMAKE" -C "$OSMO_DIR/codec/c-code" -j"$JOBS"
[ -x "$OSMO_DIR/codec/c-code/cdecoder" ] && [ -x "$OSMO_DIR/codec/c-code/sdecoder" ] \
  && info "OK: cdecoder e sdecoder" || die "codec non compilato"

# ---------------------------------------------------------------------------
# 6) telive
# ---------------------------------------------------------------------------
step "6) Compilo telive"
inject_cflags "$TELIVE_DIR/Makefile"
# time.h (come su Linux): prepend robusto (niente 'sed 1i', fragile su BSD)
TRH="$TELIVE_DIR/telive_receiver.h"
if [ -f "$TRH" ] && ! grep -q '#include <time.h>' "$TRH"; then
  { printf '#include <time.h>\n'; cat "$TRH"; } > "$TRH.tmp" && mv "$TRH.tmp" "$TRH"
  info "aggiunto #include <time.h> a telive_receiver.h"
fi
# nanohttp: la libxml2 di MacPorts potrebbe non averlo più → patch a socket.
probe="$(mktemp -d)"
printf '#include <libxml/nanohttp.h>\nint main(void){xmlNanoHTTPInit();return 0;}\n' > "$probe/p.c"
# SC2046 volontario: xml2-config stampa più flag che DEVONO essere separati.
# shellcheck disable=SC2046
if cc "$probe/p.c" $(xml2-config --cflags --libs) -o "$probe/p" >/dev/null 2>&1; then
  info "libxml2 con nanohttp: nessuna patch."
else
  info "libxml2 senza nanohttp: applico la patch socket."
  if patch -p1 -R --dry-run -d "$TELIVE_DIR" < "$NANOHTTP_PATCH" >/dev/null 2>&1; then
    info "patch nanohttp già applicata."
  else
    patch -p1 -N -d "$TELIVE_DIR" < "$NANOHTTP_PATCH" || die "patch nanohttp non applicabile (vedi patches/README.md)"
  fi
fi
rm -rf "$probe"
"$GMAKE" -C "$TELIVE_DIR" -j"$JOBS"
[ -x "$TELIVE_DIR/telive" ] && info "OK: telive" || die "telive non compilato"

# ---------------------------------------------------------------------------
# 7) Cartelle di lavoro, binari, PATH
# ---------------------------------------------------------------------------
step "7) Cartelle e binari"
mkdir -p "$TETRA_ROOT"/{in,out,log,tmp} "$BIN_DIR"
touch "$TETRA_ROOT/log/telive.log"
cp -v "$TELIVE_DIR"/bin/* "$BIN_DIR/" 2>/dev/null || true
cp -v "$OSMO_DIR/codec/c-code/cdecoder" "$OSMO_DIR/codec/c-code/sdecoder" "$BIN_DIR/"
cp -v "$TELIVE_DIR/telive" "$BIN_DIR/"
chmod +x "$BIN_DIR"/* || true

ZRC="$HOME/.zshrc"
if ! grep -q "OsmoTetra" "$ZRC" 2>/dev/null; then
  printf '\n# OsmoTetra (macOS)\nexport PATH="%s:$PATH"\n' "$BIN_DIR" >> "$ZRC"
  info "Aggiunto $BIN_DIR al PATH in ~/.zshrc"
fi

# ---------------------------------------------------------------------------
# 8) Flowgraph, lanciatore, interprete Python di GNU Radio
# ---------------------------------------------------------------------------
step "8) Lanciatore"
install -m 0755 "$HERE/osmotetra_rx.py"      "$OSMOTETRA_HOME/osmotetra_rx.py"
install -m 0755 "$HERE/avvia_macos.command"  "$OSMOTETRA_HOME/avvia_macos.command"

# Trova l'interprete Python che ha i binding di GNU Radio (quello di MacPorts).
GR_PY=""
for p in "$PREFIX"/bin/python3.1[0-9] "$PREFIX"/bin/python3; do
  [ -x "$p" ] || continue
  if "$p" -c 'import gnuradio' >/dev/null 2>&1; then GR_PY="$p"; break; fi
done
[ -n "$GR_PY" ] && info "Python GNU Radio: $GR_PY" \
  || info "ATTENZIONE: non ho trovato un python con 'import gnuradio'; imposta OSMOTETRA_PYTHON a mano."

# scrivi la configurazione che il lanciatore legge
cat > "$OSMOTETRA_HOME/osmotetra.env" <<EOF
export OSMOTETRA_HOME="$OSMOTETRA_HOME"
export OSMOTETRA_PYTHON="${GR_PY:-$PREFIX/bin/python3}"
export TETRA_ROOT="$TETRA_ROOT"
export OSMOTETRA_BIN="$BIN_DIR"
export PATH="$BIN_DIR:$PREFIX/bin:\$PATH"
EOF
info "Config scritta in $OSMOTETRA_HOME/osmotetra.env"

# ---------------------------------------------------------------------------
# Fine
# ---------------------------------------------------------------------------
cat <<EOF

============================================================
 Installazione OsmoTetra (macOS) completata!
============================================================

Tutto è in:  $OSMOTETRA_HOME

COME USARLO
   Doppio clic su:   $OSMOTETRA_HOME/avvia_macos.command
   oppure da Terminale:
       "$OSMOTETRA_HOME/avvia_macos.command" 390.5

   Si apre telive nella finestra del Terminale. La chiavetta RTL-SDR va
   collegata direttamente al Mac (niente VM): su macOS non c'è il problema
   del driver DVB-T.

Se un comando 'osmotetra'/telive non parte subito, riapri il Terminale
(così ~/.zshrc aggiorna il PATH).

Log: $LOG_DIR/install_macos.log
============================================================
EOF
