<p align="center"><img src="../assets/banner.svg" alt="OsmoTetra" width="100%"></p>

<p align="center"><a href="manual.en.md">🇬🇧 English</a> · <a href="manual.it.md">🇮🇹 Italiano</a></p>

<p align="center"><a href="../README.md">Project overview</a> · <a href="../SECURITY.md">Security</a> · <a href="../LICENSE">Licence</a></p>

---

## Quick Navigation

- **[What OsmoTetra does](#what-osmotetra-does)** — what OsmoTetra is and how the chain works, in short
- **[Warnings, responsibility and licence](#warnings-responsibility-and-licence)** — known-key decryption, your responsibility, the GPL licence explained in plain terms
- **[Requirements](#requirements)** — what you need before installing
- **[Install and first run (step by step)](#install-and-first-run-step-by-step)** — from a fresh Ubuntu install to your first received channel, 8 steps
- **[Command list](#command-list)** — the `osmotetra` command and all its variants
- **[Panel legend (field by field)](#panel-legend-field-by-field)** — every tab of the panel, every field, explained one by one
- **[Key editor legend](#key-editor-legend)** — every field of the graphical decryption-key editor
- **[Spectrum window legend](#spectrum-window-legend)** — every control of the spectrum window (including GNU Radio's standard ones)
- **[GNU Radio Companion (block diagram)](#gnu-radio-companion-block-diagram)** — the original block diagram, view-only
- **[telive keys](#telive-keys)** — the keys to use inside the `telive` monitor
- **[Dongle in a virtual machine](#dongle-in-a-virtual-machine)** — how to use the dongle when Ubuntu runs in a VM
- **[Troubleshooting](#troubleshooting)** — the most common errors and how to fix them
- **[Uninstall](#uninstall)** — how to remove OsmoTetra from the system

> [!TIP]
> **New here?** Jump straight to [install and first run](#install-and-first-run-step-by-step)
> — an 8-step walkthrough written for someone who has never used OsmoTetra before.

---

## What OsmoTetra does

OsmoTetra takes **Jacek Lipkowski SQ5BPF**'s TETRA monitoring chain
(`osmo-tetra-sq5bpf-2` + ETSI voice codec + `telive-2`) — normally three
separate programs you'd start by hand in three terminals, remembering the
parameters yourself — and turns it into an app with a **single graphical
panel**: you set frequency and gain, press a button, and the whole chain
starts on its own.

In short, here's what happens when you press “Avvia” (Start):

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

You don't need to understand this diagram to use the app — it's here only
for the curious. In practice what you'll see are a handful of **windows**
opening on their own (panel, GNU Radio diagram, spectrum, telive): all
explained one by one further down this guide.

This guide is written for someone who has never used OsmoTetra (or TETRA in
general) before: it follows the order — install, first run, command list,
complete legend of every tab and every field — so you can follow it start to
finish without already knowing anything.

## Warnings, responsibility and licence

> [!IMPORTANT]
> **Decryption — known keys only.** Voice decryption only works **if you
> supply a key you already legitimately own**: the software does not break,
> force, or bypass any encryption. Without the right key, encrypted calls
> simply stay silent. `telive-2` (which this part is built on) is
> experimental software, openly published by its original author.

> [!WARNING]
> **Your responsibility.** Only use this software to receive and decrypt
> traffic you are **authorized** to receive and decrypt — your own networks,
> test benches, authorized research. In many countries, listening to radio
> transmissions not addressed to you is regulated or prohibited: check the
> laws that apply in your jurisdiction before using the app. Responsibility
> for lawful use rests entirely with the person using the software, not with
> its authors.

> [!NOTE]
> **Free, open-source software.** OsmoTetra is distributed under the
> **GPL-3.0-or-later** licence (full text in [`LICENSE`](LICENSE)), the same
> one used by the upstream projects (`osmo-tetra-sq5bpf-2`, `telive-2`) it's
> built on. In practice, in plain terms:
> - You may **use, study and modify it freely**, for any purpose.
> - If you **redistribute** it — modified or not — you must do so **under
>   the same GPL licence**, with the source code available: you cannot turn
>   it into a closed product.
> - It **may not be sold as proprietary software, nor redistributed for
>   payment** while passing it off as closed commercial software: it stays
>   free and gratis for whoever receives it, in every subsequent copy.
> - It is provided **as-is, with no warranty** (neither of working correctly
>   nor of fitness for any particular purpose) — the standard for any free
>   software. See `LICENSE` for the full legal text, which takes precedence
>   over this summary if the two ever conflict.

## Requirements

- **Ubuntu 24.04 or newer** (also tested on 25.10, x86 and ARM64).
- An **RTL-SDR** (or another gr-osmosdr-supported radio: HackRF, Airspy…).
- An antenna suited to the TETRA band you want to receive.
- An Internet connection for installation (downloads ~1-2 GB between
  dependencies and sources to compile).

## Install and first run (step by step)

This section walks you, one step at a time, from a fresh Ubuntu install to
a working TETRA receiver. No prior experience is needed.

**Step 1 — Download and install.**

Open a terminal (search for “Terminal” in the applications menu, or
`Ctrl+Alt+T`) and paste:

```bash
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu.git
cd OsmoTetraUbuntu
./install.sh
```

Run it **as a normal user** (not with `sudo`: the script asks for your
password itself, only when needed, for `apt` and to create the `/tetra`
folder). The script:

1. installs all system dependencies (GNU Radio, RTL-SDR drivers,
   libraries…);
2. downloads and builds `osmo-tetra-sq5bpf-2` (the decoder), the ETSI voice
   codec, and `telive-2` (the monitor);
3. creates the `osmotetra` command and an **“OsmoTetra”** entry in the
   applications menu.

It takes a few minutes (longer on a less powerful ARM64 board). It **does
not touch the radio**: you can install it even before you have the dongle
plugged in — it's only needed when you use the app, not during
installation.

If something goes wrong during installation, the script stops with a
message explaining what happened; the full log stays in
`~/telive2/logs/install.log` to review or attach if you ask for help.

**Step 2 — Reopen the terminal.**

The `osmotetra` command is added to your `PATH` (the list of folders the
system searches for commands): for the terminal to notice, **close and
reopen it**, or run `source ~/.bashrc` in the one already open.

**Step 3 — Connect the hardware.**

Plug the RTL-SDR dongle into a USB port and screw the **antenna** onto it
(without an antenna you won't receive anything useful).

**Step 4 — Open OsmoTetra.**

Two equivalent ways:
- search for **“OsmoTetra”** in the applications menu and click it;
- or open a terminal and type `osmotetra`.

The **panel** opens: it's the main window, the one everything starts from.

**Step 5 — Set the parameters.**

In the panel, **Ricezione** (Reception) tab (already open by default):

- **Frequenza del canale** (channel frequency) — the TETRA control-channel
  frequency you want to listen to, in MHz (e.g. `390.5`). If you don't know
  it, ask whoever runs the network you want to monitor, or use the spectrum
  window (see below) to spot active carriers. Type **only** the channel
  frequency: the app keeps the SDR itself tuned 500 kHz away (a technical
  trick, the “anti-DC offset”, that keeps the signal away from the
  electrical noise every RTL-SDR dongle generates right at the centre of
  its own band).
- **Guadagno RF** (RF gain) — how much to amplify the received signal, in
  dB. The starting value (`38`) works for most dongles; if you get nothing,
  try raising it; if the signal is distorted/noisy, try lowering it.
- **Sorgente SDR** (SDR source) — leave **“Chiavetta locale (USB)”** (local
  USB dongle) if the dongle is plugged straight into this PC. (If you're
  using it from inside a virtual machine instead, see “Dongle in a virtual
  machine” below.)

Every other field has a sensible default: you don't need to touch them on
your first run. If you want to understand exactly what each one does, the
**full legend** below describes every single field in the panel.

**Step 6 — Start.**

Press the **“▶ Avvia”** (Start) button. In sequence, these open:

1. **GNU Radio Companion**, with the receiver's block diagram already
   drawn — feel free to leave it in the background, it's a view-only window
   (explained below);
2. the **spectrum window** — two plots showing the incoming radio signal;
3. **`telive`** — the actual monitor, full-screen in a terminal.

**Step 7 — Check you're actually receiving.**

Go back to the panel and open the **Stato** (Status) tab: within a few
seconds the six rows go from `·` (grey, “not known yet”) to **✓** (green,
“all good”). In particular, once the **“Rete rilevata”** (network detected)
row shows something like `MCC 222 · MNC 55 · CC 30 · ↓ 390.5000 MHz`, you
are really receiving the TETRA network.

You can also check directly in **`telive`**: the top shows **`MCC`**,
**`MNC`** and the frequencies (e.g. `MCC: 222 MNC: 55 …
Control:390.5000MHz`) instead of the initial zeros. Calls on that channel
appear in the main list and in the message window at the bottom.

Not seeing anything after a minute? Go to “Troubleshooting” below: the
Status panel already tells you where the chain stopped.

**Step 8 — Stop.**

When you're done, press **“■ Ferma”** (Stop) in the panel (or press `q`
inside `telive`): the whole chain shuts down in order, including the
windows that opened automatically.

## Command list

Everything you can do from a terminal goes through the `osmotetra` command.
Each row in the table matches a window or an action; the order goes from the
smallest “single piece” up to “everything together”:

| Command | What it does |
|---|---|
| `osmotetra` | opens the graphical **panel** — the recommended way to start |
| `osmotetra grc` | opens **only** GNU Radio Companion, with the block diagram |
| `osmotetra spettro 390.5` | opens **only** the spectrum window, on the given channel (to watch/tune without starting the rest) |
| `osmotetra monitor 390.5` | starts receiver + telive, **without** opening the spectrum |
| `osmotetra avvia 390.5` | starts **everything together**: block diagram + receiver + spectrum + telive |
| `osmotetra chiavi` | opens **only** the decryption key editor |
| `osmotetra stop` | stops the whole chain, whatever was running |
| `osmotetra aiuto` | prints this same list to the terminal |

Wherever a command accepts a frequency (`spettro`, `monitor`, `avvia`), it's
always in **MHz** and **optional**: if you omit it, the app uses whatever
value was last left in the panel (or `390.5` the very first time). After the
frequency you can also specify which SDR device to use, e.g.:

```bash
osmotetra avvia 390.5 rtl=0                          # first dongle plugged in
osmotetra avvia 390.5 rtl_tcp=192.168.64.1:1234      # dongle over the network (VM)
```

**Environment variables (advanced, terminal use).** If you launch the chain
from `avvia.sh` instead of the panel, a few details can be tuned with
environment variables, placed before the command:

| Variable | What it does | Default |
|---|---|---|
| `OSMOTETRA_HOME` | where the compiled sources live | `~/telive2` |
| `OSMOTETRA_GAIN` | RF gain in dB | `38` |
| `OSMOTETRA_PPM` | frequency correction in ppm | `0` |
| `OSMOTETRA_NOGUI` | if set, never opens the spectrum window | (unset) |
| `OSMOTETRA_NOGRC` | if set, never opens GNU Radio Companion | (unset) |
| `OSMOTETRA_LANG` | panel language: `it` or `en` | `it` |
| `OSMOTETRA_PYTHON` | Python interpreter with the GNU Radio bindings | `python3` |

Example: `OSMOTETRA_NOGRC=1 osmotetra avvia 390.5` starts everything
**except** GNU Radio Companion, just this once, without changing your saved
settings.

## Panel legend (field by field)

This section describes **every single element** of the main panel: none
should be missing. Use it as a reference whenever you're unsure what a
field does.

### Top bar (always visible)

These stay visible no matter which tab you have open:

| Element | What it does |
|---|---|
| **Modalità** (Mode) | **Base** / **Avanzata** (Advanced) selector. In **Base** you see only the essentials; in **Avanzata** the **Avanzate** tab also appears, along with ppm correction and the manual device field. Switch it any time, even while stopped. |
| **Lingua** (Language) | **Italiano** / **English** selector: changes the language of the whole panel (and the flowgraph's diagnostic messages). Changing it makes the app **restart itself** to apply it (stopping reception first, if it was running); the choice is saved for next time. |
| **▶ Avvia** (Start) | starts the whole chain with the parameters set in the Ricezione tab. Disabled while the chain is already running. |
| **■ Ferma** (Stop) | stops the whole chain (flowgraph, receiver, telive) in order. Disabled when nothing is running. |
| **◆ Chiavi di decifratura…** (Decryption keys…) | opens the key editor (see the dedicated section below). Available both while stopped and while running. |
| **Status bar** (coloured strip under the buttons) | sums up the state in one word: **grey** “Fermo” (Stopped), **yellow** “Avvio in corso…” (Starting…), **green** “In esecuzione — guarda la finestra di telive” (Running — watch the telive window). |

### “Ricezione” (Reception) tab

What you need to get started, plus saved profiles.

| Field | What it does |
|---|---|
| **Frequenza del canale** (Channel frequency) | the TETRA control-channel frequency (MHz) to listen to. Its arrow steps by 25 kHz at a time (the TETRA channel spacing); if you type a value that falls off that grid, a warning appears below the field with the nearest valid channel. |
| **Guadagno RF** (RF gain) | amplification of the received signal, in dB (0–50). Default `38`. |
| **Sorgente SDR** (SDR source) | **Chiavetta locale (USB)** (local USB dongle) if the radio is plugged into this PC; **Chiavetta remota (rete / VM)** (remote dongle, network/VM) if it's on another machine reachable over the network (typically: inside a virtual machine). |
| **Indirizzo remoto** (Remote address) (IP / port) | only shown when “Sorgente SDR” is set to remote: the IP address and port of the `rtl_tcp` service exposing the dongle over the network. See “Dongle in a virtual machine”. |
| **Mostra la finestra dello spettro (grafici + controlli)** (Show the spectrum window) | box, ticked by default. If ticked, “Avvia” also opens the spectrum window; if unticked, that window never opens (handy if you only want `telive` up front). |
| **Apri anche GNU Radio Companion (schema a blocchi)** (Also open GNU Radio Companion) | box, ticked by default (if the diagram file is present). If ticked, “Avvia” also opens GNU Radio Companion with the receiver's block diagram, view-only. See the dedicated section. |
| **Profili** (Profiles) → dropdown | list of saved profiles (free-form names, chosen by you). Selecting one fills the fields above with that profile's saved values. |
| **Profili → “Salva come…”** (Save as…) | saves the current values (frequency, gain, source, etc.) as a new profile, or updates an existing one if you reuse its name. Asks for the name in a small dialog. Profiles **never contain decryption keys**. |
| **Profili → “Elimina”** (Delete) | removes the profile selected in the dropdown, after confirmation. |

### “Stato” (Status) tab

Six rows summing up at a glance how far the chain got. Each row has a
symbol (**✓** green = all good, **!** amber = something's missing, **·**
grey = not known yet) and hovering it shows the full explanation.

| Row | What **✓** means | What **!** means |
|---|---|---|
| **Ricevitore SDR** (SDR receiver) | the radio is open and the flowgraph is running | — (if not green, check the logs: the radio probably didn't open) |
| **Segnale in arrivo** (Incoming signal) | the decoder is getting samples from the radio and measuring the frequency offset | no samples: check frequency, gain, or a disconnected antenna |
| **Sincronizzazione TETRA** (TETRA sync) | the decoder has locked onto the frame structure and is on a real control channel | not locked: you might be on a channel that isn't a control channel, or the signal is too weak |
| **Rete rilevata** (Network detected) | shows `MCC · MNC · CC · LA · ↓ frequency` read from the cell's messages | no network read so far |
| **Traffico cifrato** (Encrypted traffic) | the traffic you're hearing is in the clear | the traffic is encrypted — over the air you only know *that* it is, not *which* algorithm (see the note below) |
| **Chiavi configurate** (Configured keys) | how many keys are in the keyfile and for which network, with the chosen algorithm | — (always shows its state, even while stopped) |

> [!IMPORTANT]
> **Mind what the radio actually tells you.** Over the air TETRA signals
> **whether** traffic is encrypted, **not which algorithm** it uses. The
> algorithm (`TEA1`…`TEA7`) is something **you need to know** (from the
> network or the test bench) and choose in the key editor — the panel can't
> guess it.

### “Rete” (Network) tab

The data of the cell you're listening to, read from its network messages as
soon as reception locks onto the channel. Each field has a **`?`** to hover
for the full explanation.

| Field | What it shows |
|---|---|
| **MCC (Paese)** (MCC, Country) | *Mobile Country Code*: the network's country (e.g. `222` = Italy). |
| **MNC (rete)** (MNC, network) | *Mobile Network Code*: which network, within that country. |
| **Codice colore (CC)** (Colour code) | *Colour Code*: tells apart nearby cells on the same frequency; if it changes while you listen, you've moved to another cell. |
| **Area di localizzazione (LA)** (Location area) | *Location Area*: the group of cells terminals are registered in. |
| **Frequenza di discesa** (Downlink frequency) | the downlink control-channel frequency (network to terminals) — the one you're listening to. |
| **Cifratura** (Encryption) | whether current traffic is encrypted or in the clear (see the note in the Status tab). |
| **Ultimo aggiornamento** (Last update) | the time of the last network message received. |

Below the fields, the **“▸ Copia dettagli rete”** (Copy network details)
button copies a plain-text summary of everything above to the clipboard,
ready to paste elsewhere (a note, an email…).

### “Chiavi” (Keys) tab

A read-only summary of what's in the keyfile: how many keys, for which
network, with which algorithm. The **“◆ Apri l'editor delle chiavi…”**
(Open the key editor…) button opens the full graphical editor (described in
the next section). The file's path on disk is shown below.

### “Log” tab

| Element | What it does |
|---|---|
| **Log tecnico (mostra tutto)** (Technical log, show everything) | box, off by default. When off, the log shows only the messages meant for you (start, stop, errors). When on, it also shows the raw output of the flowgraph and receiver — handy to copy when asking for help. You can toggle it at any time without losing anything already scrolled by. |
| **▪ Esporta diagnostica…** (Export diagnostics…) | saves a text report to a file with system versions, current settings, installed components, status, network data and the last log lines — **with no keys at all**: of the keyfile it only reports how many keys there are and for which network, and any sequence that looks like a key is stripped from the log. Meant to be attached when you ask for help. |
| **Log box** | the actual text, updated live. |

### “Avanzate” (Advanced) tab (Advanced mode only)

Only shows up when **Modalità** is set to **Avanzata**; in **Base** it
disappears entirely.

| Field | What it does |
|---|---|
| **Correzione (ppm)** (Correction) | fine frequency correction, in parts per million, to compensate for the dongle's oscillator drift. Start at `0`; if `telive`'s AFC is far from zero (see “telive keys”), adjust this value. |
| **Dispositivo (manuale)** (Device, manual) | free-text field (with a few ready-made presets in the dropdown) for a hand-written `gr-osmosdr` string, e.g. `rtl=0`, `hackrf=0`, `rtl_tcp=IP:port`. If left empty, the choice made in “Sorgente SDR” on the Ricezione tab is used instead. |
| **“Dove sono le cose”** (Where things are) | a read-only summary of the paths the app uses: sources and binaries, decoder, telive monitor, keyfile, the Python interpreter with GNU Radio, and the network ports used internally. Handy for debugging or for anyone curious about the files. |

## Key editor legend

The editor opens with the **“◆ Chiavi di decifratura…”** button in the
panel, from the **Chiavi** tab, or from a terminal with `osmotetra chiavi`.
It writes the keyfile the decoder uses **without editing a text file by
hand**. It starts in **guided mode**: advanced technical fields stay hidden
until you explicitly ask for them.

### “Rete” (Network) section

| Field | What it does |
|---|---|
| **MCC** | the network's country code (e.g. `222`). Padded to 4 digits by itself when you leave the field (`222` → `0222`): that's the format the keyfile requires. |
| **MNC** | the network code within that country (e.g. `55`), padded to 4 digits the same way. |
| **↧ Usa rete rilevata** (Use detected network) | button that fills MCC and MNC for you, with values read from the air during reception. **Only enabled after** the Status panel has shown “Rete rilevata” (Network detected): if you haven't seen it yet, the button stays disabled with an explanation in its tooltip. |
| **Algoritmo (ksg_type)** (Algorithm) | `TEA1`…`TEA7` dropdown. **Pick the algorithm you know your network or test bench uses — never guess it from the country**: over the air TETRA only signals *whether* traffic is encrypted, not *which* algorithm it uses. |
| **Classe di sicurezza** (Security class) | `2` (SCK, static key) or `3` (CCK+DCK, derived keys). If you don't know which to pick, ask whoever runs the network. |

### “Chiavi” (Keys) section (table)

| Column | What it holds |
|---|---|
| **Tipo di chiave** (Key type) | what role the key plays: usually `1` (CCK/SCK); `16` is for a 32-bit shortened TEA1 key. The other entries (`2` DCK, `4` MGCK, `8` GCK) are for more specific cases. |
| **Chiave (80 bit hex)** (Key) | the key's value, in hex digits (`0`-`9`, `a`-`f`): 20 digits = 80 bit, the standard format. For type `16` (32-bit TEA1) enter the 8 digits and pad the rest with zeros up to 20 (e.g. `12345678` becomes `12345678000000000000`). The field is masked like a password; see the “Mostra chiavi” box to reveal it. |
| **MCC / MNC** *(advanced columns)* | network specific to this single key, if different from the one set above. Leave blank to use the Rete section's values. |
| **addr** *(advanced column)* | the address associated with the key (8 digits); `00000000` is fine in most cases. |
| **key_num** *(advanced column)* | the key's sequence number, when the network uses more than one of the same type. |

Above the table:

| Element | What it does |
|---|---|
| **+ Aggiungi chiave** (Add key) | adds a blank row to the table. |
| **− Rimuovi selezionata** (Remove selected) | removes the currently selected row. |
| **Mostra chiavi** (Show keys) | box: when ticked, key text becomes readable instead of masked — handy to double-check what you typed before saving. |
| **Parametri avanzati ▼** (Advanced parameters) | box: shows/hides the technical per-key columns (MCC, MNC, addr, key_num). Off by default: Type and Key are enough in most cases. |

### Buttons at the bottom

| Button | What it does |
|---|---|
| **▸ Mostra file generato** (Show generated file) | opens a read-only preview of exactly what the editor will write to the keyfile (the `network …` and `key …` lines) — without saving anything. Handy to understand the format or compare against a hand-written keyfile. |
| **Ricarica dal file** (Reload from file) | discards unsaved changes and reloads the fields from the keyfile on disk. |
| **▪ Salva** (Save) | validates the fields (warns if a key isn't hex or isn't 20 digits long), shows a summary (network, algorithm, number of keys, file path) and, after confirmation, writes the keyfile with owner-only permissions (`0600` — no other user on the PC can read it). |
| **Chiudi** (Close) | closes the editor. Unsaved changes are lost. |

> [!NOTE]
> Without keys (or with only the sample key that ships with the install)
> you will hear **clear calls only**; encrypted ones stay silent. That is
> the expected behaviour, not an error.

## Spectrum window legend

Opens together with the rest via “Avvia” (if the box in the Ricezione tab
is ticked), on its own with `osmotetra spettro 390.5`, or by pressing
“Avvia” with the box unticked and reopening it later with that same
command. It's the same panel as SQ5BPF's original flowgraph, plus GNU
Radio's standard controls for the two plots.

**Controls on top (live — the effect is immediate):**

| Element | What it does |
|---|---|
| **Frequenza canale** (Channel frequency) | shows/lets you change the frequency of the channel you're listening to (e.g. `390.5M`). |
| **Fine tune** | fine tuning trim in kHz, via slider or numeric box. |
| **ppm** | frequency correction, equivalent to the panel's “Correzione (ppm)” field. |
| **gain** | RF gain, equivalent to the panel's “Guadagno RF” field. |

**The two plots:**

| Plot | What it shows |
|---|---|
| **Left (full band)** | the full spectrum of the sampled band (2 MHz): shows the TETRA signal and nearby channels, handy to find the right carrier. |
| **IF (right)** | the single channel after the filter (~62.5 kHz of bandwidth): handy to centre the tuning well — the “flat-top” shape roughly 25 kHz wide is the sign of a TETRA carrier. |

**GNU Radio's standard controls, next to each plot** (the same for both
plots; you don't need to touch them to receive — they're for anyone who
wants to dig deeper into the spectrum):

| Element | What it does |
|---|---|
| **Trace Options → Max Hold / Min Hold** | shows the maximum/minimum value observed over time for each frequency, instead of the instantaneous value. |
| **Trace Options → Avg** | how much to average the display over time (further right = steadier but slower to react). |
| **Axis Options → Grid / Axis Labels** | shows/hides the grid and axis labels. |
| **Axis Options → Y Range (+/−) / Ref Level (+/−)** | manually adjust the plot's vertical scale (in dB). |
| **Axis Options → Autoscale** | automatically fits the vertical scale to the signal currently present. |
| **FFT → size / window** | the number of points in the Fourier transform and the windowing type used to compute the spectrum: higher values give more frequency detail but update more slowly. |
| **Trigger** | condition to “freeze” the plot on an event (defaults to `Free`, i.e. no trigger: the plot scrolls continuously). |
| **Extras → Stop** | stops updating that single plot (not reception itself). |

## GNU Radio Companion (block diagram)

Besides the windows already described, pressing **“▶ Avvia”** (Start) (or
`osmotetra avvia`) also opens **GNU Radio Companion**, GNU Radio's own
program showing the block diagram — SDR source, filter, AGC, resampler, UDP
output — already drawn and wired, exactly like the original version of the
SQ5BPF chain.

It's **view-only**: actual reception is already handled by the automated
part (the headless flowgraph started by the panel), so there's no conflict
over the dongle. Use it to look at or edit the diagram, understand how the
signal flow works, or compare its parameters with the panel's.

**To open it on its own**, without starting the rest: `osmotetra grc`, or
the **“Apri anche GNU Radio Companion (schema a blocchi)”** box in the
panel's *Ricezione* tab controls whether it opens along with everything
else (ticked by default, if the diagram file is present on disk).

> [!CAUTION]
> Don't press **Execute** inside GNU Radio Companion while reception is
> already running from the panel: it would try to open the same dongle a
> second time, and fail. Use it to look at and understand the diagram, not
> to run it in parallel with automated reception.

## telive keys

`telive`'s interface stays the original ncurses one (full-screen in the
terminal). The most used keys:

| Key | Effect |
|---|---|
| `?` | help, full list of available keys |
| `t` | toggle SSI window / frequency window (shows the **AFC**) |
| `R` | toggle call recording |
| `l` | toggle signalling log |
| `M` / `m` | mute everything / mute unknown SSIs only |
| `q` | quit `telive` (also stops the rest of the chain, if started from the panel) |

**Fine correction (ppm).** Press `t` to open the frequency window: if the
**AFC** value shown is far from zero, adjust the **ppm** field (in the
spectrum window or the panel's Avanzate tab) until it gets close to zero —
that means the dongle's oscillator has a small drift you're compensating
for by hand.

## Dongle in a virtual machine

If Ubuntu runs inside a virtual machine whose hypervisor **does not forward
USB** to the VM (this happens for instance with Apple Virtualization VMs on
a Mac), the dongle plugged into the physical computer isn't visible from
inside the VM. The fix is to leave the dongle on the **host** (the physical
Mac or PC) and expose it over the network to the VM:

1. On the **host** system (not inside the VM), install and start `rtl_tcp`:
   ```bash
   rtl_tcp -a 0.0.0.0 -p 1234
   ```
   and leave that window open for the whole session.
2. Inside the VM, in the OsmoTetra panel's Ricezione tab, set **Sorgente
   SDR** = **“Chiavetta remota (rete / VM)”**.
3. Fill in **Indirizzo remoto**: the **host's IP** (visible from the VM —
   for Apple Virtualization VMs it's typically `192.168.64.1`) and the
   **port** `1234`.

The app builds the technical string itself
(`rtl_tcp=192.168.64.1:1234`): you don't need to type it by hand.

## Troubleshooting

- **“No SDR device found”** — the dongle isn't seen by the system. Check
  with `rtl_test -t`. If you see `usb_claim_interface error -6`, the
  generic DVB-T driver is still loaded: replug the dongle or reboot the PC.
  In a VM, use `rtl_tcp` (see above).
- **“rtl_tcp not responding”** — on the host system `rtl_tcp` isn't
  running, or a firewall is blocking port `1234`.
- **`telive` opens but the header stays at zero** — look at the **Stato**
  (Status) box in the panel first: it tells you whether the **signal** is
  missing (wrong frequency, gain too low, antenna unplugged) or only the
  **sync** (that channel isn't a control channel, or there's no network
  coverage at that spot). Then look at the spectrum
  (`osmotetra spettro 390.5`): the TETRA signal should be clearly visible
  and well centred in the IF plot.
- **Encrypted calls stay silent** — normal without the right keys: open
  them with `osmotetra chiavi` and enter yours.
- **GNU Radio Companion doesn't open** — check that `gnuradio-companion` is
  installed (`which gnuradio-companion`): it's part of the `gnuradio`
  package that `install.sh` already installs, so usually just re-running
  `./install.sh` fixes it. If you don't need it, untick the box in the
  *Ricezione* tab or export `OSMOTETRA_NOGRC=1` before `avvia.sh`.
- **telive build fails on nanohttp** — only happens on libxml2 ≥ 2.14
  (Ubuntu 25.10 and newer); the installer applies the fix automatically, no
  manual action needed.
- **Need to ask for help?** In the panel, **Log** tab, tick **“Log tecnico
  (mostra tutto)”** (technical log, show everything) and copy what appears,
  or use **“▪ Esporta diagnostica…”** (Export diagnostics…) for a complete
  file ready to attach (it never contains keys).

All logs are kept in `~/telive2/logs/` regardless.

## Uninstall

```bash
./uninstall.sh          # keeps recordings and logs
./uninstall.sh --purge  # removes everything, including /tetra
```

---

## Credits

- **Jacek Lipkowski SQ5BPF** — [osmo-tetra-sq5bpf-2](https://github.com/sq5bpf/osmo-tetra-sq5bpf-2)
  and [telive-2](https://github.com/sq5bpf/telive-2), the receiving and decoding chain.
  `osmotetra_rx.grc` (the GNU Radio Companion diagram) is the author's original
  file, included unmodified from telive-2.
- Original osmo-tetra project by **Harald Welte** and contributors.
- **ETSI** EN 300 395-2 voice codec.

## Licence

OsmoTetra is distributed under **GPL-3.0-or-later** (see [`LICENSE`](LICENSE)),
like the upstream sources it's built on. It is **free, open-source software**:
you may use, study and modify it, but not resell it or redistribute it as a
paid, closed product — every copy, even a modified one, stays free for
whoever receives it.

---

<p align="center">
  <sub>Built on the TETRA monitoring chain by <a href="https://github.com/sq5bpf">Jacek Lipkowski SQ5BPF</a></sub>
</p>
