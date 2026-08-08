#!/bin/bash
# lib_common.sh - funzioni condivise dagli script di installazione di OsmoTetraUbuntu
#
# Questo file va sorgente-ato, non eseguito:  . scripts/lib_common.sh
#
# SPDX-License-Identifier: GPL-3.0-or-later

# --- output ---------------------------------------------------------------

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
	C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
	C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
	C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""
fi

log_step()  { printf '\n%s==>%s %s%s%s\n' "$C_BLUE" "$C_RESET" "$C_BOLD" "$*" "$C_RESET"; }
log_info()  { printf '    %s\n' "$*"; }
log_ok()    { printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
log_warn()  { printf '    %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
log_error() { printf '%sERRORE:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
die()       { log_error "$*"; exit 1; }

# Esegue un comando, oppure lo stampa soltanto se DRY_RUN=1.
run() {
	if [ "${DRY_RUN:-0}" = "1" ]; then
		printf '    %s[dry-run]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"
		return 0
	fi
	"$@"
}

# Come run(), ma per comandi che vanno passati alla shell (pipe, redirezioni).
run_sh() {
	if [ "${DRY_RUN:-0}" = "1" ]; then
		printf '    %s[dry-run]%s sh -c %q\n' "$C_YELLOW" "$C_RESET" "$1"
		return 0
	fi
	bash -c "$1"
}

# --- controlli ------------------------------------------------------------

have_cmd() { command -v "$1" >/dev/null 2>&1; }

require_cmd() {
	have_cmd "$1" || die "comando '$1' non trovato. Installalo e riprova (di solito: sudo apt-get install ${2:-$1})"
}

# Legge un campo da /etc/os-release
osr() { ( . /etc/os-release 2>/dev/null; eval "printf '%s' \"\$$1\"" ); }

# Rifiuta l'esecuzione come root: i sorgenti e la config vanno nella home
# dell'utente, e telive stesso non va eseguito da root.
refuse_root() {
	if [ "$(id -u)" = "0" ] && [ "${OSMOTETRA_ALLOW_ROOT:-0}" != "1" ]; then
		log_error "Non eseguire questo script come root."
		log_info  "Va lanciato come utente normale; userà sudo solo per apt e udev."
		log_info  "(Per forzare — ad esempio dentro un container — esporta OSMOTETRA_ALLOW_ROOT=1.)"
		exit 1
	fi
}

# Verifica che la distribuzione sia Ubuntu (o derivata) 24.04 o successiva.
require_ubuntu_2404() {
	[ -f /etc/os-release ] || die "/etc/os-release assente: distribuzione non riconoscibile."
	local id id_like ver major minor
	id="$(osr ID)"; id_like="$(osr ID_LIKE)"; ver="$(osr VERSION_ID)"
	case "$id:$id_like" in
		ubuntu:*|*:*ubuntu*|linuxmint:*|pop:*|neon:*|zorin:*|elementary:*) ;;
		debian:*|*:*debian*)
			log_warn "Distribuzione Debian rilevata ($id $ver): non è il target ufficiale, procedo comunque."
			return 0 ;;
		*)
			log_warn "Distribuzione non riconosciuta ($id $ver). Procedo, ma i nomi dei pacchetti potrebbero non corrispondere."
			return 0 ;;
	esac
	major="${ver%%.*}"; minor="${ver#*.}"; minor="${minor%%.*}"
	if [ -z "$major" ] || ! [ "$major" -ge 24 ] 2>/dev/null; then
		die "Serve Ubuntu 24.04 o successiva (trovata: ${ver:-sconosciuta})."
	fi
	if [ "$major" = "24" ] && [ -n "$minor" ] && [ "$minor" -lt 4 ] 2>/dev/null; then
		die "Serve Ubuntu 24.04 o successiva (trovata: $ver)."
	fi
	log_ok "Distribuzione: $(osr PRETTY_NAME)"
}

# Verifica che sudo sia utilizzabile (a meno che non siamo già root).
require_sudo() {
	if [ "$(id -u)" = "0" ]; then SUDO=""; return 0; fi
	have_cmd sudo || die "sudo non installato. Installalo (da root: apt-get install sudo) e riprova."
	log_info "Verifica di sudo (potrebbe essere richiesta la password)..."
	if [ "${DRY_RUN:-0}" = "1" ]; then SUDO="sudo"; return 0; fi
	sudo -v >/dev/null 2>&1 || die "sudo non utilizzabile da questo utente."
	SUDO="sudo"
}

