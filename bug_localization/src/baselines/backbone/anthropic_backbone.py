import json
import os
from typing import Dict, Any, List

import backoff
import anthropic
from tenacity import retry, stop_after_attempt, wait_random_exponential

from src import logger
from src.baselines.backbone.base_backbone import BaseBackbone
from src.baselines.backbone.utils import extract_json_from_output
from src.baselines.context_composers.base_context_composer import BaseContextComposer
from src.baselines.utils.type_utils import ChatMessage

class AnthropicBackbone(BaseBackbone):

    def __init__(
            self,
            name: str,
            model_name: str,
            parameters: Dict[str, Any],
            context_composer: BaseContextComposer,
    ):
        super().__init__(name)
        # 1. Initialize Anthropic Client
        self._client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        self._model_name = model_name
        self._parameters = parameters
        self._context_composer = context_composer

    @backoff.on_exception(backoff.expo, anthropic.APIError)
    def _get_chat_completion(self, messages: List[ChatMessage], system_prompt: str = None) -> Any:
        kwargs = {
            "messages": messages,
            "model": self._model_name,
            "max_tokens": self._parameters.get("max_tokens", 4096)
        }
        if system_prompt:
            kwargs["system"] = system_prompt
            
        # --- FIXED: Filter out OpenAI-specific parameters like 'seed' ---
        for k, v in self._parameters.items():
            if k not in ["max_tokens", "system", "seed"]: 
                kwargs[k] = v

        return self._client.messages.create(**kwargs)

    @retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
    def localize_bugs(self, dp: dict) -> Dict[str, Any]:
        messages = self._context_composer.compose_chat(dp, "gpt-3.5-turbo-1106")
        
        # 3. Extract system prompt from messages if it exists
        system_prompt = None
        if messages and messages[0].get("role") == "system":
            system_prompt = messages[0].get("content")
            messages = messages[1:] # Remove it from the main list

        completion = self._get_chat_completion(messages, system_prompt)
        
        # 4. Extract Claude's token usage and text content
        total_tokens = completion.usage.input_tokens + completion.usage.output_tokens
        raw_completion_content = completion.content[0].text

        json_completion_content = None
        num_predicted_files = 0
        
        try:
            json_completion_content = extract_json_from_output(raw_completion_content)
            
            if isinstance(json_completion_content, list):
                num_predicted_files = len(json_completion_content)
            elif isinstance(json_completion_content, dict):
                for value in json_completion_content.values():
                    if isinstance(value, list):
                        num_predicted_files += len(value)
                        
        except Exception:
            logger.info(f"Failed to parse json from output: {raw_completion_content}")

        return {
            "messages": json.dumps(messages),
            "raw_completion": raw_completion_content,
            "json_completion": json.dumps(json_completion_content) if json_completion_content else None,
            "total_tokens": total_tokens,
            "valid_json": json_completion_content is not None,
            "num_predicted_files": num_predicted_files
        }