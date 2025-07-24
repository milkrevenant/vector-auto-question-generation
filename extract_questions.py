#!/usr/bin/env python3
import PyPDF2
import re
import json
import os

def extract_text_from_pdf(pdf_path, start_page=None, end_page=None):
    """Extract text from specific pages of PDF"""
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf = PyPDF2.PdfReader(file)
        start = start_page if start_page else 0
        end = end_page if end_page else len(pdf.pages)
        
        for page_num in range(start, min(end, len(pdf.pages))):
            page = pdf.pages[page_num]
            text += page.extract_text() + "\n"
    return text

def find_question_35_onwards(text):
    """Find question 35 and subsequent questions"""
    # Try to find pattern like "35. " at the beginning of a line
    # Split text into lines and look for question patterns
    lines = text.split('\n')
    
    questions = {}
    current_question = None
    current_content = []
    
    for line in lines:
        # Check if line starts with a question number (35 or higher)
        match = re.match(r'^(\d{2})\.\s*(.*)$', line.strip())
        if match:
            num = int(match.group(1))
            if num >= 35:
                # Save previous question if exists
                if current_question:
                    questions[current_question] = '\n'.join(current_content)
                
                current_question = num
                current_content = [match.group(2)]
        elif current_question:
            # Continue collecting content for current question
            current_content.append(line)
    
    # Don't forget the last question
    if current_question:
        questions[current_question] = '\n'.join(current_content)
    
    return questions

def analyze_pdfs_for_question_35():
    """Analyze PDFs to find question 35"""
    split_dir = "/Users/stillclie_mac/Documents/ug/snoriginal/23_11_split"
    
    # Based on previous analysis, check these files
    target_files = ["23_11_part04.pdf", "23_11_part05.pdf", "23_11_part09.pdf", "23_11_part10.pdf"]
    
    for filename in target_files:
        pdf_path = os.path.join(split_dir, filename)
        print(f"\nAnalyzing {filename}...")
        
        text = extract_text_from_pdf(pdf_path)
        
        # Save text to file for manual inspection
        text_file = pdf_path.replace('.pdf', '_text.txt')
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"  Saved text to: {text_file}")
        
        # Try to find question 35
        questions = find_question_35_onwards(text)
        if questions:
            print(f"  Found questions: {list(questions.keys())}")
            if 35 in questions:
                print(f"  Question 35 preview: {questions[35][:100]}...")

if __name__ == "__main__":
    analyze_pdfs_for_question_35()