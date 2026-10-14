"""Small semantic controls for the static music inventory, without game data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import mido

spec = importlib.util.spec_from_file_location('analyze_music', Path(__file__).with_name('analyze_music.py'))
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class MusicInventoryTest(unittest.TestCase):
    def test_merged_tracks_tempo_and_note_window(self):
        midi = mido.MidiFile(type=1, ticks_per_beat=100)
        midi.tracks.append(mido.MidiTrack([
            mido.MetaMessage('set_tempo', tempo=500000, time=0),
            mido.MetaMessage('set_tempo', tempo=1000000, time=100),
            mido.MetaMessage('end_of_track', time=100)]))
        midi.tracks.append(mido.MidiTrack([
            mido.Message('program_change', program=9, time=0),
            mido.Message('note_on', note=60, time=0),
            mido.Message('note_on', note=64, time=10),
            mido.Message('note_on', note=67, time=10),
            mido.Message('note_off', note=60, time=10),
            mido.Message('note_off', note=64, time=10),
            mido.Message('note_off', note=67, time=10)]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fixture.mid'
            midi.save(path)
            result = music.analyze(path, 151)
            self.assertAlmostEqual(result['seconds'], 1.5)
            self.assertEqual(result['peak_key_down_after_tick'], 3)
            self.assertEqual(result['peak_note_ons_in_window'], 3)
            self.assertEqual(result['peak_note_ons_same_tick'], 1)
            self.assertEqual(result['programs_at_note_on'], {'9': 3})
            self.assertEqual(result['remaining_key_down'], 0)
            self.assertEqual(result['unmatched_note_offs'], 0)
            with self.assertRaises(ValueError):
                music.validate_chunks(path.read_bytes()[:-1])

    def test_fragmented_sysex(self):
        # One Roland write split across an F0 start and an F7 continuation.
        track = bytes.fromhex('00f00741101612050000 00f703017af7 00ff2f00')
        data = bytes.fromhex('4d54686400000006000000010060 4d54726b')
        data += len(track).to_bytes(4, 'big') + track
        result = music.sysex_only_messages(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['address'], '050000')
        self.assertEqual(result[0]['data_bytes'], 1)
        self.assertTrue(result[0]['roland_checksum_valid'])
        corrupt = data.replace(bytes.fromhex('017af7'), bytes.fromhex('017bf7'))
        self.assertFalse(music.sysex_only_messages(corrupt)[0]['roland_checksum_valid'])


if __name__ == '__main__':
    unittest.main()
