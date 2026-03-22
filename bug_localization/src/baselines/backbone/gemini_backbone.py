import json
import os
import google.generativeai as genai
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_random_exponential

from src import logger
from src.baselines.backbone.base_backbone import BaseBackbone
from src.baselines.backbone.utils import extract_json_from_output
from src.baselines.context_composers.base_context_composer import BaseContextComposer

class GeminiBackbone(BaseBackbone):
    def __init__(self, name: str, model_name: str, parameters: Dict[str, Any], context_composer: BaseContextComposer):
        super().__init__(name)
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'), transport='rest')
        self._model_name = model_name
        self._parameters = parameters
        self._context_composer = context_composer
        self._model = genai.GenerativeModel(model_name=self._model_name)

    @retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
    def localize_bugs(self, dp: dict) -> Dict[str, Any]:
        logger.info(f"Localizing bug for instance: {dp.get('instance_id', 'unknown')}")
        # We tell the composer to use 'gpt-3.5' just to get the messages correctly
        messages = self._context_composer.compose_chat(dp, "gpt-3.5-turbo-1106")
        
        # Convert OpenAI message format to Gemini format
        prompt = ""
        for msg in messages:
            prompt += f"{msg['role']}: {msg['content']}\n"

        response = self._model.generate_content(prompt, generation_config=self._parameters)
        
        raw_completion_content = response.text
        # Gemini doesn't use tokens the same way, we'll estimate or use response metadata
        try:
            total_tokens = response.usage_metadata.total_token_count
        except AttributeError:
            total_tokens = 0 # Fallback if metadata is missing
            
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
            logger.info(f"Failed to parse json: {raw_completion_content}")

        return {
            "messages": json.dumps(messages),
            "raw_completion": raw_completion_content,
            "json_completion": json.dumps(json_completion_content) if json_completion_content else None,
            "total_tokens": total_tokens,
            "valid_json": json_completion_content is not None,
            "num_predicted_files": num_predicted_files
        }