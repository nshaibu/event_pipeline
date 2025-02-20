import unittest
from unittest import mock
from event_pipeline.signal import SoftSignal
from event_pipeline.decorators import listener


class Target(object):
    pass


class Target1(object):
    pass


class Target2(object):
    pass


example_func_signal1 = SoftSignal(provide_args=["country"])
example_func_signal2 = SoftSignal(provide_args=["school", "school_id"])
example_func_signal3 = SoftSignal(provide_args=["country", "town"])


@listener(example_func_signal1, sender=Target)
def example_func_handler1(sender, signal, country):
    return sender, signal, country


def example_func_handler3(sender, signal, country, town):
    return sender, signal, country, town


example_func_signal3.connect(sender=Target1, listener=example_func_handler3)


@listener(example_func_signal2, sender=Target2)
def example_func_handler2(signal, school, school_id):
    return signal, school, school_id


class TestSignal(unittest.TestCase):

    def test_signal_emitter_invokes_handler_function(self):
        responses = example_func_signal1.emit(sender=Target, country="Ghana")
        self.assertIsInstance(responses, list)
        self.assertEqual(len(responses), 1)
        for response in responses:
            self.assertEqual(example_func_handler1.__name__, response[0].__name__)
            self.assertEqual(response[1][2], "Ghana")

    def test_disconnect_remover_listener(self):
        example_func_signal2.disconnect(sender=Target2, listener=example_func_handler2)
        response = example_func_signal2.emit(sender=Target2, school="KNUST", school_id="KNUST")
        self.assertIsInstance(response, list)
        self.assertTrue(len(response) == 0)

    def test_listener_is_removed_when_listener_referent_is_garbage_collected(self):
        global example_func_handler3

        del example_func_handler3

        response = example_func_signal3.emit(sender=Target1, country="Ghana", town="KU")
        self.assertIsInstance(response, list)
        self.assertTrue(len(response) == 0)







