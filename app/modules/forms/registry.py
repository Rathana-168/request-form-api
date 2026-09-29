"""Auto-discovers form plugins in app/modules/forms/definitions/.

Add a folder with an `__init__.py` exporting `definition` and it is registered.
"""

import importlib
import pkgutil

from app.modules.forms.exceptions import UnknownFormError
from app.modules.forms.plugin import FormDefinition

FORM_REGISTRY: dict[str, FormDefinition] = {}
_loaded = False


def load_plugins() -> dict[str, FormDefinition]:
    """Import every plugin package once. Safe to call many times."""
    global _loaded
    if _loaded:
        return FORM_REGISTRY

    # Load form definition
    from app.modules.forms import definitions
    
    for mod in pkgutil.iter_modules(definitions.__path__):
        if not mod.ispkg:
            continue
        module = importlib.import_module(f"{definitions.__name__}.{mod.name}")
        definition = getattr(module, "definition", None)
        if not isinstance(definition, FormDefinition):
            raise TypeError(f"Form plugin '{mod.name}' must export `definition`")
        if definition.code in FORM_REGISTRY:
            raise RuntimeError(f"Duplicate form code '{definition.code}'")
        FORM_REGISTRY[definition.code] = definition

    # validate form using the same prefix
    prefixes = [d.prefix for d in FORM_REGISTRY.values()]
    if len(prefixes) != len(set(prefixes)):
        raise RuntimeError("Form plugins must use unique request number prefixes")

    # load one time cache in memory
    _loaded = True
    return FORM_REGISTRY


def get_definition(code: str) -> FormDefinition:
    definition = load_plugins().get(code)
    if not definition:
        raise UnknownFormError(f"No plugin registered for form '{code}'")
    return definition