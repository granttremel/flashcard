import pandas as pd
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from .config import DomainConfig, ANATOMY_CONFIG

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
        
        # Auto-link after loading
        self._auto_link_cards()
    
    def _auto_link_cards(self):
        """Create cross-domain links based on field values"""
        for concept, card in self.cards.items():
            # Check all fields for potential links
            for field_name, values in card.get_all_fields().items():
                # Look for link-type indicators in field names
                field_lower = field_name.lower()
                
                # Cross-domain linking rules
                if 'patholog' in field_lower:
                    for value in values:
                        if value in self.cards:
                            card.add_link('related_pathology', value)
                            self.cards[value].add_link('pathology_of', concept)
                
                elif 'process' in field_lower or 'participates' in field_lower:
                    for value in values:
                        if value in self.cards:
                            card.add_link('participates_in_process', value)
                            self.cards[value].add_link('has_participant', concept)
                
                # Standard within-domain links
                for link_type in card.links:
                    if link_type in field_lower:
                        for value in values:
                            if value in self.cards:
                                card.add_link(link_type, value)
    
    def get_cards_by_domain(self, domain_name: str) -> List[Flashcard]:
        """Get all cards of a specific domain"""
        return [self.cards[concept] for concept in self.domain_members.get(domain_name, set())]
    
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
