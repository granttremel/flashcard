#!/usr/bin/env python3

from flashcard import FlashcardCollection
from flashcard.edit import FlashcardEditor

def main():
    # Load the collection
    print("Loading flashcard collection...")
    collection = FlashcardCollection()
    collection.load_from_excel("./data/flashcards.ods", domain_name="anatomy", sheet_name="anatomy")
    
    # Create editor
    editor = FlashcardEditor(collection)
    
    # Show current summary
    editor.show_summary()
    
    # Show orphan analysis
    editor.show_orphan_analysis('anatomy')
    
    # Uncomment to test interactive creation:
    # editor.create_missing_cards('anatomy', max_cards=5)

if __name__ == "__main__":
    main()