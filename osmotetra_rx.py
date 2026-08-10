#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ricevitore TETRA a 1 canale, headless, per la catena telive-2.

Questo file è la versione **senza interfaccia grafica** del flowgraph
originale di Jacek Lipkowski SQ5BPF
``telive_1ch_simple_gr310_udp_xmlrpc.py`` (quello che si vede nello
screenshot "SQ5BPF Tetra live receiver 1ch simple UDP demo with fixed
offset"). La catena di segnale — filtro, AGC, ricampionatore, uscita UDP a
36 kS/s, server XMLRPC — è **identica bit per bit** all'originale: cambia
solo che qui i pochi parametri utili (frequenza, guadagno, ppm, dispositivo)
si passano da riga di comando invece di essere cablati nel sorgente, così il
lanciatore può avviarlo da solo.

Modello di frequenza (foolproof, come nel flowgraph con GUI):

    --freq  = la frequenza del CANALE che vuoi ascoltare (es. 390.5M)

L'SDR viene sintonizzato 500 kHz *sotto* (offset anti-DC fisso), e il filtro
riporta il canale sulla sua frequenza. Così il segnale non cade mai sul picco
DC dell'RTL-SDR: scrivi la frequenza del canale e basta.

Originale: https://github.com/sq5bpf/telive-2  (GPL-3.0)
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import signal
import sys
import threading
from xmlrpc.server import SimpleXMLRPCServer

from gnuradio import analog, blocks, filter, gr, network
from gnuradio.filter import firdes

try:
    import osmosdr
except ImportError:  # pragma: no cover - dipende dall'ambiente
    osmosdr = None

#: Offset anti-DC fisso, identico a ``xlate_offset1`` di upstream.
XLATE_OFFSET = 500e3
#: Dimensione del datagramma UDP usata da upstream.
UDP_PACKET_SIZE = 1472


class OsmoTetraRX(gr.top_block):
    """Ricevitore 1 canale con uscita UDP e controllo XMLRPC.

    Nomi delle variabili e logica dei setter presi tali e quali dal
    flowgraph di upstream, perché telive li interroga per nome via XMLRPC.
    """

    def __init__(self, *, channel_freq, samp_rate, first_decim, out_sample_rate,
                 options_low_pass, sdr_gain, sdr_ifgain, sdr_bbgain, ppm_corr,
                 device_args, udp_dest_addr, first_port, source, gui=False):
        gr.top_block.__init__(
            self, "OsmoTetra RX 1ch (SQ5BPF)", catch_exceptions=True)
        self.gui = gui

        # -- variabili (stessi nomi e stessa convenzione di upstream) -----
        # Come nel flowgraph headless di SQ5BPF: ``freq`` è la frequenza di
        # BASEBAND dell'SDR e il canale sta a ``freq + xlate_offset1``. È la
        # convenzione che telive si aspetta quando controlla il ricevitore
        # (telive imposta freq=baseband e xlate_offsetN=offset del canale).
        # L'utente però ragiona per frequenza del CANALE: la convertiamo qui,
        # tenendo l'offset anti-DC fisso a 500 kHz.
        self.xlate_offset_fine1 = xlate_offset_fine1 = 0
        self.xlate_offset1 = xlate_offset1 = XLATE_OFFSET
        self.samp_rate = samp_rate = float(samp_rate)
        self.first_decim = first_decim = int(first_decim)
        self.freq = freq = float(channel_freq) - XLATE_OFFSET   # baseband
        self.udp_packet_size = UDP_PACKET_SIZE
        self.udp_dest_addr = udp_dest_addr = udp_dest_addr
        self.telive_receiver_name = 'OsmoTetra 1-channel rx for telive'
        self.telive_receiver_channels = 1
        self.sdr_ifgain = sdr_ifgain = float(sdr_ifgain)
        self.sdr_gain = sdr_gain = float(sdr_gain)
        self.sdr_bbgain = float(sdr_bbgain)
        self.ppm_corr = ppm_corr = float(ppm_corr)
        self.out_sample_rate = out_sample_rate = int(out_sample_rate)
        self.options_low_pass = options_low_pass = float(options_low_pass)
        self.if_samp_rate = if_samp_rate = samp_rate / first_decim
        self.first_port = first_port = int(first_port)
        self._device_args = device_args

        # -- blocchi ------------------------------------------------------
        self.osmosdr_source_0 = self._make_source(source, device_args)
        if self._source_ctl is not None:
            src = self._source_ctl
            src.set_time_unknown_pps(osmosdr.time_spec_t())
            src.set_sample_rate(samp_rate)
            # SDR sul baseband (500 kHz sotto il canale): il segnale sta fuori
            # dal picco DC della chiavetta.
            src.set_center_freq(freq, 0)
            src.set_freq_corr(ppm_corr, 0)
            src.set_dc_offset_mode(0, 0)
            src.set_iq_balance_mode(0, 0)
            src.set_gain_mode(False, 0)
            src.set_gain(sdr_gain, 0)
            src.set_if_gain(sdr_ifgain, 0)
            src.set_bb_gain(self.sdr_bbgain, 0)
            src.set_antenna('', 0)
            src.set_bandwidth(0, 0)

        self.network_udp_sink_0 = network.udp_sink(
            gr.sizeof_gr_complex, 1, udp_dest_addr, (first_port + 1), 0,
            UDP_PACKET_SIZE, False)
        self.mmse_resampler_xx_0 = filter.mmse_resampler_cc(
            0, (float(float(if_samp_rate) / float(out_sample_rate))))
        self.freq_xlating_fir_filter_xxx_0 = filter.freq_xlating_fir_filter_ccc(
            first_decim,
            firdes.low_pass(1, samp_rate, options_low_pass, options_low_pass * 0.2),
            (xlate_offset1 + xlate_offset_fine1), samp_rate)
        self.analog_agc3_xx_0 = analog.agc3_cc((1e-3), (1e-4), 1.0, 1.0, 1)
        self.analog_agc3_xx_0.set_max_gain(65536)

        # -- connessioni (identiche a upstream) ---------------------------
        self.connect((self.osmosdr_source_0, 0), (self.freq_xlating_fir_filter_xxx_0, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0, 0), (self.analog_agc3_xx_0, 0))
        self.connect((self.analog_agc3_xx_0, 0), (self.mmse_resampler_xx_0, 0))
        self.connect((self.mmse_resampler_xx_0, 0), (self.network_udp_sink_0, 0))

        if self.gui:
            self._build_gui_sinks(samp_rate, if_samp_rate)

        self._start_xmlrpc(first_port)

    def _build_gui_sinks(self, samp_rate, if_samp_rate):
        """Aggiunge i due analizzatori di spettro (spettro pieno + IF) come nel
        flowgraph con GUI di SQ5BPF. I widget veri si creano in make_gui_window."""
        from gnuradio import qtgui
        from gnuradio.fft import window
        import pmt

        # spettro pieno, derivato dalla sorgente SDR: centrato sul baseband
        self.freq_sink_full = qtgui.freq_sink_c(
            1024, window.WIN_BLACKMAN_hARRIS, 0, samp_rate, "", 1, None)
        self.freq_sink_full.set_update_time(0.10)
        self.freq_sink_full.enable_autoscale(False)
        self.freq_sink_full.enable_grid(False)
        self.freq_sink_full.set_fft_average(0.2)
        self.freq_sink_full.enable_control_panel(True)
        # spettro IF, dopo il filtro di canale (largo ~62,5 kHz)
        self.freq_sink_if = qtgui.freq_sink_c(
            256, window.WIN_BLACKMAN_hARRIS, 0, if_samp_rate, "IF", 1, None)
        self.freq_sink_if.set_update_time(0.01)
        self.freq_sink_if.enable_autoscale(True)
        self.freq_sink_if.enable_grid(True)
        self.freq_sink_if.enable_control_panel(True)
        # marcatore: porta il centro dello spettro pieno sul baseband dell'SDR
        self.freq_marker = blocks.message_strobe(
            pmt.cons(pmt.intern("freq"), pmt.from_float(self.freq)), 100)
        self.msg_connect((self.freq_marker, 'strobe'), (self.freq_sink_full, 'freq'))
        self.connect((self.osmosdr_source_0, 0), (self.freq_sink_full, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0, 0), (self.freq_sink_if, 0))

    def make_gui_window(self):
        """Finestra con i due grafici e i controlli (freq, fine, ppm, gain).
        Da chiamare dopo aver creato la QApplication."""
        from PyQt5 import Qt, QtCore
        import sip
        from gnuradio.qtgui import Range, RangeWidget
        from gnuradio import eng_notation

        win = Qt.QWidget()
        win.setWindowTitle("OsmoTetra — spettro e parametri")
        grid = Qt.QGridLayout(win)

        # campo Frequenza (del CANALE, non del baseband)
        channel_hz = self.freq + self.xlate_offset1
        bar = Qt.QToolBar(win)
        bar.addWidget(Qt.QLabel("Frequenza canale: "))
        self._freq_edit = Qt.QLineEdit(eng_notation.num_to_str(channel_hz))
        bar.addWidget(self._freq_edit)
        self._freq_edit.returnPressed.connect(self._on_freq_edit)
        grid.addWidget(bar, 0, 0, 1, 2)

        # Fine tune / ppm / gain (slider con contatore, come nel flowgraph SQ5BPF)
        grid.addWidget(RangeWidget(
            Range(-5e3, 5e3, 1, self.xlate_offset_fine1, 200),
            self.set_xlate_offset_fine1, "Fine tune", "counter_slider",
            float, QtCore.Qt.Horizontal), 0, 2, 1, 2)
        grid.addWidget(RangeWidget(
            Range(-100, 100, 0.5, self.ppm_corr, 200),
            self.set_ppm_corr, "ppm", "counter_slider",
            float, QtCore.Qt.Horizontal), 0, 4, 1, 2)
        grid.addWidget(RangeWidget(
            Range(0, 50, 1, self.sdr_gain, 200),
            self.set_sdr_gain, "gain", "counter_slider",
            float, QtCore.Qt.Horizontal), 0, 6, 1, 1)

        # i due analizzatori di spettro
        full_w = sip.wrapinstance(self.freq_sink_full.qwidget(), Qt.QWidget)
        if_w = sip.wrapinstance(self.freq_sink_if.qwidget(), Qt.QWidget)
        grid.addWidget(full_w, 1, 0, 1, 4)
        grid.addWidget(if_w, 1, 4, 1, 4)
        win.resize(1000, 600)
        return win

    def _on_freq_edit(self):
        from gnuradio import eng_notation
        try:
            channel = eng_notation.str_to_num(str(self._freq_edit.text()))
        except Exception:
            return
        # freq interna = baseband = canale - offset anti-DC
        self.set_freq(channel - self.xlate_offset1)

    # -- sorgente ---------------------------------------------------------

    def _make_source(self, source, device_args):
        """Crea il blocco sorgente. ``osmosdr`` per la radio vera; ``null``
        e ``file:<percorso>`` per provare la catena senza radio."""
        if source == "null":
            src = blocks.null_source(gr.sizeof_gr_complex)
            thr = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate, True)
            self.connect(src, thr)
            self._source_ctl = None
            return thr

        if source.startswith("file:"):
            path = source[len("file:"):]
            src = blocks.file_source(gr.sizeof_gr_complex, path, False)
            thr = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate, True)
            self.connect(src, thr)
            self._source_ctl = None
            return thr

        if osmosdr is None:
            raise SystemExit(
                "modulo osmosdr non disponibile: installa gr-osmosdr\n"
                "  sudo apt-get install gr-osmosdr")
        try:
            src = osmosdr.source(args="numchan=" + str(1) + " " + device_args)
        except RuntimeError as exc:
            raise SystemExit(_no_device_message(device_args, exc)) from exc
        self._source_ctl = src
        return src

    # -- XMLRPC -----------------------------------------------------------

    def _start_xmlrpc(self, port):
        self.xmlrpc_server = SimpleXMLRPCServer(
            ('0.0.0.0', port), allow_none=True, logRequests=False)
        self.xmlrpc_server.register_instance(self)
        self._xmlrpc_thread = threading.Thread(
            target=self.xmlrpc_server.serve_forever, daemon=True)
        self._xmlrpc_thread.start()

    def stop(self):
        try:
            self.xmlrpc_server.shutdown()
        except Exception:  # pragma: no cover
            pass
        return gr.top_block.stop(self)

    # -- accessori esposti via XMLRPC (nomi richiesti da telive) ----------

    def get_telive_receiver_name(self):
        return self.telive_receiver_name

    def get_telive_receiver_channels(self):
        return self.telive_receiver_channels

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        # freq = baseband dell'SDR (convenzione di telive: canale = freq + offset)
        self.freq = float(freq)
        if self._source_ctl is not None:
            self._source_ctl.set_center_freq(self.freq, 0)
        # ricentra lo spettro pieno sul nuovo baseband, se la GUI è attiva
        marker = getattr(self, "freq_marker", None)
        if marker is not None:
            import pmt
            marker.set_msg(pmt.cons(pmt.intern("freq"), pmt.from_float(self.freq)))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = float(samp_rate)
        self.if_samp_rate = self.samp_rate / self.first_decim
        self.freq_xlating_fir_filter_xxx_0.set_taps(
            firdes.low_pass(1, self.samp_rate, self.options_low_pass,
                            self.options_low_pass * 0.2))
        self.mmse_resampler_xx_0.set_resamp_ratio(
            float(self.if_samp_rate) / float(self.out_sample_rate))
        if self._source_ctl is not None:
            self._source_ctl.set_sample_rate(self.samp_rate)

    def get_first_decim(self):
        return self.first_decim

    def get_xlate_offset1(self):
        return self.xlate_offset1

    def set_xlate_offset1(self, xlate_offset1):
        # sposta solo il filtro (il canale), non il baseband — come upstream
        self.xlate_offset1 = float(xlate_offset1)
        self.freq_xlating_fir_filter_xxx_0.set_center_freq(
            self.xlate_offset1 + self.xlate_offset_fine1)

    def get_xlate_offset_fine1(self):
        return self.xlate_offset_fine1

    def set_xlate_offset_fine1(self, xlate_offset_fine1):
        self.xlate_offset_fine1 = float(xlate_offset_fine1)
        self.freq_xlating_fir_filter_xxx_0.set_center_freq(
            self.xlate_offset1 + self.xlate_offset_fine1)

    def get_sdr_gain(self):
        return self.sdr_gain

    def set_sdr_gain(self, sdr_gain):
        self.sdr_gain = float(sdr_gain)
        if self._source_ctl is not None:
            self._source_ctl.set_gain(self.sdr_gain, 0)

    def get_sdr_ifgain(self):
        return self.sdr_ifgain

    def set_sdr_ifgain(self, sdr_ifgain):
        self.sdr_ifgain = float(sdr_ifgain)
        if self._source_ctl is not None:
            self._source_ctl.set_if_gain(self.sdr_ifgain, 0)

    def get_ppm_corr(self):
        return self.ppm_corr

    def set_ppm_corr(self, ppm_corr):
        self.ppm_corr = float(ppm_corr)
        if self._source_ctl is not None:
            self._source_ctl.set_freq_corr(self.ppm_corr, 0)

    def get_options_low_pass(self):
        return self.options_low_pass

    def set_options_low_pass(self, options_low_pass):
        self.options_low_pass = float(options_low_pass)
        self.freq_xlating_fir_filter_xxx_0.set_taps(
            firdes.low_pass(1, self.samp_rate, self.options_low_pass,
                            self.options_low_pass * 0.2))

    def get_out_sample_rate(self):
        return self.out_sample_rate

    def get_if_samp_rate(self):
        return self.if_samp_rate

    def get_first_port(self):
        return self.first_port

    def get_udp_dest_addr(self):
        return self.udp_dest_addr


