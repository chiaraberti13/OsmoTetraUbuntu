# Architettura

Come sono collegati i pezzi, e perché alcune scelte non ovvie sono fatte così.

## La catena

```
                    ┌──────────────────────────────────────────────┐
   RTL-SDR ────────►│ [1] osmotetra_rx.py   (GNU Radio 3.10)       │
                    │     osmosdr_source                           │
                    │       └─► freq_xlating_fir_filter(offset_N)  │
                    │             └─► agc3_cc                      │
                    │                   └─► mmse_resampler(36ks/s) │
                    │                         └─► udp_sink         │
                    │     + SimpleXMLRPCServer su :42000           │
                    └───────────────┬──────────────────────────────┘
                                    │ UDP :42001, :42002, ...
                                    │ (campioni complessi, 36 ks/s)
                    ┌───────────────▼──────────────────────────────┐
                    │ [2] un decoder per canale                    │
                    │     socat UDP-RECV:4200N                     │
                    │       │ simdemod3_telive.py   (π/4-DQPSK)       │
                    │       │ tetra-rx -r -s                       │
                    └───────────────┬──────────────────────────────┘
                                    │ UDP :7379
                                    │ "TETMON_begin ... TETMON_end"
                    ┌───────────────▼──────────────────────────────┐
                    │ [3] telive     (ncurses, 203×60)             │
                    │       ├─popen──► tplay ─► cdecoder│sdecoder  │
                    │       │                    └─► aplay         │
                    │       └─XMLRPC─► [1]  sintonia, scansione     │
                    └───────────────┬──────────────────────────────┘
                                    │ file .out in tetra/in
                    ┌───────────────▼──────────────────────────────┐
                    │ [4] tetrad  (opzionale)  ACELP ─► OGG        │
                    └──────────────────────────────────────────────┘
```

Quello che upstream si fa a mano in tre terminali, qui lo gestisce
`osmotetra/pipeline.py`. Per vedere i comandi esatti che vengono eseguiti:

```sh
osmotetra print-cmdline
```

## Scelte non ovvie

### L'ordine di avvio è ricevitore → telive → decoder

Sembrerebbe più sensato avviare prima telive, così da non perdere pacchetti.
Non lo è: telive chiama `grxml_discover_receiver()` **una sola volta**, al
proprio avvio (`telive.c:2891`). Se in quel momento il server XMLRPC del
flowgraph non risponde, telive considera il ricevitore assente per tutta la
sessione — e non c'è modo di rimediare senza riavviarlo, perché anche il tasto
`z` chiama `grxml_update_receivers()`, non la scoperta.

Perdere il primo secondo di campioni è invece innocuo: è traffico UDP su
loopback verso porte non ancora aperte. Per questo `Pipeline.start()` avvia il
ricevitore, **aspetta che il suo XMLRPC risponda**, e solo dopo lancia telive.

### Ogni stadio si termina a gruppi di processi, non a processo singolo

Tutti gli stadi partono con `start_new_session=True`, quindi ognuno guida un
proprio gruppo, e l'arresto usa `killpg`. Non è un eccesso di zelo: quasi ogni
stadio ha figli.

- `demod-N` è una pipeline di tre processi (`socat`, `simdemod3`, `tetra-rx`):
  terminando la sola shell, gli altri due restano vivi.
- `telive` gira **dentro** un emulatore di terminale, che lo esegue come figlio.
  Uccidendo solo l'emulatore, telive resta orfano e continua a tenere occupata
  la porta UDP 7379 — al riavvio successivo il controllo preliminare fallisce
  con «porta già occupata» e l'utente non capisce perché.

### L'interprete Python viene rilevato, non dato per scontato

I binding di GNU Radio sono compilati per il Python del pacchetto Ubuntu (3.12
su 24.04). Se sulla macchina convive un altro Python che occupa il PATH —
pyenv, conda, una build da sorgente — `simdemod3_telive.py`, che ha
`#!/usr/bin/env python3` come shebang, parte con l'interprete sbagliato e
fallisce con `ModuleNotFoundError: No module named 'gnuradio.gr.gr_python'`.

