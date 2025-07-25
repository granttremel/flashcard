import urllib.parse
import webbrowser
from typing import Optional, Dict, List
import requests
import os
import json
from .wiki_parser import WikiParser
import re
import networkx as nx

class WikiPage:
    """
    Wikipedia page class similar to Paper class.
    Handles Wikipedia page identifiers and metadata.
    """
    
    _instances = {}
    
    def __init__(self, **kwargs):
        # Avoid re-initialization for singleton pattern
        if hasattr(self, '_initialized'):
            return
            
        # Use title as primary identifier (like DOI for papers)
        title = kwargs.get('title')
        page_id = kwargs.get('page_id')
        
        if title:
            self.title = title.replace(' ', '_')  # Wikipedia format
            self.canonical_title = title
        elif page_id:
            # Could fetch title from page_id if needed
            self.page_id = page_id
            self.title = f"PageID_{page_id}"
            self.canonical_title = self.title
        
        # Metadata
        self.page_id = kwargs.get('page_id', page_id)
        self.short_description = kwargs.get('short_description', '')
        self.main_definition = kwargs.get('main_definition', '')
        self.categories = kwargs.get('categories', [])
        self.internal_links = kwargs.get('internal_links', [])
        self.external_links = kwargs.get('external_links', [])
        self.images = kwargs.get('images', [])
        
        # Network metrics (similar to citation counts)
        self.in_links = kwargs.get('in_links', 0)      # Pages linking TO this page
        self.out_links = kwargs.get('out_links', 0)    # Pages this page links TO
        self.strength = kwargs.get('strength', 0.0)
        self.done = kwargs.get('done', False)
        
        # Classification
        self.is_scientific = kwargs.get('is_scientific', None)
        self.classification_confidence = kwargs.get('classification_confidence', 0.0)
        
        # DOIs extracted from external links
        self.extracted_dois = kwargs.get('extracted_dois', [])
        
        self._initialized = True
    
    def __new__(cls, **kwargs):
        # Singleton pattern like Paper class
        title = kwargs.get('title')
        page_id = kwargs.get('page_id')
        identifier = title or f"PageID_{page_id}"
        
        if identifier in cls._instances:
            return cls._instances[identifier]
        
        instance = super().__new__(cls)
        cls._instances[identifier] = instance
        return instance
    
    def get_id(self) -> str:
        """Get the page identifier (title)."""
        return self.title
    
    def get_page_id(self) -> Optional[int]:
        """Get the numeric page ID."""
        return self.page_id
    
    def set_strength(self, val: float):
        """Set page strength/priority."""
        self.strength = val
    
    def set_done(self):
        """Mark page as processed."""
        self.done = True
    
    def extract_dois_from_external_links(self) -> List[str]:
        """
        Extract DOIs from external links.
        This is the key bridge between Wikipedia and citation networks!
        """
        dois = []
        doi_pattern = re.compile(r'(?:doi\.org/|doi:|DOI:)\s*(10\.\d{4,}/[^\s<>\]]+)', re.IGNORECASE)
        
        for link in self.external_links:
            # Handle different link formats
            url = link if isinstance(link, str) else link.get('url', '')
            
            # Look for DOI patterns in URL
            matches = doi_pattern.findall(url)
            for match in matches:
                # Clean up the DOI
                clean_doi = match.strip('.,;)]}>')
                if clean_doi and clean_doi not in dois:
                    dois.append(clean_doi)
        
        self.extracted_dois = dois
        return dois
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            'title': self.title,
            'canonical_title': self.canonical_title,
            'page_id': self.page_id,
            'short_description': self.short_description,
            'main_definition': self.main_definition,
            'categories': self.categories,
            'internal_links': self.internal_links,
            'external_links': self.external_links,
            'images': self.images,
            'in_links': self.in_links,
            'out_links': self.out_links,
            'strength': self.strength,
            'done': self.done,
            'is_scientific': self.is_scientific,
            'classification_confidence': self.classification_confidence,
            'extracted_dois': self.extracted_dois
        }
    
    def __str__(self):
        return f"WikiPage({self.title})"
    
    def __repr__(self):
        return str(self)
    
    def __hash__(self):
        return hash(self.title)


