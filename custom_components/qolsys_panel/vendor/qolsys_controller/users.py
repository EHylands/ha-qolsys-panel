import logging

LOGGER = logging.getLogger(__name__)


class QolsysUser:
    def __init__(self) -> None:
        self._id: int = 0
        # Audit H3: only the hash of the code is ever held, never the code.
        self._user_code_hash = ""

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, value: int) -> None:
        self._id = value

    @property
    def user_code_hash(self) -> str:
        return self._user_code_hash

    @user_code_hash.setter
    def user_code_hash(self, value: str) -> None:
        self._user_code_hash = value
