import unittest

from work_list import missing_types, work_list


def record(harness, **fields):
    """A log_parser record of an automatic harness, verified unless overridden."""
    result = {
        'harness': harness, 'is_autoharness': True, 'autoharness_result': 'ok',
        'with_contract': False, 'crate': 'core', 'function': harness,
        'function_safeness': 'safe', 'public_target': False, 'file_name': None,
        'n_failed_properties': 0, 'n_total_properties': 3,
        'result': 'SUCCESSFUL', 'time': '1s', 'output': [],
    }
    result.update(fields)
    return {'thread_id': 0, 'result': result}


def skipped(harness, reason, **fields):
    return record(harness, autoharness_result=reason, n_total_properties=None,
                  result=None, time=None, **fields)


class WorkListTest(unittest.TestCase):

    def test_all_verified_prints_no_table(self):
        out = work_list([record('a::f'), record('a::g', is_autoharness=False, result='FAILED')])
        self.assertIn('Every selected function verified', out)
        self.assertNotIn('| Blocker', out)

    def test_groups_count_and_list_unsafe_first(self):
        out = work_list([
            record('ok::verified'),
            record('vac::nothing', n_total_properties=0),
            record('fail::safe_fn', result='FAILED', n_failed_properties=1),
            record('fail::unsafe_fn', result='FAILED', function_safeness='unsafe',
                   public_target=True, file_name='library/core/src/ptr/mod.rs'),
            record('slow::loop', result='FAILED', time='TO'),
            record('lost::no_result', result=None, n_total_properties=None),
            skipped('gen::f', 'Generic Function: no candidate type satisfies the bounds'),
            skipped('bound::f', 'Requires --bounded-arguments for argument(s) s: &str'),
            skipped('arb::one', MISSING + 'p: NonNull<T>'),
            skipped('arb::two', MISSING + 'p: NonNull<T>, m: HashMap<K, V>'),
            skipped('filtered::f', 'Did not match provided filters'),
            skipped('nobody::f', 'The function does not have a body'),
        ])
        self.assertIn('| Argument type without `kani::Arbitrary` | 2 |', out)
        self.assertIn('| Needs `--bounded-arguments` | 1 |', out)
        self.assertIn('| Generic function | 1 |', out)
        self.assertIn('| Nothing checked (0 properties) | 1 |', out)
        self.assertIn('| Verification failed | 2 |', out)
        self.assertIn('| Timed out | 1 |', out)
        self.assertIn('| Chosen but no result | 1 |', out)
        self.assertNotIn('filtered::f', out)
        self.assertNotIn('nobody::f', out)
        # HashMap<K, V> is one type, not two, and NonNull blocks two functions.
        self.assertIn('- `NonNull<T>`: 2\n- `HashMap<K, V>`: 1', out)
        self.assertIn('<summary>Needs <code>--bounded-arguments</code> (1)</summary>', out)
        self.assertIn('<summary>Verification failed (2)</summary>\n\n'
                      '- `fail::unsafe_fn` (core, unsafe, public) `library/core/src/ptr/mod.rs`\n'
                      '- `fail::safe_fn` (core, safe)', out)

    def test_missing_types_nested_generics(self):
        self.assertEqual(
            missing_types(MISSING + 'a: Option<Result<T, E>>, b: u8'),
            ['Option<Result<T, E>>', 'u8'])


MISSING = 'Missing Arbitrary implementation for argument(s) '

if __name__ == '__main__':
    unittest.main()
