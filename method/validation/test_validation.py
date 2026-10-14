"""N/A - adversarial invariants for shared analysis tools."""
import unittest
from validation.flags import Node, liveness
from validation.checkpoints import compare, byte_difference
from validation.profile import summarize


class ValidationTests(unittest.TestCase):
    def test_loop_and_unknown_exit(self):
        nodes = {0: Node(0, 3, (1,)), 1: Node(1, 0, (0, 2)), 2: Node(0, 0, (99,))}
        incoming, outgoing = liveness(nodes, 3)
        self.assertEqual(incoming[0], 0)
        self.assertEqual(outgoing[0], 3)
        self.assertEqual(incoming[2], 3)

    def test_partial_flags_and_call(self):
        incoming, _ = liveness({0: Node(0, 2, (1,)), 1: Node(1, 0, (), True)}, 3)
        self.assertEqual(incoming[0], 1)

    def test_clock_is_not_state(self):
        expected = [{'key': 'pass1:21', 'state': {'x': 7}, 'wall': 100}]
        actual = [{'key': 'pass1:21', 'state': {'x': 7}, 'wall': 800}]
        self.assertEqual(compare(expected, actual, ['x'])['status'], 'PASS')
        actual[0]['state']['x'] = 8
        self.assertEqual(compare(expected, actual, ['x'])['first']['field'], 'x')

    def test_missing_duplicate_reordered_and_extra(self):
        rows = [{'key': i, 'state': {'x': i}} for i in range(2)]
        for actual in (rows[:1], rows[::-1], rows + [{'key': 2, 'state': {'x': 2}}]):
            self.assertEqual(compare(rows, actual, ['x'])['status'], 'DIVERGENCE')
        with self.assertRaises(ValueError):
            compare(rows, [rows[0], rows[0]], ['x'])
        with self.assertRaises(ValueError):
            compare(rows, [{'key': 0, 'state': {}}], ['x'])
        with self.assertRaises(ValueError):
            compare([], [], ['x'])

    def test_exact_types_and_byte_lengths(self):
        self.assertEqual(compare([{'key': 0, 'state': {'x': 1}}],
                                 [{'key': 0, 'state': {'x': True}}], ['x'])['status'], 'DIVERGENCE')
        self.assertEqual(byte_difference(b'abc', b'ab')['offset'], 2)
        self.assertEqual(byte_difference(b'abc', b'axc')['offset'], 1)

    def test_profile_identity_mapping_and_zero_work(self):
        mapping = {'sourceSha256': 'dos', 'generatedSha256': 'native', 'linkedSha256': 'linked',
                   'sites': [{'label': 'pc1', 'functionId': 'sub_1', 'pc': 1}]}
        trace = {'sourceSha256': 'dos', 'generatedSha256': 'native', 'linkedSha256': 'linked',
                 'checkpoints': [0, 1], 'events': [{'checkpoint': 0, 'label': 'pc1', 'cycles': 12}]}
        self.assertEqual(summarize(mapping, trace)['cyclesPerCheckpoint'], 6)
        trace['generatedSha256'] = 'stale'
        with self.assertRaises(ValueError):
            summarize(mapping, trace)
        trace['generatedSha256'] = 'native'
        trace['events'][0]['label'] = 'unknown'
        with self.assertRaises(ValueError):
            summarize(mapping, trace)


if __name__ == '__main__':
    unittest.main()
