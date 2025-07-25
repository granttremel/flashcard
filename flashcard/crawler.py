#!/usr/bin/env python3

import heapq
import json
import os
import time
import pickle
import requests
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
import re
from datetime import datetime

# Import the existing components
from .wikipedia import WikiManager, WikiPage, WikiLink
from .citations import CiteManager, CrossRefManager, Paper, Citation
from .knowledge_database import UnifiedDatabase


class Crawler:
    """
    High-performance citation crawler with optimized database operations,
    batch processing, and reduced I/O overhead.
    """
    
    def __init__(self, wiki_manager: WikiManager,knowledge_database: UnifiedDatabase,  cite_manager: CiteManager = None, crossref_manager: CrossRefManager = None,
                 state_file: str = "./data/unified/crawler_state.pkl"):
        self.wiki_manager = wiki_manager
        self.cite_manager = cite_manager
        self.crossref_manager = crossref_manager or CrossRefManager()
        self.db = knowledge_database
        self.state_file = state_file
        
        # Network graph (kept in memory for analysis)
        # self.G = nx.DiGraph()
        #Wiki<->Wiki: WikiLink
        #Paper<->Paper: Citation
        #Wiki<->Paper: CrossNetworkConnection
        
        # State tracking (now database-backed)
        self.processed_paper_ids = set()   # Track IDs we've fully processed
        self.priority_queue = []           # Min-heap: (-priority, paper_id, paper)
        self.paper_references = Counter()  # Reference counting for priority
        
        # Batch processing for performance
        self.pending_papers = []           # Papers to insert in next batch
        self.pending_citations = []        # Citations to insert in next batch
        self.pending_updates = []          # Metadata updates to apply
        self.metadata_queue = []
        
        # Crawler settings
        self.max_depth = 3
        self.max_papers = 1000
        self.current_depth = 0
        
        # Batch processing settings
        self.paper_batch_size = 50         # Insert papers in batches of 50
        self.citation_batch_size = 100     # Insert citations in batches of 100
        self.crossref_batch_size = 20      # Fetch metadata for 20 papers at once
        self.state_save_frequency = 50     # Save state every 50 papers (not 10)
        
        # Statistics
        self.stats = {
            'papers_processed': 0,
            'citations_found': 0,
            'api_requests': 0,
            'crossref_requests': 0,
            'database_batches': 0,
            'start_time': None,
            'last_save_time': None,
            'last_crossref_batch': None
        }
        
        # Load previous state if it exists
        self.load_state()
    
    def add_seed_papers(self, seed_papers: List['Paper']):
        """Add initial seed papers to start crawling from."""
        paper_data_list = []
        
        for paper in seed_papers:
            paper_id = paper.get_id()
            
            # Prepare paper data for batch insertion
            paper_data = self._paper_to_dict(paper)
            paper_data_list.append(paper_data)
            
            if paper_id not in self.processed_paper_ids:
                # Add with high priority (negative for min-heap)
                priority = self.calculate_priority(paper, 0)
                heapq.heappush(self.priority_queue, (priority, paper_id, paper))
                print(f"Added seed paper: {paper}")
        
        # Batch insert all seed papers
        if paper_data_list:
            self.db.insert_paper_batch(paper_data_list)
            self.stats['database_batches'] += 1
    
    def _paper_to_dict(self, paper: 'Paper') -> Dict:
        """Convert Paper object to dictionary for database storage."""
        data = {
            'nciting': getattr(paper, 'nciting', 0),
            'ncited': getattr(paper, 'ncited', 0),
            'strength': getattr(paper, 'strength', 0.0),
            'done': getattr(paper, 'done', False)
        }
        
        # Add all identifiers
        for id_type in paper.idtypes:
            if hasattr(paper, id_type):
                data[id_type] = getattr(paper, id_type)
        
        # Add metadata if available
        if hasattr(paper, 'title') and paper.title:
            data['title'] = paper.title
        if hasattr(paper, 'authors') and paper.authors:
            data['authors'] = paper.authors
        if hasattr(paper, 'issued_timestamp') and paper.issued_timestamp:
            data['issued_timestamp'] = paper.issued_timestamp
            
        return data
    
    def calculate_priority(self, paper: 'Paper', depth: int) -> float:
        """Calculate priority for a paper."""
        reference_count = self.paper_references.get(paper.get_id(), 0)
        citation_count = getattr(paper, 'nciting', 0) + getattr(paper, 'ncited', 0)
        is_wiki = isinstance(paper, WikiPage)
        # Priority = references + citations - depth_penalty
        # Use negative for min-heap (higher priority = more negative)
        priority = reference_count + citation_count - (depth * 50)
        return -priority
    
    def crawl_paper(self, paper: 'Paper', depth: int) -> bool:
        """
        Crawl a single paper to get its citations and references.
        This version focuses on speed and batches database operations.
        """
        print(f"\\n[Depth {depth}] Crawling: {paper}")
        # paper_id = paper.get_id()
        
        try:
            # Get citing papers (papers that cite this one)
            citing_relations = self.cite_manager.get_citing_papers(paper)
            self.stats['api_requests'] += 1
            
            # Get cited papers (papers this one cites)
            cited_relations = self.cite_manager.get_cited_papers(paper)
            self.stats['api_requests'] += 1
            
            # mdata = self.crossref_manager.get(paper.doi)
            mdata = self.crossref_manager.get_set(paper)
            # self.metadata_queue.append((paper.id,mdata))
            
            # Process all citations (batch them instead of immediate insert)
            all_citations = citing_relations + cited_relations
            self.queue_citations_for_batch(all_citations, depth + 1)
            
            # Queue paper for metadata update
            self.queue_paper_update(paper, len(citing_relations), len(cited_relations))
            
            # Update statistics
            self.stats['citations_found'] += len(all_citations)
            self.stats['papers_processed'] += 1
            
            self.db.add_node(paper)
            # Add to network graph
            # self.G.add_node(paper_id, 
            #               title=str(paper),
            #               nciting=len(citing_relations),
            #               ncited=len(cited_relations),
            #               depth=depth)
            
            print(f"  Found {len(citing_relations)} citing, {len(cited_relations)} cited papers")
            
            # Process batches if we've accumulated enough
            self.process_pending_batches()
            
            return True
            
        except Exception as e:
            print(f"  ERROR crawling {paper}: {e}")
            return False
    
    def queue_citations_for_batch(self, citations: List[Tuple], depth: int):
        """Queue citations for batch processing instead of immediate insert."""
        new_papers_to_queue = []
        
        for citation, cited_paper, citing_paper in citations:
            # Add edge to graph
            # self.G.add_edge(citing_paper.get_id(), cited_paper.get_id(), 
            #               citation=citation.oci)
            
            self.db.add_edge(citation, citing_paper, cited_paper)
            
            # Update reference counts
            self.paper_references[cited_paper.get_id()] += 1
            self.paper_references[citing_paper.get_id()] += 1
            
            # Queue papers for batch insertion
            cited_data = self._paper_to_dict(cited_paper)
            citing_data = self._paper_to_dict(citing_paper)
            
            self.pending_papers.append(cited_data)
            self.pending_papers.append(citing_data)
            
            # We'll need to get the database IDs after batch insert to create citation records
            # For now, store the citation info to process later
            self.pending_citations.append((citation.oci, citing_paper.get_id(), cited_paper.get_id()))
            
            # Add to priority queue if not processed and within depth limit
            for paper in [cited_paper, citing_paper]:
                paper_id = paper.get_id()
                if (paper_id not in self.processed_paper_ids and 
                    depth <= self.max_depth and
                    not any(item[1] == paper_id for item in self.priority_queue)):
                    
                    priority = self.calculate_priority(paper, depth)
                    new_papers_to_queue.append((priority, paper_id, paper))
        
        # Add all new papers to queue at once
        for priority_item in new_papers_to_queue:
            heapq.heappush(self.priority_queue, priority_item)
        
        print(f"  Queued {len(new_papers_to_queue)} new papers for processing")
    
    def queue_paper_update(self, paper: 'Paper', nciting: int, ncited: int):
        """Queue a paper for citation count update."""
        paper_data = self._paper_to_dict(paper)
        existing_id = self.db.get_paper_id_by_identifier(paper_data)
        
        if existing_id:
            # Mark as done and update citation counts
            self.db.mark_paper_done(existing_id)
            self.db.update_paper_citations(existing_id, nciting=nciting, ncited=ncited, 
                                         strength=getattr(paper, 'strength', 0.0))
    
    def process_pending_batches(self):
        """Process accumulated batches when thresholds are reached."""
        # Process paper batch
        if len(self.pending_papers) >= self.paper_batch_size:
            print(f"  📦 Processing batch of {len(self.pending_papers)} papers...")
            
            # Remove duplicates while preserving order
            unique_papers = []
            seen_dois = set()
            for paper_data in self.pending_papers:
                doi = paper_data.get('doi')
                if doi and doi not in seen_dois:
                    unique_papers.append(paper_data)
                    seen_dois.add(doi)
                elif not doi:
                    unique_papers.append(paper_data)
            
            self.db.insert_paper_batch(unique_papers)
            self.stats['database_batches'] += 1
            self.pending_papers.clear()
        
        # Process citation batch
        if len(self.pending_citations) >= self.citation_batch_size:
            print(f"  🔗 Processing batch of {len(self.pending_citations)} citations...")
            
            # Convert paper IDs to database IDs
            citation_db_records = []
            for oci, citing_id, cited_id in self.pending_citations:
                citing_db_id = self.db.get_paper_id_by_identifier({'doi': citing_id} if ':doi:' not in citing_id else {'doi': citing_id.split(':')[1]})
                cited_db_id = self.db.get_paper_id_by_identifier({'doi': cited_id} if ':doi:' not in cited_id else {'doi': cited_id.split(':')[1]})
                
                if citing_db_id and cited_db_id:
                    citation_db_records.append((oci, citing_db_id, cited_db_id))
            
            if citation_db_records:
                self.db.insert_citations_batch(citation_db_records)
                self.stats['database_batches'] += 1
            
            self.pending_citations.clear()
    
    def force_process_all_batches(self):
        """Force process all pending batches regardless of size."""
        if self.pending_papers:
            print(f"  📦 Force processing {len(self.pending_papers)} remaining papers...")
            
            # Remove duplicates
            unique_papers = []
            seen_dois = set()
            for paper_data in self.pending_papers:
                doi = paper_data.get('doi')
                if doi and doi not in seen_dois:
                    unique_papers.append(paper_data)
                    seen_dois.add(doi)
                elif not doi:
                    unique_papers.append(paper_data)
            
            self.db.insert_paper_batch(unique_papers)
            self.stats['database_batches'] += 1
            self.pending_papers.clear()
        
        if self.pending_citations:
            print(f"  🔗 Force processing {len(self.pending_citations)} remaining citations...")
            
            # Convert paper IDs to database IDs
            citation_db_records = []
            for oci, citing_id, cited_id in self.pending_citations:
                # Try different ID extraction methods
                citing_db_id = self._get_db_id_for_paper_id(citing_id)
                cited_db_id = self._get_db_id_for_paper_id(cited_id)
                
                if citing_db_id and cited_db_id:
                    citation_db_records.append((oci, citing_db_id, cited_db_id))
            
            if citation_db_records:
                self.db.insert_citations_batch(citation_db_records)
                self.stats['database_batches'] += 1
            
            self.pending_citations.clear()
    
    def _get_db_id_for_paper_id(self, paper_id: str) -> Optional[int]:
        """Helper to get database ID from various paper ID formats."""
        if ':' in paper_id:
            # Format like "doi:10.1001/..."
            id_type, id_value = paper_id.split(':', 1)
            return self.db.get_paper_id_by_identifier({id_type: id_value})
        else:
            # Assume it's a DOI
            return self.db.get_paper_id_by_identifier({'doi': paper_id})
    
    def crawl_network(self, max_papers: int = None, max_time_hours: float = None):
        """
        Continuously crawl citation network until limits are reached.
        This version is optimized for performance with batch processing.
        """
        if max_papers:
            self.max_papers = max_papers
        
        if not self.stats['start_time']:
            self.stats['start_time'] = time.time()
        
        max_time_seconds = max_time_hours * 3600 if max_time_hours else float('inf')
        
        print(f"\\n{'='*60}")
        print(f"FAST DATABASE-INTEGRATED CITATION CRAWLER")
        print(f"{'='*60}")
        print(f"Max papers: {self.max_papers}")
        print(f"Max depth: {self.max_depth}")
        print(f"Queue size: {len(self.priority_queue)}")
        print(f"Database: {self.db.db_path}")
        print(f"Performance optimizations:")
        print(f"  - Paper batch size: {self.paper_batch_size}")
        print(f"  - Citation batch size: {self.citation_batch_size}")
        print(f"  - State save frequency: {self.state_save_frequency}")
        print(f"  - CrossRef batch size: {self.crossref_batch_size}")
        
        # Show database stats
        db_stats = self.db.get_statistics()
        print(f"Papers in database: {db_stats['total_papers']}")
        print(f"Papers with metadata: {db_stats['papers_with_metadata']}")
        
        try:
            while (self.priority_queue and 
                   self.stats['papers_processed'] < self.max_papers and
                   (time.time() - self.stats['start_time']) < max_time_seconds):
                
                # Get highest priority paper
                priority, paper_id, paper = heapq.heappop(self.priority_queue)
                
                # Skip if already processed
                if paper_id in self.processed_paper_ids:
                    continue
                
                # Determine depth (approximate)
                depth = min(self.current_depth, self.max_depth)
                
                # Crawl the paper
                success = self.crawl_paper(paper, depth)
                if success:
                    self.processed_paper_ids.add(paper_id)
                
                # Save state less frequently (every 50 papers instead of 10)
                if self.stats['papers_processed'] % self.state_save_frequency == 0:
                    self.save_state()
                    self.print_stats()
                
                # Show top referenced papers less frequently
                if self.stats['papers_processed'] % 25 == 0:
                    self.print_top_papers()
        
        except KeyboardInterrupt:
            print("\\n\\nCrawling interrupted by user. Processing final batches...")
            
        except Exception as e:
            print(f"Error during crawling: {e}")
            
        # Process any remaining batches
        self.force_process_all_batches()
        
        # Final save and stats
        self.save_state()
        self.print_final_stats()
        
        # Separate CrossRef metadata fetching (not during crawling)
        # print(f"\\n🔍 Starting separate CrossRef metadata batch...")
        # self.fetch_crossref_metadata_batch()
    
    def fetch_crossref_metadata_batch(self):
        """Fetch CrossRef metadata for papers that don't have it yet."""
        print(f"\\n🔍 Fetching CrossRef metadata in batches...")
        
        # Get papers without metadata in larger batches
        total_fetched = 0
        batch_count = 0
        
        while True:
            papers_to_fetch = self.db.get_papers_without_metadata(limit=self.crossref_batch_size)
            
            if not papers_to_fetch:
                print(f"  ✅ No more papers need metadata fetching")
                break
            
            batch_count += 1
            print(f"  📚 Batch {batch_count}: Fetching metadata for {len(papers_to_fetch)} papers...")
            
            # Prepare batch updates
            metadata_updates = []
            
            for paper_data in papers_to_fetch:
                try:
                    # Create Paper object for CrossRef manager
                    # paper = Paper(doi=paper_data['doi'])
                    doi = paper_data['doi']
                    
                    # Fetch metadata
                    metadata = self.crossref_manager.get(doi, take=['title', 'author', 'issued'])
                    
                    if metadata:
                        # Convert to database format
                        db_metadata = {
                            'title': metadata.get('title', ''),
                            'authors': metadata.get('author', []),
                            'issued_timestamp': metadata.get('issued', 0)
                        }
                        
                        metadata_updates.append((paper_data['id'], db_metadata))
                        self.stats['crossref_requests'] += 1
                        
                        # Rate limiting for CrossRef
                        time.sleep(0.05)  # 20 requests per second max
                    
                except Exception as e:
                    print(f"    ✗ Failed to fetch metadata for {paper_data['doi']}: {e}")
            
            # Batch update all metadata
            if metadata_updates:
                updated_count = self.db.update_paper_metadata_batch(metadata_updates)
                total_fetched += updated_count
                print(f"    ✅ Updated metadata for {updated_count} papers")
                self.stats['database_batches'] += 1
            
            # Break if we got less than expected (no more papers)
            if len(papers_to_fetch) < self.crossref_batch_size:
                break
        
        self.stats['last_crossref_batch'] = time.time()
        print(f"  🎉 CrossRef metadata fetching complete: {total_fetched} papers updated")
    
    def print_stats(self):
        """Print current crawling statistics."""
        elapsed = time.time() - self.stats['start_time']
        papers_per_minute = (self.stats['papers_processed'] / elapsed) * 60 if elapsed > 0 else 0
        
        print(f"\\n--- FAST CRAWLER STATS ---")
        print(f"Papers processed: {self.stats['papers_processed']}")
        print(f"Citations found: {self.stats['citations_found']}")
        print(f"OpenCitations API requests: {self.stats['api_requests']}")
        print(f"CrossRef API requests: {self.stats['crossref_requests']}")
        print(f"Database batches: {self.stats['database_batches']}")
        print(f"Queue size: {len(self.priority_queue)}")
        print(f"Pending papers: {len(self.pending_papers)}")
        print(f"Pending citations: {len(self.pending_citations)}")
        # print(f"Network size: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
        print(f"Processing rate: {papers_per_minute:.1f} papers/min")
        print(f"Elapsed time: {elapsed/60:.1f} minutes")
        
        # Database stats
        db_stats = self.db.get_statistics()
        print(f"Database: {db_stats['total_papers']} papers, {db_stats['papers_with_metadata']} with metadata")
    
    def print_top_papers(self, top_n: int = 10):
        """Print the most frequently referenced papers from database."""
        top_papers = self.db.get_top_papers(metric='nciting', limit=top_n)
        
        if not top_papers:
            return
            
        print(f"\\n--- TOP {top_n} PAPERS BY CITATIONS ---")
        for paper in top_papers[:top_n]:
            title = paper.get('title', '')[:50] + '...' if len(paper.get('title', '')) > 50 else paper.get('title', '')
            title = title or paper.get('doi', 'Unknown')
            status = "✓ Processed" if paper['id'] in self.processed_paper_ids else "⏳ Pending"
            print(f"  {paper['nciting']:3d} citing: {title} ({status})")
    
    def print_final_stats(self):
        """Print final crawling statistics."""
        elapsed = time.time() - self.stats['start_time']
        
        print(f"\\n{'='*60}")
        print(f"FAST CITATION CRAWLING COMPLETE")
        print(f"{'='*60}")
        print(f"Total papers processed: {self.stats['papers_processed']}")
        print(f"Total citations found: {self.stats['citations_found']}")
        print(f"OpenCitations API requests: {self.stats['api_requests']}")
        print(f"CrossRef API requests: {self.stats['crossref_requests']}")
        print(f"Database batches executed: {self.stats['database_batches']}")
        # print(f"Final network: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
        print(f"Total runtime: {elapsed/60:.1f} minutes")
        print(f"Average rate: {(self.stats['papers_processed']/elapsed)*60:.1f} papers/min")
        
        # Performance breakdown
        print(f"\\n⚡ PERFORMANCE BREAKDOWN:")
        api_time_estimate = self.stats['api_requests'] * 1.5  # ~1.5s per API call
        db_time_estimate = self.stats['database_batches'] * 0.1  # ~0.1s per batch
        print(f"  API calls: ~{api_time_estimate:.1f}s ({(api_time_estimate/elapsed)*100:.1f}% of time)")
        print(f"  Database ops: ~{db_time_estimate:.1f}s ({(db_time_estimate/elapsed)*100:.1f}% of time)")
        print(f"  Other processing: ~{elapsed - api_time_estimate - db_time_estimate:.1f}s")
        
        # Database final stats
        db_stats = self.db.get_statistics()
        print(f"\\n📊 DATABASE STATISTICS:")
        print(f"  Total papers: {db_stats['total_papers']}")
        print(f"  Papers with metadata: {db_stats['papers_with_metadata']}")
        print(f"  Total citations: {db_stats['total_citations']}")
        print(f"  Avg citations per paper: {db_stats['avg_nciting']:.1f}")
        print(f"  Max citations: {db_stats['max_nciting']}")
        
        # Efficiency metrics
        if self.stats['papers_processed'] > 0:
            print(f"\\n🎯 EFFICIENCY METRICS:")
            print(f"  Papers per API request: {self.stats['papers_processed'] / max(self.stats['api_requests'], 1):.1f}")
            print(f"  Papers per database batch: {db_stats['total_papers'] / max(self.stats['database_batches'], 1):.1f}")
            print(f"  Citations per database batch: {db_stats['total_citations'] / max(self.stats['database_batches'], 1):.1f}")
    
    def save_state(self):
        """Save crawler state to disk (less frequently for performance)."""
        state = {
            'processed_paper_ids': list(self.processed_paper_ids),
            'priority_queue': self.priority_queue,
            'paper_references': dict(self.paper_references),
            # 'graph_data': {
            #     'nodes': list(self.G.nodes(data=True)),
            #     'edges': list(self.G.edges(data=True))
            # },
            'stats': self.stats,
            'max_depth': self.max_depth,
            'max_papers': self.max_papers,
            'db_path': self.db.db_path,
            # Don't save pending batches - they'll be processed
            'batch_sizes': {
                'paper_batch_size': self.paper_batch_size,
                'citation_batch_size': self.citation_batch_size,
                'crossref_batch_size': self.crossref_batch_size
            }
        }
        
        with open(self.state_file, 'wb') as f:
            pickle.dump(state, f)
        
        self.stats['last_save_time'] = time.time()
        print(f"  💾 State saved to {self.state_file}")
    
    def load_state(self):
        """Load previous crawler state if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'rb') as f:
                    state = pickle.load(f)
                
                self.processed_paper_ids = set(state.get('processed_paper_ids', []))
                self.priority_queue = state.get('priority_queue', [])
                self.paper_references = Counter(state.get('paper_references', {}))
                self.stats = state.get('stats', self.stats)
                self.max_depth = state.get('max_depth', 3)
                self.max_papers = state.get('max_papers', 1000)
                
                # Load batch sizes if available
                batch_sizes = state.get('batch_sizes', {})
                self.paper_batch_size = batch_sizes.get('paper_batch_size', 50)
                self.citation_batch_size = batch_sizes.get('citation_batch_size', 100)
                self.crossref_batch_size = batch_sizes.get('crossref_batch_size', 20)
                
                # Rebuild graph
                graph_data = state.get('graph_data', {'nodes': [], 'edges': []})
                # self.G.add_nodes_from(graph_data['nodes'])
                # self.G.add_edges_from(graph_data['edges'])
                
                print(f"Loaded previous fast crawler state:")
                print(f"  - {len(self.processed_paper_ids)} papers already processed")
                print(f"  - {len(self.priority_queue)} papers in queue")
                print(f"  - {len(self.paper_references)} papers referenced")
                # print(f"  - {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges in graph")
                print(f"  - Batch sizes: papers={self.paper_batch_size}, citations={self.citation_batch_size}")
                
            except Exception as e:
                print(f"Error loading crawler state: {e}")
                print("Starting fresh...")
    


def test_fast_crawler():
    """Test the fast citation crawler."""
    
    print("🚀 FAST CITATION CRAWLER TEST")
    print("="*50)
    
    # Create managers
    cite_manager = CiteManager()
    crossref_manager = CrossRefManager()
    
    # Create fast crawler
    crawler = Crawler(
        cite_manager, 
        crossref_manager,
        db_path="./data/citations/test_fast.db"
    )
    
    # Set test parameters for speed
    crawler.max_papers = 5
    crawler.paper_batch_size = 10    # Smaller batches for testing
    crawler.citation_batch_size = 20
    crawler.crossref_batch_size = 3
    crawler.state_save_frequency = 25  # Save less often
    
    # Create test papers
    test_papers = [
        Paper(doi="10.1001/jama.2020.1585"),
        Paper(doi="10.1038/nature12373")
    ]
    
    # Add seed papers
    start_time = time.time()
    crawler.add_seed_papers(test_papers)
    
    # Run crawler
    crawler.crawl_network(max_papers=5, max_time_hours=0.05)
    
    elapsed = time.time() - start_time
    
    print(f"\\n🏁 Fast crawler test completed in {elapsed:.1f} seconds")
    print(f"⚡ Performance: {crawler.stats['papers_processed'] / elapsed:.1f} papers/second")
    
    # Show final stats
    final_stats = crawler.db.get_statistics()
    print(f"📊 Database: {final_stats['total_papers']} papers, {final_stats['total_citations']} citations")
    
    # Cleanup
    crawler.db.close_connection()


if __name__ == "__main__":
    test_fast_crawler()