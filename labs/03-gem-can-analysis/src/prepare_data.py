"""Download pinned official files, verify, and extract without overwriting originals."""
import hashlib
import json
import stat
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((BASE / 'metadata/source-manifest.json').read_text())
    raw = BASE / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    checks = []
    for entry in manifest['files']:
        path = raw / entry['key']
        if not path.exists():
            with urllib.request.urlopen(entry['links']['self'], timeout=120) as response:
                with path.open('xb') as output:
                    while block := response.read(1024 * 1024):
                        output.write(block)
        content = path.read_bytes()
        md5 = hashlib.md5(content).hexdigest()
        if len(content) != entry['size'] or 'md5:' + md5 != entry['checksum']:
            raise ValueError(f'Integrity mismatch: {path}; original retained for inspection')
        checks.append({'file': entry['key'], 'bytes': len(content), 'md5': md5,
                       'sha256': hashlib.sha256(content).hexdigest(), 'match': True})
    target = raw / 'extracted'
    with zipfile.ZipFile(raw / 'GEM_CAN_Dataset_R2.zip') as archive:
        members = archive.infolist()
        if sum(m.file_size for m in members) > 1024**3:
            raise ValueError('Uncompressed size exceeds 1 GiB safety bound')
        for member in members:
            name = PurePosixPath(member.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in member.filename:
                raise ValueError(f'Unsafe path: {name}')
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError(f'Symlink rejected: {name}')
            if not (target / member.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError(f'Path escapes target: {name}')
        for member in members:
            path = target / member.filename
            if member.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                content = archive.read(member)  # also validates ZIP CRC
                if path.exists():
                    if path.read_bytes() != content:
                        raise ValueError(f'Existing extraction differs: {path}')
                else:
                    with path.open('xb') as output:
                        output.write(content)
    report = {'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'source': manifest['record_url'], 'files': checks,
              'zip_members': [{'path': m.filename, 'bytes': m.file_size} for m in members]}
    (BASE / 'reports').mkdir(exist_ok=True)
    destination = BASE / 'reports/integrity.json'
    if not destination.exists():
        destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
