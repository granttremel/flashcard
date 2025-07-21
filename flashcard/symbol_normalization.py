"""
Symbol normalization and validation system for consistent flashcard references.
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from difflib import SequenceMatcher

class SymbolNormalizer:
    """Handles normalization and validation of biological concept symbols."""
    
    def __init__(self):
        # Known abbreviations that should stay uppercase
        self.uppercase_abbreviations = {
            'DNA', 'RNA', 'ATP', 'ADP', 'GTP', 'GDP', 'cAMP', 'cGMP',
            'HIV', 'AIDS', 'MRI', 'CT', 'EEG', 'ECG', 'PCR', 'ELISA',
            'IgG', 'IgM', 'IgA', 'IgE', 'IgD', 'HLA', 'MHC', 'MHCI', 'MHCII',
            'WBC', 'RBC', 'CBC', 'ESR', 'CRP', 'TNF', 'IL', 'IFN',
            'CD', 'TCR', 'BCR', 'NK', 'NKC', 'APC', 'CFU', 'BFU',
            'AFP', 'PSA', 'CEA', 'CA', 'LDH', 'AST', 'ALT', 'GGT'
        }
        
        # Special mixed-case terms
        self.mixed_case_terms = {
            'panck': 'PanCK',
            'pancytokeratin': 'PanCK',
            'ph': 'pH',
            'mgso4': 'MgSO4',
            'nacl': 'NaCl',
            'koh': 'KOH',
            'h2o': 'H2O',
            'co2': 'CO2',
            'o2': 'O2',
            'n2': 'N2'
        }
        
        # Cell type suffixes that should be lowercase
        self.cell_suffixes = {'cell', 'cells', 'cyte', 'cytes', 'blast', 'blasts'}
        
        # Greek letters and special terms
        self.greek_mappings = {
            'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
            'epsilon': 'ε', 'theta': 'θ', 'lambda': 'λ', 'mu': 'μ',
            'sigma': 'σ', 'tau': 'τ', 'phi': 'φ', 'chi': 'χ', 'omega': 'ω'
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize a biological symbol for consistent representation.
        
        Rules:
        1. Known abbreviations stay uppercase (WBC, DNA, etc.)
        2. Special mixed-case terms use predefined format (PanCK, pH)
        3. Regular biological terms use title case (Basophil, T-cell)
        4. Handle hyphenated terms properly
        5. Remove excessive punctuation but preserve meaningful dashes
        """
        if not symbol or not isinstance(symbol, str):
            return symbol
        
        # Clean up the symbol
        cleaned = symbol.strip()
        if not cleaned:
            return cleaned
        
        # Remove excessive punctuation but preserve hyphens and important chars
        cleaned = re.sub(r'[^\w\s\-αβγδεθλμστφχω]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Check for exact mixed-case matches first
        if cleaned.lower() in self.mixed_case_terms:
            return self.mixed_case_terms[cleaned.lower()]
        
        # Split into words for processing
        words = cleaned.split()
        normalized_words = []
        
        for word in words:
            normalized_word = self._normalize_single_word(word)
            normalized_words.append(normalized_word)
        
        return ' '.join(normalized_words)
    
    def _normalize_single_word(self, word: str) -> str:
        """Normalize a single word according to biological conventions."""
        if not word:
            return word
        
        # Check if it's a known abbreviation
        if word.upper() in self.uppercase_abbreviations:
            return word.upper()
        
        # Check mixed-case terms
        if word.lower() in self.mixed_case_terms:
            return self.mixed_case_terms[word.lower()]
        
        # Handle hyphenated terms
        if '-' in word:
            parts = word.split('-')
            normalized_parts = [self._normalize_single_word(part) for part in parts]
            return '-'.join(normalized_parts)
        
        # Handle numbers and letters (like T4, CD8, IL-2)
        if re.match(r'^[A-Za-z]+\d+[A-Za-z]*$', word):
            # Letter(s) followed by number(s), possibly more letters
            match = re.match(r'^([A-Za-z]+)(\d+)([A-Za-z]*)$', word)
            if match:
                prefix, number, suffix = match.groups()
                if prefix.upper() in self.uppercase_abbreviations:
                    return prefix.upper() + number + suffix.lower()
                else:
                    return prefix.capitalize() + number + suffix.lower()
        
        # Handle cell types and similar
        if word.lower() in self.cell_suffixes:
            return word.lower()
        
        # Default to title case for regular biological terms
        return word.capitalize()
    
    def find_similar_symbols(self, symbol: str, existing_symbols: Set[str], 
                           threshold: float = 0.6) -> List[Tuple[str, float]]:
        """
        Find symbols that are similar to the given symbol.
        Returns list of (symbol, similarity_score) tuples.
        """
        if not symbol or not existing_symbols:
            return []
        
        normalized_input = self.normalize_symbol(symbol)
        similar = []
        
        for existing in existing_symbols:
            # Direct match (already handled elsewhere, but good to catch)
            if existing.lower() == normalized_input.lower():
                similar.append((existing, 1.0))
                continue
            
            # Calculate similarity
            similarity = SequenceMatcher(None, 
                                       normalized_input.lower(), 
                                       existing.lower()).ratio()
            
            if similarity >= threshold:
                similar.append((existing, similarity))
        
        # Sort by similarity score (highest first)
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar
    
    def suggest_normalization(self, symbol: str, existing_symbols: Set[str]) -> Dict[str, any]:
        """
        Suggest normalization for a symbol, considering existing symbols.
        
        Returns dict with:
        - 'normalized': The normalized version
        - 'exact_match': Existing symbol that matches exactly (if any)
        - 'similar': List of similar existing symbols
        - 'confidence': How confident we are in the normalization
        """
        if not symbol:
            return {'normalized': symbol, 'exact_match': None, 'similar': [], 'confidence': 0.0}
        
        normalized = self.normalize_symbol(symbol)
        
        # Check for exact matches (case-insensitive)
        exact_match = None
        for existing in existing_symbols:
            if existing.lower() == normalized.lower():
                exact_match = existing
                break
        
        # Find similar symbols
        similar = self.find_similar_symbols(symbol, existing_symbols, threshold=0.6)
        
        # Calculate confidence
        confidence = 1.0  # Start high
        if not exact_match:
            confidence *= 0.8  # Reduce if no exact match
        if len(similar) == 0:
            confidence *= 0.7  # Reduce if no similar symbols
        
        return {
            'normalized': normalized,
            'exact_match': exact_match,
            'similar': similar[:5],  # Top 5 similar
            'confidence': confidence
        }

def create_symbol_index(collection) -> Dict[str, Set[str]]:
    """Create an index of all symbols used in the collection."""
    symbol_index = {
        'concepts': set(collection.cards.keys()),
        'field_values': set(),
        'all_symbols': set()
    }
    
    # Add concept names
    symbol_index['all_symbols'].update(collection.cards.keys())
    
    # Add field values that look like symbols
    for card in collection.cards.values():
        for field_name, values in card.get_all_fields().items():
            for value in values:
                # Extract potential symbols from field values
                potential_symbols = extract_symbols_from_text(value)
                symbol_index['field_values'].update(potential_symbols)
                symbol_index['all_symbols'].update(potential_symbols)
    
    return symbol_index

def extract_symbols_from_text(text: str) -> Set[str]:
    """Extract potential biological symbols from text."""
    if not text:
        return set()
    
    symbols = set()
    
    # Split on common separators and extract short terms that might be symbols
    parts = re.split(r'[;,\n]+', text)
    
    for part in parts:
        part = part.strip()
        # Look for short terms that might be symbols (2-20 chars, contain letters)
        if 2 <= len(part) <= 20 and re.search(r'[a-zA-Z]', part):
            # Skip obvious descriptions
            if not any(word in part.lower() for word in ['the', 'and', 'or', 'in', 'of', 'to', 'for']):
                symbols.add(part)
    
    return symbols