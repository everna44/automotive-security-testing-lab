"""Descriptive analysis only; retain original CSV values and all duplicate rows."""
import csv
import hashlib
import json
import platform
import re
import statistics
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data/raw/extracted/GEM_CAN_Dataset_R2'
SOURCE = 'Source: GEM-CAN v3 | Zenodo 19161139 | CC BY-NC 3.0'
COLORS = {'Normal': '#2878b5', 'DoS': '#d62728',
          'Brake Tampering': '#e68a00', 'Steering Tampering': '#7b4ab5'}


def signature(row):
    return (Decimal(row['timestamp']), int(row['arbitration_id'], 16),
            int(row['dlc']), tuple(int(row[f'data{i}'], 16)
                                   for i in range(int(row['dlc']))))


def raw_signatures(session):
    if session == 'normal':
        with (DATA / 'PCAN_Files/GEM_Normal_Driving_Raw.json').open() as f:
            for line in f:
                r = json.loads(line)
                yield (Decimal(r['Time Offset (ms)']), int(r['ID (hex)'], 16),
                       int(r['Data Length']), tuple(int(v, 16) for v in r['Data (hex)'].split()))
    else:
        with (DATA / 'PCAN_Files/GEM_Attack_Scenario_Raw.trc').open() as f:
            for line in f:
                if not line.strip() or line.startswith(';'):
                    continue
                r = line.split()
                yield (Decimal(r[1]), int(r[3], 16), int(r[5]),
                       tuple(int(v, 16) for v in r[6:6 + int(r[5])]))


