"""An MCP server exposing one Tool: read-only SQL queries against the local
ERP database. Built as a learning project and a direct answer to a real job
requirement — "local SQL databases," "permissions, secure data transfer,
logging" are the job posting's own words; this is built against that spec.

Security is layered on purpose, not trusting any single check:
  1. The query text itself is checked — only SELECT is allowed.
  2. The database connection is opened in SQLite's own read-only mode, so
     even a check we got wrong in (1) still can't write anything.
  3. Every call — query, timestamp, and whether it was allowed — is logged.

Run it: python server/sql_server.py
"""
import logging
import re
import sqlite3
from pathlib import Path

from mcp.server.mcpserver import MCPServer

DB_PATH = Path(__file__).parent.parent / "db" / "erp.db"
LOG_PATH = Path(__file__).parent.parent / "query_audit.log"

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)

# The MCPServer instance is the whole server. Its name and description are
# what an AI client sees when deciding whether this server is relevant.
mcp = MCPServer(
    name="sql-erp-readonly",
    description="Read-only query access to a small ERP database (products, orders).",
)


def _is_select_only(sql: str) -> bool:
    """The first layer of defense: reject anything that isn't a single,
    plain SELECT. Deliberately strict — this is a boundary we document,
    not a feature we try to make clever."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return False  # no stacking a second statement after the first
    return bool(re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE))


@mcp.tool()
def run_query(sql: str) -> str:
    """Run a read-only SQL SELECT query against the ERP database (products
    and orders tables) and return the results. Only SELECT statements are
    permitted — INSERT, UPDATE, DELETE and DDL are rejected before they ever
    reach the database.
    """
    if not _is_select_only(sql):
        logging.info("REJECTED (not a plain SELECT): %s", sql)
        return "Rejected: only a single SELECT statement is permitted."

    # Second layer: SQLite's own read-only connection mode. Even if the
    # check above had a bug, this connection is physically incapable of
    # writing to the database file.
    uri = f"file:{DB_PATH}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error as e:
        logging.info("ERROR: %s -- query: %s", e, sql)
        return f"Query error: {e}"

    logging.info("OK (%d rows): %s", len(rows), sql)
    if not rows:
        return "No rows returned."
    lines = [" | ".join(columns)]
    lines += [" | ".join(str(v) for v in row) for row in rows]
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport
