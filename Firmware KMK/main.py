"""
SnekPad KMK Firmware

Hardware: Raspberry Pi Pico with KMK
- 6 mechanical switches in 3×2 matrix
- 1 rotary encoder with switch
- OLED display (128x64) with custom UI

Button Layout:
  [S1-Copy] [S2-Paste] [S3-Terminal]
  [S4-F13]  [S5-F14]   [S6-F15]

Encoder: Volume control (click to mute)
"""

import board
from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation
from kmk.modules.encoder import EncoderHandler
from kmk.extensions.display import Display, TextEntry, ImageEntry
from kmk.extensions.display.ssd1306 import SSD1306
from kmk.handlers.sequences import simple_key_sequence

# SNEKPAD LOGO (32x32 pixels)
# Logo bitmap converted to bytearray
# Format: 1 bit per pixel, 32x32 = 128 bytes
SNEKPAD_LOGO = bytearray([
    0x00, 0x00, 0x00, 0x00,  # Row 1
    0x00, 0x00, 0x00, 0x00,  # Row 2
    0x00, 0x00, 0x60, 0x00,  # Row 3
    0x00, 0x00, 0xF0, 0x00,  # Row 4
    0x00, 0x01, 0xF8, 0x00,  # Row 5
    0x00, 0x03, 0xFC, 0x00,  # Row 6
    0x00, 0x07, 0xFE, 0x00,  # Row 7
    0x00, 0x0F, 0xFF, 0x00,  # Row 8
    0x00, 0x1F, 0xFF, 0x00,  # Row 9
    0x00, 0x3F, 0xFE, 0x00,  # Row 10
    0x00, 0x7F, 0xFC, 0x00,  # Row 11
    0x00, 0xFF, 0xF8, 0x00,  # Row 12 - Snake head curve
    0x01, 0xFF, 0xF0, 0x00,  # Row 13
    0x03, 0xFC, 0xE0, 0x00,  # Row 14
    0x07, 0xF0, 0xC0, 0x00,  # Row 15
    0x0F, 0xE1, 0x80, 0x00,  # Row 16 - Snake body
    0x1F, 0xC3, 0x00, 0x00,  # Row 17
    0x3F, 0x86, 0x00, 0x00,  # Row 18
    0x7E, 0x0C, 0x00, 0x00,  # Row 19
    0x7C, 0x18, 0x00, 0x00,  # Row 20
    0x78, 0x30, 0x00, 0x00,  # Row 21
    0x70, 0x60, 0x00, 0x00,  # Row 22
    0x60, 0xC0, 0x00, 0x00,  # Row 23
    0x61, 0x80, 0x00, 0x00,  # Row 24
    0x63, 0x00, 0x00, 0x00,  # Row 25
    0x66, 0x00, 0x00, 0x00,  # Row 26
    0x6C, 0x00, 0x00, 0x00,  # Row 27
    0x78, 0x00, 0x00, 0x00,  # Row 28 - Snake tail
    0x70, 0x00, 0x00, 0x00,  # Row 29
    0x60, 0x00, 0x00, 0x00,  # Row 30
    0x00, 0x00, 0x00, 0x00,  # Row 31
    0x00, 0x00, 0x00, 0x00,  # Row 32
])

# DISPLAY EXTENSION WITH VOLUME BAR

