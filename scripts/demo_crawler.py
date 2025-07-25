#!/usr/bin/env python3

from flashcard.wiki_crawler import IntelligentWikiCrawler
from flashcard.network import WikiNet
import json

def demo_intelligent_crawler():
    """Demonstrate the intelligent Wikipedia crawler."""
    
    print("🕷️  INTELLIGENT WIKIPEDIA CRAWLER DEMO")
    print("="*60)
    
    # Create crawler with scientific filtering
    crawler = IntelligentWikiCrawler(
        filter_scientific=True,
        data_dir="./data/wiki",
        crawler_state_file="./data/crawler_state.pkl"
    )
    
    # Set crawler parameters
    crawler.max_depth = 2      # How deep to go
    crawler.max_pages = 50     # Limit for demo
    
    # Add seed pages for anatomical/biological topics
    seed_pages = [
        "Nervous_system",
        "Cardiovascular_system", 
        "Respiratory_system",
        "Digestive_system",
        "Endocrine_system"
    ]
    
    print(f"Adding {len(seed_pages)} seed pages...")
    crawler.add_seed_pages(seed_pages)
    
    # Start crawling
    print("\nStarting intelligent crawl...")
    print("The crawler will:")
    print("- Prioritize links that appear frequently across pages")
    print("- Filter out non-scientific content")
    print("- Build a knowledge network automatically")
    print("- Save progress so it can be resumed later")
    print("\nPress Ctrl+C to stop at any time\n")
    
    # Crawl with time limit for demo
    crawler.crawl_continuously(max_pages=50, max_time_hours=0.05)  # 3 minutes max
    
    # Show what we discovered
    print("\n🧠 GENERATING KNOWLEDGE NETWORK...")
    network_data = crawler.get_network_data()
    
    # Save the network
    with open('./data/wiki/intelligent_network.json', 'w') as f:
        json.dump(network_data, f, indent=2)
    
    print(f"✅ Network saved with:")
    print(f"   📄 {len(network_data['flashcards'])} flashcards")
    print(f"   🔗 {len(network_data['connections'])} connections")
    print(f"   🏆 Top concepts by reference count:")
    
    for concept, count in list(network_data['link_references'].items())[:10]:
        status = "✅" if concept in network_data['flashcards'] else "⏳"
        print(f"      {status} {concept}: {count} references")
    
    # Demonstrate network analysis
    print(f"\n🔬 NETWORK ANALYSIS:")
    wnet = WikiNet(filter_scientific=False)  # Don't re-filter
    
    # Convert crawler data to WikiNet format
    wnet.build_networkx_graph(network_data)
    analysis = wnet.analyze_network()
    
    print(f"   🔵 Network density: {analysis['density']:.3f}")
    print(f"   🔄 Average degree: {analysis['average_degree']:.2f}")
    print(f"   🌐 Connected: {analysis['is_connected']}")
    
    if 'most_central_nodes' in analysis:
        print(f"   ⭐ Most central concepts:")
        for node, centrality in analysis['most_central_nodes'][:5]:
            title = wnet.G.nodes[node]['title']
            print(f"      • {title}: {centrality:.3f}")
    
    print(f"\n💾 Crawler state saved - you can resume later with:")
    print(f"   crawler.crawl_continuously()")
    print(f"\n🎯 To explore the network interactively, use the WikiNet class!")


def resume_crawler():
    """Resume a previous crawling session."""
    print("🔄 RESUMING PREVIOUS CRAWLER SESSION")
    print("="*40)
    
    crawler = IntelligentWikiCrawler(filter_scientific=True)
    
    if crawler.stats['pages_processed'] > 0:
        print(f"Resuming from {crawler.stats['pages_processed']} processed pages")
        crawler.crawl_continuously(max_pages=100)
    else:
        print("No previous session found. Starting fresh...")
        demo_intelligent_crawler()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--resume":
        resume_crawler()
    else:
        demo_intelligent_crawler()