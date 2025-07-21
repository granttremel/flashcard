import urllib.parse
import webbrowser
from typing import Optional

def format_wikipedia_title(concept: str) -> str:
    """
    Format a concept name according to Wikipedia's title conventions.
    Generally: First word capitalized, rest lowercase, with some exceptions.
    """
    words = concept.strip().split()
    if not words:
        return concept
    
    # Common words that should stay uppercase
    keep_upper = {'DNA', 'RNA', 'ATP', 'ADP', 'GTP', 'GDP', 'cAMP', 'pH', 'HIV', 'AIDS', 'MRI', 'CT', 'EEG', 'ECG'}
    
    # Format each word
    formatted_words = []
    for i, word in enumerate(words):
        # Keep acronyms and specific terms uppercase
        if word.upper() in keep_upper:
            formatted_words.append(word.upper())
        # First word is capitalized
        elif i == 0:
            formatted_words.append(word.capitalize())
        # Prepositions and articles typically lowercase
        elif word.lower() in {'of', 'in', 'the', 'and', 'or', 'with', 'to', 'a', 'an'}:
            formatted_words.append(word.lower())
        # Words after dash are capitalized
        elif '-' in word:
            parts = word.split('-')
            formatted_parts = [p.capitalize() for p in parts]
            formatted_words.append('-'.join(formatted_parts))
        else:
            formatted_words.append(word.lower())
    
    return '_'.join(formatted_words)

def generate_wikipedia_url(concept: str, search: bool = False, format_title: bool = True) -> str:
    """
    Generate a Wikipedia URL for a concept.
    
    Args:
        concept: The concept name to look up
        search: If True, generates a search URL instead of direct article URL
        format_title: If True, formats the title according to Wikipedia conventions
    
    Returns:
        Wikipedia URL string
    """
    # Clean up the concept name
    cleaned = concept.strip()
    
    if search:
        # Generate search URL
        base_url = "https://en.wikipedia.org/w/index.php"
        params = {"search": cleaned}
        return f"{base_url}?{urllib.parse.urlencode(params)}"
    else:
        # Generate direct article URL
        if format_title:
            article_name = format_wikipedia_title(cleaned)
        else:
            article_name = cleaned.replace(" ", "_")
        return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(article_name)}"

def open_wikipedia_page(concept: str, search: bool = False) -> None:
    """
    Open Wikipedia page for a concept in the default browser.
    
    Args:
        concept: The concept name to look up
        search: If True, opens search results instead of direct article
    """
    url = generate_wikipedia_url(concept, search)
    webbrowser.open(url)

def format_wikipedia_field(url: str) -> str:
    """
    Format a Wikipedia URL for storage in the Wiki field.
    """
    return url