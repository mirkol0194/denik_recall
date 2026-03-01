# Recall — jak funguje ukládání a vektorizace (pro neprogramátory)

## Celý koncept jednoduše

Představ si **papírový deníček**. Funguje dobře, ale má jeden problém — když chceš najít, co jsi psal o dovolené v Itálii, musíš listovat stránku po stránce. To je pomalé.

Programátor tady vyřešil přesně tohle — ale pro AI. Claude si potřebuje **pamatovat** minulé konverzace a **rychle najít** relevantní záznamy.

---

## Krok za krokem: co se děje, když zapíšeš záznam

### 1. Uživatel řekne Claude: "Zapiš si, že jsem dnes měl pohovor v Googlu"

Claude zavolá nástroj `diary_write` s textem.

### 2. Automaticky se přidá datum

Kód na řádku 34-39 v `DiaryTools.cs` přidá hlavičku:

```
**Date: February 27, 2026 (Thursday 16:30)**

Dnes jsem měl pohovor v Googlu.
```

**Proč?** Aby každý záznam měl časový kontext. Když se Claude později ptá "co bylo minulý týden", potřebuje vědět KDY se co stalo.

### 3. Text se "vektorizuje" — tady je ta magie

V `DiaryDatabase.cs` řádek 113:

```
var textToEmbed = content + tags;  // spojí text + tagy
embeddingBlob = _embeddings.Embed(textToEmbed);  // → čísla!
```

**Co to znamená?**

Představ si, že každé slovo a věta má svou "polohu" v obrovském prostoru. Jako GPS souřadnice, ale místo 2D (šířka, délka) máš **384 dimenzí**.

```
"pohovor v Googlu"       →  [0.12, -0.45, 0.78, 0.03, ..., -0.21]
                              384 čísel = "otisk významu"
```

Důležité: **podobné významy mají podobné souřadnice**:

```
"pohovor v Googlu"        →  [0.12, -0.45, 0.78, ...]
"job interview at Google"  →  [0.11, -0.44, 0.79, ...]  ← skoro stejné!
"vaření večeře"            →  [0.85, 0.22, -0.61, ...]  ← úplně jiné
```

**Proč 384 čísel?** To rozhodl model all-MiniLM-L6-v2. Je to jako by měl 384 různých "os", na kterých hodnotí význam textu — jedna osa může být "je to o práci?", jiná "je to emocionální?", další "je to o technologii?" atd. (ve skutečnosti se osy nedají takhle pojmenovat, ale princip je stejný).

### 4. Jak model vytváří ta čísla (EmbeddingService.cs)

```
         "Dnes jsem měl pohovor v Googlu"
                      ↓
    ┌─────────────────────────────────────┐
    │  TOKENIZACE (BERT tokenizer)        │
    │  Rozseká text na kousky:            │
    │  [CLS] dnes jsem měl pohovor       │
    │  v go ##og ##lu [SEP]              │
    │  → pole čísel (ID tokenů)           │
    └─────────────────┬───────────────────┘
                      ↓
    ┌─────────────────────────────────────┐
    │  ONNX MODEL (neuronová síť)        │
    │  62 MB natrénovaný model            │
    │  Běží LOKÁLNĚ, žádné API volání!    │
    │                                     │
    │  Každý token → 384 čísel            │
    │  Vstup:  [10 tokenů × 384]         │
    │  = 3840 čísel                       │
    └─────────────────┬───────────────────┘
                      ↓
    ┌─────────────────────────────────────┐
    │  MEAN POOLING (průměrování)         │
    │  10 tokenů × 384 → 1 × 384         │
    │  = průměr všech tokenů              │
    │  = jeden vektor za celou větu       │
    └─────────────────┬───────────────────┘
                      ↓
    ┌─────────────────────────────────────┐
    │  L2 NORMALIZACE                     │
    │  Vektor se "natáhne" na délku 1     │
    │  = aby šla porovnávat podobnost     │
    │  = jako kdybys dal všechny body     │
    │    na povrch koule                  │
    └─────────────────┬───────────────────┘
                      ↓
              [0.12, -0.45, 0.78, ...]
              = 384 floatů = "otisk" textu
```

### 5. Uložení do SQLite databáze

Text + jeho "otisk" (embedding) jdou do databáze:

```
┌─── Tabulka "entries" ────────────────────────────────┐
│ id │ created_at       │ content          │ embedding │
│────┼──────────────────┼──────────────────┼───────────│
│  1 │ 2026-02-27 16:30 │ Pohovor v Googlu │ [BLOB]    │
│  2 │ 2026-02-26 10:00 │ Schůzka s týmem  │ [BLOB]    │
│  3 │ 2026-02-25 20:00 │ Vaření večeře    │ [BLOB]    │
└──────────────────────────────────────────────────────┘
                                             ↑
                                      384 floatů jako
                                      binární data (BLOB)
```

