from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    """Represent one retrieved repository chunk."""

    file_path: str
    chunk_id: str
    content: str
    score: float


def chunk_repository(repo_content: dict[str, str], model_name: str) -> list[RetrievedChunk]:
    """Return repository chunks for retrieval."""
    raise NotImplementedError("Repository chunking is not implemented yet.")


def build_retrieval_index(chunks: list[RetrievedChunk], model_name: str):
    """Return a searchable index for chunks."""
    raise NotImplementedError("Retrieval index construction is not implemented yet.")


def retrieve_chunks(repo_content: dict[str, str], issue_text: str, model_name: str) -> list[RetrievedChunk]:
    """Return the chunks most relevant to the issue."""
    raise NotImplementedError("Chunk retrieval is not implemented yet.")


def group_chunks_by_file(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    """Return retrieved chunks grouped by file path."""
    raise NotImplementedError("Chunk grouping is not implemented yet.")


def format_retrieved_chunks(grouped_chunks: dict[str, list[RetrievedChunk]]) -> str:
    """Return retrieved chunks as prompt text."""
    raise NotImplementedError("Retrieved chunk formatting is not implemented yet.")