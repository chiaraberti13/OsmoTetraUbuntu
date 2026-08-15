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

<p align="center">
  <b>Software libero e gratuito (GPL-3.0-or-later). Non può essere rivenduto né ridistribuito come prodotto chiuso a pagamento.</b><br>
  <b>Free, open-source software (GPL-3.0-or-later). It may not be resold or redistributed as a paid, closed product.</b>
</p>

---

## Italiano

### Cosa fa OsmoTetra

OsmoTetra prende la catena di monitoraggio TETRA di **Jacek Lipkowski SQ5BPF**
(`osmo-tetra-sq5bpf-2` + codec vocale ETSI + `telive-2`) — normalmente fatta di
tre programmi da avviare a mano in tre terminali, con parametri da ricordare a
memoria — e la trasforma in un'app con un **pannello grafico unico**:
imposti frequenza e guadagno, premi un pulsante, e la catena parte da sola.

In breve, questo è quello che succede quando premi «Avvia»:

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

Non devi capire questo schema per usare l'app — è qui solo per chi è curioso
di sapere cosa succede sotto al pannello. Quello che vedrai in pratica sono
alcune **finestre** che si aprono da sole (pannello, schema GNU Radio,
spettro, telive): tutte spiegate voce per voce più avanti in questa guida.

Questa guida è pensata per chi non ha mai usato OsmoTetra (o TETRA in
generale): segue l'ordine — installazione, primo avvio, elenco comandi,
legenda completa di ogni scheda e ogni campo — così puoi seguirla dall'inizio
alla fine senza dover già sapere nulla.

### Avvertenze, responsabilità e licenza

> **Decifratura — solo a chiave nota.** La decifratura vocale funziona **solo
> se fornisci tu una chiave che già possiedi legittimamente**: il software non
> rompe, forza o aggira alcuna cifratura. Senza la chiave giusta, le chiamate
> cifrate restano semplicemente mute. `telive-2` (da cui questa parte deriva)
> è software sperimentale, pubblicato apertamente dall'autore originale.

> **Responsabilità dell'uso.** Usa questo software solo per ricevere e
> decifrare traffico che **sei autorizzato** a ricevere e decifrare — reti di
> tua proprietà, banchi di prova, attività di ricerca autorizzata. In molti
> Paesi l'ascolto di trasmissioni radio non destinate a te è regolamentato o
> vietato: verifica le leggi applicabili nella tua giurisdizione prima di
> usare l'app. La responsabilità di un uso conforme alla legge è interamente
> di chi usa il software, non degli autori.

> **Software libero e gratuito.** OsmoTetra è distribuito sotto licenza
> **GPL-3.0-or-later** (testo completo in [`LICENSE`](LICENSE)), la stessa dei
> progetti upstream (`osmo-tetra-sq5bpf-2`, `telive-2`) su cui si basa. In
> pratica, in parole semplici:
> - Puoi **usarlo, studiarlo e modificarlo liberamente**, per qualunque scopo.
> - Se **ridistribuisci** il software — modificato o no — devi farlo **sotto
>   la stessa licenza GPL**, con il codice sorgente disponibile: non puoi
>   trasformarlo in un prodotto chiuso.
> - **Non può essere venduto come prodotto proprietario né ridistribuito a
>   pagamento** spacciandolo per software commerciale chiuso: resta libero e
>   gratuito per chiunque lo riceva, in ogni copia successiva.
> - È fornito **così com'è, senza alcuna garanzia** (né di funzionamento, né di
>   idoneità a uno scopo particolare): lo standard di qualunque software
>   libero. Vedi `LICENSE` per il testo legale completo, che prevale su questo
>   riassunto in caso di conflitto.

### Requisiti

- **Ubuntu 24.04 o successive** (testato anche su 25.10, x86 e ARM64).
- Una **RTL-SDR** (o altra radio supportata da gr-osmosdr: HackRF, Airspy…).
- Un'antenna adatta alla banda TETRA che vuoi ricevere.
- Una connessione Internet per l'installazione (scarica ~1-2 GB fra
  dipendenze e sorgenti da compilare).

### Installazione e primo avvio (passo passo)

Questa sezione ti porta, un passo alla volta, da un Ubuntu appena installato
a un ricevitore TETRA funzionante. Non serve alcuna esperienza precedente.

**Passo 1 — Scarica e installa.**

Apri un terminale (cerca «Terminale» nel menu applicazioni, oppure
`Ctrl+Alt+T`) e incolla:

```bash
git clone https://github.com/chiaraberti13/OsmoTetraUbuntu.git
cd OsmoTetraUbuntu
./install.sh
```

Lancialo **da utente normale** (non con `sudo`: lo script chiede la password
da solo, solo quando serve, per `apt` e per creare la cartella `/tetra`).
Lo script:

1. installa tutte le dipendenze di sistema (GNU Radio, driver RTL-SDR,
   librerie…);
2. scarica e compila `osmo-tetra-sq5bpf-2` (il decodificatore), il codec
   vocale ETSI e `telive-2` (il monitor);
3. crea il comando `osmotetra` e la voce **«OsmoTetra»** nel menu
   applicazioni.

Ci mette qualche minuto (di più se compili su una scheda ARM64 poco
potente). **Non tocca la radio**: puoi installare anche senza avere ancora
la chiavetta collegata — serve solo quando userai l'app, non durante
l'installazione.

Se qualcosa va storto durante l'installazione, lo script si ferma con un
messaggio che spiega cosa è successo; il log completo resta in
`~/telive2/logs/install.log` per confrontarlo o allegarlo se chiedi aiuto.

**Passo 2 — Riapri il terminale.**

Il comando `osmotetra` viene aggiunto al tuo `PATH` (l'elenco di cartelle in
cui il sistema cerca i comandi): perché il terminale se ne accorga, **chiudi
e riapri il terminale**, oppure esegui `source ~/.bashrc` in quello già
aperto.

**Passo 3 — Collega l'hardware.**

Collega la chiavetta RTL-SDR a una porta USB del PC e avvita l'**antenna**
sulla chiavetta (senza antenna non riceverai nulla di utile).

**Passo 4 — Apri OsmoTetra.**

Due modi equivalenti:
- cerca **«OsmoTetra»** nel menu applicazioni e fai clic;
- oppure apri un terminale e scrivi `osmotetra`.

Si apre il **pannello**: è la finestra principale, quella da cui parte tutto.

**Passo 5 — Imposta i parametri.**

Nel pannello, scheda **Ricezione** (si apre già selezionata):

- **Frequenza del canale** — la frequenza del canale di controllo TETRA che
  vuoi ascoltare, in MHz (es. `390.5`). Se non la conosci, chiedi a chi
  gestisce la rete che vuoi monitorare, oppure usa lo spettro (vedi più
  avanti) per individuare le portanti attive. Scrivi **solo** la frequenza
  del canale: l'app tiene da sola l'SDR sintonizzato 500 kHz più in là
  (un accorgimento tecnico, l'«offset anti-DC», che allontana il segnale dal
  disturbo elettrico che ogni chiavetta RTL-SDR genera esattamente al centro
  della sua banda).
- **Guadagno RF** — quanto amplificare il segnale ricevuto, in dB. Il valore
  di partenza (`38`) va bene per la maggior parte delle chiavette; se non
  ricevi nulla, prova ad alzarlo, se il segnale è distorto/rumoroso prova ad
  abbassarlo.
- **Sorgente SDR** — lascia **«Chiavetta locale (USB)»** se la chiavetta è
  collegata direttamente a questo PC. (Se invece la usi da dentro una
  macchina virtuale, vedi la sezione **«Chiavetta in una macchina virtuale»**
  più avanti.)

Tutti gli altri campi hanno un valore di default sensato: non serve
toccarli al primo avvio. Se vuoi capire cosa fa ciascuno nel dettaglio, la
**legenda completa** (qui sotto) descrive ogni singolo campo del pannello.

**Passo 6 — Avvia.**

Premi il pulsante **«▶ Avvia»**. Si aprono, in sequenza:

1. **GNU Radio Companion**, con lo schema a blocchi del ricevitore già
   disegnato — puoi lasciarlo pure in secondo piano, è solo una finestra di
   consultazione (spiegata più avanti);
2. la **finestra dello spettro** — due grafici che mostrano il segnale radio
   in arrivo;
3. **`telive`** — il monitor vero e proprio, in un terminale a schermo
   pieno.

**Passo 7 — Verifica che stai ricevendo.**

Torna al pannello e apri la scheda **Stato**: entro pochi secondi le sei
righe passano da `·` (grigio, «non ancora noto») a **✓** (verde, «tutto a
posto»). In particolare, quando la riga **«Rete rilevata»** mostra qualcosa
come `MCC 222 · MNC 55 · CC 30 · ↓ 390.5000 MHz`, stai ricevendo davvero la
rete TETRA.

Puoi controllare anche direttamente in **`telive`**: in alto compaiono
**`MCC`**, **`MNC`** e le frequenze (es. `MCC: 222 MNC: 55 …
Control:390.5000MHz`) al posto degli zeri iniziali. Le chiamate che passano
sul canale compaiono nell'elenco principale e nella finestra dei messaggi in
basso.

Non vedi nulla dopo un minuto? Vai alla sezione **«Se qualcosa non va»** più
in basso: il pannello Stato ti dice già a che punto si è fermata la catena.

**Passo 8 — Ferma.**

Quando hai finito, premi **«■ Ferma»** nel pannello (oppure premi `q` dentro
`telive`): tutta la catena si chiude in ordine, comprese le finestre aperte
automaticamente.

### Elenco dei comandi

Tutto quello che puoi fare da terminale passa dal comando `osmotetra`. Ogni
riga della tabella corrisponde a una finestra o a un'azione; l'ordine va dal
«pezzo singolo» più piccolo fino a «tutto insieme»:

| Comando | Cosa fa |
|---|---|
| `osmotetra` | apre il **pannello** grafico — il modo consigliato per iniziare |
| `osmotetra grc` | apre **solo** GNU Radio Companion, con lo schema a blocchi |
| `osmotetra spettro 390.5` | apre **solo** la finestra dello spettro, sul canale indicato (per guardare/sintonizzare senza avviare il resto) |
| `osmotetra monitor 390.5` | avvia ricevitore + telive, **senza** aprire lo spettro |
| `osmotetra avvia 390.5` | avvia **tutto insieme**: schema a blocchi + ricevitore + spettro + telive |
| `osmotetra chiavi` | apre **solo** l'editor delle chiavi di decifratura |
| `osmotetra stop` | ferma tutta la catena, qualunque cosa fosse in esecuzione |
| `osmotetra aiuto` | stampa questo stesso elenco nel terminale |

Dove il comando accetta una frequenza (`spettro`, `monitor`, `avvia`), è
sempre in **MHz** e **facoltativa**: se la ometti, l'app usa il valore che
avevi lasciato nel pannello (o `390.5` la primissima volta). Dopo la
frequenza puoi anche indicare il dispositivo SDR da usare, ad esempio:

