import unittest

from autoharness_report import comment, status
from coverage_summary import read
from results_summary import harness_verdicts
from test_coverage_summary import BASE, HEAD


def verdicts(**harnesses):
    """Verdicts of automatic harnesses given as name='SUCCESSFUL' or 'FAILED'."""
    return harness_verdicts([
        {'result': {'harness': name, 'is_autoharness': True,
                    'result': result, 'time': '1'}}
        for name, result in harnesses.items()])


class StatusTest(unittest.TestCase):
    def test_status(self):
        text = status(BASE, verdicts(kept='SUCCESSFUL'), 'Nov 10, 2026',
                      'https://example.com/chart.png', 'Nov 9, 2026')
        # 4 of 8 functions: Kani's own are not counted.
        self.assertTrue(text.startswith(
            '# 50%\nof the functions in core, alloc and std have a harness\n'))
        self.assertIn('over time](https://example.com/chart.png)\n\n<sub>Updated '
                      'every week · last updated Nov 9, 2026</sub>', text)
        self.assertIn('in core, alloc and std | 8 | 100% |', text)
        self.assertIn('Most have not been run yet | 4 | 50% |', text)
        self.assertIn('Kani proved it | 1 | 12% |', text)
        self.assertIn('last updated Nov 10, 2026', text)
        self.assertIn('### Why 4 functions have no harness yet', text)


class CommentTest(unittest.TestCase):
    def comment(self, head, base, coverage=(BASE, BASE)):
        return comment(read(coverage[0]), head, read(coverage[1]), base,
                       'Nov 10 · 8089282', 'https://example.com/status')

    def test_newly_verified(self):
        text = self.comment(verdicts(kept='SUCCESSFUL', broken='SUCCESSFUL'),
                            verdicts(kept='SUCCESSFUL'))
        self.assertTrue(text.startswith(
            '## +1 harness verified in CI\n\n**What this means:** CI now '
            'proves 1 more function on every pull request. Which functions '
            'have a harness did not change.\n'))
        self.assertIn('| Step |  | Main<br>Nov 10 · 8089282 '
                      '| This pull request |', text)
        self.assertIn('Kani proved it | █████░░░░░░░░░░░░░░░ | 1 | **2** (+1) |',
                      text)
        self.assertIn('**Newly verified**\n\n- `broken`', text)
        self.assertIn('Compared with `main` at Nov 10, commit 8089282.', text)
        self.assertIn('[Autoharness status](https://example.com/status)', text)

    def test_regression_comes_first(self):
        text = self.comment(verdicts(kept='FAILED', broken='SUCCESSFUL'),
                            verdicts(kept='SUCCESSFUL'))
        self.assertTrue(text.startswith(
            '## ✗ 1 harness no longer verifies\n\n**What this means:** '
            'A proof that passes on `main` fails with this change. Fix it '
            'before merging. CI now proves 1 more function'))
        self.assertIn('**No longer verified**\n\n- `kept`', text)

    def test_harness_changes(self):
        text = self.comment(verdicts(), verdicts(), coverage=(HEAD, BASE))
        self.assertTrue(text.startswith(
            '## +3 functions can now get a harness\n'))
        self.assertIn('Autoharness can no longer write a harness for '
                      '2 functions that had one on `main`.', text)
        self.assertIn('| 4 | **6** (+2) |', text)
        self.assertIn('**Can now get a harness**\n\n- `core: added`', text)

    def test_no_change(self):
        text = self.comment(verdicts(kept='SUCCESSFUL'),
                            verdicts(kept='SUCCESSFUL'))
        self.assertTrue(text.startswith(
            '## No change to the autoharness results\n'))
        self.assertNotIn('(+', text)

    def test_without_main(self):
        text = comment(read(BASE), verdicts(kept='SUCCESSFUL'))
        self.assertTrue(text.startswith('## Autoharness results\n'))
        self.assertIn('| Step |  | This pull request |', text)
        self.assertNotIn('Compared with', text)


if __name__ == '__main__':
    unittest.main()
