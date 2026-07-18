"""Locveil shared entry-point-group discovery engine (PROD-8 / voice ARCH-42).

Extracted from locveil-voice's ``utils/loader.py::DynamicLoader`` per the agreed design
``locveil-voice/docs/design/core_py_loader_extraction.md`` (§2 is the binding surface).
Faithful semantics — the ``(namespace, enabled)``-keyed class cache and the per-namespace
failure ledger (BUG-36: an enabled provider that fails to import must be reportable by
name, not vanish; success clears the entry) — plus the three agreed deltas:

1. optional ``base_class=`` validation, rejecting non-subclasses into the failure ledger;
2. ``get_provider_class`` loads only the named entry point on a group-cache miss;
3. ``list_registered`` enumerates names WITHOUT importing anything.

Ships the class ONLY — no module-level singleton; each consumer owns its instance.
Python 3.11+, ``importlib.metadata`` only (the py3.8/pkg_resources branches did not travel).

Consumers vendor this file byte-identical at a ``core-py-vN`` tag with a strict pin +
identity test — never edit a vendored copy; changes happen here and re-tag.
"""

import logging
from importlib.metadata import entry_points

logger = logging.getLogger(__name__)


class DynamicLoader:
    """Entry-points based class loader with configuration filtering.

    Discovers provider classes from an entry-point group ("namespace"), optionally
    filtered by an enabled-names list and validated against a required base class.
    Group names are consumer-owned inputs — this engine holds no registry of them.
    """

    def __init__(self) -> None:
        # (namespace, enabled-tuple|None, base_class|None) -> {name: class}
        self._cache: dict[tuple[str, tuple[str, ...] | None, type | None], dict[str, type]] = {}
        # namespace -> {entry_point_name: why it did not load}
        self._failures: dict[str, dict[str, str]] = {}

    def get_discovery_failures(self, namespace: str) -> dict[str, str]:
        """Entry points in ``namespace`` that were tried and did not load, with the reason."""
        return dict(self._failures.get(namespace, {}))

    def discover_providers(
        self,
        namespace: str,
        enabled: list[str] | None = None,
        base_class: type | None = None,
    ) -> dict[str, type]:
        """Discover provider classes in an entry-point group.

        Args:
            namespace: Entry-points group name.
            enabled: Optional allow-list of entry-point names (a falsy list means no filter).
            base_class: Optional required base class; a loaded object that is not a
                subclass is rejected into the failure ledger instead of returned.

        Returns:
            Mapping of entry-point name to loaded class. An unusable discovery
            mechanism degrades to an empty, uncached dict.
        """
        cache_key = (namespace, tuple(enabled) if enabled else None, base_class)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            eps = list(entry_points(group=namespace))
        except Exception as e:
            logger.error(f"Entry-points discovery failed for namespace '{namespace}': {e}")
            # Graceful fallback — empty dict lets component initialization proceed
            return {}

        discovered: dict[str, type] = {}
        for entry_point in eps:
            if enabled and entry_point.name not in enabled:
                continue
            try:
                provider_class = entry_point.load()
            except ImportError as e:
                logger.warning(f"Provider '{entry_point.name}' not available (import failed): {e}")
                self._failures.setdefault(namespace, {})[entry_point.name] = f"import failed: {e}"
                continue
            except Exception as e:
                logger.error(f"Failed to load provider '{entry_point.name}': {e}")
                self._failures.setdefault(namespace, {})[entry_point.name] = f"load failed: {e}"
                continue
            if self._rejected_by_base_class(namespace, entry_point.name, provider_class, base_class):
                continue
            discovered[entry_point.name] = provider_class
            self._failures.get(namespace, {}).pop(entry_point.name, None)
            logger.debug(f"Loaded provider '{entry_point.name}' from entry-point")

        self._cache[cache_key] = discovered
        logger.info(
            f"Discovered {len(discovered)} providers in namespace '{namespace}': {list(discovered.keys())}"
        )
        return discovered

    def get_provider_class(
        self,
        namespace: str,
        name: str,
        base_class: type | None = None,
    ) -> type | None:
        """Get one provider class by name, without materializing its whole group.

        A cached group containing the name answers immediately; otherwise only the
        named entry point is loaded (siblings stay unimported) and its failure, if
        any, is recorded individually in the ledger.
        """
        for (ns, _enabled, _base), classes in self._cache.items():
            if ns == namespace and name in classes:
                provider_class = classes[name]
                if self._rejected_by_base_class(namespace, name, provider_class, base_class):
                    return None
                return provider_class

        try:
            eps = list(entry_points(group=namespace))
        except Exception as e:
            logger.error(f"Entry-points discovery failed for namespace '{namespace}': {e}")
            return None

        for entry_point in eps:
            if entry_point.name != name:
                continue
            try:
                provider_class = entry_point.load()
            except ImportError as e:
                logger.warning(f"Provider '{name}' not available (import failed): {e}")
                self._failures.setdefault(namespace, {})[name] = f"import failed: {e}"
                return None
            except Exception as e:
                logger.error(f"Failed to load provider '{name}': {e}")
                self._failures.setdefault(namespace, {})[name] = f"load failed: {e}"
                return None
            if self._rejected_by_base_class(namespace, name, provider_class, base_class):
                return None
            self._failures.get(namespace, {}).pop(name, None)
            return provider_class

        return None

    def list_available_providers(self, namespace: str) -> list[str]:
        """List provider names in a namespace by loading them (historical semantics)."""
        return list(self.discover_providers(namespace).keys())

    def list_registered(self, namespace: str) -> list[str]:
        """List registered entry-point names WITHOUT importing anything.

        For offline enumeration (startup validation, catalog generators) where
        loading a provider is unwanted or impossible.
        """
        try:
            return [entry_point.name for entry_point in entry_points(group=namespace)]
        except Exception as e:
            logger.error(f"Entry-points enumeration failed for namespace '{namespace}': {e}")
            return []

    def clear_cache(self) -> None:
        """Clear the discovery cache (the failure ledger persists until a success clears it)."""
        self._cache.clear()

    def _rejected_by_base_class(
        self, namespace: str, name: str, obj: object, base_class: type | None
    ) -> bool:
        if base_class is None:
            return False
        if isinstance(obj, type) and issubclass(obj, base_class):
            return False
        logger.warning(f"Provider '{name}' rejected: not a {base_class.__name__} subclass")
        self._failures.setdefault(namespace, {})[name] = f"not a {base_class.__name__} subclass"
        return True
