import os, subprocess, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SANDBOX = os.path.join(os.path.dirname(__file__), '..', 'dev', 'sandbox.sh')
REAL_HOME = os.path.expanduser('~')
VARS = ('XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME')


def run(*args):
    script = 'for v in ' + ' '.join(VARS) + ' HOME OMATROPHY_SANDBOX; do printf "%s=%s\\n" "$v" "${!v}"; done'
    out = subprocess.run(['bash', SANDBOX, *args, 'bash', '-c', script],
                         capture_output=True, text=True, check=True).stdout
    return dict(line.split('=', 1) for line in out.splitlines())


class SandboxTest(unittest.TestCase):
    # Regression: a manual smoke test once removed the real ~/.local/share
    # because XDG_DATA_HOME was set in one shell and cleaned in the next.

    def test_points_every_xdg_dir_into_a_throwaway_folder(self):
        env = run()
        root = env['OMATROPHY_SANDBOX']
        self.assertFalse(root.startswith(REAL_HOME + os.sep))
        for var in VARS:
            self.assertTrue(env[var].startswith(root + os.sep), var)
        self.assertEqual(env['HOME'], REAL_HOME)

    def test_removes_its_folder_afterwards(self):
        root = run()['OMATROPHY_SANDBOX']
        self.assertFalse(os.path.exists(root))

    def test_home_flag_fakes_home_too(self):
        env = run('--home')
        self.assertTrue(env['HOME'].startswith(env['OMATROPHY_SANDBOX'] + os.sep))

    def test_cleanup_only_matches_its_own_mktemp_name(self):
        with open(SANDBOX) as f:
            self.assertIn('"$tmp_root"/omatrophy-sandbox.????????) rm -rf -- "$dir"', f.read())

    def test_no_dev_script_removes_an_xdg_or_home_variable(self):
        dev = os.path.dirname(SANDBOX)
        for name in sorted(os.listdir(dev)):
            if not name.endswith('.sh'):
                continue
            with open(os.path.join(dev, name)) as f:
                code = '\n'.join(l for l in f if not l.lstrip().startswith('#'))
            self.assertNotRegex(code, r'rm -[a-zA-Z]*r[a-zA-Z]*f?[^\n]*\$\{?(XDG_|HOME)', name)


if __name__ == '__main__':
    unittest.main()
