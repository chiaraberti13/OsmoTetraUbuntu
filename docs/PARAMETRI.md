# Parametri

Corrispondenza fra i campi dell'interfaccia e i parametri di upstream, utile a
chi conosce già `receiver1udp` e `rxx` — e a chi deve cercare qualcosa nel
manuale di telive.

## Scheda «Radio»

| Campo | Dove finisce | Note |
|---|---|---|
| Dispositivo | `osmotetra_rx.py --device-args` | stringa di gr-osmosdr: `rtl=0`, `hackrf=0`, `airspy=0`, `uhd`. Vuoto = primo dispositivo trovato |
| Frequenza centrale | `--freq`, XMLRPC `freq` | è la frequenza dell'SDR, non quella dei canali |
| Campionamento | `--samp-rate`, XMLRPC `samp_rate` | oltre 2,4 Ms/s le RTL-SDR perdono campioni |
| Decimazione | `--first-decim` | `samp_rate / decimazione` deve restare ≥ 2 × filtro |
| Filtro di canale | `--lowpass`, XMLRPC `options_low_pass` | 12,5 kHz = un canale TETRA |
| Guadagno RF / IF / banda base | `--gain`, `--if-gain`, `--bb-gain` | XMLRPC `sdr_gain`, `sdr_ifgain`, `sdr_bbgain` |
| Correzione | `--ppm`, XMLRPC `ppm_corr` | regolala finché l'AFC in telive (tasto `t`) è vicino a zero |
| Sorgente | `--source` | `osmosdr`, `file:<percorso>`, `null` |

**A caldo o riavvio?** Frequenza, guadagni, correzione e offset si applicano
senza fermare nulla («Applica a caldo»). Dispositivo, campionamento,
decimazione, numero di canali e porte richiedono un riavvio della catena:
l'interfaccia lo segnala con un banner.

## Scheda «Canali»

| Campo | Dove finisce | Note |
|---|---|---|
| Numero di canali | `--channels` | massimo 6, come nei flowgraph upstream |
| Offset | `--offset` (uno per canale), XMLRPC `xlate_offsetN` | scostamento dalla frequenza centrale |
| Frequenza | *(calcolata)* | frequenza centrale + offset; è quella che conta |
| Porta UDP | *(calcolata)* | porta base + N |
| Ricomponi (`-r`) | `tetra-rx -r` | ricompone i PDU frammentati |
| SDS testo (`-s`) | `tetra-rx -s` | mostra come testo gli SDS di protocollo ignoto |
| Cifrati (`-e`) | `tetra-rx -e` | tenta di interpretare i pacchetti cifrati: **produce risultati privi di senso**, non decifra nulla |

Il canale 1 conviene sintonizzarlo sul canale di controllo, che porta quasi
tutta la segnalazione.

`tetra-rx` ha anche `-a` (pseudo-AFC), che upstream funziona **solo** insieme
a `-i` (ingresso a valori float). Nella catena con `simdemod3_py3.py`
l'ingresso è già a bit, quindi `-a` non viene passato: la correzione la fa
simdemod3, che invia a telive i messaggi `AFCVAL` mostrati nella finestra
delle frequenze.

## Scheda «telive»

Tutti questi campi diventano variabili d'ambiente lette da telive
(`telive.c:2729-2905`), scritte in `tetra/bin/telive-run`.

| Campo | Variabile |
|---|---|
| Porta UDP di telive | `TETRA_PORT` (default 7379) |
| Porta base del ricevitore | usata per `TETRA_GR_XMLRPC_URL` e per le porte dei canali |
| Registra le chiamate | `TETRA_KEYS` contiene `R` |
| Scrivi il log | `TETRA_KEYS` contiene `l` |
| Silenzia SSI sconosciuti | `TETRA_KEYS` contiene `m` |
| Silenzia tutto l'audio | `TETRA_KEYS` contiene `M` |
| Mostra tutta la segnalazione | `TETRA_KEYS` contiene `a` |
| Filtro SSI | `TETRA_SSI_FILTER` |
| Descrizioni SSI | `TETRA_SSI_DESCRIPTIONS` |
| KML e intervallo | `TETRA_KML_FILE`, `TETRA_KML_INTERVAL` |
| Controllo del ricevitore | `TETRA_GR_XMLRPC_URL` |
| Sintonia automatica | `TETRA_AUTO_TUNE` |
| Correzione ppm automatica | `TETRA_RX_PPM_AUTOCORRECT` |
| Frequenza centrale automatica | `TETRA_RX_BASEBAND_AUTOCORRECT` |
| Intervalli di scansione | `TETRA_SCAN_LIST` |

Impostate sempre dall'applicazione: `TETRA_OUTDIR`, `TETRA_LOGFILE`,
`TETRA_FREQLOGFILE`, `TETRA_FREQUENCY_REPORT_FILE`, `TETRA_RX_GAIN`,
`TETRA_RX_PPM`, `TETRA_RX_BASEBAND`, `TETRA_RX_TUNE`.

Il formato del filtro SSI è quello dell'espansione estesa di bash: `10??`
copre 1000-1099, `+(1000|20??)` copre 1000 e 2000-2099. Nell'interfaccia di
telive il filtro va poi **abilitato** con il tasto `f`.

## Tasti di telive

L'interfaccia ncurses resta quella di upstream: `?` mostra l'elenco completo.
I più usati:

| Tasto | Effetto |
|---|---|
| `?` | aiuto |
| `t` | alterna finestra degli usage identifier e finestra delle frequenze |
| `R` | attiva/disattiva la registrazione |
| `l` | attiva/disattiva il log |
| `M` / `m` | silenzia tutto / silenzia gli SSI sconosciuti |
| `f` / `F` | abilita il filtro SSI / inserisci l'espressione |
| `x` | sintonizza un canale (numero, spazio, frequenza in MHz) |
| `G` / `P` | cambia guadagno / correzione in ppm |
| `q` / `Q` | scansiona fino alla prima rete / scansiona senza fermarsi |
| `d` | scrivi il report delle frequenze |

Il manuale completo è `~/.local/share/osmotetra/src/telive/telive_doc.pdf`.

## Variabili d'ambiente dell'applicazione

| Variabile | Effetto |
|---|---|
| `OSMOTETRA_PREFIX` | directory di installazione (default `~/.local/share/osmotetra`) |
| `OSMOTETRA_PYTHON` | forza l'interprete Python per GNU Radio |
| `XDG_CONFIG_HOME` | posizione di `osmotetra/config.json` |

## Valori di partenza ragionevoli

Per una prima prova su una rete TETRA nota, con una RTL-SDR:

```
Frequenza centrale   la frequenza del canale di controllo
Campionamento        2,0 Ms/s
Decimazione          32          → 62,5 kHz per canale
Filtro di canale     12,5 kHz
Guadagno RF          38 dB
Correzione           quella della tua chiavetta (spesso fra 0 e 60 ppm)
Canali               1, offset 0
```

Con un solo canale centrato, l'offset resta a zero e la frequenza del canale
coincide con quella centrale. Passando a più canali conviene invece spostare
la frequenza centrale a metà del gruppo di canali da ricevere e usare gli
offset — così tutti restano dentro la banda campionata.
