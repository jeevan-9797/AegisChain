"""AegisChain Swappable LLM Client.

Provides a modular Adapter Pattern connecting local AI proxies (Google AI Studio)
and enterprise SAP Generative AI Hub foundation models without altering downstream contracts.
Part of the AegisChain SAP Hackfest 2026 intelligence suite.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv

# Automatically load environment variables from repository root .env or CWD
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_root_dotenv = os.path.join(_REPO_ROOT, ".env")
if os.path.exists(_root_dotenv):
    load_dotenv(_root_dotenv)
else:
    load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger("aegischain.llm_client")

# Production default model: fast, responsive, and quota-friendly
DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
FALLBACK_CANDIDATE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]


class SwappableLLMClient:
    """Unified LLM client adapter supporting Google AI Studio proxy and SAP Generative AI Hub.

    Supported Providers:
      - 'google': Uses Google AI Studio via `google-genai` SDK with auto-resolving flash models.
      - 'sap_hub': Enterprise SAP AI Core / Generative AI Hub proxy (ready skeleton).
    """

    SUPPORTED_PROVIDERS = ("google", "sap_hub")

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """Initialize the swappable LLM client.

        Args:
            provider: 'google' or 'sap_hub'. Defaults to LLM_PROVIDER env var or 'google'.
            api_key: Optional API key override. Defaults to GEMINI_API_KEY env var.
            model_name: Target foundation model identifier (default: GEMINI_MODEL env var or 'gemini-flash-lite-latest').
        """
        env_provider = os.getenv("LLM_PROVIDER", "google").lower().strip()
        self.provider = (provider or env_provider).lower().strip()

        if self.provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported LLM provider '{self.provider}'. "
                f"Must be one of: {self.SUPPORTED_PROVIDERS}"
            )

        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()

        env_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
        self.model_name = model_name or env_model

        logger.info(
            "SwappableLLMClient initialized with provider='%s', model='%s'. Key configured: %s",
            self.provider,
            self.model_name,
            bool(self.api_key),
        )

    def generate_structured_json(
        self, prompt: str, system_instruction: str = ""
    ) -> Dict[str, Any]:
        """Generate structured JSON output from the configured LLM provider.

        Args:
            prompt: User/task prompt for the model.
            system_instruction: Guiding system persona and instructions.

        Returns:
            Parsed JSON dictionary conforming to the requested schema.

        Raises:
            ValueError: If credentials are missing or response cannot be parsed as JSON.
            NotImplementedError: If provider is 'sap_hub' and credentials are not yet wired.
            Exception: On network, rate limit, or model invocation failures.
        """
        if self.provider == "google":
            return self._call_google_genai(prompt, system_instruction)
        elif self.provider == "sap_hub":
            return self._call_sap_genai_hub(prompt, system_instruction)
        else:
            raise ValueError(f"Unhandled provider: {self.provider}")

    def _call_google_genai(
        self, prompt: str, system_instruction: str = ""
    ) -> Dict[str, Any]:
        """Execute structured JSON inference using google-genai SDK with model resiliency."""
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Please add GEMINI_API_KEY to your local .env file."
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImportError(
                "The 'google-genai' package is required for Google AI Studio proxy. "
                "Install it via: pip install google-genai"
            ) from exc

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=system_instruction if system_instruction else None,
            temperature=0.1,
        )

        # Assemble prioritized model candidates for high availability
        candidate_models: List[str] = [self.model_name]
        for fallback in FALLBACK_CANDIDATE_MODELS:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_exception: Optional[Exception] = None

        for model_to_attempt in candidate_models:
            try:
                logger.debug(
                    "Dispatching prompt to %s with structured JSON config...",
                    model_to_attempt,
                )
                response = client.models.generate_content(
                    model=model_to_attempt,
                    contents=prompt,
                    config=config,
                )
                raw_text = response.text or ""
                return self._clean_and_parse_json(raw_text)

            except Exception as exc:
                err_str = str(exc)
                # Catch 404 (model retired/deprecated) or 503 (temporary capacity spike)
                is_recoverable_model_error = any(
                    code in err_str for code in ["404", "NOT_FOUND", "503", "UNAVAILABLE", "no longer available"]
                )
                if is_recoverable_model_error and model_to_attempt != candidate_models[-1]:
                    logger.warning(
                        "Model '%s' failed (%s). Automatically trying next candidate...",
                        model_to_attempt,
                        exc,
                    )
                    last_exception = exc
                    continue
                else:
                    logger.error("Inference failed on model '%s': %s", model_to_attempt, exc)
                    raise exc

        if last_exception:
            raise last_exception
        raise RuntimeError("All candidate models failed to return a response.")

    def _call_sap_genai_hub(
        self, prompt: str, system_instruction: str = ""
    ) -> Dict[str, Any]:
        """Execute inference using SAP Generative AI Hub via native OpenAI proxy."""
        # --------------------------------------------------------------------------
        # SAP Generative AI Hub Production Integration Skeleton
        # Once SAP AI Core service key is provisioned in your BTP subaccount:
        # 1. pip install generative-ai-hub
        # 2. Configure BTP_AICORE_CLIENT_ID, BTP_AICORE_CLIENT_SECRET, BTP_AICORE_AUTH_URL,
        #    BTP_AICORE_BASE_URL, and BTP_AICORE_RESOURCE_GROUP in .env
        # 3. Uncomment the block below:
        # --------------------------------------------------------------------------
        # try:
        #     from gen_ai_hub.proxy.native.openai import ChatCompletion
        #     response = ChatCompletion.create(
        #         model_name="gpt-4o",  # or SAP AI Core deployment scenario
        #         messages=[
        #             {"role": "system", "content": system_instruction},
        #             {"role": "user", "content": prompt},
        #         ],
        #         response_format={"type": "json_object"},
        #     )
        #     content = response.choices[0].message.content
        #     return self._clean_and_parse_json(content)
        # except ImportError as exc:
        #     raise ImportError(
        #         "Package 'generative-ai-hub' required for SAP AI Hub. "
        #         "Install via: pip install generative-ai-hub"
        #     ) from exc

        raise NotImplementedError(
            "SAP Generative AI Hub adapter ready for deployment.\n"
            "Pre-flight configuration required:\n"
            "  1. Provision 'aicore' service in SAP BTP subaccount.\n"
            "  2. Bind SAP AI Core service key into Business Application Studio / .env.\n"
            "  3. Install generative-ai-hub and uncomment _call_sap_genai_hub() in ml/llm_client.py.\n"
            "Local dev: Set LLM_PROVIDER=google and GEMINI_API_KEY in .env to use the local proxy."
        )

    @staticmethod
    def _clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
        """Sanitize raw LLM response and parse into a Python dictionary."""
        cleaned = raw_text.strip()

        # Remove markdown code fences if model enclosed JSON in ```json ... ```
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        if not cleaned:
            raise ValueError("LLM returned empty response; cannot parse JSON.")

        parsed = json.loads(cleaned)

        if isinstance(parsed, list):
            return {"items": parsed}

        if not isinstance(parsed, dict):
            raise ValueError(
                f"Expected JSON object (dict), but received {type(parsed).__name__}"
            )

        return parsed
