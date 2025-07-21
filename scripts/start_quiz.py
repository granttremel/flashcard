#!/usr/bin/env python3

from flashcard import FlashcardCollection
from flashcard.quiz import start_interactive_quiz

def main():
    # Load the collection
    print("Loading flashcard collection...")
    collection = FlashcardCollection()
    collection.load_from_excel("./data/flashcards.ods", domain_name="anatomy", sheet_name="anatomy")
    
    print(f"Loaded {len(collection.cards)} anatomy cards")
    
    # Start the interactive quiz
    start_interactive_quiz(collection)

if __name__ == "__main__":
    main()