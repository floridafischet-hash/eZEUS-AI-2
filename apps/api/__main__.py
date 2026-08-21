import uvicorn

from core.config.settings import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.app_log_level.lower(),
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )


if __name__ == "__main__":
    run()
