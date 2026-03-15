from src.baselines.context_composers.base_context_composer import BaseContextComposer
from src.baselines.context_composers.rag_retrieval import format_retrieved_chunks, group_chunks_by_file, retrieve_chunks
from src.baselines.utils.type_utils import ChatMessage
from src.utils.tokenization_utils import TokenizationUtils


class RAGContextComposer(BaseContextComposer):

    def __init__(self, name: str, system_prompt_path: str, user_prompt_path: str):
        self._name = name
        self._system_prompt = self._read_prompt(system_prompt_path)
        self._user_prompt = self._read_prompt(user_prompt_path)

    def _get_retrieved_context(self, dp: dict, issue_text: str, model_name: str) -> str:
        """Return retrieved repository context for the issue."""
        chunks = retrieve_chunks(dp['repo_content'], issue_text, model_name)
        grouped_chunks = group_chunks_by_file(chunks)
        return format_retrieved_chunks(grouped_chunks)

    def compose_chat(self, dp: dict, model_name: str) -> list[ChatMessage]:
        """Return chat messages for RAG-based localization."""
        issue_text = f"{dp['issue_title']}\n{dp['issue_body']}"
        tokenization_utils = TokenizationUtils(model_name)
        messages = [
            {
                "role": "system",
                "content": self._system_prompt,
            },
            {
                "role": "user",
                "content": self._user_prompt.format(
                    repo_name=f"{dp['repo_owner']}/{dp['repo_name']}",
                    issue_description=issue_text,
                    retrieved_context=self._get_retrieved_context(dp, issue_text, model_name),
                ),
            },
        ]
        return tokenization_utils.truncate(messages)