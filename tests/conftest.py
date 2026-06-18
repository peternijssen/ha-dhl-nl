"""pytest configuration for the DHL NL test suite."""
import pytest

from pytest_homeassistant_custom_component.plugins import hass  # noqa: F401


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make ``custom_components.dhl_nl`` loadable from config-flow / setup tests."""
    yield
