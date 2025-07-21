#!/usr/bin/env python3

from flashcard import FlashcardCollection
from collections import defaultdict, Counter

def main():
    # Load the collection
    print("Loading flashcard collection...")
    collection = FlashcardCollection()
    collection.load_from_excel("./data/flashcards.ods", domain_name="anatomy", sheet_name="anatomy")
    
    print(f"Loaded {len(collection.cards)} cards\n")
    
    # Analyze linking
    print("=== LINK ANALYSIS ===")
    
    # Count cards with links
    cards_with_links = 0
    total_links = 0
    link_types = Counter()
    
    for concept, card in collection.cards.items():
        card_links = sum(len(links) for links in card.links.values() if links)
        if card_links > 0:
            cards_with_links += 1
            total_links += card_links
            for link_type, targets in card.links.items():
                if targets:
                    link_types[link_type] += len(targets)
    
    print(f"Cards with links: {cards_with_links}/{len(collection.cards)} ({cards_with_links/len(collection.cards)*100:.1f}%)")
    print(f"Total links: {total_links}")
    
    if link_types:
        print("\\nLink types:")
        for link_type, count in link_types.most_common():
            print(f"  {link_type}: {count}")
    
    # Show some example cards with their fields
    print("\\n=== SAMPLE CARD FIELDS ===")
    sample_cards = list(collection.cards.values())[:3]
    
    for card in sample_cards:
        print(f"\\n{card.concept}:")
        print(f"  Domain: {card.domain.name}")
        for field, values in card.get_all_fields().items():
            if values:
                print(f"  {field}: {'; '.join(values)}")
        
        # Show expected link fields
        print("  Expected link fields:")
        for link_type in card.domain.link_types:
            if link_type in card.links and card.links[link_type]:
                print(f"    {link_type}: {'; '.join(card.links[link_type])}")
            else:
                print(f"    {link_type}: [EMPTY]")
    
    # Look for orphaned references
    print("\\n=== ORPHANED REFERENCES ===")
    all_references = set()
    
    for card in collection.cards.values():
        for field_name, values in card.get_all_fields().items():
            # Look for potential concept references in field values
            for value in values:
                # Split on common separators and clean up
                refs = [ref.strip() for ref in value.replace(';', ',').split(',')]
                for ref in refs:
                    if ref and len(ref) > 2:  # Skip very short strings
                        all_references.add(ref)
    
    # Find references that don't have corresponding cards
    orphaned = all_references - set(collection.cards.keys())
    print(f"Found {len(orphaned)} potential orphaned references")
    
    if orphaned:
        print("\\nSample orphaned references:")
        for ref in list(orphaned)[:10]:
            print(f"  '{ref}'")

if __name__ == "__main__":
    main()