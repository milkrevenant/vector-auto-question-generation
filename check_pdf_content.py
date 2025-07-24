#!/usr/bin/env python3
import PyPDF2
import re
import os

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            text += f"\n\n--- Page {page_num + 1} ---\n"
            text += page.extract_text()
    return text

def find_question_numbers(text):
    """Find question numbers in the text"""
    # Pattern to match question numbers (e.g., "34.", "35.", etc.)
    pattern = r'\b(\d{1,2})\.\s'
    matches = re.findall(pattern, text)
    return [int(m) for m in matches]

def check_split_pdfs():
    """Check which split PDF contains question 35"""
    split_dir = "/Users/stillclie_mac/Documents/ug/snoriginal/23_11_split"
    
    print("Checking split PDFs for question numbers...\n")
    
    for filename in sorted(os.listdir(split_dir)):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(split_dir, filename)
            text = extract_text_from_pdf(pdf_path)
            question_numbers = find_question_numbers(text)
            
            unique_numbers = sorted(set(question_numbers))
            if unique_numbers:
                print(f"{filename}: Questions {min(unique_numbers)}-{max(unique_numbers)}")
                if 35 in unique_numbers:
                    print(f"  >>> Found question 35 in {filename}!")
            else:
                print(f"{filename}: No question numbers found")

if __name__ == "__main__":
    check_split_pdfs()