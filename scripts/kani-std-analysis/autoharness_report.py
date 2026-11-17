#!/usr/bin/env python3

"""
Write the two texts people read about autoharness, as Markdown:
```
python3 autoharness_report.py status coverage/ results.json
python3 autoharness_report.py comment coverage/ results.json \
    [--base-coverage base-coverage/] [--base-results base-results.json]
```
`status` is the "Autoharness status" issue: where `main` stands and which
functions still need help. `comment` is the pull request comment: what the
pull request changes, compared with `main`. `coverage/` holds the analyzer
output and `results.json` is the output of `log_parser.py`.
"""

import argparse

import coverage_summary
import results_summary
import work_list
from coverage_summary import CRATES, GENERATED
from results_summary import code_span

CRATE_LIST = f'{", ".join(CRATES[:-1])} and {CRATES[-1]}'
# Longest list of functions shown outside the collapsed details.
SHOWN = 10
BAR = 20


def share(n, total):
    """`n` as a percentage of `total`; small shares keep one decimal."""
    if not total:
        return '0%'
    percent = 100 * n / total
    return f'{percent:.1f}%' if 0 < percent < 1 else f'{percent:.0f}%'


def bar(n, total, width=BAR):
    filled = round(width * n / total) if total else 0
    return '█' * filled + '░' * (width - filled)


def plural(n, one, many):
    return f'{n:,} {one if n == 1 else many}'


def steps(coverage, verdicts):
    """(all functions, with a harness, verified in CI); the first two are None
    without analyzer output."""
    verified = results_summary.count(verdicts, 'Verified')
    if coverage is None:
        return None, None, verified
    counts, _ = coverage
    return sum(counts.values()), counts[GENERATED], verified


def status(coverage_dir, verdicts, stamp=None, chart_url=None,
           chart_updated=None, chart_note=None):
    """Markdown for the status issue."""
    total, written, verified = steps(coverage_summary.read(coverage_dir), verdicts)
    # The number alone as the headline, so that it is the first thing read.
    lines = [
        f'# {share(written, total)}',
        f'of the functions in {CRATE_LIST} have a harness',
        '',
        'A harness is a test that Kani can prove for every possible input. '
        'Autoharness writes harnesses automatically. This page shows how far '
        'it gets on `main`.',
        '',
    ]
    if chart_url:
        lines += [
            '![Where every function stands, and functions with a harness '
            f'over time]({chart_url})',
            '',
            '<sub>Updated every week'
            + (f' · last updated {chart_updated}' if chart_updated else '')
            + (f'<br>{chart_note}' if chart_note else '') + '</sub>',
            '',
        ]
    lines += [
        '### The numbers today',
        '',
        '| | Functions | Share |',
        '| --- | ---: | ---: |',
        f'| **All functions**<br>in {CRATE_LIST} | {total:,} | 100% |',
        '| **Harness written**<br>Autoharness wrote a harness for the function. '
        f'Most have not been run yet | {written:,} | {share(written, total)} |',
        '| **Verified in CI**<br>CI ran the harness and Kani proved it '
        f'| {verified:,} | {share(verified, total)} |',
        '',
    ]
    if stamp:
        lines += [f'<sub>Updated after every merge · last updated {stamp}</sub>',
                  '']
    lines += [
        'Why so few are verified: CI runs only the functions listed in '
        '`kani.yml`.',
        '',
        work_list.work_list(coverage_dir),
    ]
    return '\n'.join(lines)


def changes(head, base):
    """(gained, lost) names, sorted."""
    return sorted(head - base), sorted(base - head)


def verified_names(verdicts):
    return {h for h, runs in verdicts.items() if 'Verified' in runs}


def shown(title, names):
    """A short list at the top level; the details below hold all of it."""
    if not names:
        return []
    lines = ['', f'**{title}**', '']
    lines += [f'- {code_span(name)}' for name in names[:SHOWN]]
    if len(names) > SHOWN:
        lines.append(f'- and {len(names) - SHOWN:,} more, listed below')
    return lines


