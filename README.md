# 🛠️ MCP Quickstart

**Connect any LLM to any MCP server—no proprietary client required**

Model Context Protocol (MCP) is a lightweight spec that lets a large‑language‑model reach *outside* its training data by calling remote “servers” that expose tools such as browser automation, database queries, 3‑D renderers, and more.

`mcp‑use` is a Python SDK *and* agent framework that hands those tools to your chat model without ceremony:

* **Single config file** – list every MCP server you want and how to start or attach to it.
* **MCPClient** – spins up the servers, pulls each tool’s JSON schema, and maintains live sessions.
* **MCPAgent** – wraps your LLM (GPT‑4o, Claude, Llama 3 …) and runs the classic *think → act → observe* loop for you.
* Batteries included – multi‑server routing, disallowed\_tools safety filter, and drop‑in LangChain compatibility.

---

## 🤖 How an Agent Thinks

1. **Think** – The model receives the user prompt along with a scratch-pad: a running history of its previous thoughts, tool calls, and observations. This gives the model memory within the loop, helping it reason step-by-step, avoid repetition, and stay grounded in context.
2. **Act** – If the model decides to call a tool, MCPAgent encodes the request and executes it via MCPClient.
3. **Observe** – The result of the tool call is captured and appended to the scratch-pad.
4. **Repeat** - The model receives the updated context and continues reasoning until it outputs a final answer (i.e., regular text) or hits a termination condition.

> This loop turns a one-shot chat model into a goal-seeking problem-solver—able to gather live data, perform multi-step reasoning, and take real-world actions.

### Under the Hood
What happens inside `await agent.run("…")`
```
User prompt
   │
   ▼
[LLM “thinks”] ──► decides to call `search_web`
   │                          │
   │               MCPAgent marshals JSON
   │                          ▼
[MCPClient] ──► finds matching MCP server ──► tool runs in a sandbox
   │                                               │
   │<───────── JSON result comes back ─────────────┘
   │
   ▼
Tool output appended to chat; loop continues
```
The loop ends when the model returns ordinary text instead of another tool-call, and that becomes the final answer.

---

## 🚀 Quickstart Checklist (from zero)

### 1  Start in a fresh terminal

```
mkdir mcp‑quickstart
cd mcp‑quickstart
```

### 2  Open the folder in Cursor (optional)

```
open -a "Cursor" .
```

### 3  Create & activate the virtual env *(repeat inside any new shell)*

```
python3 -m venv venv
source venv/bin/activate
```

### 4  Install dependencies

```
pip install mcp‑use langchain‑openai python‑dotenv
```

*Need Anthropic, Groq, etc.?* Swap in `langchain‑anthropic`, `langchain‑groq`, …

### 5  Add your LLM API key

```
echo "OPENAI_API_KEY=sk‑..." > .env
```

### 6  Create **browser\_mcp.json**

```
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "env": { "DISPLAY": ":1" }
    }
  }
}
```

### 7  Create **agent.py**

```
import asyncio, os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPClient, MCPAgent

load_dotenv()

async def main():
    client = MCPClient.from_config_file("browser_mcp.json")
    llm    = ChatOpenAI(model="gpt‑4o")
    agent  = MCPAgent(llm=llm, client=client, max_steps=30)
    result = await agent.run("Find the best coffee shop in Brooklyn")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

### 8  Run the agent

```
python agent.py
```

⌛ First launch downloads the Playwright MCP server via *npx*, so it may take a minute.


Project tree should now look like:

```
mcp‑quickstart/
├── agent.py
├── browser_mcp.json
├── .env
└── venv/
```

---

## 📦 Required Packages & Common Commands

* `pip install mcp‑use` – unified MCP client library.
* `pip install "mcp‑use[search]"` – pulls `fastembed` & tiny data files when you need semantic search tools.
* `pip install langchain‑openai` – LangChain wrapper for OpenAI models.
* `python3 -m venv venv` – create *venv/*.
* `source venv/bin/activate` – enter the venv in the current shell.
* `deactivate` – leave the venv (closing the terminal also resets env‑vars).

---

## 🧩 Example Agents Included in This Repo

| Agent                    | Purpose                                                                                               | MCP Servers Used                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| **Quick Restaurant Finder** | One-liner demo that uses a Playwright browser to fetch “best restaurant” results for San Francisco | Playwright (browser automation)         |
| **Airbnb Finder**        | Surfaces top rentals that meet price, amenity, and date constraints                            | Playwright (browser) + Airbnb MCP       |
| **Restaurant Scout**     | Ranks the best restaurants in any city via live Google search and review-site scraping                 | Playwright (browser automation)         |
| **Equity Screener**      | Scrapes live fundamentals and returns growth/value/dividend shortlists on demand                       | Playwright (browser automation)         |


---

## 💡 Tips & Troubleshooting

* **venv gotcha** – opening a new terminal (or the built‑in one inside Cursor) starts a fresh shell, so re‑activate the venv.
* **ModuleNotFoundError: fastembed** – install with `pip install "mcp‑use[search]"` or `pip install fastembed`.
* **Step limit** – raise `max_steps` if your agent stops too early.
* **Safety filter** – block risky tools by passing `disallowed_tools=[...]` to `MCPAgent`.

---

## ⚖️ License

MIT – see LICENSE for details.
