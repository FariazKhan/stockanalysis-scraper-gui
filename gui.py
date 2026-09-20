import os
import sys
import json
import threading
import subprocess
import multiprocessing

if __name__ == '__main__':
    multiprocessing.freeze_support()
    
    # PyInstaller Fork-Bomb Fix:
    # When frozen, sys.executable points to this .exe.
    # When we try to run `sys.executable -m playwright`, it launches our .exe again!
    # We intercept this argument and route it to the Playwright installer natively.
    if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "playwright":
        sys.argv = ["playwright"] + sys.argv[3:]
        from playwright.__main__ import main
        sys.exit(main())

import customtkinter as ctk
import tkinter.messagebox as messagebox
from playwright.sync_api import sync_playwright

# Ensure playwright browsers are installed
try:
    if os.name == 'nt':
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
except Exception:
    pass # Ignore errors and let it try to run

# Set theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("DSE Share Price Scraper")
        self.geometry("600x550")
        
        # Title
        self.title_label = ctk.CTkLabel(self, text="DSE Data Extractor", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=20)
        
        # Login Section
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=10, padx=20, fill="x")
        
        self.login_label = ctk.CTkLabel(self.login_frame, text="Step 1: Authenticate with StockAnalysis", font=ctk.CTkFont(weight="bold"))
        self.login_label.pack(pady=10)
        
        self.login_btn = ctk.CTkButton(self.login_frame, text="Log In & Get Cookies", command=self.do_login)
        self.login_btn.pack(pady=10)
        
        # Settings Section
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=10, padx=20, fill="x")
        
        self.settings_label = ctk.CTkLabel(self.settings_frame, text="Step 2: Configure Scrape", font=ctk.CTkFont(weight="bold"))
        self.settings_label.pack(pady=10)
        
        self.tickers_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Enter Tickers (e.g. BRACBANK, GP, BATBC)", width=400)
        self.tickers_entry.pack(pady=10)
        
        self.date_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.date_frame.pack(pady=10)
        
        self.start_date = ctk.CTkEntry(self.date_frame, placeholder_text="Start: DD-MM-YYYY (e.g. 01-08-2021)")
        self.start_date.pack(side="left", padx=10)
        self.start_date.insert(0, "01-01-2021")
        
        self.end_date = ctk.CTkEntry(self.date_frame, placeholder_text="End: DD-MM-YYYY (e.g. 01-08-2026)")
        self.end_date.pack(side="left", padx=10)
        self.end_date.insert(0, "31-12-2026")
        
        # Run Section
        self.run_btn = ctk.CTkButton(self, text="Start Extraction", command=self.start_pipeline, fg_color="green", hover_color="darkgreen")
        self.run_btn.pack(pady=20)
        
        self.status_label = ctk.CTkLabel(self, text="Status: Ready", text_color="gray")
        self.status_label.pack(pady=5)
        
    def do_login(self):
        self.status_label.configure(text="Status: Opening browser for login...")
        threading.Thread(target=self._login_thread).start()
        
    def _login_thread(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://stockanalysis.com/login")
                
                # Show popup blocking the script until user confirms
                messagebox.showinfo(
                    "Login Required", 
                    "1. A browser window has opened.\n2. Please log into StockAnalysis.\n3. ONCE LOGGED IN, return to this prompt and click OK to capture your session."
                )
                
                # After OK is clicked, grab cookies
                cookies = context.cookies()
                with open("cookies.json", "w") as f:
                    json.dump(cookies, f)
                    
                browser.close()
                
                self.status_label.configure(text="Status: Cookies captured successfully!", text_color="green")
                messagebox.showinfo("Success", "Session cookies successfully saved!")
        except Exception as e:
            self.status_label.configure(text=f"Status: Login failed", text_color="red")
            messagebox.showerror("Error", f"Login process failed: {str(e)}")

    def start_pipeline(self):
        tickers = self.tickers_entry.get().strip()
        if not tickers:
            messagebox.showwarning("Input Error", "Please enter at least one ticker.")
            return
            
        if not os.path.exists("cookies.json"):
            messagebox.showwarning("Auth Error", "Please log in first to generate cookies.json")
            return
            
        self.run_btn.configure(state="disabled")
        self.status_label.configure(text="Status: Running pipeline (this may take a few minutes)...", text_color="orange")
        threading.Thread(target=self._pipeline_thread, args=(tickers,)).start()

    def _pipeline_thread(self, tickers):
        try:
            # 1. Save tickers to tickers.txt for the builder to use
            ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
            with open("tickers.txt", "w") as f:
                f.write("\n".join(ticker_list))
                
            # 2. Run Portfolio Builder
            self.status_label.configure(text="Status: Crawling and extracting data...")
            import portfolio_builder
            portfolio_builder.build_portfolio()
            
            # 3. Run Portfolio Analyzer
            self.status_label.configure(text="Status: Analyzing portfolio metrics...")
            import portfolio_analyzer
            if hasattr(portfolio_analyzer, 'main'):
                portfolio_analyzer.main()
            else:
                subprocess.run("python portfolio_analyzer.py", shell=True, check=True) # Fallback
            
            # 4. Run Excel Exporter with Dates
            self.status_label.configure(text="Status: Generating final Excel file...")
            start = self.start_date.get().strip()
            end = self.end_date.get().strip()
            import excel_exporter
            import pandas as pd
            start_dt = pd.to_datetime(start, format="%d-%m-%Y") if start else None
            end_dt = pd.to_datetime(end, format="%d-%m-%Y") if end else None
            excel_exporter.create_excel(start_dt, end_dt)
            
            self.status_label.configure(text="Status: Complete! Check output/portfolio.xlsx", text_color="green")
            messagebox.showinfo("Success", "Portfolio Excel file generated successfully in the 'output' folder!")
            
        except subprocess.CalledProcessError as e:
            self.status_label.configure(text="Status: Pipeline failed!", text_color="red")
            messagebox.showerror("Error", f"Pipeline failed during execution.\nEnsure all scripts are present.")
        finally:
            self.run_btn.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
