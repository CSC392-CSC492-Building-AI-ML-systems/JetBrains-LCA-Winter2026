from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, UserMessage, TextBlock
import asyncio

async def initialize_client():
    client = ClaudeSDKClient()
    await client.connect(options=ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Glob"]
    )
    )
    return client
    

async def client_run_query(client: ClaudeSDKClient, query_text):

    responses = []

    await client.query(prompt=query_text)
    async for msg in client.receive_response():
        if (isinstance(msg, UserMessage) or isinstance(msg, AssistantMessage)):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    responses.append(block.text)

    return responses

async def run_client_test():
    client = await initialize_client()
    responses = await client_run_query(client, "Write a short poem and save it to a file named poem.txt")
    print(responses)


if __name__ == "__main__":
    asyncio.run(run_client_test())