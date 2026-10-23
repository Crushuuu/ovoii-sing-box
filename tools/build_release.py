#!/usr/bin/env python3
"""Build a deterministic allowlisted runtime package; no server files are read."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'dist'
out.mkdir(parents=True, exist_ok=True)
version = '1.0.3'
names = ['sing-box.sh', 'install.sh', 'apply-brand.sh', 'README.md', 'NOTICE.md', 'LICENSE']
names += [str(p.relative_to(root)) for p in sorted((root / 'src').glob('*.sh'))]
archive = out / f'ovoii-sing-box-{version}.tar.gz'
with archive.open('wb') as raw:
    with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for name in names:
                data = (root / name).read_bytes()
                member = tarfile.TarInfo(f'ovoii-sing-box-{version}/{name}')
                member.size = len(data)
                member.mode = 0o755 if name.endswith('.sh') else 0o644
                member.mtime = 0
                tar.addfile(member, io.BytesIO(data))
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(out / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n')
bootstrap = root / 'bootstrap.sh'
text, count = re.subn(r'^package_sha256=.+$', 'package_sha256=' + digest,
                      bootstrap.read_text(), flags=re.M)
assert count == 1
bootstrap.write_text(text)
manifest = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
(out / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'asset': str(archive), 'sha256': digest, 'runtime_files': len(names)}))
