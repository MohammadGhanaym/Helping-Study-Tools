#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

import re
import os
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import timedelta
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from bs4 import BeautifulSoup as bs

class SubtitleDownloader:
    def __init__(self, driver_path):
        self.driver_path = driver_path
        self.setup_driver()

    def setup_driver(self):
        """Initialize the web driver with headless options"""
        self.ser = Service(self.driver_path)
        self.options = webdriver.EdgeOptions()
        self.options.add_argument('headless')
        self.driver = webdriver.Edge(service=self.ser, options=self.options)

    def sanitize_filename(self, name):
        """Clean filename by removing invalid characters"""
        return re.sub(r'[<>:"/\\|?*]', '', name)

    def format_timecode(self, seconds):
        """Convert seconds to SRT timecode format (HH:MM:SS,mmm)"""
        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        seconds = td.seconds % 60
        milliseconds = round(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def get_video_subtitles(self, video_id, video_title):
        """Download and save subtitles for a single video in standard SRT format"""
        try:
            sanitized_title = self.sanitize_filename(video_title)
            srt = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Create standard SRT format
            srt_content = []
            for idx, line in enumerate(srt, 1):
                start_time = self.format_timecode(line['start'])
                end_time = self.format_timecode(line['start'] + line['duration'])
                
                # Proper SRT entry format
                srt_entry = f"{idx}\n{start_time} --> {end_time}\n{line['text']}\n"
                srt_content.append(srt_entry)

            # Create subtitles directory if it doesn't exist
            os.makedirs('subtitles', exist_ok=True)
            
            # Write to file with proper encoding
            with open(f'subtitles/{sanitized_title}.srt', 'w', encoding='utf-8') as file:
                file.write('\n'.join(srt_content))
            
            print(f"✓ Successfully downloaded subtitles for: {video_title}")
            return True
        except Exception as e:
            print(f"✗ Error downloading subtitles for {video_title}: {str(e)}")
            return False

    def get_playlist_subtitles(self, url):
        """Download subtitles for all videos in a playlist"""
        try:
            self.driver.get(url)
            self.driver.implicitly_wait(5)
            content = self.driver.page_source
            
            # Parse HTML content
            soup = bs(content, 'lxml')
            videos = soup.find_all('a', {'id': 'video-title'})
            
            if not videos:
                print("No videos found in the playlist. Please check the URL.")
                return False

            video_data = []
            for idx, video in enumerate(videos, 1):
                video_id = video['href'].split('&')[0].replace('/watch?v=', '')
                video_title = f"{idx:02d} - {video['title'].replace('|', '_').replace('/', '_')}"
                video_data.append((video_id, video_title))

            # Download subtitles for each video
            success_count = 0
            with tqdm(total=len(video_data), desc="Downloading Playlist Subtitles") as pbar:
                for vid_id, title in video_data:
                    if self.get_video_subtitles(vid_id, title):
                        success_count += 1
                    pbar.update(1)

            print(f"\nDownloaded {success_count}/{len(video_data)} subtitle files")
            return True
        except Exception as e:
            print(f"Error processing playlist: {str(e)}")
            return False
        finally:
            self.driver.quit()

    def process_url(self, url):
        """Process URL for either single video or playlist"""
        try:
            if "playlist" in url:
                print("\nProcessing Playlist...")
                return self.get_playlist_subtitles(url)
            else:
                try:
                    video_id = url.split('v=')[1].split('&')[0]  # Handle additional parameters
                    video_title = input('Enter video title: ').strip()
                    if not video_title:
                        print("Error: Video title cannot be empty")
                        return False
                    return self.get_video_subtitles(video_id, video_title)
                except IndexError:
                    print("Error: Invalid YouTube URL format")
                    return False
        except Exception as e:
            print(f"Error processing URL: {str(e)}")
            return False

def main():
    # Path to Edge WebDriver
    driver_path = r"C:\Users\moham\Workplace\edgedriver_win64\msedgedriver.exe"
    downloader = SubtitleDownloader(driver_path)

    while True:
        print("\n=== YouTube Subtitle Downloader ===")
        url = input('Enter YouTube URL (Playlist or Single Video): ').strip()
        
        if not url:
            print("Error: URL cannot be empty")
            continue

        downloader.process_url(url)

        # Ask if user wants to download more
        while True:
            choice = input('\nDo you want to download more subtitles? (y/n): ').lower().strip()
            if choice in ['y', 'n']:
                break
            print("Please enter 'y' for yes or 'n' for no")

        if choice == 'n':
            print("Thank you for using YouTube Subtitle Downloader!")
            break

if __name__ == "__main__":
    main()


# In[ ]:




