import json
import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

from src import logger


class PromptCache:
    """
    Thread-safe, disk-backed cache for composed AI prompts.

    Stores the fully composed chat messages (prompts) alongside metadata
    (changed_files, all_files) so that once prompts are cached, the cloned
    repo can be safely deleted and API calls can still proceed using the
    cached prompts.

    Cache is strategy-aware: the cache directory should include the
    context_composer name so different strategies don't collide.
    """

    def __init__(self, cache_dir: str):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self._cache_dir / "prompt_cache.jsonl"
        self._lock = threading.Lock()
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_existing()

    def _load_existing(self):
        """Load existing cached prompts from disk on startup."""
        if self._cache_file.exists():
            with open(self._cache_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line.strip())
                        self._index[entry['text_id']] = entry
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Skipping corrupt cache line: {e}")
            logger.info(f"Loaded {len(self._index)} cached prompts from {self._cache_file}")

    def has(self, text_id: str) -> bool:
        """Check if a prompt is already cached for a given text_id."""
        return text_id in self._index

    def get(self, text_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached prompt entry by text_id."""
        return self._index.get(text_id)

    def put(
        self,
        text_id: str,
        messages: list,
        changed_files: list,
        all_files: list,
    ):
        """
        Cache a composed prompt entry to memory and disk.

        Args:
            text_id: Unique identifier for the data point.
            messages: The composed chat messages (system + user prompt).
            changed_files: Ground-truth list of buggy files.
            all_files: List of all file paths in the repo at that commit.
        """
        entry = {
            'text_id': text_id,
            'messages': messages,
            'changed_files': changed_files,
            'all_files': all_files,
        }
        with self._lock:
            self._index[text_id] = entry
            with open(self._cache_file, 'a') as f:
                f.write(json.dumps(entry) + "\n")

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all cached entries."""
        return list(self._index.values())

    def get_uncached_text_ids(self, all_text_ids: List[str]) -> List[str]:
        """Return text_ids that are NOT yet cached."""
        return [tid for tid in all_text_ids if tid not in self._index]

    @property
    def size(self) -> int:
        return len(self._index)

    def __contains__(self, text_id: str) -> bool:
        return self.has(text_id)

    def __len__(self) -> int:
        return self.size
