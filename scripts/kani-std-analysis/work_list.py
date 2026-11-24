"""
The library functions autoharness cannot generate a harness for, grouped by
what blocks them, as Markdown for the "Autoharness status" issue. Read from the
`<crate>_autoharness_data.json` files that scripts/autoharness_analyzer writes.
One section per blocker: what it means, with an example, how many functions it
holds back, the argument types that cause it most often, the first functions
(unsafe ones first) and the Kani issues that track it.
"""

import collections

from coverage_summary import OTHER, REASONS, load, row_of, share
from results_summary import LIST_LIMIT, code_span, listed, plural

KANI_ISSUES = 'https://redirect.github.com/model-checking/kani/issues'
# For each blocker, in the order of REASONS: a title and one sentence in plain
# words, a library function it holds back with a comment on what is in the
# way, and the Kani issues that track it. The links go through
# redirect.github.com so that they leave no mention on those issues.
# shortcut: the example functions are fixed text; replace one when autoharness
# starts to cover it.
BLOCKERS = dict(zip(REASONS.values(), [
    ('The function is generic',
     'A generic function works for many types. Autoharness has to pick one '
     'to test with, and here it found none.',
     'fn max_by<T, F>(v1: T, v2: T, compare: F) -> T'
     '   // which types should T and F be?',
     [4888, 4889]),
    ('Kani cannot make up a value for an argument',
     'Some argument types are ones Kani does not know how to make up.',
     'fn exists(path: &Path) -> io::Result<bool>'
     '   // Kani cannot make up a &Path',
     [4887, 5137]),
    ('An argument can be any length',
     'The argument is a string or a slice. Kani can only test it up to a '
     'maximum length, and CI does not set one.',
     'fn from_utf8(v: &[u8]) -> Result<&str, Utf8Error>'
     '   // v can be any length',
     [4890]),
]))


def details(title, lines):
    return ['', f'<details><summary>{title}</summary>', ''] + lines \
        + ['', '</details>']


def work_list(directory):
    """Markdown work list for the analyzer output in `directory`."""
    blocked = collections.defaultdict(list)  # blocker -> [(unsafe, name)]
    # blocker -> argument type -> functions
    by_type = collections.defaultdict(collections.Counter)
    for crate, data in load(directory):
        for function, skipped in data['skipped'].items():
            blocker = row_of(skipped['reason'])
            if blocker is not None:
                blocked[blocker].append(
                    (skipped['safety'] == 'unsafe', f'{crate}: {function}'))
                by_type[blocker].update(set(skipped['types']))

    total = sum(len(functions) for functions in blocked.values())
    if not total:
        return 'Autoharness writes a harness for every function.\n'
    have = 'has' if total == 1 else 'have'
    lines = [f'### Why {plural(total, "function")} {have} no '
             'harness yet', '',
             'To write a harness, autoharness has to call the function with '
             'made-up arguments. It gets stuck in the ways below. All of them '
             'are fixed in Kani, not in this repository.']
    # Largest group first. Every reason appears once, with all that is known
    # about it, so that a reader has nothing to match up.
    rows = sorted((b for b in BLOCKERS if blocked[b]),
                  key=lambda b: -len(blocked[b]))
    for number, blocker in enumerate(rows, 1):
        # Unsafe functions first: they are the ones the challenges ask for.
        functions = sorted(blocked[blocker], key=lambda f: (not f[0], f[1]))
        count = len(functions)
        title, why, example, issues = BLOCKERS[blocker]
        links = ', '.join(f'[kani#{i}]({KANI_ISSUES}/{i})' for i in issues)
        lines += ['', f'#### {number}. {title}', '',
                  f'**{plural(count, "function")}** '
                  f'({share(count, total)}) · tracked in {links}',
                  '', why, '', '```rust', example, '```']
        if by_type[blocker]:
            types = sorted(by_type[blocker].items(),
                           key=lambda t: (-t[1], t[0]))
            # The issue has room for the first LIST_LIMIT only; say so.
            lines += details(
                f'The {LIST_LIMIT} types that cause this most often, of '
                f'{len(types):,}' if len(types) > LIST_LIMIT else
                'Which types cause this, most common first '
                f'({plural(len(types), "type")})',
                listed(types, lambda t: f'- {code_span(t[0])}: '
                       + plural(t[1], 'function')))
        lines += details(
            f'The first {LIST_LIMIT} of {count:,} functions, unsafe first'
            if count > LIST_LIMIT else
            f'{plural(count, "function")}, unsafe first',
            listed(functions, lambda f: f'- {code_span(f[1])}'
                   + (' (unsafe)' if f[0] else '')))
    other = len(blocked[OTHER])
    if other:
        lines += ['', f'The remaining {plural(other, "function")} '
                  f'({share(other, total)}) '
                  f'{"has" if other == 1 else "have"} other reasons, such as '
                  'a function with no body.']
    return '\n'.join(lines) + '\n'
