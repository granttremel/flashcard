
from flashcard import FlashcardCollection, Flashcard
from flashcard.edit import FlashcardEditor

from pprint import pprint

fcpath = r"./data/flashcards.ods"

sn = 'anatomy'

clc = FlashcardCollection()
clc.load_from_excel(fcpath, domain_name = "anatomy", sheet_name = 'anatomy')

for c in clc.cards:
    print(clc.cards[c])
    
    break
    
