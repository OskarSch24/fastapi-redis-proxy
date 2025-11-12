# Workflow Fix Summary - Redis Query Problem

**Datum:** 2025-11-01  
**Workflow:** Redis Writer Agent - Intelligent Content Generation  
**Problem:** Alle Redis Queries returnierten `null`

---

## 🔴 Problem Identifiziert

Der n8n Workflow "Redis Writer Agent - Intelligent Content Generation" hat bei allen Redis-Queries **nur `null`** zurückgegeben statt tatsächliche Daten aus der Datenbank.

### Symptome
- Execution ID 169: Alle 5 Redis Queries returnierten `propertyName: null`
- AI Agent schlug Keys vor: `ch:brand_identity:001`, `ch:business_philosophy:001`, `ch:sales_strategy:002`
- Diese Keys **existieren nicht** in Redis

---

## 🔍 Root Cause Analysis

### 1. AI Agent hatte KEIN Database Schema
- Der "Redis Tool" (ID: `15f0741a-1c63-4444-9154-ee98d981f96c`) war als `operation: info` konfiguriert
- Dieser gibt nur Server-Statistiken zurück (Redis INFO command)
- Das eigentliche Schema liegt in `index:database_schema` und wurde **nie geladen**

### 2. AI Agent hat blind geraten
- Ohne Zugriff auf das Schema hat der AI Agent Keys nach einem vermuteten Muster generiert
- Verwendete Nummerierung: `:001`, `:002`, `:003`
- Tatsächliche Nummerierung: `:001`, `:002`, `:003`, `:004`, `:005` (aber nicht sequentiell)

### 3. Tatsächliche Keys sind anders
```
❌ Vorgeschlagen: ch:brand_identity:001
✅ Existiert:     ch:brand_identity:005

❌ Vorgeschlagen: ch:business_philosophy:001
✅ Existiert:     ch:business_philosophy:004

❌ Vorgeschlagen: ch:sales_strategy:002
✅ Existiert:     Kein sales_strategy chapter vorhanden
```

---

## ✅ Implementierte Lösung

### Änderung 1: Code Node "Load Schema" hinzugefügt

**Node Details:**
- **Name:** Load Schema
- **ID:** `load-schema-node-001`
- **Type:** `n8n-nodes-base.code`
- **Position:** [340, 300] (zwischen Chat Trigger und Query Reasoning Agent)

**Funktion:**
```javascript
const redis = require('redis');

const client = redis.createClient({
  socket: {
    host: 'redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com',
    port: 13515,
    tls: false
  },
  password: 'WNWF6sNqFg5e2N5wjWLvoMfdBuMGTdKT'
});

await client.connect();
const schema = await client.sendCommand(['JSON.GET', 'index:database_schema']);
await client.disconnect();

return {
  json: {
    chatInput: $input.item.json.chatInput,
    schema: JSON.parse(schema)
  }
};
```

**Output:**
- `chatInput`: Original Chat-Nachricht (durchgereicht)
- `schema`: Komplettes Redis Database Schema (parsed JSON)

---

### Änderung 2: AI Agent Prompt angepasst

**Node:** Query Reasoning Agent (ID: `c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f`)

**Neuer Prompt:**
```
# Query Reasoning Agent

## Database Schema
{{ JSON.stringify($json.schema, null, 2) }}

## Your Task
Analyze the user's content request and select the EXACT keys from the schema above.

## User Request
{{ $json.chatInput }}

## Instructions
1. Look at the schema above to see available documents and chapters
2. Use the EXACT key names from the schema (e.g., ch:brand_identity:005, NOT ch:brand_identity:001)
3. Analyze what type of content the user wants to create
4. Select maximum 5 relevant keys

## Output Format
Respond with ONLY this JSON:
```json
{
  "queries": [
    {"key": "EXACT_KEY_FROM_SCHEMA", "reason": "Why this key"},
    {"key": "EXACT_KEY_FROM_SCHEMA", "reason": "Why this key"}
  ],
  "content_type": "Type of content",
  "key_themes": ["theme1", "theme2"]
}
```

## Rules
- Use ONLY keys that exist in the schema above
- Maximum 5 queries
- Always include doc_[communication_rules]_001 for written content
- Include doc:brand_brief:001 for brand voice
```

