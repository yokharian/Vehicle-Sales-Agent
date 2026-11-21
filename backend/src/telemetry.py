from __future__ import annotations

import logging

import sentry_sdk
from sentry_sdk.integrations.langchain import LangchainIntegration

from config import SentrySettings


logger = logging.getLogger(__name__)


def init_sentry(settings: SentrySettings | None = None) -> bool:
    if sentry_sdk.get_client().is_active():
        return True

    resolved = settings or SentrySettings()
    if not resolved.enabled:
        logger.debug("SENTRY_DSN is not set; Sentry stays disabled")
        return False

    sentry_sdk.init(
        dsn=resolved.dsn,
        environment=resolved.environment,
        release=resolved.release,
        traces_sample_rate=resolved.resolved_traces_sample_rate,
        integrations=[LangchainIntegration()],
    )
    logger.info("Sentry initialized for environment %s", resolved.environment)
    return True
