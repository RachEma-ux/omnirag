"""OmniRAG Ops UI — Chainlit-based debugging and monitoring interface.

Features:
- Interactive query with trace visualization
- Ingestion job monitoring
- Graph browsing (entity lookup, community reports)
- Pipeline step inspection
"""

import os
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8100")

try:
    import chainlit as cl

    @cl.on_message
    async def on_message(message: cl.Message):
        """Handle user messages — route to OmniRAG API."""
        query = message.content.strip()

        # Command handlers
        if query.startswith("/"):
            await handle_command(query)
            return

        # Show thinking
        msg = cl.Message(content="Searching...")
        await msg.send()

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Auto-route the query
                route_resp = await client.post(
                    f"{API_URL}/graphrag/query/route",
                    json={"query": query, "user_principal": "public"},
                )
                route = route_resp.json()
                mode = route.get("mode", "basic")

                # Execute search
                search_resp = await client.post(
                    f"{API_URL}/v1/search",
                    json={"query": query, "top_k": 5},
                )
                result = search_resp.json()

                # Format response
                answer = result.get("answer", "No answer found.")
                metadata = result.get("metadata", {})
                citations = result.get("citations", [])

                response = f"**Answer:** {answer}\n\n"
                response += f"**Mode:** {mode} (confidence: {route.get('confidence', 0):.2f})\n"
                response += f"**Latency:** {metadata.get('total_latency_ms', 0):.0f}ms\n"

                if citations:
                    response += "\n**Citations:**\n"
                    for c in citations[:5]:
                        response += f"- `{c.get('chunk_id', '')[:8]}`: {c.get('snippet', '')[:100]}\n"

                msg.content = response
                await msg.update()

        except Exception as e:
            msg.content = f"Error: {e}"
            await msg.update()

    async def handle_command(cmd: str):
        """Handle slash commands for ops monitoring."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if cmd == "/status":
                    r = await client.get(f"{API_URL}/health")
                    h = r.json()
                    ports_r = await client.get(f"{API_URL}/ports")
                    ports = ports_r.json()
                    text = f"**Platform Status**\n- Status: {h['status']}\n- Version: {h['version']}\n"
                    text += f"- Ports: {len(ports.get('ports', {}))} services registered\n"
                    await cl.Message(content=text).send()

                elif cmd == "/graph":
                    r = await client.get(f"{API_URL}/graphrag/stats")
                    s = r.json()
                    text = f"**Graph Stats**\n- Mode: {s.get('mode')}\n"
                    text += f"- Entities: {s.get('entities', 0)}\n"
                    text += f"- Relationships: {s.get('relationships', 0)}\n"
                    text += f"- Communities: {s.get('communities', 0)}\n"
                    text += f"- Reports: {s.get('reports', 0)}\n"
                    await cl.Message(content=text).send()

                elif cmd == "/jobs":
                    r = await client.get(f"{API_URL}/intake")
                    jobs = r.json()
                    if not jobs:
                        await cl.Message(content="No intake jobs found.").send()
                        return
                    text = f"**Recent Jobs** ({len(jobs)})\n"
                    for j in jobs[:10]:
                        text += f"- `{j['id'][:8]}` — {j['state']} ({j.get('chunks_created', 0)} chunks)\n"
                    await cl.Message(content=text).send()

                elif cmd == "/trace":
                    await cl.Message(content="Send a query first, then use `/trace` to see the last execution trace.").send()

                else:
                    await cl.Message(content=f"Unknown command: `{cmd}`\n\nAvailable: `/status`, `/graph`, `/jobs`, `/trace`").send()

        except Exception as e:
            await cl.Message(content=f"Command error: {e}").send()

    @cl.on_chat_start
    async def on_start():
        """Welcome message."""
        await cl.Message(
            content="Welcome to **OmniRAG Ops UI**. Ask questions about your documents, inspect traces, or monitor the pipeline.\n\nType a query to search, or use commands:\n- `/status` — platform health\n- `/graph` — graph stats\n- `/jobs` — recent intake jobs",
        ).send()

except ImportError:
    # Chainlit not installed — provide a stub
    def main():
        print("Chainlit not installed. Install with: pip install chainlit")
        print(f"API URL: {API_URL}")

    if __name__ == "__main__":
        main()
