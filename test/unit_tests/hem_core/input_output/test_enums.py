import pytest

from hem_core.input_output.enums import WindowTreatmentControl


class TestWindowTreatmentCtrl:
    @pytest.mark.parametrize("value", list(WindowTreatmentControl))
    def test_is_either_automatic_or_manual(self, value: WindowTreatmentControl):
        assert value.is_automatic or value.is_manual, (
            "WindowTreatmentControl must be either manual or automatic"
        )

    @pytest.mark.parametrize(
        "value",
        (WindowTreatmentControl.AUTO_MOTORISED, WindowTreatmentControl.COMBINED_LIGHT_BLIND_HVAC),
    )
    def test_is_not_manual(self, value: WindowTreatmentControl):
        assert not value.is_manual, "WindowTreatmentControl is not manual"

    @pytest.mark.parametrize(
        "value", (WindowTreatmentControl.MANUAL, WindowTreatmentControl.MANUAL_MOTORISED)
    )
    def test_is_not_automatic(self, value: WindowTreatmentControl):
        assert not value.is_automatic, "WindowTreatmentControl is not automatic"
