#!/usr/bin/env python3

from flashcard.wikipedia import WikiManager

def quick_view_examples():
    """Quick examples of viewing Wikipedia pages."""
    
    wm = WikiManager()
    
    print("🚀 Quick Wikipedia Viewer Examples")
    print("="*40)
    
    # Example pages to view
    example_pages = [
        "Hormone",
        "Nervous_system", 
        "Heart",
        "Brain"
    ]
    
    for page in example_pages:
        print(f"\n📖 To view '{page.replace('_', ' ')}' page:")
        print(f"   python scripts/view_wiki_page.py {page}")
    
    print(f"\n💡 You can also do this programmatically:")
    print(f"   from flashcard.wikipedia import WikiManager")
    print(f"   wm = WikiManager()")
    print(f"   wm.view_page_in_browser('Hormone')")
    
    print(f"\n🌐 Browser options:")
    print(f"   firefox (default)")
    print(f"   chromium") 
    print(f"   google-chrome")
    print(f"   Any browser command available on your system")

if __name__ == "__main__":
    quick_view_examples()