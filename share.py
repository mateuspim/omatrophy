"""Save a platinum as an image: PlatinumShare.qml drawn by a throwaway,
offscreen Quickshell instance and written to a PNG.

The live shell is never asked: its windows are layer surfaces over the
game, and a grab there would need a visible card. A separate process
draws the same QML the platinum toast uses, on the GPU (the software
renderer drops the card's masks and its art), and exits. The drawing
fetches nothing: omatrophy.py caches the store's art first (once, as the
platinum toast does), and art without a local copy is left out. Nothing
is uploaded.
"""
import json, os, re, shutil, subprocess, tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
# Omarchy's shell modules, linked into the throwaway config folder so
# `import qs.Commons` resolves as it does in the live shell.
OMARCHY_SHELL = '/usr/share/omarchy/shell'
# The scene is 1200 x 630 (PlatinumShare.qml), grabbed at twice that.
SIZE = (2400, 1260)
# When the grab happens: the event goes in at 300 ms, and the glitter
# burst it sets off is still in the air 700 ms later.
SETTLE_MS = 1000
TIMEOUT = 30


def slug(name):
    """A file name part from a game's name: lowercase words joined by
    hyphens, nothing a shell or file manager trips on."""
    words = re.findall(r'[a-z0-9]+', str(name).lower())
    return '-'.join(words)[:80].strip('-') or 'game'


def pictures_dir(home=None, config_home=None):
    """XDG_PICTURES_DIR from user-dirs.dirs, else ~/Pictures."""
    home = home or os.path.expanduser('~')
    config_home = config_home or os.environ.get('XDG_CONFIG_HOME') or f'{home}/.config'
    try:
        with open(f'{config_home}/user-dirs.dirs') as f:
            text = f.read()
    except OSError:
        text = ''
    match = re.search(r'^XDG_PICTURES_DIR="([^"\n]*)"', text, re.M)
    path = match.group(1).replace('$HOME', home) if match else ''
    # Only an absolute folder other than home itself: the spec's "$HOME/"
    # means "no pictures folder", and a relative one is undefined.
    if not path.startswith('/') or os.path.normpath(path) == os.path.normpath(home):
        path = f'{home}/Pictures'
    return path


def default_path(game_name, home=None, config_home=None):
    return f'{pictures_dir(home, config_home)}/omatrophy/{slug(game_name)}-platinum.png'


def out_path(out, game_name, home=None, config_home=None):
    """Where the image goes: `--out` (with `~` expanded; a folder gets the
    default file name inside it), else the default path."""
    if not out:
        return default_path(game_name, home, config_home)
    out = os.path.abspath(os.path.expanduser(out))
    if os.path.isdir(out):
        out = f'{out}/{slug(game_name)}-platinum.png'
    return out


def local_art(value):
    """A file:// URL for a local image (a file:// URL or an absolute path
    that exists), else '': the throwaway shell would fetch a web URL."""
    value = str(value or '')
    path = value[len('file://'):] if value.startswith('file://') else value
    return 'file://' + path if path.startswith('/') and os.path.isfile(path) else ''


def scene_qml(scene, event_file, out_file, theme, size=SIZE, settle_ms=SETTLE_MS):
    """The throwaway shell's shell.qml. Every path goes in as a JSON string
    literal, so no path can end a string and add code."""
    q = json.dumps
    return f'''import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons

ShellRoot {{
  // The live shell loads the current theme into Commons.Color at startup.
  FileView {{ path: {q(theme + '/colors.toml')}; blockLoading: true; printErrors: false; onLoaded: Commons.Color.loadColors(text()) }}
  FileView {{ path: {q(theme + '/shell.toml')}; blockLoading: true; printErrors: false; onLoaded: Commons.Color.loadShell(text()) }}
  FileView {{ id: eventFile; path: {q(event_file)}; blockLoading: true }}
  FloatingWindow {{
    implicitWidth: 1200
    implicitHeight: 630
    color: "transparent"
    Loader {{
      id: scene
      source: {q('file://' + scene)}
    }}
    // The event goes in once the theme has reached Commons.Color: the
    // card's border is a Shape, which keeps the colour it was first
    // drawn in until its path changes.
    Timer {{
      interval: 300
      running: true
      onTriggered: {{
        var ev = JSON.parse(eventFile.text())
        scene.item.iconSet = ev.icon_set || "omarchy"
        scene.item.event = ev
      }}
    }}
    Timer {{
      interval: {int(settle_ms)}
      running: true
      onTriggered: scene.grabToImage(function(r) {{ r.saveToFile({q(out_file)}); Qt.quit() }}, Qt.size({int(size[0])}, {int(size[1])}))
    }}
  }}
}}
'''


