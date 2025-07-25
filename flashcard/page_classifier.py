from typing import List, Dict, Set, Tuple
import re


class WikipediaPageClassifier:
    """
    Classifies Wikipedia pages based on their categories and content.
    Helps filter for scientific/anatomical/biological concepts.
    """
    
    def __init__(self):
        # Scientific/medical category keywords to look for
        self.science_keywords = {
            # Anatomy & Biology
            'anatomy', 'anatomical', 'organ', 'organs', 'tissue', 'cell', 'cellular',
            'physiology', 'physiological', 'biological', 'biology', 'biomedicine',
            'medical', 'medicine', 'clinical', 'pathology', 'disease', 'disorder',
            'syndrome', 'symptom', 'diagnosis', 'treatment', 'therapy',
            
            # Body systems
            'nervous', 'cardiovascular', 'respiratory', 'digestive', 'endocrine',
            'immune', 'muscular', 'skeletal', 'integumentary', 'urinary', 'reproductive',
            'lymphatic', 'circulatory',
            
            # Neuroscience
            'neuroscience', 'neurological', 'neurology', 'brain', 'neural', 'neuron',
            'nerve', 'ganglion', 'plexus', 'cortex', 'cerebral',
            
            # Biochemistry
            'biochemistry', 'biochemical', 'protein', 'enzyme', 'hormone', 'receptor',
            'neurotransmitter', 'metabolism', 'metabolic', 'molecular',
            
            # Genetics
            'genetics', 'genetic', 'gene', 'chromosome', 'dna', 'rna', 'genome',
            
            # Pharmacology
            'pharmacology', 'pharmaceutical', 'drug', 'medication', 'pharmacological',
            
            # General science
            'science', 'scientific', 'research', 'study', 'theory', 'hypothesis',
            'experiment', 'laboratory', 'clinical'
        }
        
        # Keywords that suggest non-scientific content to avoid
        self.exclude_keywords = {
            # People & biography
            'biography', 'biographies', 'people', 'person', 'politician', 'artist',
            'actor', 'actress', 'musician', 'writer', 'author', 'poet', 'painter',
            'sculptor', 'filmmaker', 'director', 'producer', 'celebrity',
            'born', 'died', 'birth', 'death', 'nationality',
            
            # Geography & culture
            'country', 'countries', 'city', 'cities', 'town', 'village', 'state',
            'province', 'region', 'continent', 'geography', 'geographical',
            'culture', 'cultural', 'tradition', 'customs', 'language', 'dialect',
            'religion', 'religious', 'belief', 'mythology', 'folklore',
            
            # History & politics
            'history', 'historical', 'ancient', 'medieval', 'century', 'war',
            'battle', 'conflict', 'revolution', 'empire', 'dynasty', 'kingdom',
            'politics', 'political', 'government', 'election', 'party', 'democracy',
            'law', 'legal', 'legislation', 'constitution',
            
            # Entertainment & media
            'film', 'movie', 'television', 'tv', 'show', 'series', 'episode',
            'music', 'album', 'song', 'band', 'concert', 'tour',
            'book', 'novel', 'fiction', 'literature', 'poetry',
            'game', 'sport', 'team', 'player', 'championship', 'tournament',
            
            # Organizations & companies
            'company', 'companies', 'corporation', 'business', 'brand', 'product',
            'organization', 'institution', 'foundation', 'association', 'society',
            'university', 'college', 'school', 'academy'
        }
        
        # Special case patterns (regex)
        self.exclude_patterns = [
            r'\d{4} births',  # Birth year categories
            r'\d{4} deaths',  # Death year categories
            r'^\d{1,2}(st|nd|rd|th) century',  # Century categories
            r'living people',
            r'wikipedia:', # Meta pages
            r'portal:',
            r'category:',
            r'template:'
        ]
    
    def classify_page(self, categories: List[str], title: str = "", 
                     short_description: str = "", main_definition: str = "") -> Dict[str, any]:
        """
        Classify a Wikipedia page based on its categories and content.
        
        Returns:
            Dict with:
                - is_scientific: bool
                - confidence: float (0-1)
                - matched_science_keywords: set
                - matched_exclude_keywords: set
                - recommendation: str ('include', 'exclude', 'review')
        """
        
        # Normalize all inputs
        categories_lower = [cat.lower() for cat in categories]
        title_lower = title.lower()
        desc_lower = short_description.lower()
        def_lower = main_definition.lower()[:500]  # First 500 chars
        
        # Combine all text for analysis
        all_text = ' '.join(categories_lower + [title_lower, desc_lower, def_lower])
        
        # Check for exclusion patterns
        for pattern in self.exclude_patterns:
            if any(re.search(pattern, cat, re.IGNORECASE) for cat in categories):
                return {
                    'is_scientific': False,
                    'confidence': 0.9,
                    'matched_science_keywords': set(),
                    'matched_exclude_keywords': {pattern},
                    'recommendation': 'exclude',
                    'reason': f'Matched exclusion pattern: {pattern}'
                }
        
        # Count keyword matches
        science_matches = set()
        exclude_matches = set()
        
        for keyword in self.science_keywords:
            if keyword in all_text:
                science_matches.add(keyword)
        
        for keyword in self.exclude_keywords:
            if keyword in all_text:
                exclude_matches.add(keyword)
        
        # Calculate scores
        science_score = len(science_matches)
        exclude_score = len(exclude_matches) * 1.5  # Weight exclusions more heavily
        
        disambig = False
        if 'disambiguation' in title_lower:
            disambig = True
        
        # Determine classification
        if science_score > exclude_score and science_score >= 2:
            is_scientific = True
            confidence = min(science_score / 10, 1.0)
            recommendation = 'include' if confidence > 0.3 else 'review'
        elif exclude_score > science_score:
            is_scientific = False
            confidence = min(exclude_score / 10, 1.0)
            recommendation = 'exclude'
        elif disambig:
            is_scientific = False
            confidence = min(exclude_score / 10, 1.0)
            recommendation = 'exclude'
        else:
            # Ambiguous case
            is_scientific = science_score > 0
            confidence = 0.3
            recommendation = 'review'
        
        return {
            'is_scientific': is_scientific,
            'confidence': confidence,
            'matched_science_keywords': science_matches,
            'matched_exclude_keywords': exclude_matches,
            'recommendation': recommendation,
            'science_score': science_score,
            'exclude_score': exclude_score,
            'disambiguation':disambig
        }
    
    def should_include_page(self, classification: Dict) -> bool:
        """
        Simple decision function based on classification results.
        """
        return classification['recommendation'] == 'include'
    
    def get_classification_summary(self, classification: Dict) -> str:
        """
        Get a human-readable summary of the classification.
        """
        rec = classification['recommendation']
        conf = classification['confidence']
        
        if rec == 'include':
            return f"Scientific content (confidence: {conf:.1%})"
        elif rec == 'exclude':
            return f"Non-scientific content (confidence: {conf:.1%})"
        else:
            return f"Ambiguous - manual review needed (science: {classification['science_score']}, exclude: {classification['exclude_score']})"


