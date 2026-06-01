from abc import ABC, abstractmethod


class OnSiteGenerationBase(ABC):
    """Base class for on-site generation systems"""

    @abstractmethod
    def produce_energy(self) -> tuple[float, float]:
        """Produce energy from the on-site generation system"""
        pass  # pragma: no cover

    @abstractmethod
    def inverter_is_inside(self) -> bool:
        """Return whether this unit is considered inside the building or not"""
        pass  # pragma: no cover
