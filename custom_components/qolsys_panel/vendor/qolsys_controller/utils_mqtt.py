import logging
import random

LOGGER = logging.getLogger(__name__)


def generate_random_mac() -> str:  # noqa: D103
    mac = [
        0xF2,
        0x16,
        0x3E,
        random.randint(0x00, 0x7F),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    ]
    return ":".join(map(lambda x: "%02x" % x, mac))  # noqa: C417, UP031
