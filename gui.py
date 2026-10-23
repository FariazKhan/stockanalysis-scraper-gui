"""DSE StockAnalysis desktop GUI; all widgets touched only by Tk's event loop."""
import multiprocessing
import os
import queue
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox

# Set persistent PLAYWRIGHT_BROWSERS_PATH for a packaged build before starting
# the Playwright driver; never depend on PyInstaller's temporary _MEI cache.
from paths import OUTPUT_DIR, PACKAGE_DIR, ROOT, session_path
import setup_tools

import customtkinter as ctk
from playwright.sync_api import sync_playwright
from pipeline import run_pipeline, parse_tickers

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')


class App(ctk.CTk):
    MAX_LOG_LINES = 2000

    def __init__(self):
        super().__init__()
        # Match the title-bar/taskbar icon to the PyInstaller executable icon.
        # PACKAGE_DIR resolves correctly for source runs and PyInstaller --onefile.
        if os.name == 'nt':
            icon_file = PACKAGE_DIR / 'assets' / 'DSE_Scraper.ico'
            if icon_file.is_file():
                try:
                    self.iconbitmap(str(icon_file))
                except Exception:
                    pass  # Never prevent the app from starting over an optional icon.
        self.title('DSE Stock Scraper — Seven-sheet Excel')
        # Fit ordinary laptop screens while leaving the log pane resizable.
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{min(930, max(680, screen_w - 50))}x{min(800, max(600, screen_h - 95))}')
        self.minsize(680, 600)
        self.queue = queue.Queue()
        self.running = False
        self.setting_up = False
        self.setup_process = None
        self.setup_marker = ROOT / '.setup_result.txt'
        self.log_count = 0

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(14, 4))
        ctk.CTkLabel(header, text='DSE Stock Data Extractor',
                     font=ctk.CTkFont(size=23, weight='bold')).pack(anchor='w')
        ctk.CTkLabel(header,
                     text='StockAnalysis financials, prices and dividends • Seven industry-grouped Excel sheets',
                     text_color='gray').pack(anchor='w', pady=(1, 0))

        setup = ctk.CTkFrame(self)
        setup.pack(fill='x', padx=24, pady=5)
        setup_row = ctk.CTkFrame(setup, fg_color='transparent')
        setup_row.pack(fill='x', padx=14, pady=(9, 4))
        ctk.CTkLabel(setup_row, text='1. First-time setup',
                     font=ctk.CTkFont(weight='bold')).pack(side='left')
        self.setup_button = ctk.CTkButton(setup_row, text='Install / Repair Requirements',
                                          width=224, command=self.install_requirements)
        self.setup_button.pack(side='right')
        ctk.CTkLabel(setup,
                     text='One click opens a setup terminal. Installs Python packages (source app) and the matching Chromium browser.',
                     text_color='gray', wraplength=840, justify='left').pack(anchor='w', padx=14, pady=(0, 9))

        login_frame = ctk.CTkFrame(self)
        login_frame.pack(fill='x', padx=24, pady=5)
        login_row = ctk.CTkFrame(login_frame, fg_color='transparent')
        login_row.pack(fill='x', padx=14, pady=9)
        ctk.CTkLabel(login_row, text='2. Authentication (optional for public data)',
                     font=ctk.CTkFont(weight='bold')).pack(side='left')
        self.login_button = ctk.CTkButton(login_row, text='Log in to StockAnalysis',
                                           width=210, command=self.login)
        self.login_button.pack(side='right')

        form = ctk.CTkFrame(self)
        form.pack(fill='x', padx=24, pady=5)
        ctk.CTkLabel(form, text='3. Extraction settings',
                     font=ctk.CTkFont(weight='bold')).pack(anchor='w', padx=14, pady=(8, 5))
        self.tickers = ctk.CTkEntry(form,
                     placeholder_text='Comma-separated DSE tickers, e.g. BRACBANK, CITYBANK, BXPHARMA')
        self.tickers.pack(fill='x', padx=14, pady=(0, 9))
        date_frame = ctk.CTkFrame(form, fg_color='transparent')
        date_frame.pack(fill='x', padx=14)
        ctk.CTkLabel(date_frame, text='Start year').pack(side='left')
        self.start_year = ctk.CTkEntry(date_frame, width=90)
        self.start_year.pack(side='left', padx=(9, 24))
        self.start_year.insert(0, str(date.today().year - 5))
        ctk.CTkLabel(date_frame, text='End year').pack(side='left')
        self.end_year = ctk.CTkEntry(date_frame, width=90)
        self.end_year.pack(side='left', padx=9)
        self.end_year.insert(0, str(date.today().year))
        self.refresh_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(form, text='Refresh downloaded data (ignore 12-hour cache)',
                        variable=self.refresh_var).pack(anchor='w', padx=14, pady=(10, 11))

        dest = ctk.CTkFrame(self)
        dest.pack(fill='x', padx=24, pady=5)
        ctk.CTkLabel(dest, text='4. Output workbook',
                     font=ctk.CTkFont(weight='bold')).pack(anchor='w', padx=14, pady=(9, 4))
        row = ctk.CTkFrame(dest, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=(0, 10))
        self.output_path = ctk.CTkEntry(row)
        self.output_path.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.output_path.insert(0, str(OUTPUT_DIR / 'portfolio.xlsx'))
        self.browse = ctk.CTkButton(row, text='Browse…', width=95,
                                    command=self.choose_output)
        self.browse.pack(side='right')

        self.run_button = ctk.CTkButton(
            self, text='Start extraction and generate workbook',
            fg_color='#257746', hover_color='#1C6039', height=39, command=self.start)
        self.run_button.pack(fill='x', padx=24, pady=(10, 5))
        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill='x', padx=25, pady=(5, 4))
        self.progress.set(0)
        self.status = ctk.CTkLabel(self, text='Ready', anchor='w', height=22)
        self.status.pack(fill='x', padx=25, pady=(0, 3))

        log_header = ctk.CTkFrame(self, fg_color='transparent')
        log_header.pack(fill='x', padx=24, pady=(4, 4))
        ctk.CTkLabel(log_header, text='5. Activity log (scroll up or down)',
                     font=ctk.CTkFont(weight='bold')).pack(side='left')
        ctk.CTkButton(log_header, text='Clear', width=65,
                      command=self.clear_log).pack(side='right', padx=(5, 0))
        ctk.CTkButton(log_header, text='Copy all', width=85,
                      command=self.copy_log).pack(side='right')

        self.log_box = ctk.CTkTextbox(self, wrap='word', fg_color='#0c1220',
                                     text_color='#e2e8f0', font=('Consolas', 12),
                                     corner_radius=7, border_width=1, border_color='#32445e')
        self.log_box.pack(fill='both', expand=True, padx=24, pady=(0, 16))
        self.log_box.configure(state='disabled')
        self._log('Ready. Enter tickers and a year range, or click Install / Repair Requirements.', 'INFO')
        self.after(100, self.poll_events)

    def _log(self, message, level='INFO'):
        """Append a timestamped line; don't steal scroll position while reviewing older entries."""
        text = str(message).strip()
        if not text:
            return
        text = ' '.join(text.splitlines())
        stamp = datetime.now().strftime('%H:%M:%S')
        was_bottom = self.log_box.yview()[1] >= 0.97
        self.log_box.configure(state='normal')
        self.log_box.insert('end', f'[{stamp}] {level:<7} {text}\n')
        self.log_count += 1
        if self.log_count > self.MAX_LOG_LINES:
            self.log_box.delete('1.0', '201.0')
            self.log_count -= 200
        self.log_box.configure(state='disabled')
        if was_bottom:
            self.log_box.see('end')

    def clear_log(self):
        self.log_box.configure(state='normal')
        self.log_box.delete('1.0', 'end')
        self.log_box.configure(state='disabled')
        self.log_count = 0
        self._log('Log cleared.', 'INFO')

    def copy_log(self):
        content = self.log_box.get('1.0', 'end-1c')
        self.clipboard_clear()
        self.clipboard_append(content)
        self._log('Activity log copied to clipboard.', 'INFO')

    def _update_buttons(self):
        busy = self.running or self.setting_up
        self.run_button.configure(state='disabled' if busy else 'normal')
        self.login_button.configure(state='disabled' if busy else 'normal')
        self.setup_button.configure(state='disabled' if busy else 'normal')

    def choose_output(self):
        chosen = filedialog.asksaveasfilename(
            title='Save Excel workbook', defaultextension='.xlsx',
            filetypes=[('Excel workbook', '*.xlsx')], initialfile='portfolio.xlsx')
        if chosen:
            self.output_path.delete(0, 'end')
            self.output_path.insert(0, chosen)

    def install_requirements(self):
        """Windows: open real CMD and run version-matching installer, no typing."""
        if self.running or self.setting_up:
            return
        if os.name != 'nt':
            messagebox.showinfo('First-time setup',
                'The one-click terminal installer currently supports Windows.\n\n'
                'On macOS/Linux, open a terminal in this project folder and run:\n'
                'python3 -m pip install -r requirements.txt\n'
                'python3 -m playwright install chromium')
            return
        try:
            self.setup_marker.parent.mkdir(parents=True, exist_ok=True)
            self.setup_marker.unlink(missing_ok=True)
            if getattr(sys, 'frozen', False):
                node, cli = setup_tools.packaged_playwright_driver()
                script = setup_tools.create_windows_setup_script(
                    ROOT / 'setup_browser.cmd', self.setup_marker,
                    frozen=True, node=node, playwright_cli=cli)
                self._log('EXE mode: Python packages are bundled; downloading the matching Playwright Chromium.', 'SETUP')
            else:
                req = Path(__file__).resolve().parent / 'requirements.txt'
                if not req.is_file():
                    raise FileNotFoundError(f'Missing requirements file: {req}')
                script = setup_tools.create_windows_setup_script(
                    ROOT / 'setup_browser.cmd', self.setup_marker,
                    frozen=False, interpreter=setup_tools.console_python(), requirements=req)
                self._log('Source mode: installing Python requirements and matching Playwright Chromium.', 'SETUP')
            self.setup_process = setup_tools.start_windows_setup(script)
            self.setting_up = True
            self._update_buttons()
            self.status.configure(text='Installing requirements in a separate Windows terminal…')
            self._log('Setup terminal opened. Keep it open until setup finishes; no commands to type.', 'SETUP')
            self.after(500, self.poll_setup)
        except Exception as exc:
            self._log(f'Could not open the setup terminal: {exc}', 'ERROR')
            messagebox.showerror('Setup could not start', f'{exc}\n\nPlease ensure the app was extracted to a writable folder.')

    def poll_setup(self):
        if not self.setting_up:
            return
        try:
            result = self.setup_marker.read_text(encoding='utf-8').strip() if self.setup_marker.is_file() else ''
            if result in ('OK', 'FAILED'):
                self.setting_up = False
                self._update_buttons()
                if result == 'OK':
                    self.status.configure(text='Setup complete. You can log in or extract data.')
                    self._log('Installation completed successfully. Chromium is configured for this app.', 'SUCCESS')
                    if not getattr(sys, 'frozen', False):
                        self._log('Restart the app if Python packages were updated.', 'INFO')
                    messagebox.showinfo('Setup complete',
                        'Setup finished successfully. You can now use Login or Start extraction.\n\n'
                        'If running from Python source, restart the application if packages were upgraded.')
                else:
                    self.status.configure(text='Setup failed; check the terminal window for details.')
                    self._log('Setup failed. Review the error in the terminal window and try again.', 'ERROR')
                    messagebox.showerror('Setup failed',
                        'Installation failed. Please read the error shown in the setup terminal.\n\n'
                        'Common causes: network connection, blocked download or insufficient disk space.')
                return
            if self.setup_process is not None and self.setup_process.poll() is not None:
                self.setting_up = False
                self._update_buttons()
                self.status.configure(text='Setup was interrupted before finishing.')
                self._log('Setup terminal closed before installation finished.', 'WARNING')
                messagebox.showwarning('Setup interrupted',
                    'The setup terminal closed without reporting success. Try the setup button again.')
                return
        except OSError as exc:
            self._log(f'Checking setup status: {exc}', 'WARNING')
        self.after(500, self.poll_setup)

    def ensure_browser(self):
        try:
            if setup_tools.chromium_is_ready():
                return True
        except Exception as exc:
            self._log(f'Chromium check failed: {exc}', 'WARNING')
        self._log('Playwright Chromium is not installed. Please run First-time setup.', 'WARNING')
        if messagebox.askyesno('Browser setup needed',
               'Playwright Chromium is missing or cannot be found.\n\n'
               'Would you like to open the automatic setup terminal now?'):
            self.install_requirements()
        return False

    def login(self):
        if self.running or self.setting_up or not self.ensure_browser():
            return
        self.running = True
        self._update_buttons()
        self.queue.put(('status', 'Opening authentication browser…'))
        proceed = threading.Event()

        def job():
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto('https://stockanalysis.com/login', wait_until='domcontentloaded', timeout=40000)
                    self.queue.put(('login_prompt', proceed))
                    if not proceed.wait(600):
                        raise TimeoutError('Login confirmation timed out')
                    state = session_path()
                    context.storage_state(path=str(state))
                    try:
                        state.chmod(0o600)
                    except OSError:
                        pass
                    browser.close()
                self.queue.put(('info', 'Session saved in your private user configuration directory.'))
                self.queue.put(('status', 'Authentication session saved'))
            except Exception as exc:
                self.queue.put(('error', f'Login failed: {exc}'))
            finally:
                self.queue.put(('login_finished', None))
        threading.Thread(target=job, daemon=True).start()

    def start(self):
        if self.running or self.setting_up:
            return
        try:
            tickers = parse_tickers(self.tickers.get())
            start = int(self.start_year.get().strip())
            end = int(self.end_year.get().strip())
            if not 1990 <= start <= end <= 2100:
                raise ValueError('Choose years between 1990 and 2100, start <= end')
            destination = Path(self.output_path.get().strip())
            if not destination.name or destination.suffix.lower() != '.xlsx':
                raise ValueError('Choose an output filename ending in .xlsx')
        except (ValueError, OSError) as exc:
            messagebox.showwarning('Check your inputs', str(exc))
            return
        if not self.ensure_browser():
            return
        self.running = True
        self._update_buttons()
        self.progress.set(0)
        self._log(f'Started: {len(tickers)} ticker(s), {start}–{end}; output: {destination}', 'START')
        refresh = self.refresh_var.get()  # Tk variables read ONLY on main thread

        def run():
            try:
                counter = 0
                def progress(text):
                    nonlocal counter
                    counter += 1
                    self.queue.put(('status', text))
                    self.queue.put(('progress', min(0.90, counter / (len(tickers) + 3))))
                output, issues = run_pipeline(','.join(tickers), start, end,
                                              destination, refresh=refresh, progress=progress)
                for issue in issues:
                    self.queue.put(('warning', issue))
                self.queue.put(('progress', 1.0))
                self.queue.put(('complete', (str(output), issues)))
            except Exception as exc:
                self.queue.put(('error', f'Extraction failed: {exc}'))
            finally:
                self.queue.put(('finished', None))
        threading.Thread(target=run, daemon=True).start()

    def poll_events(self):
        # Limit work per iteration to keep the UI smooth on large jobs.
        for _ in range(120):
            try:
                kind, data = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == 'status':
                self.status.configure(text=data)
                self._log(data)
            elif kind == 'warning':
                self._log(data, 'WARNING')
            elif kind == 'progress':
                self.progress.set(data)
            elif kind == 'login_prompt':
                self._log('Browser open. Log in there, then click OK in the confirmation dialog.', 'AUTH')
                messagebox.showinfo('Log in',
                    'Finish logging in inside the browser, then click OK here to save the session.\n'
                    'Do not close the browser before clicking OK.')
                data.set()
            elif kind == 'info':
                self._log(data, 'SUCCESS')
                messagebox.showinfo('Session', data)
            elif kind == 'error':
                self.status.configure(text=data)
                self._log(data, 'ERROR')
                messagebox.showerror('DSE Stock Scraper', data)
            elif kind == 'complete':
                output, issues = data
                self.status.configure(text=f'Complete: {output}')
                self._log(f'Workbook saved: {output}', 'SUCCESS')
                summary = f'Workbook saved:\n{output}'
                if issues:
                    self._log(f'{len(issues)} warning(s) reported; details are in the *_warnings.txt file.', 'WARNING')
                    summary += f'\n\n{len(issues)} data-source warnings. See the *_warnings.txt file beside the workbook.'
                else:
                    summary += '\n\nBlank cells may still mean data was not available from a source.'
                messagebox.showinfo('Export finished', summary)
            elif kind in ('finished', 'login_finished'):
                self.running = False
                self._update_buttons()
        self.after(100, self.poll_events)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    App().mainloop()
