import sys
import re
import os
import subprocess
import json
import threading
import time
import itertools

class Spinner:
    """A simple spinner animation to show progress - CMD compatible version"""
    def __init__(self, message="Processing"):
        self.message = message
        # Using simple ASCII characters for CMD compatibility
        self.spinner_chars = ['|', '/', '-', '\\']
        self.stop_running = False
        self.spinner_thread = None
        self.counter = 0

    def spin(self):
        spinner = itertools.cycle(self.spinner_chars)
        while not self.stop_running:
            self.counter += 1
            if self.counter % 5 == 0:  # Only update every 0.5 seconds to reduce flicker in CMD
                sys.stdout.write('\r' + self.message + ' ' + next(spinner) + ' ')
                sys.stdout.flush()
            time.sleep(0.1)
        # Clear the line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()

    def start(self):
        # For CMD compatibility, just print dots instead of using a spinner
        print(f"{self.message}... ", end="", flush=True)
        # We don't actually start the thread for CMD to avoid flickering

    def stop(self):
        # For CMD compatibility, just print done
        print("done")
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

def check_yt_dlp_installed():
    """Check if yt-dlp is installed and accessible"""
    try:
        result = subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True, text=True)
        version = result.stdout.strip()
        return True, version
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, None

def download_subtitles(video_id, language='en'):
    """Download subtitles using yt-dlp"""
    try:
        # Check if yt-dlp is installed
        is_installed, version = check_yt_dlp_installed()
        if not is_installed:
            print("\nError: yt-dlp is not installed or not accessible in PATH.")
            print("Please install it with: pip install yt-dlp")
            print("After installation, restart this script.")
            return None
        else:
            print(f"Using yt-dlp version: {version}")
        
        # Create a temporary directory if it doesn't exist
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Set the output filename
        output_file = os.path.join(temp_dir, f"{video_id}.{language}")
        
        # Show downloading message with spinner
        with Spinner(f"Downloading subtitles for {video_id}"):
            # Run yt-dlp to download subtitles
            cmd = [
                "yt-dlp",
                f"https://www.youtube.com/watch?v={video_id}",
                "--skip-download",
                "--sub-langs", f"{language}",
                "--write-auto-sub",  # Try auto-generated subtitles if available
                "--write-sub",       # Try regular subtitles
                f"--output={output_file}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error running yt-dlp: {result.stderr}")
            return None
        
        # Find the downloaded subtitle file with the correct language extension
        subtitle_files = [f for f in os.listdir(temp_dir) if f.startswith(f"{video_id}") and f.endswith(f".{language}.vtt")]
        
        if not subtitle_files:
            print(f"No subtitle file was found for language '{language}'")
            return None
            
        subtitle_file = os.path.join(temp_dir, subtitle_files[0])
        
        # Parse VTT to transcript format
        print("Processing subtitle file...")
        
        with Spinner("Parsing subtitles"):
            transcript = parse_vtt_to_transcript(subtitle_file)
            
        if not transcript:
            print("Failed to parse subtitles - the file may be empty or malformed.")
            return None
            
        print(f"Found {len(transcript)} subtitle entries.")
        return transcript
        
    except Exception as e:
        print(f"Error using yt-dlp: {str(e)}")
        return None