def comment(coverage, verdicts, base_coverage=None, base_verdicts=None,
            base_stamp=None, status_url=None):
    """Markdown for the pull request comment.

    `coverage` and `base_coverage` are the output of `coverage_summary.read`,
    the verdicts that of `results_summary.read`; any of them can be None.
    """
    total, written, verified = steps(coverage, verdicts or {})
    compared = base_verdicts is not None
    base_total, base_written, base_verified = steps(
        base_coverage, base_verdicts or {})

    newly, no_longer = changes(
        verified_names(verdicts or {}), verified_names(base_verdicts or {})
    ) if compared else ([], [])
    can_now, cannot = [], []
    if coverage and base_coverage:
        can_now, cannot = changes(
            *({f for f, row in status.items() if row == GENERATED}
              for status in (coverage[1], base_coverage[1])))

    # The headline is the most urgent change; the sentences cover all of them.
    means = []
    if no_longer:
        means.append(
            'A proof that passes on `main` fails with this change. Fix it '
            'before merging.' if len(no_longer) == 1 else
            f'{len(no_longer):,} proofs that pass on `main` fail with this '
            'change. Fix them before merging.')
    if newly:
        means.append(f'CI now proves {plural(len(newly), "more function", "more functions")}'
                     ' on every pull request.')
    if can_now:
        means.append(
            f'Autoharness writes a harness for {plural(len(can_now), "more function", "more functions")}.'
            ' CI does not run them yet. To verify one, list it in `kani.yml`.')
    if cannot:
        means.append(
            f'Autoharness can no longer write a harness for {plural(len(cannot), "function", "functions")}'
            ' that had one on `main`.')
    if (newly or no_longer) and not (can_now or cannot) and base_coverage:
        means.append('Which functions have a harness did not change.')

    if not compared:
        headline = 'Autoharness results'
        means = ['There are no results of `main` to compare with.']
    elif no_longer:
        headline = f'✗ {plural(len(no_longer), "harness no longer verifies", "harnesses no longer verify")}'
    elif newly:
        headline = f'+{plural(len(newly), "harness", "harnesses")} verified in CI'
    elif can_now:
        headline = f'+{plural(len(can_now), "function", "functions")} can now get a harness'
    elif cannot:
        headline = f'−{plural(len(cannot), "function", "functions")} can no longer get a harness'
    else:
        headline = 'No change to the autoharness results'
        means = ['This pull request does not change which functions have a '
                 'harness or which harnesses verify.']

    def cell(n, base_n=None):
        if n is None:
            return '—'
        if base_n is None or n == base_n:
            return f'{n:,}'
        return f'**{n:,}** ({n - base_n:+,})'

    def row(title, text, n, base_n):
        graph = bar(n or 0, total) if total else ''
        cells = [f'**{title}**<br>{text}', graph]
        if compared:
            cells.append(cell(base_n))
        cells.append(cell(n, base_n if compared else None))
        return '| ' + ' | '.join(cells) + ' |'

    main = 'Main' + (f'<br>{base_stamp}' if base_stamp else '')
    header = ['Step', ''] + ([main] if compared else []) + ['This pull request']
    lines = [f'## {headline}', '', '**What this means:** ' + ' '.join(means), '',
             '| ' + ' | '.join(header) + ' |',
             '| --- | --- |' + ' ---: |' * (len(header) - 2),
             row('All functions', f'in {CRATE_LIST}', total, base_total),
             row('Harness written', 'Autoharness wrote a harness for the '
                 'function. Most have not been run yet', written, base_written),
             row('Verified in CI', 'CI ran the harness and Kani proved it',
                 verified, base_verified)]
    lines += shown('No longer verified', no_longer)
    lines += shown('Newly verified', newly)
    lines += shown('Can now get a harness', can_now)
    lines += shown('Can no longer get a harness', cannot)

    if compared:
        lines += ['', 'Compared with `main`'
                  + (f' at {base_stamp.replace(" · ", ", commit ")}' if base_stamp else '')
                  + '. If `main` has new merges since, run this again to '
                  'compare with them.']
    if status_url:
        lines += ['', 'Where the project stands and where help is needed: '
                  f'[Autoharness status]({status_url}).']

    lines += ['', '<details><summary>Counts by reason, and every function '
              'that changed</summary>', '']
    if coverage:
        lines.append(coverage_summary.summarize(coverage, base_coverage))
    if verdicts is not None:
        lines.append(results_summary.summarize(verdicts, base_verdicts))
    lines += ['</details>']
    return '\n'.join(lines) + '\n'


def read_coverage(directory):
    """Analyzer output in `directory`, or None if that job produced none."""
    try:
        return coverage_summary.read(directory) if directory else None
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('kind', choices=['status', 'comment'])
    parser.add_argument('coverage', help='directory with the analyzer output')
    parser.add_argument('results', help='results.json of the run')
    parser.add_argument('--base-coverage')
    parser.add_argument('--base-results')
    parser.add_argument('--stamp', help='date, commit and run of this run')
    parser.add_argument('--base-stamp', help='date and commit of the base run')
    parser.add_argument('--status-url', help='link to the status issue')
    parser.add_argument('--chart-url', help='address of the history chart')
    parser.add_argument('--chart-updated', help='date of its last point')
    parser.add_argument('--chart-note', help='what the chart leaves out')
    args = parser.parse_args()

    verdicts = results_summary.read(args.results)
    if args.kind == 'status':
        print(status(args.coverage, verdicts, args.stamp, args.chart_url,
                     args.chart_updated, args.chart_note), end='')
        return
    base_verdicts = (results_summary.read(args.base_results)
                     if args.base_results else None)
    print(comment(read_coverage(args.coverage), verdicts,
                  read_coverage(args.base_coverage), base_verdicts,
                  args.base_stamp, args.status_url), end='')


if __name__ == '__main__':
    main()
