#!/usr/bin/env python3
import os
import re

def search_language_media_in_texts():
    """Search for 언어와 매체 (Language and Media) sections in text files"""
    split_dir = "/Users/stillclie_mac/Documents/ug/snoriginal/23_11_split"
    
    print("Searching for '언어와 매체' sections in text files...\n")
    
    for filename in sorted(os.listdir(split_dir)):
        if filename.endswith('_text.txt'):
            file_path = os.path.join(split_dir, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Search for 언어와 매체
            if '언어와 매체' in content or '언어와매체' in content:
                print(f"\n{'='*50}")
                print(f"Found '언어와 매체' in: {filename}")
                print(f"{'='*50}")
                
                # Find context around 언어와 매체
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '언어와 매체' in line or '언어와매체' in line:
                        # Print surrounding lines for context
                        start = max(0, i-5)
                        end = min(len(lines), i+10)
                        print("\nContext:")
                        for j in range(start, end):
                            print(f"{j:4d}: {lines[j]}")
                        print()

if __name__ == "__main__":
    search_language_media_in_texts()