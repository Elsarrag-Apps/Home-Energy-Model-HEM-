from abc import ABC, abstractmethod


class SpaceCoolSystemBase(ABC):
    @abstractmethod
    def temp_setpnt(self) -> float | None:
        """Return the temperature setpoint for the air conditioning system"""
        pass  # pragma: no cover

    @abstractmethod
    def in_required_period(self) -> bool:
        """Return true if current time is inside specified time for heating/cooling"""
        pass  # pragma: no cover

    @abstractmethod
    def frac_convective(self) -> float:
        """Return the convective fraction for cooling"""
        pass  # pragma: no cover

    @abstractmethod
    def energy_output_min(self) -> float:
        """Return the minimum energy output of the air conditioning system"""
        pass  # pragma: no cover

    @abstractmethod
    def demand_energy(self, cooling_demand: float) -> float:
        """Demand energy (in kWh) from the cooling system"""
        pass  # pragma: no cover
