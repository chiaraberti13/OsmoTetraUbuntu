# Quando non arriva niente

Il primo comando da dare, sempre:

```sh
osmotetra check
```

Verifica dipendenze e configurazione e dice cosa manca. Se è tutto verde e
comunque non arriva nulla, si procede a ritroso lungo la catena.

## Dove si è fermata la catena?

Gli indicatori in cima alla finestra dicono quali stadi sono attivi. Il modo
più rapido per capire dove si interrompe il flusso è misurare i dati fra uno
stadio e l'altro.

**1. La radio produce campioni?**

```sh
timeout 3 socat -u UDP-RECV:42001 - | wc -c
```

Attesi ~864000 byte in 3 secondi (36000 campioni/s × 8 byte). Se esce 0, il
problema è nel ricevitore: guarda il log dello stadio `rx` nella scheda Log.

Nota: questo comando **ruba** i dati al decoder del canale 1, quindi va usato
con quel canale disabilitato, oppure aspettandosi che il decoder resti a bocca
asciutta finché il comando è in esecuzione.

**2. Il decoder riconosce i burst?**

Il log dello stadio `demod-1` deve scorrere. Righe che scorrono ma nessuna
informazione in telive significa quasi sempre segnale troppo debole o
frequenza sbagliata di poco.

**3. telive riceve?**

Se il decoder scorre ma telive resta vuoto, controlla che la porta di telive
nella scheda telive coincida con quella su cui il decoder invia — sono lo
stesso campo, quindi il caso tipico è un'altra istanza di telive rimasta
aperta che tiene la porta.

## Errori di compilazione

### `telive_receiver.h: unknown type name 'time_t'`

`telive_receiver.h` dichiara campi `time_t` ma include solo gli header di
libxml2 e `stdint.h`. Finora bastava, perché libxml2 tirava dentro `<time.h>`
per conto suo; dalla 2.12 non più. Il guaio si vede perché il Makefile di
telive compila anche l'header da solo (`-c $^` si espande a `.c` **e** `.h`):
il `.c` se la cava, perché include `<sys/types.h>`, l'header isolato no.

L'installer compila telive con `-include time.h`, che antepone l'header a ogni
unità di traduzione e risolve il caso. Se vedi ancora questo errore, stai
usando una versione dell'installer precedente: aggiorna il repository e
rilancia `./install.sh`.

Compilando telive a mano nella sua directory l'errore si ripresenta, perché il
flag non c'è. In quel caso:

```sh
make CC="gcc -include time.h"
```

### `timeout_receivers`: `too many arguments to function`

Da GCC 15 lo standard predefinito è GNU C23. In C23 una funzione dichiarata
con `()` non accetta argomenti, mentre nel C storico usato da telive la stessa
sintassi lasciava la lista degli argomenti non specificata. Il sorgente upstream
dichiara `timeout_receivers()` ma la chiama con un argomento inutilizzato, e il
nuovo compilatore interrompe quindi la build.

L'installer seleziona esplicitamente `-std=gnu17` per telive, mantenendo la
semantica con cui il programma è stato scritto senza modificare i sorgenti
clonati. Rilancia `./install.sh`: non occorre intervenire a mano su `telive.c`.

### `libxml/nanohttp.h: No such file or directory`

telive usa il modulo `nanohttp` di libxml2 per il controllo XMLRPC del
ricevitore. È deprecato dalla 2.12 e **rimosso dalla 2.14**: su quelle
versioni telive non compila. L'installer se ne accorge prima di iniziare e lo
dice esplicitamente. Serve una correzione a monte, in telive.

### La build fallisce con altri errori su Ubuntu recenti

GCC 14 (Ubuntu 25.04 in poi) trasforma in errori quelli che prima erano
warning: dichiarazioni implicite di funzione, `int` impliciti, conversioni di
puntatore incompatibili, `return` senza valore. I sorgenti upstream, scritti
fra il 2011 e il 2015, ne contengono. L'installer prova i corrispondenti flag
`-Wno-error=` sul compilatore in uso e applica quelli supportati — due
esistono solo da GCC 14 e GCC 13 li rifiuta, per questo vengono sondati invece
che dati per scontati.

I log completi sono in `~/.local/share/osmotetra/src/*/build.log`.

## Sintomi frequenti

### «La porta UDP 7379 è già occupata»

Un `telive` di una sessione precedente è rimasto vivo, in genere perché la sua
finestra è stata chiusa in modo brusco.

```sh
pgrep -ax telive     # controlla di cosa si tratta
pkill -x telive
```

