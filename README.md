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
mano in tre terminali.

> **Nota legale.** La decifratura vocale funziona **solo a chiave nota**: devi
> fornire tu chiavi che già possiedi. Non rompe alcuna cifratura. Usa questo
> software solo su traffico che sei autorizzato a ricevere e decifrare — reti
> proprie, banchi di prova, ricerca autorizzata. La responsabilità è di chi lo
> usa. `telive-2` è software sperimentale pubblicato dall'autore.

---

## Italiano

### Cosa fa

La catena provata di SQ5BPF, avviata automaticamente da un unico comando:

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

Quando avvii vedi fino a **tre finestre**: il **pannello** (dove imposti i
parametri), la **finestra dello spettro** (grafici + controlli a caldo) e
**`telive`** (il monitor che decodifica). Puoi aprirle tutte insieme oppure una
alla volta, come preferisci.

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
`osmo-tetra-sq5bpf-2`, il codec vocale ETSI e `telive-2`, e crea il comando
`osmotetra` e la voce «OsmoTetra» nel menu applicazioni.

L'installazione **non tocca la radio**: antenna e chiavetta servono solo quando
usi l'app, non durante `./install.sh`.

Al termine, **riapri il terminale** (o `source ~/.bashrc`) per avere il comando
`osmotetra` nel PATH.

### Primo avvio (guida passo passo)

1. **Collega** la chiavetta RTL-SDR al PC e avvita l'**antenna**.
2. **Apri OsmoTetra**: cerca **«OsmoTetra»** nel menu applicazioni, oppure apri
   un terminale e scrivi `osmotetra`.
3. Nel **pannello** imposta:
   - **Frequenza del canale** = la frequenza del canale di controllo TETRA che
     vuoi ascoltare (es. `390.5` MHz). Scrivi solo la frequenza del canale:
     l'app tiene l'SDR 500 kHz più in là (offset anti-DC) così il segnale non
     cade sul picco disturbato della chiavetta.
   - **Guadagno RF** = parti da `38` dB; se non ricevi, alzalo.
   - **Dispositivo** = lascia «rilevamento automatico» se la chiavetta è
     collegata direttamente.
4. Premi **Avvia**. Si aprono la **finestra dello spettro** e **`telive`**.
5. Guarda **`telive`**: quando in alto compaiono **`MCC`**, **`MNC`** e le
   frequenze (es. `MCC: 222 MNC: 55 … Control:390.5000MHz`), stai ricevendo la
   rete. Le chiamate compaiono nell'elenco e nella finestra dei messaggi.
6. Per **fermare**: premi **Ferma** nel pannello, oppure `q` dentro `telive`.

Non ricevi nulla? Vai a **«Se qualcosa non va»** più in basso.

### Il comando `osmotetra`

Tutto passa da un solo comando. Puoi avviare tutto insieme, oppure aprire solo
la finestra che ti serve:

| Comando | Cosa fa |
|---|---|
| `osmotetra` | apre il **pannello** (finestra 1) — il modo consigliato |
| `osmotetra avvia 390.5` | avvia **tutto**: ricevitore + spettro + telive |
| `osmotetra spettro 390.5` | apre **solo la finestra dello spettro** (per sintonizzare) |
| `osmotetra monitor 390.5` | avvia **solo telive** (senza la finestra dello spettro) |
| `osmotetra chiavi` | apre l'**editor delle chiavi** di decifratura |
| `osmotetra stop` | ferma tutto |
| `osmotetra aiuto` | mostra l'elenco dei comandi |

Dopo la frequenza puoi aggiungere il dispositivo, es.
`osmotetra avvia 390.5 rtl=0` oppure `osmotetra avvia 390.5 rtl_tcp=192.168.64.1:1234`.

### Le tre finestre

- **Pannello** *(finestra 1)* — il pannello di controllo: imposti i parametri,
  premi Avvia/Ferma e leggi i log. Lo apri con `osmotetra`.
