# n8n HTTP Request Debug Session Report

**Datum:** 9. November 2025  
**Workflow ID:** `ehfOJ46JAtE3R7h4`  
**Workflow Name:** "Redis Writer Agent - Intelligent Content Generation"

---

## 🎯 Ausgangsziel

User wollte verstehen, warum HTTP Requests im n8n Workflow nicht funktionieren.

**Wichtig:** User wollte **keine Lösung**, sondern nur eine **verständliche Erklärung** der Probleme (für Nicht-Developer).

---

## 🔍 Identifizierte Probleme

### Problem 1: Fehlender API-Key im HTTP Request Header

**Betroffen:** Node "HTTP Request" (ID: `7b6fcf9b-4be7-43d3-82f7-0a36bf59779c`)

**Was passiert:**
- n8n sendet HTTP POST zu: `https://fastapi-redis-proxy-production.up.railway.app/redis/json-get`
- Header enthält: `Content-Type: application/json`
- Header enthält **NICHT**: `X-API-Key`

**Warum das ein Problem ist:**
Der FastAPI Redis Proxy auf Railway erwartet zur Authentifizierung einen `X-API-Key` Header (Code Zeile 26-31 in `main.py`):

```python
def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server API key not configured")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
```

**Resultat:** HTTP 401 Unauthorized

---

### Problem 2: Inkonsistente Header-Formatierung

**Betroffen:** 
- Node "Get Database Schema Tool" (ID: `redis-schema-tool-001`)
- Node "HTTP Request" (ID: `7b6fcf9b-4be7-43d3-82f7-0a36bf59779c`)

**Was passiert:**

**Get Database Schema Tool:**
```json
"specifyHeaders": "keypair",
"parametersHeaders": {
  "values": [
    {"name": "Content-Type", "value": "application/json"}
  ]
}
```

**HTTP Request:**
```json
"specifyHeaders": "keypair",
"headerParameters": {
  "parameters": [
    {"name": "Content-Type", "value": "application/json"}
  ]
}
```

**Problem:** Unterschiedliche Parameter-Namen (`parametersHeaders` vs `headerParameters`)

**Resultat:** n8n könnte Header falsch interpretieren oder überspringen

---

## 🔑 API-Key Klärung (Wichtigste Erkenntnis)

### Die Verwirrung: 3 verschiedene Keys im System

| Key Name | Zweck | Wo gespeichert | Wer nutzt ihn |
|----------|-------|----------------|---------------|
| **REDIS_PASSWORD** | Zugang zur Redis Cloud Datenbank | Railway Environment Vars | Railway FastAPI Proxy → Redis Cloud |
| **API_KEY** | Zugang zur FastAPI Proxy Anwendung | Railway Environment Vars | n8n → Railway FastAPI Proxy |
| **Railway Account Token** | Zugang zum Railway Account | Railway Account Settings | Für Railway Management API |

### Was der User gemacht hat (Setup):

1. `REDIS_PASSWORD` = `WNWF6sNqFg5e2N5wjWLvoMfdBuMGTdKT` (Redis Cloud Passwort)
2. `API_KEY` = `sk.redis.n8n_2024_87a9gkL2m8SuN...` (Redis Cloud Management API Key)

**Wichtige Erkenntnis:**
- Der `API_KEY` stammt aus Redis Cloud, ist aber **NICHT** das Datenbank-Passwort
- Er ist ein separater Key (wahrscheinlich für Redis Cloud Management API generiert)
- Railway nutzt diesen Key **NICHT** für die Redis-Connection
- Railway nutzt `REDIS_PASSWORD` für die Redis-Connection
- Der `API_KEY` wird **nur** genutzt für: n8n → Railway Authentifizierung

### Datenfluss Authentifizierung:

```
n8n → [X-API-Key: sk.redis.n8n_2024_...] → Railway FastAPI Proxy
                                                    ↓
                                        [REDIS_PASSWORD: WNWF6sNqFg5e2N5wjWLvoMfdBuMGTdKT]
                                                    ↓
                                              Redis Cloud
```

---

## ❌ Fehlgeschlagene Lösungsversuche

### Versuch 1: Railway API Umgebungsvariablen abrufen
**Tool:** `mcp_railway_railway_get_environment_variables`  
**Resultat:** API Error "Problem processing request"  
**Grund:** Möglicherweise Berechtigungsproblem oder API-Limitation

---

## ✅ Erfolgreiche Erkenntnisse

### 1. Workflow-Struktur analysiert
**Tool:** `mcp_n8n-mcp_n8n_get_workflow`  
**Resultat:** Vollständige Workflow-JSON erhalten mit allen Nodes und Connections

