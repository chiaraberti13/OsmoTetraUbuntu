# OsmoTetra

<p align="center">
  <img src="assets/banner.svg" alt="OsmoTetra — monitoraggio TETRA su Ubuntu con osmo-tetra-sq5bpf-2 e telive-2" width="100%" />
</p>

<p align="center">
  <b>Installa, avvia e configura la suite di monitoraggio TETRA di
  <a href="https://github.com/sq5bpf/telive-2">SQ5BPF</a> (versione v2, con
  decrittazione a chiave nota) su Ubuntu 24.04 e successive —
  senza aprire tre terminali a mano ogni volta.</b>
</p>

[English](#english) | [Italiano](#italiano)

---

<a name="english"></a>
## 🇬🇧 English

### Overview

**OsmoTetra** installs, launches and configures the TETRA monitoring suite
written by Jacek Lipkowski (SQ5BPF) —
[`osmo-tetra-sq5bpf-2`](https://github.com/sq5bpf/osmo-tetra-sq5bpf-2) and
[`telive-2`](https://github.com/sq5bpf/telive-2) — on Ubuntu 24.04 and later,
using a cheap RTL-SDR dongle. This is the **experimental v2 branch**, which
adds known-key TEA1–4 voice decryption.

The decoders themselves are excellent. Getting them running is not: you have
to install around twenty packages by hand, build three separate projects, and
then **open three terminals in the right order every single time** you want to
listen, editing shell scripts to change any parameter.

This project takes care of all of that. One command installs everything; one
button starts the whole chain; a small GUI holds every parameter.

Here is what actually runs behind that button:

```
                    ┌──────────────────────────────────────────────┐
   RTL-SDR ────────►│ [1] osmotetra_rx.py   (GNU Radio 3.10)       │
                    │     one branch per channel, headless         │
                    │     + XMLRPC control server on :42000        │
                    └───────────────┬──────────────────────────────┘
                                    │ UDP :42001, :42002, ...
                    ┌───────────────▼──────────────────────────────┐
                    │ [2] one decoder per channel                  │
                    │     socat │ simdemod3_telive.py │ tetra-rx      │
                    └───────────────┬──────────────────────────────┘
                                    │ UDP :7379
                    ┌───────────────▼──────────────────────────────┐
                    │ [3] telive   (ncurses interface, 203×60)     │
                    └───────────────┬──────────────────────────────┘
                                    │
                    ┌───────────────▼──────────────────────────────┐
                    │ [4] tetrad   (optional)   ACELP ─► OGG       │
                    └──────────────────────────────────────────────┘
```

Stages **[1]** and **[2]** run as background processes with their logs inside
the application. Stage **[3]** opens automatically in a dedicated 203×60
terminal, because `telive` is an ncurses interface that needs exactly that
size.

> ⚠️ **Legal notice.** Receiving, decoding and recording TETRA traffic is
> regulated differently from country to country, and in many jurisdictions it
> is restricted or forbidden. This software is meant for educational,
> experimental and research use on traffic you are **authorised** to receive
> (your own networks, test benches, test signals). Checking and obeying the
> applicable rules is your responsibility.
>
> Nothing here breaks encryption. This branch can **decrypt** TEA1–4 voice,
> but only **with keys you already have** — it does not recover or crack keys.
> Use decryption only on traffic you are authorised to decrypt, with keys in
> your legitimate possession (your own network, a test bench, authorised
> research). See [🔓 Known-key decryption](#known-key-decryption-en) below.

### What the installer does

1. Checks that you are on Ubuntu 24.04 or later, and that `sudo` works.
2. Installs the system packages — compiler, libosmocore, GNU Radio, gr-osmosdr,
   ncurses, libxml2, socat, xterm, audio tools. All from the standard Ubuntu
   archives: **no PPA is added**.
3. Clones `osmo-tetra-sq5bpf-2` and `telive-2` and builds them, applying a
   small patch so telive-2 compiles against modern libxml2 (see
   [`patches/`](patches/)).
4. Creates the data directories in your home folder — not in `/tetra`, which
   upstream expects to exist and be owned by root.
5. Installs the application, a launcher and an **OsmoTetra** menu entry.
6. Configures the RTL-SDR dongle: blacklists the DVB-T kernel drivers that
   would otherwise grab it, reloads the udev rules, adds you to `plugdev`.
7. Optionally downloads and builds the ETSI voice codec (see below).

The installer is **idempotent**: run it again to update the upstream sources
and rebuild. It must be run as a normal user — it uses `sudo` only for `apt`
and udev.

### Requirements

- **Ubuntu 24.04 LTS or later** (should also work on recent derivatives such
  as Linux Mint and Pop!_OS).
- An internet connection.
- An **RTL-SDR** dongle (RTL2832U chip) with an antenna — needed only when you
  *use* OsmoTetra, not to install it.
- Your `sudo` password, for the system packages and the udev rules.
- About 2 GB of disk space, most of it GNU Radio.

---

### 🐧 Installation

**1. Install**

```bash
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu.git
cd OsmoTetraUbuntu
./install.sh
```

You will be asked for your `sudo` password. The process takes a few minutes,
mostly downloading GNU Radio. Everything lands under
`~/.local/share/osmotetra` — sources, compiled binaries, recordings and logs.

> ℹ️ **Do not run the installer as root.** The sources, the configuration and
> the recordings belong in your home directory, and `telive` itself is not
> meant to run as root. The installer refuses to start as root on purpose.

**2. The dongle is configured for you**

Nothing to do by hand: the installer blacklists `dvb_usb_rtl28xxu` and the
related DVB-T modules, reloads the udev rules and adds your user to the
`plugdev` group.

> ⚠️ **Required final step:** after installation, **unplug and re-plug** the
> dongle — or reboot — so the blacklist and the udev rules take effect. If the
> installer added you to `plugdev`, you also need to **log out and back in**.
> Then check it:
>
> ```bash
> rtl_test -t
> ```
>
> «Found 1 device(s)» means you are good. `usb_claim_interface error -6` means
> the DVB-T driver is still loaded → re-plug or reboot.

**3. Check the installation**

```bash
osmotetra check
```

This lists every dependency with its status and tells you exactly what to
install if something is missing. Optional entries — the voice codec, `sox`,
`oggenc` — are marked as such: their absence does not stop you from receiving.

> ℹ️ If `osmotetra` is not found, `~/.local/bin` is not in your `PATH`. Add it
> once: `echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.profile` and log in
> again.

**4. Voice codec (optional)**

Audio requires the ACELP codec from ETSI EN 300 395-2, which **cannot be
redistributed** and has to be downloaded from the ETSI website:

```bash
./install.sh --with-codec
```

The script downloads the archive, verifies its MD5, applies SQ5BPF's patch and
builds it. If the download fails it prints instructions for doing it by hand.

Without the codec everything else still works — signalling, SDS messages,
logging, KML export, frequency analysis. Only playback and recording of audio
are missing.

---

### 🚀 First run

Start it from the applications menu (**OsmoTetra**) or from a terminal:

```bash
osmotetra
```

**1. Fill in the Radio tab**

For a first attempt on a known TETRA network:

| Field | Suggested value |
| --- | --- |
| Device | leave empty (first device found), or `rtl=0` |
| Centre frequency | the control channel frequency of your network |
| Sample rate | 2.0 Ms/s |
| Decimation | 32 |
| Channel filter | 12.5 kHz |
| RF gain | 38 dB |
| Correction | your dongle's ppm error (often between 0 and 60) |

The greyed line under the fields shows what is left after decimation —
62.5 kHz with these values — and warns you if it is not enough for the channel
you asked for.

**2. Leave the Channels tab alone for now**

One channel, offset 0. The channel frequency then coincides with the centre
frequency. Point it at the **control channel**: that is where nearly all the
signalling is.

**3. Press Avvia (Start)**

Four things happen, in this order: the receiver starts, the application waits
for it to answer, the `telive` window opens, and the decoders start.

You should see:

- the status lights at the top turn green;
- a separate 203×60 terminal window with the `telive` interface;
- MCC, MNC, Colour Code and the downlink frequency in the green bar at the top
  of that window, once the control channel is decoded;
- the Log tab scrolling.

If the `telive` window shows zeroes and nothing scrolls, you are not locked on
the signal: see [If something goes wrong](#if-something-goes-wrong-en) below —
in almost every case it is the ppm correction or the frequency.

> ℹ️ **A continuous carrier is often just the control channel.** Voice only
> appears during an actual call, and only if that call is unencrypted.

---

### 🎛️ The interface

**Radio** — the receiver: device, centre frequency, sample rate, decimation,
channel filter, the three gains, ppm correction. The *Source* box at the
bottom lets you replace the radio with an IQ file or a null source, to test
the whole chain without hardware.

**Channels** — from 1 to 6 channels. For each one: an offset from the centre
frequency, the **resulting absolute frequency computed live**, the UDP port it
will use, and the `tetra-rx` flags (`-r` reassemble fragmented PDUs, `-s` show
unknown SDS as text, `-e` parse encrypted packets — which returns nonsense by
design, it decrypts nothing).

**telive** — the UDP port, which keys to "press" at startup (record, log,
mute), the SSI filter, KML export, and whether telive may drive the receiver
over XMLRPC (tuning, scanning, automatic ppm correction).

**Decrittazione (Decryption)** — turn on known-key TEA1–4 decryption, choose
the keyfile (with a preview of its format) and optionally dump the raw voice.
See [🔓 Known-key decryption](#known-key-decryption-en).

**Sistema (System)** — the terminal used for telive and its size, automatic
OGG re-compression, and the dependency list with buttons to install what is
missing.

**Log** — every stage's output in one place, filterable per stage, saveable to
a file.

> ℹ️ **Live parameters vs. restart parameters.** Frequency, gains, ppm and
> channel offsets are sent to the running receiver by the **Applica a caldo**
> (Apply live) button — no interruption. Number of channels, ports, device and
> sample rate cannot: they are fixed when the flowgraph is built, so they need
> a restart. The application shows a banner when that is the case.

---

### ⌨️ telive keys

The ncurses interface is upstream's; `?` shows the full list. The ones you
will actually use:

| Key | What it does |
| --- | --- |
| `?` | help |
| `t` | switch between the usage-identifier window and the frequency window |
| `R` | toggle recording |
| `l` | toggle logging |
| `M` / `m` | mute everything / mute unknown SSIs |
| `f` / `F` | enable the SSI filter / enter the filter expression |
| `x` | tune a channel (number, space, frequency in MHz) |
| `G` / `P` | change gain / ppm correction |
| `q` / `Q` | scan until the first network / scan without stopping |
| `d` | write the frequency report |

The full manual is `~/.local/share/osmotetra/src/telive-2/telive_doc.pdf`.

---

### 💻 Command line

Everything the GUI does is available without it.

| Command | What it does |
| --- | --- |
| `osmotetra` | opens the GUI (same as `osmotetra gui`) |
| `osmotetra check` | verifies dependencies and configuration |
| `osmotetra print-cmdline` | prints the commands of every stage **without running them** |
| `osmotetra start` | starts the chain and stays in the foreground |
| `osmotetra stop` | stops an instance started with `start` |
| `osmotetra self-test` | internal test — needs neither radio nor screen |

Useful options: `--config FILE` and `--profile NAME` pick a configuration;
`osmotetra print-cmdline --json` gives machine-readable output;
`osmotetra start --force` starts even if the pre-flight checks fail.

`print-cmdline` is the one to reach for when comparing with upstream's manual:
it prints exactly the three commands you would otherwise type by hand, in
their startup order.

**Installer options**

| Option | What it does |
| --- | --- |
| `--prefix DIR` | install somewhere else (default `~/.local/share/osmotetra`) |
| `--with-codec` | also install the ETSI ACELP voice codec |
| `--skip-apt` | do not install system packages |
| `--skip-udev` | do not touch udev or kernel modules |
| `--dry-run` | show what would be done, change nothing |

**Makefile targets**

| Target | What it does |
| --- | --- |
| `make install` | full installation |
| `make install-codec` | installation plus the voice codec |
| `make uninstall` | remove the application, keep data and configuration |
| `make purge` | remove everything, data and configuration included |
| `make check` | verify system dependencies |
| `make test` | run the internal self-test |
| `make lint` | check the syntax of scripts and sources |

---

### 🔊 Audio and recording

Audio needs the ETSI ACELP codec (`./install.sh --with-codec`). Once it is
installed:

- press `R` in telive, or tick **Registra le chiamate** in the telive tab, to
  record calls;
- raw ACELP recordings land in `~/.local/share/osmotetra/tetra/in`;
- tick **Ricomprimi automaticamente le chiamate registrate in OGG** in the
  System tab to have `tetrad` convert them into
  `~/.local/share/osmotetra/tetra/out/YYYYMMDD/*.ogg`;
- to play a raw recording by hand:
  `~/.local/share/osmotetra/tetra/bin/tplay file.out`.

Beware of the mutes: `M` silences everything, `m` silences unknown SSIs — and
`m` is **on by default** in the initial configuration.

> ℹ️ **Why voice often does not come out.** Most professional TETRA networks
> encrypt their voice (TEA1–4). Encrypted calls cannot be decoded without the
> keys, and no option here changes that: the «Cifrati (-e)» checkbox only makes
> `tetra-rx` interpret encrypted packets as if they were plaintext, which
> produces nonsense — that is upstream's behaviour too. You also need to be on
> a frequency actually carrying an unencrypted call, with enough signal. To
> decrypt with keys you hold, see the next section.

---

<a name="known-key-decryption-en"></a>
### 🔓 Known-key decryption

The v2 branch can decrypt TEA1–4 voice **if you provide the keys yourself**.
It does not recover or crack keys — it applies keys you already have.

> ⚠️ **Legitimate use only.** Use this only on traffic you are authorised to
> decrypt, with keys in your legitimate possession — your own network, a test
> bench, authorised research. Nothing here breaks encryption; it only applies
> keys you supply. Obeying the applicable laws is your responsibility.

In the **Decrittazione** (Decryption) tab: tick *Decifra le chiamate*, then
point *Keyfile* at your key file. The keyfile is a plain-text file in
format used by osmo-tetra-sq5bpf-2 — the shipped `sample_keyfile` (next to `tetra-rx`) documents it:

```
# one network per line, then its keys
network mcc 0222 mnc 55 ksg_type 2 security_class 2
key mcc 0222 mnc 55 addr 00000000 key_type 1 key_num 0 key 1111111111111111111
```

- `ksg_type`: 1 = TEA1, 2 = TEA2, 3 = TEA3, 4 = TEA4.
- `security_class`: 2 for SCK, 3 for CCK+DCK.
- `key_type`: 1 = CCK/SCK, 16 = 32-bit shortened TEA1 key (padded to 80 bits).
- `key`: the 80-bit key as a hex string.

The keys themselves are **out of scope** for this project: you bring your own.
When a call decrypts, the `tetra-rx` log shows `GET_KSG_KEY` and telive plays
it (`OK *PLAY*`). *Dump della voce* additionally writes the raw voice frames to
a directory, for offline analysis.

> ℹ️ This is SQ5BPF's experimental v2 branch. It may be less stable than v1;
> that is upstream's status, not a defect of this installer.

---

### 🧪 Testing without a radio

The Source box in the Radio tab accepts an IQ file (`file:`) or a null source.
This lets you verify that the orchestration, ports and processes work before
blaming the antenna:

```bash
osmotetra print-cmdline    # the exact commands, comparable with telive's manual
osmotetra self-test        # 31 internal checks, no radio and no screen needed
osmotetra start            # with the 'null' source: all lights green, empty logs
```

To measure the data flow between two stages — this reads the samples the
channel-1 decoder would get, so run it with that channel disabled:

```bash
timeout 3 socat -u UDP-RECV:42001 - | wc -c
# ~864000 bytes expected in 3 seconds (36000 samples/s × 8 bytes)
```

---

<a name="if-something-goes-wrong-en"></a>
### 🩺 If something goes wrong

Start with `osmotetra check`. If everything is green and still nothing
arrives, work backwards along the chain.

**Build errors**

- **`telive_receiver.h: unknown type name 'time_t'`**: `telive_receiver.h`
  declares `time_t` fields but only includes libxml2's headers and
  `stdint.h`. That used to be enough because libxml2 pulled `<time.h>` in by
  itself; since 2.12 it no longer does. The installer builds telive with
  `-include time.h`, which fixes it. If you still see this, you are on an
  older version of the installer — update the repository and re-run
  `./install.sh`. Building telive by hand in its own directory reproduces the
  error, because the flag is not there: use `make CC="gcc -include time.h"`.
- **`libxml/nanohttp.h: No such file or directory`**: telive uses libxml2's
  `nanohttp` module for XMLRPC receiver control. It is deprecated since 2.12
  and **removed in 2.14**, so telive will not build against those versions.
  The installer detects this before starting and says so. Fixing it needs a
  change upstream in telive.
- **`too many arguments to function 'timeout_receivers'`**: GCC 15 (Ubuntu
  25.10 onwards) defaults to `-std=gnu23`, and C23 changes what `()` means in a
  function definition — no longer "unspecified parameters" but "no
  parameters". telive defines `void timeout_receivers()` and calls it with an
  argument, which C23 rejects. It is a constraint violation, not a warning, so
  no `-Wno-error` removes it. The installer compiles with `-std=gnu17`, which
  restores the old meaning. Update the repository and re-run `./install.sh`.
- **Other build errors on recent Ubuntu**: GCC 14 (Ubuntu 25.04 onwards) turns
  what used to be warnings into errors — implicit function declarations,
  implicit `int`, incompatible pointer conversions, `return` without a value.
  The upstream sources, written between 2011 and 2015, contain those. The
  installer probes the matching `-Wno-error=` flags against your compiler and
  applies the supported ones. Full logs are in
  `~/.local/share/osmotetra/src/*/build.log`.

**Runtime problems**

- **`osmotetra: command not found` right after installing**: `~/.local/bin` is
  not in this session's `PATH`. Ubuntu's stock `~/.profile` already adds it,
  but **only if the directory exists at login time** — on a first install it is
  created afterwards, so the `PATH` ignores it until you log in again. Run
  `~/.local/bin/osmotetra` straight away, or
  `export PATH="$PATH:$HOME/.local/bin"` for this session, or simply log out
  and back in. The **OsmoTetra** menu entry works either way: it uses the
  absolute path.
- **«La porta UDP 7379 è già occupata» (port already in use)**: a `telive` from
  an earlier session is still alive, usually because its window was closed
  abruptly. `pkill -x telive` and try again.
- **The telive window opens and closes immediately**: open it by hand to read
  the error — `~/.local/share/osmotetra/tetra/bin/telive-run`. Usually the
  binary was not built (re-run `./install.sh`).
- **The telive screen is unreadable**: telive needs **203×60 characters**. In
  the System tab reduce the *font size*, not the window: the size is in
  characters, not pixels. If you use gnome-terminal, note that since 3.28 it
  ignores `--geometry` — install xterm (`sudo apt-get install xterm`) and set
  it as the terminal command.
- **`ModuleNotFoundError: No module named 'gnuradio.gr.gr_python'`**: another
  Python (pyenv, conda, a source build) is shadowing the system one. The
  application normally detects this by itself; to force the choice,
  `OSMOTETRA_PYTHON=/usr/bin/python3.12 osmotetra`.
- **«The SDR receiver exited right after startup» / `No devices specified`**:
  the chain stops as soon as it starts and the `rx` stage log shows «no SDR
  device found». No radio is reachable — this is not a parameter problem.
  Causes: the dongle is unplugged or held by another program; the DVB-T driver
  grabbed it (see `usb_claim_interface error -6` below); a VM that does not
  forward USB (see the next entry); or `rtl_tcp=…` set but the server not
  running (the message says so). The app detects this immediately and does not
  open telive for nothing.
- **The dongle does not show up at all, inside a virtual machine**: check with
  `lsusb | grep -i realtek` first. If nothing appears, no driver is missing —
  the device simply is not reaching the guest. Apple's **Virtualization**
  framework (what UTM uses in «Apple Virtualization» mode, recognisable from a
  hostname like `ubuntu-Apple-Virtualization-Generic-Platform`) does not
  forward arbitrary USB devices, and nothing on the Ubuntu side can change
  that. Either keep the dongle on the host and feed samples over the network —
  run `rtl_tcp -a 0.0.0.0 -p 1234` on the host, then set the device field to
  `rtl_tcp=HOST_ADDRESS:1234`, which `gr-osmosdr` supports natively — or use a
  hypervisor that does forward USB (UTM with the QEMU backend, Parallels,
  VMware Fusion), or run Ubuntu on real hardware.
- **`usb_claim_interface error -6`, or the device will not open**: the DVB-T
  kernel driver grabbed the dongle first. Run
  `sudo ~/.local/share/osmotetra/lib/scripts/50_sdr_udev.sh`, then unplug and
  re-plug the dongle.
- **`rtl_test` only works with `sudo`**: log out and back in once, so your
  `plugdev` group membership takes effect.
- **telive shows no receiver, the tuning keys do nothing**: telive looks for
  the receiver **once**, at its own startup, and never retries — not even with
  the `z` key. The application waits for the flowgraph on purpose before
  launching telive, so if this still happens, check that «Permetti a telive di
  controllare il ricevitore» is enabled and look for «server XMLRPC pronto» in
  the `rx` stage log. If you see the timeout warning instead, the SDR is taking
  too long to initialise: stop and start the chain again.
- **No audio**: install the codec (`./install.sh --with-codec`), then check the
  mutes in telive (`M` and `m`). Test the audio path on its own with
  `~/.local/share/osmotetra/tetra/bin/tplay ~/.local/share/osmotetra/src/telive-2/testfile.acelp`.
- **Traffic is visible but there is no voice**: the network is encrypted. You
  can decrypt it **only if you already hold the keys** — see
  [🔓 Known-key decryption](#known-key-decryption-en). Without the keys, voice
  cannot be recovered.
- **Signal is there but never locks**: adjust the ppm correction. In telive
  press `t` for the frequency window and watch the AFC value: bring it close to
  zero. Cheap RTL-SDR dongles are easily 50–60 ppm off, and a few kHz of error
  is enough to stop the demodulator from locking.

**Check that nothing is left running**

```bash
osmotetra stop
pgrep -ax 'socat|tetra-rx|telive'      # must print nothing
```

Note the `-x`: `pgrep -f` matches its own command line, which contains those
names, so it always seems to find something.

**Collecting information for a bug report**

```bash
osmotetra check
osmotetra print-cmdline
gnuradio-config-info -v
pkg-config --modversion libosmocore
lsb_release -d
```

Build logs live in `~/.local/share/osmotetra/src/*/build.log`; runtime logs can
be saved from the Log tab with «Salva su file».

---

### 🔧 Uninstalling

```bash
./uninstall.sh            # removes the application, keeps recordings and config
./uninstall.sh --purge    # removes everything, including data and configuration
```

Packages installed with `apt` are never removed automatically. To drop them:

```bash
sudo apt-get autoremove gnuradio gr-osmosdr libosmocore-dev
```

---

### Credits and licence

All the hard work — the demodulator, the TETRA decoder, telive — is by **Jacek
Lipkowski SQ5BPF**, and for `osmo-tetra` by **Harald Welte** and the
**Osmocom** project. This repository only contains the installation
automation, the process orchestration and the graphical interface; the
upstream sources are cloned from their original repositories at install time.

`gnuradio/osmotetra_rx.py` is derived from SQ5BPF's
`telive_*ch_gr310_udp_xmlrpc_headless.py` flowgraphs, made parametric.

Licensed under GPL-3.0 — see [LICENSE](LICENSE).

**Going deeper.** Three documents cover the design in detail — they are
written **in Italian**: [`docs/ARCHITETTURA.md`](docs/ARCHITETTURA.md) (how the
pieces fit together and why), [`docs/PARAMETRI.md`](docs/PARAMETRI.md) (every
GUI field mapped to its upstream variable) and
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md). Everything you need to
install and use the application is in this README, in both languages.

---

<a name="italiano"></a>
## 🇮🇹 Italiano

### Panoramica

**OsmoTetra** installa, avvia e configura la suite di monitoraggio TETRA
scritta da Jacek Lipkowski (SQ5BPF) —
[`osmo-tetra-sq5bpf-2`](https://github.com/sq5bpf/osmo-tetra-sq5bpf-2) e
[`telive-2`](https://github.com/sq5bpf/telive-2) — su Ubuntu 24.04 e successive,
con una comune chiavetta RTL-SDR. È la **versione sperimentale v2**, che
aggiunge la decrittazione vocale TEA1-4 a chiave nota.

I decoder in sé sono ottimi. Metterli in funzione no: bisogna installare una
ventina di pacchetti a mano, compilare tre progetti separati e poi **aprire
tre terminali nell'ordine giusto ogni volta** che si vuole ascoltare,
modificando script shell per cambiare qualsiasi parametro.

Di tutto questo si occupa questo progetto. Un comando installa tutto, un
pulsante avvia l'intera catena, una piccola interfaccia raccoglie ogni
parametro.

Ecco cosa gira davvero dietro quel pulsante:

```
                    ┌──────────────────────────────────────────────┐
   RTL-SDR ────────►│ [1] osmotetra_rx.py   (GNU Radio 3.10)       │
                    │     un ramo per canale, senza interfaccia    │
                    │     + server XMLRPC di controllo su :42000   │
                    └───────────────┬──────────────────────────────┘
                                    │ UDP :42001, :42002, ...
                    ┌───────────────▼──────────────────────────────┐
                    │ [2] un decoder per canale                    │
                    │     socat │ simdemod3_telive.py │ tetra-rx      │
                    └───────────────┬──────────────────────────────┘
                                    │ UDP :7379
                    ┌───────────────▼──────────────────────────────┐
                    │ [3] telive   (interfaccia ncurses, 203×60)   │
                    └───────────────┬──────────────────────────────┘
                                    │
                    ┌───────────────▼──────────────────────────────┐
                    │ [4] tetrad   (opzionale)   ACELP ─► OGG      │
                    └──────────────────────────────────────────────┘
```

Gli stadi **[1]** e **[2]** girano come processi in background, con i log
dentro l'applicazione. Lo stadio **[3]** si apre da solo in un terminale
dedicato da 203×60, perché `telive` è un'interfaccia ncurses che pretende
esattamente quella dimensione.

> ⚠️ **Avviso legale.** La ricezione, la decodifica e la registrazione di
> traffico TETRA sono regolate in modo diverso da paese a paese, e in molte
> giurisdizioni sono soggette a restrizioni o vietate. Questo software è
> pensato per uso didattico, sperimentale e di ricerca su traffico che si è
> **autorizzati** a ricevere (reti proprie, banchi di prova, segnali di test).
> Verificare e rispettare le norme applicabili è responsabilità di chi lo usa.
>
> Qui dentro non si rompe nessuna cifratura. Questa versione può **decifrare**
> la voce TEA1–4, ma **solo con chiavi che possiedi già** — non recupera né
> forza alcuna chiave. Usa la decrittazione solo su traffico che sei
> autorizzato a decifrare, con chiavi in tuo legittimo possesso (rete propria,
> banco di prova, ricerca autorizzata). Vedi
> [🔓 Decrittazione a chiave nota](#decrittazione-a-chiave-nota-it) più avanti.

### Cosa fa l'installer

1. Controlla che il sistema sia Ubuntu 24.04 o successiva e che `sudo` funzioni.
2. Installa i pacchetti di sistema — compilatore, libosmocore, GNU Radio,
   gr-osmosdr, ncurses, libxml2, socat, xterm, strumenti audio. Tutti dagli
   archivi standard di Ubuntu: **non viene aggiunto nessun PPA**.
3. Clona `osmo-tetra-sq5bpf-2` e `telive-2` e li compila, applicando una
   piccola patch perché telive-2 compili con libxml2 recente (vedi
   [`patches/`](patches/)).
4. Crea le directory dei dati nella tua home — non in `/tetra`, che upstream
   si aspetta esista e sia di proprietà di root.
5. Installa l'applicazione, un launcher e la voce di menu **OsmoTetra**.
6. Configura la chiavetta RTL-SDR: mette in blacklist i driver DVB-T del
   kernel che altrimenti se la prenderebbero, ricarica le regole udev, ti
   aggiunge al gruppo `plugdev`.
7. Facoltativamente scarica e compila il codec vocale ETSI (vedi sotto).

L'installer è **idempotente**: rilancialo per aggiornare i sorgenti upstream e
ricompilare. Va eseguito da utente normale — usa `sudo` solo per `apt` e udev.

### Cosa ti serve

- **Ubuntu 24.04 LTS o successiva** (dovrebbe funzionare anche su derivate
  recenti come Linux Mint e Pop!_OS).
- Una connessione a Internet.
- Una chiavetta **RTL-SDR** (chip RTL2832U) con antenna — serve solo quando
  *usi* OsmoTetra, non per installarlo.
- La password di `sudo`, per i pacchetti di sistema e le regole udev.
- Circa 2 GB di spazio su disco, in gran parte GNU Radio.

---

### 🐧 Installazione

**1. Installazione**

```bash
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu.git
cd OsmoTetraUbuntu
./install.sh
```

Ti verrà chiesta la password di `sudo`. Il processo richiede qualche minuto,
soprattutto per scaricare GNU Radio. Tutto finisce sotto
`~/.local/share/osmotetra`: sorgenti, binari compilati, registrazioni e log.

> ℹ️ **Non eseguire l'installer come root.** I sorgenti, la configurazione e le
> registrazioni vanno nella tua home, e `telive` stesso non è pensato per
> girare da root. L'installer si rifiuta di partire come root apposta.

**2. La chiavetta viene configurata da sola**

Non c'è niente da fare a mano: l'installer mette in blacklist
`dvb_usb_rtl28xxu` e i moduli DVB-T collegati, ricarica le regole udev e
aggiunge il tuo utente al gruppo `plugdev`.

> ⚠️ **Passo finale obbligatorio:** dopo l'installazione **scollega e
> reinserisci** la chiavetta — o riavvia — perché la blacklist e le regole
> udev abbiano effetto. Se l'installer ti ha aggiunto a `plugdev` devi anche
> **fare logout e login**. Poi verifica:
>
> ```bash
> rtl_test -t
> ```
>
> Se compare «Found 1 device(s)» sei a posto. `usb_claim_interface error -6`
> significa che il driver DVB-T è ancora caricato → reinserisci o riavvia.

**3. Verifica l'installazione**

```bash
osmotetra check
```

Elenca ogni dipendenza con il suo stato e dice esattamente cosa installare se
manca qualcosa. Le voci opzionali — il codec vocale, `sox`, `oggenc` — sono
segnalate come tali: la loro assenza non impedisce di ricevere.

> ℹ️ Se `osmotetra` non viene trovato, `~/.local/bin` non è nel tuo `PATH`.
> Aggiungilo una volta sola:
> `echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.profile` e rientra.

**4. Codec vocale (opzionale)**

L'audio richiede il codec ACELP di ETSI EN 300 395-2, che **non è
redistribuibile** e va scaricato dal sito ETSI:

```bash
./install.sh --with-codec
```

Lo script scarica l'archivio, ne verifica l'MD5, applica la patch di SQ5BPF e
lo compila. Se il download non riesce, stampa le istruzioni per farlo a mano.

Senza codec tutto il resto funziona lo stesso: segnalazione, messaggi SDS,
log, export KML, analisi delle frequenze. Mancano soltanto la riproduzione e
la registrazione dell'audio.

---

### 🚀 Primo avvio

Avvialo dal menu applicazioni (**OsmoTetra**) oppure da terminale:

```bash
osmotetra
```

**1. Compila la scheda Radio**

Per un primo tentativo su una rete TETRA nota:

| Campo | Valore consigliato |
| --- | --- |
| Dispositivo | lascia vuoto (primo trovato), oppure `rtl=0` |
| Frequenza centrale | la frequenza del canale di controllo della tua rete |
| Campionamento | 2,0 Ms/s |
| Decimazione | 32 |
| Filtro di canale | 12,5 kHz |
| Guadagno RF | 38 dB |
| Correzione | l'errore in ppm della tua chiavetta (spesso fra 0 e 60) |

La riga grigia sotto i campi mostra cosa resta dopo la decimazione — 62,5 kHz
con questi valori — e avvisa se non basta per il canale che hai chiesto.

**2. Per ora lascia stare la scheda Canali**

Un canale, offset 0. La frequenza del canale coincide così con quella
centrale. Puntala sul **canale di controllo**: è lì che sta quasi tutta la
segnalazione.

**3. Premi Avvia**

Succedono quattro cose, in quest'ordine: parte il ricevitore, l'applicazione
aspetta che risponda, si apre la finestra di `telive`, partono i decoder.

Dovresti vedere:

- gli indicatori di stato in alto diventare verdi;
- una finestra di terminale separata da 203×60 con l'interfaccia di `telive`;
- MCC, MNC, Colour Code e la frequenza di downlink nella barra verde in cima a
  quella finestra, appena il canale di controllo viene decodificato;
- la scheda Log che scorre.

Se la finestra di `telive` mostra zeri e non scorre niente, non stai
agganciando il segnale: vedi [Se qualcosa non va](#se-qualcosa-non-va-it) più
avanti — quasi sempre è la correzione in ppm o la frequenza.

> ℹ️ **Una portante continua spesso è solo il canale di controllo.** La voce
> compare solo durante una chiamata vera, e solo se quella chiamata non è
> cifrata.

---

### 🎛️ L'interfaccia

**Radio** — il ricevitore: dispositivo, frequenza centrale, campionamento,
decimazione, filtro di canale, i tre guadagni, correzione in ppm. Il riquadro
*Sorgente* in fondo permette di sostituire la radio con un file IQ o una
sorgente nulla, per provare tutta la catena senza hardware.

**Canali** — da 1 a 6 canali. Per ciascuno: un offset dalla frequenza
centrale, la **frequenza assoluta risultante calcolata in tempo reale**, la
porta UDP che userà e i flag di `tetra-rx` (`-r` ricompone i PDU frammentati,
`-s` mostra come testo gli SDS di protocollo ignoto, `-e` interpreta i
pacchetti cifrati — cosa che per costruzione restituisce risultati privi di
senso, non decifra nulla).

**telive** — la porta UDP, quali tasti "premere" all'avvio (registra, log,
silenzia), il filtro SSI, l'export KML, e se telive può pilotare il ricevitore
via XMLRPC (sintonia, scansione, correzione automatica del ppm).

**Decrittazione** — abilita la decifratura TEA1–4 a chiave nota, sceglie il
keyfile (con anteprima del formato) e, se vuoi, salva la voce grezza. Vedi
[🔓 Decrittazione a chiave nota](#decrittazione-a-chiave-nota-it).

**Sistema** — il terminale usato per telive e la sua dimensione, la
ricompressione automatica in OGG, e l'elenco delle dipendenze con i pulsanti
per installare ciò che manca.

**Log** — l'output di tutti gli stadi in un solo posto, filtrabile per stadio
e salvabile su file.

> ℹ️ **Parametri a caldo e parametri da riavvio.** Frequenza, guadagni, ppm e
> offset dei canali vengono mandati al ricevitore in funzione dal pulsante
> **Applica a caldo**, senza interrompere niente. Numero di canali, porte,
> dispositivo e campionamento no: sono fissati alla costruzione del flowgraph,
> quindi richiedono un riavvio. L'applicazione lo segnala con un banner.

---

### ⌨️ I tasti di telive

L'interfaccia ncurses è quella di upstream; `?` mostra l'elenco completo.
Quelli che userai davvero:

| Tasto | Effetto |
| --- | --- |
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

Il manuale completo è `~/.local/share/osmotetra/src/telive-2/telive_doc.pdf`.

---

### 💻 Riga di comando

Tutto ciò che fa la GUI è disponibile anche senza.

| Comando | Cosa fa |
| --- | --- |
| `osmotetra` | apre la GUI (come `osmotetra gui`) |
| `osmotetra check` | verifica dipendenze e configurazione |
| `osmotetra print-cmdline` | stampa i comandi di ogni stadio **senza eseguirli** |
| `osmotetra start` | avvia la catena e resta in primo piano |
| `osmotetra stop` | ferma un'istanza avviata con `start` |
| `osmotetra self-test` | collaudo interno — non richiede né radio né schermo |

Opzioni utili: `--config FILE` e `--profile NOME` scelgono la configurazione;
`osmotetra print-cmdline --json` dà un output leggibile da un programma;
`osmotetra start --force` avvia anche se i controlli preliminari falliscono.

`print-cmdline` è il comando da usare per confrontarsi con il manuale di
upstream: stampa esattamente i tre comandi che altrimenti scriveresti a mano,
nel loro ordine di avvio.

**Opzioni dell'installer**

| Opzione | Cosa fa |
| --- | --- |
| `--prefix DIR` | installa altrove (default `~/.local/share/osmotetra`) |
| `--with-codec` | installa anche il codec vocale ACELP di ETSI |
| `--skip-apt` | non installare i pacchetti di sistema |
| `--skip-udev` | non toccare udev né i moduli del kernel |
| `--dry-run` | mostra cosa farebbe, senza modificare niente |

**Target del Makefile**

| Target | Cosa fa |
| --- | --- |
| `make install` | installazione completa |
| `make install-codec` | installazione più il codec vocale |
| `make uninstall` | rimuove l'applicazione, conserva dati e configurazione |
| `make purge` | rimuove tutto, dati e configurazione compresi |
| `make check` | verifica le dipendenze di sistema |
| `make test` | esegue il collaudo interno |
| `make lint` | controlla la sintassi di script e sorgenti |

---

### 🔊 Audio e registrazione

L'audio richiede il codec ACELP di ETSI (`./install.sh --with-codec`). Una
volta installato:

- premi `R` in telive, o spunta **Registra le chiamate** nella scheda telive,
  per registrare;
- le registrazioni ACELP grezze finiscono in
  `~/.local/share/osmotetra/tetra/in`;
- spunta **Ricomprimi automaticamente le chiamate registrate in OGG** nella
  scheda Sistema per far convertire i file da `tetrad` in
  `~/.local/share/osmotetra/tetra/out/AAAAMMGG/*.ogg`;
- per riascoltare a mano una registrazione grezza:
  `~/.local/share/osmotetra/tetra/bin/tplay file.out`.

Attenzione ai silenziamenti: `M` silenzia tutto, `m` silenzia gli SSI
sconosciuti — e `m` è **attivo di default** nella configurazione iniziale.

> ℹ️ **Perché spesso la voce non esce.** La maggior parte delle reti TETRA
> professionali cifra la voce (TEA1–4). Le chiamate cifrate non sono
> decodificabili senza le chiavi, e nessuna opzione qui cambia questo fatto: la
> casella «Cifrati (-e)» fa solo interpretare a `tetra-rx` i pacchetti cifrati
> come se fossero in chiaro, e il risultato è privo di senso — è così anche in
> upstream. Serve inoltre essere su una frequenza che porti davvero una
> chiamata non cifrata, con segnale sufficiente. Per decifrare con chiavi che
> possiedi, vedi la sezione seguente.

---

<a name="decrittazione-a-chiave-nota-it"></a>
### 🔓 Decrittazione a chiave nota

La versione v2 può decifrare la voce TEA1–4 **se fornisci tu le chiavi**. Non
recupera né forza alcuna chiave: applica chiavi che hai già.

> ⚠️ **Solo uso legittimo.** Usala solo su traffico che sei autorizzato a
> decifrare, con chiavi in tuo legittimo possesso — rete propria, banco di
> prova, ricerca autorizzata. Qui dentro non si rompe nessuna cifratura: si
> applicano soltanto chiavi che fornisci tu. Rispettare le norme applicabili è
> responsabilità di chi la usa.

Nella scheda **Decrittazione**: spunta *Decifra le chiamate*, poi indica in
*Keyfile* il tuo file di chiavi. Il keyfile è un file di testo nel formato di
osmo-tetra-sq5bpf-2 — il `sample_keyfile` incluso (accanto a `tetra-rx`) lo
documenta:

```
# una rete per riga, poi le sue chiavi
network mcc 0222 mnc 55 ksg_type 2 security_class 2
key mcc 0222 mnc 55 addr 00000000 key_type 1 key_num 0 key 1111111111111111111
```

- `ksg_type`: 1 = TEA1, 2 = TEA2, 3 = TEA3, 4 = TEA4.
- `security_class`: 2 per SCK, 3 per CCK+DCK.
- `key_type`: 1 = CCK/SCK, 16 = chiave TEA1 accorciata a 32 bit (riempita a 80).
- `key`: la chiave a 80 bit come stringa esadecimale.

Le chiavi in sé sono **fuori dallo scopo** di questo progetto: le porti tu.
Quando una chiamata viene decifrata, il log di `tetra-rx` mostra `GET_KSG_KEY`
e telive la riproduce (`OK *PLAY*`). *Dump della voce* salva in più i frame
vocali grezzi in una directory, per l'analisi offline.

> ℹ️ Questa è la versione sperimentale v2 di SQ5BPF: può essere meno stabile
> della v1. È lo stato di upstream, non un difetto dell'installer.

---

### 🧪 Provare senza radio

Il riquadro Sorgente nella scheda Radio accetta un file IQ (`file:`) o una
sorgente nulla. Serve a verificare che orchestrazione, porte e processi
funzionino prima di dare la colpa all'antenna:

```bash
osmotetra print-cmdline    # i comandi esatti, confrontabili col manuale di telive
osmotetra self-test        # 31 controlli interni, senza radio e senza schermo
osmotetra start            # con sorgente 'null': indicatori verdi, log vuoti
```

Per misurare il flusso di dati fra due stadi — questo comando ruba i campioni
al decoder del canale 1, quindi va usato con quel canale disabilitato:

```bash
timeout 3 socat -u UDP-RECV:42001 - | wc -c
# attesi ~864000 byte in 3 secondi (36000 campioni/s × 8 byte)
```

---

<a name="se-qualcosa-non-va-it"></a>
### 🩺 Se qualcosa non va

Si parte sempre da `osmotetra check`. Se è tutto verde e comunque non arriva
niente, si procede a ritroso lungo la catena.

**Errori di compilazione**

- **`telive_receiver.h: unknown type name 'time_t'`**: `telive_receiver.h`
  dichiara campi `time_t` ma include solo gli header di libxml2 e `stdint.h`.
  Finora bastava, perché libxml2 tirava dentro `<time.h>` per conto suo; dalla
  2.12 non più. L'installer compila telive con `-include time.h`, che risolve.
  Se vedi ancora questo errore stai usando una versione precedente
  dell'installer: aggiorna il repository e rilancia `./install.sh`. Compilando
  telive a mano nella sua directory l'errore si ripresenta, perché il flag non
  c'è: usa `make CC="gcc -include time.h"`.
- **`libxml/nanohttp.h: No such file or directory`**: telive usa il modulo
  `nanohttp` di libxml2 per il controllo XMLRPC del ricevitore. È deprecato
  dalla 2.12 e **rimosso dalla 2.14**: su quelle versioni telive non compila.
  L'installer se ne accorge prima di iniziare e lo dice. Serve una correzione
  a monte, in telive.
- **`too many arguments to function 'timeout_receivers'`**: GCC 15 (Ubuntu
  25.10 in poi) usa `-std=gnu23` di default, e il C23 cambia il significato di
  `()` in una definizione di funzione: non più «parametri non specificati» ma
  «nessun parametro». telive definisce `void timeout_receivers()` e la chiama
  con un argomento, cosa che il C23 rifiuta. È una violazione di vincolo, non
  un warning, quindi nessun `-Wno-error` la toglie. L'installer compila con
  `-std=gnu17`, che ripristina la semantica precedente. Aggiorna il repository
  e rilancia `./install.sh`.
- **Altri errori di compilazione su Ubuntu recenti**: GCC 14 (Ubuntu 25.04 in
  poi) trasforma in errori quelli che prima erano warning — dichiarazioni
  implicite di funzione, `int` impliciti, conversioni di puntatore
  incompatibili, `return` senza valore. I sorgenti upstream, scritti fra il
  2011 e il 2015, ne contengono. L'installer prova i corrispondenti flag
  `-Wno-error=` sul compilatore in uso e applica quelli supportati. I log
  completi sono in `~/.local/share/osmotetra/src/*/build.log`.

**Problemi in esecuzione**

- **`osmotetra: command not found` subito dopo l'installazione**:
  `~/.local/bin` non è nel `PATH` di questa sessione. Il `~/.profile`
  predefinito di Ubuntu lo aggiunge già, ma **solo se la directory esiste al
  momento del login**: alla prima installazione viene creata dopo, quindi il
  `PATH` la ignora fino al prossimo accesso. Usa subito
  `~/.local/bin/osmotetra`, oppure `export PATH="$PATH:$HOME/.local/bin"` per
  questa sessione, oppure esci e rientra. La voce di menu **OsmoTetra**
  funziona comunque: usa il percorso assoluto.
- **«La porta UDP 7379 è già occupata»**: un `telive` di una sessione
  precedente è rimasto vivo, in genere perché la sua finestra è stata chiusa in
  modo brusco. `pkill -x telive` e riprova.
- **La finestra di telive si apre e si chiude subito**: aprila a mano per
  leggere l'errore — `~/.local/share/osmotetra/tetra/bin/telive-run`. Di solito
  il binario non è stato compilato (rilancia `./install.sh`).
- **Lo schermo di telive è illeggibile**: telive richiede **203×60
  caratteri**. Nella scheda Sistema riduci il *corpo del carattere*, non la
  finestra: la dimensione è in caratteri, non in pixel. Se usi gnome-terminal,
  tieni presente che dalla 3.28 ignora `--geometry`: installa xterm
  (`sudo apt-get install xterm`) e impostalo come comando del terminale.
- **`ModuleNotFoundError: No module named 'gnuradio.gr.gr_python'`**: un altro
  Python (pyenv, conda, una build da sorgente) occupa il PATH al posto di
  quello di sistema. L'applicazione di norma se ne accorge da sola; per forzare
  la scelta, `OSMOTETRA_PYTHON=/usr/bin/python3.12 osmotetra`.
- **«Il ricevitore SDR si è chiuso subito dopo l'avvio» / `No devices
  specified`**: la catena si ferma appena avviata e nel log dello stadio `rx`
  compare «Nessun dispositivo SDR trovato». Nessuna radio è raggiungibile — non
  è un problema dei parametri. Cause: chiavetta staccata o occupata da un altro
  programma; driver DVB-T che se l'è presa (vedi `usb_claim_interface error -6`
  qui sotto); VM che non inoltra l'USB (vedi la voce seguente); oppure
  `rtl_tcp=…` impostato ma server non avviato (il messaggio lo dice). L'app lo
  rileva subito e non apre telive a vuoto.
- **La chiavetta non compare per niente, dentro una macchina virtuale**:
  verifica prima con `lsusb | grep -i realtek`. Se non compare niente non
  manca nessun driver: il dispositivo non sta arrivando al sistema ospite. Il
  framework **Apple Virtualization** (quello che UTM usa in modalità «Apple
  Virtualization», riconoscibile da un hostname tipo
  `ubuntu-Apple-Virtualization-Generic-Platform`) non inoltra i dispositivi USB
  arbitrari, e nessuna configurazione lato Ubuntu può rimediare. O lasci la
  chiavetta al sistema ospitante e passi i campioni via rete — avvia
  `rtl_tcp -a 0.0.0.0 -p 1234` sull'host e scrivi come dispositivo
  `rtl_tcp=INDIRIZZO_HOST:1234`, che `gr-osmosdr` supporta nativamente —
  oppure usi un hypervisor che inoltra l'USB (UTM con backend QEMU, Parallels,
  VMware Fusion), oppure esegui Ubuntu su hardware vero.
- **`usb_claim_interface error -6`, oppure il dispositivo non si apre**: il
  driver DVB-T del kernel ha preso la chiavetta prima. Esegui
  `sudo ~/.local/share/osmotetra/lib/scripts/50_sdr_udev.sh`, poi scollega e
  reinserisci la chiavetta.
- **`rtl_test` funziona solo con `sudo`**: fai logout e login una volta, perché
  l'appartenenza al gruppo `plugdev` abbia effetto.
- **telive non mostra il ricevitore, i tasti di sintonia non funzionano**:
  telive cerca il ricevitore **una sola volta**, al proprio avvio, e non
  riprova mai — nemmeno con il tasto `z`. L'applicazione aspetta apposta il
  flowgraph prima di lanciare telive, quindi se succede lo stesso: controlla
  che «Permetti a telive di controllare il ricevitore» sia attivo e cerca
  «server XMLRPC pronto» nel log dello stadio `rx`. Se compare invece l'avviso
  di timeout, l'SDR ci sta mettendo troppo a inizializzarsi: ferma e riavvia la
  catena.
- **Nessun audio**: installa il codec (`./install.sh --with-codec`), poi
  controlla i silenziamenti in telive (`M` e `m`). Prova la catena audio da
  sola con
  `~/.local/share/osmotetra/tetra/bin/tplay ~/.local/share/osmotetra/src/telive-2/testfile.acelp`.
- **Traffico visibile ma nessuna voce**: la rete è quasi sicuramente cifrata.
  Puoi decifrarla **solo se possiedi già le chiavi** — vedi
  [🔓 Decrittazione a chiave nota](#decrittazione-a-chiave-nota-it). Senza le
  chiavi la voce non è recuperabile.
- **Il segnale c'è ma non aggancia**: regola la correzione in ppm. In telive
  premi `t` per la finestra delle frequenze e osserva il valore AFC: va portato
  vicino a zero. Le chiavette RTL-SDR economiche sbagliano tranquillamente di
  50-60 ppm, e bastano pochi kHz di scarto perché il demodulatore non agganci.

**Controllare che non resti niente in esecuzione**

```bash
osmotetra stop
pgrep -ax 'socat|tetra-rx|telive'      # non deve stampare niente
```

Nota il `-x`: `pgrep -f` corrisponde alla propria riga di comando, che contiene
quei nomi, e quindi sembra sempre trovare qualcosa.

**Raccogliere informazioni per una segnalazione**

```bash
osmotetra check
osmotetra print-cmdline
gnuradio-config-info -v
pkg-config --modversion libosmocore
lsb_release -d
```

I log di compilazione stanno in `~/.local/share/osmotetra/src/*/build.log`;
quelli di esecuzione si salvano dalla scheda Log con «Salva su file».

---

### 🔧 Disinstallazione

```bash
./uninstall.sh            # rimuove l'applicazione, conserva registrazioni e config
./uninstall.sh --purge    # rimuove tutto, dati e configurazione compresi
```

I pacchetti installati con `apt` non vengono mai rimossi automaticamente. Per
toglierli:

```bash
sudo apt-get autoremove gnuradio gr-osmosdr libosmocore-dev
```

---

### Crediti e licenza

Tutto il lavoro difficile — il demodulatore, il decoder TETRA, telive — è di
**Jacek Lipkowski SQ5BPF** e, per `osmo-tetra`, di **Harald Welte** e del
progetto **Osmocom**. Questa repository contiene solo l'automazione
dell'installazione, l'orchestrazione dei processi e l'interfaccia grafica; i
sorgenti upstream vengono clonati dai repository originali al momento
dell'installazione.

`gnuradio/osmotetra_rx.py` è derivato dai flowgraph
`telive_*ch_gr310_udp_xmlrpc_headless.py` di SQ5BPF, resi parametrici.

Licenza GPL-3.0 — vedi [LICENSE](LICENSE).

**Per approfondire.** Tre documenti descrivono il progetto in dettaglio:
[`docs/ARCHITETTURA.md`](docs/ARCHITETTURA.md) (come sono collegati i pezzi e
perché), [`docs/PARAMETRI.md`](docs/PARAMETRI.md) (ogni campo della GUI mappato
sulla variabile upstream corrispondente) e
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md). Tutto ciò che serve per
installare e usare l'applicazione è comunque in questo README.
