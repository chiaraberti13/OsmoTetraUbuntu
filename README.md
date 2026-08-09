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
(`osmo-tetra-sq5bpf-2` + codec ETSI + `telive-2`), la installa con tutte le
dipendenze e **automatizza l'avvio dei tre stadi** che di solito si aprono a
mano in tre terminali. Al posto della procedura manuale c'è una finestrella:
imposti frequenza, guadagno e dispositivo, premi **Avvia** e si apre `telive`.

> **Nota legale.** La decifratura vocale funziona **solo a chiave nota**: devi
> fornire tu chiavi che già possiedi. Non rompe alcuna cifratura. Usa questo
> software solo su traffico che sei autorizzato a ricevere e decifrare — reti
> proprie, banchi di prova, ricerca autorizzata. La responsabilità è di chi lo
> usa. `telive-2` è software sperimentale pubblicato dall'autore.

---

## Italiano

### Cosa fa

La catena provata di SQ5BPF, avviata automaticamente:

```
 RTL-SDR ─► flowgraph GNU Radio (osmotetra_rx.py, headless)
                 │  campioni IQ a 36 kS/s
                 ▼  UDP :42001
            receiver1udp  =  socat │ simdemod3_telive.py │ tetra-rx
                 │  frame decodificati
                 ▼  UDP :7379
              telive   ◄── l'interfaccia che guardi (ncurses)
```

Il flowgraph e `receiver1udp` girano **in sottofondo** (il loro output è nel
riquadro dei log del lanciatore); `telive` si apre in un terminale, perché è lì
che vedi le reti, gli SSI e le chiamate.

Il flowgraph è la versione headless del flowgraph originale di SQ5BPF: la catena
di segnale (filtro, AGC, ricampionatore, uscita UDP) è **identica** all'originale.
Cambia solo che frequenza, guadagno, ppm e dispositivo si passano da riga di
comando, così il lanciatore può avviarlo da solo.

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
`osmo-tetra-sq5bpf-2`, il codec vocale ETSI e `telive-2`, e crea il lanciatore.

L'installazione **non tocca la radio**: l'antenna e la chiavetta servono solo
quando usi l'app, non durante `./install.sh`.

Alla fine, riapri il terminale (o `source ~/.bashrc`) per avere il comando
`osmotetra` nel PATH.

### Uso

**Con l'interfaccia grafica** — cerca **«OsmoTetra»** nel menu applicazioni,
oppure da terminale:

```bash
osmotetra
```

1. **Frequenza del canale** — la frequenza del canale di controllo TETRA (es.
   `390.5` MHz). Scrivi la frequenza del canale e basta: l'app tiene l'SDR 500
   kHz più in là (offset anti-DC), così il segnale non cade sul picco DC della
   chiavetta.
2. **Guadagno RF** — parti da `38` dB; alzalo se il segnale è debole.
3. **Dispositivo** — «rilevamento automatico» per una chiavetta collegata;
   `rtl_tcp=INDIRIZZO:1234` se la chiavetta è su un'altra macchina (vedi sotto).
4. Premi **Avvia**. Si apre `telive`. Quando l'intestazione mostra `MCC`, `MNC`
   e le frequenze, sei agganciato.

**Da riga di comando** (senza GUI):

```bash
~/telive2/avvia.sh 390.5                       # chiavetta automatica
~/telive2/avvia.sh 390.5 rtl=0                 # prima chiavetta
~/telive2/avvia.sh 390.5 rtl_tcp=192.168.64.1:1234   # chiavetta via rete
```

### I tasti di telive

L'interfaccia resta quella originale di `telive`. I più usati:

| Tasto | Effetto |
|---|---|
| `?` | aiuto |
| `t` | alterna finestra SSI / finestra delle frequenze (mostra l'AFC) |
| `R` | attiva/disattiva la registrazione delle chiamate |
| `M` / `m` | silenzia tutto / silenzia gli SSI sconosciuti |
| `q` | esci |

Se nella finestra delle frequenze (`t`) l'**AFC** è lontano da zero, ferma,
alza o abbassa la **Correzione (ppm)** nel lanciatore e riavvia.

### Chiavetta in una macchina virtuale

Se Ubuntu gira in una VM il cui hypervisor **non inoltra l'USB** (es. le VM di
Apple Virtualization su Mac), la chiavetta non è visibile dentro la VM. Soluzione:
lasciala al **sistema ospitante** ed esponila via rete. Sull'host:

```bash
rtl_tcp -a 0.0.0.0 -p 1234
```

lascia quella finestra aperta e, nel lanciatore, imposta **Dispositivo** =
`rtl_tcp=INDIRIZZO_HOST:1234` (es. `rtl_tcp=192.168.64.1:1234`).

### macOS (Apple Silicon, M1–M4) — variante nativa

Su un Mac con Apple Silicon puoi usare OsmoTetra **direttamente**, senza
macchina virtuale: colleghi la chiavetta RTL-SDR al Mac e su macOS non c'è il
problema del driver DVB-T di Linux.

Prerequisito, una tantum: **Xcode Command Line Tools** —
`xcode-select --install`. Se manca **MacPorts**, lo installa da solo lo script
(dai sorgenti ufficiali): non devi scaricare nulla a mano.

Installazione e avvio:

```bash
cd OsmoTetraUbuntu
./install_macos.sh            # scarica e compila la catena via MacPorts
./avvia_macos.command 390.5   # oppure doppio clic sul file
```

`install_macos.sh` usa **MacPorts** — l'unico che su Apple Silicon fornisce
insieme `gnuradio`, `gr-osmosdr` e `osmocore` (libosmocore) funzionanti — e
applica al decoder due piccoli adattamenti macOS. `avvia_macos.command` apre
telive nella finestra del Terminale, esattamente come su Ubuntu.

> ⚠ Questa variante è **nuova e non ancora collaudata su ogni Mac**. Se un
> passo della build fallisce, copiami l'errore: si sistema come abbiamo fatto
> su Ubuntu. Il motore di segnale e il decoder sono gli stessi, provati, di
> SQ5BPF.

### Decifratura a chiave nota

`telive-2` può decifrare le chiamate **solo con chiavi che già possiedi**. La
catena usa `tetra-rx -k sample_keyfile`: metti la tua chiave nel file
`~/telive2/osmo-tetra-sq5bpf-2/src/sample_keyfile`. Il formato:

```
network mcc 0222 mnc 0055 ksg_type 1 security_class 2
key mcc 0222 mnc 0055 addr 00000000 key_type 16 key_num 0 key <80 bit esadecimali>
```

Con la sola chiave di esempio sentirai **solo le chiamate in chiaro**; quelle
cifrate restano mute finché non inserisci le chiavi reali.

### Se qualcosa non va

- **«Nessun dispositivo SDR trovato»** — la chiavetta non è vista. Controlla con
  `rtl_test -t`. `usb_claim_interface error -6` = il driver DVB-T è ancora
  caricato: scollega/ricollega la chiavetta o riavvia. In VM, usa `rtl_tcp`
  (vedi sopra).
- **«rtl_tcp non risponde»** — sull'host il comando `rtl_tcp` non è in
  esecuzione, oppure il firewall blocca la porta 1234.
- **telive si apre ma l'intestazione resta a zero** — sei sulla frequenza
  sbagliata o il segnale è troppo debole. Verifica la frequenza del canale di
  controllo e alza il guadagno. Premi `t`: se la finestra delle frequenze è
  vuota, non arriva segnale decodificabile.
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

The proven SQ5BPF chain, started automatically:

```
 RTL-SDR ─► GNU Radio flowgraph (osmotetra_rx.py, headless)
                 │  IQ samples at 36 kS/s
                 ▼  UDP :42001
            receiver1udp  =  socat │ simdemod3_telive.py │ tetra-rx
                 │  decoded frames
                 ▼  UDP :7379
              telive   ◄── the interface you watch (ncurses)
```

