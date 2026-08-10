<p align="center">
  <img src="assets/banner.svg" alt="OsmoTetra" width="100%">
</p>

<h1 align="center">OsmoTetra</h1>

<p align="center">
  <b>Ricevitore TETRA per Ubuntu — installazione in un comando, avvio in un clic.</b><br>
  <b>TETRA receiver for Ubuntu — one command to install, one click to run.</b>
</p>

<p align="center">
  🇮🇹 <a href="#italiano">Italiano</a> · 🇬🇧 <a href="#english">English</a>
</p>

---

OsmoTetra prende la catena di monitoraggio TETRA di **Jacek Lipkowski SQ5BPF**
(`osmo-tetra-sq5bpf-2` + codec vocale ETSI + `telive-2`), la installa con tutte
le dipendenze e **automatizza l'avvio dei tre stadi** che di solito si aprono a
mano in tre terminali. Al posto della procedura manuale c'è una finestrella:
imposti frequenza, guadagno e dispositivo, premi **Avvia** e partono da soli il
ricevitore, la finestra dello spettro e `telive`.

> **Nota legale.** La decifratura vocale funziona **solo a chiave nota**: devi
> fornire tu chiavi che già possiedi. Non rompe alcuna cifratura. Usa questo
> software solo su traffico che sei autorizzato a ricevere e decifrare — reti
> proprie, banchi di prova, ricerca autorizzata. La responsabilità è di chi lo
> usa. `telive-2` è software sperimentale pubblicato dall'autore.

---

## Italiano

### Cosa fa

La catena provata di SQ5BPF, avviata automaticamente da un unico lanciatore:

```
 RTL-SDR ─► flowgraph GNU Radio (osmotetra_rx.py)
              │        └─► finestra spettro (opzionale): 2 grafici + controlli
              │  campioni IQ a 36 kS/s
              ▼  UDP :42001
         receiver1udp  =  socat │ simdemod3_telive.py │ tetra-rx
              │  frame decodificati
              ▼  UDP :7379
           telive  ◄── il monitor che guardi: reti, SSI, chiamate (ncurses)
```

Quando premi **Avvia** vedi fino a **tre finestre**:

1. **il lanciatore** — dove imposti i parametri e leggi i log;
2. **la finestra dello spettro** (opzionale) — due analizzatori di spettro e i
   controlli a caldo di frequenza, ppm e guadagno;
3. **`telive`** — il monitor vero e proprio, in un terminale, dove compaiono
   rete, colour code, canale di controllo, SSI e chiamate.

Il flowgraph e `receiver1udp` girano **in sottofondo** (il loro output è nel
riquadro dei log del lanciatore). La catena di segnale — filtro, AGC,
ricampionatore, uscita UDP a 36 kS/s — è **identica** al flowgraph originale di
SQ5BPF: cambia solo che frequenza, guadagno, ppm e dispositivo si passano da
riga di comando, così il lanciatore può avviarlo da solo.

### Requisiti

- **Ubuntu 24.04 o successive** (testato anche su 25.10, x86 e ARM64).
- Una **RTL-SDR** (o altra radio supportata da gr-osmosdr: HackRF, Airspy…).
- Un'antenna adatta alla banda TETRA che vuoi ricevere.

### Installazione

```bash
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu.git
cd OsmoTetraUbuntu
./install.sh
```

Lancialo **da utente normale** (non con `sudo`): chiederà la password solo per
`apt` e per creare `/tetra`. Installa le dipendenze, scarica e compila
`osmo-tetra-sq5bpf-2`, il codec vocale ETSI e `telive-2`, e crea il lanciatore
(comando `osmotetra` e voce «OsmoTetra» nel menu applicazioni).

L'installazione **non tocca la radio**: antenna e chiavetta servono solo quando
usi l'app, non durante `./install.sh`.

Al termine, **riapri il terminale** (o `source ~/.bashrc`) per avere il comando
`osmotetra` nel PATH.

### Uso

Apri l'app: cerca **«OsmoTetra»** nel menu applicazioni, oppure da terminale:

```bash
osmotetra
```

Nel lanciatore:

1. **Frequenza del canale** — la frequenza del canale di controllo TETRA (es.
   `390.5` MHz). Scrivi la frequenza del canale e basta: l'app tiene l'SDR 500
   kHz più in là (offset anti-DC), così il segnale non cade sul picco DC della
   chiavetta.
2. **Guadagno RF** — parti da `38` dB; alzalo se il segnale è debole.
3. **Correzione (ppm)** — lasciala a `0` con le chiavette dotate di TCXO (come
   la RTL-SDR Blog V3); altrimenti regolala (vedi più sotto).
