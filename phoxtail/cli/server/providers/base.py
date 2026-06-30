"""Abstract provider interface and shared data models for cloud provisioning."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Uniform error type raised by all providers.

    Carries a short machine-readable *code* so the wizard can handle errors
    without knowing which provider raised them.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class Location:
    id: int | str
    name: str
    description: str
    city: str
    country: str
    network_zone: str
    # False when the location cannot run cloud-init user_data.
    # Providers that have partial support (e.g. Linode legacy regions) set this;
    # those locations are filtered out of the wizard entirely (Option A).
    metadata_support: bool = True


@dataclass
class ServerType:
    id: int | str
    name: str
    description: str
    cores: int
    memory: float  # GB
    disk: int  # GB
    cpu_type: str  # "shared" | "dedicated"
    architecture: str  # "x86" | "arm"
    price_hourly: str  # as decimal string
    price_monthly: str  # as decimal string


@dataclass
class Image:
    id: int | str
    name: str
    description: str
    os_flavor: str
    os_version: str | None
    architecture: str  # "x86" | "arm"
    # False when the image does not support cloud-init (e.g. Slackware on Linode).
    cloud_init: bool = True


@dataclass
class SSHKey:
    id: int
    name: str
    fingerprint: str
    public_key: str = ""


@dataclass
class ServerSpec:
    name: str
    server_type: str  # type name, e.g. "cpx22" or "g6-nanode-1"
    image: str  # image name/id, e.g. "ubuntu-24.04" or "linode/ubuntu24.04"
    location: str  # location name/id, e.g. "hel1" or "de-fra-2"
    ssh_key_ids: list[int] = field(default_factory=list)
    # Raw public-key strings — used by providers that authorise by key material
    # rather than stored key IDs (Linode's authorized_keys field).
    ssh_public_keys: list[str] = field(default_factory=list)
    user_data: str | None = None


@dataclass
class Server:
    id: int
    name: str
    status: str
    ipv4: str | None
    ipv6: str | None
    action_id: int | None = None
    # One-time root password returned by providers when no SSH key is supplied.
    root_password: str | None = None


_DEFAULT_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.\-]*[a-z0-9])?$")


class Provider(ABC):
    # --- Provider metadata (set on subclasses) ---------------------------------
    display_name: str = "Cloud"
    currency: str = "$"
    token_env_var: str = ""
    # Architectures offered; wizard skips the question when only one is present.
    architectures: tuple[str, ...] = ("x86",)

    def validate_server_name(self, name: str) -> bool | str:
        """Return True if *name* is valid, else a human-readable error string."""
        name = name.strip()
        if not name:
            return "Server name cannot be empty."
        if not _DEFAULT_NAME_RE.match(name):
            return "Name must contain only lowercase letters, digits, hyphens, and dots."
        return True

    @abstractmethod
    def list_locations(self) -> list[Location]: ...

    @abstractmethod
    def list_server_types(self, *, location: str | None = None) -> list[ServerType]: ...

    @abstractmethod
    def list_ssh_keys(self) -> list[SSHKey]: ...

    @abstractmethod
    def list_images(self, *, architecture: str = "x86") -> list[Image]: ...

    @abstractmethod
    def create_server(self, spec: ServerSpec) -> Server: ...

    @abstractmethod
    def delete_server(self, server_id: int) -> None: ...

    @abstractmethod
    def get_action_status(self, action_id: int) -> str: ...
