#!/usr/bin/env python3

from flashcard.wikipedia import WikiManager
import sys
import os

def view_page(page_name, browser="firefox"):
    """View a stored Wikipedia page in the browser."""
    
    wm = WikiManager()
    
    print(f"🌐 Opening Wikipedia page: {page_name}")
    print(f"📁 Looking for: ./data/wiki/{page_name}.json")
    
    success = wm.view_page_in_browser(page_name, browser)
    
    if success:
        print(f"✅ Successfully opened {page_name} in {browser}")
        print("📖 The page should now be displayed with Wikipedia-like formatting")
    else:
        print(f"❌ Failed to open {page_name}")
        print("💡 Make sure the JSON file exists in ./data/wiki/")

def list_available_pages():
    """List all available Wikipedia pages."""
    wiki_dir = "./data/wiki"
    
    if not os.path.exists(wiki_dir):
        print(f"❌ Directory {wiki_dir} not found")
        return
    
    json_files = [f for f in os.listdir(wiki_dir) if f.endswith('.json')]
    
    if not json_files:
        print(f"📂 No Wikipedia pages found in {wiki_dir}")
        return
    
    print(f"📚 Available Wikipedia pages ({len(json_files)} found):")
    print("="*50)
    
    for json_file in sorted(json_files):
        page_name = json_file.replace('.json', '')
        page_display = page_name.replace('_', ' ')
        print(f"  📄 {page_display}")
        print(f"      Command: python {sys.argv[0]} {page_name}")
    
    print("\n💡 Usage examples:")
    print(f"  python {sys.argv[0]} Hormone")
    print(f"  python {sys.argv[0]} Nervous_system firefox")
    print(f"  python {sys.argv[0]} Hormone chromium")

def main():
    if len(sys.argv) < 2:
        print("🕷️ Wikipedia Page Viewer")
        print("="*30)
        print()
        list_available_pages()
        return
    
    if sys.argv[1] in ['--list', '-l', 'list']:
        list_available_pages()
        return
    
    page_name = sys.argv[1]
    browser = sys.argv[2] if len(sys.argv) > 2 else "firefox"
    
    # Handle spaces in page names
    page_name = page_name.replace(' ', '_')
    
    view_page(page_name, browser)

if __name__ == "__main__":
    main()