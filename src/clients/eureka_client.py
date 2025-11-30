import logging

import py_eureka_client.eureka_client as eureka_client

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def register_with_eureka():
    """Đăng ký service với Eureka Server"""
    try:
        await eureka_client.init_async(
            eureka_server=settings.eureka_server_url,
            app_name=settings.app_name,
            instance_host=settings.instance_host,
            instance_port=settings.instance_port,
            health_check_url=f"http://{settings.instance_host}:{settings.instance_port}/health",
            status_page_url=f"http://{settings.instance_host}:{settings.instance_port}/docs",
        )
        logger.info(f"✅ Registered with Eureka: {settings.app_name}")
    except Exception as e:
        logger.error(f"❌ Failed to register with Eureka: {str(e)}")


async def deregister_from_eureka():
    """Hủy đăng ký service khỏi Eureka"""
    try:
        await eureka_client.stop_async()
        logger.info(f"✅ Deregistered from Eureka: {settings.app_name}")
    except Exception as e:
        logger.error(f"❌ Failed to deregister from Eureka: {str(e)}")
