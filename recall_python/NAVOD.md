# Recall Python — Návod k použití

## 1. Registrace MCP serveru s Claude Code

Jednorázový příkaz — spusť v terminálu:

```bash
claude mcp add recall -- \
  /Users/miroslavkolarik/Documents/projects/claude_repo/muj_testovaci_denicek/recall_python/.venv/bin/python \
  /Users/miroslavkolarik/Documents/projects/claude_repo/muj_testovaci_denicek/recall_python/server.py
```

### Ověření registrace

```bash
claude mcp list
```

Měl bys vidět `recall` v seznamu. Pokud chceš odebrat:

```bash
claude mcp remove recall
```

---

## 2. Jak to funguje v praxi

Po registraci má Claude Code k dispozici 7 nových nástrojů. **Nemusíš je volat ručně** — Claude je použije automaticky, když je to relevantní. Ale můžeš ho i explicitně požádat.

---

## 3. Příklady použití

### Zápis do deníčku

Řekni Claude:

> "Zapiš si, že jsem dnes měl schůzku s klientem Acme Corp o redesignu webu. Dohodli jsme se na React + Next.js stack."

Claude automaticky zavolá `diary_write` a uloží záznam s datem.

> "Zapiš si, že jsem se rozhodl pro PostgreSQL místo MongoDB. Tagni to jako 'architecture,decision'."

### Hledání v záznamech

> "Co jsem říkal o tom redesignu webu?"

Claude zavolá `diary_query` se sémantickým vyhledáváním — najde záznamy i když použiješ jiná slova než při zápisu.

> "Jaká technologická rozhodnutí jsem udělal za poslední měsíc?"

### Kontext na začátku konverzace

> "Chci pokračovat v práci na projektu Acme Corp."

Claude zavolá `diary_context` a načte relevantní záznamy — ví, co se dělo dříve.

### Zobrazení posledních záznamů

> "Ukaž mi posledních 5 záznamů z deníčku."

Claude zavolá `diary_list_recent(count=5)`.

### Konkrétní záznam

> "Ukaž mi záznam číslo 3."

Claude zavolá `diary_get(id=3)`.

### Editace záznamu

> "Uprav záznam #3 — přidej, že klient potvrdil budget 500k."

Claude zavolá `diary_update`.

### Aktuální čas

> "Kolik je hodin?"

Claude zavolá `diary_time`.

---

## 4. Tipy pro efektivní používání

### Buď konkrétní při zápisu
```
❌ "Zapiš si, že jsem měl meeting."
✅ "Zapiš si, že jsem měl meeting s Petrem z Acme Corp o API integraci.
   Výsledek: budeme používat REST, ne GraphQL. Deadline je 15. března."
```

### Používej tagy
```
"Zapiš to s tagy 'project-acme,api,decision'"
```
Tagy zlepšují vyhledávání — jsou součástí embeddingů.

### Ptej se přirozeně
Sémantické vyhledávání rozumí významu, ne jen klíčovým slovům:
```
"Co jsem říkal o databázích?"
→ Najde i "rozhodl jsem se pro PostgreSQL" (i když slovo "databáze" tam není)
```

### Nech Claude pracovat s kontextem
Na začátku nové konverzace řekni o čem to bude:
```
"Pokračujeme na projektu Acme Corp, konkrétně API design."
```
Claude si načte relevantní historii a bude vědět, co se dělo.

---

## 5. Kde jsou data?

```
~/.recall/recall_py.db     # SQLite databáze se všemi záznamy
~/.recall/config.json      # Konfigurace (volitelné)
```

### Prohlížení dat ručně

```bash
sqlite3 ~/.recall/recall_py.db "SELECT id, created_at, substr(content, 1, 80), tags FROM entries ORDER BY created_at DESC LIMIT 10;"
```

### Záloha

```bash
cp ~/.recall/recall_py.db ~/.recall/recall_py_backup.db
```

---

## 6. Konfigurace (volitelné)

Vytvoř `~/.recall/config.json`:

```json
{
  "autoContextLimit": 5,
  "searchResultLimit": 10,
  "systemPrompt": "Vždy piš záznamy česky."
}
```

| Pole | Default | Popis |
|------|---------|-------|
| `autoContextLimit` | 5 | Kolik relevantních záznamů načíst při diary_context |
| `searchResultLimit` | 10 | Max výsledků při diary_query |
| `systemPrompt` | "" | Vlastní instrukce pro chování |
| `promptFile` | — | Cesta k souboru s instrukcemi (místo inline) |

---

## 7. Řešení problémů

### "MCP server not found"
```bash
claude mcp list          # Je recall v seznamu?
claude mcp remove recall  # Odeber a znovu přidej
claude mcp add recall -- ...
```

### "Model loading slow"
První spuštění stahuje model (~90 MB). Další starty jsou rychlé (cache v `~/.cache/huggingface/`).

### "No entries found"
Deníček je prázdný — nejdřív něco zapiš pomocí `diary_write`.

### Chci začít od nuly
```bash
rm ~/.recall/recall_py.db
```
Databáze se automaticky vytvoří při dalším spuštění.
