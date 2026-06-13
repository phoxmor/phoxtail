class RegistryServiceAdminGateway:
    def __init__(self, service):
        self.service = service

    def install(self, variant_slug: str):
        from .operations.install import RegistryServiceAdminInstall

        return RegistryServiceAdminInstall(self.service).execute(variant_slug=variant_slug)
