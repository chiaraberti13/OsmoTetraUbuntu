"""Punto di ingresso di OsmoTetraUbuntu.

Senza argomenti apre la GUI. I sottocomandi servono a usare e collaudare la
catena senza interfaccia grafica::

    osmotetra check           verifica le dipendenze
    osmotetra print-cmdline   stampa i comandi dei tre stadi senza eseguirli
    osmotetra start           avvia la catena e resta in primo piano
    osmotetra stop            ferma un'istanza avviata con 'start'
    osmotetra self-test       collaudo interno (non richiede radio né schermo)

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

from . import __version__, config as config_mod, deps, paths
from .config import Config
from .pipeline import Pipeline, StageState

#: File con il PID dell'istanza avviata da 'osmotetra start'.
def _pidfile() -> Path:
    return paths.config_dir() / "osmotetra.pid"


def _load_config(args) -> Config:
    if getattr(args, "profile", None):
        return config_mod.load_profile(args.profile)
    if getattr(args, "config", None):
        return Config.load(Path(args.config).expanduser())
    return Config.load()


# -- check -----------------------------------------------------------------


def cmd_check(args) -> int:
    checks = deps.run_checks()
    width = max(len(c.name) for c in checks)
    failures = 0

    print("Dipendenze di OsmoTetraUbuntu\n")
    for check in checks:
        if check.ok:
            mark = "  ok  "
        elif check.required:
            mark = " MANCA"
            failures += 1
        else:
            mark = " (opz)"
        print(f"[{mark}] {check.name.ljust(width)}  {check.detail}")
        if not check.ok and check.hint:
            print(f"         → {check.hint}")

    cfg = _load_config(args)
    problems = cfg.validate()
    # Con la chiavetta su un'altra macchina (rtl_tcp) la raggiungibilità del
    # server è una dipendenza a tutti gli effetti: va verificata qui, non
    # scoperta a catena avviata.
    from .pipeline import check_rtl_tcp
    problems += check_rtl_tcp(cfg)
    warnings = cfg.warnings()
    if problems or warnings:
        print("\nConfigurazione")
        for problem in problems:
            print(f"[ ERRORE] {problem}")
        for warning in warnings:
            print(f"[ avviso] {warning}")

    print()
    if failures or problems:
        print(f"{failures + len(problems)} problemi da risolvere prima di avviare.")
        return 1
    print("Tutto pronto.")
    return 0


# -- print-cmdline ---------------------------------------------------------


def cmd_print_cmdline(args) -> int:
    cfg = _load_config(args)
    pipeline = Pipeline(cfg)
    stages = pipeline.build_stages()

    if args.json:
        print(json.dumps([
            {"key": s.key, "label": s.label, "argv": s.argv,
             "cwd": str(s.cwd) if s.cwd else None, "env": s.env}
            for s in stages
        ], indent=2, ensure_ascii=False))
        return 0

    print("Comandi che verrebbero eseguiti, nell'ordine di avvio:\n")
    for i, stage in enumerate(stages, start=1):
        print(f"# {i}. {stage.label}  [{stage.key}]")
        if stage.cwd:
            print(f"cd {stage.cwd}")
        for key in sorted(stage.env):
            print(f"export {key}={stage.env[key]}")
        print(stage.cmdline)
        print()

    runner = paths.tetra_bin() / "telive-run"
    if runner.is_file():
        print(f"# Variabili di telive: vedi {runner}")
    return 0


# -- start / stop ----------------------------------------------------------


def cmd_start(args) -> int:
    cfg = _load_config(args)
    pipeline = Pipeline(cfg, on_log=_print_log)

    problems = pipeline.start(skip_preflight=args.force)
    if problems:
        print("Impossibile avviare la catena:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        if not args.force:
            print("\n(usa --force per provare comunque)", file=sys.stderr)
        return 1

    pidfile = _pidfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()), encoding="utf-8")

    # L'attesa del server XMLRPC è già dentro Pipeline.start(), prima di
    # avviare telive: qui basta segnalare l'esito.
    print("\nCatena avviata. Premi Ctrl-C per fermarla.\n")

    stopping = False

    def handle(signum, frame):
        nonlocal stopping
        if stopping:
            return
        stopping = True
        print("\n[osmotetra] arresto in corso...")

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)

    try:
        while not stopping:
            time.sleep(0.5)
            pipeline.poll()
            failed = [s for s in pipeline.stages if s.state is StageState.FAILED]
            if failed:
                names = ", ".join(s.label for s in failed)
                print(f"\n[osmotetra] stadio in errore: {names}", file=sys.stderr)
                break
            if not pipeline.is_running():
                print("\n[osmotetra] tutti gli stadi sono terminati")
                break
    finally:
        pipeline.stop()
        pidfile.unlink(missing_ok=True)
        print("[osmotetra] catena fermata")
    return 0


def cmd_stop(args) -> int:
    pidfile = _pidfile()
    if not pidfile.is_file():
        print("Nessuna istanza avviata con 'osmotetra start'.", file=sys.stderr)
        return 1
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        print("File PID illeggibile.", file=sys.stderr)
        pidfile.unlink(missing_ok=True)
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print("L'istanza non è più in esecuzione.")
        pidfile.unlink(missing_ok=True)
        return 0
    except PermissionError:
        print(f"Nessun permesso per fermare il processo {pid}.", file=sys.stderr)
        return 1

    print(f"Arresto richiesto al processo {pid}.")
    return 0


def _print_log(stage_key: str, line: str) -> None:
    print(f"[{stage_key}] {line}", flush=True)


# -- self-test -------------------------------------------------------------


def cmd_self_test(args) -> int:
    """Collaudo che non richiede né radio né schermo."""
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"[{'  ok  ' if condition else ' FALLI'}] {label}"
              + (f"  {detail}" if detail else ""))
        if not condition:
            failures.append(label)

    print("Collaudo interno di OsmoTetraUbuntu\n")

    # 1. Config: default, validazione, round-trip su disco.
    cfg = Config()
    check("configurazione predefinita valida", cfg.validate() == [],
          "; ".join(cfg.validate()))

    cfg.set_channel_count(3)
    cfg.channels[1].offset_hz = 250_000
    cfg.channels[2].offset_hz = -125_000
    cfg.sdr.freq_hz = 391_100_000
    check("tre canali configurati", len(cfg.channels) == 3)
    check("frequenza canale 2 calcolata",
          abs(cfg.channel_freq_hz(2) - 391_350_000) < 1,
          f"{cfg.channel_freq_hz(2) / 1e6:.4f} MHz")
    check("porta UDP canale 3", cfg.channel_udp_port(3) == cfg.base_port + 3,
          str(cfg.channel_udp_port(3)))

    tmp = Path(args.tmpdir or paths.config_dir()) / "self-test-config.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    cfg.save(tmp)
    reloaded = Config.load(tmp)
    check("round-trip della configurazione su disco",
          reloaded.to_dict() == cfg.to_dict())
    tmp.unlink(missing_ok=True)

    # 2. I validatori devono respingere le configurazioni inutili.
    bad = Config()
    bad.sdr.first_decim = 512          # 2 Ms/s / 512 = 3,9 kHz: canale perso
    check("rilevata decimazione eccessiva", bad.validate() != [])

    bad = Config()
    bad.channels[0].offset_hz = 5_000_000  # fuori dalla banda campionata
    check("rilevato offset fuori banda", bad.validate() != [])

    bad = Config()
    bad.telive.udp_port = bad.base_port + 1   # collide col canale 1
    check("rilevata collisione di porte", bad.validate() != [])

    bad = Config()
    bad.sdr.source = "file:/percorso/inesistente.cfile"
    check("rilevato file IQ mancante", bad.validate() != [])

    # 3. Costruzione dei comandi: deve riprodurre la catena di telive.
    pipeline = Pipeline(cfg)
    stages = pipeline.build_stages()
    by_key = {s.key: s for s in stages}
    keys = [s.key for s in stages]
    # L'ordine conta: telive interroga il ricevitore una sola volta all'avvio,
    # quindi il flowgraph deve essere già in ascolto (vedi pipeline.py).
    check("primo stadio: ricevitore", bool(keys) and keys[0] == "rx", str(keys))
    check("telive avviato dopo il ricevitore",
          keys.index("telive") > keys.index("rx"))
    check("decoder avviati dopo telive",
          min(i for i, k in enumerate(keys) if k.startswith("demod-"))
          > keys.index("telive"))
    check("un decoder per canale",
          sum(1 for k in keys if k.startswith("demod-")) == 3)

    demod = by_key["demod-2"]
    cmdline = demod.cmdline
    check("il decoder usa socat", "socat" in cmdline)
    check("il decoder usa simdemod3", "simdemod3_py3.py" in cmdline)
    check("il decoder usa tetra-rx", "tetra-rx" in cmdline)
    check("il decoder ascolta sulla porta del canale",
          f"UDP-RECV:{cfg.channel_udp_port(2)}" in cmdline, cmdline)
    check("RXID passato a tetra-rx", demod.env.get("TETRA_HACK_RXID") == "2")
    check("porta di telive passata a tetra-rx",
          demod.env.get("TETRA_HACK_PORT") == str(cfg.telive.udp_port))
    check("il decoder è una pipeline shell terminabile in gruppo",
          demod.argv[0] == "bash" and demod.argv[1] == "-c")

    # 4. Variabili d'ambiente di telive.
    from . import telive_env
    env = telive_env.build_env(cfg)
    check("TETRA_PORT impostata",
          env.get("TETRA_PORT") == str(cfg.telive.udp_port))
    check("URL XMLRPC coerente con la porta base",
          env.get("TETRA_GR_XMLRPC_URL") == f"http://127.0.0.1:{cfg.base_port}/")
    check("elenco frequenze terminato da ';'",
          env.get("TETRA_RX_TUNE", "").endswith(";"), env.get("TETRA_RX_TUNE", ""))
    script = telive_env.build_runner_script(cfg)
    check("lo script di telive entra nella sua directory",
          str(paths.telive_src()) in script)
    check("lo script di telive esporta il PATH del codec",
          str(paths.tetra_bin()) in script)

    # 5. Terminale: la geometria richiesta da telive deve arrivare al comando.
    telive_stage = by_key["telive"]
    check("il terminale riceve la geometria 203x60",
          any("203x60" in a for a in telive_stage.argv), telive_stage.cmdline)

    # 6. GUI, solo se PyQt5 è disponibile e si può creare una QApplication.
    if not args.no_gui:
        rc = _self_test_gui(check)
        if rc is False:
            print("       (GUI non collaudata: PyQt5 assente)")

    print()
    if failures:
        print(f"{len(failures)} controlli falliti: " + ", ".join(failures))
        return 1
    print("Tutti i controlli superati.")
    return 0


def _self_test_gui(check) -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        from .ui.main_window import MainWindow
    except ImportError:
        return False

    app = QApplication.instance() or QApplication([])

    # Il confronto va fatto contro un oggetto indipendente: passare la stessa
    # istanza alla finestra e poi confrontarla con sé stessa renderebbe il
    # controllo sempre vero, anche se i widget azzerassero tutto.
    expected = Config()
    expected.set_channel_count(2)
    expected.sdr.freq_hz = 391_100_000.0
    expected.channels[1].offset_hz = 250_000.0

    window = MainWindow(Config.from_dict(expected.to_dict()))
    window.load_config_into_widgets()
    window.collect_widgets_into_config()

    check("la GUI conserva i parametri radio nel giro andata/ritorno",
          window.cfg.to_dict()["sdr"] == expected.to_dict()["sdr"],
          f"freq={window.cfg.sdr.freq_hz / 1e6:.4f} MHz "
          f"samp={window.cfg.sdr.samp_rate / 1e6:.3f} Ms/s "
          f"decim={window.cfg.sdr.first_decim}")
    check("la GUI conserva i canali nel giro andata/ritorno",
          window.cfg.to_dict()["channels"] == expected.to_dict()["channels"])
    check("la GUI conserva le impostazioni di telive",
          window.cfg.to_dict()["telive"] == expected.to_dict()["telive"])
    check("la GUI conserva la porta base",
          window.cfg.base_port == expected.base_port)

    window.cfg.sdr.first_decim = 512
    check("la GUI segnala le configurazioni non valide",
          window.cfg.validate() != [])

    window.close()
    app.processEvents()
    return True


# -- gui -------------------------------------------------------------------


def cmd_gui(args) -> int:
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print("PyQt5 non è installato: impossibile aprire l'interfaccia grafica.",
              file=sys.stderr)
        print("  sudo apt-get install python3-pyqt5", file=sys.stderr)
        print("\nI sottocomandi da riga di comando restano disponibili:",
              file=sys.stderr)
        print("  osmotetra check | print-cmdline | start | stop", file=sys.stderr)
        return 1

    from .ui.main_window import MainWindow

    paths.ensure_runtime_dirs()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("OsmoTetra")
    window = MainWindow(_load_config(args))
    window.show()
    return app.exec_()


# -- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="osmotetra",
        description="Monitoraggio TETRA con osmo-tetra-sq5bpf e telive.",
    )
    parser.add_argument("--version", action="version",
                        version=f"OsmoTetraUbuntu {__version__}")
    parser.add_argument("--config", metavar="FILE",
                        help="file di configurazione da usare")
    parser.add_argument("--profile", metavar="NOME",
                        help="profilo salvato da usare")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="apre l'interfaccia grafica (predefinito)")
    sub.add_parser("check", help="verifica dipendenze e configurazione")

    p_cmd = sub.add_parser("print-cmdline",
                           help="stampa i comandi dei tre stadi senza eseguirli")
    p_cmd.add_argument("--json", action="store_true", help="output in JSON")

    p_start = sub.add_parser("start", help="avvia la catena e resta in primo piano")
    p_start.add_argument("--force", action="store_true",
                         help="avvia anche se i controlli preliminari falliscono")

    sub.add_parser("stop", help="ferma l'istanza avviata con 'start'")

    p_test = sub.add_parser("self-test", help="collaudo interno senza radio")
    p_test.add_argument("--no-gui", action="store_true",
                        help="salta i controlli sull'interfaccia grafica")
    p_test.add_argument("--tmpdir", help="directory per i file temporanei")

    return parser


COMMANDS = {
    "gui": cmd_gui,
    "check": cmd_check,
    "print-cmdline": cmd_print_cmdline,
    "start": cmd_start,
    "stop": cmd_stop,
    "self-test": cmd_self_test,
}


def main(argv=None) -> int:
    # 'start' resta in primo piano per ore riversando i log degli stadi: con
    # lo stdout rediretto su file Python userebbe il buffering a blocchi e il
    # file resterebbe vuoto fino alla chiusura (o per sempre, se il processo
    # viene ucciso).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command or "gui")
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