# --- rete -----------------------------------------------------------------

# Riprova un comando con backoff esponenziale: retry <tentativi> <cmd...>
retry() {
	local tries="$1"; shift
	local n=1 delay=2
	while true; do
		if "$@"; then return 0; fi
		if [ "$n" -ge "$tries" ]; then
			log_error "comando fallito dopo $tries tentativi: $*"
			return 1
		fi
		log_warn "tentativo $n/$tries fallito, riprovo fra ${delay}s..."
		sleep "$delay"
		n=$((n + 1)); delay=$((delay * 2))
	done
}

# Clona il repository se assente, altrimenti aggiorna al ramo di default.
# clone_or_update <url> <dest>
clone_or_update() {
	local url="$1" dest="$2" name
	name="$(basename "$dest")"
	if [ -d "$dest/.git" ]; then
		local origin
		origin="$(git -C "$dest" remote get-url origin 2>/dev/null || true)"
		if [ "${origin%.git}" != "${url%.git}" ]; then
			log_warn "$dest esiste ma punta a '$origin' invece di '$url'. Lo lascio com'è."
			return 0
		fi
		log_info "Aggiorno $name..."
		if [ "${DRY_RUN:-0}" = "1" ]; then
			printf '    %s[dry-run]%s git -C %s pull --ff-only\n' "$C_YELLOW" "$C_RESET" "$dest"
			return 0
		fi
		# Un pull fallito (modifiche locali, rete) non deve interrompere
		# l'installazione: i sorgenti già presenti restano utilizzabili.
		if retry 4 git -C "$dest" pull --ff-only --quiet; then
			log_ok "$name aggiornato"
		else
			log_warn "Impossibile aggiornare $name: uso la copia locale esistente."
		fi
	elif [ -e "$dest" ]; then
		die "$dest esiste ma non è un repository git. Rimuovilo o usa --prefix diverso."
	else
		log_info "Clono $name da $url..."
		run mkdir -p "$(dirname "$dest")"
		if [ "${DRY_RUN:-0}" = "1" ]; then
			printf '    %s[dry-run]%s git clone %s %s\n' "$C_YELLOW" "$C_RESET" "$url" "$dest"
			return 0
		fi
		retry 4 git clone --quiet "$url" "$dest" || die "clone di $url fallito"
		log_ok "$name clonato"
	fi
}

# --- compilatore ----------------------------------------------------------

# I sorgenti upstream sono del 2011-2015 e contengono costrutti che GCC 14+
# (Ubuntu 25.04 in poi) rifiuta di default invece di segnalare come warning:
# dichiarazioni implicite di funzione, int impliciti, conversioni di puntatore
# incompatibili, return senza valore. Su GCC 13 (Ubuntu 24.04) sono già solo
# warning, quindi questi flag sono innocui lì e indispensabili più avanti.
#
# Vengono applicati via CC (non via CFLAGS) perché i Makefile upstream
# assegnano CFLAGS internamente con valori che non vogliamo perdere
# (pkg-config, -I., -fcommon), mentre CC è usato sia in compilazione sia in
# link e può essere sovrascritto da riga di comando.
#
# Attenzione: alcuni di questi nomi di warning esistono solo da GCC 14
# (-Wreturn-mismatch, -Wdeclaration-missing-parameter-type) e GCC 13 li
# rifiuta con un errore. Ogni flag va quindi provato sul compilatore in uso.
LEGACY_C_FLAGS_CACHE=""
legacy_c_flags() {
	if [ -n "$LEGACY_C_FLAGS_CACHE" ]; then
		printf '%s' "$LEGACY_C_FLAGS_CACHE"
		return 0
	fi
	local cc="${CC:-gcc}" probe out="" f
	local tmp; tmp="$(mktemp -d)"
	printf 'int main(void){return 0;}\n' > "$tmp/probe.c"
	for f in -Wno-error=implicit-function-declaration \
	         -Wno-error=implicit-int \
	         -Wno-error=int-conversion \
	         -Wno-error=incompatible-pointer-types \
	         -Wno-error=return-mismatch \
	         -Wno-error=declaration-missing-parameter-type; do
		if "$cc" $f -c "$tmp/probe.c" -o "$tmp/probe.o" >/dev/null 2>&1; then
			out="${out:+$out }$f"
		fi
	done
	rm -rf "$tmp"
	LEGACY_C_FLAGS_CACHE="$out"
	printf '%s' "$out"
}