```bash
osmotetra avvia 390.5 rtl=0                          # prima chiavetta collegata
osmotetra avvia 390.5 rtl_tcp=192.168.64.1:1234      # chiavetta via rete (VM)
```

**Variabili d'ambiente (uso avanzato da terminale).** Se lanci la catena da
`avvia.sh` invece che dal pannello, alcuni dettagli sono regolabili con
variabili d'ambiente, da anteporre al comando:

| Variabile | A cosa serve | Default |
|---|---|---|
| `OSMOTETRA_HOME` | dove si trovano i sorgenti compilati | `~/telive2` |
| `OSMOTETRA_GAIN` | guadagno RF in dB | `38` |
| `OSMOTETRA_PPM` | correzione di frequenza in ppm | `0` |
| `OSMOTETRA_NOGUI` | se valorizzata, non apre mai la finestra dello spettro | (spenta) |
| `OSMOTETRA_NOGRC` | se valorizzata, non apre mai GNU Radio Companion | (spenta) |
| `OSMOTETRA_LANG` | lingua del pannello: `it` oppure `en` | `it` |
| `OSMOTETRA_PYTHON` | interprete Python con i binding GNU Radio | `python3` |

Esempio: `OSMOTETRA_NOGRC=1 osmotetra avvia 390.5` avvia tutto **tranne**
GNU Radio Companion, una volta sola, senza cambiare le impostazioni salvate.

### Legenda del pannello (voce per voce)

Questa sezione descrive **ogni singolo elemento** del pannello principale:
non dovrebbe mancarne nessuno. Usala come riferimento quando non sei sicuro
di cosa faccia un campo.

#### Barra superiore (sempre visibile)

Questi elementi restano in vista qualunque scheda tu abbia aperta:

| Elemento | Cosa fa |
|---|---|
| **Modalità** | selettore **Base** / **Avanzata**. In **Base** vedi solo l'essenziale; in **Avanzata** compaiono anche la scheda **Avanzate**, la correzione ppm e il campo dispositivo manuale. Cambia in qualunque momento, anche a catena ferma. |
| **Lingua** | selettore **Italiano** / **English**: cambia la lingua di tutto il pannello (e dei messaggi diagnostici del flowgraph). Cambiandola, l'app **si riavvia da sola** per applicarla (fermando prima la ricezione, se era in corso); la scelta resta salvata per le volte successive. |
| **▶ Avvia** | avvia l'intera catena con i parametri impostati nella scheda Ricezione. Disabilitato mentre la catena è già in esecuzione. |
| **■ Ferma** | ferma tutta la catena (flowgraph, ricevitore, telive) in ordine. Disabilitato quando non c'è nulla in esecuzione. |
| **◆ Chiavi di decifratura…** | apre l'editor delle chiavi (vedi la sezione dedicata più avanti). Disponibile sia a catena ferma sia in esecuzione. |
| **Barra di stato** (striscia colorata sotto i pulsanti) | riassume lo stato in una parola: **grigia** «Fermo», **gialla** «Avvio in corso…», **verde** «In esecuzione — guarda la finestra di telive». |

#### Scheda «Ricezione»

Quello che serve per partire, più i profili salvati.

| Campo | Cosa fa |
|---|---|
| **Frequenza del canale** | la frequenza (MHz) del canale di controllo TETRA da ascoltare. Ha una freccetta che si muove di 25 kHz per volta (il passo dei canali TETRA); se scrivi un valore che cade fuori da questo reticolo, sotto il campo compare un avviso con il canale valido più vicino. |
| **Guadagno RF** | amplificazione del segnale ricevuto, in dB (0–50). Default `38`. |
| **Sorgente SDR** | **Chiavetta locale (USB)** se la radio è collegata a questo PC; **Chiavetta remota (rete / VM)** se è su un'altra macchina raggiungibile in rete (tipicamente: dentro una macchina virtuale). |
| **Indirizzo remoto** (IP / porta) | compare solo se «Sorgente SDR» è impostata su remota: l'indirizzo IP e la porta del servizio `rtl_tcp` che espone la chiavetta in rete. Vedi «Chiavetta in una macchina virtuale». |
| **Mostra la finestra dello spettro (grafici + controlli)** | casella, spuntata di default. Se spuntata, «Avvia» apre anche la finestra dello spettro; se la togli, quella finestra non si apre (utile se vuoi solo `telive` in primo piano). |
| **Apri anche GNU Radio Companion (schema a blocchi)** | casella, spuntata di default (se il file dello schema è presente). Se spuntata, «Avvia» apre anche GNU Radio Companion col diagramma a blocchi del ricevitore, di sola consultazione. Vedi la sezione dedicata. |
| **Profili → menu a tendina** | elenco dei profili salvati (nome libero, scelto da te). Selezionandone uno, i campi sopra si riempiono con i valori salvati in quel profilo. |
| **Profili → «Salva come…»** | salva i valori attuali (frequenza, guadagno, sorgente, ecc.) come nuovo profilo, o aggiorna uno esistente se usi lo stesso nome. Chiede il nome con una finestrella. I profili **non contengono mai chiavi di decifratura**. |
| **Profili → «Elimina»** | rimuove il profilo selezionato nel menu a tendina, dopo conferma. |

#### Scheda «Stato»

Sei righe che riassumono a colpo d'occhio a che punto è la catena. Ogni riga
ha un simbolo (**✓** verde = a posto, **!** ambra = manca qualcosa, **·**
grigio = non ancora noto) e passando il mouse sopra compare la spiegazione
estesa.