class SnekPadDisplay(Display):
    """Custom display with volume bar and dynamic updates"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.volume_level = 50  # 0-100
        self.is_muted = False
        self.welcome_shown = False
        self.welcome_timer = 0
        
    def update_volume(self, delta):
        """Update volume level (+1 or -1)"""
        self.volume_level = max(0, min(100, self.volume_level + (delta * 5)))
        self.is_muted = False
        
    def toggle_mute(self):
        """Toggle mute state"""
        self.is_muted = not self.is_muted
        
    def draw_volume_bar(self, display):
        """Draw volume bar on OLED"""
        # Volume bar position (bottom of screen)
        bar_x = 0
        bar_y = 54
        bar_width = 96  # Leave room for logo
        bar_height = 8
        
        # Draw border
        for x in range(bar_width):
            display.pixel(bar_x + x, bar_y, 1)
            display.pixel(bar_x + x, bar_y + bar_height, 1)
        for y in range(bar_height + 1):
            display.pixel(bar_x, bar_y + y, 1)
            display.pixel(bar_x + bar_width, bar_y + y, 1)
        
        # Fill volume level
        if not self.is_muted:
            fill_width = int((bar_width - 2) * self.volume_level / 100)
            for x in range(fill_width):
                for y in range(1, bar_height):
                    display.pixel(bar_x + 1 + x, bar_y + y, 1)
        
        # Mute indicator
        if self.is_muted:
            # Draw X in the bar
            for i in range(8):
                display.pixel(bar_x + bar_width // 2 - 4 + i, bar_y + 2 + i, 1)
                display.pixel(bar_x + bar_width // 2 + 4 - i, bar_y + 2 + i, 1)

    def during_bootup(self, keyboard):
        """Show welcome screen"""
        self.welcome_shown = False
        self.welcome_timer = 0
        
    def on_runtime_enable(self, keyboard):
        """Called when display is ready"""
        super().on_runtime_enable(keyboard)
        
    def on_runtime_disable(self, keyboard):
        """Called when display is disabled"""
        super().on_runtime_disable(keyboard)

# KEYBOARD SETUP

keyboard = KMKKeyboard()

# MATRIX CONFIGURATION (3 cols × 2 rows, COL2ROW)

keyboard.col_pins = (board.GP4, board.GP5, board.GP6)  # 3 columns
keyboard.row_pins = (board.GP9, board.GP10)            # 2 rows
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# ROTARY ENCODER SETUP WITH VOLUME TRACKING

class VolumeEncoder(EncoderHandler):
    """Custom encoder handler with volume tracking"""
    
    def __init__(self, display_ext):
        super().__init__()
        self.display_ext = display_ext
        
    def on_runtime_enable(self, keyboard):
        super().on_runtime_enable(keyboard)
        
    def on_runtime_disable(self, keyboard):
        super().on_runtime_disable(keyboard)
        
encoder_handler = VolumeEncoder(None)  # Will link display later
keyboard.modules.append(encoder_handler)

# Encoder pins: A=GP11, B=GP12, Switch=GP14
encoder_handler.pins = (
    (board.GP11, board.GP12, board.GP14,),
)

# We'll override the encoder behavior to track volume
_original_encoder_process = encoder_handler.process_key

def custom_encoder_process(keyboard, current_key, is_pressed, int_coord):
    """Custom encoder processing with volume tracking"""
    result = _original_encoder_process(keyboard, current_key, is_pressed, int_coord)
    
    # Track volume changes
    if encoder_handler.display_ext and current_key:
        if current_key == KC.VOLU:
            encoder_handler.display_ext.update_volume(1)
        elif current_key == KC.VOLD:
            encoder_handler.display_ext.update_volume(-1)
        elif current_key == KC.MUTE:
            encoder_handler.display_ext.toggle_mute()
    
    return result

encoder_handler.process_key = custom_encoder_process

# Encoder map: [clockwise, counter-clockwise, button_press]
encoder_handler.map = [
    ((KC.VOLU, KC.VOLD, KC.MUTE),),
]

# OLED DISPLAY SETUP

driver = SSD1306(
    i2c=board.I2C(),
    device_address=0x3C,
)

# Create custom display with logo and volume bar
display = SnekPadDisplay(
    display=driver,
    entries=[
        TextEntry(text="Welcome to", x=0, y=0),
        TextEntry(text="SnekPad Mark 1", x=0, y=12),
        TextEntry(text="", x=0, y=28),  # Dynamic text area
        # Logo will be drawn manually on the right side
    ],
    width=128,
    height=64,
)

# Link display to encoder
encoder_handler.display_ext = display

keyboard.extensions.append(display)

# Custom display rendering
_original_update = display.update

def custom_display_update():
    """Custom display update with logo and volume bar"""
    display.display.fill(0)  # Clear display
    
    # Show welcome for first 3 seconds
    if not display.welcome_shown:
        display.welcome_timer += 1
        if display.welcome_timer < 600:  # ~3 seconds at normal update rate
            # Welcome screen
            display.display.text("Welcome to", 0, 0, 1)
            display.display.text("SnekPad", 0, 16, 1)
            display.display.text("Mark 1", 0, 32, 1)
        else:
            display.welcome_shown = True
    else:
        # Main screen
        # Text on left side
        display.display.text("SnekPad v1.0", 0, 0, 1)
        display.display.text("Layer: 0", 0, 16, 1)
        
        # Volume info
        vol_text = f"Vol: {display.volume_level}%"
        if display.is_muted:
            vol_text = "Vol: MUTED"
        display.display.text(vol_text, 0, 32, 1)
        
        # Draw volume bar at bottom
        display.draw_volume_bar(display.display)
    
    # Draw logo on right side (96, 0) - 32x32 pixels
    logo_x = 96
    logo_y = 0
    
    for byte_idx in range(len(SNEKPAD_LOGO)):
        byte_val = SNEKPAD_LOGO[byte_idx]
        row = byte_idx // 4
        col_offset = (byte_idx % 4) * 8
        
        for bit in range(8):
            if byte_val & (1 << (7 - bit)):
                display.display.pixel(logo_x + col_offset + bit, logo_y + row, 1)
    
    display.display.show()

display.update = custom_display_update

# KEYMAP CONFIGURATION
# Custom macros for common operations
COPY = KC.LCTL(KC.C)
PASTE = KC.LCTL(KC.V)
TERMINAL = KC.LCTL(KC.LALT(KC.T))

# For Mac users, uncomment these:
# COPY = KC.LCMD(KC.C)
# PASTE = KC.LCMD(KC.V)
# TERMINAL = KC.LCMD(KC.SPACE)

# Software-mappable keys
F13_KEY = KC.F13
F14_KEY = KC.F14
F15_KEY = KC.F15

# KEYMAP LAYOUT

keyboard.keymap = [
    # Layer 0: Default Layer
    [
        COPY,     PASTE,    TERMINAL,    # Row 1: S1, S2, S3
        F13_KEY,  F14_KEY,  F15_KEY,     # Row 2: S4, S5, S6
    ],
]

# START KEYBOARD

keyboard.go()
