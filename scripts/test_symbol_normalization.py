#!/usr/bin/env python3

from flashcard.symbol_normalization import SymbolNormalizer

def main():
    normalizer = SymbolNormalizer()
    
    # Test cases covering the capitalization issues you mentioned
    test_symbols = [
        # Abbreviations that should stay uppercase
        "wbc", "WBC", "Wbc",
        "dna", "DNA", "rbc", "atp",
        
        # Regular biological terms
        "basophil", "BASOPHIL", "Basophil",
        "t-cell", "T-Cell", "T-CELL",
        
        # Mixed case terms
        "panck", "PanCK", "PANCK", "pancytokeratin",
        "ph", "pH", "PH",
        
        # Complex terms
        "helper t-cell", "HELPER T-CELL", "Helper T-Cell",
        "cd8", "CD8", "Cd8",
        "il-2", "IL-2", "interleukin-2",
        
        # Edge cases
        "B-cell receptor", "b-cell receptor", "BCR",
        "autonomic nervous system", "AUTONOMIC NERVOUS SYSTEM"
    ]
    
    print("=== Symbol Normalization Tests ===\n")
    
    for symbol in test_symbols:
        normalized = normalizer.normalize_symbol(symbol)
        if normalized != symbol:
            print(f"'{symbol}' → '{normalized}'")
        else:
            print(f"'{symbol}' (no change)")
    
    print("\n=== Similarity Testing ===\n")
    
    # Test similarity matching
    existing_symbols = {
        "WBC", "Basophil", "T-cell", "Helper T-cell", "Macrophage", 
        "Lymphocyte", "Neutrophil", "DNA", "RNA", "ATP"
    }
    
    test_queries = ["wbc", "basofil", "t cell", "helper t", "macrofage", "limfocyte"]
    
    for query in test_queries:
        suggestions = normalizer.find_similar_symbols(query, existing_symbols, threshold=0.5)
        print(f"'{query}' suggestions:")
        for symbol, score in suggestions:
            print(f"  {symbol} ({score:.2f})")
        print()

if __name__ == "__main__":
    main()