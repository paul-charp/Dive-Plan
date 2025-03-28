from typing import Optional

from diveplan import DiveSettings


def test_settings(value: Optional[float] = None):

    if DiveSettings.current_settings is None:
        raise ValueError("No settings found")

    if value is None:
        value = DiveSettings.current_settings.settings["max_depth"]

    print(value)


custom_settings = DiveSettings()
custom_settings.settings["max_depth"] = 40


test_settings()

with custom_settings:
    test_settings()

test_settings()


custom_settings.use()
test_settings()

test_settings(50)
