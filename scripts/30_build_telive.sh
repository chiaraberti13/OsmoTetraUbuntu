#!/bin/bash
# 30_build_telive.sh - clona e compila telive, e prepara le directory dati
#
# A differenza di telive/install.sh (che scrive in /tetra, di proprietà di
# root), qui tutto finisce sotto $PREFIX, nella home dell'utente:
#
#   $PREFIX/tetra/in    registrazioni ACELP grezze
#   $PREFIX/tetra/out   registrazioni ricompresse in OGG
#   $PREFIX/tetra/log   telive.log, KML, report frequenze
#   $PREFIX/tetra/tmp
#   $PREFIX/tetra/bin   tplay, tetrad e (se installati) i binari del codec
#
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib_common.sh
. "$HERE/lib_common.sh"

TELIVE_URL="${TELIVE_URL:-https://github.com/sq5bpf/telive}"
PREFIX="${PREFIX:?PREFIX non impostato}"
SRCDIR="$PREFIX/src/telive"
TETRADIR="$PREFIX/tetra"

# Genera uno script da template sostituendo i segnaposto @NOME@.
render_template() {
	local src="$1" dst="$2"
	sed -e "s|@CODEC_BIN@|$TETRADIR/bin|g" \
	    -e "s|@TETRA_IN@|$TETRADIR/in|g" \
	    -e "s|@TETRA_OUT@|$TETRADIR/out|g" \
	    "$src" > "$dst"
	chmod 755 "$dst"
}

make_data_dirs() {
	local d
	for d in in out log tmp bin; do
		run mkdir -p "$TETRADIR/$d"
	done
	[ "${DRY_RUN:-0}" = "1" ] || touch "$TETRADIR/log/telive.log"
	log_ok "Directory dati in $TETRADIR"
}

install_helpers() {
	if [ "${DRY_RUN:-0}" = "1" ]; then
		log_info "[dry-run] installo tplay e tetrad in $TETRADIR/bin"
		return 0
	fi
	# telive riproduce l'audio con popen("tplay"), cercandolo nel PATH.
	# Le versioni upstream di tplay/tetrad hanno /tetra/bin cablato dentro:
	# qui le rigeneriamo puntando alla directory reale del codec.
	render_template "$HERE/templates/tplay.in"  "$TETRADIR/bin/tplay"
	render_template "$HERE/templates/tetrad.in" "$TETRADIR/bin/tetrad"
	log_ok "tplay e tetrad installati in $TETRADIR/bin"
}

main() {
	log_step "telive"
	clone_or_update "$TELIVE_URL" "$SRCDIR"
	make_data_dirs

	if [ "${DRY_RUN:-0}" = "1" ]; then
		log_info "[dry-run] make -C $SRCDIR"
		install_helpers
		return 0
	fi

	local cc_flags; cc_flags="$(legacy_c_flags)"
	log_info "Compilo (CC=\"${CC:-gcc} $cc_flags\")..."

	make -C "$SRCDIR" clean >/dev/null 2>&1 || true

	if ! make -C "$SRCDIR" CC="${CC:-gcc} $cc_flags" > "$SRCDIR/build.log" 2>&1; then
		log_error "Compilazione di telive fallita."
		log_info  "Ultime righe di $SRCDIR/build.log:"
		tail -25 "$SRCDIR/build.log" >&2
		return 1
	fi

	if [ -x "$SRCDIR/telive" ]; then
		log_ok "telive compilato"
	else
		log_error "il binario telive non è stato prodotto"
		return 1
	fi

	install_helpers
}

main "$@"
