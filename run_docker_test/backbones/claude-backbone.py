from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, UserMessage, TextBlock
import asyncio
# from prompts.prompts import INITIAL_QUERY
# from data_sources.SWEB_data_source import SWELiteDataSource

import git

from data_sources.SWEB_data_source import SWELiteDataSource
from prompts.prompts import INITIAL_QUERY
from constants import data_path

# INITIAL_QUERY = "In the folder {}, there are some tests that are failing to pass: {}.\n\nThe tests are failing after the following commit: {}. \n\nCan you localize the bug and write a patch file for the repository that can fix the bug and make the tests pass? Please provide only the patch file content without any explanations."

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
    source = SWELiteDataSource("dev", data_path)
    for i, item in enumerate(source):
        if i > 1:
            break
        repo = git.Repo(item["repo_path"])
        repo.git.checkout(item["base_commit"])
        query_text = INITIAL_QUERY.format(item["repo_path"], item["FAIL_TO_PASS"], item["base_commit"])
        responses = await client_run_query(client, query_text)
        print(responses)


if __name__ == "__main__":
    asyncio.run(run_client_test())