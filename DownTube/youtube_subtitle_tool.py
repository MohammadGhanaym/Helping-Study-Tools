#!/usr/bin/env python
# coding: utf-8
"""
YouTube Subtitle Tool - Unified Subtitle Downloader and Converter
Features:
- Download subtitles from YouTube videos or playlists
- Convert SRT files to clean text format
- Batch processing capabilities
- User-friendly menu interface
- Multiple language support
"""

import re
import os
import sys
import time
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from datetime import timedelta
from tqdm import tqdm
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup as bs
from typing import List, Optional, Dict, Tuple

# Import selenium components with error handling
try:
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    print("Warning: Selenium not found. Playlist functionality will be limited.")
    SELENIUM_AVAILABLE = False

# Define language codes for common languages
LANGUAGE_CODES = {
    'English': 'en',
    'Spanish': 'es',
    'French': 'fr',
    'German': 'de',
    'Chinese': 'zh',
    'Japanese': 'ja',
    'Korean': 'ko',
    'Arabic': 'ar',
    'Russian': 'ru',
    'Portuguese': 'pt',
    'Auto-generated': 'a.en'  # Common for auto-generated English subtitles
}

class YouTubeSubtitleTool:
    def __init__(self, driver_path=r"..\edgedriver_win64\msedgedriver.exe"):
        self.driver_path = driver_path
        self.subtitles_dir = "subtitles"
        self.text_dir = "text_files"
        self.driver = None
        self.preferred_language = "en"  # Default to English
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories"""
        os.makedirs(self.subtitles_dir, exist_ok=True)
        os.makedirs(self.text_dir, exist_ok=True)

    def setup_driver(self):
        """Initialize the web driver with headless options"""
        if not SELENIUM_AVAILABLE:
            print("Error: Selenium is not available. Please install it with 'pip install selenium'")
            return False
            
        try:
            # Check if driver path exists
            if not os.path.exists(self.driver_path):
                print(f"Error: WebDriver not found at {self.driver_path}")
                driver_dir = os.path.dirname(self.driver_path)
                if os.path.exists(driver_dir):
                    print(f"Available files in driver directory:")
                    for f in os.listdir(driver_dir):
                        print(f"  - {f}")
                return False
                
            self.ser = Service(self.driver_path)
            self.options = webdriver.EdgeOptions()
            self.options.add_argument('--headless')
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-gpu')
            self.options.add_argument('--window-size=1920,1080')
            self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            self.driver = webdriver.Edge(service=self.ser, options=self.options)
            return True
        except Exception as e:
            print(f"Error setting up web driver: {str(e)}")
            print("Make sure Edge WebDriver is properly installed and the path is correct.")
            return False

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

    def get_video_subtitles(self, video_id, video_title, language=None):
        """
        Download and save subtitles for a single video in standard SRT format
        
        Args:
            video_id: YouTube video ID
            video_title: Title for the saved subtitle file
            language: Language code (e.g., 'en' for English)
            
        Returns:
            Path to saved subtitle file or None if failed
        """
        if language is None:
            language = self.preferred_language
            
        sanitized_title = self.sanitize_filename(video_title)
        
        try:
            # First try with specific language
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Try to find manual subtitles in the preferred language
                try:
                    transcript = transcript_list.find_manually_created_transcript([language])
                except NoTranscriptFound:
                    # If no manual transcript, try auto-generated
                    try:
                        transcript = transcript_list.find_generated_transcript([language])
                    except NoTranscriptFound:
                        # If no auto-generated in preferred language, try English
                        if language != 'en':
                            try:
                                transcript = transcript_list.find_manually_created_transcript(['en'])
                            except NoTranscriptFound:
                                try:
                                    transcript = transcript_list.find_generated_transcript(['en'])
                                except NoTranscriptFound:
                                    # Just get the first available transcript
                                    transcript = list(transcript_list)[0]
                        else:
                            # If language was already English and nothing found, get the first available
                            transcript = list(transcript_list)[0]
                
                # Now fetch the actual transcript
                srt = transcript.fetch()
                lang_used = transcript.language_code
                
            except Exception as e:
                # Fallback to direct transcript retrieval
                srt = YouTubeTranscriptApi.get_transcript(video_id, languages=[language, 'en'])
                lang_used = language
                
            # Create standard SRT format
            srt_content = []
            for idx, line in enumerate(srt, 1):
                start_time = self.format_timecode(line['start'])
                end_time = self.format_timecode(line['start'] + line['duration'])
                
                # Proper SRT entry format
                srt_entry = f"{idx}\n{start_time} --> {end_time}\n{line['text']}\n"
                srt_content.append(srt_entry)

            # Include language code in filename
            srt_path = os.path.join(self.subtitles_dir, f'{sanitized_title}_{lang_used}.srt')
            with open(srt_path, 'w', encoding='utf-8') as file:
                file.write('\n'.join(srt_content))
            
            print(f"✓ Successfully downloaded subtitles for: {video_title} (Language: {lang_used})")
            return srt_path
            
        except NoTranscriptFound:
            print(f"✗ No subtitles found for {video_title} in language '{language}'.")
            return None
        except TranscriptsDisabled:
            print(f"✗ Subtitles are disabled for {video_title}.")
            return None
        except Exception as e:
            print(f"✗ Error downloading subtitles for {video_title}: {str(e)}")
            print(f"  Video ID: {video_id}")
            return None

    def get_video_info(self, video_id):
        """Get video information directly from YouTube page"""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
            response = requests.get(url, headers=headers)
            soup = bs(response.text, 'html.parser')
            
            # Get title
            title = soup.find('title')
            if title:
                title_text = title.text.replace(' - YouTube', '').strip()
                return {'title': title_text}
            return {'title': f"Video_{video_id}"}
        except Exception as e:
            print(f"Error getting video info: {str(e)}")
            return {'title': f"Video_{video_id}"}

    def get_playlist_videos_without_selenium(self, url):
        """
        Alternative method to get playlist videos without using Selenium
        Using YouTube's API
        """
        try:
            # Extract playlist ID
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            playlist_id = query_params.get('list', [None])[0]
            
            if not playlist_id:
                print("Error: Could not extract playlist ID from URL")
                return []
                
            # The API URL to fetch playlist items
            api_url = f"https://www.youtube.com/playlist?list={playlist_id}"
            
            # Send request and get HTML content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            response = requests.get(api_url, headers=headers)
            
            if response.status_code != 200:
                print(f"Error: Failed to fetch playlist, status code: {response.status_code}")
                return []
                
            soup = bs(response.text, 'html.parser')
            
            # Parse video information
            video_data = []
            idx = 1
            
            # Try different selector patterns
            selectors = [
                'a.ytd-playlist-video-renderer', 
                'a.yt-simple-endpoint',
                'a#video-title'
            ]
            
            for selector in selectors:
                videos = soup.select(selector)
                if videos:
                    break
                    
            if not videos:
                print("Error: Could not find videos in the playlist HTML")
                return []
                
            for video in videos:
                href = video.get('href', '')
                title = video.get('title', f'Video {idx}')
                
                if href and '/watch?v=' in href:
                    video_id = href.split('v=')[1].split('&')[0]
                    video_data.append((video_id, f"{idx:02d} - {title.replace('|', '_').replace('/', '_')}"))
                    idx += 1
                    
            return video_data
            
        except Exception as e:
            print(f"Error extracting playlist videos: {str(e)}")
            return []

    def get_playlist_subtitles(self, url):
        """Download subtitles for all videos in a playlist"""
        # Ask for language preference
        print("\nSelect subtitle language for all videos:")
        print("1. English (default)")
        print("2. Spanish")
        print("3. French")
        print("4. German")
        print("5. Chinese")
        print("6. Other")
        
        lang_choice = input("Choose language (1-6, default: 1): ").strip() or "1"
        
        language = "en"  # Default to English
        if lang_choice == "2":
            language = "es"
        elif lang_choice == "3":
            language = "fr"
        elif lang_choice == "4":
            language = "de"
        elif lang_choice == "5":
            language = "zh"
        elif lang_choice == "6":
            print("\nAvailable language codes: en, es, fr, de, zh, ja, ko, ar, ru, pt")
            language = input("Enter language code: ").strip() or "en"
        
        try:
            # Try to use Selenium first
            use_selenium = False
            if SELENIUM_AVAILABLE and use_selenium:
                if not self.setup_driver():
                    print("Falling back to non-Selenium method...")
                    video_data = self.get_playlist_videos_without_selenium(url)
                else:
                    try:
                        self.driver.get(url)
                        self.driver.implicitly_wait(10)
                        
                        # Wait for the playlist to load
                        try:
                            WebDriverWait(self.driver, 20).until(
                                EC.presence_of_element_located((By.ID, "video-title"))
                            )
                        except TimeoutException:
                            print("Warning: Timed out waiting for video titles to load")
                        
                        # Give it another second to fully load
                        time.sleep(1)
                        
                        content = self.driver.page_source
                        soup = bs(content, 'html.parser')
                        videos = soup.find_all('a', {'id': 'video-title'})
                        
                        if not videos:
                            print("No videos found with Selenium method, trying alternate selectors...")
                            videos = soup.select('a.ytd-playlist-video-renderer') or soup.select('a.yt-simple-endpoint')
                        
                        if not videos:
                            print("No videos found in the playlist using Selenium. Falling back to non-Selenium method...")
                            video_data = self.get_playlist_videos_without_selenium(url)
                        else:
                            video_data = []
                            for idx, video in enumerate(videos, 1):
                                href = video.get('href', '')
                                if href and '/watch?v=' in href:
                                    video_id = href.split('v=')[1].split('&')[0]
                                    title = video.get('title', f'Video {idx}')
                                    video_data.append((video_id, f"{idx:02d} - {title.replace('|', '_').replace('/', '_')}"))
                    except Exception as e:
                        print(f"Error with Selenium: {str(e)}")
                        print("Falling back to non-Selenium method...")
                        video_data = self.get_playlist_videos_without_selenium(url)
                    finally:
                        if hasattr(self, 'driver') and self.driver:
                            self.driver.quit()
            else:
                # Use non-Selenium method
                video_data = self.get_playlist_videos_without_selenium(url)
            
            if not video_data:
                print("No videos found in the playlist. Please check the URL.")
                return []
                
            print(f"Found {len(video_data)} videos in playlist.")

            # Download subtitles for each video
            downloaded_files = []
            with tqdm(total=len(video_data), desc="Downloading Playlist Subtitles") as pbar:
                for vid_id, title in video_data:
                    file_path = self.get_video_subtitles(vid_id, title, language)
                    if file_path:
                        downloaded_files.append(file_path)
                    pbar.update(1)
                    
                    # Add a short delay to avoid API rate limiting
                    time.sleep(0.5)

            print(f"\nDownloaded {len(downloaded_files)}/{len(video_data)} subtitle files")
            return downloaded_files
        except Exception as e:
            print(f"Error processing playlist: {str(e)}")
            return []
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()

    def process_video_url(self, url):
        """Process URL for a single video"""
        video_id = self.extract_video_id(url)
        
        if not video_id:
            print("Error: Could not extract video ID from URL. Please check the URL format.")
            return []
            
        video_title = input('Enter video title: ').strip()
        if not video_title:
            print("Error: Video title cannot be empty")
            return []
            
        # Ask for language preference
        print("\nSelect subtitle language:")
        print("1. English (default)")
        print("2. Spanish")
        print("3. French")
        print("4. German")
        print("5. Chinese")
        print("6. Other")
        
        lang_choice = input("Choose language (1-6, default: 1): ").strip() or "1"
        
        language = "en"  # Default to English
        if lang_choice == "2":
            language = "es"
        elif lang_choice == "3":
            language = "fr"
        elif lang_choice == "4":
            language = "de"
        elif lang_choice == "5":
            language = "zh"
        elif lang_choice == "6":
            print("\nAvailable language codes: en, es, fr, de, zh, ja, ko, ar, ru, pt")
            language = input("Enter language code: ").strip() or "en"
        
        file_path = self.get_video_subtitles(video_id, video_title, language)
        return [file_path] if file_path else []

    def extract_video_id(self, url):
        """
        Extract video ID from different YouTube URL formats
        
        Handles formats like:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/v/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        """
        try:
            # Parse the URL
            parsed_url = urlparse(url)
            
            # youtube.com/watch?v=ID format
            if parsed_url.hostname in ['www.youtube.com', 'youtube.com', 'm.youtube.com']:
                if parsed_url.path == '/watch':
                    query_params = parse_qs(parsed_url.query)
                    return query_params.get('v', [None])[0]
                elif parsed_url.path.startswith(('/v/', '/embed/')):
                    return parsed_url.path.split('/')[2]
                    
            # youtu.be/ID format
            elif parsed_url.hostname == 'youtu.be':
                return parsed_url.path[1:]
                
            return None
        except Exception as e:
            print(f"Error extracting video ID: {str(e)}")
            return None

    def srt_to_txt(self, file_path: str, output_file: str = None) -> bool:
        """Convert SRT file to TXT file containing clean text"""
        try:
            # Read SRT file
            try:
                with open(file_path, 'r', encoding='utf-8') as subtitle:
                    lines = subtitle.readlines()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as subtitle:
                    lines = subtitle.readlines()

            # Extract text from SRT
            paragraph_lines = []
            timestamp_patterns = [
                re.compile(r'^\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}'),
                re.compile(r'^\d{1,2}:\d{2}:\d{2}\s*-->\s*\d{1,2}:\d{2}:\d{2}')
            ]

            for line in lines:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                if any(pattern.match(stripped_line) for pattern in timestamp_patterns):
                    continue
                if stripped_line.isdigit():
                    continue
                if re.match(r'^<.*>$', stripped_line):
                    continue
                
                cleaned_line = re.sub(r'<[^>]+>', '', stripped_line)
                if cleaned_line:
                    paragraph_lines.append(cleaned_line)

            paragraph = ' '.join(paragraph_lines)
            paragraph = re.sub(r'\s+', ' ', paragraph).strip()

            if not paragraph:
                print(f"Warning: No text content extracted from {file_path}")
                return False

            # Determine output file path
            if output_file is None:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_file = os.path.join(self.text_dir, f'{base_name}.txt')

            with open(output_file, 'w', encoding='utf-8') as new_file:
                new_file.write(paragraph)
            
            print(f"✓ Converted to text: {os.path.basename(output_file)}")
            return True
        except Exception as e:
            print(f"✗ Error converting {file_path}: {str(e)}")
            return False

    def convert_multiple_files(self, file_paths):
        """Convert multiple SRT files to TXT"""
        successful = 0
        for file_path in file_paths:
            if self.srt_to_txt(file_path):
                successful += 1
        print(f"\nConversion complete: {successful}/{len(file_paths)} files converted successfully")

    def show_menu(self):
        """Display main menu"""
        print("\n" + "="*50)
        print("     YouTube Subtitle Tool")
        print("="*50)
        print("1. Download subtitles (Single Video)")
        print("2. Download subtitles (Playlist)")
        print("3. Convert existing SRT files to TXT")
        print("4. Download + Convert (Single Video)")
        print("5. Download + Convert (Playlist)")
        print("6. View downloaded files")
        print("7. Set default language")
        print("8. Exit")
        print("="*50)
        
    def set_default_language(self):
        """Set the default language for subtitle downloads"""
        print("\n--- Set Default Language ---")
        print("1. English (current default)")
        print("2. Spanish")
        print("3. French")
        print("4. German")
        print("5. Chinese")
        print("6. Other")
        
        lang_choice = input("Choose default language (1-6): ").strip() or "1"
        
        if lang_choice == "1":
            self.preferred_language = "en"
            print("Default language set to English")
        elif lang_choice == "2":
            self.preferred_language = "es"
            print("Default language set to Spanish")
        elif lang_choice == "3":
            self.preferred_language = "fr"
            print("Default language set to French")
        elif lang_choice == "4":
            self.preferred_language = "de"
            print("Default language set to German")
        elif lang_choice == "5":
            self.preferred_language = "zh"
            print("Default language set to Chinese")
        elif lang_choice == "6":
            print("\nAvailable language codes: en, es, fr, de, zh, ja, ko, ar, ru, pt")
            lang = input("Enter language code: ").strip() or "en"
            self.preferred_language = lang
            print(f"Default language set to {lang}")
        else:
            print("Invalid choice. Default language unchanged.")

    def run(self):
        """Main application loop"""
        print("Welcome to YouTube Subtitle Tool!")
        
        while True:
            self.show_menu()
            choice = input("\nSelect an option (1-8): ").strip()
            
            if choice == '1':
                # Download single video
                url = input('\nEnter YouTube video URL: ').strip()
                if url:
                    downloaded_files = self.process_video_url(url)
                    if downloaded_files:
                        print(f"Downloaded {len(downloaded_files)} file(s) to '{self.subtitles_dir}' directory")
            
            elif choice == '2':
                # Download playlist
                url = input('\nEnter YouTube playlist URL: ').strip()
                if url:
                    downloaded_files = self.get_playlist_subtitles(url)
                    if downloaded_files:
                        print(f"Downloaded {len(downloaded_files)} file(s) to '{self.subtitles_dir}' directory")
                else:
                    print("Please provide a valid playlist URL")
            
            elif choice == '3':
                # Convert existing files
                self.convert_existing_files()
            
            elif choice == '4':
                # Download + Convert single video
                url = input('\nEnter YouTube video URL: ').strip()
                if url:
                    downloaded_files = self.process_video_url(url)
                    if downloaded_files:
                        print(f"Downloaded {len(downloaded_files)} file(s)")
                        self.convert_multiple_files(downloaded_files)
            
            elif choice == '5':
                # Download + Convert playlist
                url = input('\nEnter YouTube playlist URL: ').strip()
                if url:
                    downloaded_files = self.get_playlist_subtitles(url)
                    if downloaded_files:
                        print(f"Downloaded {len(downloaded_files)} file(s)")
                        convert_choice = input("\nConvert all downloaded files to text? (y/n): ").lower().strip()
                        if convert_choice == 'y':
                            self.convert_multiple_files(downloaded_files)
                else:
                    print("Please provide a valid playlist URL")
            
            elif choice == '6':
                # View files
                self.view_files()
                
            elif choice == '7':
                # Set default language
                self.set_default_language()
            
            elif choice == '8':
                # Exit
                print("\nThank you for using YouTube Subtitle Tool!")
                break
            
            else:
                print("Invalid choice. Please select 1-8.")
            
            # Ask if user wants to continue
            if choice in ['1', '2', '3', '4', '5']:
                input("\nPress Enter to continue...")

def main():
    """Entry point of the application"""
    try:
        tool = YouTubeSubtitleTool()
        tool.run()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        print("Please check your setup and try again.")

if __name__ == "__main__":
    main()