| Riga | Cosa significa **✓** | Cosa significa **!** |
|---|---|---|
| **Ricevitore SDR** | la radio è aperta e il flowgraph gira | — (se non è verde, guarda i log: la radio probabilmente non si è aperta) |
| **Segnale in arrivo** | il decoder riceve campioni dalla radio e misura lo scostamento di frequenza | nessun campione: controlla frequenza, guadagno o antenna scollegata |
| **Sincronizzazione TETRA** | il decoder ha agganciato la struttura delle trame ed è su un vero canale di controllo | non agganciato: sei forse su un canale che non è di controllo, o il segnale è troppo debole |
| **Rete rilevata** | mostra `MCC · MNC · CC · LA · ↓ frequenza` letti dai messaggi della cella | nessuna rete letta finora |
| **Traffico cifrato** | il traffico che senti è in chiaro | il traffico è cifrato — via etere si sa *che* lo è, non *con quale* algoritmo (vedi il riquadro sotto) |
| **Chiavi configurate** | quante chiavi ci sono nel keyfile e per quale rete, con l'algoritmo scelto | — (mostra sempre lo stato, anche a catena ferma) |

> **Attenzione a cosa dice davvero la radio.** Via etere TETRA segnala **se**
> il traffico è cifrato, **non quale algoritmo** usa. L'algoritmo
> (`TEA1`…`TEA7`) è un'informazione che **devi conoscere tu** (dalla rete o
> dal banco di prova) e che scegli nell'editor delle chiavi — il pannello non
> può indovinarlo.

#### Scheda «Rete»

I dati della cella che stai ascoltando, letti dai messaggi di rete non
appena la ricezione aggancia il canale. Ogni campo ha un **`?`** su cui
passare il mouse per la spiegazione estesa.

| Campo | Cosa mostra |
|---|---|
| **MCC (Paese)** | *Mobile Country Code*: il Paese della rete (es. `222` = Italia). |
| **MNC (rete)** | *Mobile Network Code*: quale rete, dentro quel Paese. |
| **Codice colore (CC)** | *Colour Code*: distingue celle vicine sulla stessa frequenza; se cambia mentre ascolti, ti sei spostato su un'altra cella. |
| **Area di localizzazione (LA)** | *Location Area*: il gruppo di celle in cui i terminali sono registrati. |
| **Frequenza di discesa** | la frequenza del canale di controllo in discesa (dalla rete verso i terminali) — quella che stai ascoltando. |
| **Cifratura** | se il traffico attuale è cifrato o in chiaro (vedi la nota sulla scheda Stato). |
| **Ultimo aggiornamento** | l'orario dell'ultimo messaggio di rete ricevuto. |

Sotto ai campi, il pulsante **«▸ Copia dettagli rete»** copia un riassunto
in testo semplice di tutti i valori sopra negli appunti, pronto da incollare
altrove (una nota, una email…).

#### Scheda «Chiavi»

Un riepilogo di sola lettura di cosa c'è nel keyfile: quante chiavi, per
quale rete, con quale algoritmo. Il pulsante **«◆ Apri l'editor delle
chiavi…»** apre l'editor grafico completo (descritto nella sezione
successiva). Sotto compare anche il percorso del file sul disco.

#### Scheda «Log»

| Elemento | Cosa fa |
|---|---|
| **Log tecnico (mostra tutto)** | casella, spenta di default. Da spenta, il log mostra solo i messaggi pensati per te (avvio, arresto, errori). Da accesa, mostra anche l'output grezzo di flowgraph e ricevitore — utile da copiare quando chiedi aiuto. Puoi accenderla/spegnerla in ogni momento senza perdere nulla di ciò che è già passato. |
| **▪ Esporta diagnostica…** | salva su file un rapporto di testo con versioni di sistema, impostazioni correnti, componenti installati, stato, dati di rete e le ultime righe di log — **senza alcuna chiave**: del keyfile riporta solo quante chiavi ci sono e per quale rete, e ogni sequenza che somiglia a una chiave viene rimossa dal log. Pensato per essere allegato quando chiedi aiuto. |
| **Riquadro del log** | il testo vero e proprio, aggiornato in tempo reale. |

#### Scheda «Avanzate» (solo in modalità Avanzata)

Compare solo se **Modalità** è impostata su **Avanzata**; in **Base**
sparisce del tutto.

| Campo | Cosa fa |
|---|---|
| **Correzione (ppm)** | correzione fine della frequenza, in parti per milione, per compensare la deriva dell'oscillatore della chiavetta. Parti da `0`; se in `telive` l'AFC è lontano da zero (vedi «I tasti di telive»), ritocca questo valore. |
| **Dispositivo (manuale)** | campo libero (con alcuni preset già pronti nel menu a tendina) per una stringa `gr-osmosdr` scritta a mano, ad es. `rtl=0`, `hackrf=0`, `rtl_tcp=IP:porta`. Se lo lasci vuoto, vale la scelta fatta in «Sorgente SDR» nella scheda Ricezione. |
| **«Dove sono le cose»** | un riepilogo di sola lettura dei percorsi usati dall'app: sorgenti e binari, decoder, monitor telive, keyfile, interprete Python con GNU Radio, e le porte di rete usate internamente. Utile per il debug o per chi vuole curiosare nei file. |

### Legenda dell'editor delle chiavi