- **Finestra dello spettro** *(finestra 2)* — due grafici e i controlli a caldo.
  Si apre insieme al resto se la casella «Mostra la finestra dello spettro» è
  spuntata; da sola con `osmotetra spettro 390.5`; per non aprirla mai togli la
  spunta oppure usa `osmotetra monitor …`.
- **`telive`** *(finestra 3)* — il monitor vero e proprio, in un terminale. Si
  apre con Avvia, oppure da solo (senza spettro) con `osmotetra monitor 390.5`.

### La finestra dello spettro

È lo stesso pannello del flowgraph originale di SQ5BPF. In alto i controlli, in
basso due grafici:

| Elemento | A cosa serve |
|---|---|
| **Frequency** | frequenza del **canale** da ascoltare (es. `390.5M`) |
| **Fine tune** | ritocco fine della sintonia, in kHz, a caldo |
| **ppm** | correzione della frequenza a caldo |
| **gain** | guadagno RF a caldo |
| grafico **sinistro** | spettro completo della banda (2 MHz): ci vedi il segnale TETRA e i canali vicini |
| grafico **IF** (destro) | il singolo canale dopo il filtro (~62,5 kHz): utile per centrare la sintonia |

I controlli agiscono **a caldo**: muovi `gain`, `ppm` o `Fine tune` mentre
guardi lo spettro e vedi subito l'effetto.

### Le chiavi di decifratura (con l'interfaccia)

Per decifrare le chiamate serve una **chiave che già possiedi**. Non devi più
modificare a mano il file di testo: c'è un editor grafico.

**Come aprirlo:** premi il pulsante **«🔑 Chiavi di decifratura…»** nel pannello,
oppure da terminale `osmotetra chiavi`.

