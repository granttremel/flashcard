import heapq
import json
import os
import time
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
import pickle

from .wikipedia import WikiManager
from .wiki_parser import WikiParser
from .page_classifier import WikipediaPageClassifier


class IntelligentWikiCrawler:
    """
    Intelligent Wikipedia crawler that builds networks by prioritizing 
    links based on reference frequency and scientific relevance.
    """
    
    def __init__(self, filter_scientific=True, data_dir="./data/wiki", 
                 crawler_state_file="./data/crawler_state.pkl"):
        self.wiki_manager = WikiManager()
        self.parser = WikiParser()
        self.classifier = WikipediaPageClassifier() if filter_scientific else None
        self.filter_scientific = filter_scientific
        
        self.data_dir = data_dir
        self.crawler_state_file = crawler_state_file
        
        # Crawler state
        self.link_references = Counter()  # Count how many times each link appears
        self.processed_pages = set()      # Pages we've already crawled
        self.priority_queue = []          # Min-heap: (-priority, page_name)
        self.current_depth = 0
        self.max_depth = 3
        self.max_pages = 1000
        
        # Statistics
        self.stats = {
            'pages_processed': 0,
            'pages_skipped': 0,
            'scientific_pages': 0,
            'non_scientific_pages': 0,
            'total_links_found': 0,
            'start_time': None,
            'last_save_time': None
        }
        
        # Load previous state if it exists
        self.load_state()
    
    def add_seed_pages(self, seed_pages: List[str]):
        """Add initial seed pages to start crawling from."""
        for page in seed_pages:
            if page not in self.processed_pages:
                # Add with high priority (negative number for min-heap)
                heapq.heappush(self.priority_queue, (-1000, page, 0))  # (priority, page, depth)
                print(f"Added seed page: {page}")
    
    def calculate_priority(self, page_name: str, current_depth: int) -> float:
        """
        Calculate priority for a page based on reference count and depth.
        Higher reference count = higher priority
        Lower depth = higher priority
        """
        reference_count = self.link_references.get(page_name, 0)
        depth_penalty = current_depth * 10
        
        # Priority = reference_count - depth_penalty
        # We use negative for min-heap (higher priority = more negative)
        priority = reference_count - depth_penalty
        return -priority  # Negative for min-heap
    
    def crawl_page(self, page_name: str, depth: int) -> Optional[Dict]:
        """
        Crawl a single Wikipedia page and extract its data.
        
        Returns:
            Dict with page data if successful and scientific (if filtering enabled)
            None if page should be skipped
        """
        print(f"\n[Depth {depth}] Crawling: {page_name}")
        
        # Check if we already have this page locally
        local_path = os.path.join(self.data_dir, f"{page_name}.json")
        
        # Rate limiting
        time.sleep(1.1)  # Be respectful to Wikipedia's servers
        
        try:
            # Fetch the page
            page_data = self.wiki_manager.fetch_wikipedia_page(page_name, save_local=True)
            
            # Parse the page
            self.parser.load_from_json(page_data)
            extracted_data = self.parser.extract_all()
            
            # Apply scientific filtering if enabled
            if self.filter_scientific and self.classifier:
                classification = self.classifier.classify_page(
                    extracted_data.get('categories', []),
                    extracted_data.get('title', ''),
                    extracted_data.get('short_description', ''),
                    extracted_data.get('main_definition', '')
                )
                
                if not self.classifier.should_include_page(classification):
                    print(f"  SKIPPED (non-scientific): {self.classifier.get_classification_summary(classification)}")
                    self.stats['non_scientific_pages'] += 1
                    self.stats['pages_skipped'] += 1
                    return None
                else:
                    print(f"  INCLUDED: {self.classifier.get_classification_summary(classification)}")
                    self.stats['scientific_pages'] += 1
            
            # Update link reference counts
            internal_links = extracted_data.get('internal_links', [])
            for link_data in internal_links:
                if isinstance(link_data, tuple):
                    link_name = link_data[0]  # (page_name, title) format
                else:
                    link_name = link_data
                
                # Skip special pages
                if ':' not in link_name:
                    self.link_references[link_name] += 1
            
            self.stats['total_links_found'] += len(internal_links)
            self.stats['pages_processed'] += 1
            
            # Add new links to priority queue if we haven't reached max depth
            if depth < self.max_depth:
                new_links_added = 0
                for link_data in internal_links[:20]:  # Limit to top 20 links per page
                    if isinstance(link_data, tuple):
                        link_name = link_data[0]
                    else:
                        link_name = link_data
                    
                    # Skip if already processed or in queue or is special page
                    if (link_name not in self.processed_pages and 
                        ':' not in link_name and
                        not any(item[1] == link_name for item in self.priority_queue)):
                        
                        priority = self.calculate_priority(link_name, depth + 1)
                        heapq.heappush(self.priority_queue, (priority, link_name, depth + 1))
                        new_links_added += 1
                
                print(f"  Added {new_links_added} new links to queue")
            
            return extracted_data
            
        except Exception as e:
            print(f"  ERROR crawling {page_name}: {e}")
            self.stats['pages_skipped'] += 1
            return None
    
    def crawl_continuously(self, max_pages: int = None, max_time_hours: float = None):
        """
        Continuously crawl Wikipedia pages until limits are reached.
        
        Args:
            max_pages: Maximum number of pages to process
            max_time_hours: Maximum time to run in hours
        """
        if max_pages:
            self.max_pages = max_pages
        
        if not self.stats['start_time']:
            self.stats['start_time'] = time.time()
        
        max_time_seconds = max_time_hours * 3600 if max_time_hours else float('inf')
        
        print(f"\n{'='*60}")
        print(f"STARTING INTELLIGENT WIKIPEDIA CRAWLER")
        print(f"{'='*60}")
        print(f"Max pages: {self.max_pages}")
        print(f"Max depth: {self.max_depth}")
        print(f"Scientific filtering: {self.filter_scientific}")
        print(f"Queue size: {len(self.priority_queue)}")
        print(f"Already processed: {len(self.processed_pages)}")
        
        try:
            while (self.priority_queue and 
                   self.stats['pages_processed'] < self.max_pages and
                   (time.time() - self.stats['start_time']) < max_time_seconds):
                
                # Get highest priority page
                priority, page_name, depth = heapq.heappop(self.priority_queue)
                
                # Skip if already processed
                if page_name in self.processed_pages:
                    continue
                
                # Crawl the page
                page_data = self.crawl_page(page_name, depth)
                self.processed_pages.add(page_name)
                
                # Save state periodically
                if self.stats['pages_processed'] % 10 == 0:
                    self.save_state()
                    self.print_stats()
                
                # Show top referenced links periodically
                if self.stats['pages_processed'] % 25 == 0:
                    self.print_top_references()
        
        except KeyboardInterrupt:
            print("\n\nCrawling interrupted by user. Saving state...")
        
        # Final save and stats
        self.save_state()
        self.print_final_stats()
    
    def print_stats(self):
        """Print current crawling statistics."""
        elapsed = time.time() - self.stats['start_time']
        pages_per_minute = (self.stats['pages_processed'] / elapsed) * 60 if elapsed > 0 else 0
        
        print(f"\n--- CRAWLER STATS ---")
        print(f"Pages processed: {self.stats['pages_processed']}")
        print(f"Scientific pages: {self.stats['scientific_pages']}")
        print(f"Non-scientific skipped: {self.stats['non_scientific_pages']}")
        print(f"Queue size: {len(self.priority_queue)}")
        print(f"Unique links found: {len(self.link_references)}")
        print(f"Processing rate: {pages_per_minute:.1f} pages/min")
        print(f"Elapsed time: {elapsed/60:.1f} minutes")
    
    def print_top_references(self, top_n: int = 10):
        """Print the most frequently referenced pages."""
        if not self.link_references:
            return
            
        print(f"\n--- TOP {top_n} MOST REFERENCED PAGES ---")
        for page, count in self.link_references.most_common(top_n):
            status = "✓ Processed" if page in self.processed_pages else "⏳ Pending"
            print(f"  {count:3d} refs: {page} ({status})")
    
    def print_final_stats(self):
        """Print final crawling statistics."""
        elapsed = time.time() - self.stats['start_time']
        
        print(f"\n{'='*60}")
        print(f"CRAWLING COMPLETE")
        print(f"{'='*60}")
        print(f"Total pages processed: {self.stats['pages_processed']}")
        print(f"Scientific pages included: {self.stats['scientific_pages']}")
        print(f"Non-scientific pages skipped: {self.stats['non_scientific_pages']}")
        print(f"Total runtime: {elapsed/60:.1f} minutes")
        print(f"Average rate: {(self.stats['pages_processed']/elapsed)*60:.1f} pages/min")
        print(f"Unique links discovered: {len(self.link_references)}")
        print(f"Remaining in queue: {len(self.priority_queue)}")
        
        # Show top referenced pages
        self.print_top_references(15)
    
    def save_state(self):
        """Save crawler state to disk for resuming later."""
        state = {
            'link_references': dict(self.link_references),
            'processed_pages': list(self.processed_pages),
            'priority_queue': self.priority_queue,
            'current_depth': self.current_depth,
            'max_depth': self.max_depth,
            'max_pages': self.max_pages,
            'stats': self.stats,
            'filter_scientific': self.filter_scientific
        }
        
        with open(self.crawler_state_file, 'wb') as f:
            pickle.dump(state, f)
        
        self.stats['last_save_time'] = time.time()
        print(f"  State saved to {self.crawler_state_file}")
    
    def load_state(self):
        """Load previous crawler state if it exists."""
        if os.path.exists(self.crawler_state_file):
            try:
                with open(self.crawler_state_file, 'rb') as f:
                    state = pickle.load(f)
                
                self.link_references = Counter(state.get('link_references', {}))
                self.processed_pages = set(state.get('processed_pages', []))
                self.priority_queue = state.get('priority_queue', [])
                self.current_depth = state.get('current_depth', 0)
                self.max_depth = state.get('max_depth', 3)
                self.max_pages = state.get('max_pages', 1000)
                self.stats = state.get('stats', self.stats)
                self.filter_scientific = state.get('filter_scientific', True)
                
                print(f"Loaded previous crawler state:")
                print(f"  - {len(self.processed_pages)} pages already processed")
                print(f"  - {len(self.priority_queue)} pages in queue")
                print(f"  - {len(self.link_references)} unique links discovered")
                
            except Exception as e:
                print(f"Error loading crawler state: {e}")
                print("Starting fresh...")
    
    def get_network_data(self) -> Dict:
        """
        Generate network data from crawled pages.
        
        Returns:
            Dict in the same format as WikiNet.build_flashcard_network()
        """
        flashcards = {}
        connections = []
        
        for page_name in self.processed_pages:
            local_path = os.path.join(self.data_dir, f"{page_name}.json")
            
            if os.path.exists(local_path):
                try:
                    self.parser.load_from_file(local_path)
                    data = self.parser.extract_all()
                    
                    # Create flashcard entry
                    flashcard = {
                        'term': data.get('title', page_name),
                        'definition': data.get('short_description', '') or data.get('main_definition', '')[:200],
                        'full_definition': data.get('main_definition', ''),
                        'depth': 0,  # Could track actual depth if needed
                        'related_concepts': [],
                        'categories': data.get('categories', []),
                        'reference_count': self.link_references.get(page_name, 0)
                    }
                    
                    # Add internal links as related concepts
                    internal_links = data.get('internal_links', [])
                    for link_data in internal_links[:10]:  # Limit related concepts
                        if isinstance(link_data, tuple):
                            link_name = link_data[0]
                        else:
                            link_name = link_data
                        
                        if link_name in self.processed_pages:
                            flashcard['related_concepts'].append(link_name)
                            connections.append({
                                'from': page_name,
                                'to': link_name,
                                'type': 'related_concept'
                            })
                    
                    flashcards[page_name] = flashcard
                    
                except Exception as e:
                    print(f"Error processing {page_name} for network: {e}")
        
        return {
            'flashcards': flashcards,
            'connections': connections,
            'crawler_stats': self.stats,
            'link_references': dict(self.link_references.most_common(100))
        }


def test_crawler():
    """Test the intelligent crawler."""
    crawler = IntelligentWikiCrawler(
        filter_scientific=True,
        data_dir="./data/wiki",
        crawler_state_file="./data/test_crawler_state.pkl"
    )
    
    # Add some seed pages
    seed_pages = [
        "Autonomic_nervous_system",
        "Human_anatomy", 
        "Physiology"
    ]
    
    crawler.add_seed_pages(seed_pages)
    
    # Crawl for a limited time/pages for testing
    crawler.crawl_continuously(max_pages=20, max_time_hours=0.1)  # 6 minutes max
    
    # Generate network data
    network = crawler.get_network_data()
    print(f"\nGenerated network with {len(network['flashcards'])} flashcards")
    print(f"and {len(network['connections'])} connections")


if __name__ == "__main__":
    test_crawler()