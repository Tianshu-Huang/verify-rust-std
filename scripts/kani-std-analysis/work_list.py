#!/usr/bin/env python3

"""
List the library functions autoharness cannot generate a harness for, grouped
by what blocks them, as Markdown. Given a directory with the
`<crate>_autoharness_data.json` files that scripts/autoharness_analyzer writes,
```
python3 work_list.py coverage/
```
prints, for each blocker, how many functions it holds back and the Kani issues
that track it, the argument types that block the most functions, and the first
functions of each group, unsafe ones first.
"""

import argparse
import collections

from coverage_summary import OTHER, REASONS, load, row_of
from results_summary import code_span, listed

KANI_ISSUES = 'https://redirect.github.com/model-checking/kani/issues'
# For each blocker, in the order of REASONS: what it means in plain words, the
# title of its list of functions, and the Kani issues that track it. The links
# go through redirect.github.com so that they leave no mention on those issues.
BLOCKERS = dict(zip(REASONS.values(), [
    ('The function is generic and autoharness has no type to pick',
     'Generic functions', [4888, 4889]),
    ('Kani cannot create a value for one of the argument types',
     'Functions blocked by an argument type', [4887, 5137]),
    ('An argument needs a size limit',
     'Functions that need a size limit', [4890]),
]))
BAR = 12


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
            if blocker is not None:
                blocked[blocker].append(
                    (skipped['safety'] == 'unsafe', f'{crate}: {function}'))
                by_type.update(set(skipped['types']))

    total = sum(len(functions) for functions in blocked.values())
    if not total:
        return 'Autoharness writes a harness for every function.\n'
    lines = [f'### Why {total:,} functions have no harness yet', '',
             '| Reason | | Functions | Share | Where to help |',
             '| --- | --- | ---: | ---: | --- |']
    largest = max(len(functions) for functions in blocked.values())
    # Largest group first; the reasons nobody tracks go last.
    rows = sorted(BLOCKERS, key=lambda b: -len(blocked[b])) + [OTHER]
    for blocker in rows:
        count = len(blocked[blocker])
        if not count:
            continue
        text, _, issues = BLOCKERS.get(blocker, ('Other', None, []))
        links = ', '.join(f'[kani#{i}]({KANI_ISSUES}/{i})' for i in issues)
        bar = '█' * round(BAR * count / largest) or '▏'
        lines.append(f'| {text} | {bar} | {count:,} '
                     f'| {100 * count / total:.0f}% | {links} |')
    lines += ['', 'These are fixed in Kani, not in this repository. The '
              'numbers move when a pull request here updates the Kani version.',
              '', '**The functions, one by one**']
    if by_type:
        types = sorted(by_type.items(), key=lambda t: (-t[1], t[0]))
        lines += details(
            'Argument types that block the most functions '
            f'({len(types):,} types)',
            listed(types, lambda t: f'- {code_span(t[0])}: {t[1]:,}'))
    for blocker in rows[:-1]:
        # Unsafe functions first: they are the ones the challenges ask for.
        functions = sorted(blocked[blocker], key=lambda f: (not f[0], f[1]))
        if functions:
            unsafe = sum(is_unsafe for is_unsafe, _ in functions)
            lines += details(
                f'{BLOCKERS[blocker][1]} ({len(functions):,}, '
                f'of which {unsafe:,} unsafe)',
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
