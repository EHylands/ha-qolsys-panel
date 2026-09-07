import logging

LOGGER = logging.getLogger(__name__)


class QolsysUser:
    def __init__(self) -> None:
        self._id: int = 0
        self._user_code = ""

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, value: int) -> None:
        self._id = value

    @property
    def user_code(self) -> str:
        return self._user_code

    @user_code.setter
    def user_code(self, value: str) -> None:
        self._user_code = value
