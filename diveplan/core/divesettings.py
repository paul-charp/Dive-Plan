from typing import Any, Optional


class DiveSettings:

    _old_settings: Optional["DiveSettings"] = None
    current_settings: Optional["DiveSettings"] = None

    def __init__(self):
        self._settings: dict[str, Any] = {
            "max_depth": 30,
            "min_temperature": 10,
            "gas_mix": "air",
            "safety_stop": True,
        }

        cls = self.__class__

        if cls.current_settings is None:
            cls.current_settings = self

    @classmethod
    def get_current_settings(cls) -> Optional["DiveSettings"]:
        return cls.current_settings

    def use(self) -> None:
        cls = self.__class__
        cls.current_settings = self

    def __enter__(self) -> None:
        cls = self.__class__
        cls._old_settings = cls.current_settings
        cls.current_settings = self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        cls = self.__class__
        cls.current_settings = cls._old_settings
        cls._old_settings = None

    def load_from_file(self, filename: str) -> None:
        pass

    def save_to_file(self, filename: str) -> None:
        pass

    def load_from_dict(self, data: dict[str, Any]) -> None:
        pass

    def get_setting(self, key: str) -> Any:
        pass

    def set_setting(self, key: str, value: Any) -> None:
        pass

    @property
    def settings(self) -> dict[str, Any]:
        return self._settings
