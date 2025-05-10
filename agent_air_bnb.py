import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient


async def run_airbnb_agent():
    # Load environment variables
    load_dotenv()

    # Create MCPClient from configuration dictionary
    client = MCPClient.from_config_file(
        os.path.join(os.path.dirname(__file__), "airbnb_mcp.json")
    )

    # Create LLM
    llm = ChatOpenAI(model="gpt-4o")

    # Create agent with the client
    agent = MCPAgent(llm=llm, client=client, max_steps=30)

    try:
        # Run a query to search for accomodations
        results = await agent.run(
            "Find me a nice place to stay in Ibiza for 2 adults "
            "for a week in July. I prefer places with a pool and "
            "a good view of the sea and good reviews. I don't want to spend more than 3000€. "
            "Show me the top 3 options."
        )
        print(f"\nResult: {results}")
    finally:
        # Ensure that we clean up resources properly
        if client.sessions:
            await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(run_airbnb_agent())
