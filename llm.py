"""
llm.py - Modular LLM Router and Multi-Provider Client

Supports:
- OpenRouter (REST API)
- Google Gemini (google-generativeai SDK & REST fallback)
- Groq (REST API)
- Ollama (Local REST API)
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class LLMError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when an LLM provider is misconfigured or missing credentials."""
    pass


class LLMProviderError(LLMError):
    """Raised when an LLM API request fails during runtime."""
    pass


class BaseLLMProvider(ABC):
    """Abstract Base Class for all LLM providers."""

    def __init__(self, model: Optional[str] = None, timeout: int = 60):
        self.timeout = int(os.getenv("REQUEST_TIMEOUT", str(timeout)))
        self.model = model or self.get_default_model()

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the user-friendly name of the provider."""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Return the default model name for this provider."""
        pass

    @abstractmethod
    def generate_review(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send the review prompt to the LLM and return the generated text.

        :param prompt: User prompt containing the git diff and context.
        :param system_prompt: Optional system prompt instructing the reviewer persona.
        :return: Generated review markdown string.
        """
        pass


class OpenRouterProvider(BaseLLMProvider):
    """LLM Provider for OpenRouter (https://openrouter.ai)."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key or self.api_key.startswith("your_"):
            raise LLMConfigurationError(
                "OPENROUTER_API_KEY is missing or invalid. "
                "Please set OPENROUTER_API_KEY in your .env file or environment."
            )
        super().__init__(model=model)

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    def get_default_model(self) -> str:
        return "anthropic/claude-3.5-sonnet"

    def generate_review(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/git-diff-reviewer",
            "X-Title": "Git Diff Reviewer",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                self.ENDPOINT,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMProviderError(f"OpenRouter returned empty choices: {data}")
            return choices[0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            error_detail = response.text
            try:
                err_json = response.json()
                if "error" in err_json:
                    error_detail = err_json["error"].get("message", response.text)
            except Exception:
                pass
            raise LLMProviderError(f"OpenRouter HTTP Error ({response.status_code}): {error_detail}") from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"OpenRouter Network Request Failed: {str(e)}") from e


class GeminiProvider(BaseLLMProvider):
    """LLM Provider for Google Gemini."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key or self.api_key.startswith("your_"):
            raise LLMConfigurationError(
                "GEMINI_API_KEY is missing or invalid. "
                "Please set GEMINI_API_KEY in your .env file or environment."
            )
        super().__init__(model=model)

    @property
    def provider_name(self) -> str:
        return "Google Gemini"

    def get_default_model(self) -> str:
        return "gemini-2.0-flash"

    def generate_review(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Try SDK first if available
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)

            # Model configurations
            system_instruction = system_prompt if system_prompt else None
            model_instance = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_instruction
            )
            response = model_instance.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            if response.text:
                return response.text
            raise LLMProviderError("Gemini SDK returned an empty response.")
        except ImportError:
            # Fallback to direct REST API if google-generativeai is not installed
            return self._generate_rest(prompt, system_prompt)
        except Exception as e:
            # If SDK throws unexpected error, try REST fallback
            try:
                return self._generate_rest(prompt, system_prompt)
            except Exception:
                raise LLMProviderError(f"Gemini API Error: {str(e)}") from e

    def _generate_rest(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System Instruction:\n{system_prompt}\n\nTask:\n{prompt}"}]
            })
        else:
            contents.append({
                "role": "user",
                "parts": [{"text": prompt}]
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2
            }
        }

        try:
            response = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMProviderError(f"Gemini REST returned no candidates: {data}")
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
            raise LLMProviderError(f"Gemini REST response contained no text parts: {data}")
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"Gemini REST Request Failed: {str(e)}") from e


class GroqProvider(BaseLLMProvider):
    """LLM Provider for Groq (https://groq.com)."""

    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key or self.api_key.startswith("your_"):
            raise LLMConfigurationError(
                "GROQ_API_KEY is missing or invalid. "
                "Please set GROQ_API_KEY in your .env file or environment."
            )
        super().__init__(model=model)

    @property
    def provider_name(self) -> str:
        return "Groq"

    def get_default_model(self) -> str:
        return "llama-3.3-70b-versatile"

    def generate_review(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                self.ENDPOINT,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMProviderError(f"Groq returned empty choices: {data}")
            return choices[0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            error_detail = response.text
            try:
                err_json = response.json()
                if "error" in err_json:
                    error_detail = err_json["error"].get("message", response.text)
            except Exception:
                pass
            raise LLMProviderError(f"Groq HTTP Error ({response.status_code}): {error_detail}") from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"Groq Network Request Failed: {str(e)}") from e


class OllamaProvider(BaseLLMProvider):
    """LLM Provider for local Ollama instances."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        super().__init__(model=model)

    @property
    def provider_name(self) -> str:
        return "Ollama (Local)"

    def get_default_model(self) -> str:
        return "llama3"

    def generate_review(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        chat_endpoint = f"{self.base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        }

        try:
            response = requests.post(
                chat_endpoint,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"]
            if "response" in data:
                return data["response"]
            raise LLMProviderError(f"Ollama returned unexpected payload: {data}")
        except requests.exceptions.ConnectionError as e:
            raise LLMProviderError(
                f"Could not connect to Ollama at '{self.base_url}'. "
                "Ensure that Ollama is installed and running (`ollama serve`)."
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMProviderError(
                f"Ollama HTTP Error ({response.status_code}): {response.text}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"Ollama Request Failed: {str(e)}") from e


# Registered Provider Mapping
PROVIDERS: Dict[str, type] = {
    "openrouter": OpenRouterProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
}


def get_llm_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseLLMProvider:
    """
    Factory function to instantiate an LLM provider based on name and environment.

    :param provider_name: Target provider ('openrouter', 'gemini', 'groq', 'ollama').
                          Defaults to LLM_PROVIDER from env or 'openrouter'.
    :param model_name: Optional model override. Defaults to LLM_MODEL from env.
    :return: An initialized BaseLLMProvider instance.
    """
    selected_provider = (
        provider_name or os.getenv("LLM_PROVIDER", "openrouter")
    ).strip().lower()

    selected_model = (
        model_name or os.getenv("LLM_MODEL", "")
    ).strip() or None

    if selected_provider not in PROVIDERS:
        supported = ", ".join(PROVIDERS.keys())
        raise LLMConfigurationError(
            f"Unsupported LLM_PROVIDER: '{selected_provider}'. Supported providers: {supported}"
        )

    provider_cls = PROVIDERS[selected_provider]
    return provider_cls(model=selected_model)
