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
            # Nothing a contributor can unblock.
            'no_body': ('The function does not have a body', 'safe', []),
            'kani': ('Kani implementation', 'unsafe', []),
        })
        self.assertEqual(work_list(directory), '\n'.join([
            '### Where autoharness needs help',
            '',
            '| No harness because | Functions | Unsafe | What unblocks them |',
            '| --- | ---: | ---: | --- |',
            '| generic function | 1 | 0 '
            '| write a harness that calls it with one concrete type |',
            '| an argument type has no `kani::Arbitrary` | 3 | 1 '
            '| implement `kani::Arbitrary` for the type, or write a harness '
            'that builds the argument |',
            '| needs `--bounded-arguments` | 1 | 0 '
            '| write a harness that bounds the argument |',
            '',
            '<details><summary>Argument types, by functions they block (3)'
            '</summary>',
            '',
            '- `&mut i32`: 2',
            '- `*const u8`: 2',
            '- `&[u8]`: 1',
            '',
            '</details>',
            '',
            '<details><summary>generic function (1)</summary>',
            '',
            '- `core: generic`',
            '',
            '</details>',
            '',
            '<details><summary>an argument type has no '
            '<code>kani::Arbitrary</code> (3)</summary>',
            '',
            '- `core: c_unsafe` (unsafe)',
            '- `core: a_safe`',
            '- `core: b_safe`',
            '',
            '</details>',
            '',
            '<details><summary>needs <code>--bounded-arguments</code> (1)'
            '</summary>',
            '',
            '- `core: bounded`',
            '',
            '</details>',
            '',
        ]))

    def test_nothing_blocked(self):
        self.assertIn('Autoharness generates a harness for every function.',
                      work_list(analyzer_output({})))


if __name__ == '__main__':
    unittest.main()