### La finestra di telive si apre e si chiude subito

Aprila a mano per leggere l'errore:

```sh
~/.local/share/osmotetra/tetra/bin/telive-run
```

Le cause più comuni sono il binario non compilato (rilancia `./install.sh`) o
`tetra.xml` non trovato — telive lo cerca nella directory corrente, cosa di
cui si occupa `telive-run`.

### Lo schermo di telive è illeggibile

telive richiede **203×60 caratteri**. Nella scheda Sistema riduci il corpo del
carattere invece della finestra: la dimensione è in caratteri, non in pixel.
Con font troppo grandi la finestra non ci sta nello schermo e il gestore di
finestre la ridimensiona, riducendo il numero di caratteri.

Se usi gnome-terminal: dalla versione 3.28 ignora `--geometry`. Imposta xterm
come comando del terminale nella scheda Sistema (`sudo apt-get install xterm`).

### `ModuleNotFoundError: No module named 'gnuradio.gr.gr_python'`

Un altro Python (pyenv, conda, una build da sorgente) occupa il PATH al posto
di quello di sistema. L'applicazione di norma se ne accorge da sola; per
forzare la scelta:

```sh
OSMOTETRA_PYTHON=/usr/bin/python3.12 osmotetra
```

### `usb_claim_interface error -6` oppure il dispositivo non si apre

Il driver DVB-T del kernel ha preso la chiavetta prima di gr-osmosdr:

```sh
sudo ~/.local/share/osmotetra/lib/scripts/50_sdr_udev.sh
```

poi scollega e reinserisci la chiavetta. Se compare invece un errore di
permessi, devi fare logout e login perché l'appartenenza al gruppo `plugdev`
abbia effetto.

### telive non mostra il ricevitore, i tasti di sintonia non funzionano

telive cerca il ricevitore **una sola volta**, al proprio avvio, e non
riprova più. L'applicazione aspetta apposta che il flowgraph risponda prima di
lanciare telive, quindi se succede lo stesso: controlla che «Permetti a telive
di controllare il ricevitore» sia attivo, e guarda nel log dello stadio `rx`
se compare «server XMLRPC pronto». Se compare invece l'avviso di timeout,
l'SDR ci sta mettendo troppo a inizializzarsi: ferma e riavvia la catena.

### Nessun audio

L'audio richiede il codec ACELP, che non è redistribuibile:

```sh
./install.sh --with-codec
```

Verifica poi che in telive non siano attivi i silenziamenti: `M` silenzia
tutto, `m` silenzia gli SSI sconosciuti — e `m` è **attivo di default** nella
configurazione iniziale. Prova la catena audio da sola:

```sh
~/.local/share/osmotetra/tetra/bin/tplay \
    ~/.local/share/osmotetra/src/telive/testfile.acelp
```

### Traffico visibile ma nessuna voce

La rete è probabilmente cifrata. Nulla di questo software decifra alcunché:
l'opzione «Cifrati (-e)» fa solo interpretare i pacchetti come se fossero in
chiaro, e il risultato è privo di senso — è così anche in upstream.

### Il segnale c'è ma non aggancia

Regola la correzione in ppm. In telive premi `t` per la finestra delle
frequenze e osserva il valore AFC: va portato vicino a zero. Gli errori delle
chiavette RTL-SDR economiche arrivano tranquillamente a 50-60 ppm, e con più
di qualche kHz di scarto il demodulatore non aggancia.

## Provare senza radio

Nella scheda Radio, «Sorgente» accetta un file IQ (`file:`) o una sorgente
nulla. Serve a verificare che l'orchestrazione, le porte e i processi
funzionino prima di dare la colpa all'antenna:

```sh
osmotetra print-cmdline   # i comandi esatti, da confrontare col manuale telive
osmotetra start           # con sorgente 'null': tutti gli indicatori verdi, log vuoti
```

## Controllare che non resti nulla in esecuzione

```sh
osmotetra stop
pgrep -ax 'socat|tetra-rx|telive'
```

L'elenco deve essere vuoto. Attenzione a `pgrep -f`: la sua stessa riga di
comando contiene i nomi cercati e finisce per corrispondere a sé stessa —
usa `pgrep -x` con il nome esatto del programma.

## Raccogliere informazioni per una segnalazione

```sh
osmotetra check
osmotetra print-cmdline
gnuradio-config-info -v
pkg-config --modversion libosmocore
lsb_release -d
```

I log di compilazione stanno in `~/.local/share/osmotetra/src/*/build.log`,
quelli di esecuzione si salvano dalla scheda Log con «Salva su file».
