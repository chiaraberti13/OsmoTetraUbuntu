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

TELIVE_URL="${TELIVE_URL:-https://github.com/sq5bpf/telive-2}"
PREFIX="${PREFIX:?PREFIX non impostato}"
SRCDIR="$PREFIX/src/telive-2"
TETRADIR="$PREFIX/tetra"
PATCHES="$(cd "$HERE/.." && pwd)/patches"

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

# telive-2 comunica in XMLRPC col ricevitore usando il modulo nanohttp di
# libxml2, deprecato dalla 2.12 e rimosso dalla 2.14. Su Ubuntu 25.04+
# (libxml2 >= 2.14) non compilerebbe. Applichiamo una patch che sostituisce
# quelle chiamate con una POST via socket (vedi patches/README.md).
#
# patch -p1 -N è idempotente: se è già applicata (secondo ./install.sh) esce
# senza fare danni. Se non applica pulita — l'autore ha toccato quelle righe a
# monte — ci si ferma con una diagnosi chiara invece di un errore oscuro del
# compilatore su nanohttp.h.
NANOHTTP_PATCH="telive2-nanohttp-to-socket.diff"
apply_nanohttp_patch() {
	local patch="$PATCHES/$NANOHTTP_PATCH"
	if [ ! -f "$patch" ]; then
		log_warn "Patch $NANOHTTP_PATCH non trovata in $PATCHES: procedo senza."
		return 0
	fi
	if [ "${DRY_RUN:-0}" = "1" ]; then
		log_info "[dry-run] applico $NANOHTTP_PATCH a telive-2"
		return 0
	fi

	# Già applicata? (il -R --dry-run riesce quando la patch è invertibile,
	# cioè già presente nei sorgenti.)
	if patch -p1 -R --dry-run -f -d "$SRCDIR" < "$patch" >/dev/null 2>&1; then
		log_ok "Patch nanohttp già applicata"
		return 0
	fi
	if patch -p1 -N -d "$SRCDIR" < "$patch" >/dev/null 2>&1; then
		log_ok "Patch nanohttp applicata (POST XMLRPC via socket)"
		return 0
	fi

	log_error "La patch $NANOHTTP_PATCH non si applica ai sorgenti attuali di telive-2."
	log_info  "Probabilmente l'autore ha modificato le funzioni XMLRPC a monte."
	log_info  "Va rigenerata: vedi le istruzioni in patches/README.md."
	return 1
}

main() {
	log_step "telive-2"
	clone_or_update "$TELIVE_URL" "$SRCDIR"
	apply_nanohttp_patch || return 1
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
	#
	# Lo standard del linguaggio è fissato a gnu17 dentro legacy_c_flags(), che
	# serve entrambi i progetti: serve anche qui, perché GCC 15 passa a gnu23 e
	# in C23 `void timeout_receivers()` significa "nessun parametro" invece di
	# "parametri non specificati", mentre telive la chiama passando grxml_url.
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
