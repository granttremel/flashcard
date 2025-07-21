#!/usr/bin/env python3

from flashcard.wikipedia import generate_wikipedia_url, format_wikipedia_title

# Test Wikipedia URL generation
test_concepts = [
    "lymph node medulla",
    "Brain",
    "Autonomic Nervous system", 
    "Red blood cell",
    "T-cell",
    "DNA polymerase",
    "Adenosine triphosphate",
    "Central nervous system",
    "Heart of the matter",  # Test preposition handling
    "B-cell receptor"      # Test hyphenated words
]

print("Testing Wikipedia URL generation with proper formatting:\n")
for concept in test_concepts:
    formatted_title = format_wikipedia_title(concept)
    direct_url = generate_wikipedia_url(concept, search=False)
    search_url = generate_wikipedia_url(concept, search=True)
    
    print(f"Concept: {concept}")
    print(f"  Formatted: {formatted_title}")
    print(f"  Direct: {direct_url}")
    print(f"  Search: {search_url}")
    print()