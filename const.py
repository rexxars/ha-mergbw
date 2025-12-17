"""Constants for MeRGBW integration."""
from typing import Final

DOMAIN: Final = "mergbw"

# Bluetooth UUIDs
SERVICE_UUID: Final = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID: Final = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID: Final = "0000fff4-0000-1000-8000-00805f9b34fb"

# Advertisement signature (in Type 2 - Complete 16-bit Service UUIDs)
ADVERTISEMENT_SIGNATURE: Final = bytes([0x19, 0x35])

# Device types
DEVICE_TYPE_LETTERS: Final = 1
DEVICE_TYPE_RGB_LINE: Final = 2
DEVICE_TYPE_STAR: Final = 3
DEVICE_TYPE_HANDLE: Final = 4
DEVICE_TYPE_SUNSET: Final = 5
DEVICE_TYPE_BULB: Final = 6
DEVICE_TYPE_CEILING_COLORFUL: Final = 7
DEVICE_TYPE_CEILING_RGB: Final = 8

DEVICE_TYPE_NAMES: Final = {
    1: "Letters Lights",
    2: "RGB Line/Strip",
    3: "Star Lights",
    4: "Handle Lights",
    5: "Sunset Lights",
    6: "Bulb",
    7: "Ceiling Lights (Colorful)",
    8: "Ceiling Lights (RGB)",
}

# Device types that require binding
BINDING_REQUIRED_TYPES: Final = {DEVICE_TYPE_LETTERS, DEVICE_TYPE_HANDLE}

# Device types using 2-byte brightness
TWO_BYTE_BRIGHTNESS_TYPES: Final = {DEVICE_TYPE_LETTERS, DEVICE_TYPE_RGB_LINE, DEVICE_TYPE_HANDLE}

# Command codes
CMD_SYNC_STATUS: Final = 0x00
CMD_POWER: Final = 0x01
CMD_FIRMWARE_INFO: Final = 0x02
CMD_SET_COLOR: Final = 0x03
CMD_SET_PART_COLOR: Final = 0x04
CMD_SET_BRIGHTNESS: Final = 0x05
CMD_SET_MODE: Final = 0x06
CMD_SET_MUSIC_MODE: Final = 0x07
CMD_SET_MUSIC_SENS: Final = 0x08
CMD_SET_DIY_MODE: Final = 0x09
CMD_SET_TIMER: Final = 0x0A
CMD_SET_LED_NUM: Final = 0x0B
CMD_SYNC_TIME: Final = 0x0C
CMD_CONFIG_MODE: Final = 0x0D
CMD_CHECK_BIND_STATE: Final = 0x0E
CMD_SET_MODE_SPEED: Final = 0x0F
CMD_SET_WHITE_LIGHT: Final = 0x10
CMD_SET_WHITE_BRIGHTNESS: Final = 0x11
CMD_SET_COLD_AND_WARM: Final = 0x12

# Packet constants
HEADER_CMD: Final = 0x55
HEADER_RSP: Final = 0x56
SEQ_SINGLE: Final = 0xFF

# Bind states
BIND_STATE_BOUND: Final = 0x01
BIND_STATE_UNBIND: Final = 0x02
BIND_STATE_TIMEOUT: Final = 0x03
