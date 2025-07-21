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
    
    # Show summary
    editor.show_summary()
    
    # Find an incomplete card to test
    incomplete_cards = collection.get_incomplete_cards()
    if incomplete_cards:
        print(f"\nTesting editor with card: {incomplete_cards[0].concept}")
        # Uncomment to test interactive editing:
        # editor.edit_card(incomplete_cards[0].concept)
    
    # Test domain-specific filtering
    print("\n=== Anatomy Domain Cards ===")
    anatomy_cards = collection.get_cards_by_domain('anatomy')
    print(f"Total anatomy cards: {len(anatomy_cards)}")
    
    # Show a sample card
    if anatomy_cards:
        sample_card = anatomy_cards[0]
        print(f"\nSample card: {sample_card.concept}")
        print(f"Domain: {sample_card.domain.name}")
        print(f"Complete: {sample_card.is_complete()}")
        if not sample_card.is_complete():
            print(f"Missing fields: {', '.join(sample_card.get_incomplete_fields())}")

if __name__ == "__main__":
    main()