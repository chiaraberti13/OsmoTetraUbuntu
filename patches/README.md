# Patch applicate ai sorgenti upstream

Queste patch vengono applicate dai sorgenti clonati da GitHub durante
l'installazione (`install.sh`, funzione `maybe_patch_nanohttp`), con
`patch -p1 -N` — che è idempotente: se la patch è già applicata non viene
riapplicata, quindi un secondo `./install.sh` non fallisce. La patch viene
applicata **solo quando serve**, cioè quando la libxml2 di sistema non ha più
il modulo `nanohttp` (Ubuntu 25.10 e successive).

Non modifichiamo i sorgenti upstream nel loro repository: le patch stanno qui
e vengono sovrapposte a ogni build, così un aggiornamento dei sorgenti
(`git pull`) le ritrova pulite.

## `telive2-nanohttp-to-socket.diff`

**Problema.** telive-2 comunica in XMLRPC con il ricevitore gnuradio usando il
modulo `nanohttp` di libxml2 (`xmlNanoHTTPMethod`, `xmlNanoHTTPRead`, …). Quel
modulo è **deprecato dalla libxml2 2.12 e rimosso dalla 2.14**: su Ubuntu 25.04
e successive (libxml2 ≥ 2.14) telive-2 non compila, si ferma su
`libxml/nanohttp.h: No such file or directory`.

**Cosa fa la patch.** Sostituisce le chiamate `xmlNanoHTTP*` in
`telive_receiver.c` con una funzione `xmlrpc_http_post()` che esegue la stessa
POST HTTP tramite socket POSIX (`getaddrinfo`/`connect`/`write`/`read`). La
richiesta XMLRPC verso il ricevitore è HTTP/1.0 semplice su loopback, quindi
non serve né nanohttp né una libreria HTTP esterna: nessuna dipendenza
aggiuntiva. Rimuove anche `xmlNanoHTTPInit()` da `telive.c` e l'`#include
<libxml/nanohttp.h>` da `telive_receiver.h`.

Il parsing dell'XML di risposta resta invariato (usa `xmlReadMemory`, che
libxml2 conserva): cambia solo il trasporto HTTP.

**Verifica.** Con la patch applicata, telive-2 compila anche con gli header di
libxml2 privati di `nanohttp.h`, e la scoperta del ricevitore
(`grxml_discover_receiver`) contro un vero server XMLRPC restituisce nome e
numero di canali corretti.

**Se smette di applicarsi.** Significa che l'autore ha modificato quelle righe
a monte. `install.sh` (funzione `maybe_patch_nanohttp`) se ne accorge e si
ferma con un messaggio esplicito invece di lasciare un errore di compilazione
oscuro. In quel caso la patch va rigenerata sulle nuove righe:

```sh
# in un clone di telive-2 con le modifiche riapplicate a mano
git diff telive.c telive_receiver.c telive_receiver.h > patches/telive2-nanohttp-to-socket.diff
```
