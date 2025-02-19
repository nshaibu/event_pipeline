from abc import ABC, abstractmethod


class Connection(ABC):

    def __init__(self, connection):
        pass

    def runshell(self):
        raise NotImplementedError
