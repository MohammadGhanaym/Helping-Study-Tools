#!/usr/bin/env python
# coding: utf-8

# In[3]:


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


# Path to your Edge WebDriver
path = r"C:\Users\moham\Workplace\edgedriver_win64\msedgedriver.exe"

# Selenium setup
ser = Service(path)
options = webdriver.EdgeOptions()
options.add_argument('headless')
driver = webdriver.Edge(service=ser, options=options)


# Function to clean filenames
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name)  # Remove invalid characters


# Function to get video subtitles for a single video
def get_video_subtitles(video_id, video_title):
    try:
        sanitized_title = sanitize_filename(video_title)
        srt = YouTubeTranscriptApi.get_transcript(video_id)
        text = ''
        for idx, line in enumerate(srt):
            start_time = strftime("%H:%M:%S", gmtime(line['start']))
            end_time = strftime("%H:%M:%S", gmtime(line['start'] + line['duration']))
            text += f"{idx+1}\n{start_time} --> {end_time}\n{line['text']}\n\n"
        
        # Create subtitles directory if it doesn't exist
        os.makedirs('subtitles', exist_ok=True)
        with open(f'subtitles/{sanitized_title}.srt', 'w', encoding='utf-8') as file:
            file.write(text)
        print(f"Downloaded subtitles for {video_title}")
    except Exception as e:
        print(f"Error downloading subtitles for {video_title}: {e}")


# Function to get playlist subtitles
def get_playlist_subtitles(url):
    # Get playlist URL
    driver.get(url)
    driver.implicitly_wait(5)
    content = driver.page_source
    driver.quit()

    # Parse HTML content
    soup = bs(content, 'lxml')
    videos = soup.find_all('a', {'id': 'video-title'})
    
    video_id = []
    video_title = []
    
    # Extract video IDs and titles
    for idx, video in enumerate(videos):
        video_id.append(video['href'].split('&')[0].replace('/watch?v=', ''))
        video_title.append(str(idx+1) + ' - ' + video['title'].replace('|', '_').replace('/', '_'))
    
    # Download subtitles for each video in the playlist
    for title, id_ in tqdm(zip(video_title, video_id), total=len(video_title), desc="Downloading Subtitles"):
        get_video_subtitles(id_, title)


# Function to check if the URL is for a single video or playlist
def process_url(url):
    if "playlist" in url:  # Check if URL is for a playlist
        print("Processing Playlist...")
        get_playlist_subtitles(url)
    else:  # Assume it's a single video
        video_id = url.split('v=')[1]
        video_title = input('Enter video title: ')  # Ask user for the video title
        get_video_subtitles(video_id, video_title)


# Main function
if __name__ == "__main__":
    url = input('Enter URL (Playlist or Single Video): ')
    process_url(url)