def test_classifier():
    """Test the classifier with some example pages."""
    classifier = WikipediaPageClassifier()
    
    test_cases = [
        {
            'title': 'Spleen',
            'categories': ['Organs (anatomy)', 'Lymphatic system', 'Abdomen'],
            'short_description': 'Organ found in virtually all vertebrates',
            'main_definition': 'The spleen is an organ found in virtually all vertebrates.'
        },
        {
            'title': 'Barack Obama',
            'categories': ['1961 births', '21st-century American politicians', 'Presidents of the United States'],
            'short_description': '44th president of the United States',
            'main_definition': 'Barack Hussein Obama II is an American politician who served as the 44th president.'
        },
        {
            'title': 'Paris',
            'categories': ['Capital cities in Europe', 'Cities in France', 'Populated places in France'],
            'short_description': 'Capital and largest city of France',
            'main_definition': 'Paris is the capital and most populous city of France.'
        },
        {
            'title': 'DNA',
            'categories': ['Genetics', 'Molecular biology', 'Nucleic acids'],
            'short_description': 'Molecule that carries genetic information',
            'main_definition': 'Deoxyribonucleic acid is a molecule composed of two polynucleotide chains.'
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {test['title']}")
        print(f"Categories: {', '.join(test['categories'])}")
        
        result = classifier.classify_page(
            test['categories'],
            test['title'],
            test['short_description'],
            test['main_definition']
        )
        
        print(f"\nClassification: {classifier.get_classification_summary(result)}")
        print(f"Science keywords: {', '.join(result['matched_science_keywords']) or 'None'}")
        print(f"Exclude keywords: {', '.join(result['matched_exclude_keywords']) or 'None'}")
        print(f"Should include: {classifier.should_include_page(result)}")


if __name__ == "__main__":
    test_classifier()