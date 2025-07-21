
from flashcard import FlashcardCollection, Flashcard
from flashcard.edit import FlashcardEditor
from flashcard.quiz import start_interactive_quiz

from pprint import pprint

fcpath = r"./data/flashcards.ods"

sn = 'anatomy'

clc = FlashcardCollection()
clc.load_from_excel(fcpath, domain_name = "anatomy", sheet_name = 'anatomy')

# editor = FlashcardEditor(clc)
# editor.edit_incomplete_cards('anatomy')

start_interactive_quiz(clc)

# incomplete_cards = clc.get_incomplete_cards()
# if incomplete_cards:
#     print(f"\nTesting editor with card: {incomplete_cards[0].concept}")
#     # Uncomment to test interactive editing:
#     editor.edit_card(incomplete_cards[0].concept)
    