4. **Dispositivo** — «rilevamento automatico» per una chiavetta collegata
   direttamente; `rtl_tcp=INDIRIZZO:1234` se la chiavetta è su un'altra macchina
   (vedi «Chiavetta in una macchina virtuale»).
5. **Mostra la finestra dello spettro** — spuntata di default; toglila se
   vuoi avviare senza i grafici.
6. Premi **Avvia**. Si aprono lo spettro e `telive`. Quando l'intestazione di
   `telive` mostra `MCC`, `MNC` e le frequenze, sei agganciato.

Per fermare tutto: **Ferma** nel lanciatore, oppure `q` in `telive`, oppure
chiudi il lanciatore.

### La finestra dello spettro

È lo stesso pannello del flowgraph originale di SQ5BPF. In alto i controlli, in
basso due grafici:

| Elemento | A cosa serve |
|---|---|
| **Frequency** | frequenza del **canale** da ascoltare (es. `390.5M`) |
| **Fine tune** | ritocco fine della sintonia, in kHz, a caldo |
| **ppm** | correzione della frequenza a caldo |
| **gain** | guadagno RF a caldo |
| grafico **sinistro** | spettro completo della banda campionata (2 MHz): ci vedi il segnale TETRA e i canali vicini |
| grafico **IF** (destro) | il singolo canale dopo il filtro (~62,5 kHz): utile per centrare bene la sintonia |

I controlli agiscono **a caldo**: muovi `gain`, `ppm` o `Fine tune` mentre
guardi lo spettro e vedi subito l'effetto.

### I tasti di telive

L'interfaccia resta quella originale di `telive`. I più usati:

| Tasto | Effetto |
|---|---|
| `?` | aiuto (elenco completo) |
| `t` | alterna finestra SSI / finestra delle frequenze (mostra l'**AFC**) |
| `R` | attiva/disattiva la registrazione delle chiamate |
| `l` | attiva/disattiva il log della segnalazione |
| `M` / `m` | silenzia tutto / silenzia gli SSI sconosciuti |
| `q` | esci |

**Correzione fine (ppm).** Premi `t` per la finestra delle frequenze: se il
valore **AFC** è lontano da zero, ferma, ritocca la **Correzione (ppm)** nel
lanciatore (o il campo `ppm` nella finestra dello spettro) e riavvia, finché
l'AFC non è vicino a zero.

### Chiavetta in una macchina virtuale

Se Ubuntu gira in una VM il cui hypervisor **non inoltra l'USB** (es. le VM di
Apple Virtualization su Mac), la chiavetta non è visibile dentro la VM.
Soluzione: lasciala al **sistema ospitante** ed esponila via rete. Sull'host:

```bash
rtl_tcp -a 0.0.0.0 -p 1234
```

lascia quella finestra aperta e, nel lanciatore, imposta **Dispositivo** =
`rtl_tcp=INDIRIZZO_HOST:1234` (es. `rtl_tcp=192.168.64.1:1234`).

### Decifratura a chiave nota

`telive-2` può decifrare le chiamate **solo con chiavi che già possiedi**. La
catena usa `tetra-rx -k sample_keyfile`: metti la tua chiave nel file
`~/telive2/osmo-tetra-sq5bpf-2/src/sample_keyfile`. Il formato:

```
network mcc 0222 mnc 0055 ksg_type 1 security_class 2
key mcc 0222 mnc 0055 addr 00000000 key_type 16 key_num 0 key <80 bit esadecimali>
```

Con la sola chiave di esempio sentirai **solo le chiamate in chiaro**; quelle
cifrate restano mute finché non inserisci le chiavi reali che possiedi.

### Uso da riga di comando

Senza interfaccia grafica, direttamente da terminale:

```bash
~/telive2/avvia.sh 390.5                             # chiavetta automatica
~/telive2/avvia.sh 390.5 rtl=0                        # prima chiavetta
~/telive2/avvia.sh 390.5 rtl_tcp=192.168.64.1:1234   # chiavetta via rete
```

`avvia.sh` apre `telive` in questo terminale e tiene flowgraph e ricevitore in
sottofondo. Se c'è un display attivo mostra anche la finestra dello spettro; via
SSH resta headless. Per non aprirla mai: `OSMOTETRA_NOGUI=1 ~/telive2/avvia.sh 390.5`.
Guadagno e ppm si passano con `OSMOTETRA_GAIN` e `OSMOTETRA_PPM`.

### Se qualcosa non va

