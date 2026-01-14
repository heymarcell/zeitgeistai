"""
Async Base Utilities for Collectors

Shared async utilities for HTTP requests and session management.
"""

import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import structlog

import aiohttp

logger = structlog.get_logger()

# Default timeouts
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

# Shared session (created per event loop)
_sessions: Dict[int, aiohttp.ClientSession] = {}


async def get_aiohttp_session() -> aiohttp.ClientSession:
    """
    Get or create an aiohttp session for the current event loop.
    
    Sessions are cached per event loop to allow reuse.
    """
    loop_id = id(asyncio.get_event_loop())
    
    if loop_id not in _sessions or _sessions[loop_id].closed:
        _sessions[loop_id] = aiohttp.ClientSession(
            timeout=DEFAULT_TIMEOUT,
            headers={
                "User-Agent": "ZeitgeistEngine/2.0 (News Aggregator)"
            }
        )
    
    return _sessions[loop_id]


async def close_session():
    """Close the aiohttp session for the current event loop."""
    loop_id = id(asyncio.get_event_loop())
    
    if loop_id in _sessions and not _sessions[loop_id].closed:
        await _sessions[loop_id].close()
        del _sessions[loop_id]


async def fetch_url(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    retries: int = 3,
    retry_delay: float = 1.0
) -> Optional[str]:
    """
    Fetch URL content with automatic retries.
    
    Args:
        url: URL to fetch
        method: HTTP method
        headers: Optional additional headers
        json_data: Optional JSON body for POST
        retries: Number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Response text or None on failure
    """
    session = await get_aiohttp_session()
    
    for attempt in range(retries):
        try:
            async with session.request(
                method,
                url,
                headers=headers,
                json=json_data
            ) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:
                    # Rate limited - wait longer
                    await asyncio.sleep(retry_delay * (attempt + 2))
                else:
                    logger.debug("fetch_url_error", 
                                url=url[:50], 
                                status=response.status)
                    
        except asyncio.TimeoutError:
            logger.debug("fetch_url_timeout", url=url[:50], attempt=attempt)
        except aiohttp.ClientError as e:
            logger.debug("fetch_url_client_error", url=url[:50], error=str(e))
        
        if attempt < retries - 1:
            await asyncio.sleep(retry_delay)
    
    return None


async def fetch_json(
    url: str,
    headers: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """Fetch and parse JSON from URL."""
    text = await fetch_url(url, headers=headers)
    
    if text:
        try:
            import json
            return json.loads(text)
        except Exception as e:
            logger.debug("fetch_json_parse_error", error=str(e))
    
    return None


@asynccontextmanager
async def async_collector_context():
    """
    Context manager for async collectors.
    
    Ensures session cleanup on exit.
    """
    try:
        yield
    finally:
        await close_session()
