"""Test the Generic Agent end to end."""
import asyncio
import sys
sys.path.insert(0, ".")

from agents.generic_agent import run_generic_agent

async def main():
    question = "What is the BDT engine and what does it do?"
    print(f"Question: {question}\n")
    response = await run_generic_agent(question)
    print(f"Response:\n{response}")

asyncio.run(main())