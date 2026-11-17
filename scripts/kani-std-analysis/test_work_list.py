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
            '| Reason | | Functions | Share | Where to help |',
            '| --- | --- | ---: | ---: | --- |',
            '| Kani cannot create a value for one of the argument types '
            '| ████████████ | 3 | 50% '
            '| [kani#4887](https://redirect.github.com/model-checking/kani/issues/4887), [kani#5137](https://redirect.github.com/model-checking/kani/issues/5137) |',
            '| The function is generic and autoharness has no type to pick '
            '| ████ | 1 | 17% '
            '| [kani#4888](https://redirect.github.com/model-checking/kani/issues/4888), [kani#4889](https://redirect.github.com/model-checking/kani/issues/4889) |',
            '| An argument needs a size limit | ████ | 1 | 17% '
            '| [kani#4890](https://redirect.github.com/model-checking/kani/issues/4890) |',
            # Kani's own functions are not counted.
            '| Other | ████ | 1 | 17% |  |',
            '',
            'These are fixed in Kani, not in this repository. The numbers '
            'move when a pull request here updates the Kani version.',
            '',
            '**The functions, one by one**',
            '',
            '<details><summary>Argument types that block the most functions '
            '(3 types)</summary>',
            '',
            '- `&mut i32`: 2',
            '- `*const u8`: 2',
            '- `&[u8]`: 1',
            '',
            '</details>',
            '',
            '<details><summary>Functions blocked by an argument type '
            '(3, of which 1 unsafe)</summary>',
            '',
            '- `core: c_unsafe` (unsafe)',
            '- `core: a_safe`',
            '- `core: b_safe`',
            '',
            '</details>',
            '',
            '<details><summary>Generic functions (1, of which 0 unsafe)'
            '</summary>',
            '',
            '- `core: generic`',
            '',
            '</details>',
            '',
            '<details><summary>Functions that need a size limit '
            '(1, of which 0 unsafe)</summary>',
            '',
            '- `core: bounded`',
            '',
            '</details>',
            '',
        ]))

    def test_nothing_blocked(self):
        self.assertIn('Autoharness writes a harness for every function.',
                      work_list(analyzer_output({})))


if __name__ == '__main__':
    unittest.main()
