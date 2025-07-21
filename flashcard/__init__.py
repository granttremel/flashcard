import pandas as pd
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from .config import DomainConfig, ANATOMY_CONFIG
from .symbol_normalization import SymbolNormalizer, create_symbol_index

class Flashcard:
    
    def __init__(self, concept: str, domain: DomainConfig):
        self.concept = concept
        self.domain = domain
        self.data: Dict[str, List[str]] = {field: [] for field in domain.data_fields}
        self.links: Dict[str, Set[str]] = {link_type: set() for link_type in domain.link_types}
        self.custom_fields: Dict[str, List[str]] = {}  # For ad-hoc fields
        
    def add_field(self, field_name: str, values: str):
        """Add values to a field (standard or custom)"""
        if pd.isna(values) or values == '':
            return
            
        value_list = [v.strip() for v in str(values).split(';') if v.strip()]
        
        if field_name in self.data:
            self.data[field_name] = value_list
        else:
            # Handle as custom field
            self.custom_fields[field_name] = value_list
    
    def add_link(self, link_type: str, target_concept: str):
        """Add a link of specified type"""
        if link_type not in self.links:
            # Allow custom link types too
            self.links[link_type] = set()
        self.links[link_type].add(target_concept)
    
    def is_complete(self) -> bool:
        """Check if all required fields are filled"""
        for field in self.domain.required_fields:
            if not self.data.get(field, []):
                return False
        return True
    
    def get_incomplete_fields(self) -> List[str]:
        """Get list of required fields that are not filled"""
        incomplete = []
        for field in self.domain.required_fields:
            if not self.data.get(field, []):
                incomplete.append(field)
        return incomplete
    
    def get_all_fields(self) -> Dict[str, List[str]]:
        """Get both standard and custom fields"""
        return {**self.data, **self.custom_fields}
    
    def to_dict(self) -> dict:
        return {
            'concept': self.concept,
            'domain': self.domain.name,
            'data': self.data,
            'custom_fields': self.custom_fields,
            'links': {k: list(v) for k, v in self.links.items()}
        }

    def __str__(self):
        
        fd = self.to_dict()
        topstr = f'Concept: {self.concept}'
        outstrs = [topstr]
        
        dcts = [self.data, self.links, self.custom_fields]
        
        for dct in dcts:
            for ff in dct:
                vv = dct[ff]
                if len(vv) > 0:
                    fielditems = '; '.join(vv)
                    outstrs.append(f'{ff}: {fielditems}')

        return '\n\t'.join(outstrs)
    
    
        
