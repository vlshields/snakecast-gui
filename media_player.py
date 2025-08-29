import podcastparser
import urllib.request
import requests
import pygame
import os
import sys
from pathlib import Path
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from enum import Enum


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Episode:
    """Data model for a podcast episode"""
    title: str
    description: str
    url: str
    published: Optional[int] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    index: int = 0
    
    @property
    def formatted_date(self) -> str:
        if self.published:
            try:
                dt = datetime.fromtimestamp(self.published)
                return dt.strftime("%b %d, %Y")
            except:
                pass
        return "Unknown date"
    
    @property
    def formatted_duration(self) -> str:
        if not self.duration:
            return ""
        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        secs = int(self.duration % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    @property
    def size_mb(self) -> float:
        if self.file_size:
            return self.file_size / (1024 * 1024)
        return 0

class PlayerState(Enum):
    """Player state enumeration"""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    DOWNLOADING = "downloading"

# ============================================================================
# Services
# ============================================================================

class PodcastFeedService:
    """Handles fetching and parsing podcast feeds"""
    
    def __init__(self, feed_url: str = 'https://realpython.com/podcasts/rpp/feed'):
        self.feed_url = feed_url
        self.podcast_title = "Podcast"
    
    def fetch_episodes(self, limit: int = 20) -> List[Episode]:
        """Fetch episodes from podcast feed"""
        try:
            parsed = podcastparser.parse(self.feed_url, urllib.request.urlopen(self.feed_url))
            self.podcast_title = parsed.get('title', 'Podcast')
            
            episodes = []
            for i, ep in enumerate(parsed['episodes'][:limit]):
                if ep.get('enclosures'):
                    episode = Episode(
                        title=ep.get('title', 'Unknown'),
                        description=ep.get('description', ''),
                        url=ep['enclosures'][0]['url'],
                        published=ep.get('published'),
                        duration=ep.get('total_time'),
                        file_size=ep['enclosures'][0].get('file_size'),
                        index=i
                    )
                    episodes.append(episode)
            return episodes
        except Exception as e:
            print(f"Error fetching feed: {e}")
            return []

class DownloadService:
    """Handles downloading podcast episodes"""
    
    def __init__(self, downloads_dir: Path):
        self.downloads_dir = downloads_dir
        self.downloads_dir.mkdir(exist_ok=True)
        self.progress = 0
        self.is_downloading = False
        self._lock = threading.Lock()
    
    def download_episode(self, episode: Episode, callback=None) -> Path:
        """Download episode to local file"""
        with self._lock:
            self.is_downloading = True
            self.progress = 0
        
        filename = self.downloads_dir / f"episode_{episode.index}.mp3"
        
        try:
            response = requests.get(episode.url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        with self._lock:
                            self.progress = (downloaded / total_size) * 100
                        if callback:
                            callback(self.progress)
            
            return filename
        finally:
            with self._lock:
                self.is_downloading = False
                self.progress = 0

class AudioPlayer:
    """Handles audio playback"""
    
    def __init__(self):
        pygame.mixer.init()
        self.state = PlayerState.STOPPED
        self.current_episode: Optional[Episode] = None
        self.current_file: Optional[Path] = None
    
    def load_and_play(self, file_path: Path, episode: Episode):
        """Load and play an audio file"""
        pygame.mixer.music.load(str(file_path))
        pygame.mixer.music.play()
        self.current_file = file_path
        self.current_episode = episode
        self.state = PlayerState.PLAYING
    
    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if self.state == PlayerState.PLAYING:
            pygame.mixer.music.pause()
            self.state = PlayerState.PAUSED
        elif self.state == PlayerState.PAUSED:
            pygame.mixer.music.unpause()
            self.state = PlayerState.PLAYING
    
    def stop(self):
        """Stop playback"""
        pygame.mixer.music.stop()
        self.state = PlayerState.STOPPED
        self.current_episode = None
        self.current_file = None
    
    def get_position(self) -> float:
        """Get current playback position in seconds"""
        if self.state in [PlayerState.PLAYING, PlayerState.PAUSED]:
            return pygame.mixer.music.get_pos() / 1000
        return 0
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        return pygame.mixer.music.get_busy() and self.state == PlayerState.PLAYING