# -- diagnostica del dispositivo -------------------------------------------


def _no_device_message(device_args: str, exc: Exception) -> str:
    """Traduce il RuntimeError generico di gr-osmosdr in cosa manca e cosa fare."""
    args = device_args.strip()
    if "rtl_tcp=" in args:
        endpoint = ""
        for token in args.split():
            if token.startswith("rtl_tcp="):
                endpoint = token[len("rtl_tcp="):]
        return (
            f"[osmotetra_rx] Nessun ricevitore rtl_tcp su {endpoint or '(indirizzo mancante)'}.\n"
            f"  Il server rtl_tcp non risponde. Sulla macchina a cui è collegata\n"
            f"  la chiavetta avvia:  rtl_tcp -a 0.0.0.0 -p 1234\n"
            f"  e lascia quella finestra aperta; verifica host e porta.\n"
            f"  (dettaglio gr-osmosdr: {exc})")
    where = args or "auto (nessun dispositivo indicato)"
    return (
        f"[osmotetra_rx] Nessun dispositivo SDR trovato (richiesto: {where}).\n"
        f"  • Se la chiavetta è collegata direttamente: controlla con\n"
        f"      rtl_test -t\n"
        f"    'usb_claim_interface error -6' = driver DVB-T ancora caricato\n"
        f"    (scollega/ricollega o riavvia); se serve, fai logout/login per il\n"
        f"    gruppo plugdev.\n"
        f"  • In una macchina virtuale l'USB potrebbe non essere inoltrato:\n"
        f"    lascia la chiavetta al sistema ospitante ed esponila con rtl_tcp\n"
        f"    (dispositivo 'rtl_tcp=INDIRIZZO:1234'). Vedi il README.\n"
        f"  (dettaglio gr-osmosdr: {exc})")


