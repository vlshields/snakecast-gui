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

class PodcastPlayer:
    def __init__(self):
        pygame.init()
        self.width = 1280
        self.height = 720
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Podcast Player")
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.title_font = pygame.font.Font(None, 32)
        
        self.episodes = []
        self.current_episode = None
        self.audio_file = None
        self.is_playing = False
        self.is_paused = False
        self.download_progress = 0
        self.is_downloading = False
        
        self.downloads_dir = Path("downloads")
        self.downloads_dir.mkdir(exist_ok=True)
        
        pygame.mixer.init()
        
        self.colors = {
            'bg': (30, 30, 40),
            'button': (70, 130, 180),
            'button_hover': (100, 160, 210),
            'text': (255, 255, 255),
            'text_secondary': (180, 180, 180),
            'progress': (50, 205, 50),
            'progress_bg': (60, 60, 70)
        }
        
        self.buttons = {
            'play_pause': pygame.Rect(350, 500, 100, 40),
            'stop': pygame.Rect(460, 500, 100, 40),
            'refresh': pygame.Rect(680, 20, 100, 30)
        }
        
        self.episode_rects = []
        self.scroll_offset = 0
        self.selected_episode = None
        self.show_details = False
        
    def download_episode(self, url, filename):
        """Download podcast episode to local file"""
        self.is_downloading = True
        self.download_progress = 0
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    self.download_progress = (downloaded / total_size) * 100
        
        self.is_downloading = False
        return filename
    
    def format_date(self, timestamp):
        """Format timestamp to readable date"""
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%b %d, %Y")
        except:
            return "Unknown date"
    
    def format_duration(self, seconds):
        """Format duration in seconds to HH:MM:SS or MM:SS"""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes}:{secs:02d}"
        except:
            return ""
    
    def fetch_episodes(self):
        """Fetch podcast episodes from feed"""
        feedurl = 'https://realpython.com/podcasts/rpp/feed'
        try:
            parsed = podcastparser.parse(feedurl, urllib.request.urlopen(feedurl))
            self.episodes = parsed['episodes'][:20]  # Get first 20 episodes
            self.podcast_title = parsed.get('title', 'Podcast')
        except Exception as e:
            print(f"Error fetching feed: {e}")
    
    def play_episode(self, episode_index):
        """Download and play selected episode"""
        if episode_index >= len(self.episodes):
            return
        
        episode = self.episodes[episode_index]
        self.current_episode = episode
        
        if not episode.get('enclosures'):
            return
        
        audio_url = episode['enclosures'][0]['url']
        filename = self.downloads_dir / f"episode_{episode_index}.mp3"
        
        # Download in background thread
        def download_and_play():
            self.audio_file = self.download_episode(audio_url, filename)
            pygame.mixer.music.load(str(self.audio_file))
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
        
        thread = threading.Thread(target=download_and_play)
        thread.daemon = True
        thread.start()
    
    def toggle_play_pause(self):
        """Toggle play/pause state"""
        if self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
    
    def stop_playback(self):
        """Stop current playback"""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.current_episode = None
    
    def draw_button(self, rect, text, hover=False):
        """Draw a button"""
        color = self.colors['button_hover'] if hover else self.colors['button']
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, self.colors['text'], rect, 2)
        
        text_surf = self.font.render(text, True, self.colors['text'])
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)
    
    def draw_progress_bar(self, x, y, width, height, progress):
        """Draw a progress bar"""
        pygame.draw.rect(self.screen, self.colors['progress_bg'], (x, y, width, height))
        if progress > 0:
            fill_width = int(width * (progress / 100))
            pygame.draw.rect(self.screen, self.colors['progress'], (x, y, fill_width, height))
    
    def draw_episode_details(self):
        """Draw detailed view of selected episode"""
        if not self.selected_episode:
            return
        
        # Semi-transparent background
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(240)
        overlay.fill((20, 20, 30))
        self.screen.blit(overlay, (0, 0))
        
        # Details panel
        panel_width = 1000
        panel_height = 600
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2
        
        pygame.draw.rect(self.screen, (40, 40, 50), (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, self.colors['button'], (panel_x, panel_y, panel_width, panel_height), 3)
        
        # Close button
        close_rect = pygame.Rect(panel_x + panel_width - 40, panel_y + 10, 30, 30)
        pygame.draw.rect(self.screen, self.colors['button'], close_rect)
        close_text = self.font.render("X", True, self.colors['text'])
        self.screen.blit(close_text, (close_rect.x + 9, close_rect.y + 3))
        
        # Episode title
        title = self.selected_episode.get('title', 'Unknown')
        title_lines = []
        words = title.split()
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if self.title_font.size(test_line)[0] < panel_width - 100:
                current_line = test_line
            else:
                if current_line:
                    title_lines.append(current_line)
                current_line = word
        if current_line:
            title_lines.append(current_line)
        
        y_pos = panel_y + 30
        for line in title_lines[:2]:  # Max 2 lines for title
            title_surface = self.title_font.render(line, True, self.colors['text'])
            self.screen.blit(title_surface, (panel_x + 30, y_pos))
            y_pos += 35
        
        y_pos += 10
        
        # Metadata
        metadata_items = []
        if self.selected_episode.get('published'):
            date_str = self.format_date(self.selected_episode['published'])
            metadata_items.append(f"Published: {date_str}")
        
        if self.selected_episode.get('total_time'):
            duration_str = self.format_duration(self.selected_episode['total_time'])
            if duration_str:
                metadata_items.append(f"Duration: {duration_str}")
        
        if self.selected_episode.get('enclosures') and self.selected_episode['enclosures'][0].get('file_size'):
            size_mb = self.selected_episode['enclosures'][0]['file_size'] / (1024 * 1024)
            metadata_items.append(f"File size: {size_mb:.1f} MB")
        
        for item in metadata_items:
            meta_surface = self.font.render(item, True, self.colors['text_secondary'])
            self.screen.blit(meta_surface, (panel_x + 30, y_pos))
            y_pos += 25
        
        y_pos += 20
        
        # Description
        if self.selected_episode.get('description'):
            desc_lines = []
            words = self.selected_episode['description'].split()
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                if self.small_font.size(test_line)[0] < panel_width - 60:
                    current_line = test_line
                else:
                    if current_line:
                        desc_lines.append(current_line)
                    current_line = word
            if current_line:
                desc_lines.append(current_line)
            
            # Display description with scrolling if needed
            max_lines = (panel_height - (y_pos - panel_y) - 80) // 22
            for i, line in enumerate(desc_lines[:max_lines]):
                desc_surface = self.small_font.render(line, True, self.colors['text'])
                self.screen.blit(desc_surface, (panel_x + 30, y_pos + i * 22))
        
        # Play button
        play_rect = pygame.Rect(panel_x + panel_width // 2 - 60, panel_y + panel_height - 60, 120, 40)
        mouse_pos = pygame.mouse.get_pos()
        self.draw_button(play_rect, "Play Episode", play_rect.collidepoint(mouse_pos))
    
    def draw(self):
        """Draw the GUI"""
        self.screen.fill(self.colors['bg'])
        
        # Title
        title_text = self.title_font.render("Podcast Player", True, self.colors['text'])
        self.screen.blit(title_text, (20, 20))
        
        # Refresh button
        mouse_pos = pygame.mouse.get_pos()
        self.draw_button(self.buttons['refresh'], "Refresh", 
                        self.buttons['refresh'].collidepoint(mouse_pos))
        
        # Episodes list
        y_offset = 80
        self.episode_rects = []
        episode_height = 65  # Increased height for metadata
        
        for i, episode in enumerate(self.episodes):
            if y_offset + self.scroll_offset < 60 or y_offset + self.scroll_offset > 450:
                y_offset += episode_height + 5
                continue
                
            rect = pygame.Rect(20, y_offset + self.scroll_offset, 1240, episode_height)
            self.episode_rects.append(rect)
            
            # Highlight current episode
            if self.current_episode and episode == self.current_episode:
                pygame.draw.rect(self.screen, (50, 50, 60), rect)
                pygame.draw.rect(self.screen, (70, 130, 180), rect, 2)
            elif rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, (40, 40, 50), rect)
            
            # Episode number and title
            title = episode.get('title', 'Unknown')
            if len(title) > 90:
                title = title[:87] + '...'
            text = self.font.render(f"{i+1}. {title}", True, self.colors['text'])
            self.screen.blit(text, (rect.x + 10, rect.y + 5))
            
            # Episode metadata (date, duration, etc.)
            metadata_parts = []
            
            # Date
            if episode.get('published'):
                date_str = self.format_date(episode['published'])
                metadata_parts.append(date_str)
            
            # Duration
            if episode.get('total_time'):
                duration_str = self.format_duration(episode['total_time'])
                if duration_str:
                    metadata_parts.append(f"Duration: {duration_str}")
            
            # File size if available
            if episode.get('enclosures') and episode['enclosures'][0].get('file_size'):
                size_mb = episode['enclosures'][0]['file_size'] / (1024 * 1024)
                metadata_parts.append(f"Size: {size_mb:.1f} MB")
            
            metadata_text = " | ".join(metadata_parts)
            meta_surface = self.small_font.render(metadata_text, True, self.colors['text_secondary'])
            self.screen.blit(meta_surface, (rect.x + 10, rect.y + 30))
            
            # Show brief description
            if episode.get('description'):
                desc = episode['description'][:120] + '...' if len(episode.get('description', '')) > 120 else episode['description']
                desc_surface = self.small_font.render(desc, True, self.colors['text_secondary'])
                self.screen.blit(desc_surface, (rect.x + 10, rect.y + 45))
            
            y_offset += episode_height + 5
        
        # Download progress
        if self.is_downloading:
            self.draw_progress_bar(20, 460, 760, 20, self.download_progress)
            progress_text = self.font.render(f"Downloading: {self.download_progress:.1f}%", 
                                           True, self.colors['text'])
            self.screen.blit(progress_text, (350, 485))
        
        # Playback progress
        if self.is_playing and pygame.mixer.music.get_busy():
            pos = pygame.mixer.music.get_pos() / 1000  # Convert to seconds
            if pos > 0:
                # This is a simple time display, actual progress would need audio duration
                time_text = self.font.render(f"Playing: {int(pos//60)}:{int(pos%60):02d}", 
                                           True, self.colors['text'])
                self.screen.blit(time_text, (20, 485))
        
        # Control buttons
        play_pause_text = "Pause" if self.is_playing and not self.is_paused else "Play"
        self.draw_button(self.buttons['play_pause'], play_pause_text,
                        self.buttons['play_pause'].collidepoint(mouse_pos))
        self.draw_button(self.buttons['stop'], "Stop",
                        self.buttons['stop'].collidepoint(mouse_pos))
        
        # Current episode info
        if self.current_episode:
            current_text = self.font.render(f"Now: {self.current_episode.get('title', 'Unknown')[:60]}...", 
                                          True, self.colors['text'])
            self.screen.blit(current_text, (20, 550))
        
        # Draw episode details overlay if active
        if self.show_details:
            self.draw_episode_details()
        
        pygame.display.flip()
    
    def handle_click(self, pos, double_click=False):
        """Handle mouse clicks"""
        # Handle clicks in detail view
        if self.show_details:
            # Check for close button
            panel_width = 1000
            panel_height = 600
            panel_x = (self.width - panel_width) // 2
            panel_y = (self.height - panel_height) // 2
            close_rect = pygame.Rect(panel_x + panel_width - 40, panel_y + 10, 30, 30)
            play_rect = pygame.Rect(panel_x + panel_width // 2 - 60, panel_y + panel_height - 60, 120, 40)
            
            if close_rect.collidepoint(pos):
                self.show_details = False
                self.selected_episode = None
            elif play_rect.collidepoint(pos) and self.selected_episode:
                # Play the selected episode
                episode_idx = self.episodes.index(self.selected_episode)
                self.play_episode(episode_idx)
                self.show_details = False
                self.selected_episode = None
            return
        
        # Check control buttons
        if self.buttons['play_pause'].collidepoint(pos):
            self.toggle_play_pause()
        elif self.buttons['stop'].collidepoint(pos):
            self.stop_playback()
        elif self.buttons['refresh'].collidepoint(pos):
            self.fetch_episodes()
        
        # Check episode list
        for i, rect in enumerate(self.episode_rects):
            if rect.collidepoint(pos):
                if double_click:
                    # Show episode details on double click
                    self.selected_episode = self.episodes[i]
                    self.show_details = True
                else:
                    # Play episode on single click
                    self.play_episode(i)
                break
    
    def run(self):
        """Main game loop"""
        self.fetch_episodes()
        running = True
        last_click_time = 0
        double_click_threshold = 500  # milliseconds
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.toggle_play_pause()
                    elif event.key == pygame.K_s:
                        self.stop_playback()
                    elif event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                        if self.show_details:
                            self.show_details = False
                            self.selected_episode = None
                        else:
                            running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        current_time = pygame.time.get_ticks()
                        is_double_click = (current_time - last_click_time) < double_click_threshold
                        self.handle_click(event.pos, is_double_click)
                        last_click_time = current_time
                    elif event.button == 4:  # Scroll up
                        if not self.show_details:
                            self.scroll_offset = min(self.scroll_offset + 30, 0)
                    elif event.button == 5:  # Scroll down
                        if not self.show_details:
                            episode_height = 70  # Height of each episode with metadata
                            max_scroll = -max(0, len(self.episodes) * episode_height - 350)
                            self.scroll_offset = max(self.scroll_offset - 30, max_scroll)
            
            # Check if music is still playing
            if self.is_playing and not pygame.mixer.music.get_busy() and not self.is_paused:
                self.is_playing = False
            
            self.draw()
            self.clock.tick(30)
        
        pygame.quit()

if __name__ == "__main__":
    player = PodcastPlayer()
    player.run()