class WikiLink:
    """
    Wikipedia link class similar to Citation class.
    Represents connections between Wikipedia pages.
    """
    
    _instances = {}
    
    def __init__(self, source_page: str, target_page: str, link_type: str = "internal"):
        self.source_page = source_page  # Page that contains the link
        self.target_page = target_page  # Page being linked to
        self.link_type = link_type      # "internal", "external", "category", etc.
        self.link_id = f"{source_page}->{target_page}"
    
    def get_id(self):
        return self.link_id
    
    @classmethod
    def __new__(cls, source_page: str, target_page: str, link_type: str = "internal"):
        link_id = f"{source_page}->{target_page}"
        
        if link_id in cls._instances:
            return cls._instances[link_id]
        
        instance = super().__new__(cls)
        cls._instances[link_id] = instance
        return instance
    
    def __str__(self):
        return f"WikiLink({self.source_page} -> {self.target_page})"
    
    def __repr__(self):
        return str(self)
    
    def __hash__(self):
        return hash(self.link_id)



class WikiManager:
    
    api_endpoint = r"https://en.wikipedia.org/w/api.php"
    hdrs = {'user_agent': 'granttool/0.1 (grant.tremel@proton.me)'}

    max_chain = 10

    api_options = {
        "action":("parse","query",),
        "page":None,
        "titles":None,
        "prop":("title","extract","categories","info","links","extlinks"),
        "format":("json","none","xml")
    }

    local_path = './data/wiki/{page}.json'
    
    def __init__(self):
        
        self.parser = WikiParser()
        
    def build_api_request(self, **options):
    
        optstrs = []
        
        frm = "{k}={v}"
        
        for opt, defvals in self.api_options.items():
            if opt in options:
                optval = options[opt]
                if not defvals or optval in defvals:
                    if isinstance(optval, list) or isinstance(optval, tuple):
                        optval = '|'.join(optval)
                    optstrs.append(frm.format(k = opt, v = optval))
                elif optval:
                    optstrs.append(frm.format(k = opt, v = defvals[0]))
                else:
                    pass
                    
        optstr = '&'.join(optstrs)
        
        return '?'.join((self.api_endpoint, optstr))

    def fetch_wikipedia_pages(self, titles, prop = None, save_local = True, overwrite = False):
        action = "query"
        format = "json"
        
        check = []
        if titles:
            check.extend(titles)
        data = {}
        do_pages = []
        for page in check:
            loc_pth = self.local_path.format(page=page)
            if os.path.exists(loc_pth) and not overwrite:
                self.parser.load_from_file(loc_pth)
                dat = self.parser.extract_all()
                data[page] = dat
            else:
                do_pages.append(page)
        
        if not prop:
            prop = self.api_options["prop"]
        else:
            prop = [p for p in prop if p in self.api_options["prop"]]
        
        # For bulk queries, we need to use 'titles' parameter and specific props
        opts = dict(
            action=action, 
            titles='|'.join(do_pages),  # Use 'titles' (plural) for bulk requests
            prop='|'.join(prop),  # What data to retrieve
            exintro=True,  # Get intro section
            explaintext=True,  # Plain text instead of HTML
            cllimit="max",  # Get all categories
            format=format
        )
        
        req = self.build_api_request(**opts)
        print(f"API Request: {req}")
        res = requests.get(req, headers=self.hdrs)
        
        if res.status_code != 200:
            print(f"HTTP Error: {res.status_code}")
            return data
        
        try:
            js = res.json()
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response text: {res.text[:500]}")
            return data
        
        # Process query response format and convert to parse-like format for compatibility
        if 'query' in js and 'pages' in js['query']:
            for page_id, page_data in js['query']['pages'].items():
                if page_id == '-1':  # Page doesn't exist
                    print(f"Page not found: {page_data.get('title', 'Unknown')}")
                    continue
                
                page_title = page_data.get('title', '')
                normalized_title = page_title.replace(' ', '_')
                
                # Convert to parse-like format for compatibility with existing parser
                converted_data = self._create_trimmed_data(page_data)
                
                
                data[normalized_title] = converted_data
                
                if save_local:
                    loc_pth = self.local_path.format(page=normalized_title)
                    with open(loc_pth, 'w') as f:
                        json.dump(converted_data, f, indent=3)
                    print(f"Saved {page_title} to: {loc_pth}")
        else:
            print(f"Unexpected API response format: {js}")
        
        return data
        
        
    def fetch_wikipedia_page(self, page_name: str, save_local: bool = True, overwrite: bool = False):
        """Fetch a Wikipedia page and optionally save it locally"""
        action = "parse"
        format = "json"
        
        loc_pth = self.local_path.format(page=page_name)
        if os.path.exists(loc_pth) and not overwrite:
            self.parser.load_from_file(loc_pth)
            data = self.parser.extract_all()
            return data
        
        req = self.build_api_request(page=page_name, action=action, format=format)
        res = requests.get(req, headers=self.hdrs)
        
        js = dict(res.json())
        # Apply trimming to reduce file size
        js = self._trim_parse_data(js)
        if save_local:
            loc_pth = self.local_path.format(page=page_name)
            with open(loc_pth, 'w') as f:
                json.dump(js, f, indent=3)
            print(f"Saved to: {loc_pth}")
        
        return js
    
    def _create_trimmed_data(self, page_data):
        """Create trimmed data structure from query response."""
        page_title = page_data.get('title', '')
        page_id = page_data.get('pageid', 0)
        
        # Extract categories (remove namespace info)
        categories = []
        if 'categories' in page_data:
            categories = [cat.get('title', '').replace('Category:', '') 
                         for cat in page_data['categories']]
        
        # Create minimal data structure
        return {
            'parse': {
                'title': page_title,
                'pageid': int(page_id),
                'text': {
                    '*': f'<p>{page_data.get("extract", "")}</p>'
                }
            },
            'categories': categories,
            'extract': page_data.get('extract', ''),
            'pageimage': page_data.get('pageimage', ''),
            'ns': page_data.get('ns', 0)
        }
    
    def _trim_parse_data(self, data):
        """Trim unnecessary data from parse API response."""
        if 'parse' not in data:
            return data
        
        parse_data = data['parse']
        
        # Keep only essential fields
        trimmed = {
            'parse': {
                'title': parse_data.get('title', ''),
                'pageid': parse_data.get('pageid', 0),
                'text': parse_data.get('text', {'*': ''}),
                'links': parse_data.get('links', []),  # Limit to first 50 links
                'categories': parse_data.get('categories', []),
                'externallinks': parse_data.get('externallinks',[])
            }
        }
        
        # Extract internal links if present
        if 'links' in parse_data:
            internal_links = []
            for link in parse_data['links'][:50]:  # Limit links
                if isinstance(link, dict) and '*' in link:
                    title = link['*']
                    # Skip namespace pages and special pages
                    if ':' not in title or title.startswith('Category:'):
                        internal_links.append(title)
            trimmed['internal_links'] = internal_links
        
        # Extract categories in clean format
        if 'categories' in parse_data:
            categories = []
            for cat in parse_data['categories']:
                if isinstance(cat, dict) and '*' in cat:
                    cat_name = cat['*'].replace('Category:', '')
                    categories.append(cat_name)
            trimmed['categories'] = categories
        
        return trimmed

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

    def generate_wikipedia_url(self, concept: str, search: bool = False, format_title: bool = True) -> str:
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
                article_name = self.format_wikipedia_title(cleaned)
            else:
                article_name = cleaned.replace(" ", "_")
            return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(article_name)}"

    def open_wikipedia_page(self, concept: str, search: bool = False) -> None:
        """
        Open Wikipedia page for a concept in the default browser.
        
        Args:
            concept: The concept name to look up
            search: If True, opens search results instead of direct article
        """
        url = self.generate_wikipedia_url(concept, search)
        webbrowser.open(url)

    def format_wikipedia_field(url: str) -> str:
        """
        Format a Wikipedia URL for storage in the Wiki field.
        """
        return url
    
    def view_page_in_browser(self, page_name: str, browser="firefox") -> bool:
        """
        Open a Wikipedia page's HTML content in the browser.
        
        Args:
            page_name: Name of the Wikipedia page (without .json extension)
            browser: Browser command to use (default: "firefox")
        
        Returns:
            True if successful, False otherwise
        """
        import tempfile
        import subprocess
        import os
        
        # Check if JSON file exists
        json_path = self.local_path.format(page=page_name)
        if not os.path.exists(json_path):
            print(f"JSON file not found: {json_path}")
            return False
        
        try:
            # Load and parse the JSON file
            self.parser.load_from_file(json_path)
            
            # Try to get HTML content from different possible locations
            html_content = None
            
            # Try to access the raw JSON data first
            with open(json_path, 'r') as f:
                import json
                data = json.load(f)
            
            # Look for HTML content in different locations
            if 'parse' in data and 'text' in data['parse'] and '*' in data['parse']['text']:
                html_content = data['parse']['text']['*']
            elif 'query_data' in data and 'extract' in data['query_data']:
                # For query-based data, create basic HTML
                extract = data['query_data']['extract']
                title = data['query_data'].get('title', page_name)
                html_content = f"""
                <div class="mw-content-ltr mw-parser-output">
                    <h1>{title}</h1>
                    <p>{extract}</p>
                </div>
                """
            
            if not html_content:
                print(f"No HTML content found in {page_name}")
                return False
            
            # Create complete HTML document with Wikipedia-like styling
            full_html = self._create_full_html_document(html_content, page_name)
            
            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8', dir = './data/tmp') as tmp_file:
                tmp_file.write(full_html)
                tmp_path = tmp_file.name
            
            print(f"Created temporary HTML file: {tmp_path}")
            print(f"Opening {page_name} in {browser}...")
            
            # Open in browser
            subprocess.run([browser, tmp_path], check=False)
            
            return True
            
        except Exception as e:
            print(f"Error opening {page_name} in browser: {e}")
            return False
    
    def _create_full_html_document(self, content: str, title: str) -> str:
        """Create a complete HTML document with Wikipedia-like styling."""
        
        # Basic Wikipedia-like CSS styling
        css_styles = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Lato, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #202122;
                background-color: #ffffff;
                margin: 0;
                padding: 20px;
                max-width: 1000px;
                margin: 0 auto;
            }
            
            .mw-content-ltr {
                direction: ltr;
            }
            
            .mw-parser-output {
                margin: 0;
            }
            
            h1, h2, h3, h4, h5, h6 {
                color: #000;
                font-weight: normal;
                margin: 1em 0 0.5em 0;
                border-bottom: 1px solid #a2a9b1;
                padding-bottom: 0.25em;
            }
            
            h1 {
                font-size: 2.5em;
                font-weight: normal;
                border-bottom: 3px solid #a2a9b1;
            }
            
            h2 {
                font-size: 1.8em;
            }
            
            h3 {
                font-size: 1.4em;
            }
            
            p {
                margin: 1em 0;
            }
            
            a {
                color: #0645ad;
                text-decoration: none;
            }
            
            a:hover {
                text-decoration: underline;
            }
            
            .infobox {
                border: 1px solid #a2a9b1;
                border-spacing: 3px;
                background-color: #f8f9fa;
                color: #202122;
                margin: 0.5em 0 0.5em 1em;
                padding: 0.2em;
                float: right;
                clear: right;
                font-size: 88%;
                line-height: 1.5em;
                width: 22em;
            }
            
            .infobox-above {
                text-align: center;
                font-size: 125%;
                font-weight: bold;
            }
            
            figure {
                margin: 1em 0;
                text-align: center;
            }
            
            figcaption {
                font-size: 0.9em;
                color: #555;
                margin-top: 0.5em;
            }
            
            img {
                max-width: 100%;
                height: auto;
            }
            
            .shortdescription {
                display: none;
            }
            
            .hatnote {
                font-style: italic;
                padding: 5px 7px;
                color: #555;
                border-left: 3px solid #36c;
                margin-bottom: 1em;
                background-color: #f8f9fa;
            }
            
            .reference {
                font-size: 0.8em;
                vertical-align: super;
            }
            
            .cite-bracket {
                color: #555;
            }
            
            ul, ol {
                margin: 1em 0;
                padding-left: 2em;
            }
            
            li {
                margin: 0.3em 0;
            }
            
            table {
                border-collapse: collapse;
                margin: 1em 0;
            }
            
            th, td {
                border: 1px solid #a2a9b1;
                padding: 0.3em 0.5em;
            }
            
            th {
                background-color: #eaecf0;
                font-weight: bold;
            }
            
            .navigation-not-searchable {
                background-color: #f8f9fa;
                border: 1px solid #a2a9b1;
                padding: 3px 5px;
                font-size: 0.9em;
            }
        </style>
        """
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title} - Wikipedia</title>
            {css_styles}
        </head>
        <body>
            <div class="wikipedia-content">
                {content}
            </div>
            <footer style="margin-top: 3em; padding-top: 1em; border-top: 1px solid #a2a9b1; font-size: 0.8em; color: #555;">
                <p>Content extracted from Wikipedia page: <strong>{title}</strong></p>
                <p>Generated by WikiManager for flashcard study purposes</p>
            </footer>
        </body>
        </html>
        """