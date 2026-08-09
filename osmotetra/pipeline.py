"""Orchestrazione della catena di ricezione.

Sostituisce i tre terminali che il manuale di telive fa aprire a mano:

  1. ``rx``      — il flowgraph GNU Radio (osmotetra_rx.py)
  2. ``demod-N`` — ``socat | simdemod3_py3.py | tetra-rx``, uno per canale
                   (l'equivalente di ``receiver1udp N``)
  3. ``telive``  — l'interfaccia ncurses, in un terminale da 203x60
  4. ``tetrad``  — opzionale, ricompressione ACELP → OGG

Ordine di avvio: **prima il ricevitore, poi telive, poi i decoder**.

Il vincolo viene da telive: ``grxml_discover_receiver()`` è invocata una sola
volta, all'avvio (telive.c:2891). Se in quel momento il server XMLRPC del
flowgraph non risponde, telive considera il ricevitore assente per tutta la
sessione — e non c'è modo di rimediare senza riavviarlo, perché anche il
tasto ``z`` chiama ``grxml_update_receivers()``, non la scoperta. Perdere il
primo secondo di campioni o di pacchetti decodificati è invece innocuo: è
traffico UDP su loopback verso porte non ancora aperte.

L'arresto avviene in ordine inverso.

Ogni stadio ``demod-N`` è una pipeline di tre processi lanciata via shell:
terminarla richiede di uccidere l'intero gruppo di processi, non solo la
shell, altrimenti socat e tetra-rx restano orfani.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import errno
import os
import shlex
import signal
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from . import deps, paths, telive_env
from .config import Config
from .xmlrpc_ctl import ReceiverControl

#: Righe di log conservate per stadio.
LOG_BUFFER_LINES = 4000
#: Attesa fra SIGTERM e SIGKILL.
TERM_GRACE_SECONDS = 5.0
#: Quanto attendere che il server XMLRPC del flowgraph risponda prima di
#: avviare telive. Con una RTL-SDR l'inizializzazione richiede un paio di
#: secondi; con --source file: è quasi immediata.
RECEIVER_WAIT_SECONDS = 20.0


class StageState(Enum):
    STOPPED = "fermo"
    STARTING = "avvio"
    RUNNING = "attivo"
    FAILED = "errore"


@dataclass
class Stage:
    """Un processo della catena."""

    key: str
    label: str
    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    #: Se True la morte del processo non è considerata un guasto della catena
    #: (è il caso di telive, che l'utente può chiudere con 'q').
    optional: bool = False

    process: subprocess.Popen | None = None
    state: StageState = StageState.STOPPED
    log: deque[str] = field(default_factory=lambda: deque(maxlen=LOG_BUFFER_LINES))
    exit_code: int | None = None
    _reader: threading.Thread | None = None

    @property
    def cmdline(self) -> str:
        return " ".join(shlex.quote(a) for a in self.argv)

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None


class Pipeline:
    """Avvia, sorveglia e ferma tutti gli stadi."""

    def __init__(self, cfg: Config,
                 on_log: Callable[[str, str], None] | None = None,
                 on_state: Callable[[str, StageState], None] | None = None):
        self.cfg = cfg
        self._on_log = on_log
        self._on_state = on_state
        self.stages: list[Stage] = []
        self._lock = threading.Lock()
        self._python = deps.find_gnuradio_python()[0] or "python3"
        #: True durante stop(): serve a non segnalare come guasti i processi
        #: che stiamo terminando noi.
        self._stopping = False

    # -- costruzione dei comandi ------------------------------------------

    def build_stages(self) -> list[Stage]:
        """Costruisce gli stadi senza avviarli.

        Utile anche da sola: ``osmotetra print-cmdline`` la usa per mostrare
        i comandi equivalenti a quelli che si darebbero a mano.

        Se la catena non è in esecuzione il risultato diventa anche l'elenco
        corrente di ``self.stages``, così ``stage()`` è interrogabile senza
        aver prima avviato nulla.

        L'ordine della lista è quello di avvio (vedi il commento in testa al
        modulo): ricevitore, telive, decoder, ricompressione.
        """
        cfg = self.cfg
        stages: list[Stage] = [self._rx_stage(), self._telive_stage()]
        stages += [self._demod_stage(idx, ch) for idx, ch in cfg.active_channels]
        if cfg.recording.tetrad_enabled:
            stages.append(self._tetrad_stage())
        if not self.is_running():
            with self._lock:
                self.stages = stages
        return stages

    def _rx_stage(self) -> Stage:
        cfg, sdr = self.cfg, self.cfg.sdr
        argv = [
            self._python, str(paths.flowgraph()),
            "--channels", str(len(cfg.channels)),
            "--freq", repr(sdr.freq_hz),
            "--samp-rate", repr(sdr.samp_rate),
            "--first-decim", str(sdr.first_decim),
            "--lowpass", repr(sdr.lowpass_hz),
            "--gain", repr(sdr.gain),
            "--if-gain", repr(sdr.if_gain),
            "--bb-gain", repr(sdr.bb_gain),
            "--ppm", repr(sdr.ppm),
            "--udp-host", cfg.udp_host,
            "--base-port", str(cfg.base_port),
            "--source", sdr.source,
        ]
        # Gli offset vanno passati per tutti i canali, non solo per quelli
        # abilitati: la posizione nell'elenco determina la porta UDP.
        for ch in cfg.channels:
            argv += ["--offset", repr(ch.offset_hz)]
        if sdr.device_args:
            argv += ["--device-args", sdr.device_args]
        if sdr.antenna:
            argv += ["--antenna", sdr.antenna]
        if sdr.bandwidth_hz:
            argv += ["--bandwidth", repr(sdr.bandwidth_hz)]
        if sdr.source.startswith("file:") and sdr.repeat_file:
            argv.append("--repeat")

        return Stage(
            key="rx",
            label="Ricevitore SDR",
            argv=argv,
            cwd=paths.flowgraph().parent,
            env={"PYTHONUNBUFFERED": "1"},
        )

    def _demod_stage(self, index1: int, channel) -> Stage:
        """Equivalente parametrizzato di ``receiver1udp N``.

        Upstream lo script cabla la porta 7379 e i flag ``-r -s``; qui
        arrivano dalla configurazione.
        """
        cfg = self.cfg
        udp_port = cfg.channel_udp_port(index1)
        src = paths.osmo_tetra_src()

        flags = channel.tetra_rx_flags()
        # Decrittazione a chiave nota e dump della voce (novità della v2):
        # aggiungono -k <keyfile> e -d <dumpdir> agli argomenti di tetra-rx.
        flags += cfg.decrypt.tetra_rx_flags()

        pipeline = (
            f"set -o pipefail; "
            f"socat -b 4096 UDP-RECV:{udp_port} STDOUT "
            f"| {shlex.quote(self._python)} {shlex.quote(str(paths.simdemod()))} "
            f"| {shlex.quote(str(paths.tetra_rx()))} "
            f"{' '.join(shlex.quote(f) for f in flags)} /dev/stdin"
        )

        return Stage(
            key=f"demod-{index1}",
            label=f"Decoder canale {index1}",
            argv=["bash", "-c", pipeline],
            # simdemod3_telive.py importa simdemod3_telive_send_udp_to_telive
            # dalla propria directory: senza questa cwd l'import fallisce.
            cwd=src / "demod",
            env={
                # Lette da tetra-rx (tetra-rx.c) e da simdemod3 per sapere
                # dove mandare i dati decodificati e i messaggi AFC.
                "TETRA_HACK_PORT": str(cfg.telive.udp_port),
                "TETRA_HACK_IP": "127.0.0.1",
                "TETRA_HACK_RXID": str(index1),
                "PYTHONUNBUFFERED": "1",
            },
        )

    def _telive_stage(self) -> Stage:
        """Apre telive in un terminale della dimensione che pretende."""
        cfg = self.cfg
        runner = telive_env.write_runner_script(cfg)
        argv = _terminal_argv(cfg.terminal, "telive — OsmoTetra", str(runner))
        return Stage(
            key="telive",
            label="telive",
            argv=argv,
            cwd=paths.telive_src(),
            # L'utente può chiudere telive con 'q' senza che questo significhi
            # che la catena è guasta.
            optional=True,
        )

    def _tetrad_stage(self) -> Stage:
        return Stage(
            key="tetrad",
            label="Ricompressione OGG",
            argv=[str(paths.tetra_bin() / "tetrad")],
            cwd=paths.tetra_dir(),
            env={
                "TETRA_OUTDIR": str(paths.tetra_dir() / "in"),
                "TETRA_OGGDIR": str(paths.tetra_dir() / "out"),
            },
            optional=True,
        )

    # -- avvio e arresto ---------------------------------------------------

    def preflight(self) -> list[str]:
        """Controlli da fare prima di avviare: restituisce i problemi trovati."""
        problems = list(self.cfg.validate())

        for check in deps.blocking_failures():
            problems.append(f"Dipendenza mancante — {check.name}: {check.detail}")

        for port, what in self._ports_to_check():
            if _udp_port_busy(port):
                problems.append(
                    f"La porta UDP {port} ({what}) è già occupata: "
                    f"un'altra istanza è in esecuzione?"
                )

        problems.extend(check_rtl_tcp(self.cfg))
        return problems

    def _ports_to_check(self) -> Iterable[tuple[int, str]]:
        yield self.cfg.telive.udp_port, "telive"
        for idx, _ in self.cfg.active_channels:
            yield self.cfg.channel_udp_port(idx), f"canale {idx}"

    def start(self, skip_preflight: bool = False) -> list[str]:
        """Avvia tutti gli stadi. Restituisce i problemi che l'hanno impedito."""
        if self.is_running():
            return ["La catena è già in esecuzione."]

        if not skip_preflight:
            problems = self.preflight()
            if problems:
                return problems

        paths.ensure_runtime_dirs()

        # build_stages() aggiorna self.stages prendendo il lock per conto suo:
        # racchiuderla in un altro 'with self._lock' bloccherebbe il processo,
        # perché threading.Lock non è rientrante.
        stages = self.build_stages()
        self._stopping = False

        for stage in stages:
            try:
                self._spawn(stage)
            except OSError as exc:
                self._log(stage, f"avvio fallito: {exc}")
                self._set_state(stage, StageState.FAILED)
                self.stop()
                return [f"Avvio di «{stage.label}» fallito: {exc}"]

            if stage.key == "rx":
                # telive interroga il ricevitore una sola volta, al proprio
                # avvio: se non risponde ancora, resta senza controllo RX per
                # tutta la sessione. Meglio aspettarlo qui — e accorgersi
                # subito se invece il ricevitore è morto all'avvio (SDR
                # assente), senza sprecare il timeout e aprire telive a vuoto.
                if self.cfg.telive.xmlrpc_enabled:
                    if self.wait_for_receiver(RECEIVER_WAIT_SECONDS, stage):
                        self._log(stage, "server XMLRPC pronto")
                    elif not self._stage_alive(stage):
                        return self._abort_receiver_dead(stage)
                    else:
                        self._log(stage, (
                            f"il server XMLRPC non risponde dopo "
                            f"{RECEIVER_WAIT_SECONDS:.0f}s: telive partirà senza "
                            f"controllo del ricevitore"
                        ))
                else:
                    # Senza XMLRPC non c'è nulla da attendere, ma un breve
                    # respiro fa emergere un crash immediato del ricevitore.
                    time.sleep(1.5)
                    if not self._stage_alive(stage):
                        return self._abort_receiver_dead(stage)
            else:
                time.sleep(0.3)

        return []

    @staticmethod
    def _stage_alive(stage: Stage) -> bool:
        return stage.process is not None and stage.process.poll() is None

    def _abort_receiver_dead(self, stage: Stage) -> list[str]:
        """Ferma la catena quando il ricevitore muore all'avvio.

        Restituisce un problema con le ultime righe di log dello stadio rx,
        dove il flowgraph ha già scritto la diagnosi (SDR assente, rtl_tcp
        irraggiungibile, ...). Evita di avviare telive e i decoder a vuoto.
        """
        self._set_state(stage, StageState.FAILED)
        self.stop()

        # Mostra il blocco diagnostico dal punto in cui il flowgraph l'ha
        # scritto ("[osmotetra_rx] ..."), non solo le ultime righe che ne
        # taglierebbero l'inizio.
        log = list(stage.log)
        start = next((i for i, ln in enumerate(log)
                      if "osmotetra_rx]" in ln and "avviato" not in ln), None)
        if start is not None:
            block = [ln for ln in log[start:] if ln.strip()
                     and "terminato" not in ln]
        else:
            block = [ln for ln in log[-8:] if ln.strip()]
        detail = ("\n    " + "\n    ".join(block)) if block else ""
        return [
            "Il ricevitore SDR si è chiuso subito dopo l'avvio "
            "(nessuna radio raggiungibile?)." + detail
        ]

    def _spawn(self, stage: Stage) -> None:
        self._set_state(stage, StageState.STARTING)
        env = dict(os.environ)
        env.update(stage.env)
        # tplay e i binari del codec devono essere raggiungibili da telive.
        env["PATH"] = f"{paths.tetra_bin()}{os.pathsep}{env.get('PATH', '')}"

        stage.process = subprocess.Popen(
            stage.argv,
            cwd=str(stage.cwd) if stage.cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            # Gruppo di processi proprio: permette di terminare in blocco le
            # pipeline a tre processi, e protegge gli stadi da un Ctrl-C
            # diretto al terminale della GUI.
            start_new_session=True,
        )
        stage.exit_code = None
        stage._reader = threading.Thread(
            target=self._pump_output, args=(stage,), daemon=True
        )
        stage._reader.start()
        self._set_state(stage, StageState.RUNNING)
        self._log(stage, f"avviato (pid {stage.process.pid})")

    def _pump_output(self, stage: Stage) -> None:
        process = stage.process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                self._log(stage, line.rstrip("\n"))
        except (ValueError, OSError):
            pass  # pipe chiusa durante l'arresto
        finally:
            code = process.wait()
            stage.exit_code = code
            if stage.state is not StageState.STOPPED:
                if self._is_clean_exit(stage, code):
                    self._set_state(stage, StageState.STOPPED)
                    self._log(stage, f"terminato (codice {code})")
                else:
                    self._set_state(stage, StageState.FAILED)
                    self._log(stage, f"terminato con errore (codice {code})")

    def _is_clean_exit(self, stage: Stage, code: int) -> bool:
        """Distingue una chiusura normale da un guasto.

        Un processo ucciso da noi esce con codice negativo (``-SIGTERM``):
        segnalarlo come errore confonderebbe l'utente a ogni arresto.
        """
        if code == 0 or stage.optional:
            return True
        if self._stopping and code in (-signal.SIGTERM, -signal.SIGKILL):
            return True
        return False

    def stop(self) -> None:
        """Ferma tutti gli stadi, in ordine inverso rispetto all'avvio."""
        self._stopping = True
        with self._lock:
            stages = list(reversed(self.stages))

        for stage in stages:
            self._terminate(stage)
        for stage in stages:
            self._wait_or_kill(stage)
        for stage in stages:
            stage.process = None
            self._set_state(stage, StageState.STOPPED)

    def _signal_group(self, stage: Stage, sig: int) -> None:
        """Invia un segnale all'intero gruppo di processi dello stadio.

        Ogni stadio è avviato con ``start_new_session=True`` e quindi guida un
        proprio gruppo: segnalare il gruppo, e non il solo processo, è
        indispensabile perché quasi tutti gli stadi hanno figli.

        - ``demod-N`` è una pipeline di tre processi (socat, simdemod, tetra-rx):
          terminando la sola shell, gli altri restano vivi;
        - ``telive`` gira dentro un emulatore di terminale che lo esegue come
          figlio: uccidendo solo l'emulatore, telive resta orfano e continua a
          tenere occupata la porta UDP 7379, impedendo il riavvio successivo;
        - ``tetrad`` ha un ``sleep`` come figlio.
        """
        process = stage.process
        if process is None:
            return
        try:
            os.killpg(os.getpgid(process.pid), sig)
        except (ProcessLookupError, PermissionError):
            # Il processo è già uscito, oppure ha cambiato gruppo: ripiega
            # sul solo processo diretto.
            try:
                process.send_signal(sig)
            except (ProcessLookupError, PermissionError, ValueError):
                pass
        except OSError as exc:
            if exc.errno != errno.ESRCH:
                raise

    def _terminate(self, stage: Stage) -> None:
        if stage.process is None or stage.process.poll() is not None:
            return
        self._signal_group(stage, signal.SIGTERM)

    def _wait_or_kill(self, stage: Stage) -> None:
        process = stage.process
        if process is None:
            return
        try:
            process.wait(timeout=TERM_GRACE_SECONDS)
            return
        except subprocess.TimeoutExpired:
            self._log(stage, "non risponde a SIGTERM, invio SIGKILL")
        self._signal_group(stage, signal.SIGKILL)
        try:
            process.wait(timeout=TERM_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            self._log(stage, "il processo non è terminato nemmeno con SIGKILL")

    # -- stato -------------------------------------------------------------

    def poll(self) -> None:
        """Aggiorna lo stato degli stadi: da chiamare periodicamente."""
        for stage in self.stages:
            if stage.process is None:
                continue
            code = stage.process.poll()
            if code is None:
                if stage.state is StageState.STARTING:
                    self._set_state(stage, StageState.RUNNING)
            elif stage.state in (StageState.RUNNING, StageState.STARTING):
                stage.exit_code = code
                self._set_state(
                    stage,
                    StageState.STOPPED if (code == 0 or stage.optional)
                    else StageState.FAILED,
                )

    def is_running(self) -> bool:
        return any(
            s.process is not None and s.process.poll() is None for s in self.stages
        )

    def stage(self, key: str) -> Stage | None:
        return next((s for s in self.stages if s.key == key), None)

    def receiver(self) -> ReceiverControl:
        return ReceiverControl(self.cfg.base_port, self.cfg.udp_host)

    def wait_for_receiver(self, timeout: float = 10.0,
                          stage: "Stage | None" = None) -> bool:
        """Attende che il server XMLRPC del flowgraph risponda.

        Se ``stage`` è fornito e il suo processo termina durante l'attesa, si
        smette subito: non ha senso sondare per tutto il timeout un ricevitore
        che è già morto (es. SDR assente).
        """
        control = self.receiver()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if stage is not None and stage.process is not None \
                    and stage.process.poll() is not None:
                return False
            if control.is_alive():
                return True
            time.sleep(0.4)
        return False

    # -- notifiche ---------------------------------------------------------

    def _log(self, stage: Stage, line: str) -> None:
        stage.log.append(line)
        if self._on_log:
            self._on_log(stage.key, line)

    def _set_state(self, stage: Stage, state: StageState) -> None:
        if stage.state is state:
            return
        stage.state = state
        if self._on_state:
            self._on_state(stage.key, state)


# -- funzioni di supporto ---------------------------------------------------


def rtl_tcp_endpoint(device_args: str) -> tuple[str, int] | None:
    """Estrae host e porta da una stringa di dispositivo ``rtl_tcp=host:porta``.

    Restituisce None se il dispositivo non è un rtl_tcp.
    """
    for token in device_args.split():
        if not token.startswith("rtl_tcp="):
            continue
        value = token[len("rtl_tcp="):]
        host, _, port = value.rpartition(":")
        if not host:
            host, port = value, "1234"
        try:
            return host, int(port)
        except ValueError:
            return host, 1234
    return None


def check_rtl_tcp(cfg, timeout: float = 3.0) -> list[str]:
    """Verifica che un server rtl_tcp remoto sia raggiungibile.

    Con la chiavetta collegata a un'altra macchina — il caso tipico è Ubuntu
    dentro una macchina virtuale il cui hypervisor non inoltra l'USB — il
    server va avviato là e deve restare in esecuzione. Se non lo è,
    gr-osmosdr fallisce con un errore che non spiega niente: meglio dirlo qui,
    con la diagnosi giusta.
    """
    endpoint = rtl_tcp_endpoint(cfg.sdr.device_args)
    if endpoint is None or cfg.sdr.source != "osmosdr":
        return []

    host, port = endpoint
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return []
    except ConnectionRefusedError:
        return [
            f"Nessun server rtl_tcp in ascolto su {host}:{port} (connessione "
            f"rifiutata). Il pacchetto arriva, ma là non ascolta nessuno: "
            f"avvia 'rtl_tcp -a 0.0.0.0 -p {port}' sulla macchina a cui è "
            f"collegata la chiavetta, e lascia quella finestra aperta."
        ]
    except socket.timeout:
        return [
            f"{host}:{port} non risponde entro {timeout:.0f}s. Il server "
            f"rtl_tcp non è raggiungibile: controlla il firewall della "
            f"macchina che lo esegue e che l'indirizzo sia quello giusto."
        ]
    except OSError as exc:
        return [f"Impossibile raggiungere il server rtl_tcp {host}:{port}: {exc}"]


def _udp_port_busy(port: int, host: str = "127.0.0.1") -> bool:
    """True se la porta UDP è già in uso."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def _terminal_argv(term_cfg, title: str, command: str) -> list[str]:
    """Riga di comando per aprire ``command`` in un terminale della misura giusta.

    telive pretende 203x60 caratteri (telive_doc.txt): sotto quella soglia
    l'interfaccia risulta illeggibile. Ogni emulatore esprime la geometria a
    modo suo, e alcuni non la accettano affatto.
    """
    geometry = f"{term_cfg.columns}x{term_cfg.rows}"
    command_path = command

    explicit = (term_cfg.command or "").strip()
    if explicit:
        program = shlex.split(explicit)[0]
        extra = shlex.split(explicit)[1:]
    else:
        found, _ = deps.find_terminal()
        program = found or "xterm"
        extra = []

    name = Path(program).name

    if name == "xterm":
        return [program, *extra,
                "-title", title,
                "-fa", term_cfg.font, "-fs", str(term_cfg.font_size),
                "-bg", "black", "-fg", "white",
                "-geometry", geometry,
                "-e", command_path]

    if name == "gnome-terminal":
        # gnome-terminal ignora la geometria da riga di comando dalla 3.28 in
        # poi; la si passa comunque perché su alcune build funziona ancora.
        return [program, *extra,
                f"--geometry={geometry}",
                "--title", title,
                "--", command_path]

    if name == "konsole":
        return [program, *extra,
                "-p", f"TerminalColumns={term_cfg.columns}",
                "-p", f"TerminalRows={term_cfg.rows}",
                "--title", title,
                "-e", command_path]

    if name in ("xfce4-terminal", "mate-terminal", "lxterminal"):
        return [program, *extra,
                f"--geometry={geometry}",
                f"--title={title}",
                "-e", command_path]

    # Emulatore sconosciuto: il tentativo più diffuso è '-e'.
    return [program, *extra, "-e", command_path]
