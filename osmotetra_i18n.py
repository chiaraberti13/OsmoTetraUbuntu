#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OsmoTetra — lingua del pannello (italiano/inglese).

Nessuna dipendenza da PyQt: la usano sia il pannello sia il flowgraph
headless, così i loro messaggi restano coerenti. Il testo sorgente del
resto del programma è in italiano; ``_()`` lo traduce in inglese quando
la lingua attiva è "en", e lo lascia invariato altrimenti (e per
qualunque stringa dinamica non presente nel dizionario: non si rompe
mai, nel peggiore dei casi resta in italiano).

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "osmotetra"
SETTINGS_FILE = CONFIG_DIR / "impostazioni.json"


def _detect_lang() -> str:
    env = os.environ.get("OSMOTETRA_LANG", "").strip().lower()
    if env in ("it", "en"):
        return env
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        lang = data.get("lang")
        if lang in ("it", "en"):
            return lang
    except (OSError, ValueError):
        pass
    return "it"


#: lingua attiva per questo processo, decisa una volta sola all'avvio
#: (variabile d'ambiente OSMOTETRA_LANG, poi il file di impostazioni, poi italiano).
LANG = _detect_lang()


def set_lang(lang: str) -> None:
    """Salva la lingua scelta su disco (letta al prossimo avvio)."""
    global LANG
    LANG = lang
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        data["lang"] = lang
        SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _(text: str) -> str:
    """Traduce ``text`` in inglese se LANG=="en", altrimenti lo lascia com'è."""
    if LANG == "en":
        return EN.get(text, text)
    return text


