"""Regression checks for unique, validated runtime placement (not DOS parity)."""
import shlex
import unittest
from pathlib import Path

from probe_timer_runtime import EXE, locate_timer_wait


class SnapshotQmp:
    def __init__(self, ram):
        self.ram = ram

    def hmp(self, command):
        words = shlex.split(command)
        assert words[:3] == ['pmemsave', '0x100000', '0xF00000']
        Path(words[3]).write_bytes(self.ram)
        return ''


@unittest.skipUnless(EXE.is_file(), 'requires the supplied unpatched game tree')
class TimerPlacementTests(unittest.TestCase):
    def setUp(self):
        self.exe = EXE.read_bytes()
        self.ram = bytearray(0xF00000)

    def instance(self, offset, timer=0x1E21BA):
        code = bytearray(self.exe[0x8F032:0x8F070])
        code[0x38:0x3C] = timer.to_bytes(4, 'little')
        self.ram[offset:offset + len(code)] = code

    def test_relocated_wait_independent_of_sampled_pc(self):
        self.instance(0xB3D8E)
        self.assertEqual(locate_timer_wait(SnapshotQmp(self.ram), self.exe),
                         (0x124D5C, 0x1E21BA))

    def test_ambiguous_instance_is_rejected(self):
        self.instance(0xB3D8E)
        self.instance(0x100)
        with self.assertRaisesRegex(RuntimeError, 'expected one'):
            locate_timer_wait(SnapshotQmp(self.ram), self.exe)

    def test_changed_branch_is_rejected(self):
        self.instance(0xB3D8E)
        self.ram[0xB3D8E + 0x3C] = 0x76
        with self.assertRaisesRegex(RuntimeError, 'expected one'):
            locate_timer_wait(SnapshotQmp(self.ram), self.exe)

    def test_short_snapshot_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'short RAM'):
            locate_timer_wait(SnapshotQmp(bytes(10)), self.exe)


if __name__ == '__main__':
    unittest.main()