def parse_vtt_to_transcript(vtt_file):
    """Parse a VTT file into transcript format"""
    transcript = []
    try:
        with open(vtt_file, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # Simple VTT parsing (this is a basic implementation)
        lines = content.split('\n')
        current_text = ""
        current_start = 0
        
        for i, line in enumerate(lines):
            if '-->' in line:
                # This is a timestamp line
                timestamps = line.split('-->')
                start_time = parse_timestamp(timestamps[0].strip())
                
                # Get the text (next line)
                if i + 1 < len(lines):
                    text = lines[i + 1].strip()
                    if text and not text.startswith('WEBVTT'):
                        transcript.append({
                            'text': text,
                            'start': start_time,
                            'duration': 2.0  # Default duration
                        })
        
        return transcript
    except Exception as e:
        print(f"Error parsing VTT file: {str(e)}")
        return []

def process_transcript_for_ai(transcript):
    """Process transcript to optimize for AI input by removing duplicates and optimizing text"""
    if not transcript:
        return ""
        
    # Extract just the text from transcript entries
    text_entries = [entry['text'] for entry in transcript]
    
    # Process the text to remove duplicates and optimize
    processed_text = []
    prev_text = ""
    
    for text in text_entries:
        # Skip if this line is identical or nearly identical to the previous one
        # (Some subtitle systems repeat lines with minimal differences)
        if text == prev_text:
            continue
            
        # Check for significant overlap with previous line
        # This helps catch cases where only a word or two is added
        if prev_text and (prev_text in text or text in prev_text):
            # If current text is longer, replace previous text
            if len(text) > len(prev_text):
                if processed_text:  # Make sure we have something to replace
                    processed_text[-1] = text
                    prev_text = text
                continue
            # If current text is shorter, skip it
            else:
                continue
                
        # Add text to processed list
        processed_text.append(text)
        prev_text = text
    
    # Build optimized text:
    # 1. Join sentences that belong together (often split across subtitle entries)
    # 2. Maintain paragraph structure for major topic changes
    
    optimized_text = ""
    current_sentence = ""
    
    for text in processed_text:
        # Check if this text ends with sentence-ending punctuation
        ends_sentence = bool(re.search(r'[.!?]"?\s*$', text))
        
        # If text starts with lowercase and previous doesn't end with sentence punctuation,
        # it's likely a continuation
        starts_lowercase = bool(re.match(r'^[a-z]', text))
        
        # Join with the current sentence if it's a continuation
        if starts_lowercase and current_sentence:
            current_sentence += " " + text
        else:
            # If we have a complete sentence, add it to the optimized text
            if current_sentence:
                optimized_text += current_sentence + " "
            current_sentence = text
        
        # If this part ends a sentence, reset current_sentence
        if ends_sentence:
            if current_sentence:
                optimized_text += current_sentence + " "
                current_sentence = ""
    
    # Add any remaining text
    if current_sentence:
        optimized_text += current_sentence
        
    # Final cleanup: 
    # 1. Normalize spacing
    # 2. Remove any special subtitle formatting
    optimized_text = re.sub(r'\s+', ' ', optimized_text)  # Normalize spaces
    optimized_text = re.sub(r'<[^>]+>', '', optimized_text)  # Remove HTML-like tags
    optimized_text = re.sub(r'\[[^\]]+\]', '', optimized_text)  # Remove bracketed content
    optimized_text = re.sub(r'\([^)]*\)', '', optimized_text)  # Remove parenthesized content that's likely not part of the script
    
    return optimized_text.strip()

def parse_timestamp(timestamp):
    """Convert VTT timestamp to seconds"""
    try:
        parts = timestamp.replace(',', '.').split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
    except:
        return 0.0

def clean_filename(title):
    """Clean a string to make it a valid filename"""
    # Step 1: Replace invalid characters with underscores
    invalid_chars = r'[<>:"/\\|?*]'
    clean_title = re.sub(invalid_chars, '_', title)
    
    # Step 2: Check for reserved names in Windows
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL', 
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    
    # If the cleaned name (without extension) matches a reserved name, add an underscore
    if clean_title.upper() in reserved_names:
        clean_title = clean_title + "_"
    
    # Step 3: Remove leading/trailing periods and spaces
    clean_title = clean_title.strip('. ')
    
    # Step 4: Replace multiple spaces with a single space
    clean_title = re.sub(r'\s+', ' ', clean_title)
    
    # Step 5: Trim to a reasonable length (max 100 chars)
    if len(clean_title) > 100:
        clean_title = clean_title[:97] + "..."
    
    # Step 6: If the title is empty after cleaning, use a default name
    if not clean_title:
        clean_title = "youtube_video"
    
    return clean_title

def is_valid_youtube_id(video_id):
    """Check if string is a valid YouTube ID (11 characters of letters, numbers, dashes, underscores)"""
    if not video_id:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]{11}$', video_id))

