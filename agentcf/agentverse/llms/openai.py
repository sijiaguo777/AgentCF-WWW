
import os
import json
import time
import asyncio
from logging import getLogger
from typing import Dict, List, Optional, Union, Any

import requests

from pydantic import BaseModel, Field

from agentverse.llms.base import LLMResult

from . import llm_registry
from .base import BaseChatModel, BaseCompletionModel, BaseModelArgs

logger = getLogger()

_batch_host = os.environ.get("BATCH_API_HOST", "http://localhost:8888")
_batch_url = f"{_batch_host}/batch"

# Direct API configuration: used when batch server is unavailable
_DIRECT_API_BASE = os.environ.get("DIRECT_API_BASE", "https://api.deepseek.com")
_DIRECT_API_KEY = os.environ.get("DIRECT_API_KEY", "")  # Fallback to api_key_list[0] if empty


class OpenAIChatArgs(BaseModelArgs):
    model: str = Field(default="gpt-3.5-turbo")
    max_tokens: int = Field(default=2048)
    temperature: float = Field(default=1.0)
    top_p: int = Field(default=1)
    n: int = Field(default=1)
    stop: Optional[Union[str, List]] = Field(default=None)
    presence_penalty: int = Field(default=0)
    frequency_penalty: int = Field(default=0)


class OpenAICompletionArgs(OpenAIChatArgs):
    model: str = Field(default="text-davinci-003")
    best_of: int = Field(default=1)


def _parse_merged_input(inp: str) -> list:
    """Parse a merged [System Instructions]/[User Request] string into chat messages."""
    if isinstance(inp, str) and "[System Instructions]" in inp and "[User Request]" in inp:
        sys_marker = "[System Instructions]"
        usr_marker = "[User Request]"
        sys_start = inp.find(sys_marker)
        usr_start = inp.find(usr_marker)
        system_part = inp[sys_start + len(sys_marker):usr_start].strip() if sys_start >= 0 and usr_start >= 0 else ""
        user_part = inp[usr_start + len(usr_marker):].strip() if usr_start >= 0 else str(inp)
        return [
            {"role": "system", "content": system_part},
            {"role": "user", "content": user_part},
        ]
    else:
        return [{"role": "user", "content": str(inp)}]


def _call_direct_api(prompt: str, inputs: list, max_tokens: int = 2048, model: str = "deepseek-v4-flash",
                     temperature: float = 0.2, api_key: str = "", batch_size: int = 10) -> list:
    """Call the DeepSeek chat API directly, batching multiple inputs per request.

    Each batch combines N inputs into one chat completion request using a numbered
    format. The LLM responds with numbered answers that we parse back.

    Args:
        prompt: Template (unused, kept for interface compat).
        inputs: List of input strings.
        max_tokens: Max tokens per individual response.
        model: Model name.
        temperature: Sampling temperature.
        api_key: API key override.
        batch_size: Number of inputs to merge per API call.
    """
    from openai import OpenAI

    key = api_key or _DIRECT_API_KEY
    if not key:
        logger.warning("No API key available for direct API call")
        return [None] * len(inputs)

    client = OpenAI(api_key=key, base_url=_DIRECT_API_BASE, timeout=120.0)
    results = [None] * len(inputs)

    # Process in batches
    for batch_start in range(0, len(inputs), batch_size):
        batch_end = min(batch_start + batch_size, len(inputs))
        batch = inputs[batch_start:batch_end]

        if len(batch) == 1:
            # Single input — simple call, no numbering needed
            messages = _parse_merged_input(batch[0])
            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(
                        model=model, messages=messages,
                        max_tokens=max_tokens, temperature=temperature,
                    )
                    results[batch_start] = resp.choices[0].message.content
                    break
                except Exception as e:
                    logger.info(f"Direct API error (attempt {attempt+1}/3): {e}")
                    if attempt < 2:
                        time.sleep(5)
        else:
            # Multiple inputs — combine into one numbered prompt
            combined_user_parts = []
            for i, inp in enumerate(batch):
                msgs = _parse_merged_input(inp)
                # Extract system vs user content
                sys_content = ""
                usr_content = ""
                for m in msgs:
                    if m["role"] == "system":
                        sys_content = m["content"]
                    else:
                        usr_content = m["content"]

                if sys_content:
                    combined_user_parts.append(
                        f"--- Task {i+1} ---\n[Context]: {sys_content}\n[Request]: {usr_content}"
                    )
                else:
                    combined_user_parts.append(f"--- Task {i+1} ---\n{usr_content}")

            system_msg = (
                "You are processing multiple independent tasks in one response. "
                "For each task, provide your answer prefixed with '=== Task N ===' "
                "where N is the task number. Complete ALL tasks.\n"
                f"Total tasks: {len(batch)}"
            )
            user_msg = "\n\n".join(combined_user_parts)

            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]
            # Scale max_tokens by batch size
            batch_max_tokens = max_tokens * len(batch)

            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(
                        model=model, messages=messages,
                        max_tokens=batch_max_tokens, temperature=temperature,
                    )
                    text = resp.choices[0].message.content
                    # Parse numbered responses
                    parsed = _parse_batch_response(text, len(batch))
                    for i, val in enumerate(parsed):
                        results[batch_start + i] = val
                    break
                except Exception as e:
                    logger.info(f"Direct API batch error (attempt {attempt+1}/3): {e}")
                    if attempt < 2:
                        time.sleep(5)

        # Small delay between batches to avoid rate limiting
        if batch_end < len(inputs):
            time.sleep(0.5)

    return results


