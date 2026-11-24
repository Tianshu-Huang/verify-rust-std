import datetime
import unittest

from autoharness_history import record, series
from test_coverage_summary import MISSING, analyzer_output


def result(harness, outcome):
    return {'result': {'harness': harness, 'is_autoharness': True,
                       'result': outcome, 'time': '1s'}}


COVERAGE = analyzer_output(
    (['a', 'b'], {'c': MISSING, 'kani_harness': 'Kani implementation'}),
    alloc=(['d'], {}))
RESULTS = [result('a', 'SUCCESSFUL'), result('b', 'FAILED')]


def entry(date, **crates):
    return {'date': date, 'crates': {
        crate: {'generated': generated, 'total': total}
        for crate, (generated, total) in crates.items()}}


class AutoharnessHistoryTest(unittest.TestCase):
    def test_record_appends_a_point(self):
        history = record([entry('2026-01-01', core=(1, 2))], COVERAGE,
                         RESULTS, '2026-01-08', 'https://example.org/run/1')
        self.assertEqual(history[-1], {
            'date': '2026-01-08',
            # Kani's own functions are not library functions.
            'crates': {'core': {'generated': 2, 'total': 3},
                       'alloc': {'generated': 1, 'total': 1},
                       'std': {'generated': 0, 'total': 0}},
            'verified_in_ci': 1,
            'run': 'https://example.org/run/1'})
        self.assertEqual(len(history), 2)

    def test_record_replaces_the_point_of_the_same_day(self):
        history = record([entry('2026-01-08', core=(1, 2))], COVERAGE,
                         RESULTS, '2026-01-08')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['verified_in_ci'], 1)

    def test_record_skips_a_run_without_harnesses(self):
        empty = analyzer_output(([], {'c': MISSING}))
        history = [entry('2026-01-01', core=(1, 2))]
        self.assertEqual(record(history, empty, [], '2026-01-08'), history)

    def test_series_sums_only_crates_every_point_has(self):
        crates, points = series([
            entry('2026-01-01', core=(10, 20), std=(1, 2)),
            entry('2026-01-15', core=(11, 20), std=(1, 2), alloc=(5, 9))])
        self.assertEqual(crates, ['core', 'std'])
        self.assertEqual(points, [
            (datetime.date(2026, 1, 1), 11, 22),
            (datetime.date(2026, 1, 15), 12, 22)])

    def test_series_drops_points_older_than_the_window(self):
        _, points = series([entry('2025-01-01', core=(1, 2)),
                            entry('2026-06-01', core=(3, 4))])
        self.assertEqual(points, [(datetime.date(2026, 6, 1), 3, 4)])


if __name__ == '__main__':
    unittest.main()
