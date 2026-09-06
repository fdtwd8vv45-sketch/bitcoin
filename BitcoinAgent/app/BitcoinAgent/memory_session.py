"""Wire AgentCore Memory when MEMORY_BITCOINMEMORY_ID is present (after deploy)."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MEMORY_ID = os.getenv("MEMORY_BITCOINMEMORY_ID")
REGION = os.getenv("AWS_REGION", "us-east-1")


def build_session_manager(actor_id: str, session_id: str):
    """Return an AgentCoreMemorySessionManager, or None during local dev."""
    if not MEMORY_ID:
        return None
    from bedrock_agentcore.memory.integrations.strands.config import (
        AgentCoreMemoryConfig,
        RetrievalConfig,
    )
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )

    memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id=actor_id,
        async_mode=True,
        retrieval_config={
            f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.5),
            f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.5),
            f"/summaries/{actor_id}/{session_id}": RetrievalConfig(top_k=2, relevance_score=0.2),
        },
    )
    logger.info("Using AgentCore Memory %s for actor %s", MEMORY_ID, actor_id)
    return AgentCoreMemorySessionManager(memory_config, REGION)
