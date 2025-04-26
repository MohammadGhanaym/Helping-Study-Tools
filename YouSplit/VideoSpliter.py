#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import pandas as pd
from moviepy.video.io.VideoFileClip import VideoFileClip


# In[ ]:


def time_to_seconds(time_str):
    """Convert time format (HH:MM:SS) to seconds."""
    h, m, s = map(int, time_str.split(":"))
    return h * 3600 + m * 60 + s


# In[ ]:


def split_video(video_path, chapters_file, output_dir):
    # Read chapters from Excel
    chapters = pd.read_excel(chapters_file)
    
    # Check if output directory exists, create if not
    os.makedirs(output_dir, exist_ok=True)
    
    # Load video file
    video = VideoFileClip(video_path)
    
    # Iterate through chapters and split the video
    for index, row in chapters.iterrows():
        start_time = time_to_seconds(row["Start Time"])
        end_time = time_to_seconds(row["End Time"])
        title = row["Title"]
        
        # Extract clip
        clip = video.subclip(start_time, end_time)
        
        # Clean title for a valid filename
        filename = f"{index + 1:02d}_{title.replace('/', '-').replace(':', ' -')}.mp4"
        output_path = os.path.join(output_dir, filename)
        
        # Write the clip to a file
        print(f"Processing: {title} -> {filename}")
        clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print("Video splitting completed.")


# In[ ]:


if __name__ == "__main__":
    # Path to the video file
    video_path = "path_to_your_video.mp4"  # Replace with your video file path
    
    # Path to the Excel file with chapters
    chapters_file = "Chapters.xlsx"
    
    # Output directory for the split videos
    output_dir = "SplitVideos"
    
    # Split the video
    split_video(video_path, chapters_file, output_dir)

