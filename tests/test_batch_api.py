"""Tests for the batch API conversion.

Located outside agentcf/ to avoid triggering the heavy agentcf/__init__.py
import chain. The pytest.ini adds agentcf/ to pythonpath so that the
`agentverse` absolute imports used inside the llms package resolve correctly.

For utils.py, we use importlib to load it directly since `from agentcf.utils`
would trigger agentcf/__init__.py which requires recbole.
"""

import os
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock

from agentverse.llms.openai import (
    _call_batch_api,
    OpenAIChat,
    OpenAICompletion,
    _MockResponse,
)

# Mock recbole before loading utils.py (which imports it at module level)
if "recbole" not in sys.modules:
    recbole_mock = MagicMock()
    recbole_utils_mock = MagicMock()
    sys.modules["recbole"] = recbole_mock
    sys.modules["recbole.utils"] = recbole_utils_mock

# Load agentcf.utils directly via importlib to bypass agentcf/__init__.py
_utils_spec = importlib.util.spec_from_file_location(
    "agentcf.utils",
    os.path.join(os.path.dirname(__file__), "..", "agentcf", "utils.py"),
)
_utils_mod = importlib.util.module_from_spec(_utils_spec)
sys.modules["agentcf.utils"] = _utils_mod
_utils_spec.loader.exec_module(_utils_mod)

dispatch_openai_requests = _utils_mod.dispatch_openai_requests
dispatch_single_openai_requests = _utils_mod.dispatch_single_openai_requests

