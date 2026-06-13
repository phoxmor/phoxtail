from functools import cached_property


class RegistryService:
    def __init__(self, registry=None):
        self.registry = registry

    @cached_property
    def admin(self):
        from .admin.gateway import RegistryServiceAdminGateway

        return RegistryServiceAdminGateway(self)
