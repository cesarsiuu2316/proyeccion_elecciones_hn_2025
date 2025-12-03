"""
Scraper y Analizador de Proyecciones Electorales
Elecciones Generales Honduras 2025

Este script obtiene resultados electorales del sitio web del CNE,
calcula proyecciones basadas en las "Actas" procesadas, y muestra los resultados.

USO:
1. Ejecutar el script - se abrirá el navegador automáticamente
2. Recargar la página hasta que muestre los datos electorales
3. Presionar ENTER en la terminal para iniciar el scraping
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeout


# Configuration
BASE_URL = "https://resultadosgenerales2025.cne.hn/results-presentation"
CACHE_FILE = "last_results.json"
CHECK_INTERVAL = 120  # 2 minutes in seconds
PAGE_TIMEOUT = 60000  # 60 seconds in milliseconds
DEBUG_PORT = 9222  # Port for connecting to browser

# Detect OS and set browser paths
IS_WINDOWS = os.name == 'nt'
IS_MAC = os.sys.platform == 'darwin'

if IS_WINDOWS:
    # Edge paths for Windows
    BROWSER_PATHS = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    BROWSER_NAME = "Edge"
elif IS_MAC:
    # Chrome paths for macOS
    BROWSER_PATHS = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ]
    BROWSER_NAME = "Chrome"
else:
    # Chrome paths for Linux
    BROWSER_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    BROWSER_NAME = "Chrome"

# Temporary profile directory (won't affect your normal browser)
BROWSER_PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_scraper_profile")

# Honduras departments (as they appear in the dropdown - uppercase, no accents)
HONDURAS_DEPARTMENTS = [
    "ATLANTIDA", "COLON", "COMAYAGUA", "COPAN", "CORTES",
    "CHOLUTECA", "EL PARAISO", "FRANCISCO MORAZAN", "GRACIAS A DIOS",
    "INTIBUCA", "ISLAS DE LA BAHIA", "LA PAZ", "LEMPIRA", "OCOTEPEQUE",
    "OLANCHO", "SANTA BARBARA", "VALLE", "YORO", "VOTO EN EL EXTERIOR"
]


def clear_console():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def connect_to_existing_browser():
    """
    Connect to an existing browser with remote debugging enabled.
    Returns the playwright instance, browser, and page if successful.
    """
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
        
        # Get existing pages
        contexts = browser.contexts
        if contexts:
            pages = contexts[0].pages
            # Find the election page or use the first page
            for page in pages:
                if 'resultadosgenerales2025' in page.url or 'cne.hn' in page.url:
                    print(f"  ✅ Connected to existing page: {page.url[:60]}...")
                    return playwright, browser, page
            
            # Use first page if no election page found
            if pages:
                print(f"  ✅ Connected to browser, using first page")
                return playwright, browser, pages[0]
        
        # Create new page if none exists
        page = browser.contexts[0].new_page() if contexts else browser.new_context().new_page()
        return playwright, browser, page
        
    except Exception as e:
        print(f"  ⚠️  Could not connect to existing browser: {e}")
        return None, None, None


def launch_browser_with_debugging() -> bool:
    """
    Launch browser with remote debugging enabled using a separate profile.
    Uses Edge on Windows, Chrome on Mac/Linux.
    This won't affect your normal browser sessions.
    Returns True if successful.
    """
    import subprocess
    
    # Find browser executable
    browser_path = None
    for path in BROWSER_PATHS:
        if os.path.exists(path):
            browser_path = path
            break
    
    if not browser_path:
        print(f"  ⚠️  {BROWSER_NAME} not found!")
        if IS_MAC:
            print("  Please install Google Chrome from https://www.google.com/chrome/")
        return False
    
    # Create profile directory if it doesn't exist
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
    
    # Launch browser with debugging and separate profile
    cmd = [
        browser_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={BROWSER_PROFILE_DIR}",
        "--no-first-run",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--no-default-browser-check",
        "--disable-background-networking",
        BASE_URL
    ]
    
    print(f"  Launching {BROWSER_NAME} with separate profile...")
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)  # Wait for browser to start
        return True
    except Exception as e:
        print(f"  ⚠️  Failed to launch Edge: {e}")
        return False


def try_direct_api() -> Optional[dict]:
    """
    Try to access the API directly using requests library.
    Sometimes this bypasses WAF that blocks browsers.
    """
    # Common API endpoint patterns
    api_endpoints = [
        "https://resultadosgenerales2025.cne.hn/api/results",
        "https://resultadosgenerales2025.cne.hn/api/actas",
        "https://resultadosgenerales2025.cne.hn/api/presidential",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'es-HN,es;q=0.9,en;q=0.8',
        'Referer': BASE_URL,
        'Origin': 'https://resultadosgenerales2025.cne.hn',
    }
    
    for endpoint in api_endpoints:
        try:
            response = requests.get(endpoint, headers=headers, timeout=15)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data:
                        print(f"  ✅ Found working API: {endpoint}")
                        return data
                except:
                    pass
        except Exception:
            continue
    
    return None


def create_stealth_context(browser: Browser) -> BrowserContext:
    """
    Create a browser context with anti-detection measures.
    This helps bypass WAF/bot detection systems.
    """
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        locale='es-HN',
        timezone_id='America/Tegucigalpa',
        geolocation={'latitude': 14.0818, 'longitude': -87.2068},
        permissions=['geolocation'],
        java_script_enabled=True,
        bypass_csp=True,
        extra_http_headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'es-HN,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
    )
    
    # Add stealth scripts to evade detection
    context.add_init_script("""
        // Override webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['es-HN', 'es', 'en-US', 'en']
        });
        
        // Override platform
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });
        
        // Override hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });
        
        // Override device memory
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
        
        // Mock chrome object
        window.chrome = {
            runtime: {}
        };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)
    
    return context


