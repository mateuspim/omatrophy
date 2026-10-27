"""The game stores OmaTrophy watches. Add a store by subclassing
stores.base.Store in its own module and listing the class here; see
docs/guide/stores.md."""
from .steam import Steam

STORES = [Steam]


def available():
    """An instance of every store that is installed and has achievement data."""
    return [s for s in (cls() for cls in STORES) if s.available()]
