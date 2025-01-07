#!/usr/bin/env python
# coding: utf-8

# In[7]:


import os
import re

def read_srt_file(file_path):
    """
    Reads the lines of an SRT file.
    """
    with open(file_path, 'r', encoding='utf-8') as subtitle:
        return subtitle.readlines()

def extract_text_from_srt(lines):
    """
    Extracts text from SRT lines while ignoring numerical counters and timestamps.
    """
    paragraph_lines = []
    timestamp_pattern = re.compile(r'^\d{2}:\d{2}:\d{2} --> \d{2}:\d{2}:\d{2}')

    for line in lines:
        stripped_line = line.strip()
        # Ignore lines with timestamps
        if timestamp_pattern.match(stripped_line):
            continue
        # Ignore lines that are purely numeric counters
        if stripped_line.isdigit():
            continue
        # Append meaningful text
        if stripped_line:
            paragraph_lines.append(stripped_line)
    
    # Join all lines into a single paragraph
    paragraph = ' '.join(paragraph_lines)
    return paragraph

def srt_to_txt(file_path, output_file):
    """
    Converts SRT file to TXT file containing a single paragraph of text.
    """
    try:
        lines = read_srt_file(file_path)
        paragraph = extract_text_from_srt(lines)
        
        with open(output_file, 'w', encoding='utf-8') as new_file:
            new_file.write(paragraph)
        print(f"Converted: {file_path} -> {output_file}")
    except Exception as e:
        print(f"Error converting {file_path}: {e}")

def process_srt_files(folder_path, language_filter=None):
    """
    Processes SRT files in the folder based on the language filter.
    If no language filter is provided, processes all SRT files.
    """
    try:
        for file in os.listdir(folder_path):
            # Check if file is an SRT file and optionally matches the language filter
            if file.endswith(".srt") and (language_filter is None or language_filter in file):
                file_path = os.path.join(folder_path, file)
                output_file = os.path.join(folder_path, file.replace('.srt', '.txt'))
                srt_to_txt(file_path, output_file)
    except Exception as e:
        print(f"Error processing files: {e}")

if __name__ == "__main__":
    again = 'y'
    while again.lower() == 'y':
        folder_path = input("Enter Folder Path: ").strip()
        
        # Ask the user if there are multiple languages
        multiple_languages = input("Are there SRT files for multiple languages? (yes/no): ").strip().lower()
        
        if multiple_languages == 'yes':
            language_filter = input("Enter the language tag to filter files (e.g., 'lang_en'): ").strip()
            print(f"Processing files with the language tag '{language_filter}'...")
            process_srt_files(folder_path, language_filter)
        else:
            print("Processing all SRT files in the folder...")
            process_srt_files(folder_path)
        
        again = input("Again? (y or n): ").strip()

