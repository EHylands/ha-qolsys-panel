from __future__ import annotations

from typing import TYPE_CHECKING

from .adc import AdcCommands
from .automation import AutomationCommands
from .camera import CameraCommands
from .panel import PanelCommands
from .zwave import ZWaveCommands

if TYPE_CHECKING:
    from ..controller import QolsysController


class QolsysCommandService:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller

        self.adc = AdcCommands(controller)
        self.panel = PanelCommands(controller)
        self.zwave = ZWaveCommands(controller)
        self.automation = AutomationCommands(controller)
        self.camera = CameraCommands(controller)