# -- riga di comando -------------------------------------------------------


def eng_float(text):
    """Converte "390.5M", "12.5k", "2.4e6" in float."""
    text = str(text).strip()
    suffixes = {"k": 1e3, "K": 1e3, "M": 1e6, "m": 1e6, "G": 1e9, "g": 1e9}
    if text and text[-1] in suffixes:
        return float(text[:-1]) * suffixes[text[-1]]
    return float(text)


def build_parser():
    p = argparse.ArgumentParser(
        prog="osmotetra_rx.py",
        description="Ricevitore TETRA 1 canale per telive (DSP di SQ5BPF); "
                    "headless, oppure con --gui mostra spettro e controlli.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--freq", type=eng_float, default=390.5e6,
                   help="frequenza del CANALE da ascoltare in Hz (es. 390.5M)")
    p.add_argument("--gain", type=float, default=38, help="guadagno RF (dB)")
    p.add_argument("--if-gain", type=float, default=20, help="guadagno IF (dB)")
    p.add_argument("--bb-gain", type=float, default=20, help="guadagno banda base (dB)")
    p.add_argument("--ppm", type=float, default=0, help="correzione di frequenza (ppm)")
    p.add_argument("--device-args", default="",
                   help="argomenti osmosdr: 'rtl=0', 'rtl_tcp=IP:1234', 'hackrf=0'…")
    p.add_argument("--samp-rate", type=eng_float, default=2e6,
                   help="campionamento dell'SDR in Hz")
    p.add_argument("--first-decim", type=int, default=32, help="decimazione del filtro")
    p.add_argument("--out-rate", type=int, default=36000,
                   help="frequenza di uscita attesa da simdemod3 (36 kS/s)")
    p.add_argument("--lowpass", type=eng_float, default=12500,
                   help="larghezza del filtro di canale in Hz")
    p.add_argument("--udp-host", default="127.0.0.1",
                   help="host di destinazione dei campioni IQ")
    p.add_argument("--port", type=int, default=42000,
                   help="porta XMLRPC; i campioni escono su porta+1 in UDP")
    p.add_argument("--source", default="osmosdr", metavar="SPEC",
                   help="'osmosdr' (radio), 'null' o 'file:<percorso>' (prova senza radio)")
    p.add_argument("--gui", action="store_true",
                   help="mostra la finestra con lo spettro e i controlli (freq/ppm/gain)")
    return p


