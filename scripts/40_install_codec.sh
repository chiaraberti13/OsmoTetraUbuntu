#!/bin/bash
# 40_install_codec.sh - installa il codec vocale ACELP (ETSI EN 300 395-2)
#
# PASSO OPZIONALE. Il codec non è redistribuibile: va scaricato dal sito ETSI.
# Senza codec tutto il resto di OsmoTetraUbuntu funziona (segnalazione, SDS,
# log, KML, analisi frequenze): manca solo l'audio.
#
# La procedura riprende install-tetra-codec di Jacek Lipkowski SQ5BPF:
# scarica lo zip ETSI, verifica l'md5, applica codec.diff, compila e installa
# cdecoder/ccoder/sdecoder/scoder — qui in $PREFIX/tetra/bin invece che in
# /tetra/bin.
#
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib_common.sh
. "$HERE/lib_common.sh"

CODEC_URL="${CODEC_URL:-https://www.etsi.org/deliver/etsi_en/300300_300399/30039502/01.03.01_60/en_30039502v010301p0.zip}"
CODEC_MD5="a8115fe68ef8f8cc466f4192572a1e3e"
CODEC_PATCH_URL="${CODEC_PATCH_URL:-https://github.com/sq5bpf/install-tetra-codec}"

# ETSI protegge l'area download con un filtro anti-bot che rifiuta il
# User-Agent predefinito di wget con HTTP 403, anche se il documento è
# pubblicamente scaricabile dal browser. Questi header riproducono una normale
# navigazione senza cookie, token o aggiramenti dell'autenticazione. L'MD5
# obbligatorio sotto resta la fonte di verità sul contenuto ricevuto.
ETSI_WGET_ARGS=(
	--user-agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
	--referer="https://www.etsi.org/standards-search"
	--header="Accept: application/zip,application/octet-stream;q=0.9,*/*;q=0.8"
)

PREFIX="${PREFIX:?PREFIX non impostato}"
INSTALLDIR="$PREFIX/tetra/bin"
CACHEDIR="$PREFIX/cache"
ZIPFILE="$CACHEDIR/en_30039502v010301p0.zip"
PATCHDIR="$PREFIX/src/install-tetra-codec"
ARCHIVE_NAME="$(basename "$ZIPFILE")"

CODEC_BINARIES=(cdecoder ccoder sdecoder scoder)

valid_archive() {
	local archive="$1" sum
	[ -f "$archive" ] || return 1
	sum="$(md5sum "$archive" 2>/dev/null | cut -d' ' -f1)"
	[ "$sum" = "$CODEC_MD5" ]
}

# ETSI può consentire il download dal browser ma negarlo ai client da riga di
# comando. Accetta quindi anche un archivio indicato esplicitamente o lasciato
# nella cartella Download, ma solo dopo averne verificato l'MD5.
import_local_archive() {
	local candidate
	for candidate in "${CODEC_ARCHIVE:-}" \
		"${XDG_DOWNLOAD_DIR:-${HOME:-}/Downloads}/$ARCHIVE_NAME" \
		"${HOME:-}/Scaricati/$ARCHIVE_NAME"; do
		[ -n "$candidate" ] || continue
		[ "$candidate" != "$ZIPFILE" ] || continue
		[ -f "$candidate" ] || continue
		if ! valid_archive "$candidate"; then
			log_warn "Ignoro l'archivio locale con MD5 errato: $candidate"
			continue
		fi
		mkdir -p "$CACHEDIR"
		install -m 600 "$candidate" "$ZIPFILE"
		log_ok "Archivio ETSI importato da $candidate"
		return 0
	done
	return 1
}

manual_instructions() {
	cat >&2 <<EOF

  ${C_BOLD}Installazione manuale del codec${C_RESET}

  1. Scarica il file dal sito ETSI (accesso libero, nessun account):
       $CODEC_URL
     In alternativa cerca "EN 300 395-2" su https://www.etsi.org/standards-search
     e scarica la versione 1.3.1.

  2. Lascialo in ~/Downloads (o ~/Scaricati), oppure indica il percorso:
       CODEC_ARCHIVE="/percorso/$ARCHIVE_NAME" PREFIX="$PREFIX" $HERE/$(basename "$0")
     Lo script lo importerà solo se corrisponde all'md5 atteso: $CODEC_MD5

  3. Se hai lasciato il file nella cartella Download, rilancia questo script:
       PREFIX="$PREFIX" $HERE/$(basename "$0")

EOF
}

