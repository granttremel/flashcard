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
from .citations_refactored import CiteManager, CrossRefManager, Paper, Citation
from .paper_database import PaperDatabase


class DatabaseIntegratedCitationCrawler:
    """
    Enhanced citation crawler that integrates with SQLite database for
    efficient storage of large numbers of papers and automatic CrossRef metadata fetching.
    """
    
    def __init__(self, cite_manager: CiteManager, crossref_manager: CrossRefManager = None,
                 db_path: str = "./data/citations/papers.db", 
                 state_file: str = "./data/citation_crawler_db_state.pkl"):
        self.cite_manager = cite_manager
        self.crossref_manager = crossref_manager or CrossRefManager()
        self.db = PaperDatabase(db_path)
        self.state_file = state_file
        
        # Network graph (kept in memory for analysis)
        self.G = nx.DiGraph()
        
        # State tracking (now database-backed)
        self.processed_paper_ids = set()   # Track IDs we've fully processed
        self.priority_queue = []           # Min-heap: (-priority, paper_id, paper)
        self.paper_references = Counter()  # Reference counting for priority
        
        # Crawler settings
        self.max_depth = 3
        self.max_papers = 1000
        self.current_depth = 0
        
        # Batch processing settings
        self.batch_size = 50
        self.crossref_batch_size = 20
        
        # Statistics
        self.stats = {
            'papers_processed': 0,
            'citations_found': 0,
            'api_requests': 0,
            'crossref_requests': 0,
            'start_time': None,
            'last_save_time': None,
            'last_crossref_batch': None
        }
        
        # Load previous state if it exists
        self.load_state()
    
    def add_seed_papers(self, seed_papers: List['Paper']):
        """Add initial seed papers to start crawling from."""
        for paper in seed_papers:
            paper_id = paper.get_id()
            
            # Store paper in database
            paper_data = self._paper_to_dict(paper)
            db_id = self.db.insert_paper(paper_data)
            
            if paper_id not in self.processed_paper_ids:
                # Add with high priority (negative for min-heap)
                priority = self.calculate_priority(paper, 0)
                heapq.heappush(self.priority_queue, (priority, paper_id, paper))
                print(f"Added seed paper: {paper}")
    
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
        """
        Calculate priority for a paper.
        Higher citation count = higher priority (more negative for min-heap)
        Lower depth = higher priority
        """
        reference_count = self.paper_references.get(paper.get_id(), 0)
        citation_count = getattr(paper, 'nciting', 0) + getattr(paper, 'ncited', 0)
        
        # Priority = references + citations - depth_penalty
        # Use negative for min-heap (higher priority = more negative)
        priority = reference_count + citation_count - (depth * 50)
        return -priority
    
    def crawl_paper(self, paper: 'Paper', depth: int) -> bool:
        """
        Crawl a single paper to get its citations and references.
        
        Returns:
            True if successful, False if failed
        """
        print(f"\n[Depth {depth}] Crawling: {paper}")
        paper_id = paper.get_id()
        
        try:
            # Get citing papers (papers that cite this one)
            citing_relations = self.cite_manager.get_citing_papers(paper)
            self.stats['api_requests'] += 1
            
            # Get cited papers (papers this one cites)
            cited_relations = self.cite_manager.get_cited_papers(paper)
            self.stats['api_requests'] += 1
            
            # Process all citations
            all_citations = citing_relations + cited_relations
            self.add_citations_to_database(all_citations, depth + 1)
            
            # Update paper in database
            self.db.update_paper_citations(
                self.db.get_paper_id_by_identifier({'doi': paper.get_id('doi')} if hasattr(paper, 'doi') else {}),
                nciting=len(citing_relations),
                ncited=len(cited_relations),
                strength=getattr(paper, 'strength', 0.0)
            )
            
            # Mark as done
            db_paper_id = self.db.get_paper_id_by_identifier(self._paper_to_dict(paper))
            if db_paper_id:
                self.db.mark_paper_done(db_paper_id)
            
            # Update statistics
            self.stats['citations_found'] += len(all_citations)
            self.stats['papers_processed'] += 1
            
            # Add to network graph
            self.G.add_node(paper_id, 
                          title=str(paper),
                          nciting=getattr(paper, 'nciting', 0),
                          ncited=getattr(paper, 'ncited', 0),
                          depth=depth)
            
            print(f"  Found {len(citing_relations)} citing, {len(cited_relations)} cited papers")
            return True
            
        except Exception as e:
            print(f"  ERROR crawling {paper}: {e}")
            return False
    
    def add_citations_to_database(self, citations: List[Tuple], depth: int):
        """Add citations to the database and update queues."""
        new_papers_added = 0
        
        for citation, cited_paper, citing_paper in citations:
            # Store papers in database
            cited_data = self._paper_to_dict(cited_paper)
            citing_data = self._paper_to_dict(citing_paper)
            
            cited_db_id = self.db.insert_paper(cited_data)
            citing_db_id = self.db.insert_paper(citing_data)
            
            # Store citation relationship
            if cited_db_id and citing_db_id:
                self.db.insert_citation(citation.oci, citing_db_id, cited_db_id)
            
            # Add edge to graph
            self.G.add_edge(citing_paper.get_id(), cited_paper.get_id(), 
                          citation=citation.oci)
            
            # Update reference counts
            self.paper_references[cited_paper.get_id()] += 1
            self.paper_references[citing_paper.get_id()] += 1
            
            # Add to priority queue if not processed and within depth limit
            for paper in [cited_paper, citing_paper]:
                paper_id = paper.get_id()
                if (paper_id not in self.processed_paper_ids and 
                    depth <= self.max_depth and
                    not any(item[1] == paper_id for item in self.priority_queue)):
                    
                    priority = self.calculate_priority(paper, depth)
                    heapq.heappush(self.priority_queue, (priority, paper_id, paper))
                    new_papers_added += 1
        
        print(f"  Added {new_papers_added} new papers to queue")
    
    def crawl_network(self, max_papers: int = None, max_time_hours: float = None):
        """
        Continuously crawl citation network until limits are reached.
        """
        if max_papers:
            self.max_papers = max_papers
        
        if not self.stats['start_time']:
            self.stats['start_time'] = time.time()
        
        max_time_seconds = max_time_hours * 3600 if max_time_hours else float('inf')
        
        print(f"\n{'='*60}")
        print(f"DATABASE-INTEGRATED CITATION CRAWLER")
        print(f"{'='*60}")
        print(f"Max papers: {self.max_papers}")
        print(f"Max depth: {self.max_depth}")
        print(f"Queue size: {len(self.priority_queue)}")
        print(f"Database: {self.db.db_path}")
        
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
                
                # Save state and fetch metadata periodically
                if self.stats['papers_processed'] % 10 == 0:
                    self.save_state()
                    self.print_stats()
                
                # Fetch CrossRef metadata in batches
                if self.stats['papers_processed'] % self.crossref_batch_size == 0:
                    self.fetch_crossref_metadata_batch()
                
                # Show top referenced papers periodically
                if self.stats['papers_processed'] % 25 == 0:
                    self.print_top_papers()
        
        except KeyboardInterrupt:
            print("\n\nCrawling interrupted by user. Saving state...")
            
        except Exception as e:
            print(f"Error during crawling: {e}")
            
        # Final save and metadata fetch
        self.save_state()
        self.fetch_crossref_metadata_batch()
        self.print_final_stats()
    
    def fetch_crossref_metadata_batch(self):
        """Fetch CrossRef metadata for papers that don't have it yet."""
        print(f"\n🔍 Fetching CrossRef metadata...")
        
        # Get papers without metadata
        papers_to_fetch = self.db.get_papers_without_metadata(limit=self.crossref_batch_size)
        
        if not papers_to_fetch:
            print("  No papers need metadata fetching")
            return
        
        print(f"  Fetching metadata for {len(papers_to_fetch)} papers...")
        
        for paper_data in papers_to_fetch:
            try:
                # Create Paper object for CrossRef manager
                paper = Paper(doi=paper_data['doi'])
                
                # Fetch metadata
                metadata = self.crossref_manager.get(paper, take=['title', 'author', 'issued'])
                
                if metadata:
                    # Convert to database format
                    db_metadata = {
                        'title': metadata.get('title', ''),
                        'authors': metadata.get('author', []),
                        'issued_timestamp': metadata.get('issued', 0)
                    }
                    
                    # Update database
                    self.db.update_paper_metadata(paper_data['id'], db_metadata)
                    print(f"    ✓ Updated: {metadata.get('title', paper_data['doi'])[:50]}...")
                    
                    self.stats['crossref_requests'] += 1
                    
                    # Rate limiting
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"    ✗ Failed to fetch metadata for {paper_data['doi']}: {e}")
        
        self.stats['last_crossref_batch'] = time.time()
        print(f"  ✅ CrossRef batch complete")
    
    def print_stats(self):
        """Print current crawling statistics."""
        elapsed = time.time() - self.stats['start_time']
        papers_per_minute = (self.stats['papers_processed'] / elapsed) * 60 if elapsed > 0 else 0
        
        print(f"\n--- DATABASE CRAWLER STATS ---")
        print(f"Papers processed: {self.stats['papers_processed']}")
        print(f"Citations found: {self.stats['citations_found']}")
        print(f"OpenCitations API requests: {self.stats['api_requests']}")
        print(f"CrossRef API requests: {self.stats['crossref_requests']}")
        print(f"Queue size: {len(self.priority_queue)}")
        print(f"Network size: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
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
            
        print(f"\n--- TOP {top_n} PAPERS BY CITATIONS ---")
        for paper in top_papers:
            title = paper.get('title', '')[:50] + '...' if len(paper.get('title', '')) > 50 else paper.get('title', '')
            title = title or paper.get('doi', 'Unknown')
            status = "✓ Processed" if paper['id'] in self.processed_paper_ids else "⏳ Pending"
            print(f"  {paper['nciting']:3d} citing: {title} ({status})")
    
    def print_final_stats(self):
        """Print final crawling statistics."""
        elapsed = time.time() - self.stats['start_time']
        
        print(f"\n{'='*60}")
        print(f"DATABASE CITATION CRAWLING COMPLETE")
        print(f"{'='*60}")
        print(f"Total papers processed: {self.stats['papers_processed']}")
        print(f"Total citations found: {self.stats['citations_found']}")
        print(f"OpenCitations API requests: {self.stats['api_requests']}")
        print(f"CrossRef API requests: {self.stats['crossref_requests']}")
        print(f"Final network: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
        print(f"Total runtime: {elapsed/60:.1f} minutes")
        
        # Database final stats
        db_stats = self.db.get_statistics()
        print(f"\n📊 DATABASE STATISTICS:")
        print(f"  Total papers: {db_stats['total_papers']}")
        print(f"  Papers with metadata: {db_stats['papers_with_metadata']}")
        print(f"  Total citations: {db_stats['total_citations']}")
        print(f"  Avg citations per paper: {db_stats['avg_nciting']:.1f}")
        print(f"  Max citations: {db_stats['max_nciting']}")
        
        # Show top journals if available
        if db_stats.get('top_journals'):
            print(f"\n📚 TOP JOURNALS:")
            for journal, count in list(db_stats['top_journals'].items())[:5]:
                print(f"  {count:3d} papers: {journal}")
        
        # Show network analysis
        if self.G.number_of_nodes() > 0:
            print(f"\n🕸️ NETWORK ANALYSIS:")
            print(f"  Density: {nx.density(self.G):.4f}")
            print(f"  Average degree: {sum(dict(self.G.degree()).values()) / self.G.number_of_nodes():.2f}")
            
            # Most central papers
            if self.G.number_of_nodes() > 1:
                centrality = nx.degree_centrality(self.G)
                sorted_centrality = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
                print(f"  Most central papers:")
                for paper_id, cent in sorted_centrality[:3]:
                    print(f"    {paper_id}: {cent:.3f}")
    
    def save_state(self):
        """Save crawler state to disk."""
        state = {
            'processed_paper_ids': list(self.processed_paper_ids),
            'priority_queue': self.priority_queue,
            'paper_references': dict(self.paper_references),
            'graph_data': {
                'nodes': list(self.G.nodes(data=True)),
                'edges': list(self.G.edges(data=True))
            },
            'stats': self.stats,
            'max_depth': self.max_depth,
            'max_papers': self.max_papers,
            'db_path': self.db.db_path
        }
        
        with open(self.state_file, 'wb') as f:
            pickle.dump(state, f)
        
        self.stats['last_save_time'] = time.time()
        print(f"  State saved to {self.state_file}")
    
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
                
                # Rebuild graph
                graph_data = state.get('graph_data', {'nodes': [], 'edges': []})
                self.G.add_nodes_from(graph_data['nodes'])
                self.G.add_edges_from(graph_data['edges'])
                
                print(f"Loaded previous crawler state:")
                print(f"  - {len(self.processed_paper_ids)} papers already processed")
                print(f"  - {len(self.priority_queue)} papers in queue")
                print(f"  - {len(self.paper_references)} papers referenced")
                print(f"  - {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges in graph")
                
            except Exception as e:
                print(f"Error loading crawler state: {e}")
                print("Starting fresh...")
    
    def get_network_analysis(self) -> Dict:
        """Get comprehensive network analysis including database stats."""
        db_stats = self.db.get_statistics()
        
        analysis = {
            'database_stats': db_stats,
            'crawler_stats': self.stats,
            'basic_stats': {
                'nodes': self.G.number_of_nodes(),
                'edges': self.G.number_of_edges(),
                'density': nx.density(self.G) if self.G.number_of_nodes() > 0 else 0,
                'is_connected': nx.is_weakly_connected(self.G) if self.G.number_of_nodes() > 1 else False
            }
        }
        
        if self.G.number_of_nodes() > 1:
            analysis['centrality'] = {
                'degree': dict(sorted(nx.degree_centrality(self.G).items(), 
                                    key=lambda x: x[1], reverse=True)[:10]),
                'pagerank': dict(sorted(nx.pagerank(self.G).items(), 
                                      key=lambda x: x[1], reverse=True)[:10])
            }
        
        return analysis
    
    def export_network_data(self, output_dir: str = "./data/citations"):
        """Export network data in various formats."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Export database to JSON
        json_file = os.path.join(output_dir, "papers_database_export.json")
        self.db.export_to_json(json_file, limit=None)
        
        # Export network analysis
        analysis_file = os.path.join(output_dir, "network_analysis_db.json")
        analysis = self.get_network_analysis()
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        # Export graph as GraphML
        if self.G.number_of_nodes() > 0:
            graphml_file = os.path.join(output_dir, "citation_network.graphml")
            nx.write_graphml(self.G, graphml_file)
            print(f"Network exported to: {graphml_file}")
        
        print(f"Data exported to: {output_dir}")
        return {
            'database_json': json_file,
            'analysis': analysis_file,
            'network': graphml_file if self.G.number_of_nodes() > 0 else None
        }


def test_database_crawler():
    """Test the database-integrated citation crawler."""
    
    print("🗄️ DATABASE-INTEGRATED CITATION CRAWLER TEST")
    print("="*50)
    
    # Create managers
    cite_manager = CiteManager()
    crossref_manager = CrossRefManager()
    
    # Create database crawler
    crawler = DatabaseIntegratedCitationCrawler(
        cite_manager, 
        crossref_manager,
        db_path="./data/citations/test_papers.db"
    )
    
    # Set test parameters
    crawler.max_papers = 5
    crawler.crossref_batch_size = 3
    
    # Create test papers
    test_papers = [
        Paper(doi="10.1001/jama.2020.1585"),
        Paper(doi="10.1038/nature12373")
    ]
    
    # Add seed papers
    crawler.add_seed_papers(test_papers)
    
    # Run crawler
    crawler.crawl_network(max_papers=5, max_time_hours=0.05)
    
    # Export results
    exports = crawler.export_network_data("./data/citations/test_export")
    
    print(f"\n✅ Test complete. Exports: {exports}")


if __name__ == "__main__":
    test_database_crawler()