# -*- coding: utf-8 -*-
"""
Auto-update from GitHub (Pi only).

Compares the local version.json with the one on GitHub. If they differ, it
makes this folder an exact copy of GitHub (git fetch + git reset --hard) and
restarts the scoreboard so the new code runs.

Only runs with --production, and only if this folder is a git clone, so it
never touches your working copy on Windows. If GitHub can't be reached it just
carries on with the current version.
"""
import json
import os
import subprocess
import sys
import time

import requests

from paths import BASE_DIR

GITHUB_USER = 'chitown88'
GITHUB_REPO = 'nfl-led-scoreboard'
BRANCH = 'main'

VERSION_FILE = os.path.join(BASE_DIR, 'version.json')
REMOTE_VERSION_URL = f'https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/version.json'

CHECK_EVERY_HOURS = 3
_last_check = 0


def local_version():
    try:
        with open(VERSION_FILE) as f:
            return json.load(f)['version']
    except Exception as e:
        print(f'Update check: could not read version.json: {e}')
        return None


def remote_version():
    try:
        # the t= parameter stops a cached copy being returned
        r = requests.get(REMOTE_VERSION_URL, params={'t': int(time.time())}, timeout=5)
        r.raise_for_status()
        return r.json()['version']
    except Exception as e:
        print(f'Update check: could not reach GitHub, keeping current version ({e})')
        return None


def git(*args):
    """Run git in the project folder, as the folder's owner (normally 'pi').

    The scoreboard runs as root (sudo), but git should run as the folder's owner,
    so it doesn't leave root-owned files that 'pi' can't change later.
    """
    cmd = ['git', '-c', f'safe.directory={BASE_DIR}', '-C', BASE_DIR] + list(args)
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        import pwd   # Linux only, so imported here
        owner = pwd.getpwuid(os.stat(BASE_DIR).st_uid).pw_name
        if owner != 'root':
            cmd = ['sudo', '-u', owner] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def check_for_update(force=False):
    """Update from GitHub and restart if version.json there is different.

    Called at startup (force=True) and then from the main loop; between those
    it only actually checks every CHECK_EVERY_HOURS.
    """
    global _last_check
    if not force and time.time() - _last_check < CHECK_EVERY_HOURS * 3600:
        return
    _last_check = time.time()

    if not os.path.isdir(os.path.join(BASE_DIR, '.git')):
        print('Update check: not a git clone, skipping')
        return

    local, remote = local_version(), remote_version()
    if remote is None:
        return
    if local == remote:
        print(f'Up to date (version {local})')
        return

    print(f'Updating from {local} to {remote}...')
    try:
        before = git('rev-parse', 'HEAD')
        git('fetch', '--quiet', 'origin', BRANCH)
        git('reset', '--hard', f'origin/{BRANCH}')
        after = git('rev-parse', 'HEAD')
    except Exception as e:
        print(f'Update failed, keeping current version: {e}')
        return

    if before == after:
        # version.json on GitHub changed but the code hasn't arrived yet; try next time
        print('Nothing new downloaded yet, will try again later')
        return

    print(f'Updated to {local_version()}. Restarting...')
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)
