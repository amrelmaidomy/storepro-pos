"""Shared light palette for the offline desktop UI."""
import customtkinter as ctk

BG='#F3F6FA'
SURFACE='#FFFFFF'
TEXT='#162C3B'
MUTED='#738391'
PRIMARY='#087F8C'
HOVER='#066874'
TINT='#E5F4F3'
BORDER='#E2E9EF'
DANGER='#C65050'
NAV='#122D3B'


def configure():
    ctk.set_appearance_mode('light')
    ctk.set_default_color_theme('blue')
    # Keep all existing administration screens on the same palette.
    ctk.ThemeManager.theme['CTkFrame'].update(fg_color=[SURFACE,SURFACE],top_fg_color=[BG,BG],border_color=[BORDER,BORDER])
    ctk.ThemeManager.theme['CTkButton'].update(fg_color=[PRIMARY,PRIMARY],hover_color=[HOVER,HOVER],corner_radius=10)
    ctk.ThemeManager.theme['CTkLabel'].update(text_color=[TEXT,TEXT])
    ctk.ThemeManager.theme['CTkEntry'].update(fg_color=[SURFACE,SURFACE],border_color=[BORDER,BORDER],text_color=[TEXT,TEXT],corner_radius=8)
    ctk.ThemeManager.theme['CTkComboBox'].update(fg_color=[SURFACE,SURFACE],border_color=[BORDER,BORDER],button_color=[BORDER,BORDER],button_hover_color=[TINT,TINT],text_color=[TEXT,TEXT])
