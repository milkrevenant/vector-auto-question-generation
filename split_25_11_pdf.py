import os
import PyPDF2
import pdfplumber
import json
import re
from typing import Dict, List, Optional

def split_pdf(input_pdf: str, output_dir: str):
    """PDF를 페이지별로 분할"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Open the input PDF
    with open(input_pdf, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        num_pages = len(pdf_reader.pages)
        
        print(f"Total pages: {num_pages}")
        
        # Split each page
        for i in range(num_pages):
            pdf_writer = PyPDF2.PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[i])
            
            output_file = os.path.join(output_dir, f"25_11_page{i+1:02d}.pdf")
            with open(output_file, 'wb') as output:
                pdf_writer.write(output)
            print(f"Created: {output_file}")
    
    return num_pages

if __name__ == "__main__":
    # PDF 분할
    input_pdf = "pdforg/25_11.pdf"
    output_dir = "pdforg/25_11_split"
    
    num_pages = split_pdf(input_pdf, output_dir)
    print(f"\nSuccessfully split {input_pdf} into {num_pages} pages")