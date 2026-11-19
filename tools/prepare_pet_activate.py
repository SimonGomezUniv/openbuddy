"""Mount the SD for activation of an existing pet; never format or copy files."""

import json
import os
import vfs
from machine import Pin, SDCard, SPI
import board_config as cfg


def valid_name(value):
    return (isinstance(value, str) and 1 <= len(value) <= 64
            and all(character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value))


if not valid_name(PACK_ID):
    raise ValueError("Unsafe pet id")
Pin(cfg.LCD_CS, Pin.OUT, value=1)
Pin(cfg.SD_CS, Pin.OUT, value=1)
spi = SPI(cfg.LCD_SPI_ID, baudrate=1_000_000, sck=Pin(cfg.LCD_SCLK),
          mosi=Pin(cfg.LCD_MOSI), miso=Pin(cfg.SD_MISO))
spi.deinit()
sd = SDCard(slot=2, sck=Pin(cfg.LCD_SCLK), mosi=Pin(cfg.LCD_MOSI),
            miso=Pin(cfg.SD_MISO), cs=Pin(cfg.SD_CS), freq=10_000_000)
vfs.mount(sd, cfg.SD_MOUNT)
pack_root = cfg.PET_DIRECTORY + "/" + PACK_ID
if os.stat(pack_root + "/manifest.json")[6] > 8192:
    raise ValueError("Manifest too large")
with open(pack_root + "/manifest.json") as handle:
    manifest = json.load(handle)
if manifest.get("id") != PACK_ID or manifest.get("format") != "RGB565-BE":
    raise ValueError("Unexpected pet pack")
print("Existing pet pack ready for verification:", PACK_ID)