`deps.find_gnuradio_python()` prova i candidati finché uno non importa
`gnuradio`, e sia il flowgraph sia `simdemod3_telive.py` vengono invocati con
quell'interprete invece che tramite shebang. `OSMOTETRA_PYTHON` forza la scelta.

### Il flowgraph è parametrico invece di essere pilotato solo via XMLRPC

Nei flowgraph originali di SQ5BPF il numero di canali, le porte UDP e la porta
XMLRPC sono fissati alla costruzione: `set_first_port()` esiste ma non
riconfigura né i sink UDP né il server. Pilotare da fuori un `.py` generato da
GNU Radio Companion basta per frequenza e guadagni, non per la topologia.

`gnuradio/osmotetra_rx.py` prende quindi tutto da riga di comando. Resta la
distinzione fra parametri **a caldo** (frequenza, guadagni, ppm, offset →
XMLRPC, pulsante «Applica a caldo») e **strutturali** (canali, porte,
dispositivo, campionamento → riavvio della catena, segnalato dal banner).

I nomi delle variabili esposte via XMLRPC sono vincolati: telive cerca
`telive_receiver_name`, `telive_receiver_channels`, `freq`, `samp_rate`,
`ppm_corr`, `sdr_gain`, `xlate_offsetN`. Cambiarli spegne il controllo del
ricevitore.

### telive si configura scrivendo uno script, non variabili sulla riga di comando

telive non ha né file di configurazione né opzioni: legge una ventina di
variabili `TETRA_*`. Passarle come `env A=1 B=2 ...` funziona con xterm ma non
con gnome-terminal, che accetta un solo comando. `telive_env.write_runner_script()`
genera quindi `tetra/bin/telive-run`, uno script con tutti gli `export`, un
`cd` nella directory dei sorgenti di telive (dove il programma cerca
`tetra.xml` e `ssi_descriptions`) e infine `./telive`.

### tplay e tetrad sono rigenerati, non copiati

Le versioni upstream hanno `/tetra/bin` cablato dentro — una directory di
proprietà di root. Qui tutto sta nella home dell'utente, quindi
`scripts/templates/*.in` vengono resi con il percorso reale del codec.
telive riproduce l'audio con `popen("tplay")`, cercandolo nel `PATH`: per
questo `Pipeline._spawn()` antepone `tetra/bin` al `PATH` di ogni stadio.

## Struttura dei file

| Percorso | Contenuto |
|---|---|
| `install.sh`, `scripts/` | installazione: pacchetti, build upstream, codec, udev |
| `patches/` | patch applicate ai sorgenti upstream (es. nanohttp→socket per telive-2) |
| `gnuradio/osmotetra_rx.py` | flowgraph parametrico 1..6 canali |
| `osmotetra/config.py` | configurazione, validazione, profili |
| `osmotetra/deps.py` | rilevamento dipendenze e interprete GNU Radio |
| `osmotetra/pipeline.py` | avvio, sorveglianza e arresto degli stadi |
| `osmotetra/telive_env.py` | configurazione → variabili `TETRA_*` |
| `osmotetra/xmlrpc_ctl.py` | client XMLRPC verso il flowgraph |
| `osmotetra/ui/` | interfaccia PyQt5 |

A runtime, sotto `~/.local/share/osmotetra`:

| Percorso | Contenuto |
|---|---|
| `src/osmo-tetra-sq5bpf-2`, `src/telive-2` | sorgenti upstream (v2) clonati e compilati |
| `lib/` | copia dell'applicazione usata dal launcher |
| `tetra/in`, `tetra/out` | chiamate registrate, grezze e in OGG |
| `tetra/log` | `telive.log`, KML, report delle frequenze |
| `tetra/bin` | `tplay`, `tetrad`, `telive-run`, binari del codec |

Configurazione e profili stanno in `~/.config/osmotetra/`.
