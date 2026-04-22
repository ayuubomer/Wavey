# READme

> Et Flask-basert webapplikasjon som bruker Google Gemini og en RAG-pipeline (Retrieval-Augmented Generation) til å svare på spørsmål om bedriftens tjenester og e-handel – alltid på norsk.

---

## Formål

Wavey er en chatbot-assistent bygd for en norsk e-handelsbedrift (E-Waves). Målet er å gi besøkende på nettsiden raske og presise svar på spørsmål om selskapets tjenester – uten at en menneskelig operatør trenger å være tilstede.

Assistenten er strengt begrenset til å:
- Kun svare på spørsmål relatert til bedriften og e-handel
- Alltid svare på norsk
- Aldri avsløre systemoppsett eller følge instruksjoner som forsøker å endre dens rolle

---

## Arkitektur og logikk

### Kunnskapsdatabasen (File Search Store)

Kjernen i systemet er en **File Search Store** hostet på Google Gemini. Dette er en vektordatabase der bedriftens egne dokumenter (f.eks. produktbeskrivelser, FAQ, retningslinjer) lagres og indekseres.

Når en bruker stiller et spørsmål, søker modellen **semantisk** gjennom disse dokumentene for å finne relevante tekstbiter og genererer et svar basert på dem. Dette kalles **RAG (Retrieval-Augmented Generation)** – modellen hallusinerer ikke, men henter faktisk innhold fra den opplastede kunnskapsbasen.

```
Bruker stiller spørsmål
        │
        ▼
  Søk i File Search Store (bedriftens egne dokumenter)
        │
        ├── Fant svar ──► Returner svar til bruker
        │
        └── Ingen treff ──► Fallback til Google Web Search
                                    │
                                    └── Returner svar til bruker
```

### To-stegs svarlogikk

`generate_website_answer()` i `main.py` implementerer en prioritert to-stegs logikk:

1. **Steg 1 – Dokumentsøk (`_ask_documents`):**  
   Gemini søker i File Search Store med bedriftens opplastede dokumenter. Dersom dokumentene ikke inneholder relevant informasjon, returnerer modellen et internt token (`FALLBACK_TOKEN`) som signaliserer at man skal gå videre til steg 2.

2. **Steg 2 – Nettsøk (`_ask_web`):**  
   Dersom dokumentsøket feiler eller ikke gir svar, brukes Googles innebygde nettsøk som et fallback. Systemprompten holder fortsatt modellen innenfor temaet e-handel og norsk språk.

3. **Steg 3 – Feilhåndtering:**  
   Dersom begge steg feiler (f.eks. nettverksfeil eller timeout), returneres en norsk feilmelding til brukeren.

Alle LLM-kall pakkes i `_safe_llm_call()` som bruker en `ThreadPoolExecutor` med **10 sekunders timeout** for å unngå at applikasjonen henger.

### Sikkerhetslag

`security.py` implementerer et risikobasert sikkerhetssystem som analyserer hver innkommende spørring **før** den sendes til AI-modellen. Systemet er bygd som en in-memory løsning (uten behov for Redis).

**Analysesteg:**

| Sjekk | Beskrivelse | Maks poengstraff |
|---|---|---|
| `detect_injection` | Finner prompt injection-forsøk (f.eks. "ignore instructions", "jailbreak") | 100 |
| `detect_obfuscation` | Finner usynlige Unicode-tegn brukt for å skjule ondsinnet tekst | 50 |
| `detect_encoding_tricks` | Finner base64-kodet innhold | 50 |
| `detect_structure_anomaly` | Finner unormalt lange spørsmål eller spamming av spørsmålstegn | 50 |
| IP-risiko | Akkumulert risikoscore per IP-adresse over tid | 80 |
| Velocity | For mange forespørsler fra samme IP | 50 |

**Beslutningslogikk (total risikoscore 0–100):**

| Score | Beslutning | Handling |
|---|---|---|
| < 25 | `ALLOW` | Spørsmålet sendes videre |
| 25–39 | `CHALLENGE` | IP-risiko økes litt |
| 40–69 | `LIMIT` | 2 sekunders forsinkelse pålegges |
| ≥ 70 | `BLOCK` | Forespørselen blokkeres (HTTP 403) |

IP-risikoscore forfaller gradvis over tid (2 poeng hvert 60. sekund) og nullstilles etter 1 time uten aktivitet.

