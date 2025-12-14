import logging
from typing import Optional

import httpx
import py_eureka_client.eureka_client as eureka_client

logger = logging.getLogger(__name__)


async def get_vector_search_service_url() -> Optional[str]:
    """
    Resolve VECTOR-SEARCH-SERVICE from Eureka server.

    Returns:
        Base URL of the vector search service or None if not found
    """
    try:
        # Get service instance from Eureka
        service_url = await eureka_client.do_service_async(
            app_name="VECTOR-SEARCH-SERVICE",
            return_type="url"
        )
        if service_url:
            logger.info(f"✅ Resolved VECTOR-SEARCH-SERVICE: {service_url}")
            return service_url
        else:
            logger.warning("⚠️ VECTOR-SEARCH-SERVICE not found in Eureka")
            return None
    except Exception as e:
        logger.error(f"❌ Failed to resolve VECTOR-SEARCH-SERVICE: {str(e)}")
        return None


async def search_courses_semantic(query: str, filter: dict, page: int = 0, size: int = 9) -> dict:
    """
    Search courses using semantic search via VECTOR-SEARCH-SERVICE.

    Args:
        query: Search query (e.g., "Học python")
        page: Page number (default: 0)
        size: Page size (default: 9)

    Returns:
        API response with course list and pagination info
        :param filter:
    """
    # base_url = await get_vector_search_service_url()
    base_url = 'https://api.vnacademy.io.vn'
    if not base_url:
        return {
            "status": "ERROR",
            "message": "Vector search service unavailable",
            "data": None
        }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/api/v1/courses/aisearch",
                params={
                    "semantic": "true",
                    "keyword": query,
                    "page": page,
                    "size": size,
                    **filter
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error during semantic search: {str(e)}")
        return {
            "status": "ERROR",
            "message": f"Search failed: {str(e)}",
            "data": None
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error during semantic search: {str(e)}")
        return {
            "status": "ERROR",
            "message": f"Unexpected error: {str(e)}",
            "data": None
        }
