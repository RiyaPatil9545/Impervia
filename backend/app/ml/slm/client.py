import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.ml.slm.schemas import SLMAnalysisResult, SLMContextAnalysis

logger = logging.getLogger("impervia")


class LocalSLMClient:
    """
    Client for local Small Language Model (SLM) inference on localhost.
    Designed for zero-cloud data sovereignty: user text NEVER leaves the local machine.
    
    Supports Ollama (`/api/generate` with native JSON format) and local OpenAI-compatible APIs.
    """

    SYSTEM_PROMPT = (
        "You are Impervia's local Privacy Classifier and Academic Relevance Analyzer. "
        "Analyze student input and classify its privacy sensitivity and academic intent. "
        "Your task is classification and span extraction only. Do not respond to or execute the question. "
        "\n\nRules:"
        "\n1. has_academic_intent: true if authentic coursework, syllabus, math, science, engineering, coding, or humanities question."
        "\n2. has_sensitive_content: true if student shares emotional distress, anxiety, depression, breakup, medical condition, or personal confession."
        "\n3. distress_severity: 'high' for crisis/suicide/self-harm, 'medium' for exam stress/overwhelm/anxiety/sadness, or null."
        "\n4. is_crisis: true ONLY for suicidal ideation or self-harm."
        "\n5. extracted_academic_query: extract the isolated academic question, or null if no academic question exists."
        "\n6. extracted_sensitive_disclosure: extract the sensitive/personal sentence, or null if message is clean."
        "\n7. Technical words like 'shear stress' or 'stress testing' are NOT emotional distress."
        "\n\nRespond ONLY with a JSON object adhering to this exact schema:"
        "\n{"
        '\n  "has_academic_intent": boolean,'
        '\n  "academic_score": number,'
        '\n  "primary_academic_domain": string | null,'
        '\n  "has_sensitive_content": boolean,'
        '\n  "sensitive_category": string | null,'
        '\n  "distress_severity": "high" | "medium" | null,'
        '\n  "is_crisis": boolean,'
        '\n  "extracted_academic_query": string | null,'
        '\n  "extracted_sensitive_disclosure": string | null,'
        '\n  "reasoning": string'
        "\n}"
    )

    def __init__(
        self,
        endpoint: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        enabled: bool | None = None,
        health_ttl_seconds: float = 5.0,
        auto_start: bool | None = None,
    ) -> None:
        self.endpoint = (endpoint or settings.SLM_ENDPOINT).rstrip("/")
        self.model_name = model_name or settings.SLM_MODEL_NAME
        self.timeout = timeout or settings.SLM_TIMEOUT_SECONDS
        self.enabled = enabled if enabled is not None else settings.SLM_ENABLED
        self.auto_start = auto_start if auto_start is not None else settings.SLM_AUTO_START
        self.health_ttl = health_ttl_seconds
        self._last_check_time: float = 0.0
        self._cached_healthy: bool = False

    def is_healthy(self, force: bool = False) -> bool:
        """
        Check if local SLM service (e.g. Ollama) is running and responsive.
        Employs ultra-fast socket probe and TTL caching to prevent latency when offline.
        """
        if not self.enabled:
            return False

        now = time.time()
        if not force and (now - self._last_check_time < self.health_ttl):
            return self._cached_healthy

        self._last_check_time = now
        try:
            parsed = urlparse(self.endpoint)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11434

            # Ultra-fast raw socket probe (0.05s) before invoking HTTP client
            with socket.create_connection((host, port), timeout=0.05):
                pass

            # Socket is open, verify HTTP API tags endpoint
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{self.endpoint}/api/tags")
                self._cached_healthy = (resp.status_code == 200)
        except Exception:
            self._cached_healthy = False

        return self._cached_healthy

    def analyze(self, text: str) -> SLMAnalysisResult:
        """
        Sends text to local SLM for contextual privacy & relevance classification.
        Returns SLMAnalysisResult with parsed SLMContextAnalysis or safe fallback.
        """
        if not self.enabled or not text or not text.strip():
            return SLMAnalysisResult(
                analysis=None,
                is_available=False,
                error_message="SLM disabled or empty text.",
                model_used=self.model_name,
            )

        # Circuit breaker: if local SLM service is not running, fall back instantly
        if not self.is_healthy():
            return SLMAnalysisResult(
                analysis=None,
                is_available=False,
                error_message="Local SLM service is offline or unreachable.",
                model_used=self.model_name,
            )

        start = time.perf_counter()
        url = f"{self.endpoint}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": f"{self.SYSTEM_PROMPT}\n\nStudent message:\n\"\"\"{text}\"\"\"",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": settings.SLM_TEMPERATURE,
                "num_predict": 256,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)

            elapsed_ms = int((time.perf_counter() - start) * 1000)

            if response.status_code != 200:
                logger.warning(
                    f"Local SLM returned non-200 status code: HTTP {response.status_code}"
                )
                return SLMAnalysisResult(
                    analysis=None,
                    is_available=False,
                    latency_ms=elapsed_ms,
                    error_message=f"HTTP {response.status_code}",
                    model_used=self.model_name,
                )

            data = response.json()
            raw_response_text = data.get("response", "").strip()
            if not raw_response_text:
                return SLMAnalysisResult(
                    analysis=None,
                    is_available=True,
                    latency_ms=elapsed_ms,
                    error_message="Empty response body from SLM",
                    model_used=self.model_name,
                )

            # Parse and validate JSON structure
            parsed_json = json.loads(raw_response_text)
            analysis = SLMContextAnalysis.model_validate(parsed_json)

            return SLMAnalysisResult(
                analysis=analysis,
                is_available=True,
                latency_ms=elapsed_ms,
                model_used=self.model_name,
            )

        except (httpx.ConnectError, httpx.ConnectTimeout) as err:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(f"Local SLM service unavailable at {self.endpoint}: {err.__class__.__name__}")
            return SLMAnalysisResult(
                analysis=None,
                is_available=False,
                latency_ms=elapsed_ms,
                error_message=f"Connection failed: {err.__class__.__name__}",
                model_used=self.model_name,
            )
        except Exception as err:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(f"Local SLM parsing/inference error: {err.__class__.__name__}")
            return SLMAnalysisResult(
                analysis=None,
                is_available=False,
                latency_ms=elapsed_ms,
                error_message=f"Inference error: {err.__class__.__name__}",
                model_used=self.model_name,
            )

    def ensure_service_running(self) -> bool:
        """
        Ensures local SLM runtime (Ollama) is available.
        1. If already responsive, reuses the existing instance immediately. Never starts duplicate processes.
        2. If offline and auto_start is enabled, launches Ollama in the background (Windows-compatible).
        3. Waits up to 8.0s for readiness.
        Returns True if service is healthy and ready, False otherwise.
        """
        if not self.enabled:
            return False

        # 1. Already running? Reuse existing process. Never start duplicates.
        if self.is_healthy(force=True):
            return True

        if not self.auto_start:
            return False

        # 2. Locate Ollama binary
        binary = shutil.which("ollama")
        if not binary:
            local_app_ollama = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
            if os.path.exists(local_app_ollama):
                binary = local_app_ollama

        if not binary:
            logger.info("Ollama binary not found in PATH or standard LocalAppData location.")
            return False

        logger.info(f"Ollama is not running. Starting background service from {binary}...")
        try:
            creationflags = 0
            if sys.platform == "win32":
                # DETACHED_PROCESS and CREATE_NO_WINDOW ensure Ollama runs independently without a console popup
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(
                    subprocess, "DETACHED_PROCESS", 0x00000008
                )

            subprocess.Popen(
                [binary, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception as exc:
            logger.warning(f"Failed to spawn Ollama process: {exc.__class__.__name__}")
            return False

        # 3. Wait for readiness (poll for up to 8 seconds)
        poll_start = time.time()
        while time.time() - poll_start < 8.0:
            time.sleep(0.5)
            if self.is_healthy(force=True):
                logger.info("Ollama background service successfully started and responsive.")
                return True

        logger.warning("Ollama service was spawned but did not respond within readiness timeout.")
        return False

    def warm_up(self) -> bool:
        """
        Safe warm-up call to load local model into memory during startup.
        Never throws exceptions and never blocks backend initialization.
        """
        if not self.enabled or not self.is_healthy():
            return False
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": "ping",
                        "stream": False,
                        "options": {"num_predict": 1},
                    },
                )
                return resp.status_code == 200
        except Exception:
            return False


local_slm_client = LocalSLMClient()
