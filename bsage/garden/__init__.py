"""Garden layer — vault management and structured note writing."""

from bsage.garden.sync import SyncBackend, SyncManager, WriteEvent, WriteEventType
from bsage.garden.vault import Vault
from bsage.garden.writer import GardenNote, GardenWriter

__all__ = [
    "GardenNote",
    "GardenWriter",
    "SyncBackend",
    "SyncManager",
    "Vault",
    "WriteEvent",
    "WriteEventType",
]
