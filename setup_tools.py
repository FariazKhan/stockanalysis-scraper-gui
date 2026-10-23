"""First-time setup helpers. Only uses the Python standard library.

A frozen application includes all Python dependencies; it needs only the
matching Playwright Chromium binaries, installed by its bundled Node CLI.
A source checkout needs requirements.txt installed into the running Python
interpreter before the browser download.
"""
import os
from pathlib import Path
import subprocess
import sys


def windows_batch_quote(value):
    """Return a CMD-safe double quoted path (not arbitrary command input)."""
    value = str(value)
    if any(c in value for c in ('\"', '\r', '\n', '\0')):
        raise ValueError('Unsupported character in installation path')
    return '"' + value.replace('%', '%%') + '"'


def create_windows_setup_script(destination, status_file, *, frozen=False,
                                interpreter=None, requirements=None, node=None,
                                playwright_cli=None):
    """Write a visible CMD setup script, returning its path.

    The status marker is written BEFORE the terminal's final pause/delay, so
    the GUI can report a result without waiting for the user to close CMD.
    """
    destination = Path(destination)
    status_file = Path(status_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    marker = windows_batch_quote(status_file)
    lines = [
        '@echo off', 'setlocal DisableDelayedExpansion', 'chcp 65001 >nul',
        'title DSE Stock Scraper - First-time Setup',
        'echo ====================================================',
        'echo DSE STOCK SCRAPER - AUTOMATIC SETUP',
        'echo ====================================================',
        'echo Please keep this window open while setup is running.',
        'echo An internet connection is needed to download Chromium.',
        'echo.',
    ]
    if frozen:
        if not node or not playwright_cli:
            raise ValueError('The packaged Playwright installer was not found')
        lines.extend([
            'echo Python packages: already included in this app.',
            'echo Installing Chromium matching the packaged Playwright version...',
            f'{windows_batch_quote(node)} {windows_batch_quote(playwright_cli)} install chromium',
            'if errorlevel 1 goto failed',
        ])
    else:
        if not interpreter or not requirements:
            raise ValueError('Python and requirements.txt are needed for source setup')
        py = windows_batch_quote(interpreter)
        req = windows_batch_quote(requirements)
        lines.extend([
            'echo Step 1/2: Installing Python packages for this app...',
            f'{py} -m pip install -r {req}',
            'if errorlevel 1 goto failed',
            'echo.',
            'echo Step 2/2: Downloading and configuring Chromium...',
            f'{py} -m playwright install chromium',
            'if errorlevel 1 goto failed',
        ])
    lines.extend([
        'echo.',
        'echo ====================================================',
        'echo SETUP COMPLETED SUCCESSFULLY.',
        'echo You can return to the DSE Stock Scraper window.',
        'echo ====================================================',
        f'> {marker} echo OK',
        'timeout /t 8 /nobreak >nul',
        'exit /b 0',
        ':failed',
        'echo.',
        'echo SETUP FAILED. Check the error messages shown above.',
        'echo Check your internet connection, disk space and permissions.',
        f'> {marker} echo FAILED',
        'echo Press any key to close this terminal after reading the error.',
        'pause >nul',
        'exit /b 1',
    ])
    destination.write_text('\r\n'.join(lines) + '\r\n', encoding='utf-8')
    return destination


def start_windows_setup(script):
    """Open a *real* user-visible Windows command window without shell=True."""
    if os.name != 'nt':
        raise OSError('Windows CMD is only available on Windows')
    return subprocess.Popen(['cmd.exe', '/c', str(Path(script).resolve())],
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
                            cwd=str(Path(script).resolve().parent))


def console_python():
    """If the app started with pythonw, prefer python to show install output."""
    executable = Path(sys.executable)
    if executable.name.casefold() == 'pythonw.exe':
        maybe = executable.with_name('python.exe')
        if maybe.is_file():
            return maybe
    return executable


def packaged_playwright_driver():
    """Resolve the Node executable/CLI *bundled with this exact app version*."""
    from playwright._impl._driver import compute_driver_executable
    node, cli = [Path(x) for x in compute_driver_executable()]
    if not node.is_file() or not cli.is_file():
        raise FileNotFoundError('Bundled Playwright installer is missing. Rebuild the EXE using build.bat.')
    return node, cli


def chromium_is_ready():
    """Check the matching headful Chromium binary without downloading anything."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path).is_file()
