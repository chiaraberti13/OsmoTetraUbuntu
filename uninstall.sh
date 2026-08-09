#!/usr/bin/env bash
# ============================================================================
#  uninstall.sh — rimuove OsmoTetra
# ============================================================================
#  Di default conserva registrazioni e log in /tetra. Usa --purge per togliere
#  tutto, compresi i sorgenti e /tetra.
# ============================================================================
set -euo pipefail

OSMOTETRA_HOME="${OSMOTETRA_HOME:-$HOME/telive2}"
BIN="$HOME/.local/bin/osmotetra"
DESKTOP="$HOME/.local/share/applications/osmotetra.desktop"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

echo "Rimozione di OsmoTetra…"
rm -f "$BIN" "$DESKTOP"
update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
echo "  -> lanciatore e voce di menu rimossi"

if [ "$PURGE" -eq 1 ]; then
  rm -rf "$OSMOTETRA_HOME"
  echo "  -> sorgenti e log rimossi ($OSMOTETRA_HOME)"
  if [ -d /tetra ]; then
    sudo rm -rf /tetra && echo "  -> /tetra rimossa (registrazioni e log)"
  fi
  # togli la riga di PATH aggiunta a ~/.bashrc
  sed -i '/# OsmoTetra: decoder vocali TETRA/,+1d' "$HOME/.bashrc" 2>/dev/null || true
else
  echo "  Conservati (usa --purge per rimuoverli):"
  echo "    sorgenti e log: $OSMOTETRA_HOME"
  echo "    registrazioni e log TETRA: /tetra"
fi

echo "I pacchetti apt non vengono rimossi. Per toglierli:"
echo "  sudo apt-get autoremove gnuradio gr-osmosdr libosmocore-dev python3-pyqt5"
