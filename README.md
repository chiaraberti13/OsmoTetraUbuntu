# OsmoTetraUbuntu

Applicazione per **Ubuntu 24.04 LTS e successive** che rende usabile la suite di monitoraggio
TETRA di Jacek Lipkowski (SQ5BPF): installa tutte le dipendenze, compila
[`osmo-tetra-sq5bpf`](https://github.com/sq5bpf/osmo-tetra-sq5bpf) e
[`telive`](https://github.com/sq5bpf/telive), **avvia automaticamente i tre stadi della catena di
ricezione** (che normalmente vanno lanciati a mano in tre terminali separati) e offre una GUI
PyQt5 per impostare tutti i parametri.

> ⚠️ **Avviso legale.** La ricezione, la decodifica e la registrazione di traffico radio TETRA
> sono regolate in modo diverso da paese a paese, e in molte giurisdizioni sono soggette a
> restrizioni o vietate. Questo software è pensato per uso didattico, sperimentale e di ricerca
> su traffico che si è **autorizzati** a ricevere (reti proprie, banchi di prova, segnali di
> test). È responsabilità di chi lo usa verificare e rispettare le norme applicabili.

---

## Cosa fa, in una riga

Quello che nel manuale di telive richiede tre terminali e una ventina di variabili d'ambiente
scritte a mano, qui è un pulsante **Avvia** e una finestra di configurazione.

## La catena di ricezione

```
RTL-SDR ──► [1] osmotetra_rx.py            flowgraph GNU Radio 3.10 headless
                 osmosdr → xlating FIR(offsetN) → AGC → resampler(36 ks/s)
                 → UDP 127.0.0.1:<base+N>          + XMLRPC su <base>
                        │
                        ▼
            [2] socat UDP-RECV:<base+N> │ simdemod3_py3.py │ tetra-rx      (uno per canale)
                        │                π/4-DQPSK          decoder TETRA
                        ▼  UDP :7379
            [3] telive                        interfaccia ncurses 203x60
                        └─► tplay → cdecoder │ sdecoder │ aplay      (audio, se il codec c'è)
            [4] tetrad                        ACELP → OGG            (opzionale)
```

Lo stadio **[1]** e gli stadi **[2]** girano come sottoprocessi, con i log dentro l'applicazione.
Lo stadio **[3]** viene aperto automaticamente in un terminale dedicato a 203x60 caratteri, perché
`telive` è un'interfaccia ncurses che richiede quella dimensione esatta.

## Installazione

```sh
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu
cd OsmoTetraUbuntu
./install.sh
```

L'installer è **idempotente** (si può rilanciare per aggiornare), va eseguito come utente normale
— non come root — e usa `sudo` solo per `apt` e per le regole udev. Installa i pacchetti da
`universe` di Ubuntu 24.04 (nessun PPA), clona e compila i sorgenti upstream in
`~/.local/share/osmotetra/src`, e crea la voce di menu «OsmoTetra».

Opzioni utili:

| Opzione | Effetto |
|---|---|
| `--prefix DIR` | Directory di installazione (default `~/.local/share/osmotetra`) |
| `--with-codec` | Tenta anche l'installazione del codec vocale ACELP (vedi sotto) |
| `--skip-apt` | Salta l'installazione dei pacchetti di sistema |
| `--dry-run` | Mostra cosa farebbe, senza modificare nulla |

### Codec vocale ACELP (opzionale)

L'audio richiede il codec ACELP di ETSI EN 300 395-2, che **non è redistribuibile** e va scaricato
dal sito ETSI. `scripts/40_install_codec.sh` prova a farlo automaticamente (verificando l'md5) e
applica la patch di sq5bpf; se il download non riesce, stampa le istruzioni per il download
manuale.

Senza codec l'applicazione è comunque pienamente funzionante per segnalazione, messaggi SDS, log,
export KML e analisi delle frequenze: manca soltanto la riproduzione e la registrazione dell'audio.

## Uso

Dal menu applicazioni («OsmoTetra») oppure da terminale:

```sh
osmotetra              # GUI
osmotetra check        # verifica le dipendenze
osmotetra print-cmdline  # stampa i comandi dei tre stadi senza eseguirli
osmotetra start        # avvia la catena da riga di comando
osmotetra stop         # ferma tutto
```

Configurazione e profili vivono in `~/.config/osmotetra/`.

## Documentazione

- [`docs/ARCHITETTURA.md`](docs/ARCHITETTURA.md) — come sono collegati i pezzi e perché
- [`docs/PARAMETRI.md`](docs/PARAMETRI.md) — mappa fra i campi della GUI e le variabili/argomenti upstream
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — cosa fare quando non arriva nulla

Il manuale originale di telive, indispensabile per capire l'interfaccia ncurses, è
[`telive_doc.pdf`](https://github.com/sq5bpf/telive/raw/master/telive_doc.pdf).

## Crediti

Tutto il lavoro difficile — demodulatore, decoder TETRA, telive — è di **Jacek Lipkowski SQ5BPF**
e, per `osmo-tetra`, di **Harald Welte** e del progetto Osmocom. Questo repository contiene solo
l'automazione dell'installazione, l'orchestrazione dei processi e l'interfaccia grafica; i
sorgenti upstream vengono clonati dai repository originali al momento dell'installazione.

Il flowgraph `gnuradio/osmotetra_rx.py` è derivato dai flowgraph
`telive_*ch_gr310_udp_xmlrpc_headless.py` di SQ5BPF, resi parametrici.

## Licenza

GPL-3.0 — vedi [LICENSE](LICENSE).