- **«Nessun dispositivo SDR trovato»** — la chiavetta non è vista. Controlla con
  `rtl_test -t`. `usb_claim_interface error -6` = il driver DVB-T è ancora
  caricato: scollega/ricollega la chiavetta o riavvia. In VM, usa `rtl_tcp`
  (vedi sopra).
- **«rtl_tcp non risponde»** — sull'host il comando `rtl_tcp` non è in
  esecuzione, oppure il firewall blocca la porta 1234.
- **telive si apre ma l'intestazione resta a zero** — sei sulla frequenza
  sbagliata o il segnale è troppo debole. Verifica la frequenza del canale di
  controllo e alza il guadagno. Guarda lo spettro: il segnale TETRA deve essere
  ben visibile nel grafico IF. Premi `t` in telive: se la finestra delle
  frequenze è vuota, non arriva segnale decodificabile.
- **La build di telive fallisce su nanohttp** — succede solo su libxml2 ≥ 2.14
  (Ubuntu 25.10); l'installer applica da solo la patch che lo risolve.

Tutti i log sono in `~/telive2/logs/`.

### Disinstallazione

```bash
./uninstall.sh          # conserva registrazioni e log
./uninstall.sh --purge  # rimuove tutto, compresa /tetra
```

---

## English

### What it does

The proven SQ5BPF chain, started automatically from a single launcher:

```
 RTL-SDR ─► GNU Radio flowgraph (osmotetra_rx.py)
              │        └─► spectrum window (optional): 2 plots + controls
              │  IQ samples at 36 kS/s
              ▼  UDP :42001
         receiver1udp  =  socat │ simdemod3_telive.py │ tetra-rx
              │  decoded frames
              ▼  UDP :7379
           telive  ◄── the monitor you watch: networks, SSIs, calls (ncurses)
```

When you press **Start** you get up to **three windows**:

1. **the launcher** — where you set the parameters and read the logs;
2. **the spectrum window** (optional) — two spectrum analysers and live controls
   for frequency, ppm and gain;
3. **`telive`** — the actual monitor, in a terminal, showing network, colour
   code, control channel, SSIs and calls.

