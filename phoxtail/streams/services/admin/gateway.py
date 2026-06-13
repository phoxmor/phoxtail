class RegistryServiceAdminGateway:
    def __init__(self, service):
        self.service = service

    def install(self, variant_id: int):
        from .operations.install import RegistryServiceAdminInstall

        return RegistryServiceAdminInstall(self.service).execute(variant_id=variant_id)
