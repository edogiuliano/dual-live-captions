"""Never let GUI tests overwrite the user's running application preferences."""
import pytest
from dual_live_captions.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings_writes(monkeypatch, tmp_path):
    original = Settings.save
    monkeypatch.setattr(Settings, "save", lambda self, path=None: original(self, path or tmp_path / "ui-settings.json"))
