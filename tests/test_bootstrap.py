#!/usr/bin/env python3
"""Exercise the complete GitHub entrypoint against disposable downloaded packages."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
BASH = shutil.which(os.environ.get('OVOII_TEST_BASH', 'bash'))
if not BASH:
    raise RuntimeError('Bash executable not found')


class BootstrapTests(unittest.TestCase):
    def run_entry(self, existing=False, check=False, corrupt=False, network=False,
                  partial=False, install_failure=False):
        with tempfile.TemporaryDirectory(prefix='ovoii-bootstrap-') as folder:
            root = Path(folder)
            target = root / 'target'
            if existing:
                (target / 'sh/src').mkdir(parents=True)
                (target / 'sh/src/core.sh').write_text('# fixture\n')
            elif partial:
                target.mkdir()
            trace = root / 'trace'
            archive = root / 'fixture.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                for name in ['install.sh', 'apply-brand.sh', 'sing-box.sh', 'src/brand.sh', 'LICENSE', 'NOTICE.md']:
                    text = '# fixture\n'
                    if name in ['install.sh', 'apply-brand.sh']:
                        text = '#!/bin/bash\nprintf "%s\\n" "' + name + ':$*" >> "$TRACE"\n'
                        if install_failure and name == 'install.sh':
                            text += 'exit 33\n'
                    data = text.encode()
                    member = tarfile.TarInfo('ovoii-sing-box-1.0.3/' + name)
                    member.size = len(data)
                    tar.addfile(member, io.BytesIO(data))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            if corrupt:
                archive.write_bytes(b'corrupt downloaded file')
            original = (PROJECT / 'bootstrap.sh').read_text()
            # Only the disposable test copy bypasses root and redirects production paths.
            needle = "[[ $EUID == 0 ]] || fail '请以 root 执行。'"
            self.assertEqual(original.count(needle), 1)
            original = original.replace(needle, ': # test process is not root')
            original = original.replace('/etc/sing-box', str(target))
            original = original.replace('/usr/local/bin/', str(root / 'bin') + '/')
            import re
            original, count = re.subn(r'^package_sha256=.+$', 'package_sha256=' + digest, original, flags=re.M)
            self.assertEqual(count, 1)
            script = root / 'bootstrap.sh'; script.write_text(original)
            shims = root / 'shims'; shims.mkdir()
            tools = {
                'uname': '#!/bin/sh\nif [ "$1" = -s ]; then echo Linux; else echo x86_64; fi\n',
                'bash': '#!/bin/sh\nexec "$TEST_BASH" "$@"\n',
                'curl': '#!/bin/sh\n[ "$NETWORK_FAILURE" = 0 ] || exit 22\nwhile [ "$#" -gt 0 ]; do\nif [ "$1" = -o ]; then cp "$ARCHIVE" "$2"; exit; fi\nshift\ndone\nexit 1\n',
                'sha256sum': '#!/usr/bin/env python3\nimport hashlib,sys\ns=sys.stdin.read().strip().split(None,1)\nsys.exit(0 if len(s)==2 and hashlib.sha256(open(s[1],"rb").read()).hexdigest()==s[0] else 1)\n',
            }
            for name, code in tools.items():
                p = shims / name; p.write_text(code); p.chmod(0o755)
            env = dict(os.environ, PATH=str(shims) + os.pathsep + os.environ['PATH'],
                       TEST_BASH=BASH, TRACE=str(trace), ARCHIVE=str(archive),
                       NETWORK_FAILURE='1' if network else '0')
            result = subprocess.run([BASH, str(script)] + (['--check'] if check else []),
                                    env=env, capture_output=True, text=True, errors='replace', timeout=10)
            return result, trace.read_text() if trace.exists() else ''

    def test_fresh_server_installs_pinned_kernel(self):
        r, trace = self.run_entry()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(trace, 'install.sh:--core-version v1.14.3\n')

    def test_existing_install_only_replaces_management_scripts(self):
        r, trace = self.run_entry(existing=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(trace, 'apply-brand.sh:--apply\n')

    def test_fresh_check_does_not_install(self):
        r, trace = self.run_entry(check=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(trace, '')

    def test_existing_check_does_not_apply(self):
        r, trace = self.run_entry(existing=True, check=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(trace, 'apply-brand.sh:--check\n')

    def test_checksum_mismatch_never_runs_installer(self):
        r, trace = self.run_entry(corrupt=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(trace, '')
        self.assertIn('SHA-256', r.stderr)

    def test_download_failure_never_runs_installer(self):
        r, trace = self.run_entry(network=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(trace, '')

    def test_partial_existing_install_is_not_overwritten(self):
        r, trace = self.run_entry(partial=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(trace, '')

    def test_install_failure_is_not_reported_as_success(self):
        r, trace = self.run_entry(install_failure=True)
        self.assertEqual(r.returncode, 33)
        self.assertNotIn('操作完成', r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