def save_cache(data: dict) -> None:
    """Save results to cache file and signal dashboard to reload."""
    data['cached_at'] = datetime.now().isoformat()
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Signal dashboard to reload
    with open('.data_updated', 'w') as f:
        f.write(datetime.now().isoformat())


def load_cache() -> Optional[dict]:
    """Load results from cache file if exists."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def calculate_projection(current_votes: float, actas_percentage: float) -> float:
    """
    Calculate projected votes based on current votes and actas percentage.
    
    Formula: Projected Votes = (Current Votes * 100) / Actas Percentage
    """
    if actas_percentage <= 0:
        return current_votes
    return (current_votes * 100) / actas_percentage


class ElectionScraper:
    """Scraper for Honduras election results."""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.api_data: Optional[dict] = None
        self.api_url: Optional[str] = None
        self.use_api: bool = False
        self.cookies: Optional[List[dict]] = None
        
    def create_browser(self, playwright, channel: str = None):
        """Create browser with anti-detection settings."""
        # Try different browser channels
        if channel == 'msedge':
            try:
                return playwright.chromium.launch(
                    channel='msedge',
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled']
                )
            except Exception:
                pass
        
        if channel == 'firefox':
            try:
                return playwright.firefox.launch(headless=False)
            except Exception:
                pass
        
        # Default to Chromium
        return playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-infobars',
                '--disable-extensions',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--window-size=1920,1080',
            ]
        )
        
    def close_browser(self) -> None:
        """Close the browser instance."""
        if self.browser:
            self.browser.close()
    
    def manual_browser_session(self) -> Optional[dict]:
        """
        Open a browser for manual intervention.
        User can solve CAPTCHA/verification, then we continue scraping.
        """
        print("\n" + "="*60)
        print("MANUAL INTERVENTION REQUIRED")
        print("="*60)
        print("The website is using bot protection.")
        print("A browser window will open. Please:")
        print("  1. Wait for the page to load")
        print("  2. Solve any CAPTCHA if presented")
        print("  3. Once you see the election results, press ENTER here")
        print("="*60)
        
        with sync_playwright() as p:
            browser = self.create_browser(p, 'msedge')
            context = create_stealth_context(browser)
            page = context.new_page()
            
            # Capture API responses
            captured = []
            def handle_response(response):
                try:
                    if 'json' in response.headers.get('content-type', ''):
                        if 'nexusguard' not in response.url:
                            try:
                                captured.append({
                                    'url': response.url,
                                    'data': response.json()
                                })
                            except:
                                pass
                except:
                    pass
            
            page.on('response', handle_response)
            
            print("\nOpening browser...")
            page.goto(BASE_URL, wait_until='domcontentloaded')
            
            input("\n>>> Press ENTER when the election results are visible... ")
            
            # Save cookies for future use
            self.cookies = context.cookies()
            
            # Give it a moment
            time.sleep(2)
            
            # Check for API data
            for resp in captured:
                data = resp['data']
                if isinstance(data, (dict, list)):
                    data_str = str(data).lower()
                    if any(k in data_str for k in ['candidato', 'votos', 'partido', 'actas']):
                        print(f"  ✅ Captured election API: {resp['url'][:60]}...")
                        self.api_url = resp['url']
                        context.close()
                        browser.close()
                        return self.parse_api_response(data)
            
            # Try UI extraction
            print("  Extracting data from UI...")
            results = {}
            
            try:
                actas_pct = self.extract_actas_percentage(page)
                candidates = self.extract_candidates(page)
                
                if candidates:
                    results['Nacional'] = {
                        'actas_percentage': actas_pct,
                        'candidates': candidates
                    }
                    print(f"  ✅ Extracted {len(candidates)} candidates, {actas_pct}% actas")
            except Exception as e:
                print(f"  ⚠️  Extraction error: {e}")
            
            context.close()
            browser.close()
            return results
    
    def scrape_with_existing_browser(self) -> Dict[str, dict]:
        """
        Scrape all departments using an existing Chrome browser session.
        This bypasses bot protection by using your authenticated browser.
        """
        print("\nConnecting to your existing Chrome browser...")
        playwright, browser, page = connect_to_existing_browser()
        
        if not page:
            return {}
        
        results = {}
        
        try:
            # Make sure we're on the right page
            if 'resultadosgenerales2025' not in page.url:
                print(f"  Navigating to election results page...")
                page.goto(BASE_URL, wait_until='domcontentloaded')
                time.sleep(3)
            
            # Reload to get fresh data
            print("  Reloading page for fresh data...")
            page.reload(wait_until='domcontentloaded')
            time.sleep(3)
            
            # First get national/general data
            print("\n  Extracting Nacional data...")
            actas_pct = self.extract_actas_percentage(page)
            candidates = self.extract_candidates(page)
            
            if candidates:
                results['Nacional'] = {
                    'actas_percentage': actas_pct,
                    'candidates': candidates
                }
                print(f"    ✅ Nacional: {actas_pct}% actas, {len(candidates)} candidates")
            
            # Now try to get department-specific data
            print("\n  Looking for department selector...")
            
            # Try to find and iterate through departments
            dept_results = self.scrape_all_departments(page)
            if dept_results:
                results.update(dept_results)
            
            print(f"\n  Total departments scraped: {len(results)}")
            
        except Exception as e:
            print(f"  ⚠️  Error during scraping: {e}")
        finally:
            # Don't close the browser - user wants to keep it open
            if playwright:
                playwright.stop()
        
        return results
    
    def scrape_all_departments(self, page: Page) -> Dict[str, dict]:
        """
        Iterate through all departments and extract their data.
        Uses the select.form-select dropdown and Consultar button.
        """
        results = {}
        
        print("    Searching for Departamento dropdown...")
        
        # Find the select element with class form-select that contains department options
        dropdown = None
        try:
            # Look for select elements
            selects = page.query_selector_all('select.form-select')
            print(f"    Found {len(selects)} select.form-select elements")
            
            for i, sel in enumerate(selects):
                # Check if this select has department options
                options_text = sel.inner_text().upper()
                if 'TODOS' in options_text and ('ATLANTIDA' in options_text or 'FRANCISCO MORAZAN' in options_text):
                    dropdown = sel
                    print(f"    ✅ Found department dropdown (select #{i})")
                    break
            
            if not dropdown:
                # Try any select that has TODOS option
                selects = page.query_selector_all('select')
                for sel in selects:
                    options_text = sel.inner_text().upper()
                    if 'TODOS' in options_text:
                        dropdown = sel
                        print(f"    ✅ Found dropdown with TODOS option")
                        break
        except Exception as e:
            print(f"    Error finding dropdown: {e}")
        
        if not dropdown:
            print("    ⚠️  Could not find department dropdown")
            return results
        
        # Department codes mapping (from the HTML)
        dept_codes = {
            "ATLANTIDA": "01",
            "CHOLUTECA": "06",
            "COLON": "02",
            "COMAYAGUA": "03",
            "COPAN": "04",
            "CORTES": "05",
            "EL PARAISO": "07",
            "FRANCISCO MORAZAN": "08",
            "GRACIAS A DIOS": "09",
            "INTIBUCA": "10",
            "ISLAS DE LA BAHIA": "11",
            "LA PAZ": "12",
            "LEMPIRA": "13",
            "OCOTEPEQUE": "14",
            "OLANCHO": "15",
            "SANTA BARBARA": "16",
            "VALLE": "17",
            "VOTO EN EL EXTERIOR": "20",
            "YORO": "18",
        }
        
        print(f"    Iterating through {len(HONDURAS_DEPARTMENTS)} departments...")
        
        for dept_name in HONDURAS_DEPARTMENTS:
            # VOTO EN EL EXTERIOR: only 1 try, accept 0 votes
            max_retries = 1 if dept_name == "VOTO EN EL EXTERIOR" else 10
            
            for attempt in range(max_retries):
                try:
                    if attempt == 0:
                        print(f"    Processing: {dept_name}...", end=' ', flush=True)
                    else:
                        print(f"    Retry {attempt}: {dept_name}...", end=' ', flush=True)
                    
                    # Get the value code for this department
                    dept_code = dept_codes.get(dept_name)
                    if not dept_code:
                        print("no code mapping")
                        break
                    
                    # Select the department using value
                    dropdown.select_option(value=dept_code)
                    time.sleep(0.5)
                    
                    # Click the Consultar button
                    consultar_clicked = False
                    try:
                        button_selectors = [
                            'button:has(span.label:text("Consultar"))',
                            'button:has-text("Consultar")',
                            'button.text',
                            'button span.label',
                        ]
                        
                        for selector in button_selectors:
                            try:
                                btn = page.query_selector(selector)
                                if btn:
                                    btn.click()
                                    consultar_clicked = True
                                    break
                            except:
                                continue
                        
                        if not consultar_clicked:
                            page.locator('button', has_text='Consultar').first.click()
                            consultar_clicked = True
                            
                    except Exception as e:
                        print(f"btn error: {e}", end=' ')
                    
                    if not consultar_clicked:
                        print("couldn't click Consultar")
                        continue
                    
                    # Wait for data to load - 8 seconds to handle slow page loads
                    time.sleep(8)
                    
                    # Extract data
                    actas_pct = self.extract_actas_percentage(page)
                    candidates = self.extract_candidates(page)
                    
                    # Validate: need candidates with votes
                    total_votes = sum(c.get('votes', 0) for c in candidates) if candidates else 0
                    
                    # VOTO EN EL EXTERIOR: accept whatever we get (may have 0 votes)
                    if dept_name == "VOTO EN EL EXTERIOR" and candidates and len(candidates) >= 2:
                        results[dept_name] = {
                            'actas_percentage': actas_pct,
                            'candidates': candidates
                        }
                        print(f"✅ {actas_pct}% actas, {total_votes:,} votes (exterior)")
                        break
                    
                    # Regular departments: need votes > 0
                    if candidates and len(candidates) >= 2 and total_votes > 0:
                        results[dept_name] = {
                            'actas_percentage': actas_pct,
                            'candidates': candidates
                        }
                        print(f"✅ {actas_pct}% actas, {total_votes:,} votes ({len(candidates)} candidates)")
                        break  # Success, move to next department
                    else:
                        # Invalid data - retry
                        reason = "0 votes" if total_votes == 0 else "not enough candidates"
                        print(f"⚠️ {reason} - retrying...", flush=True)
                        time.sleep(2)  # Wait before retry
                        
                except Exception as e:
                    print(f"error: {e}")
                    time.sleep(2)
        
        return results
            
    def intercept_api_requests(self, page: Page) -> List[dict]:
        """
        Intercept network requests to find JSON API endpoints.
        Returns a list of captured JSON responses.
        """
        captured_responses = []
        
        def handle_response(response):
            try:
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    url = response.url
                    # Only capture relevant API calls (not error pages)
                    if 'nexusguard' not in url and 'errpage' not in url:
                        try:
                            data = response.json()
                            captured_responses.append({
                                'url': url,
                                'data': data
                            })
                            print(f"  📡 Captured API: {url[:80]}...")
                        except Exception:
                            pass
            except Exception:
                pass
        
        page.on('response', handle_response)
        return captured_responses
    
    def investigate_api(self) -> bool:
        """
        Investigate if the website uses a JSON API.
        Returns True if API is found and can be used.
        """
        print("Investigating data sources...")
        
        # First, try direct API access (fastest method)
        print("\n[1/3] Trying direct API access...")
        api_data = try_direct_api()
        if api_data:
            self.api_data = api_data
            self.use_api = True
            return True
        
        # Try browser with multiple channels
        print("\n[2/3] Trying stealth browser access...")
        
        channels = [None, 'msedge']  # Try default chromium, then edge
        
        for channel in channels:
            channel_name = channel or 'chromium'
            print(f"  Trying {channel_name}...")
            
            try:
                with sync_playwright() as p:
                    browser = self.create_browser(p, channel)
                    context = create_stealth_context(browser)
                    page = context.new_page()
                    page.set_default_timeout(PAGE_TIMEOUT)
                    
                    captured = self.intercept_api_requests(page)
                    
                    page.goto(BASE_URL, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
                    time.sleep(8)
                    
                    # Check if blocked
                    page_content = page.content()
                    if 'nexusguard' in page_content.lower():
                        print(f"    ⚠️  Blocked with {channel_name}")
                        context.close()
                        browser.close()
                        continue
                    
                    print(f"    ✅ Page loaded: {page.title()}")
                    
                    # Check captured responses
                    for response in captured:
                        url = response['url']
                        data = response['data']
                        
                        if isinstance(data, (dict, list)):
                            data_str = str(data).lower()
                            if any(key in data_str for key in ['candidato', 'votos', 'actas', 'partido', 'electoral']):
                                print(f"    ✅ Found election API: {url[:60]}...")
                                self.api_data = data
                                self.api_url = url
                                self.use_api = True
                                context.close()
                                browser.close()
                                return True
                    
                    context.close()
                    browser.close()
                    
            except Exception as e:
                print(f"    Error with {channel_name}: {e}")
                continue
        
        print("\n[3/3] Automatic methods failed. Manual intervention may be needed.")
        print("      The website is using aggressive bot protection.")
        return False
    
    def get_departments(self, page: Page) -> List[str]:
        """Get list of departments from dropdown."""
        departments = []
        
        try:
            # Wait for page to be interactive
            time.sleep(2)
            
            # Try to find the department dropdown - common selectors
            dropdown_selectors = [
                'select[name*="department"]',
                'select[name*="departamento"]',
                'select[id*="department"]',
                'select[id*="departamento"]',
                '#departamento',
                '#department',
                'select.department-select',
                '[data-testid*="department"]',
                'select.form-control',
                'select.form-select',
                'select',  # Fallback to any select
            ]
            
            for selector in dropdown_selectors:
                try:
                    dropdown = page.query_selector(selector)
                    if dropdown:
                        # Get all options
                        options = dropdown.query_selector_all('option')
                        for option in options:
                            value = option.get_attribute('value')
                            text = option.inner_text().strip()
                            if text and text.lower() not in ['seleccione', 'seleccionar', 'todos', 'all', '--', '']:
                                departments.append(text)
                        if departments:
                            print(f"  Found dropdown with {len(departments)} departments")
                            break
                except Exception:
                    continue
            
            # If no select found, look for Angular Material / PrimeNG / custom dropdowns
            if not departments:
                custom_dropdown_selectors = [
                    'mat-select',
                    'p-dropdown',
                    'ng-select',
                    '[class*="p-dropdown"]',
                    '[class*="mat-select"]',
                    '[class*="dropdown"]',
                    '[role="combobox"]',
                    '[aria-haspopup="listbox"]',
                    '.p-dropdown',
                    '.custom-select',
                ]
                
                for selector in custom_dropdown_selectors:
                    try:
                        element = page.query_selector(selector)
                        if element:
                            print(f"  Found custom dropdown: {selector}")
                            element.click()
                            time.sleep(1)
                            
                            # Look for dropdown options
                            option_selectors = [
                                '[role="option"]',
                                '.p-dropdown-item',
                                '.mat-option',
                                '.dropdown-item',
                                'li.p-dropdown-item',
                                'mat-option',
                                'li[role="option"]',
                            ]
                            
                            for opt_selector in option_selectors:
                                options = page.query_selector_all(opt_selector)
                                for option in options:
                                    text = option.inner_text().strip()
                                    if text and text.lower() not in ['seleccione', 'seleccionar', 'todos', 'all', '--', '']:
                                        departments.append(text)
                                
                                if departments:
                                    break
                            
                            if departments:
                                # Close dropdown
                                page.keyboard.press('Escape')
                                time.sleep(0.5)
                                break
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"Error getting departments: {e}")
            
        return departments
    
    def extract_actas_percentage(self, page: Page) -> float:
        """Extract the percentage of processed actas."""
        try:
            # Get all text from the page
            page_text = page.inner_text('body')
            
            # Look for patterns like "50% Actas" or "Actas: 50%" or just percentages near actas
            patterns = [
                r'(\d+(?:[.,]\d+)?)\s*%\s*(?:de\s+)?[Aa]ctas',
                r'[Aa]ctas[:\s]+(\d+(?:[.,]\d+)?)\s*%',
                r'[Pp]rocesad[ao]s?[:\s]+(\d+(?:[.,]\d+)?)\s*%',
                r'[Aa]ctas\s+[Pp]rocesad[ao]s?[:\s]+(\d+(?:[.,]\d+)?)\s*%',
                r'(\d+(?:[.,]\d+)?)\s*%\s*[Pp]rocesad[ao]',
                r'[Aa]vance[:\s]+(\d+(?:[.,]\d+)?)\s*%',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text)
                if match:
                    value = match.group(1).replace(',', '.')
                    return float(value)
            
            # Try specific element selectors
            selectors = [
                '[class*="actas"]',
                '[class*="percentage"]',
                '[class*="progress"]',
                '[class*="avance"]',
                '.progress-value',
                '.percentage',
            ]
            
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        text = element.inner_text()
                        match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', text)
                        if match:
                            value = match.group(1).replace(',', '.')
                            return float(value)
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Error extracting actas percentage: {e}")
            
        return 0.0
    
    def extract_candidates(self, page: Page) -> List[Dict[str, any]]:
        """Extract candidate names and vote counts."""
        candidates = []
        
        try:
            # First try to find data in tables
            tables = page.query_selector_all('table')
            for table in tables:
                rows = table.query_selector_all('tr')
                for row in rows:
                    cells = row.query_selector_all('td')
                    if len(cells) >= 2:
                        name = cells[0].inner_text().strip()
                        # Try to find votes in the last cells
                        for cell in reversed(cells):
                            votes_text = cell.inner_text().strip()
                            votes_text = votes_text.replace(',', '').replace('.', '').replace(' ', '')
                            votes_match = re.search(r'(\d+)', votes_text)
                            if votes_match and name:
                                votes = int(votes_match.group(1))
                                if votes > 0:
                                    candidates.append({'name': name, 'votes': votes})
                                    break
                
                if candidates:
                    break
            
            # Try card-based layouts (common in modern SPAs)
            if not candidates:
                card_selectors = [
                    '[class*="candidate"]',
                    '[class*="card"]',
                    '[class*="result"]',
                    '[class*="partido"]',
                    '[class*="item"]',
                    '.candidate-card',
                    '.result-card',
                    '.p-card',
                    '.mat-card',
                ]
                
                for selector in card_selectors:
                    try:
                        cards = page.query_selector_all(selector)
                        for card in cards:
                            text = card.inner_text()
                            lines = [l.strip() for l in text.split('\n') if l.strip()]
                            
                            if len(lines) >= 1:
                                # First non-numeric line is likely the name
                                name = None
                                votes = None
                                
                                for line in lines:
                                    clean_line = line.replace(',', '').replace('.', '').replace(' ', '')
                                    if re.match(r'^\d+$', clean_line) and int(clean_line) >= 1:
                                        votes = int(clean_line)
                                    elif not name and not re.match(r'^[\d\s.,]+$', line) and len(line) > 2:
                                        name = line
                                
                                if name and votes is not None:
                                    candidates.append({'name': name, 'votes': votes})
                        
                        if candidates:
                            break
                    except Exception:
                        continue
            
            # Try extracting from the raw page text using patterns
            if not candidates:
                page_text = page.inner_text('body')
                # Look for patterns like "Candidate Name: 123,456 votes"
                pattern = r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)\s*[:\-]?\s*(\d{1,3}(?:[,.\s]\d{3})*)\s*(?:votos?)?'
                matches = re.findall(pattern, page_text)
                for name, votes_str in matches:
                    votes = int(votes_str.replace(',', '').replace('.', '').replace(' ', ''))
                    if votes > 100:
                        candidates.append({'name': name.strip(), 'votes': votes})
                        
        except Exception as e:
            print(f"Error extracting candidates: {e}")
            
        return candidates
    
    def select_department(self, page: Page, department: str) -> bool:
        """Select a department from the dropdown."""
        try:
            # Try standard select element
            selects = page.query_selector_all('select')
            for select in selects:
                options = select.query_selector_all('option')
                for option in options:
                    if department.lower() in option.inner_text().lower():
                        select.select_option(label=option.inner_text())
                        time.sleep(1)
                        return True
            
            # Try PrimeNG / Angular Material dropdowns
            custom_selectors = [
                'p-dropdown',
                'mat-select',
                'ng-select',
                '[class*="p-dropdown"]',
                '[class*="dropdown"]',
                '[role="combobox"]',
            ]
            
            for selector in custom_selectors:
                try:
                    dropdowns = page.query_selector_all(selector)
                    for dropdown in dropdowns:
                        dropdown.click()
                        time.sleep(0.5)
                        
                        option_selectors = ['[role="option"]', '.p-dropdown-item', '.mat-option', 'li']
                        for opt_sel in option_selectors:
                            options = page.query_selector_all(opt_sel)
                            for option in options:
                                if department.lower() in option.inner_text().lower():
                                    option.click()
                                    time.sleep(1)
                                    return True
                        
                        page.keyboard.press('Escape')
                        time.sleep(0.3)
                except Exception:
                    continue
                        
        except Exception as e:
            print(f"Error selecting department {department}: {e}")
            
        return False
    
    def click_consultar(self, page: Page) -> bool:
        """Click the 'Consultar' or equivalent button."""
        try:
            button_texts = ['Consultar', 'Buscar', 'Ver', 'Search', 'Submit', 'Filtrar', 'Aplicar']
            
            for text in button_texts:
                try:
                    # Try different button selectors
                    selectors = [
                        f'button:has-text("{text}")',
                        f'input[type="submit"][value*="{text}"]',
                        f'a:has-text("{text}")',
                        f'[class*="btn"]:has-text("{text}")',
                    ]
                    for sel in selectors:
                        try:
                            button = page.query_selector(sel)
                            if button:
                                button.click()
                                time.sleep(2)
                                return True
                        except:
                            continue
                except Exception:
                    continue
            
            # Try any submit/primary button
            fallback_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button.btn-primary',
                'button.p-button',
                '.btn-primary',
            ]
            
            for sel in fallback_selectors:
                try:
                    button = page.query_selector(sel)
                    if button:
                        button.click()
                        time.sleep(2)
                        return True
                except:
                    continue
                
        except Exception as e:
            print(f"Error clicking consultar button: {e}")
            
        return False
    
    def scrape_ui(self) -> Dict[str, List[Dict]]:
        """
        Scrape election data using UI interaction.
        Returns dictionary with department data.
        """
        results = {}
        
        with sync_playwright() as p:
            browser = self.create_browser(p)
            context = create_stealth_context(browser)
            page = context.new_page()
            page.set_default_timeout(PAGE_TIMEOUT)
            
            # Intercept API requests while browsing
            captured = self.intercept_api_requests(page)
            
            try:
                print("Loading page with stealth browser...")
                page.goto(BASE_URL, wait_until='domcontentloaded')
                
                # Wait for dynamic content
                print("Waiting for page content to load...")
                time.sleep(5)
                
                # Check if blocked
                page_content = page.content()
                if 'nexusguard' in page_content.lower():
                    print("⚠️  Access blocked by security system")
                    context.close()
                    browser.close()
                    return results
                
                print(f"Page loaded: {page.title()}")
                
                # First check if we captured any API data
                for response in captured:
                    if 'nexusguard' not in response['url']:
                        data = response['data']
                        parsed = self.parse_api_response(data)
                        if parsed and 'raw_data' not in parsed:
                            print(f"  ✅ Got data from API: {response['url'][:60]}...")
                            context.close()
                            browser.close()
                            return parsed
                
                # Get list of departments
                departments = self.get_departments(page)
                
                if not departments:
                    print("No departments dropdown found, extracting from current page...")
                    actas_pct = self.extract_actas_percentage(page)
                    candidates = self.extract_candidates(page)
                    
                    print(f"  Actas: {actas_pct}%, Candidates: {len(candidates)}")
                    
                    if candidates:
                        results['Nacional'] = {
                            'actas_percentage': actas_pct,
                            'candidates': candidates
                        }
                else:
                    print(f"Found {len(departments)} departments")
                    
                    for dept in departments:
                        print(f"  Processing: {dept}")
                        
                        if self.select_department(page, dept):
                            self.click_consultar(page)
                            time.sleep(1)
                            
                            # Check for new API responses
                            for response in captured:
                                if 'nexusguard' not in response['url']:
                                    data = response['data']
                                    # Check if this contains department-specific data
                                    if dept.lower() in str(data).lower():
                                        parsed = self.parse_api_response(data)
                                        if parsed:
                                            results.update(parsed)
                            
                            # Also try UI extraction
                            actas_pct = self.extract_actas_percentage(page)
                            candidates = self.extract_candidates(page)
                            
                            if candidates:
                                results[dept] = {
                                    'actas_percentage': actas_pct,
                                    'candidates': candidates
                                }
                
                context.close()
                browser.close()
                
            except PlaywrightTimeout:
                print("Page timeout - website may be slow or unavailable")
                try:
                    context.close()
                    browser.close()
                except:
                    pass
            except Exception as e:
                print(f"Scraping error: {e}")
                try:
                    context.close()
                    browser.close()
                except:
                    pass
                
        return results
    
    def scrape_api(self, api_url: str) -> Dict:
        """
        Scrape election data from API endpoint.
        """
        results = {}
        
        with sync_playwright() as p:
            browser = self.create_browser(p)
            context = create_stealth_context(browser)
            page = context.new_page()
            
            try:
                response = page.goto(api_url)
                if response and response.ok:
                    data = response.json()
                    results = self.parse_api_response(data)
            except Exception as e:
                print(f"API scraping error: {e}")
            finally:
                try:
                    context.close()
                    browser.close()
                except:
                    pass
                
        return results
    
    def parse_api_response(self, data) -> Dict:
        """Parse the API response into our format."""
        results = {}
        
        try:
            # Handle both dict and list responses
            if isinstance(data, list):
                # Might be a list of candidates or departments
                for item in data:
                    if isinstance(item, dict):
                        # Check if it's candidate data
                        name = item.get('nombre', item.get('name', item.get('candidato', item.get('partido', ''))))
                        votes = item.get('votos', item.get('votes', item.get('total', 0)))
                        dept = item.get('departamento', item.get('department', 'Nacional'))
                        
                        if name and votes:
                            if dept not in results:
                                results[dept] = {
                                    'actas_percentage': item.get('porcentaje_actas', item.get('actas_percentage', item.get('avance', 100))),
                                    'candidates': []
                                }
                            results[dept]['candidates'].append({
                                'name': name,
                                'votes': int(votes) if isinstance(votes, (int, float, str)) else 0
                            })
                            
            elif isinstance(data, dict):
                # Try common data structures
                
                # Check for nested data structures
                for key in ['data', 'results', 'resultados', 'response']:
                    if key in data:
                        nested = self.parse_api_response(data[key])
                        if nested and 'raw_data' not in nested:
                            return nested
                
                # Check for department-based structure
                if 'departamentos' in data or 'departments' in data:
                    depts = data.get('departamentos', data.get('departments', []))
                    for dept in depts:
                        dept_name = dept.get('nombre', dept.get('name', 'Unknown'))
                        results[dept_name] = {
                            'actas_percentage': dept.get('porcentaje_actas', dept.get('actas_percentage', dept.get('avance', 0))),
                            'candidates': [
                                {'name': c.get('nombre', c.get('name')), 'votes': c.get('votos', c.get('votes', 0))}
                                for c in dept.get('candidatos', dept.get('candidates', []))
                            ]
                        }
                
                # Check for candidatos/candidates at top level
                elif 'candidatos' in data or 'candidates' in data:
                    candidates = data.get('candidatos', data.get('candidates', []))
                    results['Nacional'] = {
                        'actas_percentage': data.get('porcentaje_actas', data.get('actas_percentage', data.get('avance', 100))),
                        'candidates': [
                            {'name': c.get('nombre', c.get('name')), 'votes': c.get('votos', c.get('votes', 0))}
                            for c in candidates
                        ]
                    }
                
                # If nothing matched, store raw data
                elif not results:
                    # Look for any array that might contain candidate data
                    for key, value in data.items():
                        if isinstance(value, list) and len(value) > 0:
                            parsed = self.parse_api_response(value)
                            if parsed and 'raw_data' not in parsed:
                                return parsed
                    
                    # Last resort - store raw for debugging
                    results['raw_data'] = data
                    
        except Exception as e:
            print(f"Error parsing API response: {e}")
            
        return results


def display_department_results(department_data: Dict):
    """Display detailed results per department with current and projected votes."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "=" * 100)
    print(f"RESULTS BY DEPARTMENT                                        Data collected: {current_time}")
    print("=" * 100)
    
    # Get top 3 candidate names from the first actual department with data (not Nacional)
    top_candidates = []
    for dept_name, dept_data in department_data.items():
        if dept_name == 'raw_data' or dept_name == 'Nacional':
            continue
        candidates = dept_data.get('candidates', [])
        if candidates:
            sorted_cands = sorted(candidates, key=lambda x: x.get('votes', 0), reverse=True)
            top_candidates = [c['name'] for c in sorted_cands[:3]]
            break
    
    if not top_candidates:
        print("No candidate data found.")
        return
    
    # Print header - show candidate names
    print(f"\n{'Department':<22} {'Actas%':>6}", end="")
    for cand in top_candidates:
        short_name = cand[:10] if len(cand) > 10 else cand
        print(f"  {short_name:^19}", end="")
    print()
    
    # Sub-header for Current/Projected
    print(f"{'':<22} {'':>6}", end="")
    for _ in top_candidates:
        print(f"  {'Current':>9} {'Proj':>9}", end="")
    print()
    print("-" * 100)
    
    # Sort departments alphabetically (exclude Nacional and raw_data)
    sorted_depts = sorted([d for d in department_data.keys() if d not in ('raw_data', 'Nacional')])
    
    total_votes_by_candidate = {c: 0 for c in top_candidates}
    total_projected_by_candidate = {c: 0 for c in top_candidates}
    
    for dept_name in sorted_depts:
        dept_data = department_data[dept_name]
        actas_pct = dept_data.get('actas_percentage', 0)
        candidates = dept_data.get('candidates', [])
        
        # Create a lookup by name
        cand_votes = {c['name']: c['votes'] for c in candidates}
        
        print(f"{dept_name:<22} {actas_pct:>5.1f}%", end="")
        
        for cand_name in top_candidates:
            votes = cand_votes.get(cand_name, 0)
            total_votes_by_candidate[cand_name] += votes
            
            # Calculate projection for this department
            if actas_pct > 0:
                projected = int(calculate_projection(votes, actas_pct))
            else:
                projected = votes
            total_projected_by_candidate[cand_name] += projected
            
            print(f"  {votes:>9,} {projected:>9,}", end="")
        print()
    
    # Print totals
    print("-" * 100)
    print(f"{'TOTAL':<22} {'':>6}", end="")
    for cand_name in top_candidates:
        current = total_votes_by_candidate[cand_name]
        projected = int(total_projected_by_candidate[cand_name])
        print(f"  {current:>9,} {projected:>9,}", end="")
    print()
    
    # Calculate and show percentages (both current and projected)
    total_current = sum(total_votes_by_candidate.values())
    total_projected = sum(total_projected_by_candidate.values())
    if total_projected > 0:
        print(f"{'PERCENTAGE':<22} {'':>6}", end="")
        for cand_name in top_candidates:
            curr_pct = (total_votes_by_candidate[cand_name] / total_current * 100) if total_current > 0 else 0
            proj_pct = (total_projected_by_candidate[cand_name] / total_projected) * 100
            print(f"  {curr_pct:>8.2f}% {proj_pct:>8.2f}%", end="")
        print()
    
    print("=" * 100)


