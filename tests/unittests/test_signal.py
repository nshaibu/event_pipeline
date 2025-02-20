import unittest
from event_pipeline.signal import SoftSignal
from event_pipeline.decorators import listener


class TestSignal(unittest.TestCase):
    def setUp(self):
        class Target(object):
            pass

        class Target1(object):
            pass

        class Target2(object):
            pass

        self.example_func_signal1 = SoftSignal(provide_args=["country"])
        self.example_obj_signal2 = SoftSignal(provide_args=["school", "school_id"])
        self.example_any_signal3 = SoftSignal(provide_args=["country", "town"])

        @listener(self.example_func_signal1, sender=Target)
        def example_func_signal1(sender, signal, country):
            return sender, signal, country

        def example_func_signal2(sender, signal, town):
            return sender, signal, town

        self.example_any_signal3.connect(sender=Target1, listener=example_func_signal2)




