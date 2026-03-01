import sys
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from mcp.server.fastmcp import FastMCP

from config import RecallConfig
from embeddings import EmbeddingService
from database import DiaryDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

config = RecallConfig.load()
embeddings = EmbeddingService(config.model_name)
db = DiaryDatabase(config.database_path, embeddings)
db.backfill_embeddings()

mcp = FastMCP("recall")


def format_entries(entries):
    lines = []
    for e in entries:
        try:
            dt = datetime.fromisoformat(e.created_at).astimezone()
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = e.created_at
        tag_str = f" [{e.tags}]" if e.tags else ""
        lines.append(f"--- Entry #{e.id} ({date_str}){tag_str} ---")
        lines.append(e.content)
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def diary_time() -> str:
    """Returns the current date, time, and day of week. Call this when you need to know what time it is."""
    now = datetime.now(timezone.utc).astimezone()
    return f"{now:%Y-%m-%d %H:%M:%S %z} ({now:%A})"


@mcp.tool()
def diary_write(
    content: str,
    tags: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> str:
    """Write a diary entry. Record thoughts, events, decisions, insights, or anything worth remembering. Be specific and detailed.

    Args:
        content: The diary entry text
        tags: Optional comma-separated tags (e.g. 'work,decision,project-x')
        conversation_id: Optional conversation ID to group related entries
    """
    if not content.startswith("**Date:") and not content.startswith("Date:"):
        now = datetime.now(timezone.utc).astimezone()
        date_header = f"**Date: {now:%B %d, %Y} ({now:%A} {now:%H:%M})**"
        content = f"{date_header}\n\n{content}"

    entry_id = db.write_entry(content, tags, conversation_id)
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    return f"Entry #{entry_id} saved at {now_str}."


@mcp.tool()
def diary_update(
    id: int,
    content: str,
    tags: Optional[str] = None,
) -> str:
    """Update an existing diary entry. Replaces the content and tags of the specified entry. The created_at timestamp is preserved.

    Args:
        id: The ID of the entry to update
        content: The new content for the entry
        tags: Optional new tags (replaces existing tags)
    """
    if db.update_entry(id, content, tags):
        now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        return f"Entry #{id} updated at {now_str}."
    return f"Entry #{id} not found."


@mcp.tool()
def diary_get(id: int) -> str:
    """Get a specific diary entry by its ID number.

    Args:
        id: The entry ID number
    """
    entry = db.get_entry(id)
    if not entry:
        return f"Entry #{id} not found."
    return format_entries([entry])


@mcp.tool()
def diary_query(
    query: str,
    limit: int = 0,
) -> str:
    """Search past diary entries using natural language. Use keywords or phrases to find specific topics, events, or decisions.

    Args:
        query: Search words or phrase
        limit: Max results to return (default: from config)
    """
    effective_limit = limit if limit > 0 else config.search_result_limit
    results = db.search(query, effective_limit)
    if not results:
        return "No entries found matching your query."
    return format_entries(results)


@mcp.tool()
def diary_context(topic: str) -> str:
    """Get relevant diary context for the current conversation. Call this at the START of every conversation with a brief topic summary. Returns recent entries plus entries matching the topic.

    Args:
        topic: Brief summary of what this conversation is about
    """
    conversation_id = uuid.uuid4().hex[:12]
    limit = config.auto_context_limit

    recent = db.get_recent(3)
    relevant = db.search(topic, limit)

    seen = set()
    merged = []
    for e in recent + relevant:
        if e.id not in seen:
            seen.add(e.id)
            merged.append(e)

    merged.sort(key=lambda e: e.created_at, reverse=True)
    merged = merged[: limit + 3]

    total = db.get_entry_count()

    if not merged:
        now = datetime.now(timezone.utc).astimezone()
        return (
            f"No diary entries yet. This is a fresh start.\n"
            f"Conversation ID: {conversation_id}\n"
            f"Current time: {now:%Y-%m-%d %H:%M:%S %z} ({now:%A})"
        )

    now = datetime.now(timezone.utc).astimezone()
    header = (
        f"Current time: {now:%Y-%m-%d %H:%M:%S %z} ({now:%A})\n"
        f"Diary has {total} entries total. Showing {len(merged)} relevant:\n"
        f"Conversation ID: {conversation_id}\n\n"
    )
    return header + format_entries(merged)


@mcp.tool()
def diary_list_recent(count: int = 10) -> str:
    """List the most recent diary entries in chronological order.

    Args:
        count: Number of entries to return (default: 10)
    """
    entries = db.get_recent(count)
    if not entries:
        return "No diary entries yet."
    return format_entries(entries)


if __name__ == "__main__":
    logger.info("Recall Python MCP server starting...")
    mcp.run(transport="stdio")
