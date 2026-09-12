import logging
from dataclasses import dataclass, field

from amqtt.contexts import BaseContext
from amqtt.plugins.authentication import BaseAuthPlugin
from amqtt.session import Session
from passlib.hash import sha512_crypt

LOGGER = logging.getLogger(__name__)


class AuthPlugin(BaseAuthPlugin):  # type: ignore[misc]
    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)
        self.allowed_users = self._get_config_option("allowed_users", {})

    async def authenticate(self, *, session: Session) -> bool | None:
        if not session:
            LOGGER.debug("MQTT Bridge Broker - Authentication failure: no session provided")
            return None

        if not session.username or not session.password:
            LOGGER.debug("MQTT Bridge Broker - Authentication failure: session username or password is empty")
            return None

        allowed_password_hash = self.allowed_users.get(session.username)

        if not allowed_password_hash:
            LOGGER.debug("MQTT Bridge Broker - Authentication failure: username %s", session.username)
            return False

        if sha512_crypt.verify(session.password, allowed_password_hash):
            LOGGER.info("MQTT Bridge Broker - Authentication success for username: %s", session.username)
            return True
        else:
            LOGGER.debug("MQTT Bridge Broker - Authentication failure: username %s", session.username)

        return False

    @dataclass
    class Config:
        allowed_users: dict[str, str] = field(default_factory=dict)