def _build_tb(opts, gui):
    return OsmoTetraRX(
        channel_freq=opts.freq, samp_rate=opts.samp_rate, first_decim=opts.first_decim,
        out_sample_rate=opts.out_rate, options_low_pass=opts.lowpass,
        sdr_gain=opts.gain, sdr_ifgain=opts.if_gain, sdr_bbgain=opts.bb_gain,
        ppm_corr=opts.ppm, device_args=opts.device_args, udp_dest_addr=opts.udp_host,
        first_port=opts.port, source=opts.source, gui=gui)


def _announce(opts):
    print(
        f"[osmotetra_rx] canale {opts.freq / 1e6:.4f} MHz "
        f"(SDR a {(opts.freq - XLATE_OFFSET) / 1e6:.4f} MHz, offset anti-DC "
        f"{XLATE_OFFSET / 1e3:.0f} kHz), {opts.samp_rate / 1e6:.3f} Ms/s, "
        f"XMLRPC su 0.0.0.0:{opts.port}, UDP su {opts.udp_host}:{opts.port + 1}"
        + ("  [finestra spettro attiva]" if opts.gui else ""),
        flush=True)


def main(argv=None):
    opts = build_parser().parse_args(argv)

    # --- con finestra dello spettro: serve una QApplication ---------------
    if opts.gui:
        from PyQt5 import Qt
        qapp = Qt.QApplication(sys.argv)
        tb = _build_tb(opts, gui=True)      # i sink qtgui vogliono la QApplication già viva
        win = tb.make_gui_window()
        _announce(opts)

        def sig_handler(signum=None, frame=None):
            tb.stop(); tb.wait(); Qt.QApplication.quit()

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
        tb.start()
        win.show()
        timer = Qt.QTimer(); timer.start(500); timer.timeout.connect(lambda: None)
        qapp.exec_()
        return 0

    # --- headless ---------------------------------------------------------
    tb = _build_tb(opts, gui=False)
    _announce(opts)

    stopping = threading.Event()

    def handle_signal(signum, frame):
        if stopping.is_set():
            return
        stopping.set()
        print("[osmotetra_rx] arresto in corso...", flush=True)
        tb.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    tb.start()
    tb.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
