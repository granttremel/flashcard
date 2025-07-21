#!/usr/bin/env python3
"""
Demo of the new editor command system.

Available commands during field editing:

=== Field Commands ===
- wiki -w [concept]  : Open Wikipedia page  
- wiki -s [concept]  : Search Wikipedia
- wiki -g [concept]  : Generate and insert Wikipedia URL
- wiki -v            : Validate current Wiki URL
- skip               : Skip this field
- clear              : Clear this field
- last               : Go back to previous field

=== Card Navigation ===
- next               : Save and go to next incomplete card
- prev               : Save and go to previous card  
- done               : Save and exit editing
- help               : Show available commands

Example usage:
1. When editing the Wiki field, type: wiki -g
   This will generate a URL and ask if you want to use it

2. When editing any field, type: wiki -w lymph node
   This will open the Wikipedia page for "lymph node"

3. Type: help
   To see all available commands
"""

print(__doc__)

print("\nTo test the editor interactively, run:")
print("  python scripts/dev-flashcards01.py")
print("\nThe editor will prompt you to edit an incomplete card.")
print("Try using commands like 'wiki -g' or 'help' when editing fields!")