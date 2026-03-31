"""Abstract provider interface and shared data models for cloud provisioning."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Location:
    id: int
    name: str
    description: str
    city: str
    country: str
    network_zone: str


@dataclass
class ServerType:
    id: int
    name: str
    description: str
    cores: int
    memory: float  # GB
    disk: int  # GB
    cpu_type: str  # "shared" | "dedicated"
    architecture: str  # "x86" | "arm"
    price_hourly: str  # gross, as decimal string
    price_monthly: str  # gross, as decimal string


@dataclass
class Image:
    id: int
    name: str
    description: str
    os_flavor: str
    os_version: str | None
    architecture: str  # "x86" | "arm"


@dataclass
class SSHKey:
    id: int
    name: str
    fingerprint: str
    public_key: str = ""


@dataclass
class ServerSpec:
    name: str
    server_type: str  # type name, e.g. "cpx22"
    image: str  # image name, e.g. "ubuntu-24.04"
    location: str  # location name, e.g. "hel1"
    ssh_key_ids: list[int] = field(default_factory=list)
    user_data: str | None = None


@dataclass
class Server:
    id: int
    name: str
    status: str
    ipv4: str | None
    ipv6: str | None
    action_id: int | None = None


class Provider(ABC):
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
