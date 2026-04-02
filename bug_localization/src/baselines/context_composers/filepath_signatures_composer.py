from src import logger
from src.baselines.context_composers.base_context_composer import BaseContextComposer
from src.baselines.context_composers.tree_sitter.utils import extract_signatures
from src.baselines.context_composers.utils import sort_files_by_relevance
from src.baselines.utils.type_utils import ChatMessage
from src.utils.tokenization_utils import TokenizationUtils


class FilepathSignaturesComposer(BaseContextComposer):
    """Provides file paths ranked by BM25 relevance,
    annotated with its function / class / method signatures extracted
    using tree sitter
    """

    def __init__(self, name: str, system_prompt_path: str, user_prompt_path: str):
        self._name = name
        self._system_prompt = self._read_prompt(system_prompt_path)
        self._user_prompt = self._read_prompt(user_prompt_path)

    @staticmethod
    def _get_filepath_signatures_list(dp: dict, issue_text: str, model_name: str) -> str:
        """Build a string of ``filepath\\n  signature1\\n  signature2\\n…``
        entries"""
        ranked = sort_files_by_relevance(dp["repo_content"], issue_text)
        parts: list[str] = []
        for path, _content in ranked:
            file_extension = path.rsplit(".", 1)[-1] if "." in path else ""
            sigs = extract_signatures(_content, file_extension)
            entry = path
            if sigs:
                entry += "\n" + "\n".join(f"  {s}" for s in sigs)
            parts.append(entry)
        return "\n".join(parts)

    def compose_chat(self, dp: dict, model_name: str) -> list[ChatMessage]:
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
                    filepath_signatures=self._get_filepath_signatures_list(
                        dp, issue_text, model_name
                    ),
                ),
            },
        ]

        logger.info(
            f"Messages tokens count: {tokenization_utils.count_messages_tokens(messages)}"
        )

        truncated_messages = tokenization_utils.truncate(messages)

        logger.info(
            f"Truncated messages tokens count: "
            f"{tokenization_utils.count_messages_tokens(truncated_messages)}"
        )

        return truncated_messages
