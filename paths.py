"""Project paths and private session storage, independent of the working directory."""
from pathlib import Path
import os
import sys
import shutil

# A PyInstaller one-file build extracts Python files into a temporary _MEI folder.
# Force Playwright to look in its persistent browser installation instead.
if getattr(sys, 'frozen', False) and 'PLAYWRIGHT_BROWSERS_PATH' not in os.environ:
    if os.name == 'nt':
        browser_home = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'ms-playwright'
    elif sys.platform == 'darwin':
        browser_home = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
    else:
        browser_home = Path.home() / '.cache' / 'ms-playwright'
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_home)

PACKAGE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

ROOT = ((Path.home() / 'Documents' / 'DSEStockScraper') if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent)
ROOT.mkdir(parents=True, exist_ok=True)

# Ship verified seed events and URL mappings with the packaged GUI; never
# overwrite a user's own edits in their Documents/DSEStockScraper directory.
if getattr(sys, 'frozen', False):
    bundled = PACKAGE_DIR
    for fname in ('corporate_actions.csv', 'investing_split_urls.csv'):
        target = ROOT / fname
        source = bundled / fname
        if source.is_file() and not target.exists():
            try:
                shutil.copyfile(source, target)
            except OSError:
                pass
DATA_DIR = ROOT / 'data'
OUTPUT_DIR = ROOT / 'output'


def session_path():
    """Never save browser authentication credentials in the project folder."""
    if os.name == 'nt':
        home = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        home = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    folder = home / 'dsestockscraper-gui'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'browser_session.json'
