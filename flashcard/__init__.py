import pandas as pd
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Flashcard:
    """Represents a single flashcard with multiple fields and linkages"""
    concept: str
    fields: Dict[str, List[str]] = field(default_factory=dict)
    links: Dict[str, Set[str]] = field(default_factory=dict)  # link_type -> set of linked concepts
    
    def add_field(self, field_name: str, values: str):
        """Add field values, splitting by semicolon"""
        if pd.isna(values) or values == '':
            self.fields[field_name] = []
        else:
            self.fields[field_name] = [v.strip() for v in str(values).split(';') if v.strip()]
    
    def add_link(self, link_type: str, target_concept: str):
        """Add a link to another concept"""
        if link_type not in self.links:
            self.links[link_type] = set()
        self.links[link_type].add(target_concept)
    
    def get_field_values(self, field_name: str) -> List[str]:
        """Get all values for a specific field"""
        return self.fields.get(field_name, [])
    
    def is_complete(self) -> bool:
        """Check if all fields have at least one value"""
        return all(len(values) > 0 for values in self.fields.values())
    
    def get_incomplete_fields(self) -> List[str]:
        """Return list of fields that are empty"""
        return [field for field, values in self.fields.items() if len(values) == 0]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'concept': self.concept,
            'fields': self.fields,
            'links': {k: list(v) for k, v in self.links.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Flashcard':
        """Create from dictionary"""
        card = cls(concept=data['concept'])
        card.fields = data['fields']
        card.links = {k: set(v) for k, v in data.get('links', {}).items()}
        return card

    def __str__(self):
        
        fd = self.to_dict()
        topstr = f'Concept: {self.concept}'
        outstrs = [topstr]
        
        for ff in self.fields:
            fielditems = '; '.join(self.fields[ff])
            outstrs.append(f'{ff}: {fielditems}')
            print(f'did {ff}')
        return '\n\t'.join(outstrs)
        
class FlashcardCollection:
    """Manages a collection of flashcards with automatic linking"""
    
    def __init__(self):
        self.cards: Dict[str, Flashcard] = {}
        self.field_names: Set[str] = set()
        self.link_types: Set[str] = {'Superstructure', 'Superclass', 'Substructure', 'Subclass','Link'}
    
    def load_from_excel(self, filepath: str, sheet_name: Optional[str] = None):
        """Load flashcards from Excel/ODS file"""
        
        dfs = pd.read_excel(filepath, sheet_name=sheet_name)

        if sheet_name:
            df = dfs
        else:
            sns = list(dfs.keys())
            sheet_name = sns[0]
            df = dfs[sheet_name]
            print(f"no sheet name provided, defaulting to {sheet_name} out of {sns}")
            
        # Store field names (column headers)
        self.field_names = set(df.columns)
        
        # Create flashcards from rows
        for _, row in df.iterrows():
            # Assume first column is the concept name
            concept_name = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else None
            if not concept_name:
                continue
                
            card = Flashcard(concept=concept_name)
            
            # Add all fields
            for col in df.columns:
                card.add_field(col, row[col])
            
            self.cards[concept_name] = card
        
        # Auto-link cards based on shared symbols
        self._auto_link_cards()
    
    def _auto_link_cards(self):
        """Automatically create links between cards based on shared symbols"""
        # First, build an index of all symbols to concepts
        symbol_to_concepts: Dict[str, Set[str]] = {}
        
        for concept, card in self.cards.items():
            # Check each field for potential symbols
            for field_name, values in card.fields.items():
                # Look for link-type fields
                if any(link_type in field_name.lower() for link_type in self.link_types):
                    for value in values:
                        if value in self.cards:  # If the value is another concept
                            # Determine link type from field name
                            for link_type in self.link_types:
                                if link_type in field_name.lower():
                                    card.add_link(link_type, value)
                                    # Add reverse link
                                    reverse_type = self._get_reverse_link_type(link_type)
                                    if reverse_type:
                                        self.cards[value].add_link(reverse_type, concept)
    
    def _get_reverse_link_type(self, link_type: str) -> Optional[str]:
        """Get the reverse link type"""
        reverse_map = {
            'superstructure': 'substructure',
            'substructure': 'superstructure',
            'superclass': 'subclass',
            'subclass': 'superclass'
        }
        return reverse_map.get(link_type)
    
    def get_card(self, concept: str) -> Optional[Flashcard]:
        """Get a specific flashcard by concept"""
        return self.cards.get(concept)
    
    def get_incomplete_cards(self) -> List[Flashcard]:
        """Get all cards with incomplete information"""
        return [card for card in self.cards.values() if not card.is_complete()]
    
    def get_linked_cards(self, concept: str, link_type: Optional[str] = None) -> Dict[str, Set[str]]:
        """Get all cards linked to a specific concept"""
        card = self.get_card(concept)
        if not card:
            return {}
        
        if link_type:
            return {link_type: card.links.get(link_type, set())}
        return dict(card.links)
    
    def save_to_json(self, filepath: str):
        """Save collection to JSON file"""
        data = {
            'cards': {concept: card.to_dict() for concept, card in self.cards.items()},
            'field_names': list(self.field_names),
            'link_types': list(self.link_types)
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_json(self, filepath: str):
        """Load collection from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.field_names = set(data['field_names'])
        self.link_types = set(data['link_types'])
        self.cards = {
            concept: Flashcard.from_dict(card_data) 
            for concept, card_data in data['cards'].items()
        }