def _parse_batch_response(text: str, expected_count: int) -> list:
    """Parse a batched LLM response back into individual results.

    Looks for '=== Task N ===' markers. Falls back to splitting by '--- Task N ---'
    or returning the whole text as the first result.
    """
    import re
    results = [None] * expected_count

    # Try === Task N === format
    pattern = r'===\s*Task\s+(\d+)\s*==='
    splits = re.split(pattern, text)

    if len(splits) > 1:
        # splits: [before, num1, content1, num2, content2, ...]
        for i in range(1, len(splits), 2):
            task_num = int(splits[i])
            content = splits[i + 1].strip() if i + 1 < len(splits) else ""
            if 1 <= task_num <= expected_count:
                results[task_num - 1] = content
    else:
        # Fallback: try --- Task N --- format
        pattern2 = r'---\s*Task\s+(\d+)\s*---'
        splits2 = re.split(pattern2, text)
        if len(splits2) > 1:
            for i in range(1, len(splits2), 2):
                task_num = int(splits2[i])
                content = splits2[i + 1].strip() if i + 1 < len(splits2) else ""
                if 1 <= task_num <= expected_count:
                    results[task_num - 1] = content
        else:
            # Last resort: whole text as first result
            results[0] = text.strip()

    return results


def _call_batch_api(prompt: str, inputs: list, max_tokens: int = 2048, timeout: int = 300):
    """Call the batch LLM API endpoint.

    Args:
        prompt: Template string with {input} placeholder.
        inputs: List of input strings to fill into the template.
        max_tokens: Maximum tokens for the response.
        timeout: Request timeout in seconds.
    Returns:
        List of response strings, one per input.
    """
    payload = {
        "prompt": prompt,
        "inputs": inputs,
        "max_tokens": max_tokens,
    }
    max_retries = 5
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                _batch_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # The API returns a list of strings
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "results" in data:
                return data["results"]
            elif isinstance(data, dict) and "outputs" in data:
                return data["outputs"]
            else:
                return data
        except requests.exceptions.RequestException as e:
            logger.info(f"Batch API error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == 0:
                # On first failure, fall back to direct API
                logger.info("Batch API unavailable, falling back to direct API calls")
                api_key = _get_available_api_key()
                return _call_direct_api(prompt, inputs, max_tokens, api_key=api_key)
            if attempt < max_retries - 1:
                time.sleep(20)
            else:
                logger.info(f"Max retries ({max_retries}) reached, returning empty responses")
                return [None] * len(inputs)
    return [None] * len(inputs)


def _get_available_api_key() -> str:
    """Try to find an available API key from global config or env."""
    if _DIRECT_API_KEY:
        return _DIRECT_API_KEY
    return ""


@llm_registry.register("text-davinci-003")
class OpenAICompletion(BaseCompletionModel):
    args: OpenAICompletionArgs = Field(default_factory=OpenAICompletionArgs)
    api_key_list: Any = []
    current_key_idx: int = 0

    def __init__(self, max_retry: int = 15, **kwargs):
        api_key_list = kwargs.pop('api_key_list', [])
        current_key_idx = kwargs.pop('current_key_idx', 0)
        args = OpenAICompletionArgs()
        args = args.model_dump()

        for k, v in args.items():
            args[k] = kwargs.pop(k, v)
        super().__init__(args=args, max_retry=max_retry)
        object.__setattr__(self, 'api_key_list', api_key_list)
        object.__setattr__(self, 'current_key_idx', current_key_idx)
        if api_key_list and not _DIRECT_API_KEY:
            globals()['_DIRECT_API_KEY'] = api_key_list[current_key_idx]

    def generate_response(self, prompt: str) -> LLMResult:
        results = _call_batch_api("{input}", [prompt], self.args.max_tokens)
        return LLMResult(
            content=results[0] if results[0] is not None else "",
        )

    async def agenerate_response(self, prompt: str) -> LLMResult:
        results = _call_batch_api("{input}", prompt, self.args.max_tokens)
        return results


@llm_registry.register("embedding")
class OpenAIEmbedding(BaseCompletionModel):
    args: OpenAICompletionArgs = Field(default_factory=OpenAICompletionArgs)
    api_key_list: Any = []
    current_key_idx: int = 0

    def __init__(self, max_retry: int = 3, **kwargs):
        api_key_list = kwargs.pop('api_key_list', [])
        current_key_idx = kwargs.pop('current_key_idx', 0)
        args = OpenAICompletionArgs()
        args = args.model_dump()
        for k, v in args.items():
            args[k] = kwargs.pop(k, v)
        super().__init__(args=args, max_retry=max_retry)
        object.__setattr__(self, 'api_key_list', api_key_list)
        object.__setattr__(self, 'current_key_idx', current_key_idx)

    def generate_response(self, prompt: str) -> LLMResult:
        import nomic
        from nomic import embed
        result = nomic.embed.text(model='nomic-embed-text-v1', texts=prompt)
        embeddings = result['embeddings']
        return LLMResult(
            content=embeddings[0],
        )

    def generate_response_batch(self, sentences: list) -> list:
        import nomic
        from nomic import embed
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = nomic.embed.text(model='nomic-embed-text-v1', texts=sentences)
                embeddings = result['embeddings']
                return [{"data": [{"embedding": emb}]} for emb in embeddings]
            except Exception as e:
                logger.info(e)
                if attempt < max_retries - 1:
                    logger.info(f"Retrying... (attempt {attempt+1}/{max_retries})")
                    time.sleep(20)
                else:
                    logger.info(f"Max retries ({max_retries}) reached, returning empty responses")
                    return [None] * len(sentences)

    async def agenerate_response(self, sentences: str) -> LLMResult:
        import nomic
        from nomic import embed
        while True:
            try:
                result = nomic.embed.text(model='nomic-embed-text-v1', texts=sentences)
                embeddings = result['embeddings']
                return [{"data": [{"embedding": emb}]} for emb in embeddings]
            except Exception as e:
                logger.info(e)
                logger.info("Retrying...")
                await asyncio.sleep(20)
                continue


@llm_registry.register("gpt-3.5-turbo-16k-0613")
@llm_registry.register("gpt-3.5-turbo")
@llm_registry.register("gpt-4")
@llm_registry.register("deepseek-v4-flash")
@llm_registry.register("deepseek-v4-pro")
class OpenAIChat(BaseChatModel):
    args: OpenAIChatArgs = Field(default_factory=OpenAIChatArgs)
    api_key_list: Any = []
    current_key_idx: int = 0

    def __init__(self, max_retry: int = 3, **kwargs):
        api_key_list = kwargs.pop('api_key_list', [])
        current_key_idx = kwargs.pop('current_key_idx', 0)
        args = OpenAIChatArgs()
        args = args.model_dump()

        for k, v in args.items():
            args[k] = kwargs.pop(k, v)
        super().__init__(args=args, max_retry=max_retry)
        object.__setattr__(self, 'api_key_list', api_key_list)
        object.__setattr__(self, 'current_key_idx', current_key_idx)
        # Store first API key in module-level var for direct API fallback
        if api_key_list and not _DIRECT_API_KEY:
            globals()['_DIRECT_API_KEY'] = api_key_list[current_key_idx]

    def _construct_messages(self, prompts: list):
        messages = []
        for prompt in prompts:
            messages.append([
                            {"role": "user", "content": prompt}])
        return messages

    def generate_response(self, prompt: str) -> LLMResult:
        results = _call_batch_api("{input}", [prompt], self.args.max_tokens)
        return LLMResult(
            content=results[0] if results[0] is not None else "",
        )

    def generate_response_batch(self, prompts: list) -> list:
        """Batch call using the /batch API.

        Each prompt is a raw string. They all share the same template pattern.
        The batch API applies the template to each input.
        """
        print(f"[batch] Sending {len(prompts)} prompts to batch API", flush=True)
        results = _call_batch_api("{input}", prompts, self.args.max_tokens)
        # Wrap each result in a mock response object for backward compatibility
        return [_MockResponse(text) for text in results]

    def generate_response_without_construction_batch(self, messages: list) -> list:
        """Batch call for pre-constructed [system_role, user_role] message pairs.

        Each element in messages is [system_role_dict, user_role_dict].
        Since system content varies per input (e.g. different user descriptions),
        we merge each message pair into a single input string with a clear
        system/user structure, and use "{input}" as the template.
        """
        merged_inputs = []
        for msg_pair in messages:
            if isinstance(msg_pair, list) and len(msg_pair) == 2 and isinstance(msg_pair[0], dict):
                system_content = msg_pair[0].get("content", "")
                user_content = msg_pair[1].get("content", "")
                merged = f"[System Instructions]\n{system_content}\n\n[User Request]\n{user_content}"
                merged_inputs.append(merged)
            else:
                merged_inputs.append(str(msg_pair))

        print(f"[batch] Sending {len(merged_inputs)} pre-constructed messages to batch API", flush=True)
        results = _call_batch_api("{input}", merged_inputs, self.args.max_tokens)
        return [_MockResponse(text) for text in results]

    async def _agenerate_response_batch(self, messages: list, semaphore_limit: int = 20) -> list:
        """Async wrapper that delegates to the sync batch API call."""
        # Determine if messages are pre-constructed pairs or raw prompts
        if messages and isinstance(messages[0], list) and len(messages[0]) == 2 and isinstance(messages[0][0], dict):
            return self.generate_response_without_construction_batch(messages)
        else:
            return self.generate_response_batch(messages)

    async def agenerate_response(self, prompt: str) -> LLMResult:
        if isinstance(prompt, list) and prompt and isinstance(prompt[0], list):
            return self.generate_response_without_construction_batch(prompt)
        results = _call_batch_api("{input}", prompt, self.args.max_tokens)
        return results

    async def agenerate_response_without_construction(self, messages: str) -> LLMResult:
        return self.generate_response_without_construction_batch(messages)


class _MockResponse:
    """Mock OpenAI response object for backward compatibility.

    The original code accesses response.choices[0].message.content
    or response["choices"][0]["message"]["content"].
    This mock provides both interfaces.
    """
    def __init__(self, text):
        self.choices = [_MockChoice(text)]

    def __getitem__(self, key):
        if key == "choices":
            return [{"message": {"content": self.choices[0].message.content}}]
        raise KeyError(key)

    def __contains__(self, key):
        return key == "choices"


class _MockChoice:
    def __init__(self, text):
        self.message = _MockMessage(text)


class _MockMessage:
    def __init__(self, text):
        self.content = text if text is not None else ""
