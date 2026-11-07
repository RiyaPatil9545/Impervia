import logging
from typing import Any

from app.core.config import settings
from app.ml.slm.client import local_slm_client

logger = logging.getLogger("impervia")


class ModelManager:
    """
    Coordinates model lifecycle, health checks, and engine metadata
    for both deterministic Python rule detectors and the local SLM intelligence layer.
    """

    @classmethod
    def get_system_health(cls) -> dict[str, Any]:
        """
        Inspects availability of local engines without making blocking calls.
        """
        slm_online = local_slm_client.is_healthy() if settings.SLM_ENABLED else False
        return {
            "hybrid_mode_enabled": settings.SLM_ENABLED,
            "rule_based_engines": {
                "pii_detector": "active",
                "sensitive_detector": "active",
                "academic_relevance_detector": "active",
                "risk_assessor": "active",
            },
            "slm_engine": {
                "enabled": settings.SLM_ENABLED,
                "provider": settings.SLM_PROVIDER,
                "model_name": settings.SLM_MODEL_NAME,
                "endpoint": settings.SLM_ENDPOINT,
                "is_healthy": slm_online,
            },
            "version": settings.DETECTOR_VERSION,
        }


model_manager = ModelManager()