L'editor si apre col pulsante **«◆ Chiavi di decifratura…»** nel pannello,
dalla scheda **Chiavi**, oppure da terminale con `osmotetra chiavi`. Serve a
scrivere il keyfile che usa il decoder **senza dover modificare un file di
testo a mano**. Parte in **modalità guidata**: i campi tecnici avanzati sono
nascosti finché non li richiami esplicitamente.

#### Sezione «Rete»

| Campo | Cosa fa |
|---|---|
| **MCC** | il codice del Paese della rete (es. `222`). Viene completato da solo a 4 cifre quando esci dal campo (`222` → `0222`): è il formato che il keyfile richiede. |
| **MNC** | il codice della rete dentro quel Paese (es. `55`), completato a 4 cifre allo stesso modo. |
| **↧ Usa rete rilevata** | pulsante che compila MCC e MNC al posto tuo, con i valori letti dall'aria durante la ricezione. **Attivo solo dopo** che il pannello Stato ha mostrato «Rete rilevata»: se non l'hai ancora vista, il pulsante resta disabilitato con una spiegazione nel tooltip. |
| **Algoritmo (ksg_type)** | menu a tendina `TEA1`…`TEA7`. **Scegli l'algoritmo che sai essere usato dalla tua rete o dal tuo banco di prova — mai «a occhio» in base al Paese**: via etere TETRA segnala solo *se* il traffico è cifrato, non *quale* algoritmo usa. |
| **Classe di sicurezza** | `2` (SCK, chiave statica) oppure `3` (CCK+DCK, chiavi derivate). Se non sai quale scegliere, chiedi a chi gestisce la rete. |

#### Sezione «Chiavi» (tabella)

| Colonna | Cosa contiene |
|---|---|
| **Tipo di chiave** | quale ruolo ha la chiave: di solito `1` (CCK/SCK); `16` è per una chiave TEA1 accorciata a 32 bit. Le altre voci (`2` DCK, `4` MGCK, `8` GCK) sono per casi più specifici. |
| **Chiave (80 bit hex)** | il valore della chiave, in cifre esadecimali (`0`-`9`, `a`-`f`): 20 cifre = 80 bit, il formato standard. Per il tipo `16` (TEA1 a 32 bit) inserisci le 8 cifre e riempi il resto con zeri fino a 20 (es. `12345678` diventa `12345678000000000000`). Il campo è mascherato come una password; vedi la casella «Mostra chiavi» per rivelarlo. |
| **MCC / MNC** *(colonne avanzate)* | rete specifica per questa singola chiave, se diversa da quella impostata sopra. Lasciale vuote per usare i valori della sezione Rete. |
| **addr** *(colonna avanzata)* | indirizzo associato alla chiave (8 cifre); `00000000` va bene nella maggior parte dei casi. |
| **key_num** *(colonna avanzata)* | numero progressivo della chiave, quando la rete ne usa più di una dello stesso tipo. |

Sopra la tabella:

| Elemento | Cosa fa |
|---|---|
| **+ Aggiungi chiave** | aggiunge una riga vuota alla tabella. |
| **− Rimuovi selezionata** | rimuove la riga attualmente selezionata. |
| **Mostra chiavi** | casella: se spuntata, il testo delle chiavi diventa leggibile invece che mascherato — utile per ricontrollare quanto scritto prima di salvare. |
| **Parametri avanzati ▼** | casella: mostra/nasconde le colonne tecniche (MCC, MNC, addr, key_num) per singola chiave. Spenta di default: nella maggior parte dei casi bastano Tipo e Chiave. |

#### Pulsanti in basso

| Pulsante | Cosa fa |
|---|---|
| **▸ Mostra file generato** | apre un'anteprima di sola lettura di esattamente ciò che l'editor scriverà nel keyfile (le righe `network …` e `key …`) — senza salvare nulla. Utile per capire il formato o per confrontare con un keyfile scritto a mano. |
| **Ricarica dal file** | scarta le modifiche non salvate e ricarica i campi dal keyfile su disco. |
| **▪ Salva** | valida i campi (avvisa se una chiave non è esadecimale o non è lunga 20 cifre), mostra un riepilogo (rete, algoritmo, numero di chiavi, percorso del file) e, dopo conferma, scrive il keyfile con permessi riservati al tuo utente (`0600` — nessun altro utente del PC può leggerlo). |
| **Chiudi** | chiude l'editor. Le modifiche non salvate vengono perse. |

> Senza chiavi (o con la sola chiave d'esempio che arriva con l'installazione)
> sentirai **solo le chiamate in chiaro**; quelle cifrate restano mute. È il
> comportamento atteso, non un errore.

### Legenda della finestra dello spettro

Si apre insieme al resto con «Avvia» (se la casella nella scheda Ricezione è
spuntata), da sola con `osmotetra spettro 390.5`, oppure premendo «Avvia»
con la casella tolta e poi riaprendola in un secondo momento con lo stesso
comando. È lo stesso pannello del flowgraph originale di SQ5BPF, con in più
i comandi standard di GNU Radio per i due grafici.

