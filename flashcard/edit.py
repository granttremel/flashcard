
import webbrowser
from typing import Optional, List, Dict
from . import FlashcardCollection
from .wikipedia import generate_wikipedia_url, open_wikipedia_page
from .orphan_detection import suggest_missing_cards

class FlashcardEditor:
    """Interactive editor for flashcards"""
    
    def __init__(self, collection: FlashcardCollection):
        self.collection = collection
        self.navigation_action = None  # Used to signal navigation between cards
    
    def _process_field_command(self, command: str, card, field_name: str) -> Optional[str]:
        """Process commands entered during field editing. Returns field value if any."""
        parts = command.strip().split()
        if not parts:
            return None
            
        cmd = parts[0].lower()
        
        if cmd == 'wiki':
            if len(parts) < 2:
                print("  Wiki commands: -w (open page), -s (search), -g (generate URL), -v (validate)")
                return None
                
            flag = parts[1]
            # Allow custom concept if provided after flag
            concept_override = ' '.join(parts[2:]) if len(parts) > 2 else card.concept
            
            if flag == '-w':
                open_wikipedia_page(concept_override)
                print(f"  Opened Wikipedia page for: {concept_override}")
            elif flag == '-s':
                open_wikipedia_page(concept_override, search=True)
                print(f"  Searching Wikipedia for: {concept_override}")
            elif flag == '-g':
                wiki_url = generate_wikipedia_url(concept_override)
                print(f"  Generated URL: {wiki_url}")
                use_it = input("  Use this URL? (y/n): ").lower()
                if use_it == 'y':
                    return wiki_url
            elif flag == '-v':
                current_wiki = card.data.get('Wiki', [])
                if current_wiki:
                    print(f"  Current Wiki URL: {current_wiki[0]}")
                    open_url = input("  Open this URL to validate? (y/n): ").lower()
                    if open_url == 'y':
                        webbrowser.open(current_wiki[0])
                else:
                    print("  No Wiki URL set for this card")
                    
        elif cmd == 'help':
            print("\n  Available commands:")
            print("  === Field Commands ===")
            print("  wiki -w [concept]  : Open Wikipedia page")
            print("  wiki -s [concept]  : Search Wikipedia")
            print("  wiki -g [concept]  : Generate and insert Wikipedia URL")
            print("  wiki -v            : Validate current Wiki URL")
            print("  suggest <partial>  : Find similar existing symbols")
            print("  skip               : Skip this field")
            print("  clear              : Clear this field")
            print("  last               : Go back to previous field")
            print("  === Card Navigation ===")
            print("  next               : Save and go to next incomplete card")
            print("  prev               : Save and go to previous card")
            print("  done               : Save and exit editing")
            print("  help               : Show this help")
            
        elif cmd == 'skip':
            return 'SKIP_FIELD'
            
        elif cmd == 'clear':
            return ''
            
        elif cmd == 'last':
            return 'GO_BACK'
            
        elif cmd == 'suggest':
            # Suggest symbols based on partial input
            if len(parts) < 2:
                print("  Usage: suggest <partial_symbol>")
                return None
            
            partial = ' '.join(parts[1:])
            suggestions = self.collection.symbol_normalizer.find_similar_symbols(
                partial, set(self.collection.cards.keys()), threshold=0.3
            )
            
            if suggestions:
                print(f"  Symbol suggestions for '{partial}':")
                for symbol, score in suggestions[:10]:
                    print(f"    {symbol} ({score:.2f})")
            else:
                print(f"  No similar symbols found for '{partial}'")
            return None
            
        elif cmd in ['next', 'prev', 'done']:
            self.navigation_action = cmd
            return 'SKIP_FIELD'  # Skip remaining fields
            
        return None
    
    def edit_card(self, concept: str):
        """Edit a specific flashcard interactively"""
        card = self.collection.get_card(concept)
        if not card:
            print(f"Card '{concept}' not found!")
            return
        
        print(f"\n=== Editing: {concept} ({card.domain.name}) ===")
        incomplete_fields = card.get_incomplete_fields()
        
        if not incomplete_fields:
            print("This card is complete!")
            edit_anyway = input("Edit anyway? (y/n): ").lower() == 'y'
            if not edit_anyway:
                return
        else:
            print(f"Incomplete fields: {', '.join(incomplete_fields)}")
        
        print("\nTip: Type 'help' at any field for available commands")
        
        # Edit each field
        field_index = 0
        while field_index < len(card.domain.data_fields):
            field_name = card.domain.data_fields[field_index]
            while True:  # Loop until we get a non-command input
                current_values = card.data.get(field_name, [])
                print(f"\n{field_name}:")
                if current_values:
                    print(f"  Current: {'; '.join(current_values)}")
                else:
                    print("  Current: [EMPTY]")
                
                new_value = input("  New value (or command): ")
                
                # Check if it's a command
                cmd_words = new_value.strip().lower().split()
                if cmd_words and (cmd_words[0] in ['wiki', 'help', 'skip', 'clear', 'last', 'next', 'prev', 'done', 'suggest'] or new_value.strip().startswith('wiki ')):
                    result = self._process_field_command(new_value, card, field_name)
                    if result == 'SKIP_FIELD':
                        field_index += 1
                        break  # Skip to next field
                    elif result == 'GO_BACK':
                        if field_index > 0:
                            field_index -= 1
                            print("\n  << Going back to previous field >>")
                        else:
                            print("\n  (Already at first field)")
                        break
                    elif result is not None:
                        # Command returned a value to use
                        card.add_field(field_name, result)
                        field_index += 1
                        break
                    # Otherwise continue prompting
                else:
                    # Regular input
                    if new_value:  # Non-empty input
                        # Validate and suggest corrections for symbol references
                        self._validate_field_input(new_value, field_name)
                        card.add_field(field_name, new_value)
                    field_index += 1
                    break  # Move to next field
    
    def _validate_field_input(self, value: str, field_name: str):
        """Validate field input and suggest corrections for potential symbols."""
        # Only validate fields that might contain symbol references
        link_related_fields = ['superstructure', 'substructure', 'superclass', 'subclass', 
                              'localizedwith', 'developsfrom', 'relatedpathology', 'involvedin']
        
        field_lower = field_name.lower().replace(' ', '').replace('_', '')
        if not any(pattern in field_lower for pattern in link_related_fields):
            return  # Skip validation for non-link fields
        
        # Split value by semicolons and check each part
        parts = [part.strip() for part in value.split(';')]
        for part in parts:
            if len(part) < 2:
                continue
                
            # Check if it matches an existing symbol
            if part in self.collection.cards:
                continue  # Perfect match, no issue
                
            # Get normalization suggestion
            suggestion = self.collection.symbol_normalizer.suggest_normalization(
                part, set(self.collection.cards.keys())
            )
            
            if suggestion['exact_match']:
                print(f"  💡 '{part}' → suggested: '{suggestion['exact_match']}'")
            elif suggestion['similar'] and suggestion['similar'][0][1] > 0.7:
                best_match = suggestion['similar'][0][0]
                score = suggestion['similar'][0][1]
                print(f"  ⚠️  '{part}' → did you mean: '{best_match}' ({score:.2f})?")
            elif suggestion['confidence'] < 0.5:
                normalized = suggestion['normalized']
                if normalized != part:
                    print(f"  📝 '{part}' → normalized: '{normalized}'")
        
        # # Show linked cards
        # if card.links:
        #     print("\nLinked cards:")
        #     for link_type, linked_concepts in card.links.items():
        #         if linked_concepts:
        #             print(f"  {link_type}: {', '.join(linked_concepts)}")
    
    def edit_incomplete_cards(self, domain_name: str = None):
        """Edit all incomplete cards, optionally filtered by domain"""
        incomplete = self.collection.get_incomplete_cards(domain_name)
        if not incomplete:
            if domain_name:
                print(f"All {domain_name} cards are complete!")
            else:
                print("All cards are complete!")
            return
        
        print(f"\nFound {len(incomplete)} incomplete cards.")
        print("Navigation: Use 'next' or 'prev' commands while editing to move between cards.")
        
        i = 0
        while 0 <= i < len(incomplete):
            print(f"\n[{i+1}/{len(incomplete)}]")
            self.navigation_action = None  # Reset navigation
            self.edit_card(incomplete[i].concept)
            
            # Check navigation action
            if self.navigation_action == 'next':
                i += 1
                if i >= len(incomplete):
                    print("\nReached the last incomplete card.")
                    i = len(incomplete) - 1
            elif self.navigation_action == 'prev':
                i -= 1
                if i < 0:
                    print("\nAlready at the first card.")
                    i = 0
            elif self.navigation_action == 'done':
                print("\nExiting editor.")
                break
            else:
                # No navigation command, ask to continue
                if i < len(incomplete) - 1:
                    cont = input("\nContinue to next card? (y/n): ").lower()
                    if cont == 'y':
                        i += 1
                    else:
                        break
                else:
                    print("\nCompleted all incomplete cards!")
                    break
    
    def create_missing_cards(self, domain_name: str = 'anatomy', max_cards: int = 10):
        """Create new cards based on orphaned references"""
        print(f"\n=== Creating Missing {domain_name.title()} Cards ===")
        
        suggestions = suggest_missing_cards(self.collection, domain_name)
        if not suggestions:
            print("No missing cards detected!")
            return
        
        print(f"Found {len(suggestions)} potential missing cards.")
        print(f"Showing top {min(max_cards, len(suggestions))}:\n")
        
        created_count = 0
        for i, suggestion in enumerate(suggestions[:max_cards]):
            concept = suggestion['concept']
            mentions = suggestion['mentions']
            referenced_by = suggestion['referenced_by']
            
            print(f"[{i+1}/{min(max_cards, len(suggestions))}] {concept}")
            print(f"  Referenced {mentions} times by: {', '.join(referenced_by[:3])}")
            if len(referenced_by) > 3:
                print(f"    ...and {len(referenced_by)-3} more cards")
            
            create = input(f"  Create card for '{concept}'? (y/n/s=skip rest): ").lower()
            
            if create == 's':
                break
            elif create == 'y':
                # Create the new card
                new_card = self.collection.create_card(concept, domain_name)
                print(f"  Created new {domain_name} card: {concept}")
                
                # Edit it immediately
                auto_edit = input("  Edit this card now? (y/n): ").lower()
                if auto_edit == 'y':
                    self.edit_card(concept)
                
                created_count += 1
            
            print()  # Empty line for readability
        
        print(f"\nCreated {created_count} new cards.")
        
        # Re-run auto-linking to connect new cards
        if created_count > 0:
            print("Re-running auto-linking to connect new cards...")
            self.collection._auto_link_cards()
    
    def show_orphan_analysis(self, domain_name: str = 'anatomy'):
        """Show analysis of missing/orphaned references"""
        print(f"\n=== Orphan Analysis for {domain_name.title()} ===")
        
        suggestions = suggest_missing_cards(self.collection, domain_name)
        if not suggestions:
            print("No orphaned references found!")
            return
        
        print(f"Found {len(suggestions)} potential missing cards:\n")
        
        for i, suggestion in enumerate(suggestions[:20]):  # Show top 20
            concept = suggestion['concept']
            mentions = suggestion['mentions']
            referenced_by = suggestion['referenced_by']
            
            print(f"{i+1:2d}. {concept} ({mentions} mentions)")
            print(f"     Referenced by: {', '.join(referenced_by)}")
        
        if len(suggestions) > 20:
            print(f"     ... and {len(suggestions)-20} more")
        
        print(f"\nUse editor.create_missing_cards() to create some of these cards.")

    def show_summary(self):
        """Show summary of the collection"""
        total = len(self.collection.cards)
        incomplete = len(self.collection.get_incomplete_cards())
        complete = total - incomplete
        
        print(f"\n=== Collection Summary ===")
        print(f"Total cards: {total}")
        print(f"Complete: {complete} ({complete/total*100:.1f}%)")
        print(f"Incomplete: {incomplete} ({incomplete/total*100:.1f}%)")
        
        # Show breakdown by domain
        print("\nBy domain:")
        for domain_name in self.collection.domains:
            domain_cards = self.collection.get_cards_by_domain(domain_name)
            if domain_cards:
                incomplete_in_domain = sum(1 for card in domain_cards if not card.is_complete())
                print(f"  {domain_name}: {len(domain_cards)} cards ({incomplete_in_domain} incomplete)")
        
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
                print(f"  {concept} ({card.domain.name}): {total_links} links")
