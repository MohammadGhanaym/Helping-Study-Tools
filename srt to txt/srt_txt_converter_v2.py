#!/usr/bin/env python
# coding: utf-8

# In[2]:


import os
import re
from typing import List, Optional

def read_srt_file(file_path: str) -> List[str]:
    """
    Reads the lines of an SRT file.
    
    Args:
        file_path (str): Path to the SRT file
        
    Returns:
        List[str]: Lines from the SRT file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        UnicodeDecodeError: If the file encoding is not UTF-8
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as subtitle:
            return subtitle.readlines()
    except UnicodeDecodeError:
        # Fallback to latin-1 encoding if UTF-8 fails
        with open(file_path, 'r', encoding='latin-1') as subtitle:
            return subtitle.readlines()

def extract_text_from_srt(lines: List[str]) -> str:
    """
    Extracts text from SRT lines while ignoring numerical counters and timestamps.
    
    Args:
        lines (List[str]): Lines from the SRT file
        
    Returns:
        str: Extracted text as a single paragraph
    """
    paragraph_lines = []
    # Updated timestamp pattern to handle more format variations
    timestamp_pattern = re.compile(r'^\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}')
    
    for line in lines:
        stripped_line = line.strip()
        # Skip empty lines
        if not stripped_line:
            continue
        # Skip timestamp lines
        if timestamp_pattern.match(stripped_line):
            continue
        # Skip subtitle number lines
        if stripped_line.isdigit():
            continue
        # Skip lines with common subtitle formatting tags
        if re.match(r'^<.*>$', stripped_line):
            continue
        # Remove any HTML-style formatting tags
        cleaned_line = re.sub(r'<[^>]+>', '', stripped_line)
        # Append meaningful text
        if cleaned_line:
            paragraph_lines.append(cleaned_line)
    
    # Join lines with proper spacing
    paragraph = ' '.join(paragraph_lines)
    # Clean up multiple spaces
    paragraph = re.sub(r'\s+', ' ', paragraph)
    return paragraph.strip()

def srt_to_txt(file_path: str, output_file: str) -> bool:
    """
    Converts SRT file to TXT file containing a single paragraph of text.
    
    Args:
        file_path (str): Path to the input SRT file
        output_file (str): Path for the output TXT file
        
    Returns:
        bool: True if conversion was successful, False otherwise
    """
    try:
        lines = read_srt_file(file_path)
        paragraph = extract_text_from_srt(lines)
        
        if not paragraph:
            print(f"Warning: No text content extracted from {file_path}")
            return False
            
        with open(output_file, 'w', encoding='utf-8') as new_file:
            new_file.write(paragraph)
        print(f"Successfully converted: {file_path} -> {output_file}")
        return True
    except Exception as e:
        print(f"Error converting {file_path}: {str(e)}")
        return False

def process_srt_files(folder_path: str, language_filter: Optional[str] = None) -> None:
    """
    Processes SRT files in the folder based on the language filter.
    
    Args:
        folder_path (str): Path to the folder containing SRT files
        language_filter (Optional[str]): Language tag to filter files (e.g., 'lang_en')
    """
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a valid directory")
        return
        
    try:
        processed_files = 0
        successful_conversions = 0
        
        for file in os.listdir(folder_path):
            if file.endswith(".srt") and (language_filter is None or language_filter in file):
                processed_files += 1
                file_path = os.path.join(folder_path, file)
                output_file = os.path.join(folder_path, file.replace('.srt', '.txt'))
                
                if srt_to_txt(file_path, output_file):
                    successful_conversions += 1
        
        if processed_files == 0:
            print(f"No matching SRT files found in {folder_path}")
            if language_filter:
                print(f"Note: Using language filter '{language_filter}'")
        else:
            print(f"\nProcessing complete:")
            print(f"Total files processed: {processed_files}")
            print(f"Successful conversions: {successful_conversions}")
            print(f"Failed conversions: {processed_files - successful_conversions}")
            
    except Exception as e:
        print(f"Error processing files: {str(e)}")

def main():
    while True:
        folder_path = input("Enter Folder Path (or 'q' to quit): ").strip()
        
        if folder_path.lower() == 'q':
            break
            
        if not os.path.isdir(folder_path):
            print(f"Error: '{folder_path}' is not a valid directory")
            continue
            
        multiple_languages = input("Are there SRT files for multiple languages? (yes/no): ").strip().lower()
        
        if multiple_languages == 'yes':
            language_filter = input("Enter the language tag to filter files (e.g., 'lang_en'): ").strip()
            print(f"\nProcessing files with the language tag '{language_filter}'...")
            process_srt_files(folder_path, language_filter)
        else:
            print("\nProcessing all SRT files in the folder...")
            process_srt_files(folder_path)
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()

