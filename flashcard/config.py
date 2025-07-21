from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
import json
import pandas as pd


@dataclass
class ConceptFamilyConfig:
    """Configuration for a concept family defining its fields and link types"""
    name: str
    data_fields: List[str]  # Regular data fields
    link_types: List[str]   # Types of links this family can have
    required_fields: List[str] = field(default_factory=list)  # Fields that must be filled
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'data_fields': self.data_fields,
            'link_types': self.link_types,
            'required_fields': self.required_fields
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConceptFamilyConfig':
        return cls(**data)


# Predefined configurations for different concept families
ANATOMY_CONFIG = ConceptFamilyConfig(
    name="anatomy",
    data_fields=[
        "Description", "Develops From", "Localization", 
        "Innervation", "Blood Supply", "Metrics"
    ],
    link_types=[
        "superstructure", "substructure", "superclass", "subclass",
        "spatial_neighbor", "related_pathology", "participates_in_process"
    ],
    required_fields=["Description"]
)

PATHOLOGY_CONFIG = ConceptFamilyConfig(
    name="pathology",
    data_fields=[
        "Description", "Etiology", "Pathogenesis", "Clinical Features",
        "Diagnosis", "Treatment", "Prognosis", "Complications"
    ],
    link_types=[
        "affects_structure", "caused_by_process", "causes_process",
        "differential_diagnosis", "risk_factor", "sequela"
    ],
    required_fields=["Description", "Etiology"]
)

PROCESS_CONFIG = ConceptFamilyConfig(
    name="process",
    data_fields=[
        "Description", "Steps", "Regulation", "Input", "Output", 
        "Energy Requirements", "Location", "Duration"
    ],
    link_types=[
        "subprocess", "superprocess", "regulated_by", "regulates",
        "requires_structure", "produces_molecule", "consumes_molecule"
    ],
    required_fields=["Description"]
)


class FlexibleFlashcard:
    """A flashcard that can adapt to different concept families"""
    
    def __init__(self, concept: str, family: ConceptFamilyConfig):
        self.concept = concept
        self.family = family
        self.data: Dict[str, List[str]] = {field: [] for field in family.data_fields}
        self.links: Dict[str, Set[str]] = {link_type: set() for link_type in family.link_types}
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
        for field in self.family.required_fields:
            if not self.data.get(field, []):
                return False
        return True
    
    def get_all_fields(self) -> Dict[str, List[str]]:
        """Get both standard and custom fields"""
        return {**self.data, **self.custom_fields}
    
    def to_dict(self) -> dict:
        return {
            'concept': self.concept,
            'family': self.family.name,
            'data': self.data,
            'custom_fields': self.custom_fields,
            'links': {k: list(v) for k, v in self.links.items()}
        }