The flowgraph and `receiver1udp` run **in the background** (their output shows in
the launcher's log pane); `telive` opens in a terminal, because that is where you
see the networks, SSIs and calls.

The flowgraph is the headless version of SQ5BPF's original flowgraph: the signal
chain (filter, AGC, resampler, UDP output) is **identical** to the original. The
only change is that frequency, gain, ppm and device are passed on the command
line, so the launcher can start it on its own.

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

Run it **as a normal user** (not with `sudo`): it will ask for your password only
for `apt` and to create `/tetra`. It installs the dependencies, downloads and
builds `osmo-tetra-sq5bpf-2`, the ETSI voice codec and `telive-2`, and sets up the
launcher.

Installing **does not touch the radio**: the antenna and dongle are only needed
when you use the app, not during `./install.sh`.

When it finishes, reopen the terminal (or `source ~/.bashrc`) so the `osmotetra`
command is on your PATH.

### Use

**With the GUI** — find **“OsmoTetra”** in the applications menu, or run:

```bash
osmotetra
```

1. **Channel frequency** — the TETRA control-channel frequency (e.g. `390.5`
   MHz). Just type the channel frequency: the app keeps the SDR tuned 500 kHz
   away (anti-DC offset) so the signal never sits on the dongle's DC spike.
2. **RF gain** — start at `38` dB; raise it if the signal is weak.
3. **Device** — “automatic” for a directly connected dongle;
   `rtl_tcp=ADDRESS:1234` if the dongle is on another machine (see below).
4. Press **Start**. `telive` opens. When the header shows `MCC`, `MNC` and the
   frequencies, you are locked on.

**From the command line** (no GUI):

```bash
~/telive2/avvia.sh 390.5                       # automatic dongle
~/telive2/avvia.sh 390.5 rtl=0                 # first dongle
~/telive2/avvia.sh 390.5 rtl_tcp=192.168.64.1:1234   # dongle over the network
```

### telive keys

The interface is `telive`'s original one. The most used keys:

| Key | Effect |
|---|---|
| `?` | help |
| `t` | toggle SSI window / frequency window (shows AFC) |
| `R` | toggle call recording |
| `M` / `m` | mute everything / mute unknown SSIs |
| `q` | quit |

If the AFC in the frequency window (`t`) is far from zero, stop, adjust the
**Correction (ppm)** in the launcher and start again.

### Dongle in a virtual machine

If Ubuntu runs in a VM whose hypervisor **does not forward USB** (e.g. Apple
Virtualization VMs on a Mac), the dongle is invisible inside the VM. Solution:
keep it on the **host** and expose it over the network. On the host:

```bash
rtl_tcp -a 0.0.0.0 -p 1234
```

leave that window open and, in the launcher, set **Device** =
`rtl_tcp=HOST_ADDRESS:1234` (e.g. `rtl_tcp=192.168.64.1:1234`).

### macOS (Apple Silicon, M1–M4) — native variant

On an Apple Silicon Mac you can run OsmoTetra **directly**, with no virtual
machine: plug the RTL-SDR into the Mac — macOS has none of Linux's DVB-T driver
problem.

One-time prerequisite: **Xcode Command Line Tools** —
`xcode-select --install`. If **MacPorts** is missing, the script installs it
for you (from the official sources): nothing to download by hand.

Install and run:

```bash
cd OsmoTetraUbuntu
./install_macos.sh            # downloads and builds the chain via MacPorts
./avvia_macos.command 390.5   # or double-click the file
```

`install_macos.sh` uses **MacPorts** — the only one that ships working
`gnuradio`, `gr-osmosdr` and `osmocore` (libosmocore) together on Apple Silicon
— and applies two small macOS tweaks to the decoder. `avvia_macos.command`
opens telive in the Terminal window, exactly like on Ubuntu.

> ⚠ This variant is **new and not yet tested on every Mac**. If a build step
> fails, send me the error: we'll fix it just like we did on Ubuntu. The signal
> engine and the decoder are the same, proven, SQ5BPF ones.

### Known-key decryption

`telive-2` can decrypt calls **only with keys you already own**. The chain uses
`tetra-rx -k sample_keyfile`: put your key in
`~/telive2/osmo-tetra-sq5bpf-2/src/sample_keyfile`. Format:

```
network mcc 0222 mnc 0055 ksg_type 1 security_class 2
key mcc 0222 mnc 0055 addr 00000000 key_type 16 key_num 0 key <80-bit hex>
```

With the sample key alone you will only hear **clear calls**; encrypted ones stay
silent until you provide the real keys.

### Troubleshooting

- **“No SDR device found”** — the dongle isn't seen. Check with `rtl_test -t`.
  `usb_claim_interface error -6` = the DVB-T driver is still loaded: replug the
  dongle or reboot. In a VM, use `rtl_tcp` (see above).
- **“rtl_tcp not responding”** — `rtl_tcp` isn't running on the host, or a
  firewall blocks port 1234.
- **telive opens but the header stays at zero** — wrong frequency or the signal
  is too weak. Check the control-channel frequency and raise the gain. Press `t`:
  if the frequency window is empty, no decodable signal is arriving.
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
