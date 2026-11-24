#!/usr/bin/env python3

"""
Keep a history of how many library functions autoharness generates a harness
for, and draw the chart of it that the "Autoharness status" issue shows. The
weekly metrics workflow adds one point each time it runs.
```
python3 autoharness_history.py record coverage/ results.json [--run URL]
python3 autoharness_history.py plot
```
`record` appends today's point to autoharness-history.json from the analyzer
output and the `log_parser.py` JSON of one run (the same inputs as
`autoharness_report.py`); `--run` is the address of that run. `plot` draws the
last twelve months of that file.

A run in which the analyzer reported no generated harness at all is not
recorded: that is a broken run, not a week without harnesses.
"""

import argparse
import datetime
import json
import os

from coverage_summary import load, row_of
from results_summary import count, harness_verdicts

HISTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'autoharness-history.json')
PLOT_FILE = 'autoharness_history.png'
PLOT_DAYS = 365


def crate_counts(coverage):
    """{crate: {'generated': n, 'total': n}} for the analyzer output in the
    directory `coverage`. The total leaves out what `coverage_summary` does
    not count."""
    crates = {}
    for crate, data in load(coverage):
        generated = len(data['chosen'])
        skipped = sum(row_of(s['reason']) is not None
                      for s in data['skipped'].values())
        crates[crate] = {'generated': generated, 'total': generated + skipped}
    return crates


def record(history, coverage, results, date, run=None):
    """Add the point of `date` to the list `history`, replacing an earlier
    point of the same day. `run` is the address of the run it comes from."""
    crates = crate_counts(coverage)
    if not any(c['generated'] for c in crates.values()):
        return history
    entry = {'date': date, 'crates': crates,
             'verified_in_ci': count(harness_verdicts(results), 'Verified')}
    if run:
        entry['run'] = run
    return [e for e in history if e['date'] != date] + [entry]


def series(history, last_days=PLOT_DAYS):
    """Return (crates, [(date, generated, total)]) to plot: the entries of the
    last `last_days` days, summed over the crates all of them have, so that a
    crate recorded only later does not look like progress."""
    dated = [(datetime.date.fromisoformat(e['date']), e) for e in history]
    start = dated[-1][0] - datetime.timedelta(days=last_days)
    dated = [(d, e) for d, e in dated if d >= start]
    crates = [c for c in dated[0][1]['crates']
              if all(c in e['crates'] for _, e in dated)]

    def total(entry, key):
        return sum(entry['crates'][c][key] for c in crates)
    return crates, [(d, total(e, 'generated'), total(e, 'total'))
                    for d, e in dated]