The flowgraph and `receiver1udp` run **in the background** (their output shows in
the launcher's log pane). The signal chain — filter, AGC, resampler, UDP output
at 36 kS/s — is **identical** to SQ5BPF's original flowgraph: the only change is
that frequency, gain, ppm and device are passed on the command line, so the
launcher can start it on its own.

### Requirements

- **Ubuntu 24.04 or newer** (also tested on 25.10, x86 and ARM64).
- An **RTL-SDR** (or another gr-osmosdr radio: HackRF, Airspy…).
- An antenna for the TETRA band you want to receive.

### Install

```bash
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu.git
cd OsmoTetraUbuntu
./install.sh
```

Run it **as a normal user** (not with `sudo`): it asks for your password only for
`apt` and to create `/tetra`. It installs the dependencies, downloads and builds
`osmo-tetra-sq5bpf-2`, the ETSI voice codec and `telive-2`, and sets up the
launcher (the `osmotetra` command and an “OsmoTetra” entry in the app menu).

Installing **does not touch the radio**: the antenna and dongle are only needed
when you use the app, not during `./install.sh`.

When it finishes, **reopen the terminal** (or `source ~/.bashrc`) so the
`osmotetra` command is on your PATH.

### Use

Open the app: find **“OsmoTetra”** in the applications menu, or run:

```bash
osmotetra
```

In the launcher:

1. **Channel frequency** — the TETRA control-channel frequency (e.g. `390.5`
   MHz). Just type the channel frequency: the app keeps the SDR tuned 500 kHz
   away (anti-DC offset) so the signal never sits on the dongle's DC spike.
2. **RF gain** — start at `38` dB; raise it if the signal is weak.
3. **Correction (ppm)** — leave it at `0` with TCXO dongles (like the RTL-SDR
   Blog V3); otherwise adjust it (see below).
4. **Device** — “automatic” for a directly connected dongle;
   `rtl_tcp=ADDRESS:1234` if the dongle is on another machine (see “Dongle in a
   virtual machine”).
5. **Show the spectrum window** — ticked by default; untick it to start without
   the plots.
6. Press **Start**. The spectrum and `telive` open. When `telive`'s header shows
   `MCC`, `MNC` and the frequencies, you are locked on.

To stop everything: **Stop** in the launcher, or `q` in `telive`, or close the
launcher.

### The spectrum window

It is the same panel as SQ5BPF's original flowgraph. Controls on top, two plots
below:

| Element | What it does |
|---|---|
| **Frequency** | the **channel** frequency to listen to (e.g. `390.5M`) |
| **Fine tune** | fine tuning trim, in kHz, live |
| **ppm** | frequency correction, live |
| **gain** | RF gain, live |
| **left** plot | full spectrum of the sampled band (2 MHz): shows the TETRA signal and nearby channels |
| **IF** plot (right) | the single channel after the filter (~62.5 kHz): handy to center the tuning |

The controls act **live**: move `gain`, `ppm` or `Fine tune` while watching the
spectrum and you see the effect immediately.

### telive keys

The interface is `telive`'s original one. The most used keys:

| Key | Effect |
|---|---|
| `?` | help (full list) |
| `t` | toggle SSI window / frequency window (shows the **AFC**) |
| `R` | toggle call recording |
| `l` | toggle signalling log |
| `M` / `m` | mute everything / mute unknown SSIs |
| `q` | quit |

**Fine correction (ppm).** Press `t` for the frequency window: if the **AFC**
value is far from zero, stop, adjust the **Correction (ppm)** in the launcher (or
the `ppm` field in the spectrum window) and start again, until the AFC is near
zero.

### Dongle in a virtual machine

If Ubuntu runs in a VM whose hypervisor **does not forward USB** (e.g. Apple
Virtualization VMs on a Mac), the dongle is invisible inside the VM. Solution:
keep it on the **host** and expose it over the network. On the host:

```bash
rtl_tcp -a 0.0.0.0 -p 1234
```

leave that window open and, in the launcher, set **Device** =
`rtl_tcp=HOST_ADDRESS:1234` (e.g. `rtl_tcp=192.168.64.1:1234`).

### Known-key decryption

`telive-2` can decrypt calls **only with keys you already own**. The chain uses
`tetra-rx -k sample_keyfile`: put your key in
`~/telive2/osmo-tetra-sq5bpf-2/src/sample_keyfile`. Format:

```
network mcc 0222 mnc 0055 ksg_type 1 security_class 2
key mcc 0222 mnc 0055 addr 00000000 key_type 16 key_num 0 key <80-bit hex>
```

With the sample key alone you will only hear **clear calls**; encrypted ones stay
silent until you provide the real keys you legitimately own.

### Command-line use

Without the GUI, straight from a terminal:

```bash
~/telive2/avvia.sh 390.5                             # automatic dongle
~/telive2/avvia.sh 390.5 rtl=0                        # first dongle
~/telive2/avvia.sh 390.5 rtl_tcp=192.168.64.1:1234   # dongle over the network
```

`avvia.sh` opens `telive` in this terminal and keeps the flowgraph and receiver
in the background. If a display is available it also shows the spectrum window;
over SSH it stays headless. To never open it: `OSMOTETRA_NOGUI=1 ~/telive2/avvia.sh 390.5`.
Gain and ppm are passed with `OSMOTETRA_GAIN` and `OSMOTETRA_PPM`.

### Troubleshooting

- **“No SDR device found”** — the dongle isn't seen. Check with `rtl_test -t`.
  `usb_claim_interface error -6` = the DVB-T driver is still loaded: replug the
  dongle or reboot. In a VM, use `rtl_tcp` (see above).
- **“rtl_tcp not responding”** — `rtl_tcp` isn't running on the host, or a
  firewall blocks port 1234.
- **telive opens but the header stays at zero** — wrong frequency or the signal
  is too weak. Check the control-channel frequency and raise the gain. Look at
  the spectrum: the TETRA signal should be clearly visible in the IF plot. Press
  `t` in telive: if the frequency window is empty, no decodable signal is
  arriving.
- **telive build fails on nanohttp** — only on libxml2 ≥ 2.14 (Ubuntu 25.10); the
  installer applies the fix automatically.

All logs are in `~/telive2/logs/`.

### Uninstall

```bash
./uninstall.sh          # keeps recordings and logs
./uninstall.sh --purge  # removes everything, including /tetra
```

---

## Crediti / Credits

- **Jacek Lipkowski SQ5BPF** — [osmo-tetra-sq5bpf-2](https://github.com/sq5bpf/osmo-tetra-sq5bpf-2)
  e [telive-2](https://github.com/sq5bpf/telive-2), la catena di ricezione e decodifica.
- Progetto originale osmo-tetra di **Harald Welte** e collaboratori.
- Codec vocale **ETSI** EN 300 395-2.

OsmoTetra è distribuito sotto **GPL-3.0-or-later** (vedi `LICENSE`), come i
sorgenti di upstream su cui si basa.