def calculate_national_projection(department_data: Dict) -> pd.DataFrame:
    """
    Calculate national projection by summing projected votes from all departments.
    Excludes 'Nacional' to avoid double-counting - only uses actual department data.
    """
    candidate_projections = {}
    
    # Keywords that indicate non-candidate entries
    exclude_keywords = ['información', 'general', 'acta', 'total', 'votos', 'nulos', 'blancos', 'abstención']
    
    for dept_name, dept_data in department_data.items():
        # Skip Nacional (general count) and raw_data - only use actual departments
        if dept_name in ('raw_data', 'Nacional'):
            continue
            
        actas_pct = dept_data.get('actas_percentage', 0)
        candidates = dept_data.get('candidates', [])
        
        for candidate in candidates:
            name = candidate['name']
            votes = candidate['votes']
            
            # Skip non-candidate entries
            name_lower = name.lower()
            if any(kw in name_lower for kw in exclude_keywords):
                continue
            
            # Skip entries with very low votes (likely metadata)
            if votes < 100:
                continue
            
            # Calculate projection
            projected = calculate_projection(votes, actas_pct) if actas_pct > 0 else votes
            
            if name not in candidate_projections:
                candidate_projections[name] = {
                    'current_votes': 0,
                    'projected_votes': 0
                }
            
            candidate_projections[name]['current_votes'] += votes
            candidate_projections[name]['projected_votes'] += projected
    
    # Convert to DataFrame
    if candidate_projections:
        df = pd.DataFrame([
            {
                'Candidate': name,
                'Current Votes': data['current_votes'],
                'Projected Votes': int(data['projected_votes']),
            }
            for name, data in candidate_projections.items()
        ])
        
        # Calculate percentages
        total_projected = df['Projected Votes'].sum()
        if total_projected > 0:
            df['Percentage'] = (df['Projected Votes'] / total_projected * 100).round(2)
        else:
            df['Percentage'] = 0.0
        
        # Sort by projected votes descending
        df = df.sort_values('Projected Votes', ascending=False).reset_index(drop=True)
        df.index = df.index + 1  # 1-based ranking
        
        return df
    
    return pd.DataFrame()


