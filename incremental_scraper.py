import os
import time
import json
import hashlib
from playwright.sync_api import sync_playwright
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import config
from rag import get_collection, get_embedder

PDF_DOWNLOAD_DIR = "./pdfs"
TEXT_DOWNLOAD_DIR = "./scraped_data"
STATE_FILE = "scraper_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            # Ensure new keys exist if updating from older state file
            if "text_hashes" not in state:
                state["text_hashes"] = {}
            if "embedded_text" not in state:
                state["embedded_text"] = {}
            if "processed_tests" not in state:
                state["processed_tests"] = state.get("processed_pdfs", [])
            if "processed_files" not in state:
                state["processed_files"] = []
            return state
    return {"processed_tests": [], "processed_files": [], "text_hashes": {}, "embedded_text": {}}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def scrape_section(page, section_name, state):
    print(f"[Scraper] Navigating to {section_name}...")
    try:
        page.locator(f'text="{section_name}"').first.click()
        page.wait_for_timeout(3000)
        
        print(f"[Scraper] Scrolling through {section_name} to load all data...")
        last_height = page.evaluate("document.body.scrollHeight")
        # Infinite scroll to ensure we get ALL students/staff
        while True:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
        print(f"[Scraper] Extracting data from {section_name}...")
        text_content = page.evaluate("document.body.innerText")
        
        # Calculate MD5 hash of the page text to see if anything changed
        content_hash = hashlib.md5(text_content.encode('utf-8')).hexdigest()
        
        if state["text_hashes"].get(section_name) == content_hash:
            print(f"[Scraper] No new data found in {section_name}. Skipping.")
            return False # Indicates no changes
            
        filepath = os.path.join(TEXT_DOWNLOAD_DIR, f"{section_name.replace(' ', '_').replace('&', 'and')}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text_content)
            
        state["text_hashes"][section_name] = content_hash
        save_state(state)
        print(f"[Scraper] Saved new/updated data to {filepath}")
        return True # Indicates changes were made
    except Exception as e:
        print(f"[Scraper] Failed to scrape section '{section_name}': {e}")
        return False

def scrape_incremental():
    print("=========================================")
    print(" STARTING INCREMENTAL SCRAPER")
    print("=========================================")
    
    os.makedirs(PDF_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(TEXT_DOWNLOAD_DIR, exist_ok=True)
    state = load_state()
    
    # Track which text sections were actually updated this run
    updated_text_sections = []
    
    # 1. Scrape the website using Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"[Scraper] Navigating to {config.ADMIN_PORTAL_URL}")
        
        try:
            page.goto(config.ADMIN_PORTAL_URL, timeout=60000)
            
            # Login Form
            print("[Scraper] Waiting for login screen...")
            page.get_by_placeholder("Enter your User ID or Email").fill(config.ADMIN_USERNAME)
            page.get_by_placeholder("Enter your password").fill(config.ADMIN_PASSWORD)
            page.get_by_role("button", name="Sign In").click()
            print("[Scraper] Logged in successfully. Waiting for dashboard...")
            page.wait_for_timeout(3000)
            
            # --- SCRAPE NEW SECTIONS (TEXT) INCREMENTALLY ---
            sections_to_scrape = [
                "Dashboard",
                "Departments", 
                "Faculty & Staff", 
                "Students",
                "Question Bank",
                "Tests Management",
                "Selective Reports"
            ]
            
            for section in sections_to_scrape:
                if scrape_section(page, section, state):
                    updated_text_sections.append(section)
            
            # --- SCRAPE REPORTS (PDFs) ---
            print("[Scraper] Navigating to Reports & Analytics...")
            page.locator('text="Reports & Analytics"').first.click()
            page.wait_for_timeout(2000)
            
            print("[Scraper] Navigating to Test-Wise PDF...")
            page.locator('text="Test-Wise PDF"').first.click()
            page.wait_for_timeout(3000)

            print("[Scraper] Auto-scrolling the test list to find ALL test cards...")
            # Use xpath or :has to target the parent container card, not the inner text div!
            test_cards_locator = page.locator("div.cursor-pointer:has-text('students')")
            
            # Infinite scroll logic to get all 900+ cards instead of just 367
            current_count = test_cards_locator.count()
            while current_count > 0:
                print(f"[Scraper] Found {current_count} tests so far. Scrolling down...")
                test_cards_locator.nth(current_count - 1).scroll_into_view_if_needed()
                page.wait_for_timeout(2000)
                new_count = test_cards_locator.count()
                if new_count == current_count:
                    break # Reached the bottom
                current_count = new_count
                
            print(f"[Scraper] Total tests found on page: {current_count}")
            
            if current_count == 0:
                print("[Scraper] No test cards found! Could not locate the list of tests.")
            else:
                for i in range(current_count):
                    card = test_cards_locator.nth(i)
                    
                    # Try to get a unique identifier for the test card to avoid re-downloading
                    test_info = card.inner_text()
                    # test_info now contains multiple lines: "Test Name\nDate\nFaculty\n39 students"
                    # Combine them to create a perfectly unique ID for every test
                    test_id = "_".join([line.strip() for line in test_info.split("\n") if line.strip()]).replace(" ", "_").replace("/", "-")
                    
                    if test_id in state["processed_tests"]:
                        print(f"[Scraper] Skipping already processed test: {test_id}")
                        continue
                        
                    print(f"[Scraper] Clicking new test card {i+1}/{current_count}: {test_id}")
                    card.scroll_into_view_if_needed()
                    card.click()
                    
                    # Wait dynamically for the UI to render the download button (up to 15 seconds)
                    # We use page.wait_for_function to guarantee we only target the *visible* button, 
                    # avoiding any hidden templates that might break Playwright locators.
                    try:
                        page.wait_for_function('''() => {
                            let btns = Array.from(document.querySelectorAll('button, a'));
                            return btns.some(el => el.innerText.includes('Download PDF Report') && el.offsetParent !== null);
                        }''', timeout=15000)
                        
                        # Wait properly for the download to completely finish
                        with page.expect_download(timeout=60000) as download_info:
                            page.evaluate('''() => {
                                let btns = Array.from(document.querySelectorAll('button, a'));
                                let btn = btns.find(el => el.innerText.includes('Download PDF Report') && el.offsetParent !== null);
                                if (btn) btn.click();
                            }''')
                            
                        download = download_info.value
                        original_name = download.suggested_filename
                        filepath = os.path.join(PDF_DOWNLOAD_DIR, original_name)
                        download.save_as(filepath)
                        print(f"[Scraper] Successfully downloaded: {original_name}")
                        
                        # Mark this test as processed so we don't click it again next run
                        state["processed_tests"].append(test_id)
                        save_state(state)
                    except Exception as e:
                        print(f"[Scraper] Warning: Download button did not appear for test {test_id}. Error: {e}")
            
        except Exception as e:
            print(f"[Scraper] Error during scraping: {e}")
        finally:
            browser.close()

    # 2. Process and Embed into ChromaDB Incrementally
    print("[Scraper] Processing downloaded data into embeddings...")
    collection = get_collection()
    embedder = get_embedder()
    
    embedded_count = 0
    
    # Process text files (incrementally)
    for section_name in updated_text_sections:
        filename = f"{section_name.replace(' ', '_').replace('&', 'and')}.txt"
        filepath = os.path.join(TEXT_DOWNLOAD_DIR, filename)
        
        if os.path.exists(filepath):
            print(f"[Scraper] Embedding updated text section: {section_name}")
            loader = TextLoader(filepath, encoding="utf-8")
            docs = loader.load_and_split()
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = text_splitter.split_documents(docs)
            
            for i, chunk in enumerate(chunks):
                embedding = embedder.encode(chunk.page_content).tolist()
                collection.upsert(
                    ids=[f"{filename}_chunk_{i}"],
                    embeddings=[embedding],
                    documents=[chunk.page_content],
                    metadatas=[{"source": filename}]
                )
            embedded_count += 1
            
    # Process PDFs incrementally
    for filename in os.listdir(PDF_DOWNLOAD_DIR):
        if filename.endswith(".pdf"):
            if filename in state["processed_files"]:
                continue # Skip already embedded PDFs to save time
                
            print(f"[Scraper] Embedding new PDF: {filename}")
            filepath = os.path.join(PDF_DOWNLOAD_DIR, filename)
            loader = PyPDFLoader(filepath)
            pages = loader.load_and_split()
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = text_splitter.split_documents(pages)
            
            for i, chunk in enumerate(chunks):
                embedding = embedder.encode(chunk.page_content).tolist()
                collection.upsert(
                    ids=[f"{filename}_chunk_{i}"],
                    embeddings=[embedding],
                    documents=[chunk.page_content],
                    metadatas=[{"source": filename}]
                )
                
            state["processed_files"].append(filename)
            save_state(state)
            embedded_count += 1
            
    print(f"[Scraper] Incremental run complete. Embedded {embedded_count} new/updated documents.")

if __name__ == "__main__":
    while True:
        try:
            scrape_incremental()
        except Exception as e:
            print(f"[Scraper] Critical Error: {e}")
        
        # Sleep for 12 hours before next incremental run
        print("[Scraper] Sleeping for 12 hours. (Leave this window open to run in background)")
        time.sleep(12 * 60 * 60)