**Proč BLOB?** 384 floatů × 4 byty = **1536 bytů** na záznam. To je nic — tisíce záznamů zabírají pár MB. Programátor zvolil nejjednodušší řešení: uloží to jako binární data přímo do SQLite, žádná speciální vektorová databáze.

---

## Co se děje při hledání

Řekneš Claude: *"Co jsem říkal o pracovních pohovorech?"*

### Krok 1: Tvůj dotaz se taky vektorizuje

```
"pracovní pohovory" → [0.13, -0.43, 0.77, ...]
```

### Krok 2: Porovnání se VŠEMI záznamy

Kód `VectorSearch` (DiaryDatabase.cs řádek 185-221):

```
Dotaz:   [0.13, -0.43, 0.77, ...]

vs. Záznam 1 (pohovor v Googlu):   podobnost = 0.92  ← hodně!
vs. Záznam 2 (schůzka s týmem):    podobnost = 0.41  ← trochu
vs. Záznam 3 (vaření večeře):      podobnost = 0.05  ← vůbec
```

### Krok 3: Vrátí TOP N nejpodobnějších

Seřadí od nejvyšší podobnosti a vrátí nejrelevantnější záznamy.

**Jak se počítá podobnost?** Dot product (skalární součin) — pro L2-normalizované vektory to je totéž jako cosine similarity:

```
Podobnost = a[0]×b[0] + a[1]×b[1] + ... + a[383]×b[383]

Výsledek:  1.0 = identické
            0.0 = nesouvisí
           -1.0 = opačný význam
```

---

## Proč programátor zvolil tenhle přístup?

### Rozhodnutí 1: "Všechno lokálně"
- Žádné API volání, žádný cloud — data zůstávají na tvém počítači
- Model (62 MB) běží přes ONNX Runtime, inference < 10 ms

### Rozhodnutí 2: "SQLite místo vektorové databáze"
- Mohl použít Pinecone, Weaviate, ChromaDB...
- Ale pro osobní deníček je SQLite dokonalé — jeden soubor, nulová konfigurace
- Načte **všechny embeddings do paměti** a porovná v C# — pro tisíce záznamů to stačí

### Rozhodnutí 3: "Vždy mít fallback"

```
VectorSearch selže? → FallbackLikeSearch (hledání textu)
Model neexistuje?   → Text search (LIKE %query%)
Embedding selže?    → Záznam se uloží bez embeddingu
```

Programátor nikdy nenechá systém kompletně selhat.

### Rozhodnutí 4: "Backfill embeddingů"

Při startu server projde všechny staré záznamy BEZ embeddingu a dogeneruje je (`BackfillEmbeddings`, DiaryDatabase.cs řádek 376). Takže i záznamy z doby bez modelu zpětně získají vektorový "otisk".

### Rozhodnutí 5: "Tagy zlepšují hledání"

```
textToEmbed = content + "\n" + tags
```

Tagy se přidají k textu před vektorizací. Takže `tags: "work, interview"` posiluje vyhledávání pracovních témat, i když samotný text je vágní.

---

## Schema evoluce — jak databáze rostla

```
v0: základní deník (text, tagy, datum)
 ↓
v1: + embedding BLOB (vektory pro sémantické hledání)
 ↓
v2: + health_data tabulka (Fitbit)
 ↓
v3: + OAuth tabulky (vzdálený přístup)
 ↓
v4: + restricted sloupec (soukromé záznamy)
 ↓
v5: + scope sloupec (multi-user izolace)
```

Každá verze jen **přidává** — nikdy neodstraňuje. Starší databáze se automaticky upgradují při startu.

---

## Architektura celého systému

```
Klient (Claude Code / claude.ai)
        ↓
┌─────────────────────────────────────┐
│  Recall MCP Server (.NET 10)        │
│                                     │
│  Transport:                         │
│  ├─ stdio (Claude Code, lokálně)    │
│  └─ HTTP/SSE (claude.ai, vzdáleně) │
│                                     │
│  7 Diary Tools:                     │
│  ├─ diary_context (start konverzace)│
│  ├─ diary_write (zápis)            │
│  ├─ diary_query (sémantické hledání)│
│  ├─ diary_update (editace)         │
│  ├─ diary_list_recent (poslední N) │
│  ├─ diary_get (konkrétní záznam)   │
│  └─ diary_time (aktuální čas)      │
│                                     │
│  Auth:                              │
│  ├─ Guardian (plný přístup)        │
│  ├─ Coding (jen nerestriktované)   │
│  └─ Scoped (izolovaný prostor)     │
└──────────┬──────────────────────────┘
           ↓
┌──────────────────┐  ┌──────────────────┐
│  SQLite databáze │  │  ONNX Model      │
│  ~/.recall/      │  │  all-MiniLM-L6-v2│
│  recall.db       │  │  384-dim vektory  │
│                  │  │  lokální inference │
└──────────────────┘  └──────────────────┘
```

---

*Zdroj: analýza kódu z https://github.com/anicka-net/recall*
