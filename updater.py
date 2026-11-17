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


def download():
    """Make this folder an exact copy of GitHub. Returns the commit before and after."""
    before = git('rev-parse', 'HEAD')
    git('fetch', '--quiet', 'origin', BRANCH)
    git('reset', '--hard', f'origin/{BRANCH}')
    return before, git('rev-parse', 'HEAD')


def check_for_update(matrix=None, force=False):
    """Update from GitHub and restart if version.json there is different.

    Called at startup (force=True) and then from the main loop; between those
    it only actually checks every CHECK_EVERY_HOURS. With a matrix, the update
    animation plays while it downloads.
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
    animation = None
    if matrix is not None:
        try:
            import update_animation as animation
            animation.announce(matrix, remote)
        except Exception as e:   # a broken animation must never stop an update
            print(f'Update animation unavailable: {e}')
            animation = None

    try:
        if animation:
            with animation.Updating(matrix, remote):
                before, after = download()
        else:
            before, after = download()
    except Exception as e:
        print(f'Update failed, keeping current version: {e}')
        if animation:
            animation.failed(matrix, local)
        return

    if before == after:
        # version.json on GitHub changed but the code hasn't arrived yet; try next time
        print('Nothing new downloaded yet, will try again later')
        return

    print(f'Updated to {local_version()}. Restarting...')
    if animation:
        animation.done(matrix, local_version())
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)
