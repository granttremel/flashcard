from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
import json
import pandas as pd


@dataclass
class DomainConfig:
    """Configuration for a concept domain defining its fields and link types"""
    name: str
    data_fields: List[str]  # Regular data fields
    link_types: List[str]   # Types of links this domain can have
    required_fields: List[str] = field(default_factory=list)  # Fields that must be filled
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'data_fields': self.data_fields,
            'link_types': self.link_types,
            'required_fields': self.required_fields
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DomainConfig':
        return cls(**data)


# Predefined configurations for different concept domains
ANATOMY_CONFIG = DomainConfig(
    name="anatomy",
    data_fields=[
        "Structure", "Function", "Metrics", "Anatomical Class", "AKA", "Wiki"
    ],
    link_types=[
        "Superstructure", "Substructure", "Superclass", "Subclass",
        "Localized with", "Develops from", "Related Pathology", "Involved in"
    ],
    required_fields=["Structure","Function"]
)

# PATHOLOGY_CONFIG = DomainConfig(
#     name="pathology",
#     data_fields=[
#         "Description", "Etiology", "Pathogenesis", "Clinical Features",
#         "Diagnosis", "Treatment", "Prognosis", "Complications"
#     ],
#     link_types=[
#         "affects_structure", "caused_by_process", "causes_process",
#         "differential_diagnosis", "risk_factor", "sequela"
#     ],
#     required_fields=["Description", "Etiology"]
# )

# PROCESS_CONFIG = DomainConfig(
#     name="process",
#     data_fields=[
#         "Description", "Steps", "Regulation", "Input", "Output", 
#         "Energy Requirements", "Location", "Duration"
#     ],
#     link_types=[
#         "subprocess", "superprocess", "regulated_by", "regulates",
#         "requires_structure", "produces_molecule", "consumes_molecule"
#     ],
#     required_fields=["Description"]
# )

