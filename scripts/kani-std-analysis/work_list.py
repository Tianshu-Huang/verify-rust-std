#!/usr/bin/env python3

"""
List the functions that autoharness could not verify, grouped by what would
unblock them, as Markdown for a CI job summary or a book page. Given the JSON
that `log_parser.py` writes,
```
python3 work_list.py results.json
```
prints one table of blockers with counts, then one list per blocker so a
contributor can pick a function to work on. Functions the include filter left
out and Kani-internal functions are not listed: nobody can act on them here.
"""

import argparse
import collections
import json
import re

from results_summary import code_span, listed, verdict

MISSING_ARBITRARY = 'Missing Arbitrary implementation for argument(s) '
# Blocker name -> what a contributor does about it. The order is the order of
# the table; the first two need no knowledge of the function itself.
ACTIONS = [
    ('Argument type without `kani::Arbitrary`',
     'implement `Arbitrary` for the type, or write a manual harness'),
    ('Needs `--bounded-arguments`',
     'write a manual harness with bounded arguments'),
    ('Generic function',
     'write a manual harness for one concrete type'),
    ('Nothing checked (0 properties)',
     'add a contract (`#[requires]`, `#[ensures]`) so there is something to verify'),
    ('Verification failed',
     'unsafe without a contract: add `#[requires]`; otherwise find the failing check in the log'),
    ('Timed out',
     'add `#[kani::unwind]` or bounds, or stub a slow callee'),
    ('Chosen but no result',
     'the run stopped before this harness; check the log'),
]


def split_top_level(text, sep=', '):
    """Split on `sep` outside angle brackets: `a: X<Y, Z>, b: W` has two parts."""
    parts, depth, start = [], 0, 0
    for i, c in enumerate(text):
        depth += (c == '<') - (c == '>')
        if depth == 0 and text.startswith(sep, i):
            parts.append(text[start:i])
            start = i + len(sep)
    parts.append(text[start:])
    return parts


def missing_types(reason):
    """Types named in a 'Missing Arbitrary implementation' reason."""
    args = reason[len(MISSING_ARBITRARY):]
    return [arg.split(': ', 1)[1] for arg in split_top_level(args) if ': ' in arg]


def blocker(result):
    """Blocker name for one log_parser record, or None if not actionable."""
    reason = result.get('autoharness_result')
    if reason is not None and reason != 'ok':
        if reason.startswith(MISSING_ARBITRARY):
            return ACTIONS[0][0]
        if reason.startswith('Requires --bounded-arguments'):
            return ACTIONS[1][0]
        if reason.startswith('Generic Function'):
            return ACTIONS[2][0]
        return None  # no body, excluded by the filter, Kani-internal
    v = verdict(result)
    if v == 'Verified':
        return ACTIONS[3][0] if result.get('n_total_properties') == 0 else None
    if v == 'Failed':
        return ACTIONS[4][0]
    if v == 'Timed out':
        return ACTIONS[5][0]
    return ACTIONS[6][0] if reason == 'ok' else None


def describe(result):
    """One list item: name, then crate / safeness / visibility, then file."""
    tags = []
    for key in ('crate', 'function_safeness'):
        value = result.get(key)
        if isinstance(value, list):
            value = ', '.join(sorted(set(filter(None, value))))
        if value:
            tags.append(value)
    if result.get('public_target') is True:
        tags.append('public')
    line = f'- {code_span(result["harness"])}'
    if tags:
        line += f' ({", ".join(tags)})'
    if result.get('file_name'):
        line += f' `{result["file_name"]}`'
    return line


def sort_key(result):
    """Unsafe first (soundness), then public, then by name."""
    safeness = result.get('function_safeness')
    unsafe = safeness == 'unsafe' or (isinstance(safeness, list) and 'unsafe' in safeness)
    return (not unsafe, result.get('public_target') is not True, result['harness'])


def summary(text):
    """<summary> is HTML: GitHub does not render Markdown inside it."""
    return '<summary>' + re.sub(r'`([^`]*)`', r'<code>\1</code>', text) + '</summary>'


def work_list(entries):
    groups = collections.defaultdict(list)
    for entry in entries:
        result = entry['result']
        if not result['is_autoharness']:
            continue
        b = blocker(result)
        if b is not None:
            groups[b].append(result)

    lines = ['### Where autoharness needs help', '']
    if not groups:
        return '\n'.join(lines + ['Every selected function verified with at least one check.']) + '\n'

    lines += ['| Blocker | Functions | What unblocks them |', '| --- | ---: | --- |']
    for name, action in ACTIONS:
        if name in groups:
            lines.append(f'| {name} | {len(groups[name])} | {action} |')

    first = ACTIONS[0][0]
    if first in groups:
        by_type = collections.Counter()
        for result in groups[first]:
            by_type.update(set(missing_types(result['autoharness_result'])))
        lines += ['', '<details>',
                  summary(f'Types without `Arbitrary`, by functions they block ({len(by_type)})'), '']
        lines += listed(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])),
                        lambda kv: f'- {code_span(kv[0])}: {kv[1]}')
        lines += ['', '</details>']

    for name, _ in ACTIONS:
        results = groups.get(name)
        if not results:
            continue
        results.sort(key=sort_key)
        lines += ['', '<details>', summary(f'{name} ({len(results)})'), '']
        lines += listed(results, describe)
        lines += ['', '</details>']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('results', help='results.json of the run to report')
    args = parser.parse_args()
    with open(args.results) as f:
        print(work_list(json.load(f)), end='')


if __name__ == '__main__':
    main()
