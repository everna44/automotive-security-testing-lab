"""표준 라이브러리만 사용한 제한 표본 분석. 원본 ZIP은 수정하지 않는다."""
import csv
import hashlib
import io
import json
import platform
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent
ARCHIVE = BASE.parent / 'data/raw/Autohack2025_Dataset.zip'
MEMBER = 'Autohack2025_Dataset/Interface/test/autohack_test_both_interface.csv'
LIMIT = 10000
OUT = BASE / 'results'
OUT.mkdir(exist_ok=True)
rows = {'Normal': [], 'Fuzzing': []}
labels = Counter()
interfaces = Counter()
scanned = 0
with zipfile.ZipFile(ARCHIVE) as z:
    with z.open(MEMBER) as binary:
        reader = csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8-sig', newline=''))
        columns = reader.fieldnames
        assert columns == ['Interface', 'Timestamp', 'Arbitration_ID', 'DLC', 'Data', 'Label']
        for line, row in enumerate(reader, 2):
            scanned += 1
            labels[row['Label']] += 1
            interfaces[row['Interface']] += 1
            label = row['Label']
            if row['Interface'] == 'C-CAN' and label in rows and len(rows[label]) < LIMIT:
                rows[label].append({'source_line': line, **row})
            if all(len(v) == LIMIT for v in rows.values()):
                break

def quantile(values, p):
    values = sorted(values)
    return float(values[int((len(values)-1)*p)]) if values else None

summary = {'python': platform.python_version(), 'archive_sha256': hashlib.file_digest(ARCHIVE.open('rb'), 'sha256').hexdigest(),
           'member': MEMBER, 'columns': columns, 'selection': 'C-CAN; first up to 10000 rows per label in file order',
           'scanned_rows': scanned, 'scanned_prefix_labels': dict(labels), 'scanned_prefix_interfaces': dict(interfaces), 'groups': {}}
counts = {}
gaps = {}
for label, data in rows.items():
    if not data:
        raise ValueError(f'No rows for {label}')
    with (OUT / f'{label.lower()}_frames.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
    times = [Decimal(r['Timestamp']) for r in data]
    delta = [b-a for a,b in zip(times,times[1:])]
    gaps[label] = delta
    counts[label] = Counter(r['Arbitration_ID'] for r in data)
    bad = [r['source_line'] for r in data if len(r['Data'].split()) != int(r['DLC'])]
    summary['groups'][label] = {
        'count': len(data), 'first_timestamp': str(times[0]), 'last_timestamp': str(times[-1]),
        'unique_ids': len(counts[label]), 'dlc_counts': dict(Counter(r['DLC'] for r in data)),
        'unique_payloads': len({r['Data'] for r in data}), 'payload_length_mismatch_lines': bad,
        'negative_gaps': sum(d < 0 for d in delta), 'zero_gaps': sum(d == 0 for d in delta),
        'gap_seconds': {'min': float(min(delta)), 'median': quantile(delta,.5), 'p95': quantile(delta,.95), 'max': float(max(delta))},
        'top_ids': counts[label].most_common(10), 'examples': data[:3]}
with (OUT / 'can_id_counts.csv').open('w', newline='') as f:
    w=csv.writer(f); w.writerow(['CAN_ID','Normal','Fuzzing'])
    for cid in sorted(set(counts['Normal']) | set(counts['Fuzzing']), key=lambda v:int(v,16)):
        w.writerow([cid,counts['Normal'][cid],counts['Fuzzing'][cid]])
with (OUT / 'intervals.csv').open('w', newline='') as f:
    w=csv.writer(f); w.writerow(['Label','previous_source_line','source_line','gap_seconds'])
    for label,data in rows.items():
        for a,b,d in zip(data,data[1:],gaps[label]): w.writerow([label,a['source_line'],b['source_line'],str(d)])

# SVG를 직접 생성하여 추가 패키지 설치 없이 결과를 시각화한다.
def chart(path, title, categories, series, ylabel):
    width,height=1050,430; left,top,bottom=85,65,330
    maximum=max(max(v) for v in series.values()) or 1
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>',f'<text x="30" y="28" font-family="sans-serif" font-size="18">{escape(title)}</text>',f'<text x="15" y="52" font-family="sans-serif" font-size="12">{escape(ylabel)}</text>']
    for i in range(6):
        y=bottom-(bottom-top)*i/5
        parts += [f'<path d="M {left} {y} H 1020" stroke="#ddd"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-size="12">{maximum*i/5:.0f}</text>']
    step=930/len(categories)
    for j,(name,values) in enumerate(series.items()):
        color=['#2471a3','#dc7633'][j]
        parts.append(f'<text x="{650+j*160}" y="50" fill="{color}" font-family="sans-serif">{name}</text>')
        for i,value in enumerate(values):
            h=(bottom-top)*value/maximum
            parts.append(f'<rect x="{left+i*step+j*step*.4}" y="{bottom-h}" width="{step*.37}" height="{h}" fill="{color}"><title>{escape(name)} {escape(categories[i])}: {value}</title></rect>')
    for i,label in enumerate(categories):
        parts.append(f'<text x="{left+i*step+step*.4}" y="350" transform="rotate(25 {left+i*step+step*.4} 350)" font-family="sans-serif" font-size="11">{escape(label)}</text>')
    parts.append('</svg>'); path.write_text('\n'.join(parts))
ids=[cid for cid,_ in counts['Normal'].most_common(15)]
chart(OUT/'can_id_distribution.svg','C-CAN: top 15 Normal IDs + all other IDs',ids+['Other IDs'],{label:[c[cid] for cid in ids]+[sum(v for cid,v in c.items() if cid not in ids)] for label,c in counts.items()},'Frame count (each label n=10000)')
bounds=[Decimal('0'),Decimal('0.0001'),Decimal('0.0005'),Decimal('0.001'),Decimal('0.005'),Decimal('0.01'),Decimal('0.1')]
names=['<0','[0,0.1) ms','[0.1,0.5) ms','[0.5,1) ms','[1,5) ms','[5,10) ms','[10,100) ms','>=100 ms']
bins={}
for label,values in gaps.items():
    bins[label]=[sum(d<0 for d in values)]+[sum(a<=d<b for d in values) for a,b in zip(bounds,bounds[1:])]+[sum(d>=bounds[-1] for d in values)]
chart(OUT/'interval_distribution.svg','C-CAN: consecutive same-label observed gaps',names,bins,'Gap count (9999 per label)')
summary['interval_histogram']={'bins':names,'counts':bins}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