### 2. FastAPI Code analysiert
**Datei:** `/Users/oskarschiermeister/Desktop/Database Project/fastapi-redis-proxy/app/main.py`  
**Erkenntnisse:**
- Zeile 26-31: API-Key Validierung
- Zeile 34-68: Redis Connection Setup
- `API_KEY` wird für HTTP Auth genutzt, **nicht** für Redis Connection

### 3. Railway Projekt gefunden
**Projekt ID:** `066da31e-74b8-474a-a272-fe565d8d5cf4`  
**Service ID:** `456c4dd9-5099-4bfb-8396-5f8000b775c4`  
**Service Name:** `fastapi-redis-proxy`

### 4. Environment Variables Dokumentation
**Datei:** `/Users/oskarschiermeister/Desktop/Database Project/fastapi-redis-proxy/ENV_VARS_EXAMPLE.md`

Benötigte Variablen:
- `REDIS_HOST` = redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com
- `REDIS_PORT` = 13515
- `REDIS_PASSWORD` = (Redis Cloud Passwort)
- `REDIS_TLS` = true
- `API_KEY` = (Selbst gewählter Key für n8n Auth)
- `PYTHONUNBUFFERED` = 1

---

## 📋 Zusammenfassung für nächsten Chat

### Was funktioniert:
✅ Railway FastAPI Proxy → Redis Cloud Connection  
✅ API_KEY ist in Railway konfiguriert (Wert: `sk.redis.n8n_2024_...`)

### Was fehlt:
❌ n8n HTTP Request sendet keinen `X-API-Key` Header  
❌ Inkonsistente Header-Konfiguration in n8n Nodes

### Was zu tun ist (für nächsten Chat):
1. **Im n8n Workflow:**
   - Node "HTTP Request" bearbeiten
   - Header hinzufügen: `X-API-Key` = `sk.redis.n8n_2024_87a9gkL2m8SuN...` (vollständiger Wert aus Railway)
   
2. **Header-Format vereinheitlichen:**
   - Beide HTTP-Nodes sollten gleiche Parameter-Struktur nutzen
   - Entweder beide `headerParameters` oder beide `parametersHeaders`

3. **Testen:**
   - Workflow ausführen
   - Logs in Railway prüfen
   - Erfolgreiche Redis-Daten-Abfrage verifizieren

---

## 🔧 Technische Details

### FastAPI Proxy Endpoints:

**1. JSON Get Endpoint:**
```
POST https://fastapi-redis-proxy-production.up.railway.app/redis/json-get
Headers: 
  - Content-Type: application/json
  - X-API-Key: [API_KEY aus Railway]
Body:
  {"key": "doc:brand_brief:001"}
```

**2. Command Endpoint:**
```
POST https://fastapi-redis-proxy-production.up.railway.app/redis/command
Headers:
  - Content-Type: application/json
  - X-API-Key: [API_KEY aus Railway]
Body:
  {"command": "KEYS", "args": ["*"]}
```

### Workflow Nodes im Detail:

| Node Name | Type | ID | Problem |
|-----------|------|----|---------| 
| Get Database Schema Tool | @n8n/n8n-nodes-langchain.toolHttpRequest | redis-schema-tool-001 | Missing X-API-Key |
| HTTP Request | n8n-nodes-base.httpRequest | 7b6fcf9b-4be7-43d3-82f7-0a36bf59779c | Missing X-API-Key |

---

## 📝 Wichtige Dateien

- Workflow: n8n Cloud (ID: `ehfOJ46JAtE3R7h4`)
- FastAPI Code: `/Desktop/Database Project/fastapi-redis-proxy/app/main.py`
- ENV Docs: `/Desktop/Database Project/fastapi-redis-proxy/ENV_VARS_EXAMPLE.md`
- Railway Projekt: `066da31e-74b8-474a-a272-fe565d8d5cf4`
- MCP Config: `/Users/oskarschiermeister/.cursor/mcp.json`

---

## 🎓 Lessons Learned

1. **API_KEY ist NICHT das Redis-Passwort** - Es ist ein separater Auth-Key für die Proxy-Anwendung
2. **Railway nutzt REDIS_PASSWORD für Redis** - Nicht API_KEY
3. **API_KEY = Türsteher für n8n → Railway** - Railway nutzt es nur zur HTTP-Auth-Validierung
4. **Der sk.redis... Key ist bereits der richtige** - Muss nur in n8n als X-API-Key Header eingefügt werden

---

**Status:** Problem identifiziert, Lösung bekannt, Umsetzung ausstehend




