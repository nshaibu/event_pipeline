import typing
from event_pipeline.utils import generate_unique_id, get_obj_klass_import_str


class ObjectIdentityMixin:

    def __init__(self, *args, **kwargs):
        generate_unique_id(self)

    @property
    def id(self):
        return generate_unique_id(self)

    @property
    def __object_import_str__(self):
        return get_obj_klass_import_str(self)

    def get_state(self) -> typing.Dict[str, typing.Any]:
        raise NotImplementedError()

    def set_state(self, state: typing.Dict[str, typing.Any]) -> None:
        raise NotImplementedError()

    def __setstate__(self, state):
        self.set_state(state)

    def __getstate__(self):
        return self.get_state()