**System Message:**
```
You are a precise query planning agent. Always respond with valid JSON only. Use ONLY keys from the provided schema.
```

---

## ⚠️ Manuelle Aktion erforderlich

**Connections in n8n UI umziehen:**

### Vorher:
```
Chat Trigger → Query Reasoning Agent
```

### Nachher:
```
Chat Trigger → Load Schema → Query Reasoning Agent
```

**Schritte:**
1. In n8n Workflow Editor öffnen
2. Connection von `Chat Trigger` zu `Query Reasoning Agent` löschen
3. Connection von `Chat Trigger` zu `Load Schema` erstellen
4. Connection von `Load Schema` zu `Query Reasoning Agent` erstellen

**Node ist bereits vorhanden!** Nur Connections müssen umgezogen werden.

---

## 📊 Redis Datenbank Info

### Aktuelle Struktur
- **Total Keys:** 799
- **Documents:** 2
  - `doc:brand_brief:001` - "Brand Brief" (8 chapters)
  - `doc_[communication_rules]_001` - "Communication Rules" (1 chapter)

### Existierende Chapter Keys
```
ch:brand_identity:005
ch:brand_overview:003
ch:business_philosophy:004
ch:communication_rules:001
ch:future_elaborations_and_ideas:008
ch:introduction:002
ch:meta_data:001
ch:offer_service:007
ch:visual_branding:006
```

### Schema Location
- **Key:** `index:database_schema`
- **Type:** RedisJSON (gespeichert mit `JSON.SET`)
- **Abruf:** `JSON.GET index:database_schema` (NICHT normaler `GET`)

---

## 🎯 Erwartetes Ergebnis nach Fix

### Vor dem Fix:
```json
{
  "queries": [
    {"key": "ch:brand_identity:001", "reason": "..."},  // ❌ Existiert nicht
    {"key": "ch:business_philosophy:001", "reason": "..."}  // ❌ Existiert nicht
  ]
}
```
**Redis Returns:** `null`, `null`, `null`

### Nach dem Fix:
```json
{
  "queries": [
    {"key": "doc:brand_brief:001", "reason": "..."},  // ✅ Existiert
    {"key": "ch:brand_identity:005", "reason": "..."},  // ✅ Existiert
    {"key": "doc_[communication_rules]_001", "reason": "..."}  // ✅ Existiert
  ]
}
```
**Redis Returns:** Tatsächliche JSON-Daten aus der Datenbank

---

## 🔧 Technische Details

### Warum der ursprüngliche Redis Tool nicht funktionierte
- **Redis Tool Node** mit `operation: info` führt den Befehl `INFO` aus
- Dieser returnt Server-Statistiken, NICHT das Database Schema
- Das Schema liegt als RedisJSON Objekt in `index:database_schema`
- RedisJSON benötigt spezielle Commands: `JSON.GET`, `JSON.SET`
- Der Standard Redis Node unterstützt diese Commands nicht direkt

### Warum ein Code Node nötig war
- n8n Redis Node unterstützt keine RedisJSON Commands
- Code Node kann `redis-py` Library nutzen
- Über `sendCommand()` können beliebige Redis Commands ausgeführt werden

### Connection String (für Referenz)
```
redis://default:WNWF6sNqFg5e2N5wjWLvoMfdBuMGTdKT@redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com:13515
```
**Wichtig:** SSL/TLS muss **deaktiviert** sein (`tls: false`)

---

## 📝 Lessons Learned

1. **Redis Tool in n8n ist limitiert** - Unterstützt keine RedisJSON Commands
2. **AI Agents brauchen echte Daten** - Ohne Schema generieren sie ungültige Keys
3. **Schema-First Approach** - Immer zuerst verfügbare Daten zeigen
4. **Explizite Key-Validierung** - AI muss instruiert werden, nur existierende Keys zu verwenden

---

## ✅ Status

- [x] Problem identifiziert
- [x] Code Node "Load Schema" hinzugefügt
- [x] AI Agent Prompt aktualisiert
- [ ] **Connections in n8n UI umziehen** (MANUELL)
- [ ] Workflow testen mit echter Chat-Nachricht

---

**Next Step:** Connections in n8n manuell umziehen und Workflow erneut testen.