def plot(history, out):
    # Only the chart needs matplotlib; `record` runs without it.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    verified_color, written, none = '#0d366b', '#256abf', '#d1d9e0'
    ink, muted, grid = '#1f2328', '#59636e', '#e1e4e8'
    plt.rcParams.update({
        'font.size': 11, 'text.color': muted, 'axes.labelcolor': muted,
        'xtick.color': muted, 'ytick.color': muted})
    fig, (bar, line) = plt.subplots(
        2, 1, figsize=(8, 4.6),
        gridspec_kw={'height_ratios': [1, 3.2], 'hspace': 0.5})

    # Where every function stands today: one bar, three states.
    last = history[-1]
    total = sum(c['total'] for c in last['crates'].values())
    generated = sum(c['generated'] for c in last['crates'].values())
    verified = last.get('verified_in_ci', 0)
    bar.set_title('Where every function stands', loc='left', color=ink,
                  fontweight='bold', fontsize=12)
    gap, sliver = total * 0.004, total * 0.006
    left = 0
    for n, color, text_color, label in (
            (verified, verified_color, None, None),
            (generated - verified, written, 'white',
             'harness written, not run in CI'),
            (total - generated, none, ink, 'no harness yet')):
        if not n:
            continue
        bar.barh(0, max(n - gap, sliver), left=left, color=color, height=0.8)
        if label:
            bar.text(left + gap * 4, 0, f'{n / total:.0%} {label}',
                     va='center', color=text_color, fontweight='bold')
        left += max(n, sliver + gap)
    if verified:
        bar.text(0, -0.95, f'▲ {verified / total:.1%} verified in CI '
                 f'({verified:,} of {total:,} functions)', va='center')
    bar.set_xlim(0, left)
    bar.set_ylim(-1.3, 0.5)
    bar.axis('off')

    # Functions with a harness, over time.
    crates, points = series(history)
    names = ' and '.join(filter(None, [', '.join(crates[:-1]), crates[-1]]))
    line.set_title(f'How many functions in {names} have a harness, over time',
                   loc='left', color=ink, fontweight='bold', fontsize=12)
    days = [d for d, _, _ in points]
    values = [v for _, v, _ in points]
    totals = [t for _, _, t in points]
    line.plot(days, totals, color=muted, linewidth=1, linestyle=(0, (4, 3)),
              drawstyle='steps-post')
    line.plot(days, values, color=written, linewidth=2,
              drawstyle='steps-post')
    first, end = 0, len(points) - 1
    line.plot(days[end], values[end], 'o', color=written, markersize=9,
              markeredgecolor='white', markeredgewidth=2)
    line.annotate(f'{values[end]:,} ({values[end] / totals[end]:.0%})',
                  (days[end], values[end]),
                  xytext=(10, -4), textcoords='offset points', color=ink,
                  fontweight='bold')
    line.annotate('have a harness', (days[end], values[end]),
                  xytext=(10, -19), textcoords='offset points')
    if end > first:
        line.annotate(f'{values[first]:,} '
                      f'({values[first] / totals[first]:.0%})',
                      (days[first], values[first]),
                      xytext=(0, 7), textcoords='offset points', color=ink)
        line.annotate(f'{totals[first]:,}', (days[first], totals[first]),
                      xytext=(0, -16), textcoords='offset points', color=ink)
    line.annotate(f'{totals[end]:,}', (days[end], totals[end]),
                  xytext=(10, -4), textcoords='offset points', color=ink)
    line.annotate(f'functions in {names}', (days[end], totals[end]),
                  xytext=(10, -19), textcoords='offset points')
    days_shown = max((days[-1] - days[0]).days, 30)
    line.set_ylim(0, max(totals) * 1.12)
    line.set_xlim(days[0] - datetime.timedelta(days=days_shown * 0.04),
                  days[-1] + datetime.timedelta(days=days_shown * 0.36))
    line.yaxis.set_major_formatter(lambda v, _: f'{int(v):,}')
    line.xaxis.set_major_locator(mdates.MonthLocator())
    line.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    line.grid(axis='y', color=grid, linewidth=1)
    line.set_axisbelow(True)
    for side in ('top', 'right', 'left'):
        line.spines[side].set_visible(False)
    line.spines['bottom'].set_color(grid)
    line.tick_params(length=0)
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--history', default=HISTORY)
    commands = parser.add_subparsers(dest='command', required=True)
    rec = commands.add_parser('record')
    rec.add_argument('coverage', help='directory with the analyzer output')
    rec.add_argument('results', help='JSON written by log_parser.py')
    rec.add_argument('--run', help='address of the run the numbers are from')
    commands.add_parser('plot').add_argument(
        '--plot-dir', default=os.path.dirname(HISTORY))
    args = parser.parse_args()

    with open(args.history) as f:
        history = json.load(f)['results']
    if args.command == 'plot':
        plot(history, os.path.join(args.plot_dir, PLOT_FILE))
        return
    with open(args.results) as f:
        results = json.load(f)
    history = record(history, args.coverage, results,
                     datetime.date.today().isoformat(), args.run)
    with open(args.history, 'w') as f:
        json.dump({'results': history}, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
