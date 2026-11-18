"""Sentry SDK initialization shared by the application entry points.

Initialization is idempotent: every entry module may call :func:`init_sentry`
without sending duplicate events or spans. When no DSN is configured the SDK
stays disabled, so local scripts and tests run without network side effects.
"""

from __future__ import annotations

import logging

import sentry_sdk
from sentry_sdk.integrations.langchain import LangchainIntegration

from config import SentrySettings


logger = logging.getLogger(__name__)


def init_sentry(settings: SentrySettings | None = None) -> bool:
    """Initialize the Sentry SDK once.

    Returns True when the SDK is active, False when no DSN is configured.
    FastAPI and LangChain integrations are discovered from the installed
    packages; LangChain is declared explicitly so agent tracing stays wired
    even if it stops being enabled by default.
    """
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
