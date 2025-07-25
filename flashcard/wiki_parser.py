from bs4 import BeautifulSoup
import re
from typing import Dict, List, Tuple, Optional
import json


class WikiParser:
    def __init__(self):
        self.soup = None
        self.data = None
    
    def load_from_file(self, filepath: str) -> None:
        with open(filepath, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
            if 'parse' in self.data and 'text' in self.data['parse']:
                html_content = self.data['parse']['text']['*']
                self.soup = BeautifulSoup(html_content, 'html.parser')
    
    def load_from_json(self, json_data: Dict) -> None:
        self.data = json_data
        if 'parse' in self.data and 'text' in self.data['parse']:
            html_content = self.data['parse']['text']['*']
            self.soup = BeautifulSoup(html_content, 'html.parser')
    
    def get_title(self) -> str:
        if self.data and 'parse' in self.data:
            return self.data['parse'].get('title', '')
        return ''
    
    def get_page_id(self) -> int:
        if self.data and 'parse' in self.data:
            return self.data['parse'].get('pageid', 0)
        return 0
    
    def get_short_description(self) -> str:
        if not self.soup:
            return ''
        
        short_desc = self.soup.find('div', class_='shortdescription')
        if short_desc:
            return short_desc.get_text(strip=True)
        return ''
    
    def get_main_definition(self) -> str:
        if not self.soup:
            return ''
        
        # Get the first paragraph after any images/figures
        paragraphs = self.soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Skip empty paragraphs and meta content
            if text and not text.startswith('Coordinates:'):
                # Clean up the text
                text = re.sub(r'\[\d+\]', '', text)  # Remove reference numbers
                text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                return text
        return ''
    
    def get_sections(self) -> Dict[str, str]:
        if not self.soup:
            return {}
        
        sections = {}
        current_section = "Introduction"
        current_content = []
        
        for element in self.soup.find_all(['h2', 'h3', 'p', 'ul', 'ol']):
            if element.name in ['h2', 'h3']:
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                heading_text = element.get_text(strip=True)
                # Remove [edit] links
                current_section = re.sub(r'\[edit\]', '', heading_text).strip()
                current_content = []
            
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text and not text.startswith('Coordinates:'):
                    # Clean references
                    text = re.sub(r'\[\d+\]', '', text)
                    text = re.sub(r'\s+', ' ', text)
                    current_content.append(text)
            
            elif element.name in ['ul', 'ol']:
                # Extract list items
                items = []
                for li in element.find_all('li', recursive=False):
                    item_text = li.get_text(strip=True)
                    item_text = re.sub(r'\[\d+\]', '', item_text)
                    item_text = re.sub(r'\s+', ' ', item_text)
                    items.append(f"• {item_text}")
                if items:
                    current_content.append('\n'.join(items))
        
        # Don't forget the last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def get_internal_links(self) -> List[Tuple[str, str]]:
        if not self.soup:
            return []
        
        links = []
        seen = set()
        
        # Find all internal wiki links
        for link in self.soup.find_all('a', href=True):
            href = link['href']
            # Filter for internal wiki links
            if href.startswith('/wiki/') and ':' not in href:
                title = link.get('title', '')
                text = link.get_text(strip=True)
                
                # Extract page name from URL
                page_name = href.replace('/wiki/', '')
                
                # Avoid duplicates
                if page_name not in seen and page_name:
                    seen.add(page_name)
                    links.append((page_name, title or text))
        
        return links
    
    def get_language_links(self) -> Dict[str, str]:
        if not self.data or 'parse' not in self.data:
            return {}
        
        lang_links = {}
        if 'langlinks' in self.data['parse']:
            for link in self.data['parse']['langlinks']:
                lang_code = link.get('lang', '')
                translation = link.get('*', '')
                if lang_code and translation:
                    lang_links[lang_code] = translation
        
        return lang_links
    
    def get_categories(self) -> List[str]:
        if not self.soup:
            return []
        
        categories = []
        # Categories are usually in links with href starting with /wiki/Category:
        for link in self.soup.find_all('a', href=re.compile(r'^/wiki/Category:')):
            category = link.get_text(strip=True)
            if category:
                categories.append(category)
        
        return categories
    
    def get_images(self) -> List[Dict[str, str]]:
        if not self.soup:
            return []
        
        images = []
        for img in self.soup.find_all('img'):
            img_data = {
                'src': img.get('src', ''),
                'alt': img.get('alt', ''),
                'width': img.get('width', ''),
                'height': img.get('height', '')
            }
            
            # Check if image has a caption
            parent = img.find_parent('figure')
            if parent:
                caption = parent.find('figcaption')
                if caption:
                    img_data['caption'] = caption.get_text(strip=True)
            
            images.append(img_data)
        
        return images
    
    def extract_all(self) -> Dict:
        return {
            'title': self.get_title(),
            'page_id': self.get_page_id(),
            'short_description': self.get_short_description(),
            'main_definition': self.get_main_definition(),
            'sections': self.get_sections(),
            'internal_links': self.get_internal_links(),
            # 'language_links': self.get_language_links(),
            'categories': self.get_categories(),
            'images': self.get_images()
        }


def test_parser():
    parser = WikiParser()
    parser.load_from_file('./data/wiki/Spleen.json')
    
    data = parser.extract_all()
    
    print(f"Title: {data['title']}")
    print(f"Page ID: {data['page_id']}")
    print(f"\nShort Description: {data['short_description']}")
    print(f"\nMain Definition: {data['main_definition'][:200]}...")
    
    print(f"\nSections found: {len(data['sections'])}")
    for section_name in list(data['sections'].keys())[:3]:
        print(f"  - {section_name}")
    
    print(f"\nInternal links found: {len(data['internal_links'])}")
    for link, title in data['internal_links'][:5]:
        print(f"  - {link}: {title}")
    
    print(f"\nLanguage translations: {len(data['language_links'])}")
    for lang, translation in list(data['language_links'].items())[:5]:
        print(f"  - {lang}: {translation}")
    
    print(f"\nCategories: {len(data['categories'])}")
    print(f"Images: {len(data['images'])}")


if __name__ == "__main__":
    test_parser()