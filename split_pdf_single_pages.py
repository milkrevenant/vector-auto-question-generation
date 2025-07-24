#!/usr/bin/env python3
import PyPDF2
import sys
import os

def split_pdf_by_single_pages(pdf_path):
    """Split PDF into single page files"""
    with open(pdf_path, 'rb') as file:
        pdf = PyPDF2.PdfReader(file)
        total_pages = len(pdf.pages)
        
        base_name = os.path.splitext(pdf_path)[0]
        output_dir = f"{base_name}_split"
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Splitting {pdf_path} into {total_pages} single-page files...")
        
        for page_num in range(total_pages):
            writer = PyPDF2.PdfWriter()
            writer.add_page(pdf.pages[page_num])
            
            # Format: XX_XX_pageYY.pdf
            output_file = os.path.join(output_dir, f"{os.path.basename(base_name)}_page{page_num+1:02d}.pdf")
            with open(output_file, 'wb') as output:
                writer.write(output)
            
            if (page_num + 1) % 10 == 0:
                print(f"Progress: {page_num + 1}/{total_pages} pages processed")
        
        print(f"\nCompleted! All {total_pages} pages saved in: {output_dir}")
        return output_dir, total_pages

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default to 24_11.pdf
        pdf_path = "/Users/stillclie_mac/Documents/ug/snoriginal/24_11.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found!")
        sys.exit(1)
    
    split_pdf_by_single_pages(pdf_path)