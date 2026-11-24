import json
import os
import tempfile
import unittest

from work_list import work_list

MISSING = 'Missing Arbitrary implementation for argument(s)'
BOUNDED = 'Requires --bounded-arguments for argument(s)'


def analyzer_output(core):
    """Directory with analyzer JSON; `core` maps function -> (reason,
    safety, types). alloc and std are empty."""
    directory = tempfile.mkdtemp()
    for crate, skipped in [('core', core), ('alloc', {}), ('std', {})]:
        path = os.path.join(directory, f'{crate}_autoharness_data.json')
        with open(path, 'w') as f:
            json.dump({'chosen': [['fine', 'safe']], 'skipped': {
                name: {'reason': reason, 'safety': safety, 'types': types}
                for name, (reason, safety, types) in skipped.items()}}, f)
    return directory


class WorkListTest(unittest.TestCase):
    def test_groups_by_blocker(self):
        directory = analyzer_output({
            'generic': ('Generic Function', 'safe', []),
            'b_safe': (MISSING, 'safe', ['&mut i32']),
            'c_unsafe': (MISSING, 'unsafe', ['&mut i32', '*const u8']),
            # The same type twice blocks this function once.
            'a_safe': (MISSING, None, ['*const u8', '*const u8']),
            'bounded': (BOUNDED, 'safe', ['&[u8]']),
            'no_body': ('The function does not have a body', 'safe', []),
            'kani': ('Kani implementation', 'unsafe', []),
        })
        self.assertEqual(work_list(directory), '\n'.join([
            '### Why 6 functions have no harness yet',
            '',
            'To write a harness, autoharness has to call the function '
            'with made-up arguments. It gets stuck in the ways below. '
            'All of them are fixed in Kani, not in this repository.',
            '',
            '#### 1. Kani cannot make up a value for an argument',
            '',
            '**3 functions** (50%) · tracked in '
            '[kani#4887](https://redirect.github.com/model-'
            'checking/kani/issues/4887), '
            '[kani#5137](https://redirect.github.com/model-'
            'checking/kani/issues/5137)',
            '',
            'Some argument types are ones Kani does not know how to '
            'make up.',
            '',
            '```rust',
            'fn exists(path: &Path) -> io::Result<bool>   // Kani '
            'cannot make up a &Path',
            '```',
            '',
            '<details><summary>Which types cause this, most common '
            'first (2 types)</summary>',
            '',
            '- `&mut i32`: 2 functions',
            '- `*const u8`: 2 functions',
            '',
            '</details>',
            '',
            '<details><summary>3 functions, unsafe first</summary>',
            '',
            '- `core: c_unsafe` (unsafe)',
            '- `core: a_safe`',
            '- `core: b_safe`',
            '',
            '</details>',
            '',
            '#### 2. The function is generic',
            '',
            '**1 function** (17%) · tracked in '
            '[kani#4888](https://redirect.github.com/model-'
            'checking/kani/issues/4888), '
            '[kani#4889](https://redirect.github.com/model-'
            'checking/kani/issues/4889)',
            '',
            'A generic function works for many types. Autoharness has '
            'to pick one to test with, and here it found none.',
            '',
            '```rust',
            'fn max_by<T, F>(v1: T, v2: T, compare: F) -> T   // which '
            'types should T and F be?',
            '```',
            '',
            '<details><summary>1 function, unsafe first</summary>',
            '',
            '- `core: generic`',
            '',
            '</details>',
            '',
            '#### 3. An argument can be any length',
            '',
            '**1 function** (17%) · tracked in '
            '[kani#4890](https://redirect.github.com/model-'
            'checking/kani/issues/4890)',
            '',
            'The argument is a string or a slice. Kani can only test it'
            ' up to a maximum length, and CI does not set one.',
            '',
            '```rust',
            'fn from_utf8(v: &[u8]) -> Result<&str, Utf8Error>   // v '
            'can be any length',
            '```',
            '',
            '<details><summary>Which types cause this, most common '
            'first (1 type)</summary>',
            '',
            '- `&[u8]`: 1 function',
            '',
            '</details>',
            '',
            '<details><summary>1 function, unsafe first</summary>',
            '',
            '- `core: bounded`',
            '',
            '</details>',
            '',
            'The remaining 1 function (17%) has other reasons, such as'
            ' a function with no body.',
            '',
        ]))

    def test_long_lists_say_how_much_they_show(self):
        text = work_list(analyzer_output({
            f'f{i:02}': (MISSING, 'safe', [f'T{i:02}']) for i in range(51)}))
        self.assertIn('<summary>The 50 types that cause this most often, '
                      'of 51</summary>', text)
        self.assertIn('<summary>The first 50 of 51 functions, unsafe first'
                      '</summary>', text)
        self.assertEqual(text.count('- and 1 more'), 2)

    def test_nothing_blocked(self):
        self.assertIn('Autoharness writes a harness for every function.',
                      work_list(analyzer_output({})))


if __name__ == '__main__':
    unittest.main()