**Controlli in alto (a caldo — l'effetto è immediato):**

| Elemento | Cosa fa |
|---|---|
| **Frequenza canale** | mostra/permette di cambiare la frequenza del canale che stai ascoltando (es. `390.5M`). |
| **Fine tune** | ritocco fine della sintonia in kHz, con cursore o casella numerica. |
| **ppm** | correzione della frequenza, equivalente al campo «Correzione (ppm)» del pannello. |
| **gain** | guadagno RF, equivalente al campo «Guadagno RF» del pannello. |

**I due grafici:**

| Grafico | Cosa mostra |
|---|---|
| **Sinistro (banda intera)** | lo spettro completo della banda campionata (2 MHz): ci vedi il segnale TETRA e i canali vicini, utile per trovare la portante giusta. |
| **IF (destro)** | il singolo canale dopo il filtro (~62,5 kHz di banda): utile per centrare bene la sintonia — la forma «a tetto piatto» larga circa 25 kHz è il segno di una portante TETRA. |

**Controlli standard di GNU Radio, a fianco di ciascun grafico** (uguali per
entrambi i grafici; non serve toccarli per ricevere, sono per chi vuole
analizzare lo spettro più a fondo):

| Elemento | Cosa fa |
|---|---|
| **Trace Options → Max Hold / Min Hold** | mostra il valore massimo/minimo osservato nel tempo per ogni frequenza, invece del valore istantaneo. |
| **Trace Options → Avg** | quanto mediare la visualizzazione nel tempo (più a destra = più stabile ma più lenta a reagire). |
| **Axis Options → Grid / Axis Labels** | mostra/nasconde la griglia e le etichette degli assi. |
| **Axis Options → Y Range (+/−) / Ref Level (+/−)** | regolano manualmente la scala verticale del grafico (in dB). |
| **Axis Options → Autoscale** | adatta automaticamente la scala verticale al segnale presente in quel momento. |
| **FFT → dimensione / finestra** | numero di punti della trasformata di Fourier e tipo di finestratura usati per calcolare lo spettro: valori più alti danno più dettaglio in frequenza ma aggiornano più lentamente. |
| **Trigger** | condizione per «congelare» il grafico su un evento (di default `Free`, cioè nessun trigger: il grafico scorre continuamente). |
| **Extras → Stop** | ferma l'aggiornamento di quel singolo grafico (non la ricezione). |

### GNU Radio Companion (schema a blocchi)

Oltre alle finestre già descritte, con **«▶ Avvia»** (o `osmotetra avvia`) si
apre anche **GNU Radio Companion**, il programma di GNU Radio con lo schema
a blocchi — sorgente SDR, filtro, AGC, ricampionatore, uscita UDP — già
disegnato e collegato, esattamente come nella versione originale della
catena SQ5BPF.

È **di sola consultazione**: la ricezione vera la fa già la parte automatica
(il flowgraph headless avviato dal pannello), quindi non c'è alcun conflitto
sulla chiavetta. Serve per vedere o modificare lo schema, capire come
funziona il flusso del segnale, o confrontare i parametri con quelli del
pannello.

**Per aprirlo da solo**, senza avviare il resto: `osmotetra grc`, oppure la
casella **«Apri anche GNU Radio Companion (schema a blocchi)»** nella scheda
*Ricezione* del pannello controlla se si apre insieme al resto (spuntata di
default, se il file dello schema è presente sul disco).

> ⚠ Non premere **Execute** dentro GNU Radio Companion mentre la ricezione è
> già avviata dal pannello: proverebbe ad aprire la stessa chiavetta una
> seconda volta, e fallirebbe. Usalo per guardare e capire lo schema, non per
> farlo partire in parallelo alla ricezione automatica.

### I tasti di telive

L'interfaccia di `telive` resta quella originale, in ncurses (a schermo
pieno nel terminale). I tasti più usati:

| Tasto | Effetto |
|---|---|
| `?` | aiuto, elenco completo dei tasti disponibili |
| `t` | alterna finestra SSI / finestra delle frequenze (mostra l'**AFC**) |
| `R` | attiva/disattiva la registrazione delle chiamate |
| `l` | attiva/disattiva il log della segnalazione |
| `M` / `m` | silenzia tutto / silenzia solo gli SSI sconosciuti |
| `q` | esci da `telive` (ferma anche il resto della catena, se avviata dal pannello) |

**Correzione fine (ppm).** Premi `t` per aprire la finestra delle frequenze:
se il valore **AFC** mostrato è lontano da zero, ritocca il campo **ppm**
(nella finestra dello spettro o nella scheda Avanzate del pannello) finché
non si avvicina a zero — significa che l'oscillatore della chiavetta ha una
piccola deriva che stai compensando manualmente.

### Chiavetta in una macchina virtuale

Se Ubuntu gira in una macchina virtuale il cui hypervisor **non inoltra
l'USB** alla VM (capita ad esempio con le VM di Apple Virtualization su
Mac), la chiavetta collegata al computer fisico non è visibile da dentro la
VM. La soluzione è lasciare la chiavetta al **sistema ospitante** (il Mac o
PC fisico) ed esporla in rete verso la VM:

1. Sul sistema **ospitante** (non nella VM), installa e avvia `rtl_tcp`:
   ```bash
   rtl_tcp -a 0.0.0.0 -p 1234
   ```
   e lascia quella finestra aperta per tutta la sessione.
2. Nella VM, nel pannello OsmoTetra, scheda Ricezione, imposta **Sorgente
   SDR** = **«Chiavetta remota (rete / VM)»**.
3. Compila **Indirizzo remoto**: l'**IP dell'host** (visibile dalla VM — per
   le VM di Apple Virtualization è tipicamente `192.168.64.1`) e la
   **porta** `1234`.

L'app costruisce da sola la stringa tecnica necessaria
(`rtl_tcp=192.168.64.1:1234`): non devi scriverla a mano.

### Se qualcosa non va

- **«Nessun dispositivo SDR trovato»** — la chiavetta non è vista dal
  sistema. Controlla con `rtl_test -t`. Se compare
  `usb_claim_interface error -6`, il driver DVB-T generico è ancora
  caricato: scollega/ricollega la chiavetta o riavvia il PC. In una VM, usa
  `rtl_tcp` (vedi sopra).
