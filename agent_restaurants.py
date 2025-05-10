"""
Scout the top restaurants in any city via a headless-browser MCP agent.

Overview
--------
This script wires a **ChatGPT-powered agent** to a browser-automation MCP
server so the LLM can open real web pages, read ratings, compare prices, and
return *at most five* ranked picks in a concise, emoji-bullet format.

Workflow
~~~~~~~~~
1. **Load secrets** from `.env` (your OpenAI key, etc.).
2. **Instantiate** an `MCPClient` from `browser_mcp.json`, which describes the
   remote Playwright-based browser tools.
3. **Create** a `ChatOpenAI` model (no funky kwargs—keep the SDK happy).
4. **Wrap** the model and client in an `MCPAgent`, limiting tools to stay safe.
5. **Build** the final prompt  
   • *System instructions* → `AGENT_SYSTEM_PROMPT` (how to think / format)  
   • *User request*       → auto-composed from CLI flags.
6. **Run** the agent, capture token / cost telemetry, and pretty-print results.
7. **Close** any lingering browser sessions to avoid zombie Chrome processes.

Arguments
^^^^^^^^^
--city      Target city (default: “San Francisco”)  
--cuisine   Optional cuisine filter—e.g. “sushi”  
--budget    Budget string—e.g. “under $60 pp”  
--guests    Party size (default: 2)


CLI
---
❯ python agent_restaurants.py \
    --city "Portland" \
    --cuisine "ramen" \
    --budget "$40" \
    --guests 2

Sample session
~~~~~~~~~~~~~~
❯ python agent_restaurants.py --city "Portland" --cuisine "ramen" --budget "$40"

🔍  Query: Find the best ramen restaurant in Portland for 2 guests with a
budget of $40. Use Google search and any review sites you can access. Return a
ranked list with ratings and a short rationale.

📝  Result:
⭐️ Kizuki Ramen & Izakaya – 4.8/5 – $10–20 – Friendly staff and deep, smoky broth  
⭐️ Wu-Rons – 4.8/5 – $10–20 – Sublime tonkotsu and perfectly firm noodles  
⭐️ Ramen Ryoma – 4.7/5 – $10–20 – Spicy miso that locals rave about  
⭐️ Afuri Izakaya – 4.4/5 – $$ – Bright yuzu-shio style, modern ambience  
⭐️ Pine Street Market – 4.5/5 – $$ – Variety hall with a strong ramen stall

📊  Tokens: 1 234 | Cost: $0.0123 | Elapsed: 34.9 s


Notes
~~~~~
* The agent **reflects after its first scrape**; if data looks thin, it
  revises its plan before output.  
* Adjust `max_steps` for tough searches or debugging.
"""

import argparse
import asyncio
import os
import time
from dotenv import load_dotenv

# ---- LangChain imports ----
from langchain_community.callbacks.manager import get_openai_callback
from langchain_openai import ChatOpenAI

# ---- MCP ----
from mcp_use import MCPAgent, MCPClient

# --------------------------------------------------------------------------- #
#  System-level instructions embedded in the LLM prompt
# --------------------------------------------------------------------------- #
AGENT_SYSTEM_PROMPT = (
    "You are a culinary concierge. You excel at reading live web pages and "
    "comparing ratings, price, and ambience. "
    "After your first web search, pause and reflect in ONE sentence on whether "
    "your current plan will satisfy the user; adjust if needed before returning "
    "a final ranked list (max 5 spots).\n"
    "Respond in exactly this format (one restaurant per line):\n"
    "⭐️ <name> – <rating>/5 – <price> – <short reason>"
)


###############################################################################
# CLI
###############################################################################
def parse_args() -> argparse.Namespace:
    """
    Collect command-line options.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes ``city``, ``cuisine``, ``budget``,
        and ``guests``.
    """
    p = argparse.ArgumentParser(description="Scout top restaurants via MCP agents")
    p.add_argument("--city", default="San Francisco", help="Target city")
    p.add_argument("--cuisine", default="", help="Optional cuisine filter, e.g. sushi")
    p.add_argument("--budget", default="", help="e.g. under $60 per person")
    p.add_argument("--guests", default="2", help="Party size")
    return p.parse_args()


async def main() -> None:
    """
    Orchestrate the full agent run.

    * Loads environment variables.
    * Builds the browser MCP client and LLM.
    * Crafts the prompt from CLI inputs.
    * Executes the agent, timing and metering OpenAI usage.
    * Prints results and cleans up sessions.
    """
    load_dotenv()
    args = parse_args()

    # ----------------------------------------------------------------------- #
    #  Build MCP client (browser automation lives in browser_mcp.json)
    # ----------------------------------------------------------------------- #
    client = MCPClient.from_config_file(
        os.path.join(os.path.dirname(__file__), "browser_mcp.json")
    )

    # Plain ChatOpenAI – NO extra kwargs that confuse the OpenAI SDK
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    agent = MCPAgent(
        llm=llm,
        client=client,
        max_steps=40,
        disallowed_tools=["shell"],  # basic safety guard
    )

    # ----------------------------------------------------------------------- #
    #  Compose the full prompt (system instructions + user request)
    # ----------------------------------------------------------------------- #
    user_query = (
        f"Find the best "
        f"{f'{args.cuisine} ' if args.cuisine else ''}"
        f"restaurant in {args.city} for {args.guests} guests"
        f"{f' with a budget of {args.budget}' if args.budget else ''}. "
        "Use Google search and any review sites you can access. "
        "Return a ranked list with ratings and a short rationale."
    )

    full_prompt = f"{AGENT_SYSTEM_PROMPT}\n\n{user_query}"

    print("\n🔍  Query:", user_query)
    t0 = time.perf_counter()

    with get_openai_callback() as cb:
        result = await agent.run(full_prompt)

    dt = time.perf_counter() - t0
    print("\n📝  Result:\n", result)
    print(
        f"\n📊  Tokens: {cb.total_tokens:,} | "
        f"Cost: ${cb.total_cost:.4f} | "
        f"Elapsed: {dt:.1f}s"
    )

    # Graceful cleanup
    if client.sessions:
        await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(main())
