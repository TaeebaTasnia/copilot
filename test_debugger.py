"""Test the Debugger Agent end to end including MCP chain."""

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
import asyncio
import sys
sys.path.insert(0, ".")

from agents.debugger_agent import run_debugger_agent

async def main():
    question = "Why did my BDT session fail? Can you check the error logs?"
    print(f"Question: {question}\n")
    response = await run_debugger_agent(question)
    print(f"Response:\n{response}")

asyncio.run(main())