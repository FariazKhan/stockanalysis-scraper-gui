"""Platform-independent tests for the generated Windows installer script.

These assert commands/marker logic; execution on Windows and GUI appearance
still require validation on the target PC.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_tools


class SetupScriptTests(unittest.TestCase):
    def test_source_installs_packages_then_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = setup_tools.create_windows_setup_script(
                root / 'launch.cmd', root / 'result.flag',
                frozen=False,
                interpreter=r'C:\Users\Test User\Python\python.exe',
                requirements=r'C:\Users\Test User\app\requirements.txt')
            contents = script.read_text(encoding='utf-8')
            self.assertIn('"C:\\Users\\Test User\\Python\\python.exe" -m pip install -r', contents)
            self.assertIn('"C:\\Users\\Test User\\Python\\python.exe" -m playwright install chromium', contents)
            self.assertLess(contents.index('pip install -r'), contents.index('playwright install chromium'))
            self.assertIn('if errorlevel 1 goto failed', contents)
            self.assertIn('echo OK', contents)
            self.assertIn('echo FAILED', contents)
            self.assertIn('pause >nul', contents)

    def test_frozen_uses_bundled_cli_not_external_python(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = setup_tools.create_windows_setup_script(
                root / 'launch.cmd', root / 'result.flag',
                frozen=True, node=r'C:\App\_MEI123\playwright\driver\node.exe',
                playwright_cli=r'C:\App\_MEI123\playwright\driver\package\cli.js')
            contents = script.read_text(encoding='utf-8')
            self.assertIn('node.exe" "C:\\App\\_MEI123\\playwright\\driver\\package\\cli.js" install chromium', contents)
            self.assertNotIn('pip install', contents)
            self.assertNotIn(' -m playwright', contents)

    def test_quotes_special_windows_paths_and_rejects_newlines(self):
        self.assertEqual(setup_tools.windows_batch_quote(r'C:\My Files\file%name.exe'),
                         '"C:\\My Files\\file%%name.exe"')
        with self.assertRaises(ValueError):
            setup_tools.windows_batch_quote('evil\r\necho bad')

    def test_missing_args_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                setup_tools.create_windows_setup_script(root/'x.cmd', root/'r', frozen=True)
            with self.assertRaises(ValueError):
                setup_tools.create_windows_setup_script(root/'x.cmd', root/'r', frozen=False)


if __name__ == '__main__':
    unittest.main()