def theme_dir(home=None):
    return f'{home or os.path.expanduser("~")}/.local/state/omarchy/current/theme'


def render(event, out, run=subprocess.run, shell_dir=OMARCHY_SHELL, theme=None):
    """Draw `event` (the platinum event plus `platinum`, `store_name` and
    `icon_set`) to the PNG `out`; returns `out`. Raises RuntimeError with a
    message for the owner when it can't."""
    if not shutil.which('quickshell'):
        raise RuntimeError('quickshell is not installed; it draws the image (Omarchy ships it)')
    if not os.path.isdir(f'{shell_dir}/Commons'):
        raise RuntimeError(f"Omarchy's shell isn't at {shell_dir}; the image uses its theme and fonts")
    event = dict(event, hero=local_art(event.get('hero')), header=local_art(event.get('header')))
    with tempfile.TemporaryDirectory(prefix='omatrophy-share-') as tmp:
        os.symlink(f'{shell_dir}/Commons', f'{tmp}/Commons')
        os.symlink(f'{shell_dir}/Ui', f'{tmp}/Ui')
        with open(f'{tmp}/event.json', 'w') as f:
            json.dump(event, f)
        drawn = f'{tmp}/platinum.png'
        with open(f'{tmp}/shell.qml', 'w') as f:
            f.write(scene_qml(f'{REPO}/PlatinumShare.qml', f'{tmp}/event.json', drawn, theme or theme_dir()))
        # Offscreen, on the GPU through OpenGL: the offscreen platform picks
        # the software renderer by default, which drops every MultiEffect
        # (the card's mask and art, the trophy's inlay, the blur).
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='rhi', QSG_RHI_BACKEND='opengl')
        if theme:
            # Commons.Color loads the current theme from under $HOME once it
            # starts, over the FileViews, so another theme (dev/render.sh
            # --theme) needs a home of its own whose current theme it is.
            os.makedirs(f'{tmp}/home/.local/state/omarchy/current')
            os.symlink(theme, f'{tmp}/home/.local/state/omarchy/current/theme')
            env['HOME'] = f'{tmp}/home'
        try:
            run(['quickshell', '-p', tmp], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            pass
        if not os.path.isfile(drawn):
            raise RuntimeError('Quickshell drew no image; run `omatrophy.py share` from a terminal '
                               'inside the desktop session and check `quickshell` starts')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        place(drawn, out)
    return out


def notify(summary, body, image=''):
    """A desktop notification, for a save started from the panel, which
    may be gone by the time the image is written. Quietly nothing without
    notify-send."""
    # `--` ends the options: a game's name or an error never reads as one.
    args = ['notify-send', '-a', 'OmaTrophy'] + (['-i', image] if image else []) + ['--', summary, body]
    try:
        subprocess.run(args, timeout=4, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def place(drawn, out):
    """Move the drawn image to `out` through a temporary file beside it and
    a rename: shutil.move copies across filesystems (/tmp is often tmpfs),
    and that copy would write through a link already at `out`. The mode is
    set on the open file, never by path: in a folder another user can write
    in, they could swap the temporary name for a link to one of the
    player's files before a path chmod (marketplace review, finding 11)."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(out)), prefix='.omatrophy-', suffix='.png')
    try:
        with os.fdopen(fd, 'wb') as dst, open(drawn, 'rb') as src:
            shutil.copyfileobj(src, dst)
            os.fchmod(dst.fileno(), 0o644)
        os.replace(tmp, out)
    except BaseException:
        os.unlink(tmp)
        raise
