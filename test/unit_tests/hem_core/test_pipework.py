from math import log, pi

import pytest

from hem_core import material_properties, units
from hem_core.ductwork import EXTERNAL_NONREFLECTIVE_HTC, EXTERNAL_REFLECTIVE_HTC
from hem_core.input_output.enums import PipeworkContents, WaterPipeworkLocation
from hem_core.pipework import INTERNAL_HTC_GLYCOL25, INTERNAL_HTC_WATER, Pipework, PipeworkSimple


class TestPipework:
    """Unit tests for Pipework class"""

    @pytest.fixture(autouse=True)
    def setup_pipework(self):
        """Create Pipework object to be tested."""
        self.pipework = Pipework(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=0.025,
            external_diameter=0.027,
            length=1.0,
            insulation_thermal_conductivity=0.035,
            insulation_thickness=0.038,
            reflective=False,
            contents=PipeworkContents.WATER,
        )

    def test_interior_surface_resistance(self):
        """Test that correct interior surface resistance is returned when queried

        Expected value calculated for:
        - Internal diameter: 0.025m (25mm pipe)
        - Heat transfer coefficient: 1500 W/m²K (INTERNAL_HTC_WATER)
        - Formula: 1 / (htc × π × diameter) = 1 / (1500 × π × 0.025) ≈ 0.00849 m·K/W
        """
        assert self.pipework.interior_surface_resistance == pytest.approx(
            expected=0.00849, abs=1e-5
        )

    def test_insulation_resistance(self):
        """Test that correct insulation resistance is returned when queried

        Expected value calculated for:
        - External diameter: 0.027m (27mm pipe)
        - Insulated diameter: 0.027 + 2×0.038 = 0.103m (with 38mm insulation)
        - Thermal conductivity: 0.035 W/m·K
        - Formula: ln(D_insulated/D_external) / (2π × k) = ln(0.103/0.027) / (2π × 0.035) ≈ 6.08832 m·K/W
        """
        assert self.pipework.insulation_resistance == pytest.approx(expected=6.08832, abs=1e-5)

    def test_external_surface_resistance(self):
        """Test that correct external surface resistance is returned when queried

        Expected value calculated for:
        - Insulated diameter: 0.103m (pipe + insulation)
        - Heat transfer coefficient: 10.0 W/m²K (EXTERNAL_NONREFLECTIVE_HTC, non-reflective surface)
        - Formula: 1 / (htc × π × D_insulated) = 1 / (10.0 × π × 0.103) ≈ 0.30904 m·K/W
        """
        assert self.pipework.external_surface_resistance == pytest.approx(
            expected=0.30904, abs=1e-5
        )

    @pytest.mark.parametrize(
        "T_i, T_o, expected",
        [
            (50.0, 15.0, 5.463755),
            (51.0, 16.0, 5.463755),
            (52.0, 17.0, 5.463755),
            (52.0, 18.0, 5.307648),
            (51.0, 19.0, 4.995433),
            (50.0, 20.0, 4.683219),
            (51.0, 21.0, 4.683219),
            (52.0, 21.0, 4.839326),
        ],
    )
    def test_heat_loss(self, T_i: float, T_o: float, expected: float):
        """Test that correct heat_loss is returned when queried

        Expected values calculated for pipework configuration:
        - Total thermal resistance: 0.00849 + 6.08832 + 0.30904 = 6.40585 m·K/W
        - Length: 1.0m
        - Formula: (T_inside - T_outside) / total_resistance × length

        Test cases verify heat loss decreases as temperature difference decreases:
        - 50°C to 15°C (ΔT=35°C): 35/6.40585 × 1.0 ≈ 5.463755 W
        - 52°C to 21°C (ΔT=31°C): 31/6.40585 × 1.0 ≈ 4.839326 W
        """
        result = self.pipework.calculate_steady_state_heat_loss(inside_temp=T_i, outside_temp=T_o)
        assert result == pytest.approx(expected=expected, abs=1e-5)

    @pytest.mark.parametrize(
        "T_i, T_o, expected",
        [
            (50.0, 15.0, 0.01997),
            (51.0, 16.0, 0.01997),
            (52.0, 17.0, 0.01997),
            (52.0, 18.0, 0.01940),
            (51.0, 19.0, 0.01826),
            (50.0, 20.0, 0.01712),
            (51.0, 21.0, 0.01712),
            (52.0, 21.0, 0.01769),
        ],
    )
    def test_cool_down_loss(self, T_i: float, T_o: float, expected: float):
        """Test that correct cool down loss is returned when queried

        Expected values represent total energy loss when pipe cools from inside temp to outside temp.

        Cool down loss calculation:
        - Energy content = (T_inside - T_outside) × volumetric_heat_capacity × volume
        - Volume: π × (0.025/2)² × 1.0 × 1000 = 0.4909 litres
        - Volumetric heat capacity: 4184 J/(litre·K)
        - Convert to kWh: J / 3,600,000 J/kWh

        Test cases verify energy loss decreases as temperature difference decreases:
        - 50°C to 15°C (ΔT=35°C): 35 × 4184 × 0.4909 / 3,600,000 ≈ 0.01997 kWh
        - 52°C to 21°C (ΔT=31°C): 31 × 4184 × 0.4909 / 3,600,000 ≈ 0.01769 kWh
        """
        result = self.pipework.calculate_cool_down_loss(inside_temp=T_i, outside_temp=T_o)
        assert result == pytest.approx(expected=expected, abs=1e-5)

    @pytest.mark.parametrize(
        "internal_diameter, external_diameter",
        [
            (2.0, 1.0),
            (1.0, 1.0),
            (0.5, 0.4),
        ],
    )
    def test_invalid_diameter_combinations(
        self, internal_diameter: float, external_diameter: float
    ):
        """Test various invalid diameter combinations"""
        with pytest.raises(ValueError):
            Pipework(
                location=WaterPipeworkLocation.INTERNAL,
                internal_diameter=internal_diameter,
                external_diameter=external_diameter,
                length=1.0,
                insulation_thermal_conductivity=0.035,
                insulation_thickness=0.038,
                reflective=False,
                contents=PipeworkContents.WATER,
            )

    def test_invalid_contents(self):
        """Test that ValueError is raised for invalid contents"""
        with pytest.raises(ValueError):
            Pipework(
                location=WaterPipeworkLocation.INTERNAL,
                internal_diameter=1,
                external_diameter=2,
                length=1.0,
                insulation_thermal_conductivity=0.035,
                insulation_thickness=0.038,
                reflective=False,
                contents="invalid",
            )

    def test_interior_surface_resistance_from_contents(self):
        """Test interior surface resistance calculation for different contents"""
        pipework_water = Pipework(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=1,
            external_diameter=2,
            length=1,
            insulation_thermal_conductivity=1,
            insulation_thickness=1,
            reflective=False,
            contents=PipeworkContents.WATER,
        )
        expected_water = 1 / (INTERNAL_HTC_WATER * pi)
        assert pipework_water.interior_surface_resistance == expected_water

        pipework_glycol = Pipework(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=1,
            external_diameter=2,
            length=1,
            insulation_thermal_conductivity=1,
            insulation_thickness=1,
            reflective=False,
            contents=PipeworkContents.GLYCOL25,
        )
        expected_glycol = 1 / (INTERNAL_HTC_GLYCOL25 * pi)
        assert pipework_glycol.interior_surface_resistance == expected_glycol

    def test_external_surface_resistance_from_reflective(self):
        """Test external surface resistance calculation for reflective/non-reflective surfaces"""
        pipework_nonreflective = Pipework(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=1,
            external_diameter=2,
            length=1,
            insulation_thermal_conductivity=1,
            insulation_thickness=1,
            reflective=False,
            contents=PipeworkContents.WATER,
        )
        expected_nonreflective = 1 / (EXTERNAL_NONREFLECTIVE_HTC * pi * 4)
        assert pipework_nonreflective.external_surface_resistance == expected_nonreflective

        pipework_reflective = Pipework(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=1,
            external_diameter=2,
            length=1,
            insulation_thermal_conductivity=1,
            insulation_thickness=1,
            reflective=True,
            contents=PipeworkContents.WATER,
        )
        expected_reflective = 1 / (EXTERNAL_REFLECTIVE_HTC * pi * 4)
        assert pipework_reflective.external_surface_resistance == expected_reflective

    def test_c_n_equivalence(self):
        """Test that c_n_equivalence returns correct values for emitter equivalent calculations"""

        # Test with the standard pipework object
        c, n, thermal_mass = self.pipework.c_n_equivalence()

        # Expected calculations based on the formula in the code:
        # c = length * 0.02761 * (external_diameter ** 0.8254)
        # n = -0.001793 * log(external_diameter) + 1.245135
        # thermal_mass = volume_litres * WATER.specific_heat_capacity() / units.J_per_kWh

        expected_c = 1.0 * 0.02761 * (27.0**0.8254) / units.W_per_kW
        expected_n = -0.001793 * log(27.0) + 1.245135
        # Volume calculation: pi * (internal_diameter/2)^2 * length * litres_per_cubic_metre
        volume_litres = pi * (0.025 / 2) * (0.025 / 2) * 1.0 * units.litres_per_cubic_metre
        expected_thermal_mass = (
            volume_litres * material_properties.WATER.specific_heat_capacity() / units.J_per_kWh
        )

        assert c == pytest.approx(expected_c, abs=1e-5)
        assert n == pytest.approx(expected_n, abs=1e-5)
        assert thermal_mass == pytest.approx(expected_thermal_mass, abs=1e-5)

        # Test with a different pipework configuration to ensure formula works correctly
        pipework2 = Pipework(
            location=WaterPipeworkLocation.EXTERNAL,
            internal_diameter=0.050,
            external_diameter=0.055,
            length=2.0,
            insulation_thermal_conductivity=0.040,
            insulation_thickness=0.025,
            reflective=True,
            contents=PipeworkContents.WATER,
        )
        c2, n2, thermal_mass2 = pipework2.c_n_equivalence()

        expected_c2 = 2.0 * 0.02761 * (55.0**0.8254) / units.W_per_kW
        expected_n2 = -0.001793 * log(55.0) + 1.245135
        volume_litres2 = pi * (0.050 / 2) * (0.050 / 2) * 2.0 * units.litres_per_cubic_metre
        expected_thermal_mass2 = (
            volume_litres2 * material_properties.WATER.specific_heat_capacity() / units.J_per_kWh
        )

        assert c2 == pytest.approx(expected_c2, abs=1e-5)
        assert n2 == pytest.approx(expected_n2, abs=1e-5)
        assert thermal_mass2 == pytest.approx(expected_thermal_mass2, abs=1e-5)

    def test_heat_loss_increases_with_temperature_difference(self):
        """Test that heat loss increases with temperature difference"""
        loss_small = self.pipework.calculate_steady_state_heat_loss(50.0, 45.0)  # ΔT = 5°C
        loss_large = self.pipework.calculate_steady_state_heat_loss(50.0, 20.0)  # ΔT = 30°C
        assert loss_large > loss_small


