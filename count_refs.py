#!/usr/bin/env python
import json

with open('test_reference_output/combined_references.json', 'r') as f:
    data = json.load(f)
    refs = data.get("references", [])
    print(f"Total references: {len(refs)}")
    
    # Print first and last reference
    if refs:
        print("\nFirst reference:")
        print(f"Title: {refs[0].get('title')}")
        print(f"Authors: {refs[0].get('authors')}")
        
        print("\nLast reference:")
        print(f"Title: {refs[-1].get('title')}")
        print(f"Authors: {refs[-1].get('authors')}") 