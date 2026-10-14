#!/usr/bin/env python3
"""N/A - replay comparison negative controls; no game behaviour implemented."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('boundary', Path(__file__).with_name('compare-boundary-traces.py'))
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


class ComparisonTests(unittest.TestCase):
    def rows(self):
        expected = {21: {field: 0 for field in boundary.FIELDS + boundary.VIEW_FIELDS}}
        actual = {21: dict(expected[21], variant=0)}
        return expected, actual

    def test_missing_on_both_sides_is_unproven(self):
        expected, actual = self.rows()
        del expected[21][boundary.FIELDS[0]]
        del actual[21][boundary.FIELDS[0]]
        self.assertEqual(boundary.compare('68030', 'falcon', expected, actual, 1)['status'], 'Unproven')

    def test_first_different_cursor_field(self):
        expected, actual = self.rows()
        actual[21][boundary.FIELDS[1]] = 1
        result = boundary.compare('68030', 'falcon', expected, actual, 1)
        self.assertEqual(result['first_divergence']['cursor'], 21)
        self.assertEqual(result['first_divergence']['field'], boundary.FIELDS[1])

    def test_timestamps_do_not_change_alignment(self):
        expected, actual = self.rows()
        expected[21]['timestamp'] = 1
        actual[21]['timestamp'] = 20
        self.assertEqual(boundary.compare('68030', 'falcon', expected, actual, 1)['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