already_installed() {
	local b
	for b in "${CODEC_BINARIES[@]}"; do
		[ -x "$INSTALLDIR/$b" ] || return 1
	done
	return 0
}

fetch_zip() {
	mkdir -p "$CACHEDIR"
	if [ -f "$ZIPFILE" ]; then
		log_info "Archivio già presente in $ZIPFILE"
		return 0
	fi
	if import_local_archive; then
		return 0
	fi
	log_info "Scarico il codec da ETSI..."
	# --no-verbose per non inondare il log della GUI; -T per non restare
	# appesi se il sito non risponde. Gli header browser evitano il 403 che ETSI
	# restituisce al normale User-Agent di wget.
	if ! retry 3 wget "${ETSI_WGET_ARGS[@]}" --no-verbose --timeout=60 --tries=1 \
		-O "$ZIPFILE.part" "$CODEC_URL"; then
		rm -f "$ZIPFILE.part"
		log_error "Download da ETSI non riuscito."
		manual_instructions
		return 1
	fi
	mv "$ZIPFILE.part" "$ZIPFILE"
}

verify_zip() {
	local sum
	sum="$(md5sum "$ZIPFILE" | cut -d' ' -f1)"
	if [ "$sum" != "$CODEC_MD5" ]; then
		log_error "md5 dell'archivio non corrispondente."
		log_info  "atteso:  $CODEC_MD5"
		log_info  "trovato: $sum"
		log_info  "Il file è incompleto, oppure ETSI ha pubblicato una revisione diversa."
		log_info  "Rimuovi $ZIPFILE e riprova, o scaricalo a mano."
		manual_instructions
		return 1
	fi
	log_ok "Archivio verificato (md5 $CODEC_MD5)"
}

build_and_install() {
	local work
	work="$(mktemp -d "${TMPDIR:-/tmp}/osmotetra-codec.XXXXXX")"
	# shellcheck disable=SC2064  # $work va espanso adesso, non all'uscita
	trap "rm -rf '$work'" RETURN

	log_info "Estraggo e applico la patch..."
	# -L: i sorgenti ETSI hanno nomi di file in maiuscolo misto e la patch
	# di sq5bpf si aspetta i nomi in minuscolo.
	( cd "$work" && unzip -qq -L "$ZIPFILE" ) || { log_error "unzip fallito"; return 1; }
	( cd "$work" && patch -p1 -N -E --silent < "$PATCHDIR/codec.diff" ) \
		|| { log_error "applicazione di codec.diff fallita"; return 1; }

	log_info "Compilo il codec..."
	if ! make -C "$work/c-code" > "$work/build.log" 2>&1; then
		log_error "Compilazione del codec fallita."
		tail -25 "$work/build.log" >&2
		return 1
	fi

	mkdir -p "$INSTALLDIR"
	local b
	for b in "${CODEC_BINARIES[@]}"; do
		if [ ! -x "$work/c-code/$b" ]; then
			log_error "$b non prodotto dalla compilazione"
			return 1
		fi
		install -m 755 "$work/c-code/$b" "$INSTALLDIR/$b"
	done
	log_ok "Codec installato in $INSTALLDIR"
}

main() {
	log_step "Codec vocale ACELP (opzionale)"

	if already_installed; then
		log_ok "Codec già installato in $INSTALLDIR"
		return 0
	fi

	if [ "${DRY_RUN:-0}" = "1" ]; then
		log_info "[dry-run] scarico, verifico, compilo e installo il codec in $INSTALLDIR"
		return 0
	fi

	require_cmd unzip
	require_cmd patch
	require_cmd wget
	require_cmd make

	# La patch arriva dal repo di sq5bpf, non dal sito ETSI.
	clone_or_update "$CODEC_PATCH_URL" "$PATCHDIR"
	[ -f "$PATCHDIR/codec.diff" ] || { log_error "codec.diff non trovato in $PATCHDIR"; return 1; }

	fetch_zip   || return 1
	verify_zip  || return 1
	build_and_install || return 1

	log_info "L'audio in tempo reale e la registrazione sono ora disponibili."
}

main "$@"
