#!/bin/bash
# install.sh - installazione di OsmoTetraUbuntu su Ubuntu 24.04 e successive
#
# Idempotente: si può rilanciare per aggiornare i sorgenti upstream e
# ricompilare. Va eseguito come utente normale; usa sudo solo per apt e udev.
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
DRY_RUN=0
SKIP_APT=0
SKIP_UDEV=0
WITH_CODEC=0

usage() {
	cat <<EOF
Uso: ./install.sh [opzioni]

  --prefix DIR    directory di installazione (default: $HOME/.local/share/osmotetra)
  --with-codec    tenta anche l'installazione del codec vocale ACELP da ETSI
  --skip-apt      non installare i pacchetti di sistema
  --skip-udev     non toccare udev / moduli kernel
  --dry-run       mostra le azioni senza eseguirle
  -h, --help      questo messaggio

Variabili d'ambiente riconosciute: PREFIX, BINDIR, APPDIR, ICONDIR,
OSMO_TETRA_URL, TELIVE_URL, CODEC_URL.
EOF
}

parse_args() {
	while [ $# -gt 0 ]; do
		case "$1" in
			--prefix)     PREFIX="${2:?--prefix richiede un argomento}"; shift 2 ;;
			--prefix=*)   PREFIX="${1#*=}"; shift ;;
			--with-codec) WITH_CODEC=1; shift ;;
			--skip-apt)   SKIP_APT=1; shift ;;
			--skip-udev)  SKIP_UDEV=1; shift ;;
			--dry-run)    DRY_RUN=1; shift ;;
			-h|--help)    usage; exit 0 ;;
			*)            log_error "opzione sconosciuta: $1"; usage >&2; exit 2 ;;
		esac
	done
	export PREFIX DRY_RUN
}

