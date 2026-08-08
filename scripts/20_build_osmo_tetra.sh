#!/bin/bash
# 20_build_osmo_tetra.sh - clona e compila osmo-tetra-sq5bpf
#
# Produce i due binari che servono alla catena di ricezione:
#   src/tetra-rx       decoder TETRA (con float_to_bits incorporato)
#   src/float_to_bits  conversione float -> bit (usato solo dai flussi legacy)
#
# Verificato su Ubuntu 24.04 con libosmocore-dev 1.7.0: compila senza patch.
#
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib_common.sh
. "$HERE/lib_common.sh"

OSMO_TETRA_URL="${OSMO_TETRA_URL:-https://github.com/sq5bpf/osmo-tetra-sq5bpf-2}"
PREFIX="${PREFIX:?PREFIX non impostato}"
SRCDIR="$PREFIX/src/osmo-tetra-sq5bpf-2"

check_libosmocore() {
	if ! pkg-config --exists libosmocore 2>/dev/null; then
		log_error "libosmocore non trovata da pkg-config."
		log_info  "Installa il pacchetto:  sudo apt-get install libosmocore-dev"
		return 1
	fi
	log_ok "libosmocore $(pkg-config --modversion libosmocore)"
}

main() {
	log_step "osmo-tetra-sq5bpf"
	check_libosmocore || return 1
	clone_or_update "$OSMO_TETRA_URL" "$SRCDIR"

	if [ "${DRY_RUN:-0}" = "1" ]; then
		log_info "[dry-run] make -C $SRCDIR/src"
		return 0
	fi

	local cc_flags; cc_flags="$(legacy_c_flags)"
	log_info "Compilo (CC=\"${CC:-gcc} $cc_flags\")..."

	# make clean prima: se i sorgenti sono stati aggiornati da un pull, gli
	# oggetti vecchi possono restare indietro rispetto agli header.
	make -C "$SRCDIR/src" clean >/dev/null 2>&1 || true

	if ! make -C "$SRCDIR/src" CC="${CC:-gcc} $cc_flags" > "$SRCDIR/build.log" 2>&1; then
		report_build_failure "$SRCDIR/build.log" "osmo-tetra-sq5bpf-2"
		return 1
	fi

	local missing=0 b
	for b in tetra-rx float_to_bits; do
		if [ -x "$SRCDIR/src/$b" ]; then
			log_ok "$b compilato"
		else
			log_error "$b non è stato prodotto"
			missing=1
		fi
	done
	[ "$missing" = "0" ] || return 1
}

main "$@"