def display_results(df: pd.DataFrame, status: str = "ONLINE", cached_time: str = None):
    """Display the projection results."""
    clear_console()
    
    current_time = datetime.now().strftime("%H:%M:%S")
    
    print("=" * 60)
    print(f"=== ELECTION PROJECTION [Last Updated: {current_time}] ===")
    print("=" * 60)
    
    if status == "OFFLINE":
        print(f"\n⚠️  Source Status: OFFLINE (Using Cache from {cached_time})\n")
    else:
        print(f"\n✅ Source Status: ONLINE\n")
    
    print("NATIONAL PROJECTION (Sum of Department Projections):")
    print("-" * 60)
    
    if df.empty:
        print("No data available yet.")
    else:
        for idx, row in df.iterrows():
            votes_formatted = f"{row['Projected Votes']:,}"
            print(f"{idx}. {row['Candidate']}: {votes_formatted} votes (Proj) - {row['Percentage']}%")
    
    print("-" * 60)
    print(f"\nNext update in {CHECK_INTERVAL // 60} minutes...")


def main():
    """Main execution loop."""
    print("=" * 60)
    print("Honduras Election 2025 - Projection Scraper")
    print("=" * 60)
    
    print(f"\nLaunching {BROWSER_NAME} browser...")
    print("(Using separate profile - your normal browser won't be affected)\n")
    
    scraper = ElectionScraper()
    department_data = None
    
    # Launch browser automatically
    if launch_browser_with_debugging():
        print(f"✅ {BROWSER_NAME} launched successfully!")
        print(f"\n📍 Page: {BASE_URL}")
        print("\nWait for the election results to load completely.")
        input("\n>>> Press ENTER when ready to scrape... ")
        
        department_data = scraper.scrape_with_existing_browser()
        
        if department_data:
            print(f"\n✅ Successfully scraped {len(department_data)} data sources!")
        else:
            print("\n⚠️  Could not get data. Falling back to cache...")
    else:
        print(f"❌ Failed to launch {BROWSER_NAME}. Using cached data...")
    
    print("\n[Phase 2] Starting main loop...")
    print(f"Will check for updates every {CHECK_INTERVAL // 60} minutes")
    print("Press Ctrl+C to stop\n")
    
    last_results = load_cache()
    trigger_file = ".trigger_scrape"
    
    # If we got data in phase 1, process it
    if department_data and 'raw_data' not in department_data:
        # Show detailed per-department results (includes totals and projections)
        display_department_results(department_data)
        
        projection_df = calculate_national_projection(department_data)
        if not projection_df.empty:
            cache_data = {
                'departments': department_data,
                'projection': projection_df.to_dict('records')
            }
            save_cache(cache_data)
            last_results = cache_data
    else:
        # Show cached data if no new data
        if last_results:
            cached_df = pd.DataFrame(last_results.get('projection', []))
            cached_time = last_results.get('cached_at', 'Unknown')
            display_results(cached_df, "OFFLINE", cached_time)
    
    while True:
        try:
            # Check for manual trigger every 5 seconds during wait
            for _ in range(CHECK_INTERVAL // 5):
                time.sleep(5)
                if os.path.exists(trigger_file):
                    os.remove(trigger_file)
                    print("\n🔃 Manual scrape requested from dashboard!")
                    break
            
            # Scrape data
            print("\nFetching updated data...")
            
            # Always use existing browser (Edge/Chrome)
            department_data = scraper.scrape_with_existing_browser()
            
            if department_data and 'raw_data' not in department_data:
                # Show detailed per-department results (includes totals and projections)
                display_department_results(department_data)
                
                # Calculate projections and save to cache
                projection_df = calculate_national_projection(department_data)
                
                if not projection_df.empty:
                    cache_data = {
                        'departments': department_data,
                        'projection': projection_df.to_dict('records')
                    }
                    save_cache(cache_data)
                    last_results = cache_data
                else:
                    # Use cached data if available
                    if last_results:
                        cached_df = pd.DataFrame(last_results.get('projection', []))
                        cached_time = last_results.get('cached_at', 'Unknown')
                        display_results(cached_df, "OFFLINE", cached_time)
                    else:
                        display_results(pd.DataFrame(), "OFFLINE")
            else:
                # Use cached data
                if last_results:
                    cached_df = pd.DataFrame(last_results.get('projection', []))
                    cached_time = last_results.get('cached_at', 'Unknown')
                    display_results(cached_df, "OFFLINE", cached_time)
                else:
                    display_results(pd.DataFrame(), "OFFLINE")
                    
        except KeyboardInterrupt:
            print("\n\nStopping scraper...")
            break
        except Exception as e:
            print(f"\n⚠️  Error during scraping: {e}")
            
            # Use cached data
            if last_results:
                cached_df = pd.DataFrame(last_results.get('projection', []))
                cached_time = last_results.get('cached_at', 'Unknown')
                display_results(cached_df, "OFFLINE", cached_time)
            else:
                print("No cached data available.")
        
    print("Scraper stopped. Goodbye!")


if __name__ == "__main__":
    main()