- **«rtl_tcp non risponde»** — sul sistema ospitante il comando `rtl_tcp` non
  è in esecuzione, oppure un firewall blocca la porta `1234`.
- **`telive` si apre ma l'intestazione resta a zero** — guarda prima il
  riquadro **Stato** nel pannello: ti dice se manca il **segnale**
  (frequenza sbagliata, guadagno troppo basso, antenna scollegata) o solo la
  **sincronizzazione** (quel canale non è di controllo, o non c'è copertura
  di rete in quel punto). Poi guarda lo spettro (`osmotetra spettro 390.5`):
  il segnale TETRA deve essere ben visibile e ben centrato nel grafico IF.
- **Le chiamate cifrate restano mute** — normale senza le chiavi giuste:
  aprile con `osmotetra chiavi` e inserisci le tue.
- **GNU Radio Companion non si apre** — verifica che `gnuradio-companion`
  sia installato (`which gnuradio-companion`): fa parte del pacchetto
  `gnuradio` che `install.sh` installa già, quindi di norma basta rilanciare
  `./install.sh`. Se non ti serve, togli la spunta nella scheda *Ricezione*
  oppure esporta `OSMOTETRA_NOGRC=1` prima di `avvia.sh`.
- **La build di telive fallisce su nanohttp** — succede solo su libxml2 ≥
  2.14 (Ubuntu 25.10 e successive); l'installer applica da solo la patch che
  lo risolve, non serve intervenire a mano.
- **Devi chiedere aiuto?** Nel pannello, scheda **Log**, spunta **«Log
  tecnico (mostra tutto)»** e copia quello che compare, oppure usa **«▪
  Esporta diagnostica…»** per un file completo pronto da allegare (non
  contiene mai chiavi).

Tutti i log restano comunque salvati in `~/telive2/logs/`.

### Disinstallazione

```bash
./uninstall.sh          # conserva registrazioni e log
./uninstall.sh --purge  # rimuove tutto, compresa /tetra
```

---

## English

### What OsmoTetra does

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

### Warnings, responsibility and licence

> **Decryption — known keys only.** Voice decryption only works **if you
> supply a key you already legitimately own**: the software does not break,
> force, or bypass any encryption. Without the right key, encrypted calls
> simply stay silent. `telive-2` (which this part is built on) is
> experimental software, openly published by its original author.

> **Your responsibility.** Only use this software to receive and decrypt
> traffic you are **authorized** to receive and decrypt — your own networks,
> test benches, authorized research. In many countries, listening to radio
> transmissions not addressed to you is regulated or prohibited: check the
> laws that apply in your jurisdiction before using the app. Responsibility
> for lawful use rests entirely with the person using the software, not with
> its authors.

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

### Requirements

- **Ubuntu 24.04 or newer** (also tested on 25.10, x86 and ARM64).
- An **RTL-SDR** (or another gr-osmosdr-supported radio: HackRF, Airspy…).
- An antenna suited to the TETRA band you want to receive.
- An Internet connection for installation (downloads ~1-2 GB between
  dependencies and sources to compile).

### Install and first run (step by step)

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

### Command list

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

### Panel legend (field by field)

This section describes **every single element** of the main panel: none
should be missing. Use it as a reference whenever you're unsure what a
field does.

#### Top bar (always visible)

These stay visible no matter which tab you have open:

