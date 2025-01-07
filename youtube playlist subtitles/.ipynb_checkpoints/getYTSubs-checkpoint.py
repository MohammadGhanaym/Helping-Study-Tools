#!/usr/bin/env python
# coding: utf-8

# In[7]:


#!/usr/bin/env python
# coding: utf-8
import re
import os
from youtube_transcript_api import YouTubeTranscriptApi
from time import strftime, gmtime
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from bs4 import BeautifulSoup as bs


# In[8]:


# Path to your Edge WebDriver
path = r"C:\Users\moham\Workplace\edgedriver_win64\msedgedriver.exe"

# Selenium setup
ser = Service(path)
options = webdriver.EdgeOptions()
options.add_argument('headless')
driver = webdriver.Edge(service=ser, options=options)


# In[9]:


# Get playlist URL
url = input('Enter Playlist URL: ')
driver.get(url)
driver.implicitly_wait(5)
content = driver.page_source
driver.quit()


# In[10]:


# Parse HTML content
soup = bs(content, 'lxml')


# In[11]:


# Function to clean filenames
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name)  # Remove invalid characters


# In[12]:


# Function to get playlist subtitles
def get_playlist_subtitles():
    videos = soup.find_all('a', {'id': 'video-title'})
    video_id = []
    video_title = []
    
    # Extract video IDs and titles
    for idx, video in enumerate(videos):
        video_id.append(video['href'].split('&')[0].replace('/watch?v=', ''))
        video_title.append(str(idx+1) + ' - ' + video['title'].replace('|', '_').replace('/', '_'))
    
    # Create subtitles directory if it doesn't exist
    os.makedirs('subtitles', exist_ok=True)
    
    # Download subtitles for each video
    for title, id_ in tqdm(zip(video_title, video_id), total=len(video_title), desc="Downloading Subtitles"):
        try:
            # Sanitize the title for the file name
            sanitized_title = sanitize_filename(title)
            srt = YouTubeTranscriptApi.get_transcript(video_id=id_)
            text = ''
            with open(f'subtitles/{sanitized_title}.srt', 'w', encoding='utf-8') as file:
                for idx, line in enumerate(srt):
                    text += f"{idx+1}\n"
                    start_time = strftime("%H:%M:%S", gmtime(line['start']))
                    end_time = strftime("%H:%M:%S", gmtime(line['start'] + line['duration']))
                    text += f"{start_time} --> {end_time}\n"
                    text += f"{line['text']}\n\n"
                file.write(text)
        except Exception as e:
            print(f"Error downloading subtitles for {title}: {e}")
            

            


# In[13]:


# Run the function
get_playlist_subtitles()