class TestPipeworkSimple:
    """Unit tests for PipeworkSimple class"""

    @pytest.fixture(autouse=True)
    def setup_pipework_simple(self):
        """Create PipeworkSimple objects for testing."""
        self.internal_pipe = PipeworkSimple(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=0.025,
            length=2.5,
            contents=PipeworkContents.WATER,
        )
        self.external_pipe = PipeworkSimple(
            location=WaterPipeworkLocation.EXTERNAL,
            internal_diameter=0.05,
            length=7,
            contents=PipeworkContents.WATER,
        )

    def test_glycol(self):
        """Test PipeworkSimple with glycol contents"""
        pipe = PipeworkSimple(
            location=WaterPipeworkLocation.INTERNAL,
            internal_diameter=0.05,
            length=7,
            contents=PipeworkContents.GLYCOL25,
        )
        assert pipe.contents_properties == material_properties.GLYCOL25

    def test_invalid_contents(self):
        """Check system exits if contents are not valid"""
        with pytest.raises(ValueError):
            PipeworkSimple(
                location=WaterPipeworkLocation.EXTERNAL,
                internal_diameter=0.05,
                length=7,
                contents="invalid",
            )

    def test_get_location(self):
        """Test location property returns correct values"""
        assert self.internal_pipe.location == WaterPipeworkLocation.INTERNAL
        assert self.external_pipe.location == WaterPipeworkLocation.EXTERNAL

    def test_volume_litres(self):
        """Test volume calculation follows physical laws"""
        # Test that volumes are positive and reasonable
        assert self.internal_pipe.volume > 0
        assert self.external_pipe.volume > 0

        # Test that volume scales with length
        # Internal pipe: 0.025m diameter, 2.5m length
        # External pipe: 0.05m diameter, 7.0m length
        # External pipe should have much larger volume due to larger diameter and length

        # Volume should scale with diameter² × length
        # External pipe diameter is 2x internal, length is 2.8x internal
        # So external volume should be roughly (2² × 2.8) = 11.2x internal volume
        volume_ratio = self.external_pipe.volume / self.internal_pipe.volume
        expected_ratio = (0.05 / 0.025) ** 2 * (7.0 / 2.5)  # (2² × 2.8) = 11.2
        assert volume_ratio == pytest.approx(expected_ratio, abs=1e-2)

    def test_cool_down_loss(self):
        """Test that energy loss follows physical laws"""
        # Test case 1: Positive temperature difference (heat loss)
        loss_positive = self.internal_pipe.calculate_cool_down_loss(
            inside_temp=20.0, outside_temp=10.0
        )
        assert loss_positive > 0, "Heat loss should be positive when inside is hotter"

        # Test case 2: Negative temperature difference (heat gain)
        loss_negative = self.internal_pipe.calculate_cool_down_loss(
            inside_temp=25.0, outside_temp=30.0
        )
        assert loss_negative < 0, "Heat gain should be negative when outside is hotter"

        # Test case 3: Zero temperature difference (no heat transfer)
        loss_zero = self.internal_pipe.calculate_cool_down_loss(inside_temp=25.0, outside_temp=25.0)
        assert loss_zero == pytest.approx(0.0, abs=1e-10), (
            "No heat transfer when temperatures are equal"
        )

        # Test that energy loss scales with temperature difference
        # Doubling the temperature difference should roughly double the energy loss
        loss_small = self.internal_pipe.calculate_cool_down_loss(
            inside_temp=30.0, outside_temp=20.0
        )  # 10°C diff
        loss_large = self.internal_pipe.calculate_cool_down_loss(
            inside_temp=40.0, outside_temp=20.0
        )  # 20°C diff
        assert loss_large == pytest.approx(expected=2.0 * loss_small, abs=1e-2), (
            "Energy loss should scale with temperature difference"
        )
