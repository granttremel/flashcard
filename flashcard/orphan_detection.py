"""
Orphan detection system for finding missing flashcards that should be created.
"""

from typing import Set, List, Dict, Tuple
from collections import Counter
import re

def find_orphaned_references(collection, min_mentions: int = 2) -> Dict[str, List[str]]:
    """
    Find references in card data that don't have corresponding cards.
    
    Args:
        collection: FlashcardCollection to analyze
        min_mentions: Minimum number of times a reference must appear to be considered
    
    Returns:
        Dict mapping orphaned concept names to list of cards that reference them
    """
    all_references = {}  # concept -> list of cards mentioning it
    
    for card_name, card in collection.cards.items():
        for field_name, values in card.get_all_fields().items():
            # Skip certain fields that are unlikely to contain card references
            if field_name.lower() in ['wiki', 'aka', 'metrics', 'function', 'structure']:
                continue
                
            for value in values:
                # Extract potential concept references
                refs = extract_concept_references(value)
                for ref in refs:
                    if ref not in collection.cards:  # It's orphaned
                        if ref not in all_references:
                            all_references[ref] = []
                        all_references[ref].append(card_name)
    
    # Filter by minimum mentions and clean up
    filtered_orphans = {}
    for concept, mentioning_cards in all_references.items():
        if len(mentioning_cards) >= min_mentions and is_valid_concept_name(concept):
            filtered_orphans[concept] = mentioning_cards
    
    return filtered_orphans

def extract_concept_references(text: str) -> Set[str]:
    """
    Extract potential concept names from a text field.
    """
    refs = set()
    
    # Split on common separators
    parts = re.split(r'[;,\n]+', text)
    
    for part in parts:
        # Clean up the part
        clean_part = part.strip()
        
        # Skip very short or very long strings
        if len(clean_part) < 3 or len(clean_part) > 50:
            continue
            
        # Skip strings that look like descriptions rather than concept names
        if any(word in clean_part.lower() for word in ['cells', 'process', 'function', 'role', 'part', 'located', 'contains']):
            # But allow some specific patterns that might still be concept names
            if not any(pattern in clean_part.lower() for pattern in ['cell', 'nerve', 'blood', 'tissue', 'organ']):
                continue
        
        # Clean up common prefixes/suffixes
        clean_part = clean_part.strip('()[]{}.,!?')
        
        if clean_part and is_valid_concept_name(clean_part):
            refs.add(clean_part)
    
    return refs

def is_valid_concept_name(name: str) -> bool:
    """
    Check if a string looks like a valid biological concept name.
    """
    name = name.strip()
    
    # Skip very generic words
    generic_words = {
        'and', 'or', 'the', 'of', 'in', 'to', 'for', 'with', 'by', 'from', 
        'blood', 'cells', 'tissue', 'organ', 'system', 'part', 'area',
        'function', 'role', 'process', 'structure', 'feature'
    }
    
    if name.lower() in generic_words:
        return False
    
    # Skip strings with too many common English words
    words = name.split()
    if len(words) > 1:
        common_count = sum(1 for word in words if word.lower() in generic_words)
        if common_count > len(words) * 0.5:  # More than half are common words
            return False
    
    # Skip strings that are clearly descriptions
    description_patterns = [
        r'\b(contains|located|found|responsible|involved|plays|helps|allows|enables)\b',
        r'\b(which|that|where|when|how)\b',
        r'\b(very|most|some|all|many)\b'
    ]
    
    for pattern in description_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return False
    
    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', name):
        return False
    
    return True

def suggest_missing_cards(collection, domain_name: str = 'anatomy') -> List[Dict[str, any]]:
    """
    Suggest new cards that should be created based on orphaned references.
    
    Returns list of dicts with 'concept', 'mentions', 'referenced_by', 'suggested_domain'
    """
    orphans = find_orphaned_references(collection, min_mentions=2)
    
    suggestions = []
    for concept, mentioning_cards in orphans.items():
        suggestion = {
            'concept': concept,
            'mentions': len(mentioning_cards),
            'referenced_by': mentioning_cards,
            'suggested_domain': domain_name  # Could be smarter about this
        }
        suggestions.append(suggestion)
    
    # Sort by number of mentions (most referenced first)
    suggestions.sort(key=lambda x: x['mentions'], reverse=True)
    
    return suggestions