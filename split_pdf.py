#!/usr/bin/env python3
import PyPDF2
import sys
import os

def get_pdf_info(pdf_path):
    """Get information about PDF file"""
    with open(pdf_path, 'rb') as file:
        pdf = PyPDF2.PdfReader(file)
        num_pages = len(pdf.pages)
        file_size = os.path.getsize(pdf_path)
        print(f"File: {pdf_path}")
        print(f"Total pages: {num_pages}")
        print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
        print(f"Average page size: {file_size/num_pages:,.0f} bytes")
        return num_pages

def split_pdf(pdf_path, pages_per_split=10):
    """Split PDF into smaller files"""
    with open(pdf_path, 'rb') as file:
        pdf = PyPDF2.PdfReader(file)
        total_pages = len(pdf.pages)
        
        # Calculate number of splits needed
        num_splits = (total_pages + pages_per_split - 1) // pages_per_split
        
        base_name = os.path.splitext(pdf_path)[0]
        output_dir = f"{base_name}_split"
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nSplitting into {num_splits} files ({pages_per_split} pages each)...")
        
        for i in range(num_splits):
            writer = PyPDF2.PdfWriter()
            start_page = i * pages_per_split
            end_page = min((i + 1) * pages_per_split, total_pages)
            
            for page_num in range(start_page, end_page):
                writer.add_page(pdf.pages[page_num])
            
            output_file = os.path.join(output_dir, f"{os.path.basename(base_name)}_part{i+1:02d}.pdf")
            with open(output_file, 'wb') as output:
                writer.write(output)
            
            file_size = os.path.getsize(output_file)
            print(f"Created: {output_file} (pages {start_page+1}-{end_page}, {file_size/1024:.1f} KB)")
        
        print(f"\nAll parts saved in: {output_dir}")

if __name__ == "__main__":
    pdf_path = "/Users/stillclie_mac/Documents/ug/snoriginal/23_11.pdf"
    
    # First get info about the PDF
    num_pages = get_pdf_info(pdf_path)
    
    # Suggest split size based on file size
    # 4.4MB for entire PDF, let's aim for ~500KB per split
    suggested_pages = max(1, num_pages // 9)
    
    print(f"\nSuggested pages per split: {suggested_pages} (for ~500KB per file)")
    print("You can modify the 'pages_per_split' parameter in the split_pdf() function")
    
    # Split the PDF
    split_pdf(pdf_path, pages_per_split=suggested_pages)