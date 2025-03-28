# Exposing top level classes.
from diveplan.core.dive import Dive  # type: ignore
from diveplan.core.divesettings import DiveSettings  # type: ignore
from diveplan.core.divestep import DiveStep  # type: ignore
from diveplan.core.gas import Gas  # type: ignore

# Init Default Settings
default_settings = DiveSettings()
