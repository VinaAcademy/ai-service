import logging
from typing import Optional, Dict

import httpx
import py_eureka_client.eureka_client as eureka_client

logger = logging.getLogger(__name__)

base_url = 'https://api.vnacademy.io.vn'


async def call_api(
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        timeout: float = 30.0,
) -> Dict:
    """
    Generic async API caller
    """
    if not base_url:
        return {
            "status": "ERROR",
            "message": "Service unavailable",
            "data": None
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=f"{base_url}{endpoint}",
                params=params
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error: {str(e)}")
        return {
            "status": "ERROR",
            "message": f"Request failed: {str(e)}",
            "data": None
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return {
            "status": "ERROR",
            "message": f"Unexpected error: {str(e)}",
            "data": None
        }


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


async def search_courses_semantic(
        query: str,
        filters: dict,
        page: int = 0,
        size: int = 9
) -> dict:
    """
    Search courses using semantic search
    """
    params = {
        "semantic": "true",
        "keyword": query,
        "page": page,
        "size": size,
        **filters
    }

    return await call_api(
        method="GET",
        endpoint="/api/v1/courses/aisearch",
        params=params
    )


async def search_courses_keyword(
        keyword: Optional[str] = None,
        filters=None,
        status: str = "PUBLISHED",
        page: int = 0,
        size: int = 5,
        sort: str = "rating,desc"
) -> dict:
    """
    Get course list with filter & sorting
    """
    params = {
        "status": status,
        "page": page,
        "size": size,
        "sort": sort,
        **filters
    }

    if keyword:
        params["keyword"] = keyword

    return await call_api(
        method="GET",
        endpoint="/api/v1/courses",
        params=params
    )