#: italiano -> inglese. Le voci con "{...}" sono template: si traducono
#: prima, poi si applica .format(...) sul risultato.
EN: dict[str, str] = {
    # -- finestre e titoli --------------------------------------------------
    "OsmoTetra — ricevitore TETRA": "OsmoTetra — TETRA receiver",
    "OsmoTetra — chiavi di decifratura": "OsmoTetra — decryption keys",
    "OsmoTetra — spettro e parametri": "OsmoTetra — spectrum and parameters",
    "OsmoTetra": "OsmoTetra",
    "Imposta i parametri e premi «Avvia»: si apre telive.":
        "Set the parameters and press «Start»: telive opens.",

    # -- Sintonia -------------------------------------------------------
    "Sintonia": "Tuning",
    "Frequenza del canale:": "Channel frequency:",
    "Guadagno RF:": "RF gain:",
    "Sorgente SDR:": "SDR source:",
    "Indirizzo remoto:": "Remote address:",
    "Correzione (ppm):": "Correction (ppm):",
    "Dispositivo (manuale):": "Device (manual):",
    "IP": "IP",
    "porta": "port",
    "Chiavetta locale (USB)": "Local dongle (USB)",
    "Chiavetta remota (rete / VM)": "Remote dongle (network / VM)",
    "Mostra la finestra dello spettro (grafici + controlli)":
        "Show the spectrum window (plots + controls)",
    "vuoto = usa la selezione qui sopra": "empty = use the selection above",
    "Chiavetta USB (rilevamento automatico)": "USB dongle (auto-detect)",
    "Chiavetta USB — prima (rtl=0)": "USB dongle — first (rtl=0)",
    "Chiavetta USB — seconda (rtl=1)": "USB dongle — second (rtl=1)",
    "Chiavetta via rete (rtl_tcp=127.0.0.1:1234)": "Dongle over the network (rtl_tcp=127.0.0.1:1234)",
    "⚠ {mhz:.4f} MHz non è sul reticolo dei canali TETRA (25 kHz): "
    "sei a {off:.1f} kHz dal canale più vicino, <b>{near:.4f} MHz</b>. "
    "Se non decodifichi, prova quello.":
        "⚠ {mhz:.4f} MHz is not on the TETRA channel raster (25 kHz): "
        "you're {off:.1f} kHz from the nearest channel, <b>{near:.4f} MHz</b>. "
        "If you don't decode, try that one.",

    # -- modalità / lingua ---------------------------------------------
    "Modalità:": "Mode:",
    "Base": "Basic",
    "Avanzata": "Advanced",
    "Lingua:": "Language:",
    "Italiano": "Italiano",
    "English": "English",
    "Cambio lingua": "Change language",
    "Cambio a {lang}: l'applicazione si riavvia per applicarlo.\n"
    "Se la ricezione è in corso, viene fermata prima.\n\nProcedo?":
        "Switching to {lang}: the application restarts to apply it.\n"
        "If reception is running, it is stopped first.\n\nProceed?",

    # -- pulsanti principali ----------------------------------------------
    "▶  Avvia": "▶  Start",
    "■  Ferma": "■  Stop",
    "🔑  Chiavi di decifratura…": "🔑  Decryption keys…",
    "Fermo": "Stopped",
    "Avvio in corso…": "Starting…",
    "In esecuzione — guarda la finestra di telive": "Running — watch the telive window",

    # -- schede -------------------------------------------------------------
    "Ricezione": "Reception",
    "Stato": "Status",
    "Rete": "Network",
    "Chiavi": "Keys",
    "Log": "Log",
    "Avanzate": "Advanced",

    # -- scheda Ricezione: profili ------------------------------------------
    "Profili": "Profiles",
    "Un profilo ricorda frequenza, guadagno, sorgente SDR e le altre "
    "impostazioni di questa scheda. Non contiene mai chiavi.":
        "A profile remembers frequency, gain, SDR source and this tab's other "
        "settings. It never contains keys.",
    "Salva come…": "Save as…",
    "Elimina": "Delete",
    "— nessun profilo —": "— no profile —",
    "Suggerimento: salva un profilo per ogni rete che ascolti, così "
    "ritrovi i valori giusti con un clic.":
        "Tip: save a profile for each network you listen to, so you can get "
        "the right values back with one click.",
    "Salva profilo": "Save profile",
    "Nome del profilo:": "Profile name:",
    "Nessun profilo": "No profile",
    "Scegli prima un profilo dall'elenco.": "Pick a profile from the list first.",
    "Elimino?": "Delete it?",
    "Elimino il profilo «{name}»?": "Delete the profile «{name}»?",

    # -- scheda Stato ---------------------------------------------------
    "Passa il mouse su una riga per la spiegazione. <b>✓</b> a posto, "
    "<b>!</b> c'è qualcosa da sistemare, <b>·</b> non ancora noto.":
        "Hover a row for the explanation. <b>✓</b> all good, "
        "<b>!</b> something to fix, <b>·</b> not known yet.",
    "Ricevitore SDR": "SDR receiver",
    "La radio è aperta e il flowgraph sta girando.": "The radio is open and the flowgraph is running.",
    "Segnale in arrivo": "Incoming signal",
    "Il decoder riceve campioni e misura lo scostamento di frequenza (AFC). "
    "Se resta spento: frequenza sbagliata, guadagno troppo basso o antenna scollegata.":
        "The decoder is receiving samples and measuring the frequency offset (AFC). "
        "If it stays off: wrong frequency, gain too low, or antenna disconnected.",
    "Sincronizzazione TETRA": "TETRA sync",
    "Il decoder ha agganciato la struttura delle trame TETRA e legge i "
    "messaggi di rete. È il segno che sei davvero su un canale di controllo.":
        "The decoder has locked onto the TETRA frame structure and reads "
        "network messages. It's the sign you're really on a control channel.",
    "Rete rilevata": "Network detected",
    "MCC (Paese), MNC (operatore), CC (codice colore) e LA (area) letti "
    "dai messaggi di rete della cella.":
        "MCC (country), MNC (operator), CC (colour code) and LA (area) read "
        "from the cell's network messages.",
    "Traffico cifrato": "Encrypted traffic",
    "Via etere TETRA segnala SE il traffico è cifrato, non QUALE algoritmo. "
    "L'algoritmo (TEA1…TEA7) lo scegli tu nell'editor delle chiavi.":
        "Over the air TETRA signals WHETHER traffic is encrypted, not WHICH algorithm. "
        "The algorithm (TEA1…TEA7) is the one you pick in the key editor.",
    "Chiavi configurate": "Configured keys",
    "Quante chiavi contiene il keyfile e per quale rete: serve solo per "
    "decifrare traffico che sei autorizzato a decifrare.":
        "How many keys the keyfile holds and for which network: only used to "
        "decrypt traffic you are authorized to decrypt.",
    "catena ferma": "chain stopped",
    "radio aperta, flowgraph attivo": "radio open, flowgraph running",
    "il decoder riceve campioni": "the decoder is receiving samples",
    "nessun campione: controlla frequenza, guadagno e antenna":
        "no samples: check frequency, gain and antenna",
    "agganciato al canale di controllo": "locked onto the control channel",
    "non agganciato: sei forse su un canale che non è di controllo":
        "not locked: you might be on a channel that isn't the control channel",
    "nessuna rete letta finora": "no network read so far",
    "sì — l'aria dice solo CHE è cifrato, non con quale algoritmo":
        "yes — the air only says THAT it's encrypted, not with which algorithm",
    "no, traffico in chiaro": "no, traffic in the clear",
    "non ancora determinato": "not determined yet",
    "nessuna — servono solo per decifrare, apri «Chiavi»":
        "none — only used to decrypt, open «Keys»",
    "{n} per MCC {mcc} / MNC {mnc} · algoritmo scelto: {algo}":
        "{n} for MCC {mcc} / MNC {mnc} · algorithm chosen: {algo}",

    # -- scheda Rete ---------------------------------------------------
    "Rete TETRA rilevata": "TETRA network detected",
    "MCC (Paese)": "MCC (Country)",
    "Mobile Country Code: identifica il Paese della rete. 222 = Italia. "
    "Nel keyfile va scritto a 4 cifre (222 → 0222).":
        "Mobile Country Code: identifies the network's country. 222 = Italy. "
        "In the keyfile it's written as 4 digits (222 → 0222).",
    "MNC (rete)": "MNC (network)",
    "Mobile Network Code: identifica la singola rete dentro il Paese. "
    "Anche questo va a 4 cifre nel keyfile.":
        "Mobile Network Code: identifies the single network within the country. "
        "This too is 4 digits in the keyfile.",
    "Codice colore (CC)": "Colour code (CC)",
    "Colour Code: distingue celle vicine che usano la stessa frequenza. "
    "Se cambia mentre ascolti, ti sei spostato su un'altra cella.":
        "Colour Code: tells apart nearby cells that reuse the same frequency. "
        "If it changes while you listen, you've moved onto another cell.",
    "Area di localizzazione (LA)": "Location area (LA)",
    "Location Area: il gruppo di celle in cui i terminali sono registrati.":
        "Location Area: the group of cells terminals are registered in.",
    "Frequenza di discesa": "Downlink frequency",
    "La frequenza del canale di controllo in discesa (dalla rete ai "
    "terminali): è quella che stai ascoltando.":
        "The downlink control-channel frequency (network to terminals): "
        "it's the one you're listening to.",
    "Cifratura": "Encryption",
    "Ultimo aggiornamento": "Last update",
    "Quando è arrivato l'ultimo messaggio di rete.": "When the last network message arrived.",
    "📋  Copia dettagli rete": "📋  Copy network details",
    "Copia i dati qui sopra negli appunti, come testo.": "Copies the data above to the clipboard, as text.",
    "I dati arrivano dai messaggi di rete della cella e compaiono solo "
    "quando la ricezione è agganciata.":
        "Data comes from the cell's network messages and only appears once "
        "reception is locked.",
    "sì (l'algoritmo non è deducibile dall'aria)":
        "yes (the algorithm can't be inferred from the air)",
    "Rete TETRA rilevata da OsmoTetra": "TETRA network detected by OsmoTetra",

    # -- scheda Chiavi ---------------------------------------------------
    "Chiavi di decifratura": "Decryption keys",
    "🔑  Apri l'editor delle chiavi…": "🔑  Open the key editor…",
    "File: {path}": "File: {path}",
    "⚠ La decifratura funziona <b>solo con chiavi che possiedi "
    "legittimamente</b> e non rompe alcuna cifratura. Via etere TETRA "
    "segnala <b>se</b> il traffico è cifrato, non <b>quale</b> algoritmo "
    "usa: l'algoritmo (TEA1…TEA7) lo scegli tu, in base a quello che sai "
    "della tua rete. Senza le chiavi giuste le chiamate cifrate restano "
    "mute — è normale.":
        "⚠ Decryption only works <b>with keys you legitimately own</b> "
        "and doesn't break any encryption. Over the air TETRA signals "
        "<b>whether</b> traffic is encrypted, not <b>which</b> algorithm it "
        "uses: the algorithm (TEA1…TEA7) is the one you pick, based on "
        "what you know about your network. Without the right keys, encrypted "
        "calls stay silent — that's expected.",
    "<b>{n}</b> chiave/i configurate per <b>MCC {mcc} / MNC {mnc}</b>, algoritmo "
    "scelto <b>{algo}</b>, classe di sicurezza {sec}.":
        "<b>{n}</b> key(s) configured for <b>MCC {mcc} / MNC {mnc}</b>, "
        "algorithm chosen <b>{algo}</b>, security class {sec}.",
    "Nessuna chiave configurata: sentirai <b>solo le chiamate in "
    "chiaro</b>. Apri l'editor per inserire le tue.":
        "No keys configured: you'll hear <b>only clear calls</b>. "
        "Open the editor to enter yours.",

    # -- scheda Log ---------------------------------------------------
    "Log tecnico (mostra tutto)": "Technical log (show everything)",
    "Spento: solo i messaggi che servono a te.\n"
    "Acceso: anche l'output grezzo di flowgraph e ricevitore, "
    "utile da allegare quando chiedi aiuto.":
        "Off: only the messages meant for you.\n"
        "On: also the raw output of flowgraph and receiver, "
        "handy to attach when you ask for help.",
    "💾  Esporta diagnostica…": "💾  Export diagnostics…",
    "Salva un file di testo con versioni, impostazioni, "
    "stato e log — senza alcuna chiave.":
        "Saves a text file with versions, settings, status and log — without any keys.",
    "Esporta diagnostica": "Export diagnostics",
    "File di testo (*.txt)": "Text file (*.txt)",
    "Diagnostica salvata": "Diagnostics saved",
    "Salvata in:\n{path}\n\nContiene versioni, impostazioni, stato e log "
    "(con le chiavi rimosse). Puoi allegarla quando chiedi aiuto.":
        "Saved to:\n{path}\n\nContains versions, settings, status and log "
        "(with keys removed). You can attach it when you ask for help.",

    # -- scheda Avanzate ---------------------------------------------------
    "Parametri tecnici": "Technical parameters",
    "Il campo «Dispositivo» accetta una stringa gr-osmosdr "
    "(<code>rtl=0</code>, <code>hackrf=0</code>, "
    "<code>rtl_tcp=IP:porta</code>). Se lo lasci vuoto vale la scelta "
    "fatta in «Sorgente SDR».":
        "The «Device» field accepts a gr-osmosdr string "
        "(<code>rtl=0</code>, <code>hackrf=0</code>, "
        "<code>rtl_tcp=IP:port</code>). Leave it empty to use the choice "
        "made in «SDR source».",
    "Dove sono le cose": "Where things are",
    "Sorgenti e binari:": "Sources and binaries:",
    "Decoder (osmo-tetra):": "Decoder (osmo-tetra):",
    "Monitor (telive):": "Monitor (telive):",
    "Keyfile:": "Keyfile:",
    "Interprete GNU Radio:": "GNU Radio interpreter:",
    "Porte:": "Ports:",

    # -- messaggi dell'editor delle chiavi ------------------------------
    "Compila i campi e premi <b>Salva</b>: l'editor scrive il keyfile che "
    "usa il decoder, senza doverlo modificare a mano.<br>⚠ Funziona <b>solo "
    "con chiavi che possiedi legittimamente</b>. Non rompe alcuna cifratura.":
        "Fill in the fields and press <b>Save</b>: the editor writes the "
        "keyfile the decoder uses, without having to edit it by hand.<br>"
        "⚠ Only works <b>with keys you legitimately own</b>. It doesn't "
        "break any encryption.",
    "es. 222": "e.g. 222",
    "es. 55": "e.g. 55",
    "Algoritmo (ksg_type):": "Algorithm (ksg_type):",
    "Classe di sicurezza:": "Security class:",
    "↧  Usa rete rilevata": "↧  Use detected network",
    "↧  Usa rete rilevata  (MCC {mcc} / MNC {mnc})": "↧  Use detected network  (MCC {mcc} / MNC {mnc})",
    "Copia qui MCC e MNC letti dal segnale, completati a 4 cifre.":
        "Copies MCC and MNC read from the signal here, padded to 4 digits.",
    "Disponibile dopo che la ricezione ha agganciato una rete: "
    "avvia OsmoTetra, attendi «Rete rilevata» nel pannello Stato, "
    "poi riapri questa finestra.":
        "Available once reception has locked onto a network: "
        "start OsmoTetra, wait for «Network detected» in the Status "
        "panel, then reopen this window.",
    "MCC/MNC vengono completati a 4 cifre (222 → 0222).":
        "MCC/MNC are padded to 4 digits (222 → 0222).",
    "Tipo di chiave": "Key type",
    "Chiave (80 bit hex)": "Key (80-bit hex)",
    "addr": "addr",
    "key_num": "key_num",
    "+ Aggiungi chiave": "+ Add key",
    "− Rimuovi selezionata": "− Remove selected",
    "Mostra chiavi": "Show keys",
    "Parametri avanzati  ▼": "Advanced parameters  ▼",
    "Mostra addr, key_num e MCC/MNC specifici per singola chiave":
        "Shows addr, key_num and per-key MCC/MNC",
    "<b>Tipo di chiave</b>: di solito <b>1</b> (CCK/SCK), oppure <b>16</b> per "
    "una chiave TEA1 accorciata a 32 bit (8 cifre) da riempire con zeri fino a "
    "20 cifre (80 bit). La <b>chiave</b> è esadecimale: 20 cifre = 80 bit.":
        "<b>Key type</b>: usually <b>1</b> (CCK/SCK), or <b>16</b> for a "
        "32-bit shortened TEA1 key (8 digits) padded with zeros up to 20 "
        "digits (80 bit). The <b>key</b> is hex: 20 digits = 80 bit.",
    "Chiavi": "Keys",
    "20 cifre esadecimali": "20 hex digits",
    "🔎  Mostra file generato": "🔎  Show generated file",
    "Ricarica dal file": "Reload from file",
    "💾  Salva": "💾  Save",
    "Chiudi": "Close",
    "File generato — anteprima": "Generated file — preview",
    "Questo è ciò che l'editor scriverà nel keyfile:":
        "This is what the editor will write to the keyfile:",
    "Manca la rete": "Missing network",
    "Inserisci MCC e MNC della rete.": "Enter the network's MCC and MNC.",
    "Chiave non valida": "Invalid key",
    "La chiave alla riga {row} deve contenere solo "
    "cifre esadecimali (0-9, a-f).":
        "The key on row {row} must contain only hex digits (0-9, a-f).",
    "Controlla la lunghezza": "Check the length",
    "Riga {row}: hai inserito {n} cifre esadecimali = "
    "{bits} bit.\nIl formato standard di questo campo è "
    "20 cifre = 80 bit.\n\nLa salvo comunque così com'è?":
        "Row {row}: you entered {n} hex digits = {bits} bit.\nThe standard "
        "format for this field is 20 digits = 80 bit.\n\nSave it as-is anyway?",
    "Confermi il salvataggio?": "Confirm save?",
    "Rete: {mcc} / {mnc}\nAlgoritmo: {algo}\n"
    "Security class: {sec}\nChiavi configurate: {n}\nFile: {path}":
        "Network: {mcc} / {mnc}\nAlgorithm: {algo}\n"
        "Security class: {sec}\nConfigured keys: {n}\nFile: {path}",
    "\n\nSalvo la configurazione?": "\n\nSave the configuration?",
    "Errore": "Error",
    "Impossibile scrivere {path}:\n{exc}": "Couldn't write {path}:\n{exc}",
    "Salvato": "Saved",
    "Chiavi salvate in:\n{path}\n(permessi riservati al tuo utente, 0600)\n\n"
    "Avvia (o riavvia) la ricezione per usarle.":
        "Keys saved to:\n{path}\n(permissions restricted to your user, 0600)\n\n"
        "Start (or restart) reception to use them.",

    # -- avvio/arresto della catena -----------------------------------------
    "Manca qualcosa": "Something's missing",
    "Flowgraph non trovato: {path}": "Flowgraph not found: {path}",
    "Ricevitore osmo non trovato in {path}.\n"
    "Esegui prima l'installazione:  ./install.sh":
        "osmo receiver not found in {path}.\n"
        "Run the installer first:  ./install.sh",
    "telive non trovato in {path}.\n"
    "Esegui prima l'installazione:  ./install.sh":
        "telive not found in {path}.\n"
        "Run the installer first:  ./install.sh",
    "La porta {port} è già occupata: un'altra istanza è "
    "forse in esecuzione. Premi «Ferma» o chiudila prima.":
        "Port {port} is already in use: another instance might be "
        "running. Press «Stop» or close it first.",
    "Impossibile avviare il flowgraph:\n{exc}": "Couldn't start the flowgraph:\n{exc}",
    "Ricevitore non partito": "Receiver didn't start",
    "Il flowgraph si è chiuso all'avvio (di solito manca la radio, "
    "il driver DVB-T è ancora caricato, oppure rtl_tcp non risponde).\n\n"
    "Guarda le righe [rx] nel log qui sotto: dicono cosa manca e cosa fare.":
        "The flowgraph closed on startup (usually the radio is missing, "
        "the DVB-T driver is still loaded, or rtl_tcp isn't responding).\n\n"
        "Look at the [rx] lines in the log below: they say what's missing and what to do.",
    "Impossibile avviare il ricevitore:\n{exc}": "Couldn't start the receiver:\n{exc}",
    "Terminale non trovato": "No terminal found",
    "Non trovo un emulatore di terminale (gnome-terminal, xterm…).\n"
    "Apri un terminale ed esegui a mano:\n  cd {path} && ./telive":
        "I can't find a terminal emulator (gnome-terminal, xterm…).\n"
        "Open a terminal and run by hand:\n  cd {path} && ./telive",
    "Impossibile aprire il terminale di telive:\n{exc}":
        "Couldn't open telive's terminal:\n{exc}",

    # -- messaggi di log (prefisso [launcher]) -------------------------------
    "[launcher] il ricevitore SDR non è partito: catena fermata.":
        "[launcher] the SDR receiver didn't start: chain stopped.",
    "[launcher] stato/diagnostica attivi (tap {tap} → telive {telive})":
        "[launcher] status/diagnostics active (tap {tap} → telive {telive})",
    "[launcher] tap dello stato non disponibile: proseguo senza diagnostica":
        "[launcher] status tap not available: continuing without diagnostics",
    "[launcher] apro telive con: {term}": "[launcher] opening telive with: {term}",
    "[launcher] catena avviata. telive è nella sua finestra "
    "(ingrandiscila se serve: telive vuole 203×60).":
        "[launcher] chain started. telive is in its window "
        "(maximize it if needed: telive wants 203×60).",
    "[launcher] lo stadio «flowgraph» si è fermato: chiudo la catena.":
        "[launcher] the «flowgraph» stage stopped: closing the chain.",
    "[launcher] lo stadio «ricevitore» si è fermato: chiudo la catena.":
        "[launcher] the «receiver» stage stopped: closing the chain.",
    "[launcher] telive è stato chiuso: fermo la catena.":
        "[launcher] telive was closed: stopping the chain.",
    "[launcher] fermato.": "[launcher] stopped.",
    "[launcher] profilo «{name}» applicato.": "[launcher] profile «{name}» applied.",
    "[launcher] profilo «{name}» salvato in {path}": "[launcher] profile «{name}» saved to {path}",
    "[launcher] dettagli della rete copiati negli appunti.":
        "[launcher] network details copied to the clipboard.",
    "[launcher] diagnostica esportata in {path}": "[launcher] diagnostics exported to {path}",

    # -- diagnostica esportata ---------------------------------------------
    "OsmoTetra — diagnostica": "OsmoTetra — diagnostics",
    "Generata il: {ts}": "Generated on: {ts}",
    "Questo file NON contiene alcuna chiave di decifratura.":
        "This file does NOT contain any decryption key.",
    "== Sistema ==": "== System ==",
    "Python (pannello): {v}": "Python (panel): {v}",
    "Sistema": "System",
    "== Impostazioni ==": "== Settings ==",
    "device_args effettivi: {v}": "effective device_args: {v}",
    "(automatico)": "(automatic)",
    "== Componenti ==": "== Components ==",
    "presente": "present",
    "MANCANTE": "MISSING",
    "== Stato ==": "== Status ==",
    "catena in esecuzione: {v}": "chain running: {v}",
    "sì": "yes",
    "no": "no",
    "== Rete ==": "== Network ==",
    "== Chiavi (solo conteggio) ==": "== Keys (count only) ==",
    "chiavi nel keyfile: {n}": "keys in the keyfile: {n}",
    "rete del keyfile: MCC {mcc} / MNC {mnc}": "keyfile network: MCC {mcc} / MNC {mnc}",
    "ksg_type: {ksg} · security_class: {sec}": "ksg_type: {ksg} · security_class: {sec}",
    "== Log (ultime 300 righe, chiavi rimosse) ==": "== Log (last 300 lines, keys removed) ==",
    "non disponibile": "not available",

    # -- osmotetra_rx.py: messaggi diagnostici (arrivano nel log come [rx]) --
    "[osmotetra_rx] Nessun ricevitore rtl_tcp su {endpoint}.\n"
    "  Il server rtl_tcp non risponde. Sulla macchina a cui è collegata\n"
    "  la chiavetta avvia:  rtl_tcp -a 0.0.0.0 -p 1234\n"
    "  e lascia quella finestra aperta; verifica host e porta.\n"
    "  (dettaglio gr-osmosdr: {exc})":
        "[osmotetra_rx] No rtl_tcp receiver at {endpoint}.\n"
        "  The rtl_tcp server isn't responding. On the machine the dongle\n"
        "  is plugged into, run:  rtl_tcp -a 0.0.0.0 -p 1234\n"
        "  and leave that window open; check host and port.\n"
        "  (gr-osmosdr detail: {exc})",
    "(indirizzo mancante)": "(missing address)",
    "[osmotetra_rx] Nessun dispositivo SDR trovato (richiesto: {where}).\n"
    "  • Se la chiavetta è collegata direttamente: controlla con\n"
    "      rtl_test -t\n"
    "    'usb_claim_interface error -6' = driver DVB-T ancora caricato\n"
    "    (scollega/ricollega o riavvia); se serve, fai logout/login per il\n"
    "    gruppo plugdev.\n"
    "  • In una macchina virtuale l'USB potrebbe non essere inoltrato:\n"
    "    lascia la chiavetta al sistema ospitante ed esponila con rtl_tcp\n"
    "    (dispositivo 'rtl_tcp=INDIRIZZO:1234'). Vedi il README.\n"
    "  (dettaglio gr-osmosdr: {exc})":
        "[osmotetra_rx] No SDR device found (requested: {where}).\n"
        "  • If the dongle is plugged in directly: check with\n"
        "      rtl_test -t\n"
        "    'usb_claim_interface error -6' = the DVB-T driver is still loaded\n"
        "    (unplug/replug or reboot); log out/in for the plugdev group if needed.\n"
        "  • In a virtual machine, USB might not be forwarded:\n"
        "    leave the dongle on the host system and expose it with rtl_tcp\n"
        "    (device 'rtl_tcp=ADDRESS:1234'). See the README.\n"
        "  (gr-osmosdr detail: {exc})",
    "auto (nessun dispositivo indicato)": "auto (no device given)",
    "[osmotetra_rx] canale {freq:.4f} MHz "
    "(SDR a {sdr_freq:.4f} MHz, offset anti-DC "
    "{offset:.0f} kHz), {samp_rate:.3f} Ms/s, "
    "XMLRPC su 0.0.0.0:{port}, UDP su {host}:{data_port}":
        "[osmotetra_rx] channel {freq:.4f} MHz "
        "(SDR at {sdr_freq:.4f} MHz, anti-DC offset "
        "{offset:.0f} kHz), {samp_rate:.3f} Ms/s, "
        "XMLRPC on 0.0.0.0:{port}, UDP on {host}:{data_port}",
    "  [finestra spettro attiva]": "  [spectrum window active]",
    "[osmotetra_rx] arresto in corso...": "[osmotetra_rx] stopping...",
}
