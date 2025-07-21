
from . import FlashcardCollection

class FlashcardEditor:
    """Interactive editor for flashcards"""
    
    def __init__(self, collection: FlashcardCollection):
        self.collection = collection
    
    def edit_card(self, concept: str):
        """Edit a specific flashcard interactively"""
        card = self.collection.get_card(concept)
        if not card:
            print(f"Card '{concept}' not found!")
            return
        
        print(f"\n=== Editing: {concept} ===")
        incomplete_fields = card.get_incomplete_fields()
        
        if not incomplete_fields:
            print("This card is complete!")
            edit_anyway = input("Edit anyway? (y/n): ").lower() == 'y'
            if not edit_anyway:
                return
        else:
            print(f"Incomplete fields: {', '.join(incomplete_fields)}")
        
        # Edit each field
        for field_name in card.fields:
            current_values = card.get_field_values(field_name)
            print(f"\n{field_name}:")
            if current_values:
                print(f"  Current: {'; '.join(current_values)}")
            else:
                print("  Current: [EMPTY]")
            
            new_value = input("  New value (semicolon-separated, or press Enter to keep current): ")
            if new_value:
                card.add_field(field_name, new_value)
        
        # Show linked cards
        if card.links:
            print("\nLinked cards:")
            for link_type, linked_concepts in card.links.items():
                print(f"  {link_type}: {', '.join(linked_concepts)}")
    
    def edit_incomplete_cards(self):
        """Edit all incomplete cards"""
        incomplete = self.collection.get_incomplete_cards()
        if not incomplete:
            print("All cards are complete!")
            return
        
        print(f"\nFound {len(incomplete)} incomplete cards.")
        for i, card in enumerate(incomplete):
            print(f"\n[{i+1}/{len(incomplete)}]")
            self.edit_card(card.concept)
            
            if i < len(incomplete) - 1:
                cont = input("\nContinue to next card? (y/n): ").lower()
                if cont != 'y':
                    break
    
    def show_summary(self):
        """Show summary of the collection"""
        total = len(self.collection.cards)
        incomplete = len(self.collection.get_incomplete_cards())
        complete = total - incomplete
        
        print(f"\n=== Collection Summary ===")
        print(f"Total cards: {total}")
        print(f"Complete: {complete} ({complete/total*100:.1f}%)")
        print(f"Incomplete: {incomplete} ({incomplete/total*100:.1f}%)")
        print(f"\nField names: {', '.join(sorted(self.collection.field_names))}")
        
        # Show cards with most links
        cards_by_links = sorted(
            self.collection.cards.items(), 
            key=lambda x: sum(len(links) for links in x[1].links.values()),
            reverse=True
        )[:5]
        
        print("\nMost connected cards:")
        for concept, card in cards_by_links:
            total_links = sum(len(links) for links in card.links.values())
            if total_links > 0:
                print(f"  {concept}: {total_links} links")