def save_table(name, fields, rows, output):
    with (output / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def save_plot(fig, name, output):
    fig.text(.5, .015, SOURCE, ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .055, 1, 1))
    fig.savefig(output / name, dpi=160)
    plt.close(fig)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=BASE / 'reports')
    parser.add_argument('--figures', type=Path, default=BASE / 'figures')
    args = parser.parse_args()
    # Refuse overwrites: reruns must use fresh output directories.
    args.output.mkdir(parents=True, exist_ok=True)
    args.figures.mkdir(parents=True, exist_ok=True)
    if (args.output / 'summary.json').exists() or any(args.figures.glob('*.png')):
        raise SystemExit('Use new --output and --figures paths to preserve prior results')
    summary = {'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
               'timestamp_unit': 'ms, verified against all raw records; seconds = CSV / 1000',
               'files': {}}
    datasets = {}
    id_rows, dlc_rows, time_rows, group_rows = [], [], [], []
    for session, filename in [('normal', 'GEM_Normal_Driving_Raw_Labeled.csv'),
                              ('attack', 'GEM_Attack_Scenario_Raw_Labeled.csv')]:
        path = DATA / filename
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames
            rows = list(reader)
        expected = ['timestamp', 'arbitration_id', 'dlc'] + [f'data{i}' for i in range(8)] + ['label']
        if session == 'attack':
            expected += ['Attack_Type']
        if columns != expected or any(None in r or None in r.values() for r in rows):
            raise ValueError(f'Unexpected CSV schema: {filename}')
        missing = {c: sum(not r[c].strip() for r in rows) for c in columns}
        invalid = Counter()
        for row in rows:
            invalid['id_format'] += not bool(re.fullmatch(r'[0-9A-Fa-f]{1,8}', row['arbitration_id']))
            invalid['id_range'] += not (0 <= int(row['arbitration_id'], 16) <= 0x1fffffff)
            invalid['dlc'] += not (0 <= int(row['dlc']) <= 8)
            invalid['payload_byte'] += any(not re.fullmatch(r'[0-9A-Fa-f]{1,2}', row[f'data{i}'])
                                           for i in range(8))
            invalid['label'] += row['label'] not in ('0', '1')
            invalid['nonfinite_timestamp'] += not Decimal(row['timestamp']).is_finite()
            if session == 'attack':
                invalid['label_type_mismatch'] += ((row['Attack_Type'] == 'Normal') != (row['label'] == '0'))
            invalid['payload_length_mismatch'] += sum(bool(row[f'data{i}'].strip()) for i in range(8)) != int(row['dlc'])
        if any(invalid.values()):
            raise ValueError(f'Invalid fields: {invalid}')
        sigs = [signature(r) for r in rows]
        original = list(raw_signatures(session))
        if sigs != original:
            raise ValueError(f'CSV/raw record mismatch: {filename}')
        times = [s[0] for s in sigs]
        start, end = min(times), max(times)
        span_s = float((end - start) / 1000)
        groups = defaultdict(list)
        for r, sig in zip(rows, sigs):
            # Baseline has no Attack_Type column; derive Normal only after validating all labels.
            if session == 'normal' and r['label'] != '0':
                raise ValueError('Unexpected non-normal baseline label')
            groups[r.get('Attack_Type', 'Normal')].append((r, sig))
        info = {'filename': filename, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'columns': columns, 'rows': len(rows), 'missing_by_column': missing,
                'duplicate_full_rows': len(rows) - len({tuple(r[c] for c in columns) for r in rows}),
                'duplicate_time_id_dlc_payload': len(sigs) - len(set(sigs)),
                'invalid_fields': dict(invalid), 'raw_alignment_rows': len(original),
                'labels': dict(Counter(r['label'] for r in rows)),
                'attack_types': dict(Counter(r['Attack_Type'] for r in rows)) if session == 'attack' else None,
                'id_text_widths': dict(Counter(len(r['arbitration_id']) for r in rows)),
                'ids_within_11bit_value': sum(s[1] <= 0x7ff for s in sigs),
                'ids_above_11bit_value': sum(s[1] > 0x7ff for s in sigs),
                'unique_ids': len({s[1] for s in sigs}),
                'dlc': dict(Counter(r['dlc'] for r in rows)),
                'timestamp_raw_min_ms': str(start), 'timestamp_raw_max_ms': str(end),
                'timestamp_decimal_places': dict(Counter(max(0, -t.as_tuple().exponent) for t in times)),
                'span_s': span_s, 'mean_frames_per_s_over_span': len(rows) / span_s,
                'timestamp_reversals': sum(b < a for a, b in zip(times, times[1:])),
                'duplicate_timestamps': len(times) - len(set(times)), 'groups': {}}
        for group, entries in groups.items():
            ids = Counter(f'{s[1]:08X}' for _, s in entries)
            dlcs = Counter(r['dlc'] for r, _ in entries)
            gt = sorted(s[0] for _, s in entries)
            intervals = [float(b-a) for a, b in zip(gt, gt[1:])]
            payloads = Counter(' '.join(f'{v:02X}' for v in s[3]) for _, s in entries)
            info['groups'][group] = {'rows': len(entries), 'percent_of_file': 100*len(entries)/len(rows),
                'ids': dict(ids), 'unique_payloads': len(payloads),
                'duplicate_full_rows': len(entries)-len({tuple(r[c] for c in columns) for r,_ in entries}),
                'max_row_multiplicity': max(Counter(tuple(r[c] for c in columns) for r,_ in entries).values()),
                'payload_diversity_by_id': {i: len({s[3] for _,s in entries if f'{s[1]:08X}' == i}) for i in ids},
                'first_ms': str(min(gt)), 'last_ms': str(max(gt)),
                'median_sorted_interarrival_ms': statistics.median(intervals) if intervals else None,
                'top_payloads': payloads.most_common(3)}
            group_rows.append({'session': session, 'group': group, 'frames': len(entries),
                               'percent_of_session': 100*len(entries)/len(rows)})
            for can_id, n in sorted(ids.items()):
                id_rows.append({'session': session, 'group': group, 'can_id_hex': can_id,
                                'frames': n, 'percent_of_group': 100*n/len(entries)})
            for dlc, n in sorted(dlcs.items()):
                dlc_rows.append({'session': session, 'group': group, 'dlc_bytes': dlc, 'frames': n})
        bins = int((end-start) // 1000) + 1
        counts = {g: Counter(int((s[0]-start)//1000) for _, s in entries) for g, entries in groups.items()}
        for index in range(bins):
            # Count histogram, not exposure-normalized rate; final bin is partial.
            for group in groups:
                time_rows.append({'session': session, 'group': group, 'start_s': index,
                                  'bin_width_s': 1, 'frames': counts[group][index],
                                  'last_bin_partial': index == bins-1})
        datasets[session] = (groups, counts, bins)
        summary['files'][session] = info
    save_table('can_id_distribution.csv', ['session','group','can_id_hex','frames','percent_of_group'], id_rows, args.output)
    save_table('dlc_distribution.csv', ['session','group','dlc_bytes','frames'], dlc_rows, args.output)
    save_table('time_bins.csv', ['session','group','start_s','bin_width_s','frames','last_bin_partial'], time_rows, args.output)
    save_table('group_distribution.csv', ['session','group','frames','percent_of_session'], group_rows, args.output)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    for ax, (session, (_, counts, bins)) in zip(axes, datasets.items()):
        for group, count in counts.items():
            ax.stairs([count[i] for i in range(bins)], range(bins+1), baseline=None,
                      label=group, color=COLORS.get(group))
        ax.set(title=f'{session.capitalize()} session (separate recording)', xlabel='Time since first frame (s)',
               ylabel='Frames / 1 s bin')
        ax.legend(fontsize=8)
        ax.grid(alpha=.25)
    fig.suptitle('CAN traffic over time | final bin is partial; zero bins retained')
    save_plot(fig, 'message_counts_over_time.png', args.figures)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, session in zip(axes, datasets):
        for group, stats in summary['files'][session]['groups'].items():
            ax.bar(group, stats['rows'], label=group, color=COLORS.get(group))
            ax.text(group, stats['rows'], f"{stats['rows']:,}", ha='center', va='bottom', fontsize=8)
        ax.set(title=f'{session.capitalize()} session', ylabel='Frames (count)')
        ax.tick_params(axis='x', labelrotation=20)
        ax.legend(fontsize=7)
        ax.margins(y=.15)
    save_plot(fig, 'normal_attack_distribution.png', args.figures)
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))
    for ax, session in zip(axes, datasets):
        stats = summary['files'][session]['groups']
        ids = sorted({can_id for group in stats.values() for can_id in group['ids']},
                     key=lambda i: (-sum(g['ids'].get(i, 0) for g in stats.values()), i))
        bottom = [0]*len(ids)
        for group, values in stats.items():
            n = [values['ids'].get(i, 0) for i in ids]
            ax.bar(range(len(ids)), n, bottom=bottom, label=group, color=COLORS.get(group))
            bottom = [a+b for a,b in zip(bottom,n)]
        ax.set_xticks(range(len(ids)), ids, rotation=60, ha='right', fontsize=8)
        ax.set(title=f'{session.capitalize()} session: all observed CAN IDs', xlabel='CAN ID (hex)', ylabel='Frames (count)')
        ax.legend(fontsize=8)
    save_plot(fig, 'can_id_frequency.png', args.figures)
    fig, ax = plt.subplots(figsize=(12, 5))
    # Top 10 IDs from baseline; include attack-only IDs to avoid hiding DoS.
    baseline = summary['files']['normal']['groups']['Normal']['ids']
    selected = [i for i,_ in sorted(baseline.items(), key=lambda v: -v[1])[:10]]
    selected += sorted(set(summary['files']['attack']['groups']['DoS']['ids'])-set(selected))
    series = [(s, g, info) for s, f in summary['files'].items() for g, info in f['groups'].items()]
    width = .8/len(series)
    for k,(session,group,info) in enumerate(series):
        ax.bar([i-.4+width/2+k*width for i in range(len(selected))],
               [100*info['ids'].get(i,0)/info['rows'] for i in selected], width,
               label=f'{session}: {group}')
    ax.set_xticks(range(len(selected)),selected,rotation=60,ha='right')
    ax.set(xlabel='CAN ID (hex): baseline top 10 + DoS ID', ylabel='Share within traffic group (%)',
           title='CAN ID proportions by session and supplied traffic category')
    ax.legend(fontsize=8)
    save_plot(fig,'can_id_share.png',args.figures)
    # Verify every aggregate conserves the original record counts.
    for session, info in summary['files'].items():
        for rows in (id_rows, dlc_rows, time_rows, group_rows):
            assert sum(r['frames'] for r in rows if r['session']==session) == info['rows']
    summary['total_rows'] = sum(f['rows'] for f in summary['files'].values())
    summary['total_labels'] = dict(sum((Counter(f['labels']) for f in summary['files'].values()), Counter()))
    with (DATA / 'PCAN_Files/GEM_Attack_Scenario_Raw.trc').open() as f:
        trace = [line.split() for line in f if line.strip() and not line.startswith(';')]
    summary['attack_trace_directions'] = dict(Counter(r[4] for r in trace))
    summary['dos_trace_directions'] = dict(Counter(r[4] for r in trace if int(r[3],16)==0))
    external = json.loads((BASE / 'data/raw/GEM_CAN_metadata.json').read_text())
    internal = json.loads((DATA / 'GEM_CAN_metadata.json').read_text())
    summary['metadata_intervals_ms'] = {
        'standalone': {r['type']: r['injection_interval_ms'] for r in external['attack_scenarios']},
        'inside_zip': {r['type']: r['injection_interval_ms'] for r in internal['attack_scenarios']}}
    summary['analysis_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (args.output / 'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
