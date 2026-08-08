#!/bin/bash
# 50_sdr_udev.sh - permessi USB per le chiavette SDR e disattivazione del
#                  driver DVB-T che se le prende prima di gr-osmosdr
#
# Su Ubuntu il kernel carica dvb_usb_rtl28xxu appena si inserisce una chiavetta
# RTL2832: il dispositivo risulta poi occupato e gr-osmosdr fallisce con
# "usb_claim_interface error -6". Il pacchetto rtl-sdr installa già la
# blacklist, ma i moduli possono essere caricati nella sessione corrente.
#
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib_common.sh
. "$HERE/lib_common.sh"

BLACKLIST=/etc/modprobe.d/osmotetra-blacklist-dvb.conf
DVB_MODULES=(dvb_usb_rtl28xxu rtl2832 rtl2830 e4000 dvb_usb_v2 rtl2832_sdr)

install_blacklist() {
	local tmp
	tmp="$(mktemp)"
	cat > "$tmp" <<'EOF'
# Installato da OsmoTetraUbuntu.
# Impedisce al driver DVB-T di occupare le chiavette RTL2832 che servono a
# gr-osmosdr. Rimuovi questo file se vuoi tornare a usarle per la TV digitale.
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
blacklist e4000
EOF
	if [ -f "$BLACKLIST" ] && cmp -s "$tmp" "$BLACKLIST"; then
		rm -f "$tmp"
		log_ok "Blacklist DVB-T già aggiornata"
		return 0
	fi
	run ${SUDO:+$SUDO} install -m 644 "$tmp" "$BLACKLIST"
	rm -f "$tmp"
	log_ok "Blacklist DVB-T installata in $BLACKLIST"
}

unload_modules() {
	local m loaded=0
	for m in "${DVB_MODULES[@]}"; do
		if lsmod 2>/dev/null | grep -q "^$m "; then
			loaded=1
			run ${SUDO:+$SUDO} rmmod "$m" 2>/dev/null \
				|| log_warn "impossibile scaricare il modulo $m (in uso?)"
		fi
	done
	[ "$loaded" = "1" ] && log_ok "Moduli DVB-T scaricati" || log_info "Nessun modulo DVB-T caricato"
}

add_user_to_plugdev() {
	# Le regole udev di rtl-sdr assegnano i dispositivi al gruppo plugdev.
	if ! getent group plugdev >/dev/null 2>&1; then
		log_info "Gruppo plugdev inesistente: salto."
		return 0
	fi
	if id -nG "$USER" 2>/dev/null | tr ' ' '\n' | grep -qx plugdev; then
		log_ok "$USER è già nel gruppo plugdev"
		return 0
	fi
	run ${SUDO:+$SUDO} usermod -aG plugdev "$USER"
	log_ok "$USER aggiunto al gruppo plugdev"
	log_warn "Serve un logout/login (o un riavvio) perché il nuovo gruppo abbia effetto."
}

main() {
	log_step "Configurazione SDR (udev e moduli kernel)"
	require_sudo
	install_blacklist
	unload_modules
	add_user_to_plugdev
	run ${SUDO:+$SUDO} udevadm control --reload-rules 2>/dev/null || true
	run ${SUDO:+$SUDO} udevadm trigger 2>/dev/null || true
	log_info "Se la chiavetta è già inserita, scollegala e reinseriscila."
}

main "$@"
