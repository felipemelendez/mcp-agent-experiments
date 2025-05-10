#!/usr/bin/env python
"""
Screen live equity data with an MCP-powered research agent.

Overview
--------
This script turns a ChatGPT instance into an **equity-research analyst**
equipped with a headless browser.  The agent scrapes sites like Google
Finance, Yahoo Finance, or Finviz in real time, filters tickers by sector and
market-cap, then ranks up to *N* stocks according to a chosen strategy
(value | growth | dividend).

Workflow
~~~~~~~~
1. **Secrets** – `.env` for OpenAI key, etc.  
2. **Client** – `MCPClient.from_config_file("browser_mcp.json")` spawns /
   attaches to the remote browser tools.  
3. **Model** – `ChatOpenAI` (GPT-4o) set to deterministic `temperature=0.3`.  
4. **Agent** – `MCPAgent` limits to 60 steps and blocks the `shell` tool.  
5. **Prompt** – `AGENT_SYSTEM_PROMPT` + auto-built user query.  
6. **Run** – Agent returns a markdown table; code prints it and usage stats.  
7. **Cleanup** – Close any open browser sessions.


Arguments
^^^^^^^^^
--sector     Sector filter (default: “technology”)  
--strategy   Screening style: value | growth | dividend  
--min_cap    Minimum market cap *in USD* (integer, default 0)  
--limit      Max rows in output table (1 – 10, default 5)

CLI
---
❯ python agent_stocks.py \
    --sector "technology" \
    --strategy "growth" \
    --min_cap 10000000000 \
    --limit 5

Sample session
~~~~~~~~~~~~~~
❯ python agent_stocks.py \
    --sector "technology" \
    --strategy "growth" \
    --min_cap 10_000_000_000 \
    --limit 5

🔍  Query: Find publicly-traded technology companies with a market cap above $10,000,000,000. Apply a growth strategy and return your 5 top picks. Provide live fundamentals (price, P/E, dividend yield) and a short why.

📈  Result:

The data gathered provides a comprehensive list of technology companies with large market caps, which is adequate for screening based on growth strategy.

Now, I'll rank the top 5 technology companies based on their growth potential, considering factors such as P/E ratio and dividend yield.

| Rank | Ticker | Price | P/E | Yield | Reason |
|------|--------|-------|-----|-------|--------|
| 1    | NVDA   | 116.65 | 39.68 | 0.00% | High P/E indicates strong growth expectations in the semiconductor industry. |
| 2    | MSFT   | 438.73 | 33.90 | 0.13% | Consistent growth in cloud and software services. |
| 3    | AAPL   | 198.53 | 30.98 | 0.53% | Strong brand and innovation in consumer electronics. |
| 4    | AMZN   | 193.06 | 31.49 | 0.00% | Dominance in e-commerce and cloud computing. |
| 5    | GOOG   | 154.38 | 17.22 | 0.00% | Leading position in digital advertising and AI. |

📊  Tokens: 0 | Cost: $0.0000 | Elapsed: 33.6s

Notes
~~~~~
* The agent **reflects after its first scrape** to ensure the data gathered is
  adequate; if not, it adjusts its plan automatically.  
* Change `model=` to a cheaper or faster model if GPT-4o is overkill for your
  budget or latency constraints.  
* For reproducible runs in CI, pin versions in a `requirements.txt`.
"""


import argparse
import asyncio
import os
import time

from dotenv import load_dotenv
from langchain_community.callbacks.manager import get_openai_callback
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# --------------------------------------------------------------------------- #
#  System-level instructions embedded in the LLM prompt
# --------------------------------------------------------------------------- #
AGENT_SYSTEM_PROMPT = (
    "You are an equity-research analyst armed with a headless browser.\n"
    "Workflow:\n"
    "1. Use Google / Yahoo Finance / Finviz (or similar) to pull **live** data.\n"
    "2. After the first scrape, pause and reflect in ONE sentence on whether the "
    "data gathered is adequate for screening; adjust the plan if needed.\n"
    "3. Rank up to {limit} tickers by the chosen strategy, justifying each pick "
    "with a single line.\n\n"
    "Output must be a markdown table with these columns:\n"
    "| Rank | Ticker | Price | P/E | Yield | Reason |"
)


###############################################################################
# CLI
###############################################################################
def parse_args() -> argparse.Namespace:
    """
    Parse command-line flags.

    Returns
    -------
    argparse.Namespace
        Namespace containing ``sector``, ``strategy``, ``min_cap``, and ``limit``.
    """
    p = argparse.ArgumentParser(
        description="Screen stocks via an MCP agent that scrapes live finance sites."
    )
    p.add_argument(
        "--sector", default="technology", help="Sector filter (e.g., healthcare)"
    )
    p.add_argument(
        "--strategy",
        default="value",
        choices=["value", "growth", "dividend"],
        help="Screening approach",
    )
    p.add_argument(
        "--min_cap",
        type=int,
        default=0,
        help="Minimum market cap in USD (e.g. 10000000000 for $10 B)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of stocks to return (1–10)",
    )
    return p.parse_args()


###############################################################################
# Prompt builder
###############################################################################
def make_prompt(args: argparse.Namespace) -> str:
    """
    Compose the full prompt sent to the MCP agent.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI options.

    Returns
    -------
    str
        Fully-formed prompt = system instructions + user request.
    """
    user_req = (
        f"Find publicly-traded {args.sector} companies "
        f"with a market cap above ${args.min_cap:,}. "
        f"Apply a {args.strategy} strategy and return your {args.limit} top picks. "
        "Provide live fundamentals (price, P/E, dividend yield) and a short why."
    )
    return AGENT_SYSTEM_PROMPT.format(limit=args.limit) + "\n\n" + user_req


###############################################################################
# Async runner
###############################################################################
async def run() -> None:
    """
    Entrypoint for the asyncio event loop.

    Orchestrates environment loading, MCP/LLM setup, prompt execution,
    pretty-printing, and cleanup.
    """
    load_dotenv()
    args = parse_args()

    # ---------- Build MCP client (browser tooling declared in browser_mcp.json) ----------
    client = MCPClient.from_config_file(
        os.path.join(os.path.dirname(__file__), "browser_mcp.json")
    )

    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

    agent = MCPAgent(llm=llm, client=client, max_steps=60, disallowed_tools=["shell"])

    full_prompt = make_prompt(args)

    print("\n🔍  Query:", full_prompt.splitlines()[-1])  # last line is the user request
    start = time.perf_counter()

    with get_openai_callback() as cb:
        result: str = await agent.run(full_prompt)

    elapsed = time.perf_counter() - start

    # ---------- Pretty print ----------
    print("\n📈  Result:\n")
    print(result)
    print(
        f"\n📊  Tokens: {cb.total_tokens:,} | "
        f"Cost: ${cb.total_cost:.4f} | "
        f"Elapsed: {elapsed:.1f}s"
    )

    # ---------- Cleanup ----------
    if client.sessions:
        await client.close_all_sessions()


###############################################################################
# Guard for sync invocation
###############################################################################
if __name__ == "__main__":
    asyncio.run(run())
