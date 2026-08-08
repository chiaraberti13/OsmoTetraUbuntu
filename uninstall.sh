#!/bin/bash
# uninstall.sh - rimuove OsmoTetraUbuntu
#
# Per impostazione predefinita conserva le registrazioni, i log e la
# configurazione. Usa --purge per cancellare anche quelli.
#
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib_common.sh
. "$REPO/scripts/lib_common.sh"

PREFIX="${PREFIX:-$HOME/.local/share/osmotetra}"
BINDIR="${BINDIR:-$HOME/.local/bin}"
APPDIR="${APPDIR:-$HOME/.local/share/applications}"
ICONDIR="${ICONDIR:-$HOME/.local/share/icons/hicolor/scalable/apps}"
CONFDIR="${CONFDIR:-$HOME/.config/osmotetra}"
DRY_RUN=0
PURGE=0
BLACKLIST=/etc/modprobe.d/osmotetra-blacklist-dvb.conf

usage() {
	cat <<EOF
Uso: ./uninstall.sh [opzioni]

  --prefix DIR   directory di installazione (default: $HOME/.local/share/osmotetra)
  --purge        rimuove anche registrazioni, log e configurazione
  --dry-run      mostra le azioni senza eseguirle
  -h, --help     questo messaggio
EOF
}

while [ $# -gt 0 ]; do
	case "$1" in
		--prefix)   PREFIX="${2:?}"; shift 2 ;;
		--prefix=*) PREFIX="${1#*=}"; shift ;;
		--purge)    PURGE=1; shift ;;
		--dry-run)  DRY_RUN=1; shift ;;
		-h|--help)  usage; exit 0 ;;
		*)          log_error "opzione sconosciuta: $1"; usage >&2; exit 2 ;;
	esac
done
export DRY_RUN

# Se l'installazione è avvenuta con percorsi non standard, il manifest li sa.
if [ -f "$PREFIX/install-manifest" ]; then
	# shellcheck disable=SC1090
	. "$PREFIX/install-manifest"
fi

log_step "Rimozione di OsmoTetraUbuntu"
[ "$DRY_RUN" = "1" ] && log_warn "modalità dry-run: nessuna modifica"

run rm -f "$BINDIR/osmotetra"
run rm -f "$APPDIR/osmotetra.desktop"
run rm -f "$ICONDIR/osmotetra.svg"
log_ok "Launcher e voce di menu rimossi"

run rm -rf "$PREFIX/lib"
log_ok "Applicazione rimossa"

if [ "$PURGE" = "1" ]; then
	log_warn "--purge: rimuovo sorgenti, registrazioni, log e configurazione"
	run rm -rf "$PREFIX" "$CONFDIR"
	if [ -f "$BLACKLIST" ]; then
		require_sudo
		run ${SUDO:+$SUDO} rm -f "$BLACKLIST"
		log_ok "Blacklist DVB-T rimossa"
	fi
	log_ok "Rimozione completa"
else
	log_info "Conservati (usa --purge per rimuoverli):"
	log_info "  sorgenti upstream e binari: $PREFIX/src"
	log_info "  registrazioni e log:        $PREFIX/tetra"
	log_info "  configurazione e profili:   $CONFDIR"
	log_info "  blacklist DVB-T:            $BLACKLIST"
fi

log_info "I pacchetti installati con apt non vengono rimossi."
log_info "Per toglierli:  sudo apt-get autoremove gnuradio gr-osmosdr libosmocore-dev"