**Come si usa** (parte in **modalità guidata**: vedi solo l'essenziale):

1. In alto, sezione **Rete**, compila:
   - **MCC** e **MNC** della rete (es. `222` e `55`): l'editor li completa da solo
     a 4 cifre (`222` → `0222`);
   - **Algoritmo (ksg_type)**: scegli `TEA1`…`TEA7`. **Seleziona l'algoritmo
     previsto dalla tua rete o dal tuo banco di prova — non sceglierlo in base al
     Paese.** (Via etere TETRA segnala *se* il traffico è cifrato, non *quale*
     algoritmo: quello lo sai tu.)
   - **Classe di sicurezza**: `2` (SCK) oppure `3` (CCK+DCK).
2. In basso, tabella **Chiavi**, per ogni chiave premi **«+ Aggiungi chiave»** e
   compila:
   - **Tipo di chiave**: di solito `1 — CCK/SCK`, oppure `16` per una chiave TEA1
     accorciata a 32 bit;
   - **Chiave**: la chiave in **esadecimale a 80 bit** (20 cifre). Per il tipo
     `16` metti le 8 cifre e riempi con zeri fino a 20 (es. `12345678000000000000`).
     È mascherata; spunta **«Mostra chiavi»** per vederla.
   - I campi tecnici (`addr`, `key_num`, MCC/MNC per singola chiave) sono nascosti:
     compaiono spuntando **«Parametri avanzati ▼»**.
3. (Facoltativo) **«🔎 Mostra file generato»** ti fa vedere esattamente cosa
   scriverà l'editor (`network …` / `key …`): utile per imparare il formato.
4. Premi **💾 Salva**. Ti mostra un riepilogo (rete, algoritmo, numero di chiavi,
   file), poi scrive il keyfile con permessi riservati al tuo utente (`0600`).
5. **Avvia (o riavvia)** la ricezione: adesso le chiamate cifrate con quelle
   chiavi vengono decifrate.

> Senza chiavi (o con la sola chiave d'esempio) sentirai **solo le chiamate in
> chiaro**; quelle cifrate restano mute. È normale.

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
valore **AFC** è lontano da zero, ritocca il campo **ppm** (nella finestra dello
spettro o nel pannello) finché non si avvicina a zero.

### Chiavetta in una macchina virtuale

Se Ubuntu gira in una VM il cui hypervisor **non inoltra l'USB** (es. le VM di
Apple Virtualization su Mac), la chiavetta non è visibile dentro la VM.
Soluzione: lasciala al **sistema ospitante** ed esponila via rete. Sull'host:

```bash
rtl_tcp -a 0.0.0.0 -p 1234
```

lascia quella finestra aperta e, nel pannello, imposta **Dispositivo** =
`rtl_tcp=INDIRIZZO_HOST:1234` (es. `rtl_tcp=192.168.64.1:1234`).

### Se qualcosa non va

- **«Nessun dispositivo SDR trovato»** — la chiavetta non è vista. Controlla con
  `rtl_test -t`. `usb_claim_interface error -6` = il driver DVB-T è ancora
  caricato: scollega/ricollega la chiavetta o riavvia. In VM, usa `rtl_tcp`.
- **«rtl_tcp non risponde»** — sull'host il comando `rtl_tcp` non è in
  esecuzione, oppure il firewall blocca la porta 1234.
- **telive si apre ma l'intestazione resta a zero** — sei sulla frequenza
  sbagliata o il segnale è troppo debole. Verifica la frequenza del canale di
  controllo e alza il guadagno. Guarda lo spettro (`osmotetra spettro 390.5`):
  il segnale TETRA deve essere ben visibile nel grafico IF.
- **Le chiamate cifrate restano mute** — normale senza le chiavi giuste: aprile
  con `osmotetra chiavi` e inserisci le tue.
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

The proven SQ5BPF chain, started automatically from a single command:

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

When you start it you get up to **three windows**: the **panel** (where you set
the parameters), the **spectrum window** (plots + live controls) and **`telive`**
(the monitor that decodes). You can open them all together or one at a time, as
you prefer.

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
`osmo-tetra-sq5bpf-2`, the ETSI voice codec and `telive-2`, and creates the
`osmotetra` command and an “OsmoTetra” entry in the app menu.

Installing **does not touch the radio**: the antenna and dongle are only needed
when you use the app, not during `./install.sh`.

When it finishes, **reopen the terminal** (or `source ~/.bashrc`) so the
`osmotetra` command is on your PATH.

### First run (step by step)

1. **Plug in** the RTL-SDR dongle and screw on the **antenna**.
2. **Open OsmoTetra**: find **“OsmoTetra”** in the applications menu, or open a
   terminal and type `osmotetra`.
3. In the **panel** set:
   - **Channel frequency** = the TETRA control-channel frequency you want to
     listen to (e.g. `390.5` MHz). Just type the channel frequency: the app
     keeps the SDR tuned 500 kHz away (anti-DC offset) so the signal never sits
     on the dongle's noisy DC spike.
   - **RF gain** = start at `38` dB; if you get nothing, raise it.
   - **Device** = leave “automatic” if the dongle is directly connected.
4. Press **Start**. The **spectrum window** and **`telive`** open.
5. Look at **`telive`**: when the top shows **`MCC`**, **`MNC`** and the
   frequencies (e.g. `MCC: 222 MNC: 55 … Control:390.5000MHz`), you are
   receiving the network. Calls appear in the list and in the message window.
6. To **stop**: press **Stop** in the panel, or `q` inside `telive`.

Nothing received? See **“Troubleshooting”** below.

### The `osmotetra` command

Everything goes through one command. You can start it all together, or open just
the window you need:

| Command | What it does |
|---|---|
| `osmotetra` | opens the **panel** (window 1) — recommended |
| `osmotetra avvia 390.5` | starts **everything**: receiver + spectrum + telive |
| `osmotetra spettro 390.5` | opens **only the spectrum window** (to tune) |
| `osmotetra monitor 390.5` | starts **only telive** (without the spectrum window) |
| `osmotetra chiavi` | opens the **key editor** for decryption |
| `osmotetra stop` | stops everything |
| `osmotetra aiuto` | shows the list of commands |

After the frequency you can add the device, e.g.
`osmotetra avvia 390.5 rtl=0` or `osmotetra avvia 390.5 rtl_tcp=192.168.64.1:1234`.

### The three windows

- **Panel** *(window 1)* — the control panel: set the parameters, press
  Start/Stop and read the logs. Open it with `osmotetra`.
- **Spectrum window** *(window 2)* — two plots and live controls. It opens with
  everything else if “Show the spectrum window” is ticked; on its own with
  `osmotetra spettro 390.5`; to never open it, untick the box or use
  `osmotetra monitor …`.
- **`telive`** *(window 3)* — the actual monitor, in a terminal. Opens with
  Start, or on its own (no spectrum) with `osmotetra monitor 390.5`.

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

### Decryption keys (with the editor)

To decrypt calls you need a **key you already own**. You no longer edit the text
file by hand: there is a graphical editor.

**How to open it:** press the **“🔑 Chiavi di decifratura…”** button in the panel,
or from a terminal `osmotetra chiavi`.

**How to use it** (it starts in **guided mode**: you only see the essentials):

1. At the top, **Rete** (Network) section, fill in:
   - the network's **MCC** and **MNC** (e.g. `222` and `55`): the editor pads them
     to 4 digits by itself (`222` → `0222`);
   - **Algoritmo (ksg_type)**: choose `TEA1`…`TEA7`. **Pick the algorithm your
     network or test setup uses — do not choose it by country.** (Over the air
     TETRA signals *whether* traffic is encrypted, not *which* algorithm: that
     part is your knowledge.)
   - **Classe di sicurezza** (security class): `2` (SCK) or `3` (CCK+DCK).
2. At the bottom, **Chiavi** (Keys) table, for each key press **“+ Aggiungi
   chiave”** and fill in:
   - **Tipo di chiave** (key type): usually `1 — CCK/SCK`, or `16` for a 32-bit
     shortened TEA1 key;
   - **Chiave** (key): the key in **80-bit hex** (20 digits). For type `16` enter
     the 8 digits and pad with zeros up to 20 (e.g. `12345678000000000000`). It is
     masked; tick **“Mostra chiavi”** to reveal it.
   - The technical fields (`addr`, `key_num`, per-key MCC/MNC) are hidden: they
     appear when you tick **“Parametri avanzati ▼”**.
3. (Optional) **“🔎 Mostra file generato”** shows exactly what the editor will
   write (`network …` / `key …`): handy to learn the format.
4. Press **💾 Salva** (Save). It shows a summary (network, algorithm, number of
   keys, file), then writes the keyfile with owner-only permissions (`0600`).
5. **Start (or restart)** reception: calls encrypted with those keys are now
   decrypted.

> Without keys (or with only the sample key) you will hear **clear calls only**;
> encrypted ones stay silent. That is expected.

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
value is far from zero, adjust the **ppm** field (in the spectrum window or the
panel) until it is near zero.

### Dongle in a virtual machine

If Ubuntu runs in a VM whose hypervisor **does not forward USB** (e.g. Apple
Virtualization VMs on a Mac), the dongle is invisible inside the VM. Solution:
keep it on the **host** and expose it over the network. On the host:

```bash
rtl_tcp -a 0.0.0.0 -p 1234
```

leave that window open and, in the panel, set **Device** =
`rtl_tcp=HOST_ADDRESS:1234` (e.g. `rtl_tcp=192.168.64.1:1234`).

### Troubleshooting

- **“No SDR device found”** — the dongle isn't seen. Check with `rtl_test -t`.
  `usb_claim_interface error -6` = the DVB-T driver is still loaded: replug the
  dongle or reboot. In a VM, use `rtl_tcp`.
- **“rtl_tcp not responding”** — `rtl_tcp` isn't running on the host, or a
  firewall blocks port 1234.
- **telive opens but the header stays at zero** — wrong frequency or the signal
  is too weak. Check the control-channel frequency and raise the gain. Look at
  the spectrum (`osmotetra spettro 390.5`): the TETRA signal should be clearly
  visible in the IF plot.
- **Encrypted calls stay silent** — normal without the right keys: open them with
  `osmotetra chiavi` and enter yours.
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
