
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


from media_player import Episode

class Theme:
    """UI Theme configuration"""
    BG = (30, 30, 40)
    BUTTON = (70, 130, 180)
    BUTTON_HOVER = (100, 160, 210)
    TEXT = (255, 255, 255)
    TEXT_SECONDARY = (180, 180, 180)
    PROGRESS = (50, 205, 50)
    PROGRESS_BG = (60, 60, 70)
    PANEL_BG = (40, 40, 50)
    HIGHLIGHT = (50, 50, 60)

class Button:
    """Reusable button component"""
    
    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font):
        self.rect = rect
        self.text = text
        self.font = font
        self.is_hovered = False
    
    def update(self, mouse_pos: Tuple[int, int]):
        """Update button state"""
        self.is_hovered = self.rect.collidepoint(mouse_pos)
    
    def draw(self, screen: pygame.Surface):
        """Draw the button"""
        color = Theme.BUTTON_HOVER if self.is_hovered else Theme.BUTTON
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, Theme.TEXT, self.rect, 2)
        
        text_surf = self.font.render(self.text, True, Theme.TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
    
    def is_clicked(self, pos: Tuple[int, int]) -> bool:
        """Check if button was clicked"""
        return self.rect.collidepoint(pos)

class ProgressBar:
    """Reusable progress bar component"""
    
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.progress = 0
    
    def set_progress(self, progress: float):
        """Set progress (0-100)"""
        self.progress = max(0, min(100, progress))
    
    def draw(self, screen: pygame.Surface):
        """Draw the progress bar"""
        pygame.draw.rect(screen, Theme.PROGRESS_BG, self.rect)
        if self.progress > 0:
            fill_width = int(self.rect.width * (self.progress / 100))
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_width, self.rect.height)
            pygame.draw.rect(screen, Theme.PROGRESS, fill_rect)

class EpisodeListView:
    """Manages the episode list display"""
    
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, small_font: pygame.font.Font):
        self.rect = rect
        self.font = font
        self.small_font = small_font
        self.scroll_offset = 0
        self.episode_height = 75  # Increased height for better spacing
        self.episode_rects: List[pygame.Rect] = []
        self.hovered_index = -1
    
    def update(self, mouse_pos: Tuple[int, int]):
        """Update list state"""
        self.hovered_index = -1
        for i, rect in enumerate(self.episode_rects):
            if rect.collidepoint(mouse_pos):
                self.hovered_index = i
                break
    
    def draw(self, screen: pygame.Surface, episodes: List[Episode], current_episode: Optional[Episode]):
        """Draw the episode list"""
        # Create a clipping region for the list area
        screen.set_clip(self.rect)
        
        self.episode_rects.clear()
        y_offset = self.rect.y
        
        for i, episode in enumerate(episodes):
            # Calculate actual y position
            actual_y = y_offset + self.scroll_offset
            
            # Check if episode is visible
            if actual_y + self.episode_height < self.rect.y:
                y_offset += self.episode_height + 10  # Increased spacing between episodes
                continue
            if actual_y > self.rect.bottom:
                break
            
            # Create episode rect
            ep_rect = pygame.Rect(
                self.rect.x, 
                actual_y, 
                self.rect.width, 
                self.episode_height
            )
            self.episode_rects.append(ep_rect)
            
            # Draw background
            if current_episode and episode == current_episode:
                pygame.draw.rect(screen, Theme.HIGHLIGHT, ep_rect)
                pygame.draw.rect(screen, Theme.BUTTON, ep_rect, 2)
            elif i == self.hovered_index:
                pygame.draw.rect(screen, Theme.PANEL_BG, ep_rect)
            
            # Draw title
            title = episode.title
            if len(title) > 90:
                title = title[:87] + '...'
            title_text = self.font.render(f"{i+1}. {title}", True, Theme.TEXT)
            screen.blit(title_text, (ep_rect.x + 10, ep_rect.y + 5))
            
            # Draw metadata with better vertical spacing
            metadata_parts = [episode.formatted_date]
            if episode.formatted_duration:
                metadata_parts.append(f"Duration: {episode.formatted_duration}")
            if episode.size_mb:
                metadata_parts.append(f"Size: {episode.size_mb:.1f} MB")
            
            metadata_text = " | ".join(metadata_parts)
            meta_surface = self.small_font.render(metadata_text, True, Theme.TEXT_SECONDARY)
            screen.blit(meta_surface, (ep_rect.x + 10, ep_rect.y + 32))
            
            # Draw description preview with adjusted position
            if episode.description:
                desc = episode.description[:120] + '...' if len(episode.description) > 120 else episode.description
                desc_surface = self.small_font.render(desc, True, Theme.TEXT_SECONDARY)
                screen.blit(desc_surface, (ep_rect.x + 10, ep_rect.y + 52))
            
            y_offset += self.episode_height + 10  # Increased spacing between episodes
        
        # Remove clipping
        screen.set_clip(None)
    
    def scroll(self, delta: int, episode_count: int):
        """Handle scrolling"""
        max_scroll = -max(0, episode_count * (self.episode_height + 10) - self.rect.height)
        self.scroll_offset = max(min(self.scroll_offset + delta, 0), max_scroll)
    
    def get_clicked_episode_index(self, pos: Tuple[int, int]) -> int:
        """Get the index of clicked episode, or -1 if none"""
        for i, rect in enumerate(self.episode_rects):
            if rect.collidepoint(pos):
                return i
        return -1

