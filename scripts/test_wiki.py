
from flashcard import FlashcardCollection
from flashcard.quiz import FlashcardQuiz
from flashcard.wikipedia import WikiManager
from flashcard.wiki_parser import WikiParser
from flashcard.network import WikiNet

import requests
import os
import json

from pprint import pprint

def main():
    # Test with existing Pet_door example
    # demonstrate_parser("Autonomic_nervous_system")
    
    wman = WikiManager()
    pages = ('Carboniferous_rainforest_collapse',
                                      'Swim_bladder')
    # req = wman.build_api_request(titles = pages)
    # res = requests.get(req, he1aders=wman.hdrs)
    res = wman.fetch_wikipedia_pages(pages)
    
    pprint(res)
    # print(type(res))
    
    
    # print(req)
    
    
    
    # wnet = WikiNet()
    # net = wnet.build_flashcard_network('Greater_omentum', depth = 2, max_pages = 200)
    
    # wnet.visualize_network(net)
    # wnet.analyze_network()
    # wnet.visualize_networkx_graph()
    # wnet.create_concept_map()

if __name__ == "__main__":
    main()