def extract_video_id(url):
    """Extract video ID from YouTube URL with validation."""
    # Try to extract using regex pattern for better accuracy
    youtube_regex = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    
    if match:
        return match.group(1)
    
    # Fallback to the original method if regex fails
    if "youtube.com" in url and "v=" in url:
        # Regular YouTube URL
        video_id = url.split("v=")[1].split("&")[0]
    elif "youtu.be" in url:
        # Shortened YouTube URL
        video_id = url.split("/")[-1].split("?")[0]
    else:
        # Assume it's already a video ID
        video_id = url
    
    # Validate the extracted ID
    if is_valid_youtube_id(video_id):
        return video_id
    else:
        return None

def select_language():
    """Display an interactive language selection menu"""
    # Common language codes for YouTube subtitles
    common_languages = [
        ("English", "en"),
        ("Spanish", "es"),
        ("French", "fr"),
        ("German", "de"),
        ("Japanese", "ja"),
        ("Korean", "ko"),
        ("Chinese", "zh"),
        ("Russian", "ru"),
        ("Arabic", "ar"),
        ("Portuguese", "pt"),
        ("Italian", "it"),
        ("Dutch", "nl"),
        ("Hindi", "hi"),
        ("Turkish", "tr"),
        ("Polish", "pl")
    ]
    
    # Group languages for better display
    def display_languages():
        print("\nSelect a language:")
        columns = 3  # Number of columns in the display
        rows = (len(common_languages) + columns - 1) // columns
        
        # Print header
        header = "   " + "".join([f"{i:<20}" for i in range(1, columns + 1)])
        
        # Print languages in columns
        for row in range(rows):
            line = "   "
            for col in range(columns):
                idx = row + col * rows
                if idx < len(common_languages):
                    lang_num = idx + 1
                    lang_name, lang_code = common_languages[idx]
                    line += f"{lang_num:<2}. {lang_name:<15} "
                else:
                    line += " " * 20
            print(line)
        
        # Custom option
        print(f"\n   {len(common_languages) + 1}. Other (custom language code)")
    
    while True:
        try:
            display_languages()
            choice = input(f"\nEnter your choice (1-{len(common_languages) + 1}): ").strip()
            
            # Check if the choice is a number
            if choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(common_languages):
                    selected_language, code = common_languages[choice_num - 1]
                    print(f"\nSelected: {selected_language} ({code})")
                    return code
                elif choice_num == len(common_languages) + 1:
                    print("\nEnter a custom language code.")
                    print("Examples: 'sv' (Swedish), 'uk' (Ukrainian), 'vi' (Vietnamese)")
                    
                    while True:
                        custom_code = input("\nLanguage code: ").strip().lower()
                        
                        # Validate language code - should be 2-3 characters
                        if re.match(r'^[a-z]{2,3}(-[a-z]{2,4})?$', custom_code):
                            print(f"\nSelected custom language code: {custom_code}")
                            return custom_code
                        else:
                            print("Invalid language code. Please enter a 2-3 letter code (e.g. 'sv', 'uk', 'vi').")
                else:
                    print(f"Invalid selection. Please enter a number between 1 and {len(common_languages) + 1}.")
            else:
                print("Invalid input. Please enter a number.")
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Invalid input. Please try again.")

def clear_screen():
    """Clear the terminal screen"""
    # Check if we're on Windows or Unix
    if os.name == 'nt':  # Windows
        os.system('cls')
    else:  # Unix/Linux/Mac
        os.system('clear')

