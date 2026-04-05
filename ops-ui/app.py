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
        query = message.content

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
