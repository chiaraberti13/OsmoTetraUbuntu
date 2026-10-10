---
name: convenzioni-osmotetra
description: >-
  Convenzioni, stack e pattern del progetto OsmoTetra (ricevitore/analisi TETRA
  per Ubuntu: launcher PyQt5, flowgraph GNU Radio headless, script bash di
  installazione, catena SQ5BPF osmo-tetra/telive-2, i18n italiano↔inglese).
  Usa SEMPRE questa skill quando lavori in questo repository: prima di scrivere
  o modificare qualunque file Python (.py), bash (.sh), il dispatcher
  `osmotetra`, il flowgraph `.grc`, le patch in `patches/`, la documentazione in
  `docs/` o i testi dell'interfaccia. Serve anche quando aggiungi stringhe
  visibili all'utente (vanno tradotte), tocchi la gestione delle chiavi di
  decifratura, la configurazione via variabili d'ambiente, o aggiorni i
  sorgenti upstream. In dubbio su header, lingua, naming o pattern difensivi,
  consultala invece di improvvisare.
---

# Convenzioni del progetto OsmoTetra

OsmoTetra è un **wrapper d'uso facile** attorno alla catena SDR TETRA di Jacek
Lipkowski (SQ5BPF): `osmo-tetra-sq5bpf-2` + `telive-2` + codec vocale ETSI.
Non cracca nulla — decifra **solo con chiave già nota**. Il valore del progetto
sta nel rendere quella catena installabile e usabile da non-esperti, quindi ogni
scelta tecnica serve questo obiettivo: chiarezza, robustezza, rispetto della
legge.

Catena del segnale (tienila a mente quando tocchi il DSP o l'IPC):

```
osmotetra_rx.py (flowgraph GNU Radio headless)  →  UDP 42001
    →  receiver1udp (socat | simdemod3_telive.py | tetra-rx)  →  UDP 7379
        →  telive  (ncurses, l'interfaccia vera)
    controllo runtime: XMLRPC su porta 42000
```

## Stack

- **GUI**: PyQt5 — `osmotetra_launcher.py`. Doc: https://doc.qt.io/qtforpython-5/
- **DSP/SDR**: GNU Radio + `gr-osmosdr`/`osmosdr` — `osmotetra_rx.py` (+ `osmotetra_rx.grc`). Doc: https://wiki.gnuradio.org/
- **IPC**: UDP (42001→7379) + XMLRPC (`xmlrpc.server.SimpleXMLRPCServer`, porta 42000).
- **Orchestrazione**: Bash — `install.sh`, `avvia.sh`, `uninstall.sh`, dispatcher `osmotetra`.
- **Upstream C** (clonati e compilati dall'installer): `osmo-tetra-sq5bpf-2`, `telive-2`.
- **Grafica**: SVG (`assets/banner.svg`).
- **Docs**: Markdown bilingue IT/EN in `docs/`.

Nessun framework di test e nessun gestore di pacchetti Python: si usa il
`python3` di sistema con i binding GNU Radio installati via `apt`. Non
introdurre `requirements.txt`/venv senza chiederlo: romperebbe l'assunzione che
GNU Radio venga dall'apt di sistema.

## 1. Header di ogni file

Ogni file Python inizia così — replicalo sempre:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Titolo breve in italiano.

Docstring narrativa in italiano che spiega il PERCHÉ e il flusso dei dati,
non solo il cosa. Scrivi come a una persona che non conosce il codice.

SPDX-License-Identifier: GPL-3.0-or-later
"""
```

I moduli che derivano da upstream citano la fonte e la licenza nel docstring
(es. `osmotetra_rx.py` cita `https://github.com/sq5bpf/telive-2 (GPL-3.0)`).
Usa `from __future__ import annotations` e i type hint.

Gli script bash iniziano con un banner a `====` e `set -euo pipefail`:

```bash
#!/usr/bin/env bash
# ============================================================================
#  nome.sh — a cosa serve, in italiano
# ============================================================================
#  Uso, esempi, variabili utili...
# ============================================================================
set -euo pipefail
```

## 2. Lingua: italiano sorgente, inglese via i18n

**Regola d'oro**: scrivi tutto — codice, commenti, docstring, e il testo
sorgente dell'interfaccia — **in italiano**. L'inglese esiste solo come
traduzione a runtime.

Il meccanismo sta in `osmotetra_i18n.py`:

```python
from osmotetra_i18n import _

label = _("Frequenza del canale:")   # "it" → invariato; "en" → dal dizionario EN
```

`_(text)` fa `EN.get(text, text)`: se la stringa non è nel dizionario resta in
italiano, non si rompe mai. Quando **aggiungi una stringa visibile all'utente**:

1. Scrivila in italiano e avvolgila in `_()`.
2. Aggiungi la coppia italiano→inglese nel dizionario `EN` di
   `osmotetra_i18n.py`, nella sezione a commento giusta (`# -- pulsanti`, ecc.).
3. Se la stringa ha placeholder, usa `.format(...)` **dopo** `_()`, e mantieni
   gli stessi nomi di placeholder nelle due lingue:
   `_("File non trovato: {path}").format(path=p)`.

`osmotetra_i18n.py` non dipende da PyQt apposta: lo usano sia il launcher sia il
flowgraph headless, così i messaggi restano coerenti. Non introdurre
`gettext`/file `.po`: il dizionario in-memory è la convenzione scelta.

## 3. Configurazione via variabili d'ambiente

Ogni parametro operativo si legge da env con fallback esplicito, sia in bash
(`"${OSMOTETRA_GAIN:-38}"`) sia in Python
(`os.environ.get("OSMOTETRA_HOME", str(Path.home() / "telive2"))`). Variabili
in uso — riusale, non inventarne di parallele:

| Variabile | Significato | Default |
|---|---|---|
| `OSMOTETRA_HOME` | dir dei sorgenti compilati | `~/telive2` |
| `OSMOTETRA_PYTHON` | interprete con i binding GNU Radio | `python3` |
| `OSMOTETRA_GAIN` | guadagno RF (dB) | `38` |
| `OSMOTETRA_PPM` | correzione ppm | `0` |
| `OSMOTETRA_LANG` | lingua (`it`/`en`) | auto |
| `OSMOTETRA_MODE` | forza modalità avvio | — |
| `OSMOTETRA_NOGUI` / `OSMOTETRA_NOGRC` | sopprime finestre | — |

Impostazioni e profili persistono in JSON sotto
`XDG_CONFIG_HOME/osmotetra/` (fallback `~/.config/osmotetra/`):
`impostazioni.json` (lingua) e `profili.json`. Usa sempre `pathlib.Path`, mai
concatenazioni di stringhe di percorso. Scrivi JSON con
`json.dumps(..., indent=2, ensure_ascii=False)` per non mangiare gli accenti.

## 4. Codice difensivo

Un file mancante o illeggibile **non è un errore**: si torna un valore vuoto e
si prosegue. È la norma, non l'eccezione — l'utente tipico non deve vedere uno
stack trace per un keyfile che ancora non esiste.

```python
def parse_keyfile(path):
    """Un file mancante o illeggibile non è un errore: si torna vuoti."""
    net, keys = {}, []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return net, keys
    ...
```

Cattura eccezioni **specifiche** (`OSError`, `ValueError`), non `except:` nudo.
In bash, i comandi che possono fallire senza essere fatali terminano con
`2>/dev/null || true`.

## 5. Sicurezza: le chiavi non devono trapelare

Il progetto maneggia chiavi di decifratura TETRA. Regole non negoziabili:

- **Mai loggare materiale di chiave.** Qualsiasi testo che finisce nei log
  passa da `redact_keys()` (regex `_HEX_RUN = r"\b[0-9a-fA-F]{16,}\b"` →
  `<chiave rimossa>`). Se aggiungi un nuovo percorso di log, redaci prima.
- **I profili non contengono mai chiavi** — è scritto anche nei tooltip. Non
  aggiungere campi chiave a `profili.json`.
- **Decifratura solo a chiave nota**: non aggiungere nulla che somigli a
  brute-force o cracking. Il disclaimer è parte del prodotto.
- Nei testi nuovi mantieni l'avviso d'uso responsabile (solo su sistemi/segnali
  per cui si ha autorizzazione legale). Vulnerabilità → GitHub Security
  Advisories (vedi `SECURITY.md`), mai in chiaro.

## 6. Fedeltà all'upstream e patch

I nomi di variabili del flowgraph sono tenuti **identici a upstream** perché
`telive` li interroga per nome via XMLRPC. Non rinominarli "per pulizia": li
rompi. Se tocchi `osmotetra_rx.py`, conserva la semantica bit-per-bit della
catena di segnale (filtro, AGC, ricampionatore, offset anti-DC
`XLATE_OFFSET = 500e3`).

Non si modificano i sorgenti upstream nel loro repo: si **sovrappongono patch**
da `patches/`, applicate da `install.sh` (`maybe_patch_nanohttp`) con
`patch -p1 -N` (idempotente: un secondo `./install.sh` non fallisce). Ogni
patch ha una voce in `patches/README.md` con **Problema / Cosa fa / Verifica /
Se smette di applicarsi**. Se crei una patch, segui quella struttura e
rigenerala con `git diff > patches/nome.diff`.

## 7. Pattern PyQt (launcher)

- Costruzione UI in metodi privati: `_build_ui()`, un `_tab_<nome>()` per
  scheda (`_tab_reception`, `_tab_status`, ...).
- Segnali Qt per il lavoro in background: classi `QObject` con `pyqtSignal`
  (vedi `StatusTap`, `Emitter`) invece di toccare la UI da altri thread.
- Modalità **Base/Avanzata**: i campi avanzati si mostrano/nascondono, non si
  duplicano schermate.
- Helper locali minuscoli (`_muted`, `_cell`, `_pad`) per ridurre la ripetizione.

## 8. Naming e documentazione

- I comandi e le modalità utente sono **verbi italiani**: `avvia`, `spettro`,
  `monitor`, `chiavi`, `ferma`, `aiuto` (vedi dispatcher `osmotetra`). Mantieni
  questo vocabolario quando aggiungi sottocomandi.
- Funzioni/variabili interne in italiano o inglese tecnico, coerenti col file
  circostante; i commenti sempre in italiano.
- **Tutto ciò che è rivolto all'utente è bilingue**: se aggiungi un documento in
  `docs/`, fai la coppia `*.it.md` + `*.en.md`; README e SECURITY hanno i link a
  bandiera 🇬🇧/🇮🇹 in testa. Gli screenshot/asset grafici sono SVG.

## Checklist rapida prima di un commit

- [ ] Header completo (shebang + coding + docstring IT + SPDX GPL-3.0-or-later).
- [ ] Testo utente in italiano, avvolto in `_()`, con coppia EN nel dizionario.
- [ ] Parametri nuovi letti da env con fallback; percorsi con `pathlib`.
- [ ] Errori I/O gestiti come "vuoto, non fatale"; except specifici.
- [ ] Nessuna chiave nei log/profili; `redact_keys()` sui nuovi log.
- [ ] Nomi upstream intatti; eventuali patch in `patches/` + voce nel README.
- [ ] Doc/README aggiornati in **entrambe** le lingue.
