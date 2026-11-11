"""Read-only GEM-CAN DoS analysis. Integer microseconds; no model or data cleaning.

Run from repository root with the existing Lab 03 virtualenv. Output must not exist.
"""
import argparse
import csv
import hashlib
import json
import platform
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / 'src'))
from analyze import raw_signatures, signature

DATA = LAB / 'data/raw/extracted/GEM_CAN_Dataset_R2'
SOURCE = 'GEM-CAN v3 | Zenodo 19161139 | CC BY-NC 3.0 | derived CSV analysis'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def table(out, name, rows):
    with (out / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def stats(times):
    d = np.diff(sorted(times)) / 1000  # integer us -> ms
    return {'frames': len(times), 'intervals': len(d),
            **{k: float(fn(d)) if len(d) else None for k, fn in
               [('median_ms', np.median), ('p95_ms', lambda x: np.percentile(x, 95)),
                ('max_ms', np.max)]}}


def save(fig, out, name):
    fig.text(.5, .015, SOURCE, ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, .94))
    fig.savefig(out / name, dpi=160)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path(__file__).parent / 'results')
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit('Output exists; use a fresh --output path')
    datasets, checks = {}, {}
    for session, name in [('normal', 'GEM_Normal_Driving_Raw_Labeled.csv'),
                          ('attack', 'GEM_Attack_Scenario_Raw_Labeled.csv')]:
        path = DATA / name
        with path.open() as f:
            rows = list(csv.DictReader(f))
        sigs = [signature(r) for r in rows]
        raw = list(raw_signatures(session))
        assert sigs == raw, 'CSV does not align with PCAN raw records'
        ts = [int(s[0] * 1000) for s in sigs]
        assert all(Decimal(t) == s[0] * 1000 for t, s in zip(ts, sigs))
        entries = [(t, s[1], r.get('Attack_Type', 'Normal'), r['label'])
                   for t, s, r in zip(ts, sigs, rows)]
        datasets[session] = entries
        checks[session] = {'file': name, 'sha256': digest(path), 'rows': len(rows),
            'raw_alignment_rows': len(raw), 'min_ms': min(ts)/1000, 'max_ms': max(ts)/1000,
            'span_s': (max(ts)-min(ts))/1e6,
            'first_last_equals_min_max': ts[0] == min(ts) and ts[-1] == max(ts),
            'timestamp_reversals': sum(b < a for a,b in zip(ts, ts[1:])),
            'duplicate_timestamp_rows': len(ts)-len(set(ts)),
            'duplicate_full_rows': len(rows)-len({tuple(r.values()) for r in rows}),
            'duplicate_signature_rows': len(sigs)-len(set(sigs)),
            'timestamp_decimal_places': dict(Counter(max(0,-s[0].as_tuple().exponent) for s in sigs)),
            'unique_signature_rows': len(set(sigs)),
            'all_rows_per_s': len(rows)/((max(ts)-min(ts))/1e6),
            'unique_signatures_per_s': len(set(sigs))/((max(ts)-min(ts))/1e6)}

    a = datasets['attack']
    dos = [t for t,i,g,l in a if i == 0]
    assert all((i == 0) == (g == 'DoS') for t,i,g,l in a)
    start, end = min(dos), max(dos)
    lo, hi = min(t for t,*_ in a), max(t for t,*_ in a)
    phases = [('pre', lo, start), ('during', start, end), ('post', end, hi)]
    def phase(t):
        return 'pre' if t < start else 'post' if t > end else 'during'
    rates = []
    for label, left, right in phases:
        rows = [e for e in a if phase(e[0]) == label]
        duration = (right-left)/1e6
        for group, subset in [('all', rows), ('DoS_ID0', [e for e in rows if e[1]==0]),
                              ('label0', [e for e in rows if e[3]=='0']),
                              ('nonzero_ID_all_labels', [e for e in rows if e[1]!=0])]:
            rates.append(dict(phase=label, start_offset_s=left/1e6, end_offset_s=right/1e6,
                              exposure_s=duration, group=group, frames=len(subset),
                              records_per_s=len(subset)/duration))

    # Include all baseline IDs, even if absent from a phase or the entire attack session.
    ids = sorted({i for t,i,g,l in datasets['normal']})
    intervals, crossings, gaps = [], [], []
    for i in ids:
        normal = [t for t,j,g,l in datasets['normal'] if j==i]
        intervals.append(dict(can_id=f'{i:08X}', selection='baseline_label0', phase='baseline', **stats(normal)))
        for selection in ('label0_only', 'all_labels'):
            times = sorted(t for t,j,g,l in a if j==i and (selection=='all_labels' or l=='0'))
            for t0,t1 in zip(times,times[1:]):
                gaps.append(dict(can_id=f'{i:08X}', selection=selection,
                    from_offset_s=t0/1e6, to_offset_s=t1/1e6,
                    gap_ms=(t1-t0)/1000, from_phase=phase(t0), to_phase=phase(t1)))
            for label,_,_ in phases:
                intervals.append(dict(can_id=f'{i:08X}', selection=selection, phase=label,
                                      **stats([t for t in times if phase(t)==label])))
            before, during, after = ([t for t in times if phase(t)==label] for label in ('pre','during','post'))
            crossings.append(dict(can_id=f'{i:08X}', selection=selection,
                pre_frames=len(before), during_frames=len(during), post_frames=len(after),
                last_pre_s=before[-1]/1e6 if before else None,
                first_post_s=after[0]/1e6 if after else None,
                pre_to_post_gap_s=(after[0]-before[-1])/1e6 if before and after else None,
                gap_from_dos_end_s=(after[0]-end)/1e6 if after else None))

    # One-second bins relative to each recording's first timestamp. Last bin exposure corrected.
    bins = []
    for session, entries in datasets.items():
        left, right = min(e[0] for e in entries), max(e[0] for e in entries)
        for k in range((right-left)//1000000 + 1):
            b0, b1 = left+k*1000000, min(left+(k+1)*1000000, right)
            if b1 == b0:  # exact endpoint belongs to final bin with positive exposure
                continue
            selected = [e for e in entries if b0 <= e[0] and (e[0]<b1 or e[0]==b1==right)]
            unique = set(selected)  # DoS fixed payload verified below; bin uniqueness is ID/time/type/label
            n0 = sum(e[1]==0 for e in selected)
            bins.append(dict(session=session, start_relative_s=k, end_relative_s=(b1-left)/1e6,
                exposure_s=(b1-b0)/1e6, partial=b1-b0<1000000, frames=len(selected),
                records_per_s=len(selected)/((b1-b0)/1e6), dos_frames=n0,
                dos_records_per_s=n0/((b1-b0)/1e6),
                dos_unique_timestamp_rate=len({e[0] for e in unique if e[1]==0})/((b1-b0)/1e6),
                normal_label_frames=sum(e[3]=='0' for e in selected)))
        assert sum(b['frames'] for b in bins if b['session']==session)==len(entries)

    directions = Counter()
    for line in (DATA/'PCAN_Files/GEM_Attack_Scenario_Raw.trc').read_text().splitlines():
        if line.strip() and not line.startswith(';'):
            r = line.split()
            directions[('DoS' if int(r[3],16)==0 else 'other')+'_'+r[4]] += 1
    attack_sigs = list(raw_signatures('attack'))
    assert {s[3] for s in attack_sigs if s[1]==0} == {(0,)*8}
    unique_dos = sorted(set(dos))
    dos_summary = dict(first_offset_s=start/1e6, last_offset_s=end/1e6,
        span_s=(end-start)/1e6, rows=len(dos), unique_timestamps=len(unique_dos),
        duplicates=len(dos)-len(unique_dos), records_per_s=len(dos)/((end-start)/1e6),
        unique_records_per_s=len(unique_dos)/((end-start)/1e6),
        all_intervals=stats(dos), unique_intervals=stats(unique_dos),
        max_timestamp_multiplicity=max(Counter(dos).values()), raw_directions=dict(directions))
    source_files = [LAB/'data/raw/README.md', LAB/'data/raw/GEM_CAN_metadata.json',
                    DATA/'README.md', DATA/'GEM_CAN_metadata.json',
                    DATA/'PCAN_Files/GEM_Attack_Scenario_Raw.trc',
                    DATA/'PCAN_Files/GEM_Normal_Driving_Raw.json']
    metadata = {}
    for key, path in [('external',source_files[1]),('internal',source_files[3])]:
        m = json.loads(path.read_text())
        metadata[key] = {x['type']:x['injection_interval_ms'] for x in m['attack_scenarios']}
    args.output.mkdir(parents=True)
    out = args.output
    result = dict(python=platform.python_version(), numpy=np.__version__, matplotlib=matplotlib.__version__,
        unit='CSV ms, integer microseconds internally; CSV / 1000 = seconds',
        interval_quantile='numpy percentile linear; intervals require >=2 records within same phase',
        checks=checks, dos=dos_summary, metadata_intervals_ms=metadata,
        source_sha256={str(p.relative_to(LAB)):digest(p) for p in source_files})
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    table(out,'phase_rates.csv',rates)
    table(out,'per_id_intervals.csv',intervals)
    table(out,'boundary_gaps.csv',crossings)
    table(out,'adjacent_gaps.csv',gaps)
    table(out,'time_rates.csv',bins)

    fig, axes = plt.subplots(2,1,figsize=(11,7))
    for ax, session in zip(axes, ('normal','attack')):
        b = [x for x in bins if x['session']==session]
        ax.plot([x['start_relative_s'] for x in b],[x['records_per_s'] for x in b],label='All logged records')
        ax.set(title=f'{session}: full recording, span {checks[session]["span_s"]:.6f} s',
               xlabel='Time since recording first frame (s)',ylabel='Logged records / s')
        ax.grid(alpha=.3)
        ax.legend()
    fig.suptitle('Exposure-normalized 1 s bins; final partial bin uses actual exposure')
    save(fig,out,'session_rates.png')

    fig, ax = plt.subplots(figsize=(11,4.8))
    b = [x for x in bins if x['session']=='attack']
    x = [v['start_relative_s'] for v in b]
    ax.plot(x,[v['dos_records_per_s'] for v in b],label='ID 0: all records')
    ax.plot(x,[v['dos_unique_timestamp_rate'] for v in b],label='ID 0: unique timestamp sensitivity')
    ax.plot(x,[v['normal_label_frames']/v['exposure_s'] for v in b],label='Normal label=0')
    ax.axvspan((start-lo)/1e6,(end-lo)/1e6,color='red',alpha=.1,label='First-last DoS record')
    ax.set(xlabel='Time since attack recording first frame (s)',ylabel='Logged records / s',
           title=f'Attack recording full span {checks["attack"]["span_s"]:.6f} s | 1 s bins')
    ax.legend(fontsize=8)
    ax.grid(alpha=.3)
    save(fig,out,'dos_rates.png')

    fig, ax = plt.subplots(figsize=(12,6))
    for k,i in enumerate(ids):
        for label,col,dy in [('0','#2878b5',0),('1','#e68a00',.16)]:
            ts = [t/1e6 for t,j,g,l in a if j==i and l==label]
            ax.scatter(ts,[k+dy]*len(ts),s=3,c=col,label=f'label={label}' if k==0 else None)
    ax.axvspan(start/1e6,end/1e6,color='red',alpha=.1,label='DoS first-last')
    ax.set(yticks=range(len(ids)),yticklabels=[f'{i:08X}' for i in ids],
           xlabel='PCAN time offset (s), CSV timestamp / 1000',ylabel='Baseline CAN ID (hex)',
           title=f'Attack ID timeline | offset {lo/1e6:.6f}-{hi/1e6:.6f} s | blue normal / orange attack')
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    save(fig,out,'normal_id_timeline.png')

    fig, axes = plt.subplots(1,2,figsize=(12,5))
    for ax, metric in zip(axes,('median_ms','max_ms')):
        for label,col in [('pre','#2878b5'),('during','#d62728'),('post','#2ca02c')]:
            vals = [next(r[metric] for r in intervals if r['can_id']==f'{i:08X}' and
                         r['selection']=='label0_only' and r['phase']==label) for i in ids]
            ax.plot(range(len(ids)),[np.nan if v is None else v for v in vals],'o-',label=label,color=col)
        ax.set(xticks=range(len(ids)),xticklabels=[f'{i:08X}' for i in ids],ylabel=f'{metric} (ms)',
               title='Normal label=0, within-phase intervals only')
        ax.tick_params(axis='x',rotation=90)
        ax.grid(alpha=.3)
        ax.legend()
    fig.suptitle(f'PCAN offset pre [{lo/1e6:.6f}, {start/1e6:.6f}) s; post ({end/1e6:.6f}, {hi/1e6:.6f}] s\n'
                 'Normal label=0 only; <2 records: no point; crossing gaps excluded (see adjacent_gaps.csv)')
    save(fig,out,'normal_id_intervals.png')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
