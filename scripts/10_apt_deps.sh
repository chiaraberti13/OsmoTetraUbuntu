#!/bin/bash
# 10_apt_deps.sh - installa i pacchetti di sistema necessari a OsmoTetraUbuntu
#
# Tutti i pacchetti provengono dagli archivi standard di Ubuntu 24.04
# (main + universe): nessun PPA, nessuna compilazione di GNU Radio a mano.
#
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib_common.sh
. "$HERE/lib_common.sh"

# Toolchain e librerie per compilare osmo-tetra-sq5bpf e telive
PKGS_BUILD=(
	build-essential
	git
	make
	pkg-config
	libosmocore-dev      # osmo_conv_*, msgb, gsmtap: richiesto da tetra-rx
	libncurses-dev       # interfaccia di telive
	libxml2-dev          # telive legge tetra.xml (MCC/MNC)
)

# Catena di ricezione: GNU Radio + driver SDR + trasporto
PKGS_SDR=(
	gnuradio             # 3.10.x su noble: i flowgraph sono per python3/gr3.10
	gnuradio-dev
	gr-osmosdr           # sorgente osmosdr (rtl, hackrf, airspy, uhd, ...)
	rtl-sdr              # utility rtl_test/rtl_sdr, regole udev
	socat                # trasporto UDP -> stdin del demodulatore
	python3-numpy        # usato dal blocco python embedded di simdemod3
)

# GUI e terminale per telive
PKGS_UI=(
	python3
	python3-pyqt5        # stessa Qt5 di gnuradio: nessun conflitto
	xterm                # telive richiede un terminale 203x60
)

# Audio: riproduzione e ricompressione delle chiamate registrate
PKGS_AUDIO=(
	alsa-utils           # aplay, usato da tplay
	sox                  # conversione raw -> wav in tetrad
	vorbis-tools         # oggenc
)

# Utilità richieste dallo script di installazione del codec ACELP
PKGS_CODEC=(
	unzip
	wget
	patch
)

main() {
	require_sudo

	local pkgs=("${PKGS_BUILD[@]}" "${PKGS_SDR[@]}" "${PKGS_UI[@]}" "${PKGS_AUDIO[@]}" "${PKGS_CODEC[@]}")

	log_step "Aggiornamento elenco pacchetti"
	if ! run ${SUDO:+$SUDO} apt-get update -qq; then
		log_error "apt-get update fallito."
		log_info  "Verifica la connessione di rete e che i repository Ubuntu siano raggiungibili."
		return 1
	fi

	log_step "Installazione pacchetti di sistema (${#pkgs[@]} pacchetti)"
	log_info "${pkgs[*]}"
	if ! run ${SUDO:+$SUDO} apt-get install -y "${pkgs[@]}"; then
		log_error "Installazione dei pacchetti fallita."
		log_info  "Se il problema riguarda gnuradio/gr-osmosdr, controlla che il componente"
		log_info  "'universe' sia abilitato:  sudo add-apt-repository universe"
		return 1
	fi
	log_ok "Pacchetti installati"

	# Verifica che la versione di GNU Radio sia quella attesa dai flowgraph.
	if have_cmd gnuradio-config-info; then
		local grv; grv="$(gnuradio-config-info -v 2>/dev/null || true)"
		case "$grv" in
			3.1[0-9]*) log_ok "GNU Radio $grv" ;;
			3.[89]*)   log_warn "GNU Radio $grv: i flowgraph sono sviluppati per 3.10, potrebbero non funzionare." ;;
			"")        log_warn "Impossibile determinare la versione di GNU Radio." ;;
			*)         log_warn "GNU Radio $grv non testata con questo software." ;;
		esac
	fi
}

main "$@"
