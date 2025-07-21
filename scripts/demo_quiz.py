#!/usr/bin/env python3

from flashcard import FlashcardCollection
from flashcard.quiz import FlashcardQuiz

def main():
    # Load the collection
    print("Loading flashcard collection for quiz demo...")
    collection = FlashcardCollection()
    collection.load_from_excel("./data/flashcards.ods", domain_name="anatomy", sheet_name="anatomy")
    
    print(f"Loaded {len(collection.cards)} anatomy cards\n")
    
    # Create quiz
    quiz = FlashcardQuiz(collection)
    
    # Show a sample of what questions look like
    cards = collection.get_cards_by_domain('anatomy')
    good_cards = [card for card in cards if quiz._is_good_quiz_card(card, 3)]
    
    if good_cards:
        print("=== Sample Quiz Question ===")
        sample_card = good_cards[0]  # Take first card as example
        clues = quiz._generate_clues(sample_card, 3)
        
        print("Example question format:")
        for i, clue in enumerate(clues, 1):
            print(f"{i}. {clue}")
        
        print(f"\nAnswer: {sample_card.concept}")
        print(f"Available for quiz: {len(good_cards)} cards\n")
        
        print("To start an actual quiz, run:")
        print("  python scripts/start_quiz.py")
        print("\nOr from Python:")
        print("  from flashcard.quiz import start_interactive_quiz")
        print("  start_interactive_quiz(collection)")
    else:
        print("No cards suitable for quiz found!")

if __name__ == "__main__":
    main()