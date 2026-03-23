from app.domain.monitor import MonitorDomainService


class MonitorService:
    def __init__(self):
        self.domain = MonitorDomainService()

    async def get_health_status(self):
        return await self.domain.get_health_status()