class FlashcardCollection:
    """Collection that can handle multiple concept domains"""
    
    def __init__(self):
        self.cards: Dict[str, Flashcard] = {}
        self.domains: Dict[str, DomainConfig] = {
            'anatomy': ANATOMY_CONFIG,
            # 'pathology': PATHOLOGY_CONFIG,
            # 'process': PROCESS_CONFIG
        }
        self.domain_members: Dict[str, Set[str]] = {name: set() for name in self.domains}
        self.symbol_normalizer = SymbolNormalizer()
        self.symbol_index = None  # Will be populated after loading
    
    def add_domain(self, config: DomainConfig):
        """Add a new concept domain configuration"""
        self.domains[config.name] = config
        self.domain_members[config.name] = set()
    
    def create_card(self, concept: str, domain_name: str) -> Flashcard:
        """Create a new card of specified domain"""
        if domain_name not in self.domains:
            raise ValueError(f"Unknown domain: {domain_name}")
            
        card = Flashcard(concept, self.domains[domain_name])
        self.cards[concept] = card
        self.domain_members[domain_name].add(concept)
        return card
    
    def get_card(self, concept: str) -> Optional[Flashcard]:
        """Get a card by concept name"""
        return self.cards.get(concept)
    
    
    def load_from_excel(self, filepath: str, domain_name: str, sheet_name: Optional[str] = None):
        """Load cards from Excel, treating them as specified domain"""
        if domain_name not in self.domains:
            raise ValueError(f"Unknown domain: {domain_name}")
            
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        domain_config = self.domains[domain_name]
        
        for _, row in df.iterrows():
            concept_name = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else None
            if not concept_name:
                continue
                
            card = self.create_card(concept_name, domain_name)
            
            # Add all fields from the spreadsheet
            for col in df.columns:
                card.add_field(col, row[col])
        
        # Create symbol index and auto-link after loading
        self.symbol_index = create_symbol_index(self)
        self._auto_link_cards()
    
    def _auto_link_cards(self):
        """Create links based on field values and names"""
        print("Auto-linking cards...")
        
        for concept, card in self.cards.items():
            # Check all fields for potential links
            for field_name, values in card.get_all_fields().items():
                field_lower = field_name.lower().replace(' ', '').replace('_', '')
                
                # Create mapping from field names to link types
                link_mappings = {
                    'superstructure': 'Superstructure',
                    'superstructures': 'Superstructure', 
                    'substructure': 'Substructure',
                    'substructures': 'Substructure',
                    'superclass': 'Superclass',
                    'subclass': 'Subclass',
                    'localizedwith': 'Localized with',
                    'developsfrom': 'Develops from',
                    'relatedpathology': 'Related Pathology',
                    'relatedpathologies': 'Related Pathology',
                    'involvedin': 'Involved in',
                    'patholog': 'Related Pathology',  # Catch variations
                    'process': 'Involved in'
                }
                
                # Check if this field maps to a known link type
                for pattern, link_type in link_mappings.items():
                    if pattern in field_lower:
                        # Add links for each value that matches an existing card
                        for value in values:
                            linked = self._try_link_value(card, link_type, value, concept)
                            if not linked:
                                # Try with symbol normalization
                                suggestion = self.symbol_normalizer.suggest_normalization(
                                    value, set(self.cards.keys())
                                )
                                if suggestion['exact_match']:
                                    card.add_link(link_type, suggestion['exact_match'])
                                    print(f"  Linked {concept} --{link_type}--> {suggestion['exact_match']} (normalized)")
                                elif suggestion['similar'] and suggestion['similar'][0][1] > 0.8:
                                    # High confidence match
                                    best_match = suggestion['similar'][0][0]
                                    card.add_link(link_type, best_match)
                                    print(f"  Linked {concept} --{link_type}--> {best_match} (fuzzy: {suggestion['similar'][0][1]:.2f})")
                        break  # Only match first pattern to avoid duplicates
        
        # Print summary
        total_links = sum(len(links) for card in self.cards.values() for links in card.links.values())
        print(f"Auto-linking complete. Created {total_links} total links.")
    
    def _try_link_value(self, card, link_type: str, value: str, concept: str) -> bool:
        """Try to link a value to an existing card. Returns True if successful."""
        clean_value = value.strip()
        
        # Try exact match first
        if clean_value in self.cards:
            card.add_link(link_type, clean_value)
            print(f"  Linked {concept} --{link_type}--> {clean_value}")
            return True
        
        # Try case-insensitive match
        for card_name in self.cards.keys():
            if card_name.lower() == clean_value.lower():
                card.add_link(link_type, card_name)
                print(f"  Linked {concept} --{link_type}--> {card_name} (case-insensitive)")
                return True
        
        return False
    
    def get_cards_by_domain(self, domain_name: str) -> List[Flashcard]:
        """Get all cards of a specific domain"""
        return [self.cards[concept] for concept in self.domain_members.get(domain_name, set())]
    
    def get_incomplete_cards(self, domain_name: str = None) -> List[Flashcard]:
        """Get all incomplete cards, optionally filtered by domain"""
        if domain_name:
            cards = self.get_cards_by_domain(domain_name)
        else:
            cards = list(self.cards.values())
        return [card for card in cards if not card.is_complete()]
    
    def get_cross_domain_links(self, concept: str) -> Dict[str, List[tuple]]:
        """Get all links that cross domain boundaries"""
        card = self.cards.get(concept)
        if not card:
            return {}
        
        cross_links = {}
        for link_type, targets in card.links.items():
            for target in targets:
                target_card = self.cards.get(target)
                if target_card and target_card.domain.name != card.domain.name:
                    if link_type not in cross_links:
                        cross_links[link_type] = []
                    cross_links[link_type].append((target, target_card.domain.name))
        
        return cross_links
    
    def suggest_links(self, concept: str) -> Dict[str, List[str]]:
        """Suggest potential links based on patterns"""
        suggestions = {}
        card = self.cards.get(concept)
        if not card:
            return suggestions
        
        # Example: if this is an anatomy card, suggest pathologies that might affect it
        if card.domain.name == 'anatomy':
            pathology_cards = self.get_cards_by_domain('pathology')
            for path_card in pathology_cards:
                # Check if pathology mentions this structure
                for field_values in path_card.get_all_fields().values():
                    for value in field_values:
                        if concept.lower() in value.lower():
                            suggestions.setdefault('potential_pathology', []).append(path_card.concept)
        
        return suggestions
