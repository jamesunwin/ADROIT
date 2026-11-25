"""Headless UI runs never read or write the researcher's real private model catalog."""
import pytest

@pytest.fixture(autouse=True)
def private_test_catalog(tmp_path,monkeypatch):
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(),'model_library_dir',tmp_path/'model_library')
    monkeypatch.setattr(get_settings(),'experimental_library_dir',tmp_path/'experimental_library')


@pytest.fixture(autouse=True)
def keep_adroit_packages():
    """NiceGUI's reset after a user test drops every module that registered a page from sys.modules, with its parent
    packages (adroit.ui.app, adroit.ui and adroit), so that the next test registers its pages afresh. A later
    ``import adroit`` would then create a second, empty package object, and string-path monkeypatches such as
    ``"adroit.parameter_space.searches.prefetch_lhc"`` would fail in whatever test runs next. The page modules stay
    dropped; the packages are put back."""
    import sys
    packages = {name: module for name, module in sys.modules.items()
                if (name == "adroit" or name.startswith("adroit.")) and hasattr(module, "__path__")}
    yield
    for name, module in packages.items():
        sys.modules.setdefault(name, module)


SEE_RETRIES = 40          # 4 s: Constrain a model's setup and its check arrive from a worker thread (UO-06's addendum)


@pytest.fixture(autouse=True)
def patient_should_see(monkeypatch):
    """``User.should_see`` waits up to 4 s instead of NiceGUI's 0.3 s: the scan panel computes its setup and setup check
    off the event loop (so that a cold check no longer freezes the page), and they arrive a moment after the page. It
    only delays a failure; a test passing ``retries`` keeps its own."""
    from nicegui.testing import User
    original = User.should_see

    async def should_see(self, *args, retries: int = SEE_RETRIES, **kwargs):
        return await original(self, *args, retries=retries, **kwargs)
    monkeypatch.setattr(User, "should_see", should_see)
