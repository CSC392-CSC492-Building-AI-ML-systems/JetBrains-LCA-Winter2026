from src.utils.tokenization_utils import TokenizationUtils

def get_context_metrics(messages: list[dict]):
    tokenization_utils = TokenizationUtils('gpt-4o')
    
    # Safely handle different API message structures
    if len(messages) >= 2:
        system_content = messages[0]['content']
        user_content = messages[-1]['content']
    elif len(messages) == 1:
        system_content = ""
        user_content = messages[0]['content']
    else:
        system_content = ""
        user_content = ""

    return {
        'system_prompt_tokens': tokenization_utils.count_text_tokens(system_content),
        'user_prompt_tokens': tokenization_utils.count_text_tokens(user_content),
        'total_tokens': tokenization_utils.count_messages_tokens(messages),
    }