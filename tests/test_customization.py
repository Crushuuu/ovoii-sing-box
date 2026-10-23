#!/usr/bin/env python3
"""Offline behavior and migration regression checks; no live VPS credentials."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import urlsplit

PROJECT = Path(__file__).resolve().parents[1]
BASH = os.environ.get('OVOII_TEST_BASH', 'bash')


class CustomizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        major = subprocess.check_output([BASH, '-c', 'echo "${BASH_VERSINFO[0]}"'], text=True).strip()
        if int(major) < 4:
            raise RuntimeError('Upstream requires Bash 4+; set OVOII_TEST_BASH to a supported Bash.')
        cls.tmp = tempfile.TemporaryDirectory(prefix='ovoii-tests-')
        cls.original = Path(cls.tmp.name) / 'upstream-core.sh'
        cls.original.write_bytes((PROJECT / 'tests/fixtures/upstream-core.sh').read_bytes())
        cls.shim = Path(cls.tmp.name) / 'shim'
        cls.shim.mkdir()
        (cls.shim / 'shuf').write_text('#!/bin/sh\nprintf \'4\\n\'\n')
        (cls.shim / 'shuf').chmod(0o755)
        (cls.shim / 'qrencode').write_text('#!/bin/sh\necho local-qr\n')
        (cls.shim / 'qrencode').chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def shell(self, body, original=False):
        core = self.original if original else PROJECT / 'src/core.sh'
        env = dict(os.environ, OVOII_PROJECT=str(PROJECT), OVOII_CORE=str(core), PATH=str(self.shim) + os.pathsep + os.environ['PATH'])
        # Fixed random choices; base64 shim handles GNU -w syntax on macOS too.
        prelude = '''
shuf() { printf '4\\n'; }
base64() { python3 -c 'import base64,sys;sys.stdout.write(base64.b64encode(sys.stdin.buffer.read()).decode())'; }
_green() { printf '%s' "$*"; }
_red() { printf '%s' "$*"; }
_blue() { printf '%s' "$*"; }
_cyan() { printf '%s' "$*"; }
warn() { printf '%s\\n' "$*"; }
err() { printf '%s\\n' "$*" >&2; exit 23; }
. "$OVOII_PROJECT/src/brand.sh"
. "$OVOII_CORE"
is_core=sing-box
is_core_name=sing-box
is_sh_dir=/etc/sing-box/sh
is_sh_ver=v1.18
is_core_ver=1.14.3
is_core_status=running
'''
        return subprocess.run([BASH, '-c', prelude + body], env=env, text=True, capture_output=True)

    def test_shell_syntax_and_license_preserved(self):
        for file in [*PROJECT.glob('*.sh'), *PROJECT.joinpath('src').glob('*.sh')]:
            subprocess.run([BASH, '-n', str(file)], check=True, capture_output=True)
        self.assertEqual(hashlib.sha256((PROJECT / 'LICENSE').read_bytes()).hexdigest(), '3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986')

    def test_installer_reports_success_after_cleanup(self):
        text = (PROJECT / 'install.sh').read_text()
        body = text[text.index('exit_and_del_tmpdir() {'):text.index('\n# main\n')]
        for success, expected in [(True, 0), (False, 1)]:
            with self.subTest(success=success), tempfile.TemporaryDirectory(prefix='ovoii-exit-') as parent:
                target = Path(parent) / 'installer-temporary-files'
                target.mkdir()
                script = 'tmpdir=$1; msg() { :; };\n' + body + '\nexit_and_del_tmpdir' + (' ok' if success else '')
                result = subprocess.run([BASH, '-c', script, 'test-installer', str(target)], capture_output=True)
                self.assertEqual(result.returncode, expected)
                self.assertFalse(target.exists())

    def test_export_changes_only_remark_for_supported_protocols(self):
        common = '''
is_dont_show_info=1
is_addr=192.0.2.10
port=36009
uuid=00000000-0000-4000-8000-000000000001
password=example-password
is_servername=example.com
is_public_key=example-public-key
is_https_port=443
ss_method=aes-128-gcm
ss_password=example-password
is_socks_user=existing-user
is_socks_pass=existing-password
'''
        cases = [
            'net=reality; is_protocol=vless',
            'net=tcp; is_protocol=vmess',
            'net=ws; is_protocol=vmess; host=example.com; path=/example',
            'net=ws; is_protocol=vless; host=example.com; path=/example',
            'net=trojan; is_protocol=trojan',
            'net=tuic; is_protocol=tuic',
            'net=ss; is_protocol=ss',
            'net=anytls; is_protocol=anytls',
            'net=anytls; is_protocol=anytls; is_anytls_domain=example.com',
            'net=socks; is_protocol=socks',
        ]
        for case in cases:
            with self.subTest(case=case):
                body = common + case + '\ninfo\nprintf "%s" "$is_url"\n'
                old, new = self.shell(body, True), self.shell(body)
                self.assertEqual((old.returncode, new.returncode), (0, 0), old.stderr + new.stderr)
                if new.stdout.startswith('vmess://'):
                    before = json.loads(base64.b64decode(old.stdout[8:]))
                    after = json.loads(base64.b64decode(new.stdout[8:]))
                    self.assertTrue(before.pop('ps').startswith('233boy-'))
                    self.assertTrue(after.pop('ps').startswith('ovoii-'))
                    self.assertEqual(before, after)
                else:
                    before, after = urlsplit(old.stdout), urlsplit(new.stdout)
                    self.assertEqual(before._replace(fragment=''), after._replace(fragment=''))
                    self.assertTrue(after.fragment.startswith('ovoii-'))

    def test_menu_qr_and_attribution(self):
        result = self.shell('ask() { REPLY=; }; is_main_menu; . "$OVOII_PROJECT/src/help.sh"; about')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ovoii', result.stdout)
        self.assertIn('GPL-3.0', result.stdout)
        self.assertIn('基于 233boy/sing-box', result.stdout)
        self.assertNotIn('推广', result.stdout)
        self.assertNotIn('t.me', result.stdout)
        qr = self.shell('''
info() { is_url='vless://example@192.0.2.1:443?security=reality#ovoii-example'; }
qrencode() { echo "LOCAL-QR:$*"; }
url_qr qr
''')
        self.assertEqual(qr.returncode, 0, qr.stderr)
        self.assertIn('LOCAL-QR:', qr.stdout)
        self.assertIn('vless://', qr.stdout)
        self.assertNotIn('233boy', qr.stdout)
        self.assertNotIn('https://', qr.stdout)

    def test_upstream_script_updates_blocked_before_network_or_mutation(self):
        bodies = [
            'main update sh', 'main U', 'main update.sh', 'update 2',
            '. "$OVOII_PROJECT/src/download.sh"; get_latest_version sh',
            '. "$OVOII_PROJECT/src/download.sh"; download sh v9.9.9',
            'uninstall() { echo BAD-UNINSTALL; }; get reinstall',
        ]
        for body in bodies:
            with self.subTest(body=body):
                result = self.shell('''
_wget() { echo BAD-NETWORK; exit 99; }
load() { . "$OVOII_PROJECT/src/$1"; }
''' + body)
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assertIn('ovoii', result.stderr)
                self.assertNotIn('BAD-', result.stdout)

    def fixture(self, folder):
        folder = folder.resolve()
        root, bindir = folder / 'etc/sing-box', folder / 'bin'
        for directory in [root / 'sh/src', root / 'bin', root / 'conf', bindir]:
            directory.mkdir(parents=True)
        (root / 'sh/src/core.sh').write_text('#!/bin/bash\n# original management script\n')
        (root / 'sh/sing-box.sh').write_text('#!/bin/bash\necho original\n')
        (root / 'bin/sing-box').write_text('#!/bin/sh\nexit 0\n')
        (root / 'bin/sing-box').chmod(0o755)
        (root / 'config.json').write_text('{"log":{"level":"warn"}}')
        (root / 'conf/reality.json').write_text('{"fixture":"not-real-private-key","port":36009}')
        (root / 'bin/tls.key').write_text('not-a-real-test-key')
        for name in ['sb', 'sing-box']:
            (bindir / name).symlink_to(root / 'sh/sing-box.sh')
        return root, bindir

    def data_digest(self, root):
        paths = [root / 'config.json', *root.joinpath('conf').rglob('*'), *root.joinpath('bin').rglob('*')]
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

    def apply(self, root, bindir, *args, env=None):
        return subprocess.run([BASH, str(PROJECT / 'apply-brand.sh'), '--root', str(root), '--bin-dir', str(bindir), *args], text=True, capture_output=True, env=env)

    def test_check_apply_reapply_and_rollback_preserve_data(self):
        with tempfile.TemporaryDirectory(prefix='ovoii-migration-') as temp:
            root, bindir = self.fixture(Path(temp))
            before = self.data_digest(root)
            original = (root / 'sh/sing-box.sh').read_bytes()
            check = self.apply(root, bindir, '--check')
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertFalse((root / 'ovoii-backups').exists())
            for _ in range(2):
                applied = self.apply(root, bindir, '--apply')
                self.assertEqual(applied.returncode, 0, applied.stderr)
                self.assertEqual(before, self.data_digest(root))
                self.assertTrue((root / 'sh/src/brand.sh').is_file())
                self.assertEqual(os.readlink(bindir / 'ovoii'), str(root / 'sh/sing-box.sh'))
            backups = sorted((root / 'ovoii-backups').iterdir())
            first = next(p for p in backups if (p / 'command-state').read_text().strip() == 'absent')
            restored = self.apply(root, bindir, '--rollback', str(first))
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(original, (root / 'sh/sing-box.sh').read_bytes())
            self.assertEqual(before, self.data_digest(root))
            self.assertFalse((bindir / 'ovoii').exists())
            self.assertTrue((bindir / 'sb').is_symlink())
            self.assertFalse((root / '.ovoii-brand-lock').exists())

    def test_failed_swap_restores_original_scripts(self):
        with tempfile.TemporaryDirectory(prefix='ovoii-failure-') as temp:
            folder = Path(temp)
            root, bindir = self.fixture(folder)
            before = self.data_digest(root)
            shim = folder / 'shim'
            shim.mkdir()
            real_mv = shutil.which('mv')
            (shim / 'mv').write_text('#!/bin/bash\ncase "$1" in *"/.ovoii-sh."*) exit 71;; esac\nexec "' + real_mv + '" "$@"\n')
            (shim / 'mv').chmod(0o755)
            env = dict(os.environ, PATH=str(shim) + os.pathsep + os.environ['PATH'])
            result = self.apply(root, bindir, '--apply', env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('original management script', (root / 'sh/src/core.sh').read_text())
            self.assertEqual(before, self.data_digest(root))
            self.assertFalse((root / '.ovoii-brand-lock').exists())
            self.assertFalse((bindir / 'ovoii').exists())

    def test_refuse_unrelated_command(self):
        with tempfile.TemporaryDirectory(prefix='ovoii-conflict-') as temp:
            root, bindir = self.fixture(Path(temp))
            (bindir / 'ovoii').write_text('unrelated user command')
            result = self.apply(root, bindir, '--apply')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((bindir / 'ovoii').read_text(), 'unrelated user command')
            self.assertFalse((root / 'ovoii-backups').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
