"""N/A - production-pipeline flag and byte-boundary regression tests."""
import hashlib
import unittest
import translate as T


def compile_bytes(code, optimize=True):
    build = T.Build('synthetic instruction test', code, hashlib.sha256(code).hexdigest(), [(0x1000, 0, 'test_fn')])
    return T.translate('test_fn', build, optimize=optimize)


class TranslatorTests(unittest.TestCase):
    def test_dead_compare_removed_and_live_compare_kept(self):
        # cmp eax,0; add eax,1; je ret; nop; ret
        code = bytes.fromhex('83f80083c001740190c3')
        optimized, info = compile_bytes(code)
        baseline, _ = compile_bytes(code, False)
        self.assertEqual(info['deadFlagInstructions'], [0x1000])
        self.assertNotIn('cmpi.l #$0,d0', '\n'.join(optimized))
        self.assertIn('cmpi.l #$0,d0', '\n'.join(baseline))
        self.assertIn('x86_pc_test_fn_1000:', optimized)

    def test_return_and_call_observe_flags(self):
        _, info = compile_bytes(bytes.fromhex('83f800c3'))
        self.assertEqual(info['deadFlagInstructions'], [])
        _, info = compile_bytes(bytes.fromhex('83f800e8f8ffffffc3'))
        self.assertEqual(info['deadFlagInstructions'], [])

    def test_undefined_flags_are_not_proven_kills(self):
        # TEST leaves AF undefined: an unknown return contract may observe it.
        _, info = compile_bytes(bytes.fromhex('83f80085c0740190c3'))
        self.assertEqual(info['deadFlagInstructions'], [])

    def test_preserved_ccr_does_not_need_capture(self):
        # cmp eax,0; mov ebp,esp; je ret; nop; ret
        code = bytes.fromhex('83f80089e5740190c3')
        _, fast = compile_bytes(code)
        _, slow = compile_bytes(code, False)
        self.assertEqual((fast['conditionCaptures'], slow['conditionCaptures']), (0, 1))

    def test_move_still_needs_capture(self):
        _, info = compile_bytes(bytes.fromhex('83f80089da740190c3'))
        self.assertEqual(info['conditionCaptures'], 1)

    def test_result_move_reuses_only_sign_zero(self):
        # test eax,eax; mov edx,eax; jz ret; nop; ret
        _, info = compile_bytes(bytes.fromhex('85c089c2740190c3'))
        self.assertEqual(info['conditionCaptures'], 0)
        _, info = compile_bytes(bytes.fromhex('85c089c2720190c3'))
        self.assertEqual(info['conditionCaptures'], 1)

    def test_captured_branch_clobbers_result_flags(self):
        # test eax,eax; mov edx,eax; jb ret; je ret; nop; ret
        # jb captures C; its native tst must not masquerade as eax's N/Z.
        with self.assertRaisesRegex(T.Unsupported, 'second captured condition'):
            compile_bytes(bytes.fromhex('85c089c27203740190c3'))

    def test_intervening_multiply_cannot_reuse_earlier_flags(self):
        with self.assertRaisesRegex(T.Unsupported, 'changes x86 flags'):
            compile_bytes(bytes.fromhex('83f8000fafc3740190c3'))

    def test_interior_entry_is_refused(self):
        with self.assertRaisesRegex(T.Unsupported, 'overlapping'):
            compile_bytes(bytes.fromhex('b80100000075fac3'))

    def test_cf_and_zero_shift_are_conservative(self):
        with self.assertRaisesRegex(T.Unsupported, 'needs CF'):
            compile_bytes(bytes.fromhex('40 7201 90 c3'))
        ins = next(T.CS.disasm(bytes.fromhex('d3e0'), 0x1000))
        reads, writes = T.flag_effects(ins)
        self.assertTrue(reads)
        self.assertEqual(writes, 0)


if __name__ == '__main__':
    unittest.main()
