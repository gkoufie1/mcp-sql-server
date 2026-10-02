# mcp-sql-server

A real MCP (Model Context Protocol) server: one tool, exposing read-only SQL access to a
small ERP-style SQLite database, to any MCP-aware AI client. Built and verified the same way
as the other projects in this portfolio: a real architecture, every claim backed by a command
that actually ran, every failure documented as it happened — including a live test where a
fresh AI session, with zero hints about the schema, found the tool, used it, got a real error
back, and corrected itself.

**What this is:** a stdio MCP server (`server/sql_server.py`) exposing a single tool,
`run_query`, against a local SQLite database (`db/erp.db`) holding two tables — `products`
and `orders`. Built directly against a real job posting's own words: "local SQL databases,"
"permissions, secure data transfer, logging." Security is layered on purpose, not trusting
any single check:

1. The query text itself is checked — only a single, plain `SELECT` is allowed; anything else
   (`INSERT`, `UPDATE`, `DELETE`, DDL, statement stacking) is rejected before it reaches the
   database.
2. The database connection is opened in SQLite's own read-only mode
   (`file:erp.db?mode=ro`), so even a bug in check #1 still can't write anything.
3. Every call is logged to `query_audit.log` — the query text, the timestamp, and whether it
   was allowed, rejected, or errored.

## Architecture

```
AI client (Claude Code CLI, or any MCP-aware client)
        │  stdio (JSON-RPC over stdin/stdout)
        ▼
server/sql_server.py  ── run_query(sql) ──┐
   1. regex check: single SELECT only      │
   2. opens db/erp.db in SQLite read-only   ├──► db/erp.db (products, orders)
      mode, physically can't write          │
   3. logs every call                       ▼
                                      query_audit.log
```

## Build steps

1. **Seeded a small but real schema** (`db/seed.py`): `products` (sku, name, unit price,
   quantity on hand) and `orders` (product, quantity, status — `pending` / `shipped` /
   `cancelled`), with a foreign key between them. Enough structure that a join or a `GROUP BY`
   actually means something, rather than one flat table.
2. **Wrote the server** around a single tool rather than many, matching the MCP pattern of a
   small, legible surface: one capability, described precisely enough that an AI client can
   decide on its own when to reach for it.
3. **Registered it with Claude Code** (`claude mcp add sql-erp -- python
   server/sql_server.py`, local scope) and confirmed it with `claude mcp get sql-erp` —
   `Connected`.
4. **Ran the adversarial case before trusting the happy path**: asked the server to run
   `DELETE FROM products` directly. Rejected, logged:
   ```
   REJECTED (not a plain SELECT): DELETE FROM products
   ```
5. **Tested discovery cold** — see Results below.

## Results — the real test

The actual target wasn't "can this server answer a query I write for it" — it was "will an AI
client find this tool on its own, in a brand-new session, with no hints about the schema, and
use it correctly." Opened a fresh `claude` CLI session inside this repo and asked:

> "Which products currently have a pending order?"

It reached for the tool immediately, guessed wrong on the first try, and recovered — all
visible in `query_audit.log`, written by the server itself, not by the AI:

```
ERROR: no such column: p.product_id -- query: SELECT DISTINCT p.product_id, p.name, o.order_id, o.status FROM products p JOIN orders o ON p.product_id = o.product_id WHERE o.status = 'pending'
OK (2 rows): SELECT name FROM sqlite_master WHERE type='table'
OK (1 rows): SELECT * FROM products LIMIT 1
OK (1 rows): SELECT * FROM orders LIMIT 1
OK (2 rows): SELECT DISTINCT p.id, p.sku, p.name FROM products p JOIN orders o ON p.id = o.product_id WHERE o.status = 'pending'
```

It guessed a column name that didn't exist, got a real `sqlite3.Error` back through the tool,
queried `sqlite_master` and a `LIMIT 1` row from each table to learn the actual schema, then
re-ran the join correctly — landing on the right two products (`SKU-1002` Wireless Mouse,
`SKU-1003` 27in Monitor) without being told the schema anywhere in the prompt.

## Findings

| # | What happened | Cause | Fix |
|---|---|---|---|
| 1 | In VS Code's native Claude Code extension panel, the server never got called — every answer came from the AI reading `erp.db` directly via `python -c "import sqlite3..."` in a Bash tool call, bypassing the server entirely | The extension's chat panel doesn't attach project-scoped (local) MCP servers the same way the `claude` CLI does, even after a full window reload | Ran the same question through a `claude` CLI session (Terminal → `claude`) instead of the extension's sidebar chat — the tool was found and called immediately, confirmed via fresh lines in `query_audit.log` |
| 2 | First real query attempt failed with `no such column: p.product_id` | The AI assumed a column name (`product_id` on `products`) instead of checking the actual schema first — the primary key is just `id` | Not a bug in the server — this is the tool's error path working as intended. The AI received the real SQLite error through `run_query`'s return value, queried `sqlite_master` to see the real schema, and corrected itself without any help |
| 3 | Needed to confirm the write-rejection wasn't just theoretical | Easy to assume a check "would" reject something without ever running it | Ran `DELETE FROM products` directly through the tool and confirmed the exact rejection line in `query_audit.log`, before trusting the happy-path tests |

## What this does not show

- **A single local SQLite file, not a production database.** No concurrent-write handling,
  no connection pooling, no network-exposed database — the read-only guarantee comes from
  SQLite's own `mode=ro` URI flag, not from database-server-level permissions.
- **No authentication beyond the process boundary.** Anything that can spawn
  `python server/sql_server.py` over stdio can call `run_query`. Fine for a local MCP server
  launched by a trusted client; not a model for a multi-user or network-facing deployment.
- **Only `SELECT` is handled at all.** There's no attempt to support parameterized writes
  behind a stricter permission model — the project's whole point is that writes don't happen,
  full stop.
- **Tested against one client (Claude Code's CLI).** Other MCP clients may discover and call
  tools differently; the VS Code extension gap in Findings #1 is evidence of exactly that kind
  of client-to-client difference.

## Cost

**$0.** Everything here runs locally against a SQLite file — no cloud resources, no API keys,
nothing billable anywhere.

## Reproduce it

```bash
git clone https://github.com/gkoufie1/mcp-sql-server
cd mcp-sql-server
pip install mcp   # tested against mcp==2.2.0

# rebuild the database from scratch at any time (erp.db is already included):
python db/seed.py

# register it with Claude Code (local to this project) and run it:
claude mcp add sql-erp -- python server/sql_server.py
claude mcp get sql-erp       # should report "Connected"
```

Then, from a **terminal `claude` session** (not VS Code's native extension chat panel — see
Findings #1) opened in this folder, just ask a question in plain English — e.g. "which
products are out of stock?" or "what's the total value of inventory on hand?" — and watch
`query_audit.log` for the queries it actually runs.

## Repo layout

```
mcp-sql-server/
├── README.md              you are here
├── .gitignore
├── db/
│   ├── erp.db             sample ERP database: products, orders
│   └── seed.py            rebuilds erp.db from scratch
└── server/
    └── sql_server.py      the MCP server: one tool, run_query

query_audit.log is generated at runtime and gitignored — every call this server
has ever handled, written by the server itself.
```