class EpisodeDetailsDialog:
    """Modal dialog for episode details"""
    
    def __init__(self, screen_size: Tuple[int, int], fonts: Dict):
        self.screen_width, self.screen_height = screen_size
        self.fonts = fonts
        self.episode: Optional[Episode] = None
        self.panel_width = 1000
        self.panel_height = 600
        self.panel_x = (self.screen_width - self.panel_width) // 2
        self.panel_y = (self.screen_height - self.panel_height) // 2
        
        # Create buttons
        self.close_button = Button(
            pygame.Rect(self.panel_x + self.panel_width - 40, self.panel_y + 10, 30, 30),
            "X", fonts['normal']
        )
        self.play_button = Button(
            pygame.Rect(self.panel_x + self.panel_width // 2 - 60, 
                       self.panel_y + self.panel_height - 60, 120, 40),
            "Play Episode", fonts['normal']
        )
    
    def show(self, episode: Episode):
        """Show dialog for an episode"""
        self.episode = episode
    
    def hide(self):
        """Hide the dialog"""
        self.episode = None
    
    def update(self, mouse_pos: Tuple[int, int]):
        """Update dialog components"""
        if self.episode:
            self.close_button.update(mouse_pos)
            self.play_button.update(mouse_pos)
    
    def draw(self, screen: pygame.Surface):
        """Draw the dialog"""
        if not self.episode:
            return
        
        # Draw overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(240)
        overlay.fill((20, 20, 30))
        screen.blit(overlay, (0, 0))
        
        # Draw panel
        panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_width, self.panel_height)
        pygame.draw.rect(screen, Theme.PANEL_BG, panel_rect)
        pygame.draw.rect(screen, Theme.BUTTON, panel_rect, 3)
        
        # Draw close button
        self.close_button.draw(screen)
        
        # Draw title
        self._draw_wrapped_text(
            screen, self.episode.title, 
            self.panel_x + 30, self.panel_y + 30,
            self.panel_width - 100, self.fonts['title'], 
            Theme.TEXT, max_lines=2
        )
        
        # Draw metadata
        y_pos = self.panel_y + 110
        metadata = [
            f"Published: {self.episode.formatted_date}",
            f"Duration: {self.episode.formatted_duration}" if self.episode.formatted_duration else None,
            f"File size: {self.episode.size_mb:.1f} MB" if self.episode.size_mb else None
        ]
        
        for item in metadata:
            if item:
                text_surf = self.fonts['normal'].render(item, True, Theme.TEXT_SECONDARY)
                screen.blit(text_surf, (self.panel_x + 30, y_pos))
                y_pos += 25
        
        # Draw description
        y_pos += 20
        if self.episode.description:
            max_lines = (self.panel_height - (y_pos - self.panel_y) - 80) // 22
            self._draw_wrapped_text(
                screen, self.episode.description,
                self.panel_x + 30, y_pos,
                self.panel_width - 60, self.fonts['small'],
                Theme.TEXT, max_lines=max_lines
            )
        
        # Draw play button
        self.play_button.draw(screen)
    
    def _draw_wrapped_text(self, screen, text, x, y, max_width, font, color, max_lines=None):
        """Helper to draw wrapped text"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if font.size(test_line)[0] < max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        lines_to_draw = lines[:max_lines] if max_lines else lines
        line_height = font.get_height() + 2
        
        for i, line in enumerate(lines_to_draw):
            text_surf = font.render(line, True, color)
            screen.blit(text_surf, (x, y + i * line_height))
        
        return y + len(lines_to_draw) * line_height
    
    def handle_click(self, pos: Tuple[int, int]) -> Optional[str]:
        """Handle clicks in the dialog. Returns action or None"""
        if not self.episode:
            return None
        
        if self.close_button.is_clicked(pos):
            return "close"
        elif self.play_button.is_clicked(pos):
            return "play"
        return None
