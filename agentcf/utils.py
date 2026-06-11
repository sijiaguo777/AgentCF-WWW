import importlib
import asyncio
import json
import time
import os
import torch
import random
import numpy as np
import pandas as pd
import requests
from recbole.utils import get_model as recbole_get_model
from collections import defaultdict
from tqdm import tqdm
true=True
false=False

_batch_host = os.environ.get("BATCH_API_HOST", "http://localhost:8888")
_batch_url = f"{_batch_host}/batch"
_DIRECT_API_BASE = os.environ.get("DIRECT_API_BASE", "https://api.deepseek.com")
_DIRECT_API_KEY = os.environ.get("DIRECT_API_KEY", "")


def _parse_merged_input(inp):
    """Parse merged [system]/[user] format into chat messages."""
    if isinstance(inp, str) and "[system]" in inp and "[user]" in inp:
        sys_start = inp.find("[system]")
        usr_start = inp.find("[user]")
        system_part = inp[sys_start + 8:usr_start].strip() if sys_start >= 0 and usr_start >= 0 else ""
        user_part = inp[usr_start + 6:].strip() if usr_start >= 0 else str(inp)
        return [{"role": "system", "content": system_part}, {"role": "user", "content": user_part}]
    return [{"role": "user", "content": str(inp)}]


def _parse_batch_response(text, expected_count):
    """Parse batched LLM response with === Task N === markers."""
    import re
    results = [None] * expected_count
    pattern = r'===\s*Task\s+(\d+)\s*==='
    splits = re.split(pattern, text)
    if len(splits) > 1:
        for i in range(1, len(splits), 2):
            task_num = int(splits[i])
            content = splits[i + 1].strip() if i + 1 < len(splits) else ""
            if 1 <= task_num <= expected_count:
                results[task_num - 1] = content
    else:
        results[0] = text.strip()
    return results


def _call_direct_api(prompt, inputs, max_tokens=2048, api_key="", batch_size=10):
    """Fallback: call DeepSeek chat API with batched prompts."""
    from openai import OpenAI
    key = api_key or _DIRECT_API_KEY
    if not key:
        return [None] * len(inputs)
    client = OpenAI(api_key=key, base_url=_DIRECT_API_BASE, timeout=120.0)
    results = [None] * len(inputs)

    for batch_start in range(0, len(inputs), batch_size):
        batch_end = min(batch_start + batch_size, len(inputs))
        batch = inputs[batch_start:batch_end]

        if len(batch) == 1:
            messages = _parse_merged_input(batch[0])
            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(model="deepseek-v4-flash", messages=messages, max_tokens=max_tokens, temperature=0.2)
                    results[batch_start] = resp.choices[0].message.content
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(5)
        else:
            combined = []
            for i, inp in enumerate(batch):
                msgs = _parse_merged_input(inp)
                sys_c = usr_c = ""
                for m in msgs:
                    if m["role"] == "system":
                        sys_c = m["content"]
                    else:
                        usr_c = m["content"]
                if sys_c:
                    combined.append(f"--- Task {i+1} ---\n[Context]: {sys_c}\n[Request]: {usr_c}")
                else:
                    combined.append(f"--- Task {i+1} ---\n{usr_c}")

            system_msg = "You are processing multiple independent tasks. For each task, answer prefixed with '=== Task N ==='. Complete ALL tasks.\nTotal tasks: " + str(len(batch))
            user_msg = "\n\n".join(combined)
            messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(model="deepseek-v4-flash", messages=messages, max_tokens=max_tokens * len(batch), temperature=0.2)
                    parsed = _parse_batch_response(resp.choices[0].message.content, len(batch))
                    for i, val in enumerate(parsed):
                        results[batch_start + i] = val
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(5)

        if batch_end < len(inputs):
            time.sleep(0.5)

    return results