| Element | What it does |
|---|---|
| **Modalità** (Mode) | **Base** / **Avanzata** (Advanced) selector. In **Base** you see only the essentials; in **Avanzata** the **Avanzate** tab also appears, along with ppm correction and the manual device field. Switch it any time, even while stopped. |
| **Lingua** (Language) | **Italiano** / **English** selector: changes the language of the whole panel (and the flowgraph's diagnostic messages). Changing it makes the app **restart itself** to apply it (stopping reception first, if it was running); the choice is saved for next time. |
| **▶ Avvia** (Start) | starts the whole chain with the parameters set in the Ricezione tab. Disabled while the chain is already running. |
| **■ Ferma** (Stop) | stops the whole chain (flowgraph, receiver, telive) in order. Disabled when nothing is running. |
| **◆ Chiavi di decifratura…** (Decryption keys…) | opens the key editor (see the dedicated section below). Available both while stopped and while running. |
| **Status bar** (coloured strip under the buttons) | sums up the state in one word: **grey** “Fermo” (Stopped), **yellow** “Avvio in corso…” (Starting…), **green** “In esecuzione — guarda la finestra di telive” (Running — watch the telive window). |

#### “Ricezione” (Reception) tab

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

#### “Stato” (Status) tab

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

> **Mind what the radio actually tells you.** Over the air TETRA signals
> **whether** traffic is encrypted, **not which algorithm** it uses. The
> algorithm (`TEA1`…`TEA7`) is something **you need to know** (from the
> network or the test bench) and choose in the key editor — the panel can't
> guess it.

#### “Rete” (Network) tab

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

#### “Chiavi” (Keys) tab

A read-only summary of what's in the keyfile: how many keys, for which
network, with which algorithm. The **“◆ Apri l'editor delle chiavi…”**
(Open the key editor…) button opens the full graphical editor (described in
the next section). The file's path on disk is shown below.

#### “Log” tab

| Element | What it does |
|---|---|
| **Log tecnico (mostra tutto)** (Technical log, show everything) | box, off by default. When off, the log shows only the messages meant for you (start, stop, errors). When on, it also shows the raw output of the flowgraph and receiver — handy to copy when asking for help. You can toggle it at any time without losing anything already scrolled by. |
| **▪ Esporta diagnostica…** (Export diagnostics…) | saves a text report to a file with system versions, current settings, installed components, status, network data and the last log lines — **with no keys at all**: of the keyfile it only reports how many keys there are and for which network, and any sequence that looks like a key is stripped from the log. Meant to be attached when you ask for help. |
| **Log box** | the actual text, updated live. |

#### “Avanzate” (Advanced) tab (Advanced mode only)

Only shows up when **Modalità** is set to **Avanzata**; in **Base** it
disappears entirely.

| Field | What it does |
|---|---|
| **Correzione (ppm)** (Correction) | fine frequency correction, in parts per million, to compensate for the dongle's oscillator drift. Start at `0`; if `telive`'s AFC is far from zero (see “telive keys”), adjust this value. |
| **Dispositivo (manuale)** (Device, manual) | free-text field (with a few ready-made presets in the dropdown) for a hand-written `gr-osmosdr` string, e.g. `rtl=0`, `hackrf=0`, `rtl_tcp=IP:port`. If left empty, the choice made in “Sorgente SDR” on the Ricezione tab is used instead. |
| **“Dove sono le cose”** (Where things are) | a read-only summary of the paths the app uses: sources and binaries, decoder, telive monitor, keyfile, the Python interpreter with GNU Radio, and the network ports used internally. Handy for debugging or for anyone curious about the files. |

### Key editor legend

The editor opens with the **“◆ Chiavi di decifratura…”** button in the
panel, from the **Chiavi** tab, or from a terminal with `osmotetra chiavi`.
It writes the keyfile the decoder uses **without editing a text file by
hand**. It starts in **guided mode**: advanced technical fields stay hidden
until you explicitly ask for them.

#### “Rete” (Network) section

| Field | What it does |
|---|---|
| **MCC** | the network's country code (e.g. `222`). Padded to 4 digits by itself when you leave the field (`222` → `0222`): that's the format the keyfile requires. |
| **MNC** | the network code within that country (e.g. `55`), padded to 4 digits the same way. |
| **↧ Usa rete rilevata** (Use detected network) | button that fills MCC and MNC for you, with values read from the air during reception. **Only enabled after** the Status panel has shown “Rete rilevata” (Network detected): if you haven't seen it yet, the button stays disabled with an explanation in its tooltip. |
| **Algoritmo (ksg_type)** (Algorithm) | `TEA1`…`TEA7` dropdown. **Pick the algorithm you know your network or test bench uses — never guess it from the country**: over the air TETRA only signals *whether* traffic is encrypted, not *which* algorithm it uses. |
| **Classe di sicurezza** (Security class) | `2` (SCK, static key) or `3` (CCK+DCK, derived keys). If you don't know which to pick, ask whoever runs the network. |

#### “Chiavi” (Keys) section (table)

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

#### Buttons at the bottom

| Button | What it does |
|---|---|
| **▸ Mostra file generato** (Show generated file) | opens a read-only preview of exactly what the editor will write to the keyfile (the `network …` and `key …` lines) — without saving anything. Handy to understand the format or compare against a hand-written keyfile. |
| **Ricarica dal file** (Reload from file) | discards unsaved changes and reloads the fields from the keyfile on disk. |
| **▪ Salva** (Save) | validates the fields (warns if a key isn't hex or isn't 20 digits long), shows a summary (network, algorithm, number of keys, file path) and, after confirmation, writes the keyfile with owner-only permissions (`0600` — no other user on the PC can read it). |
| **Chiudi** (Close) | closes the editor. Unsaved changes are lost. |

> Without keys (or with only the sample key that ships with the install)
> you will hear **clear calls only**; encrypted ones stay silent. That is
> the expected behaviour, not an error.

### Spectrum window legend

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

### GNU Radio Companion (block diagram)

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

> ⚠ Don't press **Execute** inside GNU Radio Companion while reception is
> already running from the panel: it would try to open the same dongle a
> second time, and fail. Use it to look at and understand the diagram, not
> to run it in parallel with automated reception.

### telive keys

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

### Dongle in a virtual machine

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

### Troubleshooting

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

### Uninstall

```bash
./uninstall.sh          # keeps recordings and logs
./uninstall.sh --purge  # removes everything, including /tetra
```

---

## Crediti / Credits

- **Jacek Lipkowski SQ5BPF** — [osmo-tetra-sq5bpf-2](https://github.com/sq5bpf/osmo-tetra-sq5bpf-2)
  e [telive-2](https://github.com/sq5bpf/telive-2), la catena di ricezione e decodifica.
  `osmotetra_rx.grc` (lo schema in GNU Radio Companion) è il file originale
  dell'autore, incluso invariato da telive-2.
- Progetto originale osmo-tetra di **Harald Welte** e collaboratori.
- Codec vocale **ETSI** EN 300 395-2.

OsmoTetra è distribuito sotto **GPL-3.0-or-later** (vedi `LICENSE`), come i
sorgenti di upstream su cui si basa. È software **libero e gratuito**: puoi
usarlo, studiarlo e modificarlo, ma non rivenderlo né ridistribuirlo come
prodotto chiuso a pagamento — ogni copia, anche modificata, resta libera per
chi la riceve.

OsmoTetra is distributed under **GPL-3.0-or-later** (see `LICENSE`), like
the upstream sources it's built on. It is **free, open-source software**:
you may use, study and modify it, but not resell it or redistribute it as a
paid, closed product — every copy, even a modified one, stays free for
whoever receives it.