install_python_app() {
	log_step "Applicazione OsmoTetra"

	local libdir="$PREFIX/lib"
	run mkdir -p "$libdir" "$BINDIR"

	if [ "$DRY_RUN" = "1" ]; then
		log_info "[dry-run] copio osmotetra/ e gnuradio/ in $libdir"
		log_info "[dry-run] creo il launcher $BINDIR/osmotetra"
		return 0
	fi

	# Copia invece di symlink: così l'app continua a funzionare anche se la
	# copia di lavoro del repository viene spostata o cancellata.
	rm -rf "$libdir/osmotetra" "$libdir/gnuradio"
	cp -r "$REPO/osmotetra" "$libdir/osmotetra"
	cp -r "$REPO/gnuradio"  "$libdir/gnuradio"
	cp -r "$REPO/scripts"   "$libdir/scripts"
	cp -r "$REPO/patches"   "$libdir/patches"
	find "$libdir" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	chmod 755 "$libdir/gnuradio/osmotetra_rx.py" "$libdir"/scripts/*.sh 2>/dev/null || true

	cat > "$BINDIR/osmotetra" <<EOF
#!/bin/sh
# Launcher generato da OsmoTetraUbuntu — non modificare a mano.
OSMOTETRA_PREFIX="$PREFIX"
export OSMOTETRA_PREFIX
PYTHONPATH="$libdir\${PYTHONPATH:+:\$PYTHONPATH}"
export PYTHONPATH

# Su una Ubuntu 24.04 standard 'python3' va benissimo. Ma se sulla macchina
# convive un altro Python (pyenv, conda, una build da sorgente) che occupa il
# PATH, quello non ha i moduli di sistema e l'interfaccia non parte. Si
# sceglie quindi il primo interprete capace di importare PyQt5.
# OSMOTETRA_PYTHON, se impostata, ha comunque la precedenza.
for candidate in "\$OSMOTETRA_PYTHON" python3 /usr/bin/python3 \\
                 /usr/bin/python3.13 /usr/bin/python3.12; do
    [ -n "\$candidate" ] || continue
    command -v "\$candidate" >/dev/null 2>&1 || continue
    if "\$candidate" -c 'import PyQt5' >/dev/null 2>&1; then
        exec "\$candidate" -m osmotetra "\$@"
    fi
done

# Nessun interprete con PyQt5: i sottocomandi testuali funzionano lo stesso e
# il messaggio d'errore della GUI spiega cosa installare.
exec python3 -m osmotetra "\$@"
EOF
	chmod 755 "$BINDIR/osmotetra"
	log_ok "Applicazione installata in $libdir"
	log_ok "Launcher: $BINDIR/osmotetra"

	warn_if_not_in_path
}

# Avvisa se il launcher non è raggiungibile, spiegando la causa giusta.
#
# Su Ubuntu il ~/.profile predefinito contiene già:
#
#     if [ -d "$HOME/.local/bin" ] ; then PATH="$HOME/.local/bin:$PATH" ; fi
#
# ma viene valutato al login. Se la directory non esisteva quando l'utente ha
# fatto l'accesso — cioè quasi sempre, alla prima installazione — il PATH non
# la contiene, e non la conterrà finché non si rientra. Suggerire di
# "aggiungerlo a ~/.profile" sarebbe quindi un consiglio sbagliato: la riga
# c'è già, e aggiungerne una seconda non risolve la sessione in corso.
warn_if_not_in_path() {
	case ":$PATH:" in
		*":$BINDIR:"*) return 0 ;;
	esac

	log_warn "$BINDIR non è ancora nel PATH di questa sessione."

	if [ -f "$HOME/.profile" ] && grep -q '\.local/bin' "$HOME/.profile" 2>/dev/null; then
		log_info "Il tuo ~/.profile lo aggiunge già al login, ma la directory è"
		log_info "stata creata adesso: basta uscire e rientrare."
	else
		log_info "Per renderlo permanente:"
		log_info "  echo 'export PATH=\"\$PATH:$BINDIR\"' >> ~/.profile"
	fi

	log_info "Per usarlo subito, senza uscire dalla sessione:"
	log_info "  export PATH=\"\$PATH:$BINDIR\""
	log_info "Oppure avvia l'applicazione dal menu, o con il percorso completo:"
	log_info "  $BINDIR/osmotetra"
}

install_desktop_entry() {
	log_step "Integrazione desktop"
	run mkdir -p "$APPDIR" "$ICONDIR"

	if [ "$DRY_RUN" = "1" ]; then
		log_info "[dry-run] installo osmotetra.desktop e l'icona"
		return 0
	fi

	install -m 644 "$REPO/packaging/osmotetra.svg" "$ICONDIR/osmotetra.svg"
	sed -e "s|@BINDIR@|$BINDIR|g" "$REPO/packaging/osmotetra.desktop" \
		> "$APPDIR/osmotetra.desktop"
	chmod 644 "$APPDIR/osmotetra.desktop"

	have_cmd update-desktop-database && update-desktop-database "$APPDIR" 2>/dev/null || true
	have_cmd gtk-update-icon-cache && gtk-update-icon-cache -qtf "${ICONDIR%/scalable/apps}" 2>/dev/null || true
	log_ok "Voce di menu «OsmoTetra» installata"
}

write_install_manifest() {
	[ "$DRY_RUN" = "1" ] && return 0
	cat > "$PREFIX/install-manifest" <<EOF
# Generato da install.sh il $(date -Is)
PREFIX=$PREFIX
BINDIR=$BINDIR
APPDIR=$APPDIR
ICONDIR=$ICONDIR
REPO=$REPO
EOF
}

final_report() {
	log_step "Fatto"
	echo
	log_info "Avvia l'applicazione dal menu («OsmoTetra») oppure con:"
	printf '        %sosmotetra%s\n' "$C_BOLD" "$C_RESET"
	echo
	log_info "Prima di collegare la radio, controlla le dipendenze con:"
	printf '        %sosmotetra check%s\n' "$C_BOLD" "$C_RESET"
	echo
	if [ "$WITH_CODEC" = "0" ]; then
		log_info "Il codec vocale ACELP non è stato installato: segnalazione, SDS, log e"
		log_info "KML funzionano comunque, manca solo l'audio. Per aggiungerlo:"
		printf '        %s./install.sh --with-codec%s\n' "$C_BOLD" "$C_RESET"
		echo
	fi
	log_info "Il manuale di telive (indispensabile per l'interfaccia ncurses) è in:"
	log_info "  $PREFIX/src/telive/telive_doc.pdf"
}

main() {
	parse_args "$@"

	printf '%s%sOsmoTetraUbuntu%s — installazione\n' "$C_BOLD" "$C_BLUE" "$C_RESET"
	[ "$DRY_RUN" = "1" ] && log_warn "modalità dry-run: nessuna modifica al sistema"

	refuse_root
	require_ubuntu_2404
	require_cmd git
	log_info "Prefix: $PREFIX"

	run mkdir -p "$PREFIX/src"

	if [ "$SKIP_APT" = "1" ]; then
		log_step "Pacchetti di sistema"
		log_info "saltati (--skip-apt)"
	else
		"$REPO/scripts/10_apt_deps.sh" || die "installazione dei pacchetti fallita"
	fi

	"$REPO/scripts/20_build_osmo_tetra.sh" || die "build di osmo-tetra-sq5bpf fallita"
	"$REPO/scripts/30_build_telive.sh"     || die "build di telive fallita"

	install_python_app
	install_desktop_entry

	if [ "$SKIP_UDEV" = "1" ]; then
		log_step "Configurazione SDR"
		log_info "saltata (--skip-udev)"
	else
		"$REPO/scripts/50_sdr_udev.sh" || log_warn "configurazione SDR incompleta, proseguo"
	fi

	if [ "$WITH_CODEC" = "1" ]; then
		# Il codec è opzionale: un fallimento qui non compromette il resto.
		"$REPO/scripts/40_install_codec.sh" || log_warn "codec vocale non installato, proseguo"
	fi

	write_install_manifest
	final_report
}

main "$@"
