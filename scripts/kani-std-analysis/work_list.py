#!/usr/bin/env python3

"""
List the library functions autoharness cannot generate a harness for, grouped
by what blocks them, as Markdown. Given a directory with the
`<crate>_autoharness_data.json` files that scripts/autoharness_analyzer writes,
```
python3 work_list.py coverage/
```
prints, for each blocker, how many functions it holds back and what would
unblock them, the argument types that block the most functions, and the first
functions of each group, unsafe ones first.
"""

import argparse
import collections

from coverage_summary import REASONS, load, row_of
from results_summary import code_span, listed

# What a contributor can do about each blocker, in the order of REASONS.
ACTIONS = dict(zip(REASONS.values(), [
    'write a harness that calls it with one concrete type',
    'implement `kani::Arbitrary` for the type, or write a harness that '
    'builds the argument',
    'write a harness that bounds the argument',
]))


def summary(text):
    """HTML for a <summary>, where Markdown code spans are not rendered."""
    parts = text.split('`')
    return ''.join(
        f'<code>{part}</code>' if i % 2 else part
        for i, part in enumerate(parts))


def details(title, lines):
    return ['', f'<details><summary>{summary(title)}</summary>', ''] + lines \
        + ['', '</details>']


def work_list(directory):
    """Markdown work list for the analyzer output in `directory`."""
    blocked = collections.defaultdict(list)  # blocker -> [(unsafe, name)]
    by_type = collections.Counter()          # argument type -> functions
    for crate, data in load(directory):
        for function, skipped in data['skipped'].items():
            blocker = row_of(skipped['reason'])
            if blocker in ACTIONS:
                blocked[blocker].append(
                    (skipped['safety'] == 'unsafe', f'{crate}: {function}'))
                by_type.update(set(skipped['types']))

    lines = ['### Where autoharness needs help', '']
    if not blocked:
        return '\n'.join(
            lines + ['Autoharness generates a harness for every function.']
        ) + '\n'
    lines += ['| No harness because | Functions | Unsafe | What unblocks them |',
              '| --- | ---: | ---: | --- |']
    for blocker, action in ACTIONS.items():
        functions = blocked[blocker]
        lines.append(f'| {blocker} | {len(functions)} '
                     f'| {sum(unsafe for unsafe, _ in functions)} | {action} |')
    if by_type:
        types = sorted(by_type.items(), key=lambda t: (-t[1], t[0]))
        lines += details(
            f'Argument types, by functions they block ({len(types)})',
            listed(types, lambda t: f'- {code_span(t[0])}: {t[1]}'))
    for blocker in ACTIONS:
        # Unsafe functions first: they are the ones the challenges ask for.
        functions = sorted(blocked[blocker], key=lambda f: (not f[0], f[1]))
        if functions:
            lines += details(
                f'{blocker} ({len(functions)})',
                listed(functions, lambda f: f'- {code_span(f[1])}'
                       + (' (unsafe)' if f[0] else '')))
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('coverage', help='directory with the analyzer output')
    print(work_list(parser.parse_args().coverage), end='')


if __name__ == '__main__':
    main()
