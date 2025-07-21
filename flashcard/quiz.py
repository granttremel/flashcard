"""
Simple quiz/test interface for flashcard study sessions.
"""

import random
from typing import Dict, List, Tuple, Optional
from . import FlashcardCollection, Flashcard

class FlashcardQuiz:
    """Interactive quiz system for flashcard studying."""
    
    def __init__(self, collection: FlashcardCollection):
        self.collection = collection
        self.stats = {
            'attempted': 0,
            'correct': 0,
            'partial': 0,
            'wrong': 0
        }
    
    def start_quiz(self, domain_name: str = 'anatomy', num_questions: int = 10, 
                   clues_per_question: int = 3, mode: str = 'forward'):
        """Start an interactive quiz session.
        
        Args:
            domain_name: Domain to quiz on
            num_questions: Number of questions
            clues_per_question: Number of clues per question (forward mode) or fields to fill (reverse mode)
            mode: 'forward' (clues → concept) or 'reverse' (concept → fields)
        """
        mode_desc = "Facts → Concept" if mode == 'forward' else "Concept → Facts"
        print(f"\n🧠 === Flashcard Quiz: {domain_name.title()} ({mode_desc}) ===")
        
        if mode == 'forward':
            print(f"Questions: {num_questions} | Clues per question: {clues_per_question}")
            print("Type 'quit' to exit, 'hint' for more clues, 'skip' to skip question\n")
        else:
            print(f"Questions: {num_questions} | Fields to fill per question: {clues_per_question}")
            print("Type 'quit' to exit, 'skip' to skip question\n")
        
        # Get cards from the specified domain
        cards = self.collection.get_cards_by_domain(domain_name)
        if not cards:
            print(f"No cards found for domain: {domain_name}")
            return
        
        # Filter to cards that have enough data for good questions
        good_cards = [card for card in cards if self._is_good_quiz_card(card, clues_per_question)]
        if not good_cards:
            print("Not enough complete cards for quiz!")
            return
        
        print(f"Quiz pool: {len(good_cards)} cards\n")
        
        for question_num in range(1, num_questions + 1):
            print(f"--- Question {question_num}/{num_questions} ---")
            
            # Select a random card
            card = random.choice(good_cards)
            
            # Ask the question based on mode
            if mode == 'forward':
                result = self._ask_question(card, clues_per_question)
            else:
                result = self._ask_reverse_question(card, clues_per_question)
            
            if result == 'quit':
                break
            elif result == 'skip':
                print("Question skipped.\n")
                continue
            
            # Update stats
            self.stats['attempted'] += 1
            self.stats[result] += 1
            
            print()  # Blank line between questions
        
        self._show_final_stats()
    
    def _is_good_quiz_card(self, card: Flashcard, min_clues: int) -> bool:
        """Check if a card has enough data to make a good quiz question."""
        non_empty_fields = sum(1 for values in card.get_all_fields().values() if values)
        return non_empty_fields >= min_clues
    
    def _ask_question(self, card: Flashcard, num_clues: int) -> str:
        """Ask a single question about a card. Returns result: 'correct'/'partial'/'wrong'/'skip'/'quit'."""
        # Generate clues from the card
        clues = self._generate_clues(card, num_clues)
        
        # Present initial clues
        for i, clue in enumerate(clues, 1):
            print(f"{i}. {clue}")
        
        hints_used = 0
        max_hints = min(3, len(self._get_available_clue_fields(card)) - num_clues)
        
        while True:
            user_input = input("\nWhat concept is this? ").strip()
            
            if user_input.lower() == 'quit':
                return 'quit'
            elif user_input.lower() == 'skip':
                print(f"\nAnswer: {card.concept}")
                return 'skip'
            elif user_input.lower() == 'hint' and hints_used < max_hints:
                # Provide an additional clue
                additional_clues = self._generate_clues(card, num_clues + hints_used + 1)
                if len(additional_clues) > len(clues):
                    new_clue = additional_clues[len(clues)]
                    print(f"\nHint: {new_clue}")
                    clues.append(new_clue)
                    hints_used += 1
                else:
                    print("No more hints available!")
                continue
            elif user_input.lower() == 'hint':
                print("No more hints available!")
                continue
            elif not user_input:
                print("Please enter your answer (or 'quit'/'skip'/'hint')")
                continue
            
            # Validate and check the answer
            return self._check_answer(user_input, card)
    
    def _generate_clues(self, card: Flashcard, num_clues: int) -> List[str]:
        """Generate clues from a flashcard."""
        available_fields = self._get_available_clue_fields(card)
        
        # Prioritize certain fields for better clues
        field_priority = {
            'Function': 1,
            'Structure': 2, 
            'Anatomical Class': 3,
            'System': 4,
            'Related Pathologies': 5,
            'Substructures': 6,
            'Superstructures': 7
        }
        
        # Sort fields by priority (lower number = higher priority)
        sorted_fields = sorted(available_fields, 
                             key=lambda f: field_priority.get(f, 10))
        
        clues = []
        for field_name in sorted_fields[:num_clues]:
            values = card.get_all_fields()[field_name]
            clue = self._format_clue(field_name, values)
            clues.append(clue)
        
        return clues
    
    def _get_available_clue_fields(self, card: Flashcard) -> List[str]:
        """Get list of fields that can be used as clues."""
        # Fields that should be excluded as they might reveal the answer
        excluded_fields = {
            'wiki', 'aka', 'anatomical structure', 'anatomic structure', 
            'concept', 'name', 'title'
        }
        
        available = []
        for field_name, values in card.get_all_fields().items():
            if values and field_name.lower() not in excluded_fields:
                # Also check if the field value contains the concept name (would give it away)
                field_reveals_answer = any(
                    card.concept.lower() in str(value).lower() 
                    for value in values
                )
                if not field_reveals_answer:
                    available.append(field_name)
        return available
    
    def _format_clue(self, field_name: str, values: List[str]) -> str:
        """Format a clue from field name and values."""
        if len(values) == 1:
            return f"{field_name}: {values[0]}"
        else:
            # Multiple values, show them nicely
            if len(values) <= 3:
                return f"{field_name}: {'; '.join(values)}"
            else:
                return f"{field_name}: {'; '.join(values[:3])} (and {len(values)-3} more)"
    
    def _check_answer(self, user_answer: str, card: Flashcard) -> str:
        """Check user's answer against the correct answer."""
        correct_concept = card.concept
        
        # Use symbol normalizer for validation
        suggestion = self.collection.symbol_normalizer.suggest_normalization(
            user_answer, {correct_concept}
        )
        
        # Show the correct answer
        print(f"\n✅ Correct answer: {correct_concept}")
        print(f"📝 Your answer: {user_answer}")
        
        # Check for exact match (case-insensitive)
        if user_answer.lower() == correct_concept.lower():
            print("🎯 Perfect match!")
            score = input("Score this as: (c)orrect, (p)artial, or (w)rong? ").lower()
        else:
            # Check if it's similar
            similar = self.collection.symbol_normalizer.find_similar_symbols(
                user_answer, {correct_concept}, threshold=0.6
            )
            
            if similar and similar[0][1] > 0.8:
                print(f"🔍 Very close! Similarity: {similar[0][1]:.2f}")
            elif similar and similar[0][1] > 0.6:
                print(f"🤔 Somewhat similar. Similarity: {similar[0][1]:.2f}")
            else:
                print("❌ Not a close match.")
            
            # Show normalized version if different
            if suggestion['normalized'] != user_answer:
                print(f"📝 Normalized: {suggestion['normalized']}")
            
            # Self-scoring
            print("\nDid you know this concept?")
            score = input("Score this as: (c)orrect, (p)artial, or (w)rong? ").lower()
        
        # Map user input to result
        if score.startswith('c'):
            print("Great job! 🎉")
            return 'correct'
        elif score.startswith('p'):
            print("Good effort! 👍")
            return 'partial' 
        else:
            print("Keep studying! 📚")
            return 'wrong'
    
    def _show_final_stats(self):
        """Show final quiz statistics."""
        if self.stats['attempted'] == 0:
            print("No questions completed!")
            return
            
        print("\n📊 === Quiz Complete! ===")
        print(f"Questions attempted: {self.stats['attempted']}")
        print(f"✅ Correct: {self.stats['correct']}")
        print(f"🔶 Partial: {self.stats['partial']}")
        print(f"❌ Wrong: {self.stats['wrong']}")
        
        if self.stats['attempted'] > 0:
            accuracy = (self.stats['correct'] + 0.5 * self.stats['partial']) / self.stats['attempted']
            print(f"📈 Accuracy: {accuracy:.1%}")
            
        print("\nKeep up the great work! 🧠💪")
    
    def _ask_reverse_question(self, card: Flashcard, num_fields: int) -> str:
        """Ask a reverse question: given concept, fill in fields. Returns result."""
        # Get available fields for questioning
        available_fields = self._get_available_clue_fields(card)
        
        if len(available_fields) < num_fields:
            print(f"Not enough fields for reverse quiz on {card.concept}")
            return 'skip'
        
        # Select random fields to ask about
        selected_fields = random.sample(available_fields, num_fields)
        
        # Present the concept
        print(f"📋 Concept: {card.concept}")
        print(f"Please provide information for these {num_fields} fields:\n")
        
        user_answers = {}
        correct_answers = {}
        
        # Ask for each field
        for i, field_name in enumerate(selected_fields, 1):
            correct_values = card.get_all_fields()[field_name]
            correct_answers[field_name] = correct_values
            
            print(f"{i}. {field_name}:")
            user_answer = input("   Your answer: ").strip()
            
            if user_answer.lower() == 'quit':
                return 'quit'
            elif user_answer.lower() == 'skip':
                print(f"\nSkipping question about {card.concept}")
                return 'skip'
            
            user_answers[field_name] = user_answer
            print()  # Blank line
        
        # Show correct answers and let user self-score
        print("✅ === Correct Answers ===")
        for field_name in selected_fields:
            user_ans = user_answers[field_name] or "[No answer]"
            correct_ans = "; ".join(correct_answers[field_name])
            
            print(f"{field_name}:")
            print(f"  Your answer: {user_ans}")
            print(f"  Correct:     {correct_ans}")
            print()
        
        # Self-scoring
        print("How well did you do overall on this concept?")
        score = input("Score this as: (c)orrect, (p)artial, or (w)rong? ").lower()
        
        # Map user input to result
        if score.startswith('c'):
            print("Excellent! You know this concept well! 🎉")
            return 'correct'
        elif score.startswith('p'):
            print("Good progress! Keep reviewing! 👍") 
            return 'partial'
        else:
            print("Keep studying this concept! 📚")
            return 'wrong'

def start_interactive_quiz(collection: FlashcardCollection):
    """Start an interactive quiz with user configuration."""
    quiz = FlashcardQuiz(collection)
    
    print("🎓 Welcome to Flashcard Quiz!")
    
    # Get quiz parameters
    domain = input("Domain (default: anatomy): ").strip() or 'anatomy'
    
    try:
        num_questions = int(input("Number of questions (default: 10): ") or "10")
    except ValueError:
        num_questions = 10
    
    try:
        clues = int(input("Clues per question (default: 3): ") or "3")
    except ValueError:
        clues = 3
    
    # Ask for quiz mode
    mode = input("Quiz mode - (f)orward (clues → concept) or (r)everse (concept → fields)? (default: forward): ").lower()
    if mode.startswith('r'):
        mode = 'reverse'
    else:
        mode = 'forward'
    
    quiz.start_quiz(domain, num_questions, clues, mode)