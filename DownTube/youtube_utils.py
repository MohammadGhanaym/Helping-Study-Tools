from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, NoTranscriptAvailable

def extract_video_id(url):
    """Extract video ID from YouTube URL."""
    if 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    elif 'youtube.com/watch' in url:
        import urllib.parse as urlparse
        parsed_url = urlparse.urlparse(url)
        return urlparse.parse_qs(parsed_url.query)['v'][0]
    return url

def check_available_subtitles(video_id):
    """Check and return a list of available subtitle languages for a video."""
    try:
        available_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = []
        
        for transcript in available_transcripts:
            available_languages.append({
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated
            })
            
        return available_languages
    except Exception as e:
        print(f"Error checking available subtitles: {str(e)}")
        return []

def get_subtitle_content(video_id, language_code='en'):
    """Download subtitles and return formatted content."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language_code])
        formatter = TextFormatter()
        formatted_transcript = formatter.format_transcript(transcript)
        return formatted_transcript, transcript
    except NoTranscriptFound:
        return None, None
    except (TranscriptsDisabled, NoTranscriptAvailable) as e:
        print(f"Error: {str(e)}")
        return None, None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None, None
