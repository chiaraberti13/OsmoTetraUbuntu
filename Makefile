# OsmoTetraUbuntu
#
# Il vero lavoro lo fa ./install.sh: questo Makefile è una comodità per chi
# preferisce 'make install' e per far girare i controlli.
#
# SPDX-License-Identifier: GPL-3.0-or-later

PYTHON ?= python3
PREFIX ?= $(HOME)/.local/share/osmotetra

SHELL_SCRIPTS := install.sh uninstall.sh $(wildcard scripts/*.sh)
PY_SOURCES    := $(wildcard osmotetra/*.py osmotetra/ui/*.py gnuradio/*.py)

.PHONY: help install install-codec uninstall purge check test lint clean

help:
	@echo "Obiettivi disponibili:"
	@echo "  make install        installa l'applicazione e le dipendenze"
	@echo "  make install-codec  installa anche il codec vocale ACELP (ETSI)"
	@echo "  make uninstall      rimuove l'applicazione, conserva dati e config"
	@echo "  make purge          rimuove tutto, dati e configurazione compresi"
	@echo "  make check          verifica le dipendenze del sistema"
	@echo "  make test           esegue il collaudo interno"
	@echo "  make lint           controlla la sintassi di script e sorgenti"
	@echo ""
	@echo "Variabili: PREFIX=$(PREFIX)  PYTHON=$(PYTHON)"

install:
	./install.sh --prefix "$(PREFIX)"

install-codec:
	./install.sh --prefix "$(PREFIX)" --with-codec

uninstall:
	./uninstall.sh --prefix "$(PREFIX)"

purge:
	./uninstall.sh --prefix "$(PREFIX)" --purge

check:
	OSMOTETRA_PREFIX="$(PREFIX)" $(PYTHON) -m osmotetra check

# QT_QPA_PLATFORM=offscreen permette di collaudare anche la GUI senza schermo.
test:
	OSMOTETRA_PREFIX="$(PREFIX)" QT_QPA_PLATFORM=offscreen \
		$(PYTHON) -m osmotetra self-test

lint:
	@echo "== sintassi degli script shell =="
	@for f in $(SHELL_SCRIPTS) scripts/templates/*.in; do \
		bash -n "$$f" && echo "  ok  $$f" || exit 1; \
	done
	@echo "== sintassi dei sorgenti Python =="
	@$(PYTHON) -m py_compile $(PY_SOURCES) && echo "  ok  $(words $(PY_SOURCES)) file"
	@echo "== validazione del file .desktop =="
	@if command -v desktop-file-validate >/dev/null 2>&1; then \
		sed 's|@BINDIR@|/usr/bin|g' packaging/osmotetra.desktop > /tmp/osmotetra-lint.desktop && \
		desktop-file-validate /tmp/osmotetra-lint.desktop && echo "  ok  osmotetra.desktop"; \
		rm -f /tmp/osmotetra-lint.desktop; \
	else \
		echo "  (desktop-file-validate non installato, salto)"; \
	fi

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete
