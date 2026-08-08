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

# telive usa il modulo nanohttp di libxml2 per parlare XMLRPC con il
# ricevitore. Da libxml2 2.12 è deprecato e dalla 2.14 è stato rimosso: su
# quelle versioni la compilazione muore su un #include mancante, con un
# messaggio che non dice niente di utile. Meglio accorgersene prima.
check_libxml_nanohttp() {
	local incdir
	incdir="$(xml2-config --cflags 2>/dev/null | tr ' ' '\n' | grep '^-I' | head -1)"
	incdir="${incdir#-I}"
	[ -n "$incdir" ] || return 0          # niente xml2-config: ci pensa la build

	if [ ! -f "$incdir/libxml/nanohttp.h" ]; then
		log_error "libxml2 $(pkg-config --modversion libxml-2.0 2>/dev/null) non fornisce più libxml/nanohttp.h."
		log_info  "telive lo usa per il controllo XMLRPC del ricevitore, quindi non compila."
		log_info  "Il modulo è stato rimosso da libxml2 2.14: serve una correzione"
		log_info  "a monte, in telive. Segnala il problema aprendo una issue su:"
		log_info  "  https://github.com/chiaraberti13/OsmoTetraUbuntu/issues"
		return 1
	fi
	return 0
}

main() {
	log_step "telive"
	check_libxml_nanohttp || return 1
	clone_or_update "$TELIVE_URL" "$SRCDIR"
	make_data_dirs

	if [ "${DRY_RUN:-0}" = "1" ]; then
		log_info "[dry-run] make -C $SRCDIR"
		install_helpers
		return 0
	fi

	# telive_receiver.h dichiara campi time_t ma include solo gli header di
	# libxml2 e stdint.h. Finora funzionava perché libxml2 tirava dentro
	# <time.h> per conto suo; dalla 2.12 non più. Il guaio si vede perché il
	# Makefile di telive compila anche l'header da solo:
	#
	#     telive_receiver.o: telive_receiver.c telive_receiver.h
	#             $(CC) $(CFLAGS) -c $^
	#
	# con "$^" che si espande a entrambi i prerequisiti. Il .c se la cava
	# perché include <sys/types.h>, l'header isolato no e la build muore con
	# "unknown type name 'time_t'".
	#
	# -include time.h antepone l'header a ogni unità di traduzione: risolve sia
	# la compilazione isolata sia qualunque altro file includa telive_receiver.h
	# senza time.h, e non richiede di modificare i sorgenti upstream (che
	# verrebbero comunque sovrascritti al prossimo aggiornamento).
	local cc_flags; cc_flags="$(legacy_c_flags) -include time.h"
	log_info "Compilo (CC=\"${CC:-gcc} $cc_flags\")..."

	make -C "$SRCDIR" clean >/dev/null 2>&1 || true

	if ! make -C "$SRCDIR" CC="${CC:-gcc} $cc_flags" > "$SRCDIR/build.log" 2>&1; then
		report_build_failure "$SRCDIR/build.log" "telive"
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
