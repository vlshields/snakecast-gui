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

# Import data models and services from media_player.py
from media_player import Episode, PlayerState, PodcastFeedService, DownloadService, AudioPlayer

# Import UI components from ui.py
from ui import Theme, Button, ProgressBar, EpisodeListView, EpisodeDetailsDialog



class PodcastPlayerApp:
    """Main application controller"""
    
    def __init__(self):
        pygame.init()
        
        # Display setup
        self.width = 1920
        self.height = 1080
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Podcast Player")
        self.clock = pygame.time.Clock()
        
        # Fonts
        self.fonts = {
            'title': pygame.font.Font(None, 62),
            'normal': pygame.font.Font(None, 44),
            'small': pygame.font.Font(None, 40)
        }
        
        # Services
        self.downloads_dir = Path("downloads")
        self.feed_service = PodcastFeedService()
        self.download_service = DownloadService(self.downloads_dir)
        self.audio_player = AudioPlayer()
        
        # UI Components
        self._init_ui_components()
        
        # State
        self.episodes: List[Episode] = []
        self.selected_episode: Optional[Episode] = None
        self.last_click_time = 0
        self.double_click_threshold = 500
        
        # Initial data load
        self.refresh_episodes()
    
    def _init_ui_components(self):
        """Initialize UI components"""
        # Layout constants
        margin = 50
        button_height = 60
        button_width = 150
        bottom_area_height = 320  # Increased space for controls and status
        
        # Buttons - positioned in bottom control area
        button_y = self.height - 120  # Move buttons up slightly for better spacing
        
        self.refresh_button = Button(
            pygame.Rect(self.width - button_width - margin, 20, button_width, 50),  # Top right corner
            "Refresh", self.fonts['normal']
        )
        self.play_pause_button = Button(
            pygame.Rect(self.width // 2 - button_width - 25, button_y, button_width, button_height),
            "Play", self.fonts['normal']
        )
        self.stop_button = Button(
            pygame.Rect(self.width // 2 + 25, button_y, button_width, button_height),
            "Stop", self.fonts['normal']
        )
        
        # Progress bar - above buttons with more spacing
        progress_y = button_y - 80
        self.download_progress = ProgressBar(
            pygame.Rect(margin, progress_y, self.width - (margin * 2), 30)
        )
        
        # Episode list - main content area (leave space for bottom controls)
        list_top = 100
        list_height = self.height - list_top - bottom_area_height
        self.episode_list = EpisodeListView(
            pygame.Rect(margin, list_top, self.width - (margin * 2), list_height),
            self.fonts['normal'], self.fonts['small']
        )
        
        # Details dialog
        self.details_dialog = EpisodeDetailsDialog(
            (self.width, self.height), self.fonts
        )
    
    def refresh_episodes(self):
        """Refresh the episode list"""
        self.episodes = self.feed_service.fetch_episodes()
    
    def play_episode(self, episode: Episode):
        """Start playing an episode"""
        def download_and_play():
            file_path = self.download_service.download_episode(
                episode,
                callback=lambda p: self.download_progress.set_progress(p)
            )
            self.audio_player.load_and_play(file_path, episode)
        
        thread = threading.Thread(target=download_and_play)
        thread.daemon = True
        thread.start()
    
    def update(self):
        """Update application state"""
        mouse_pos = pygame.mouse.get_pos()
        
        # Update UI components
        self.refresh_button.update(mouse_pos)
        self.play_pause_button.update(mouse_pos)
        self.stop_button.update(mouse_pos)
        self.episode_list.update(mouse_pos)
        self.details_dialog.update(mouse_pos)
        
        # Update button text
        if self.audio_player.state == PlayerState.PLAYING:
            self.play_pause_button.text = "Pause"
        else:
            self.play_pause_button.text = "Play"
        
        # Check if music stopped
        if self.audio_player.state == PlayerState.PLAYING:
            if not pygame.mixer.music.get_busy():
                self.audio_player.state = PlayerState.STOPPED
    
    def draw(self):
        """Draw the application"""
        self.screen.fill(Theme.BG)
        
        # Title - top left
        title_text = self.fonts['title'].render("Podcast Player", True, Theme.TEXT)
        self.screen.blit(title_text, (50, 25))
        
        # Buttons
        self.refresh_button.draw(self.screen)
        self.play_pause_button.draw(self.screen)
        self.stop_button.draw(self.screen)
        
        # Episode list
        self.episode_list.draw(self.screen, self.episodes, self.audio_player.current_episode)
        
        # Status area - position above control buttons with more spacing
        status_y = self.height - 240  # Increased spacing above buttons and progress bar
        
        # Current episode info
        if self.audio_player.current_episode:
            title = self.audio_player.current_episode.title[:100]
            if len(self.audio_player.current_episode.title) > 100:
                title += "..."
            current_text = self.fonts['normal'].render(
                f"Now Playing: {title}", True, Theme.TEXT
            )
            self.screen.blit(current_text, (50, status_y))
        
        # Playback time info
        if self.audio_player.state in [PlayerState.PLAYING, PlayerState.PAUSED]:
            pos = self.audio_player.get_position()
            if pos > 0:
                time_text = self.fonts['normal'].render(
                    f"Time: {int(pos//60)}:{int(pos%60):02d}",
                    True, Theme.TEXT
                )
                self.screen.blit(time_text, (50, status_y + 40))
        
        # Download progress
        if self.download_service.is_downloading:
            self.download_progress.set_progress(self.download_service.progress)
            self.download_progress.draw(self.screen)
            progress_text = self.fonts['small'].render(
                f"Downloading: {self.download_service.progress:.1f}%",
                True, Theme.TEXT
            )
            # Center the download text above the progress bar
            text_rect = progress_text.get_rect()
            text_rect.centerx = self.width // 2
            text_rect.bottom = self.download_progress.rect.top - 5
            self.screen.blit(progress_text, text_rect)
        
        # Details dialog (drawn last to be on top)
        self.details_dialog.draw(self.screen)
        
        pygame.display.flip()
    
    def handle_event(self, event):
        """Handle pygame events"""
        if event.type == pygame.QUIT:
            return False
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.audio_player.toggle_play_pause()
            elif event.key == pygame.K_s:
                self.audio_player.stop()
            elif event.key == pygame.K_ESCAPE:
                if self.details_dialog.episode:
                    self.details_dialog.hide()
                else:
                    return False
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                self.handle_click(event.pos)
            elif event.button == 4:  # Scroll up
                if not self.details_dialog.episode:
                    self.episode_list.scroll(30, len(self.episodes))
            elif event.button == 5:  # Scroll down
                if not self.details_dialog.episode:
                    self.episode_list.scroll(-30, len(self.episodes))
        
        return True
    
    def handle_click(self, pos):
        """Handle mouse clicks"""
        # Check dialog first
        if self.details_dialog.episode:
            action = self.details_dialog.handle_click(pos)
            if action == "close":
                self.details_dialog.hide()
            elif action == "play":
                self.play_episode(self.details_dialog.episode)
                self.details_dialog.hide()
            return
        
        # Check buttons
        if self.refresh_button.is_clicked(pos):
            self.refresh_episodes()
        elif self.play_pause_button.is_clicked(pos):
            self.audio_player.toggle_play_pause()
        elif self.stop_button.is_clicked(pos):
            self.audio_player.stop()
        else:
            # Check episode list
            episode_index = self.episode_list.get_clicked_episode_index(pos)
            if episode_index >= 0 and episode_index < len(self.episodes):
                # Check for double click
                current_time = pygame.time.get_ticks()
                if current_time - self.last_click_time < self.double_click_threshold:
                    # Double click - show details
                    self.details_dialog.show(self.episodes[episode_index])
                else:
                    # Single click - play episode
                    self.play_episode(self.episodes[episode_index])
                self.last_click_time = current_time
    
    def run(self):
        """Main application loop"""
        running = True
        
        while running:
            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
            
            self.update()
            self.draw()
            self.clock.tick(30)
        
        pygame.quit()

# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    app = PodcastPlayerApp()
    app.run()