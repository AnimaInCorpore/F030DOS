"""Check route schedules before guest launch; these are harness tests."""
import unittest
from drive_menu import ROOT, validate_script
import json


class ScheduleTests(unittest.TestCase):
    def test_checked_route(self):
        script = json.loads((ROOT / 'work/routes/poland.json').read_text())
        events = validate_script(script, 50)
        self.assertEqual(events[-1]['kind'], 'quit')
        self.assertEqual(len(script['expected_file_opens']), 6)

    def test_invalid_times(self):
        for when in (-1, float('nan'), float('inf'), 50):
            with self.subTest(when=when), self.assertRaises(ValueError):
                validate_script([{'at': when, 'kind': 'quit'}], 50)
        with self.assertRaises(ValueError):
            validate_script([{'at': 2, 'kind': 'quit'}, {'at': 1, 'kind': 'quit'}], 50)

    def test_duplicate_or_unsafe_checkpoints(self):
        with self.assertRaises(ValueError):
            validate_script([{'at': 1, 'kind': 'capture', 'name': '../old-proof'}], 50)
        with self.assertRaises(ValueError):
            validate_script([{'at': 1, 'kind': 'capture', 'name': 'same'},
                             {'at': 2, 'kind': 'capture', 'name': 'same'}], 50)

    def test_unknown_input_kind(self):
        with self.assertRaises(ValueError):
            validate_script([{'at': 1, 'kind': 'poke-game-state'}], 50)


if __name__ == '__main__':
    unittest.main()
