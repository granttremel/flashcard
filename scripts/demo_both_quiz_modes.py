#!/usr/bin/env python3

from flashcard import FlashcardCollection
from flashcard.quiz import FlashcardQuiz

def main():
    # Load the collection
    print("Loading flashcard collection...")
    collection = FlashcardCollection()
    collection.load_from_excel("./data/flashcards.ods", domain_name="anatomy", sheet_name="anatomy")
    
    print(f"Loaded {len(collection.cards)} anatomy cards\n")
    
    # Create quiz
    quiz = FlashcardQuiz(collection)
    
    # Show examples of both modes
    cards = collection.get_cards_by_domain('anatomy')
    good_cards = [card for card in cards if quiz._is_good_quiz_card(card, 3)]
    
    if not good_cards:
        print("No cards suitable for quiz found!")
        return
    
    sample_card = good_cards[0]  # Use first suitable card
    
    print("=== FORWARD MODE DEMO (Facts → Concept) ===")
    clues = quiz._generate_clues(sample_card, 3)
    print("Question format:")
    for i, clue in enumerate(clues, 1):
        print(f"{i}. {clue}")
    print(f"\\nAnswer: {sample_card.concept}\\n")
    
    print("=== REVERSE MODE DEMO (Concept → Facts) ===")
    available_fields = quiz._get_available_clue_fields(sample_card)
    print("Question format:")
    print(f"📋 Concept: {sample_card.concept}")
    print("Please provide information for these 3 fields:\\n")
    
    # Show what fields might be asked
    import random
    if len(available_fields) >= 3:
        sample_fields = random.sample(available_fields, 3)
        for i, field in enumerate(sample_fields, 1):
            correct_values = sample_card.get_all_fields()[field]
            print(f"{i}. {field}:")
            print(f"   [You would enter your answer here]")
            print(f"   Correct answer: {'; '.join(correct_values)}")
            print()
    
    print(f"Available for quiz: {len(good_cards)} cards")
    print("\\nTo start a real quiz:")
    print("  python scripts/start_quiz.py")
    print("\\nOr from your dev script:")
    print("  from flashcard.quiz import start_interactive_quiz")
    print("  start_interactive_quiz(collection)")
    
    print("\\n🎯 Both modes now exclude 'Anatomical Structure' and other revealing fields!")
    print("🎯 Self-scoring allows you to judge partial credit realistically!")

if __name__ == "__main__":
    main()