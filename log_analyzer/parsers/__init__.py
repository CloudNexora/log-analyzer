"""Parser sub-package — auto-registers all built-in parsers."""

from .base import BaseParser
from .docker import DockerParser
from .generic import GenericParser
from .jenkins import JenkinsParser
from .kubernetes import KubernetesParser

__all__ = [
    "BaseParser",
    "JenkinsParser",
    "DockerParser",
    "KubernetesParser",
    "GenericParser",
]

# Registry mapping LogSource value → parser class
PARSER_REGISTRY: dict = {
    "jenkins": JenkinsParser,
    "docker": DockerParser,
    "kubernetes": KubernetesParser,
    "generic": GenericParser,
}
