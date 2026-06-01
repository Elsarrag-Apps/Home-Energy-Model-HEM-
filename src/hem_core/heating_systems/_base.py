from abc import ABC, abstractmethod


class HeatSourceBase(ABC):
    @abstractmethod
    def energy_output_max(self, *args, **kwargs) -> float:
        """Calculates the maximum energy output of the heat source."""
        ...

    @abstractmethod
    def setpnt(self) -> tuple[float | None, float | None]:
        """Get the setpoint temperature of the heat source."""
        ...

    @abstractmethod
    def demand_energy(self, *args, **kwargs) -> float:
        """Calculate energy demand for the heat source."""
        ...


class WaterSupplyBase(ABC):
    @abstractmethod
    def draw_off_water(self, volume_needed: float) -> list[tuple[float, float]]: ...

    @abstractmethod
    def get_temp_cold_water(self, volume_needed: float) -> list[tuple[float, float]]:
        """Return the cold water temperature for the current timestep and the volume drawn."""
        ...


class SpaceHeatSystem(ABC):
    @abstractmethod
    def temp_setpnt(self) -> float | None: ...

    @abstractmethod
    def in_required_period(self) -> bool | None: ...

    @abstractmethod
    def frac_convective(self) -> float: ...

    @abstractmethod
    def energy_output_min(self) -> float: ...

    @abstractmethod
    def demand_energy(self, energy_demand: float) -> float: ...
