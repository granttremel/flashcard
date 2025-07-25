

from flashcard.wiki_parser import WikiParser
from flashcard.wikipedia import WikiManager
from flashcard.page_classifier import WikipediaPageClassifier
import sys
sys.path.append('.')
# from scripts.test_wiki import fetch_wikipedia_page
import os
import json
from typing import Dict, List, Set, Tuple
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import time


class WikiNet:
    
    def __init__(self, filter_scientific=True):
        
        self.wman = WikiManager()
        
        self.G = nx.Graph()
        self.lastfetch = 0
        self.filter_scientific = filter_scientific
        self.classifier = WikipediaPageClassifier() if filter_scientific else None
        self.classification_log = []  # Track classification decisions

    def build_flashcard_network(self, start_page: str, depth: int = 1, max_pages: int = 10) -> Dict:
        """
        Build a network of flashcards starting from a Wikipedia page.
        
        Args:
            start_page: The Wikipedia page to start from
            depth: How many levels of links to follow (1 = just direct links)
            max_pages: Maximum number of pages to fetch
        
        Returns:
            Dictionary containing flashcard data and relationships
        """
        
        flashcards = {}
        processed = set()
        to_process = [(start_page, 0)]  # (page_name, current_depth)
        
        while to_process and len(processed) < max_pages:
            page_name, current_depth = to_process.pop(0)
            
            if page_name in processed:
                continue
                
            print(f"\nProcessing: {page_name} (depth: {current_depth})")
            
            # Check if we have it locally
            loc_path = f'./data/wiki/{page_name}.json'
            if not os.path.exists(loc_path):
                
                tnow =time.time() 
                if tnow - self.lastfetch < 1.1:
                    print('sleeping 1s for rate limit')
                    time.sleep(1.0)
                
                try:
                    print(f"  Fetching from Wikipedia...")
                    json_data = self.wman.fetch_wikipedia_page(page_name, save_local=True)
                    
                    self.lastfetch = time.time()
                except Exception as e:
                    print(f"  Error fetching {page_name}: {e}")
                    continue
            else:
                print(f"  Loading from local cache...")
                with open(loc_path, 'r') as f:
                    json_data = json.load(f)
            
            # Parse the page
            parser = WikiParser()
            parser.load_from_json(json_data)
            data = parser.extract_all()
            
            # Check if we should include this page based on classification
            if self.filter_scientific and self.classifier:
                classification = self.classifier.classify_page(
                    data.get('categories', []),
                    data.get('title', ''),
                    data.get('short_description', ''),
                    data.get('main_definition', '')
                )
                
                # Log the classification decision
                self.classification_log.append({
                    'page': page_name,
                    'title': data.get('title', ''),
                    'classification': classification,
                    'included': self.classifier.should_include_page(classification)
                })
                
                # Skip non-scientific pages
                if not self.classifier.should_include_page(classification):
                    print(f"  SKIPPING (non-scientific): {self.classifier.get_classification_summary(classification)}")
                    processed.add(page_name)  # Mark as processed so we don't try again
                    continue
                else:
                    print(f"  INCLUDING: {self.classifier.get_classification_summary(classification)}")
            
            # Create flashcard
            flashcard = {
                'term': data['title'],
                'definition': data['short_description'] or data['main_definition'][:200],
                'full_definition': data['main_definition'],
                'depth': current_depth,
                'related_concepts': [],
                'categories': data.get('categories', []),
                'sections': {k: v[:300] for k, v in list(data['sections'].items())[:2]}
            }
            
            # Add to our collection
            flashcards[page_name] = flashcard
            processed.add(page_name)
            
            # Process related links if we haven't reached max depth
            if current_depth < depth:
                links_to_add = []
                for link, title in data['internal_links'][:10]:  # Check more links but filter
                    # Skip if already processed or in queue
                    if link in processed or link in [p[0] for p in to_process]:
                        continue
                    
                    # For deeper links, do a quick category check if possible
                    if self.filter_scientific and ':' not in link:  # Skip special pages
                        links_to_add.append((link, title))
                
                # Add top 5 filtered links
                for link, title in links_to_add[:5]:
                    flashcard['related_concepts'].append(link)
                    to_process.append((link, current_depth + 1))
        
        # Build the network structure
        network = {
            'flashcards': flashcards,
            'connections': []
        }
        
        # Create connections list
        for page_name, card in flashcards.items():
            for related in card['related_concepts']:
                if related in flashcards:
                    network['connections'].append({
                        'from': page_name,
                        'to': related,
                        'type': 'related_concept'
                    })
        
        self.build_networkx_graph(network)
        return network


    def visualize_network(self, network: Dict):
        """Print a simple text visualization of the flashcard network"""
        
        print("\n" + "="*60)
        print("FLASHCARD NETWORK SUMMARY")
        print("="*60)
        
        print(f"\nTotal flashcards: {len(network['flashcards'])}")
        print(f"Total connections: {len(network['connections'])}")
        
        print("\n\nFLASHCARDS:")
        print("-"*40)
        for page_name, card in network['flashcards'].items():
            print(f"\n[{card['term']}] (depth: {card['depth']})")
            print(f"  Definition: {card['definition']}")
            if card['related_concepts']:
                print(f"  Related: {', '.join(card['related_concepts'][:3])}")
        
        print("\n\nCONNECTIONS:")
        print("-"*40)
        for conn in network['connections']:
            from_title = network['flashcards'][conn['from']]['term']
            to_title = network['flashcards'][conn['to']]['term']
            print(f"  {from_title} → {to_title}")
        
        # Find central concepts (most connected)
        connection_count = {}
        for conn in network['connections']:
            connection_count[conn['from']] = connection_count.get(conn['from'], 0) + 1
            connection_count[conn['to']] = connection_count.get(conn['to'], 0) + 1
        
        if connection_count:
            print("\n\nMOST CONNECTED CONCEPTS:")
            print("-"*40)
            sorted_concepts = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)
            for concept, count in sorted_concepts[:5]:
                if concept in network['flashcards']:
                    title = network['flashcards'][concept]['term']
                    print(f"  {title}: {count} connections")


    def save_network(self, network: Dict, filename: str):
        """Save the flashcard network to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(network, f, indent=2)
        print(f"\nNetwork saved to: {filename}")


    def build_networkx_graph(self, network: Dict) -> nx.DiGraph:
        """
        Convert the flashcard network to a NetworkX directed graph.
        
        Returns:
            NetworkX DiGraph with nodes containing flashcard data
        """
        G = nx.DiGraph()
        
        # Add nodes with flashcard data
        for page_name, card in network['flashcards'].items():
            G.add_node(page_name, 
                    title=card['term'],
                    definition=card['definition'],
                    depth=card['depth'],
                    translations=len(card.get('translations', {})),
                    sections=len(card.get('sections', {})))
        
        # Add edges
        for conn in network['connections']:
            G.add_edge(conn['from'], conn['to'], type=conn['type'])
        
        self.G = G


    def analyze_network(self) -> Dict:
        """
        Analyze the network structure and return key metrics.
        """
        G = self.G
        analysis = {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'density': nx.density(G),
            'is_connected': nx.is_weakly_connected(G),
            'average_degree': sum(dict(G.degree()).values()) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0
        }
        
        # Calculate centrality measures
        if G.number_of_nodes() > 0:
            analysis['degree_centrality'] = nx.degree_centrality(G)
            analysis['in_degree_centrality'] = nx.in_degree_centrality(G)
            analysis['out_degree_centrality'] = nx.out_degree_centrality(G)
            
            # Find most central nodes
            sorted_by_degree = sorted(analysis['degree_centrality'].items(), key=lambda x: x[1], reverse=True)
            analysis['most_central_nodes'] = sorted_by_degree[:5]
        
        # Find strongly connected components
        analysis['num_strongly_connected_components'] = nx.number_strongly_connected_components(G)
        
        # Calculate shortest path statistics
        if nx.is_weakly_connected(G):
            undirected = G.to_undirected()
            analysis['average_shortest_path'] = nx.average_shortest_path_length(undirected)
            analysis['diameter'] = nx.diameter(undirected)
        
        return analysis


    def visualize_networkx_graph(self, save_path: str = None):
        """
        Create a visual representation of the NetworkX graph.
        """
        G = self.G
        plt.figure(figsize=(15, 10))
        
        # Create layout
        pos = nx.spring_layout(G, k=3, iterations=50, seed=42)
        
        # Color nodes by depth
        node_colors = []
        node_sizes = []
        for node in G.nodes():
            depth = G.nodes[node]['depth']
            # Color gradient based on depth
            color_intensity = 1 - (depth * 0.3)  # Darker for deeper nodes
            node_colors.append((color_intensity, 0.5, 1-color_intensity))
            
            # Size based on degree
            degree = G.degree(node)
            node_sizes.append(1000 + degree * 500)
        
        # Draw the graph
        nx.draw_networkx_nodes(G, pos, 
                            node_color=node_colors,
                            node_size=node_sizes,
                            alpha=0.8)
        
        nx.draw_networkx_edges(G, pos,
                            edge_color='gray',
                            arrows=True,
                            arrowsize=20,
                            alpha=0.5,
                            arrowstyle='->')
        
        # Add labels with titles
        labels = {node: G.nodes[node]['title'] for node in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold')
        
        plt.title("Wikipedia Flashcard Network", fontsize=16)
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Graph visualization saved to: {save_path}")
        
        plt.show()


    def create_concept_map(self, central_node: str, radius: int = 2) -> nx.DiGraph:
        """
        Create a subgraph centered around a specific concept.
        
        Args:
            G: The full NetworkX graph
            central_node: The node to center the concept map around
            radius: How many hops from the central node to include
        
        Returns:
            A subgraph containing only nodes within radius of central_node
        """
        G = self.G
        # Get all nodes within radius
        nodes_to_include = set([central_node])
        current_layer = set([central_node])
        
        for _ in range(radius):
            next_layer = set()
            for node in current_layer:
                # Add predecessors and successors
                next_layer.update(G.predecessors(node))
                next_layer.update(G.successors(node))
            nodes_to_include.update(next_layer)
            current_layer = next_layer
        
        # Create subgraph
        subgraph = G.subgraph(nodes_to_include).copy()
        
        return subgraph


    def export_to_graphml(self, filename: str):
        """Export the graph to GraphML format for use in other tools."""
        nx.write_graphml(self.G, filename)
        print(f"Graph exported to GraphML: {filename}")


    def export_to_gexf(self, filename: str):
        """Export the graph to GEXF format for use in Gephi."""
        nx.write_gexf(self.G, filename)
        print(f"Graph exported to GEXF: {filename}")
    
    def get_classification_report(self) -> str:
        """Generate a report of classification decisions made during network building."""
        if not self.classification_log:
            return "No classification decisions recorded."
        
        total = len(self.classification_log)
        included = sum(1 for log in self.classification_log if log['included'])
        excluded = total - included
        
        report = f"\nCLASSIFICATION REPORT:\n{'='*60}\n"
        report += f"Total pages analyzed: {total}\n"
        report += f"Scientific pages included: {included} ({included/total*100:.1f}%)\n"
        report += f"Non-scientific pages excluded: {excluded} ({excluded/total*100:.1f}%)\n"
        
        report += "\nEXCLUDED PAGES:\n" + "-"*40 + "\n"
        for log in self.classification_log:
            if not log['included']:
                classification = log['classification']
                report += f"- {log['title']}: {self.classifier.get_classification_summary(classification)}\n"
                if classification['matched_exclude_keywords']:
                    report += f"  Matched keywords: {', '.join(list(classification['matched_exclude_keywords'])[:5])}\n"
        
        return report
