from abc import ABC, abstractmethod


class SchemaBase(ABC):

    @abstractmethod
    def validate(self, schema):
        pass

    @abstractmethod
    def serialize(self, schema):
        pass

    @abstractmethod
    def create_in_storage(self):
        pass