def show_header(subtitle=""):
    """Show a consistent header"""
    clear_screen()
    print("=" * 60)
    print("YouTube Subtitle Downloader and Optimizer".center(60))
    if subtitle:
        print(subtitle.center(60))
    print("=" * 60)
    print()

def main():
    show_header("Video Selection")
    
    # Prompt user for YouTube URL or video ID with validation
    video_id = None
    while video_id is None:
        print("Enter a YouTube URL or video ID below.")
        print("Tip: You can copy the URL directly from your browser.")
        url_input = input("\n> ").strip()
        
        # Check if input is empty
        if not url_input:
            print("\nError: Empty input. Please enter a valid YouTube URL or video ID.")
            continue
            
        video_id = extract_video_id(url_input)
        
        if video_id is None:
            print("\nError: Invalid YouTube URL or video ID. Please try again.")
            print("\nExamples of valid inputs:")
            print("  • https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            print("  • https://youtu.be/dQw4w9WgXcQ")
            print("  • dQw4w9WgXcQ")
            print("\nPress Enter to try again...")
            input()
            show_header("Video Selection")
            continue
    
    print(f"Extracted video ID: {video_id}")
    language_code = "en"  # Default language code    # Check if the video exists before attempting to download subtitles
    video_title = None
    with Spinner("Verifying video exists"):
        try:
            # Use yt-dlp to verify the video exists
            verify_cmd = [
                "yt-dlp",
                f"https://www.youtube.com/watch?v={video_id}",
                "--skip-download",
                "--print", "title"
            ]
            verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
            
            if verify_result.returncode != 0:
                print(f"Error: Could not verify video. It may not exist or might be private/deleted.")
                print(f"Details: {verify_result.stderr.strip()}")
                return
                
            video_title = verify_result.stdout.strip()
            if video_title:
                print(f"Video found: {video_title}")
                # Clean the title for use as filename
                clean_title = clean_filename(video_title)
                print(f"Using filename: {clean_title}")
            else:
                # If we couldn't get a title for some reason, use the video ID
                clean_title = video_id
                print(f"Could not retrieve video title. Using video ID as filename.")
        except Exception as e:
            print(f"Error verifying video: {str(e)}")
            return
              # Download subtitles
    subtitles = download_subtitles(video_id, language_code)
    
    if subtitles is None:
        show_header("No Subtitles Found")
        print("No subtitles were found for this video in English.")
        print("\nOptions:")
        print("1. Try another language")
        print("2. Return to main menu")
        
        while True:
            choice = input("\nEnter your choice (1-2): ")
            if choice in ['1', '2']:
                break
            else:
                print("Invalid input. Please enter 1 or 2.")

        if choice == '1':
            # Prompt for another language
            show_header("Language Selection")
            language_code = select_language()
            
            show_header(f"Downloading Subtitles in {language_code.upper()}")
            subtitles = download_subtitles(video_id, language_code)
            
            if subtitles is None:
                show_header("Subtitle Download Failed")
                print(f"Still unable to find subtitles for this video in {language_code.upper()}.")
                print("\nPossible reasons:")
                print("• The video doesn't have subtitles in this language")
                print("• The subtitles are disabled by the video owner")                
                print("• There might be an issue with the YouTube servers")
                print("\nReturning to main menu...")
                input("\nPress Enter to continue...")
                return
        else:
            print("Returning to main menu...")
            return
            
    # Proceed with the successfully downloaded subtitles
    show_header("Processing Subtitles")
    print(f"Successfully retrieved {len(subtitles)} subtitle entries")
    
    # Create subtitles directory if it doesn't exist
    subtitles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subtitles")
    os.makedirs(subtitles_dir, exist_ok=True)
    
    # Save to a text file - both raw and AI-optimized versions
    raw_subtitle_txt_file = os.path.join(subtitles_dir, f"{clean_title}_{language_code}_raw.txt")
    optimized_subtitle_txt_file = os.path.join(subtitles_dir, f"{clean_title}_{language_code}.txt")
    
    with Spinner("Processing and saving subtitle files"):
        # Save the raw transcript with one subtitle per line
        with open(raw_subtitle_txt_file, "w", encoding="utf-8") as file:
            for entry in subtitles:
                file.write(f"{entry['text']}\n")
                  # Process and save the AI-optimized version
        optimized_text = process_transcript_for_ai(subtitles)
        with open(optimized_subtitle_txt_file, "w", encoding="utf-8") as file:
            file.write(optimized_text)
            
    print(f"\n📂 Files saved:")
    print(f"   • Raw subtitles: {os.path.basename(raw_subtitle_txt_file)}")
    print(f"   • AI-optimized: {os.path.basename(optimized_subtitle_txt_file)}")
    print(f"\n📁 Location: {subtitles_dir}")
      # Print statistics about the optimization
    raw_size = os.path.getsize(raw_subtitle_txt_file)
    optimized_size = os.path.getsize(optimized_subtitle_txt_file)
    reduction = ((raw_size - optimized_size) / raw_size) * 100 if raw_size > 0 else 0
    char_count = len(optimized_text)
    
    # Calculate approximate tokens (rough estimate: ~4 chars per token)
    approx_tokens = char_count // 4
    
    # Show summary in a nice format
    show_header("Download Complete!")
    
    print(f"📝 Video title: {video_title}")
    print(f"🔤 Language: {language_code.upper()}")
    print(f"📊 Statistics:")
    print(f"   • {len(subtitles):,} subtitle entries processed")
    print(f"   • {raw_size:,} bytes in raw format")
    print(f"   • {optimized_size:,} bytes in optimized format")
    print(f"   • {reduction:.1f}% size reduction")
    print(f"   • {char_count:,} characters for AI model")
    print(f"   • ~{approx_tokens:,} estimated tokens for AI model")
      # Copy the original VTT file if it exists
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    vtt_source = os.path.join(temp_dir, f"{video_id}.{language_code}.vtt.{language_code}.vtt")
    
    if os.path.exists(vtt_source):
        subtitle_vtt_file = os.path.join(subtitles_dir, f"{clean_title}_{language_code}.vtt")
        try:
            with Spinner("Saving VTT subtitle file"):
                # Read from source VTT
                with open(vtt_source, "r", encoding="utf-8") as source:
                    vtt_content = source.read()
                
                # Write to destination VTT
                with open(subtitle_vtt_file, "w", encoding="utf-8") as dest:
                    dest.write(vtt_content)
            
            print(f"✓ Original VTT file saved to {subtitle_vtt_file}")
        except Exception as e:
            print(f"Error copying VTT file: {str(e)}")

def download_another():
    """Ask the user if they want to download another subtitle"""
    while True:
        print("\n" + "=" * 60)
        print("Would you like to download subtitles for another video?")
        print("1. Yes, download another")
        print("2. No, exit program")
        choice = input("Enter your choice (1-2): ").strip()
        
        if choice == '1':
            return True
        elif choice == '2':
            return False
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    try:
        print("=" * 60)
        print("YouTube Subtitle Downloader and Optimizer".center(60))
        print("=" * 60)
        
        continue_downloading = True
        downloads_count = 0
        
        while continue_downloading:
            if downloads_count > 0:
                print("\n" + "=" * 60)
                print(f"Starting download #{downloads_count + 1}")
                print("=" * 60)
                
            main()
            downloads_count += 1
            
            continue_downloading = download_another()
        
        print("\n" + "=" * 60)
        print(f"Program finished. Downloaded subtitles for {downloads_count} video(s).")
        print("=" * 60)
        input("\nPress Enter key to exit...")  # Wait for user input before exiting
        
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
        input("\nPress Enter key to exit...")  # Wait for user input before exiting
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")
        input("\nPress Enter key to exit...")  # Wait for user input before exiting