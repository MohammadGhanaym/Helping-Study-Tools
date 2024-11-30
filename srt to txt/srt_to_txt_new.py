#!/usr/bin/env python
# coding: utf-8

# In[2]:


import os


# In[ ]:





# In[3]:


def read_srtFile(file_path):
    subtitle = open(file_path, 'r')
    return subtitle.readlines()


# In[4]:


def srt_to_txt(lines):
    paragraph_lines = []
    for line in lines:
        if len(line) > 2:

            if line[0].isalpha() or line[1].isalpha():
                if '.' in line:
                    paragraph_lines.append(line)
                else:
                    paragraph_lines.append(line.replace('\n', ' '))
                    
    paragraph = ''.join(paragraph_lines)
    
    new_file = open(file_name, 'w')
    new_file.write(paragraph)
    new_file.close()


# In[5]:


again = 'y'


# In[6]:


while again.lower() == 'y':
    try:
        # Folder Path
        path = input("Enter Folder Path: ")
      
        # Change the directory
        os.chdir(path)
        
        # iterate through all file
        lines = []
        file_name = ''
        for file in os.listdir():
            try:
                # Check whether file is in text format or not
                if file.endswith(".srt") and 'lang_en' in file:
                    file_path = f"{path}\{file}"
        
                    file_name = file_path.split('\\')[-1].split('.srt')[0] + '.txt'
                    # call read text file function
                    lines = read_srtFile(file_path)
                    srt_to_txt(lines)
            except Exception as e:
                print(e)
                continue
                 
        again = input("Again? (y or n): ")
    except Exception as e:
        print(e)
        again = input("Again? (y or n): ")