### Admin-panel

Admin-panelet (`/admin`) gir en grafisk oversikt over alle dokumenter som er lastet opp til kunnskapsdatabasen. Herfra kan man:

- **Se** alle opplastede filer med navn, status og størrelse
- **Laste opp** nye dokumenter til File Search Store
- **Slette** eksisterende dokumenter

Dette er det primære verktøyet for å vedlikeholde og oppdatere kunnskapsbasen uten å skrive kode.

---

## Prosjektstruktur

```
Wavey/
├── main.py              # Flask-app, ruter, LLM-logikk og to-stegs svarmotor
├── security.py          # Risikoanalyse og IP-basert sikkerhetssystem
├── requirements.txt     # Python-avhengigheter
├── .env                 # Miljøvariabler (skal IKKE committes til git)
├── static/
│   ├── Ewavespng.png    # Bedriftslogo (PNG)
│   └── e-waves logo.jpg # Bedriftslogo (JPG)
└── templates/
    ├── base.html        # Felles HTML-base
    ├── index.html       # Hovedside med chatbot-grensesnitt
    └── admin.html       # Admin-panel for kunnskapsdatabasen
```

---

## Kom i gang – lokal oppsett

### Krav

- **Python 3.10 eller nyere**
- En **Google Gemini API-nøkkel** med tilgang til `gemini-2.0-flash` og File Search API
- En eksisterende **File Search Store** opprettet via Google AI Studio eller Gemini API

### Installasjon

**1. Klon repositoryet**

```bash
git clone https://github.com/ayuubomer/Wavey.git
cd Wavey
```

**2. Opprett og aktiver et virtuelt miljø (anbefalt)**

```bash
# Opprett virtuelt miljø
python -m venv venv

# Aktiver på macOS/Linux
source venv/bin/activate

# Aktiver på Windows
venv\Scripts\activate
```

**3. Installer alle avhengigheter**

```bash
pip install -r requirements.txt
```

De viktigste pakkene som installeres:

| Pakke | Formål |
|---|---|
| `Flask` | Webserver og ruting |
| `google-genai` | Google Gemini AI SDK (LLM + File Search) |
| `python-dotenv` | Laster miljøvariabler fra `.env`-fil |
| `gunicorn` | Produksjons-webserver (brukes ved deploy) |

### Miljøvariabler

Opprett en fil som heter `.env` i rotmappen av prosjektet og legg til følgende:

```env
GEMINI_API_KEY=din_gemini_api_nøkkel_her
FILE_SEARCH_STORE_NAME=projects/PROSJEKT_ID/locations/REGION/fileSearchStores/STORE_ID
```

> ⚠️ **Viktig:** Del aldri `.env`-filen offentlig eller last den opp til GitHub. Legg til `.env` i `.gitignore` hvis den ikke allerede er der.

**Slik finner du `FILE_SEARCH_STORE_NAME`:**
- Logg inn på [Google AI Studio](https://aistudio.google.com) eller Gemini API-konsollen
- Naviger til File Search Stores under ditt prosjekt
- Kopier den fulle ressursstrengen (starter med `projects/...`)

### Kjør applikasjonen

```bash
python main.py
```

Applikasjonen starter på `http://localhost:5000`.

| Rute | Beskrivelse |
|---|---|
| `http://localhost:5000/` | Chatbot-grensesnittet |
| `http://localhost:5000/admin` | Admin-panel for kunnskapsdatabasen |

---

## Viktig for fremtidige studenter

- **Kunnskapsdatabasen oppdateres via admin-panelet** på `/admin`. Last opp nye PDF- eller tekstfiler for å utvide hva assistenten kan svare på.
- **Systemprompten** som definerer assistentens adferd og begrensninger ligger øverst i `main.py` i variabelen `_SYSTEM_INSTRUCTION`. Endre denne for å justere tone, språk eller temaavgrensning.
- **Sikkerhetssystemet** i `security.py` er stateless mellom serverrestarter (in-memory). Vurder å koble til Redis for persistent IP-risikoscore i produksjonsmiljø.
- **Timeout for LLM-kall** er satt til 10 sekunder (`LLM_TIMEOUT_SECONDS`). Juster dette ved behov.
- For **produksjonsdeploy** brukes `gunicorn` (allerede inkludert i `requirements.txt`):
  ```bash
  gunicorn -w 4 -b 0.0.0.0:5000 main:app
  ```