def _call_batch_api(prompt: str, inputs: list, max_tokens: int = 2048, timeout: int = 300):
    """Call the batch LLM API endpoint. Falls back to direct API on failure."""
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
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "results" in data:
                return data["results"]
            elif isinstance(data, dict) and "outputs" in data:
                return data["outputs"]
            else:
                return data
        except requests.exceptions.RequestException as e:
            if attempt == 0:
                # Fall back to direct API on first failure
                return _call_direct_api(prompt, inputs, max_tokens)
            if attempt < max_retries - 1:
                time.sleep(20)
            else:
                return [None] * len(inputs)
    return [None] * len(inputs)

def check_path(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_model(model_name):
    if importlib.util.find_spec(f'model.{model_name.lower()}', __name__):
        model_module = importlib.import_module(f'model.{model_name.lower()}', __name__)
        model_class = getattr(model_module, model_name)
        return model_class
    else:
        return recbole_get_model(model_name)


async def dispatch_openai_requests(
    messages_list,
    model: str,
    temperature: float
):
    """Dispatches requests to batch LLM API.

    Args:
        messages_list: List of messages (each is a list of dicts with role/content).
        model: Model name (unused, kept for API compat).
        temperature: Temperature (unused, kept for API compat).
    Returns:
        List of response objects with .choices[0].message.content interface.
    """
    merged_inputs = []
    for msg in messages_list:
        if isinstance(msg, list) and msg and isinstance(msg[0], dict):
            parts = []
            for m in msg:
                role = m.get("role", "user")
                content = m.get("content", "")
                parts.append(f"[{role}]\n{content}")
            merged_inputs.append("\n\n".join(parts))
        else:
            merged_inputs.append(str(msg))

    results = _call_batch_api("{input}", merged_inputs)

    class _MockMsg:
        def __init__(self, t): self.content = t if t is not None else ""
    class _MockChoice:
        def __init__(self, t): self.message = _MockMsg(t)
    class _MockResp:
        def __init__(self, t): self.choices = [_MockChoice(t)]

    return [_MockResp(r) for r in results]


def dispatch_single_openai_requests(
    message,
    model: str,
    temperature: float
):
    """Dispatches a single request to batch LLM API.

    Args:
        message: Messages to be sent (list of dicts with role/content).
        model: Model name (unused, kept for API compat).
        temperature: Temperature (unused, kept for API compat).
    Returns:
        Response object with .choices[0].message.content interface.
    """
    if isinstance(message, list) and message and isinstance(message[0], dict):
        parts = []
        for m in message:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"[{role}]\n{content}")
        merged = "\n\n".join(parts)
    else:
        merged = str(message)

    results = _call_batch_api("{input}", [merged])

    class _MockMsg:
        def __init__(self, t): self.content = t if t is not None else ""
    class _MockChoice:
        def __init__(self, t): self.message = _MockMsg(t)
    class _MockResp:
        def __init__(self, t): self.choices = [_MockChoice(t)]

    return _MockResp(results[0])


amazon_dataset2fullname = {
    'Beauty': 'All_Beauty',
    'Fashion': 'AMAZON_FASHION',
    'Appliances': 'Appliances',
    'Arts': 'Arts_Crafts_and_Sewing',
    'Automotive': 'Automotive',
    'Books': 'Books',
    'CDs': 'CDs_and_Vinyl',
    'Cell': 'Cell_Phones_and_Accessories',
    'Clothing': 'Clothing_Shoes_and_Jewelry',
    'Music': 'Digital_Music',
    'Electronics': 'Electronics',
    'Gift': 'Gift_Cards',
    'Food': 'Grocery_and_Gourmet_Food',
    'Home': 'Home_and_Kitchen',
    'Scientific': 'Industrial_and_Scientific',
    'Kindle': 'Kindle_Store',
    'Luxury': 'Luxury_Beauty',
    'Magazine': 'Magazine_Subscriptions',
    'Movies': 'Movies_and_TV',
    'Instruments': 'Musical_Instruments',
    'Office': 'Office_Products',
    'Garden': 'Patio_Lawn_and_Garden',
    'Pantry': 'Prime_Pantry',
    'Pet': 'Pet_Supplies',
    'Software': 'Software',
    'Sports': 'Sports_and_Outdoors',
    'Tools': 'Tools_and_Home_Improvement',
    'Toys': 'Toys_and_Games',
    'Games': 'Video_Games'
}