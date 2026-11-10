#!/usr/bin/env python3

"""
Summarize which library functions autoharness can generate a harness for, as
Markdown for a CI job summary. Given a directory with the
`<crate>_autoharness_data.json` files that scripts/autoharness_analyzer writes,
```
python3 coverage_summary.py coverage/ [--base base-coverage/]
```
prints how many functions get a harness and how many do not, by reason. With
`--base` (the same files from another run, typically of the base branch) it
also prints the change in each count and lists the functions that gained or
lost their harness.

The analyzer only generates harnesses; it does not run them. Whether a harness
verifies is what `results_summary.py` reports.
"""

import argparse
import collections
import json
import os

from results_summary import change_row, code_span, listed

CRATES = ['core', 'alloc', 'std']
GENERATED = 'harness generated'
# Skip reasons with a row of their own, as the analyzer spells them.
REASONS = {
    'Generic Function': 'generic function',
    'Missing Arbitrary implementation for argument(s)':
        'an argument type has no `kani::Arbitrary`',
    'Requires --bounded-arguments for argument(s)':
        'needs `--bounded-arguments`',
}
OTHER = 'other reason'
# Not library functions somebody could unblock: Kani's own harnesses and
# contract instrumentation, and functions a run with filters did not look at.
NOT_COUNTED = ['Kani implementation', 'Did not match provided filters']
ROWS = [GENERATED] + list(REASONS.values()) + [OTHER]


def load(directory):
    """Yield (crate, analyzer data) for the analyzer output in `directory`."""
    for crate in CRATES:
        path = os.path.join(directory, f'{crate}_autoharness_data.json')
        with open(path) as f:
            yield crate, json.load(f)


def row_of(reason):
    """Row a skip reason is counted in, or None if it is not counted."""
    return None if reason in NOT_COUNTED else REASONS.get(reason, OTHER)


def read(directory):
    """Return (count per row, {'crate: function': row}) for the analyzer
    output in `directory`."""
    counts = collections.Counter()
    status = {}
    for crate, data in load(directory):
        # A list, not a map: two functions can share a printed name.
        for function, _safety in data['chosen']:
            counts[GENERATED] += 1
            status[f'{crate}: {function}'] = GENERATED
        for function, skipped in data['skipped'].items():
            row = row_of(skipped['reason'])
            if row is not None:
                counts[row] += 1
                status[f'{crate}: {function}'] = row
    return counts, status


def label(row):
    return 'Harness generated' if row == GENERATED else f'No harness: {row}'


def section(title, functions, base, head):
    if not functions:
        return []
    absent = 'not in the library'
    return ['', f'#### {title} ({len(functions)})', ''] + listed(
        functions, lambda f: f'- {code_span(f)}: '
        f'{base.get(f, absent)} → {head.get(f, absent)}')


def summarize(head, base=None):
    """Markdown summary of `head`, compared with `base` if given.

    Both are the output of `read`.
    """
    counts, status = head
    lines = ['### Functions autoharness can handle', '']
    if base is None:
        lines += ['| | Functions |', '| --- | ---: |']
        lines += [f'| {label(row)} | {counts[row]} |' for row in ROWS]
    else:
        base_counts, base_status = base
        lines += ['| | Base | This run | Change |',
                  '| --- | ---: | ---: | ---: |']
        lines += [change_row(label(row), base_counts[row], counts[row])
                  for row in ROWS]
        generated = {f for f, row in status.items() if row == GENERATED}
        base_generated = {
            f for f, row in base_status.items() if row == GENERATED}
        lines += section('Can now get a harness',
                         sorted(generated - base_generated),
                         base_status, status)
        lines += section('Can no longer get a harness',
                         sorted(base_generated - generated),
                         base_status, status)
    lines += ['', f'Counts cover {", ".join(CRATES[:-1])} and {CRATES[-1]}. '
              'A generated harness is not a proof yet: CI runs only the '
              'harnesses counted below.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
            'coverage', help='directory with the analyzer output to report')
    parser.add_argument(
            '--base',
            help='directory with the analyzer output to compare against')
    args = parser.parse_args()

    base = read(args.base) if args.base else None
    print(summarize(read(args.coverage), base), end='')


if __name__ == '__main__':
    main()
