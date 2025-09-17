from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, NoTranscriptAvailable

def list_available_subtitle_languages(video_id):
    """List all available subtitle languages for a video."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = []
        
        for transcript in transcript_list:
            language_info = {
                'language_code': transcript.language_code,
                'language': transcript.language,
                'is_generated': transcript.is_generated
            }
            available_languages.append(language_info)
            
        return available_languages
    except Exception as e:
        print(f"Error retrieving subtitle languages: {str(e)}")
        return []

def download_subtitle_with_fallback(video_id, primary_language='en', fallback_languages=None):
    """
    Tries to download subtitles in the primary language.
    If not available, attempts fallback languages.
    """
    if fallback_languages is None:
        fallback_languages = ['en-US', 'en-GB', 'en']
        
    # If primary language is not in fallback languages, add it
    if primary_language not in fallback_languages:
        fallback_languages.insert(0, primary_language)
    
    for lang in fallback_languages:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
            print(f"Successfully downloaded subtitles in {lang}")
            return transcript, lang
        except (NoTranscriptFound, TranscriptsDisabled, NoTranscriptAvailable):
            continue
        except Exception as e:
            print(f"Unexpected error with language {lang}: {str(e)}")
            continue
    
    # No subtitles found in any language
    return None, None

def save_subtitles_to_file(subtitles, filename):
    """Save subtitles to a file."""
    if not subtitles:
        return False
        
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            for entry in subtitles:
                start_time = entry['start']
                text = entry['text']
                file.write(f"[{format_time(start_time)}] {text}\n")
        return True
    except Exception as e:
        print(f"Error saving subtitles: {str(e)}")
        return False
        
def format_time(seconds):
    """Format time in seconds to MM:SS format."""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"
