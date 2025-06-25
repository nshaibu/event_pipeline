from typing import Type, Set, Iterator, Dict, List
from collections import deque
import weakref
from functools import lru_cache


class EventBase:
    """Improved EventBase with optimized class discovery"""

    # Class-level registry to cache discovered subclasses
    _subclass_registry: Dict[Type, Set[Type]] = {}

    # WeakSet to automatically clean up when classes are garbage collected
    _all_event_classes: "weakref.WeakSet[Type[EventBase]]" = weakref.WeakSet()

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses when they're defined"""
        super().__init_subclass__(**kwargs)

        # Register this class in the global registry
        EventBase._all_event_classes.add(cls)

        # Clear the cache for affected parent classes
        for parent in cls.__mro__[1:]:  # Skip self
            if parent in EventBase._subclass_registry:
                del EventBase._subclass_registry[parent]

    @classmethod
    @lru_cache(maxsize=128)
    def get_event_klasses(cls) -> frozenset:
        """
        Optimized version using breadth-first search with caching.
        Returns frozenset for immutability and better caching.
        """
        if cls in cls._subclass_registry:
            return frozenset(cls._subclass_registry[cls])

        # Use BFS instead of DFS to avoid deep recursion
        discovered = set()
        queue = deque([cls])
        visited = set()

        while queue:
            current_class = queue.popleft()

            if current_class in visited:
                continue
            visited.add(current_class)

            # Get direct subclasses
            for subclass in current_class.__subclasses__():
                if subclass not in discovered:
                    discovered.add(subclass)
                    queue.append(subclass)

        # Cache the result
        cls._subclass_registry[cls] = discovered
        return frozenset(discovered)

    @classmethod
    def get_all_event_classes(cls) -> Set[Type["EventBase"]]:
        """
        Alternative approach: return all registered event classes.
        This is O(1) but returns ALL event classes, not just subclasses.
        """
        return set(cls._all_event_classes)

    @classmethod
    def get_direct_subclasses(cls) -> Set[Type["EventBase"]]:
        """Get only direct subclasses (one level down)"""
        return set(cls.__subclasses__())

    @classmethod
    def clear_class_cache(cls):
        """Clear the cached subclass registry"""
        cls._subclass_registry.clear()
        # Clear LRU cache
        cls.get_event_klasses.cache_clear()


# Alternative implementation using a dedicated registry
class EventRegistry:
    """Centralized registry for event classes with better performance"""

    def __init__(self):
        self._classes: Set[Type[EventBase]] = set()
        self._hierarchy_cache: Dict[Type, Set[Type]] = {}
        self._parent_to_children: Dict[Type, Set[Type]] = {}

    def register(self, event_class: Type[EventBase]):
        """Register an event class"""
        self._classes.add(event_class)

        # Build parent-child relationships
        for parent in event_class.__mro__[1:]:  # Skip self
            if issubclass(parent, EventBase):
                if parent not in self._parent_to_children:
                    self._parent_to_children[parent] = set()
                self._parent_to_children[parent].add(event_class)

        # Invalidate cache for affected parents
        for parent in event_class.__mro__[1:]:
            if parent in self._hierarchy_cache:
                del self._hierarchy_cache[parent]

    def get_subclasses(self, base_class: Type[EventBase]) -> Set[Type[EventBase]]:
        """Get all subclasses of a given base class efficiently"""
        if base_class in self._hierarchy_cache:
            return self._hierarchy_cache[base_class]

        # Build subclass set iteratively
        subclasses = set()
        queue = deque([base_class])

        while queue:
            current = queue.popleft()
            if current in self._parent_to_children:
                children = self._parent_to_children[current]
                subclasses.update(children)
                queue.extend(children)

        # Cache the result
        self._hierarchy_cache[base_class] = subclasses
        return subclasses

    def get_all_classes(self) -> Set[Type[EventBase]]:
        """Get all registered event classes"""
        return self._classes.copy()


# Global registry instance
event_registry = EventRegistry()


class ImprovedEventBase:
    """EventBase using the centralized registry"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        event_registry.register(cls)

    @classmethod
    def get_event_klasses(cls) -> Set[Type["ImprovedEventBase"]]:
        """Get all subclasses using the centralized registry"""
        return event_registry.get_subclasses(cls)


# Lazy loading approach
class LazyEventBase:
    """EventBase with lazy loading of subclasses"""

    _subclass_cache: Dict[Type, Set[Type]] = {}
    _cache_valid: Dict[Type, bool] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Invalidate caches when new subclasses are created
        LazyEventBase._cache_valid.clear()

    @classmethod
    def get_event_klasses(cls) -> Set[Type["LazyEventBase"]]:
        """Lazy-loaded subclass discovery with invalidation"""

        # Check if cache is valid
        if cls in cls._cache_valid and cls._cache_valid[cls]:
            return cls._subclass_cache[cls]

        # Rebuild cache
        subclasses = set()
        for candidate in cls._get_all_classes():
            if issubclass(candidate, cls) and candidate != cls:
                subclasses.add(candidate)

        cls._subclass_cache[cls] = subclasses
        cls._cache_valid[cls] = True
        return subclasses

    @classmethod
    def _get_all_classes(cls):
        """Get all classes in the module/package - implement based on your needs"""
        import gc

        return [
            obj
            for obj in gc.get_objects()
            if isinstance(obj, type) and issubclass(obj, LazyEventBase)
        ]


# Performance comparison utility
def benchmark_approaches():
    """Utility to benchmark different approaches"""
    import time
    from typing import Type

    # Create a deep hierarchy for testing
    class Level0(EventBase):
        pass

    class Level1(Level0):
        pass

    class Level2(Level1):
        pass

    class Level3(Level2):
        pass

    class Level4(Level3):
        pass

    def time_approach(func, iterations=1000):
        start = time.perf_counter()
        for _ in range(iterations):
            result = func()
        end = time.perf_counter()
        return end - start, len(result)

    # Benchmark original recursive approach vs optimized
    print("Benchmarking class discovery approaches...")

    # Clear caches
    EventBase.clear_class_cache()

    time_taken, count = time_approach(lambda: EventBase.get_event_klasses())
    print(f"Optimized BFS: {time_taken:.4f}s for {count} classes")

    time_taken, count = time_approach(lambda: EventBase.get_all_event_classes())
    print(f"Registry approach: {time_taken:.4f}s for {count} classes")


if __name__ == "__main__":
    benchmark_approaches()
