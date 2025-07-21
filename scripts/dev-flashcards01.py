
from flashcard import FlashcardCollection, Flashcard
from flashcard.edit import FlashcardEditor

from pprint import pprint

fcpath = r"~/Documents/flashcards_short.ods"

sn = 'anatomy'

clc = FlashcardCollection()
clc.load_from_excel(fcpath, sheet_name = 'anatomy')

pprint(vars(clc))

# for ff in clc.cards:
#     print(ff)
