import os
import unittest
from unittest.mock import patch, MagicMock
from llm import (
    get_llm_provider,
    OpenRouterProvider,
    GeminiProvider,
    GroqProvider,
    OllamaProvider,
    LLMConfigurationError,
    LLMProviderError
)


class TestLLMProviders(unittest.TestCase):

    def test_missing_api_key_raises_config_error(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                OpenRouterProvider()

        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                GeminiProvider()

        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                GroqProvider()

    def test_unsupported_provider_raises_config_error(self):
        with self.assertRaises(LLMConfigurationError):
            get_llm_provider(provider_name="unknown_provider")

    @patch("requests.post")
    def test_openrouter_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter review result"}}]
        }
        mock_post.return_value = mock_response

        provider = OpenRouterProvider(api_key="valid_test_key")
        result = provider.generate_review("test prompt", "system instructions")
        self.assertEqual(result, "OpenRouter review result")
        self.assertEqual(provider.provider_name, "OpenRouter")

    @patch("requests.post")
    def test_groq_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Groq review result"}}]
        }
        mock_post.return_value = mock_response

        provider = GroqProvider(api_key="valid_test_key")
        result = provider.generate_review("test prompt", "system instructions")
        self.assertEqual(result, "Groq review result")
        self.assertEqual(provider.provider_name, "Groq")

    @patch("requests.post")
    def test_ollama_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Ollama review result"}
        }
        mock_post.return_value = mock_response

        provider = OllamaProvider(base_url="http://localhost:11434")
        result = provider.generate_review("test prompt", "system instructions")
        self.assertEqual(result, "Ollama review result")
        self.assertEqual(provider.provider_name, "Ollama (Local)")

    @patch("requests.post")
    def test_gemini_rest_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini review result"}]
                }
            }]
        }
        mock_post.return_value = mock_response

        provider = GeminiProvider(api_key="valid_test_key")
        result = provider._generate_rest("test prompt", "system instructions")
        self.assertEqual(result, "Gemini review result")
        self.assertEqual(provider.provider_name, "Google Gemini")


if __name__ == "__main__":
    unittest.main()