# Patch target for openai module
_OPENAI_MODULE = "agentverse.llms.openai"
# For utils, we patch the module object directly since agentcf/__init__.py
# triggers recbole imports that may not be installed.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_batch_response(results, status_code=200):
    """Build a mock requests.Response for the /batch endpoint."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = results
    if status_code >= 400:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(f"{status_code} error")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ===========================================================================
# 1. _call_batch_api
# ===========================================================================

class TestCallBatchApi:

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_basic_list_response(self, mock_post):
        mock_post.return_value = _make_batch_response(["hello", "world"])

        result = _call_batch_api("{input}", ["hi", "there"], 1024)

        assert result == ["hello", "world"]
        sent_payload = mock_post.call_args[1]["json"]
        assert sent_payload == {"prompt": "{input}", "inputs": ["hi", "there"], "max_tokens": 1024}

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_dict_results_key(self, mock_post):
        mock_post.return_value = _make_batch_response({"results": ["a", "b"]})

        result = _call_batch_api("{input}", ["x", "y"])
        assert result == ["a", "b"]

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_dict_outputs_key(self, mock_post):
        mock_post.return_value = _make_batch_response({"outputs": ["c", "d"]})

        result = _call_batch_api("{input}", ["x", "y"])
        assert result == ["c", "d"]

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_dict_fallback_passthrough(self, mock_post):
        mock_post.return_value = _make_batch_response({"data": ["e"]})

        result = _call_batch_api("{input}", ["x"])
        assert result == {"data": ["e"]}

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_retry_on_error_then_success(self, mock_post):
        from requests.exceptions import ConnectionError

        mock_post.side_effect = [
            ConnectionError("down"),
            _make_batch_response(["ok"]),
        ]

        result = _call_batch_api("{input}", ["test"])
        assert result == ["ok"]
        assert mock_post.call_count == 2

    @patch(f"{_OPENAI_MODULE}.time.sleep", return_value=None)
    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_all_retries_fail_returns_none_list(self, mock_post, mock_sleep):
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("down")

        result = _call_batch_api("{input}", ["a", "b", "c"])
        assert result == [None, None, None]
        assert mock_post.call_count == 5

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_http_error_retries(self, mock_post):
        mock_post.return_value = _make_batch_response({}, status_code=500)

        result = _call_batch_api("{input}", ["x"])
        assert result == [None]

    @patch(f"{_OPENAI_MODULE}.requests.post")
    def test_timeout_passed_to_requests(self, mock_post):
        mock_post.return_value = _make_batch_response(["ok"])

        _call_batch_api("{input}", ["x"], max_tokens=512, timeout=60)
        assert mock_post.call_args[1]["timeout"] == 60


# ===========================================================================
# 2. _MockResponse
# ===========================================================================

class TestMockResponse:

    def test_attribute_access(self):
        resp = _MockResponse("hello world")
        assert resp.choices[0].message.content == "hello world"

    def test_dict_access(self):
        resp = _MockResponse("hello world")
        assert resp["choices"][0]["message"]["content"] == "hello world"

    def test_attribute_and_dict_match(self):
        resp = _MockResponse("consistent")
        assert resp.choices[0].message.content == resp["choices"][0]["message"]["content"]

    def test_contains_choices(self):
        resp = _MockResponse("x")
        assert "choices" in resp

    def test_contains_other_key_fails(self):
        resp = _MockResponse("x")
        assert "data" not in resp

    def test_getitem_unknown_key_raises(self):
        resp = _MockResponse("x")
        with pytest.raises(KeyError):
            _ = resp["data"]

    def test_none_content_becomes_empty_string(self):
        resp = _MockResponse(None)
        assert resp.choices[0].message.content == ""


# ===========================================================================
# 3. OpenAIChat
# ===========================================================================

class TestOpenAIChat:

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_generate_response_single(self, mock_batch):
        mock_batch.return_value = ["response text"]

        chat = OpenAIChat()
        result = chat.generate_response("test prompt")

        assert result.content == "response text"
        mock_batch.assert_called_once_with("{input}", ["test prompt"], 2048)

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_generate_response_none_fallback(self, mock_batch):
        mock_batch.return_value = [None]

        chat = OpenAIChat()
        result = chat.generate_response("test prompt")

        assert result.content == ""

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_generate_response_batch(self, mock_batch):
        mock_batch.return_value = ["resp1", "resp2", "resp3"]

        chat = OpenAIChat()
        results = chat.generate_response_batch(["p1", "p2", "p3"])

        assert len(results) == 3
        assert results[0].choices[0].message.content == "resp1"
        assert results[1].choices[0].message.content == "resp2"
        assert results[2].choices[0].message.content == "resp3"
        mock_batch.assert_called_once_with("{input}", ["p1", "p2", "p3"], 2048)

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_generate_response_batch_none_entries(self, mock_batch):
        mock_batch.return_value = ["ok", None, "also ok"]

        chat = OpenAIChat()
        results = chat.generate_response_batch(["a", "b", "c"])

        assert results[0].choices[0].message.content == "ok"
        assert results[1].choices[0].message.content == ""
        assert results[2].choices[0].message.content == "also ok"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_generate_response_without_construction_batch(self, mock_batch):
        mock_batch.return_value = ["user chose CD 1", "user chose CD 2"]

        messages = [
            [
                {"role": "system", "content": "You are user Alice who likes jazz."},
                {"role": "user", "content": "Which CD do you prefer? 1. Rock 2. Jazz"},
            ],
            [
                {"role": "system", "content": "You are user Bob who likes pop."},
                {"role": "user", "content": "Which CD do you prefer? 1. Pop 2. Classical"},
            ],
        ]

        chat = OpenAIChat()
        results = chat.generate_response_without_construction_batch(messages)

        assert len(results) == 2
        assert results[0].choices[0].message.content == "user chose CD 1"
        assert results[1].choices[0].message.content == "user chose CD 2"

        merged_inputs = mock_batch.call_args[0][1]
        assert "[System Instructions]" in merged_inputs[0]
        assert "You are user Alice who likes jazz." in merged_inputs[0]
        assert "[User Request]" in merged_inputs[0]
        assert "Which CD do you prefer? 1. Rock 2. Jazz" in merged_inputs[0]
        assert "You are user Bob who likes pop." in merged_inputs[1]

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_without_construction_batch_non_pair_input(self, mock_batch):
        mock_batch.return_value = ["result"]

        chat = OpenAIChat()
        results = chat.generate_response_without_construction_batch(["just a string"])

        assert len(results) == 1
        assert results[0].choices[0].message.content == "result"
        merged_inputs = mock_batch.call_args[0][1]
        assert merged_inputs[0] == "just a string"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    async def test_agenerate_response_batch_delegates(self, mock_batch):
        mock_batch.return_value = ["a", "b"]

        chat = OpenAIChat()
        results = await chat._agenerate_response_batch(["p1", "p2"])

        assert len(results) == 2
        assert results[0].choices[0].message.content == "a"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    async def test_agenerate_response_batch_message_pairs(self, mock_batch):
        mock_batch.return_value = ["result"]

        messages = [[{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]]
        chat = OpenAIChat()
        results = await chat._agenerate_response_batch(messages)

        assert len(results) == 1
        assert results[0].choices[0].message.content == "result"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    async def test_agenerate_response_string(self, mock_batch):
        mock_batch.return_value = ["single response"]

        chat = OpenAIChat()
        result = await chat.agenerate_response("hello")

        assert result == ["single response"]

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    async def test_agenerate_response_message_pairs(self, mock_batch):
        mock_batch.return_value = ["merged response"]

        msg_pairs = [[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]]
        chat = OpenAIChat()
        results = await chat.agenerate_response(msg_pairs)

        assert len(results) == 1
        assert results[0].choices[0].message.content == "merged response"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    async def test_agenerate_response_without_construction(self, mock_batch):
        mock_batch.return_value = ["wc result"]

        messages = [[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]]
        chat = OpenAIChat()
        results = await chat.agenerate_response_without_construction(messages)

        assert len(results) == 1
        assert results[0].choices[0].message.content == "wc result"


# ===========================================================================
# 4. OpenAICompletion
# ===========================================================================

class TestOpenAICompletion:

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_generate_response(self, mock_batch):
        mock_batch.return_value = ["completed text"]

        comp = OpenAICompletion()
        result = comp.generate_response("test")

        assert result.content == "completed text"
        mock_batch.assert_called_once_with("{input}", ["test"], 2048)


# ===========================================================================
# 5. utils.dispatch functions
# ===========================================================================

class TestDispatchUtils:

    async def test_dispatch_openai_requests_string_prompts(self):
        with patch.object(_utils_mod, "_call_batch_api", return_value=["r1", "r2"]) as mock_batch:
            results = await dispatch_openai_requests(["prompt a", "prompt b"], "gpt-4", 1.0)

            assert len(results) == 2
            assert results[0].choices[0].message.content == "r1"
            assert results[1].choices[0].message.content == "r2"

    async def test_dispatch_openai_requests_message_pairs(self):
        with patch.object(_utils_mod, "_call_batch_api", return_value=["merged"]) as mock_batch:
            messages = [[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ]]
            results = await dispatch_openai_requests(messages, "gpt-4", 1.0)

            assert len(results) == 1
            assert results[0].choices[0].message.content == "merged"

            merged = mock_batch.call_args[0][1][0]
            assert "[system]" in merged
            assert "[user]" in merged

    def test_dispatch_single_openai_requests_string(self):
        with patch.object(_utils_mod, "_call_batch_api", return_value=["single"]) as mock_batch:
            result = dispatch_single_openai_requests("test prompt", "gpt-4", 1.0)

            assert result.choices[0].message.content == "single"

    def test_dispatch_single_openai_requests_message_pair(self):
        with patch.object(_utils_mod, "_call_batch_api", return_value=["merged single"]) as mock_batch:
            msg = [
                {"role": "system", "content": "sys prompt"},
                {"role": "user", "content": "user prompt"},
            ]
            result = dispatch_single_openai_requests(msg, "gpt-4", 1.0)

            assert result.choices[0].message.content == "merged single"


# ===========================================================================
# 6. End-to-end: agentcf.py call patterns
# ===========================================================================

class TestAgentCFIntegration:

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_forward_pattern(self, mock_batch):
        """forward: generate_response_batch -> .choices[0].message.content"""
        mock_batch.return_value = [
            "Recommendation: CD 1\nReasoning: The user likes rock music.",
            "Recommendation: CD 2\nReasoning: The user prefers classical.",
        ]

        chat = OpenAIChat()
        prompts = [
            "User likes rock. Which CD? 1. Rock CD 2. Jazz CD",
            "User likes classical. Which CD? 1. Rock CD 2. Classical CD",
        ]
        responses = chat.generate_response_batch(prompts)

        for i, resp in enumerate(responses):
            assert resp.choices[0].message.content == mock_batch.return_value[i]

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_user_backward_pattern(self, mock_batch):
        """user backward: generate_response_without_construction_batch -> .choices[0].message.content"""
        mock_batch.return_value = [
            "I choose CD 1 because I enjoy upbeat music.",
            "I choose CD 2 because I prefer calm melodies.",
        ]

        chat = OpenAIChat()
        messages = [
            [
                {"role": "system", "content": "You are user 42. You like electronic and pop music."},
                {"role": "user", "content": "Which CD do you prefer?\n1. Jazz CD\n2. Pop CD"},
            ],
            [
                {"role": "system", "content": "You are user 7. You like classical and opera."},
                {"role": "user", "content": "Which CD do you prefer?\n1. Classical CD\n2. Rock CD"},
            ],
        ]
        responses = chat.generate_response_without_construction_batch(messages)

        assert responses[0].choices[0].message.content == "I choose CD 1 because I enjoy upbeat music."
        assert responses[1].choices[0].message.content == "I choose CD 2 because I prefer calm melodies."

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_item_backward_pattern(self, mock_batch):
        """item backward: generate_response_batch -> .choices[0].message.content"""
        mock_batch.return_value = [
            "This CD appeals to users who enjoy energetic rock with guitar solos.",
        ]

        chat = OpenAIChat()
        prompts = ["Describe your appeal: Rock CD with guitar solos."]
        responses = chat.generate_response_batch(prompts)

        assert responses[0].choices[0].message.content == mock_batch.return_value[0]

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_evaluation_pattern(self, mock_batch):
        """evaluation: generate_response_without_construction_batch -> .choices[0].message.content"""
        mock_batch.return_value = ["1. Jazz CD\n2. Rock CD\n3. Pop CD"]

        chat = OpenAIChat()
        messages = [
            [
                {"role": "system", "content": "You are a recommender system. Reorder CDs by user preference."},
                {"role": "user", "content": "User likes jazz. Reorder: 1. Pop 2. Jazz 3. Rock"},
            ],
        ]
        responses = chat.generate_response_without_construction_batch(messages)

        assert responses[0].choices[0].message.content == "1. Jazz CD\n2. Rock CD\n3. Pop CD"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_dict_access_pattern_from_old_model(self, mock_batch):
        """agentcf_old.py uses response["choices"][0]["message"]["content"]."""
        mock_batch.return_value = ["parsed content here"]

        chat = OpenAIChat()
        responses = chat.generate_response_batch(["test"])

        assert responses[0]["choices"][0]["message"]["content"] == "parsed content here"
        assert responses[0].choices[0].message.content == "parsed content here"

    @patch(f"{_OPENAI_MODULE}._call_batch_api")
    def test_empty_batch(self, mock_batch):
        mock_batch.return_value = []

        chat = OpenAIChat()
        results = chat.generate_response_batch([])

        assert results == []


# ===========================================================================
# 7. Misc: batch host config, method existence checks
# ===========================================================================

class TestMisc:

    def test_embedding_has_generate_response(self):
        import inspect
        sig = inspect.signature(OpenAICompletion.generate_response)
        assert "prompt" in sig.parameters

    def test_chat_has_batch_methods(self):
        assert hasattr(OpenAIChat, "generate_response_batch")
        assert hasattr(OpenAIChat, "generate_response_without_construction_batch")

    def test_default_batch_host(self):
        import agentverse.llms.openai as mod
        assert mod._batch_host == os.environ.get("BATCH_API_HOST", "http://localhost:8888")
        assert "/batch" in mod._batch_url

    def test_utils_default_batch_host(self):
        assert _utils_mod._batch_host == os.environ.get("BATCH_API_HOST", "http://localhost:8888")
        assert "/batch" in _utils_mod._batch_url