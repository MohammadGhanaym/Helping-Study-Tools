#!/usr/bin/env python
# coding: utf-8

# In[19]:


from youtube_transcript_api import YouTubeTranscriptApi
from time import strftime
from time import gmtime


# In[37]:


from selenium import webdriver
from selenium.webdriver.edge.service import Service
from bs4 import BeautifulSoup as bs


# In[38]:


path = r"C:\Users\moham\Workplace\Freelancing\edgedriver_win64\msedgedriver.exe"

# In[39]:


ser = Service(path)
options = webdriver.EdgeOptions()
options.add_argument('headless')

driver = webdriver.Edge(service = ser, options=options)


# In[40]:


url = input('Enter Playlist URL: ')


# In[41]:


driver.get(url)
content = driver.page_source


# In[42]:


soup = bs(content)


# In[67]:


videos = soup.find_all('a', {'id': 'video-title'})
video_id = []
video_title = []
for idx, video in enumerate(videos):
    video_id.append(video['href'].split('&')[0].replace('/watch?v=', ''))
    video_title.append(str(idx+1) + ' - ' + video['title'].replace('|', '_'))


# In[71]:


for title, id_ in zip(video_title, video_id):
    srt = YouTubeTranscriptApi.get_transcript(video_id=id_)
    text = ''
    with open('{}.srt'.format(title), 'w') as file:
        for idx, line in enumerate(srt):
            text += str(idx+1) + '\n'
            start_time = strftime("%H:%M:%S", gmtime(line['start']))
            end_time = strftime("%H:%M:%S", gmtime(line['start'] + line['duration']))
            text += start_time +' --> '+ end_time
            text += '\n'
            text += line['text']
            text += '\n\n'
        file.write(text)

