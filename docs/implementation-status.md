# Stato implementazione RedCode

Ultimo aggiornamento: 2026-08-27

Questo documento distingue il comportamento **verificato** dalle parti ancora
in lavorazione. Non sostituisce la policy del programma, il manifest di
engagement o la revisione dell'analista.

## Obiettivo

Rendere RedCode un assistente pratico per bug bounty autorizzato: conserva il
contesto tra sessioni, trasforma traffico Burp selezionato in una mappa e in una
coda MAPPA, prepara test minimi soggetti ad approvazione e produce bozze di
report. L'analista mantiene sempre controllo su scope, richieste attive,
validazione dell'impatto e invio della submission.

## Implementato e verificato

### Controllo locale per bug bounty

- Comando `./redcode bugbounty` con onboarding del programma, snapshot locale
  della policy, scope esplicito, esclusioni e azioni vietate.
- Intersezione fail-closed fra manifest RedCode e policy del programma.
- Policy snapshot copiata sotto `output/`, hashata e verificata a ogni controllo:
  se viene modificata o manca, il workflow viene negato finché non viene fatta
  una nuova revisione.
- Identità solo simboliche (ruolo, tenant e stato di autenticazione), senza
  cookie, bearer token o segreti memorizzati.
- Importazione di esportazioni Burp JSON/JSONL selezionate, con redazione prima
  della persistenza di query value, userinfo, fragment, header sensibili e body.
- URL e riferimenti persistiti normalizzati: nessun token o valore di query
  viene scritto nella tabella `targets`; gli identificatori di percorso sono
  trasformati in `{id}` negli artefatti di mapping.
- Provenienza Burp con riferimenti di sorgente e fingerprint redatti per
  deduplicare reimportazioni senza confondere identificatori locali di progetti
  Burp diversi.
- Mappa di endpoint, workflow, coverage gap, coda MAPPA, piani immutabili,
  approvazioni con scadenza, registrazione di esiti, evidenze hashate e bozze
  HackerOne/Bugcrowd solo locali.
- Annotazioni guidate di workflow (attori simbolici, oggetti, stati e
  sensibilità) e ipotesi MAPPA contestuali per endpoint già mappati.
- Punteggio MAPPA basato su identità/tenant realmente importati, sensibilità
  del workflow, copertura osservata, numero di osservazioni e duplicate risk
  del programma; i componenti restano visibili nella coda.

### Integrità e controllo umano

- Un piano è legato alla specifica snapshot di policy revisionata; un cambio
  policy annulla piani e esecuzioni ancora aperti.
- La registrazione rifiuta esiti oltre la scadenza o oltre il numero massimo di
  richieste; le autorizzazioni scadute riportano l'ipotesi in coda.
- Un candidato non può diventare finding se il file di evidenza manca, è stato
  modificato o non coincide con l'hash dell'esecuzione approvata.
- L'agente `bugbounty` è configurato senza permessi MCP di rete (HexStrike,
  Fetch, Playwright, Burp): non può eseguire richieste di target direttamente;
  il suo workflow gli vieta inoltre di delegare attività di rete. Il Repeater,
  se consentito, resta manuale e limitato all'analista.
- Nessun comando invia submission a HackerOne, Bugcrowd o altra piattaforma.

### MAPPA semantico

- Il modello di workflow conserva stati terminali, transizioni ordinate,
  prerequisiti/postcondizioni, effetti di autorizzazione, capability, trust
  boundary, invarianti, assunzioni e osservazioni di apprendimento.
- `queue --generate` mantiene i seed ownership/tenant e aggiunge proposte
  spiegabili derivate solo da semantica confermata dall'analista, con chiave
  semantica stabile per la deduplicazione. I piani immutabili conservano il
  ragionamento usato per crearli.
- La migration 008 aggiunge la correlazione degli identificatori semantici:
  path, query, request e response producono solo fingerprint HMAC locali e
  contesto di campo/percorso. `identifier list`, `identifier confirm` e
  `identifier reject` rendono esplicita la revisione dei ruoli; le relazioni
  osservate restano lead finché l'analista non usa `identifier relationship
  confirm`. Solo le relazioni confermate alimentano nuove ipotesi, mantenendo il
  template generico per deduplicazione e aggiungendo un display template
  spiegabile.

### Proxychains

- Ogni processo avviato dal launcher `./redcode` riceve il prefisso
  configurabile `REDCODE_COMMAND_PREFIX` (predefinito `proxychains4 -q`); il
  launcher fallisce se il wrapper non è disponibile.
- Il backend HexStrike viene avviato tramite
  `scripts/hexstrike_proxychains_runner.py`; i processi figli del backend
  ricevono il prefisso configurabile `proxychains4 -q`.
- Il launcher esporta anche le variabili proxy HTTP standard quando `PROXY_URL`
  è configurato.
- Il setup conserva la lista proxy esistente e aggiunge esclusioni `localnet`
  ristrette a loopback e all'host/porta numerici di Burp MCP, creando prima un
  backup della configurazione. Il controllo di raggiungibilità Burp ha un
  limite temporale anche quando il server mantiene aperto uno stream SSE.

## Verifiche già eseguite

- Compilazione Python dei controller.
- Test di migrazione SQLite dalla versione 1 alla 8.
- Test end-to-end del flusso bug bounty: onboarding, import Burp, redazione,
  mappa, piano, approvazione, evidenza, conferma e bozza report.
- Regressioni dedicate per token in URL, manomissione della policy e manomissione
  dell'evidenza.
- Test del probe MCP Burp con server HTTP fittizio compatibile con il protocollo
  MCP streamable HTTP.
- Suite completa: 74 test superati; 5 test d'integrazione saltati
  intenzionalmente perché non è configurato un servizio locale loopback.
- Verifica sintattica degli script shell e controllo whitespace Git.

## Stato corrente

- Implementazione e test automatici sono completi per il perimetro locale.
- Prima di usarlo su un programma reale, eseguire un pilot con una policy
  autorizzata, un Burp MCP/JSON export reale e un analista responsabile della
  verifica manuale. Questo è un passaggio operativo, non una funzione che il
  repository possa dimostrare senza un engagement autorizzato.

## Limiti noti, intenzionali

- Il controllo locale non è un proxy di policy capace di intercettare azioni
  manuali eseguite dentro Burp o chiamate effettuate da altri agenti RedCode.
  Per il workflow bug bounty, l'agente dedicato è privo di tool di rete proprio
  per non presentare i prompt come enforcement fisico.
- Il launcher applica il prefisso ai processi che avvia, ma Burp remoto,
  Fetch, Playwright e servizi MCP esterni possono introdurre ulteriori processi
  o percorsi di rete. Non va quindi descritto come proxy end-to-end finché un
  test di rete non avrà verificato ogni percorso esterno effettivamente usato.
- Il probe Burp verifica handshake e lista tool MCP; l'import usa un formato
  JSON/JSONL selezionato dall'analista perché i nomi/payload della history
  cambiano fra implementazioni Burp MCP.

## Criteri soddisfatti e prossimo controllo reale

- La coda MAPPA spiega il punteggio con dati reali di identità e workflow.
- L'analista può annotare contesto business senza SQL ad hoc.
- Le nuove regole critiche hanno test di regressione.
- La documentazione non promette esecuzione autonoma, policy enforcement fisico
  o proxychains end-to-end senza evidenza tecnica.
