#!/usr/bin/env python3
import time
import sys
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont

def main():
    # Matrix configuration
    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = 2
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat-pwm'
    options.brightness = 90
    options.pwm_bits = 10
    options.pwm_lsb_nanoseconds = 150
    options.led_rgb_sequence = 'RGB'
    options.pixel_mapper_config = ''
    options.row_address_type = 0
    options.multiplexing = 0
    options.disable_hardware_pulsing = False
    options.show_refresh_rate = False
    options.limit_refresh_rate_hz = 90
    options.gpio_slowdown = 2

    # Initialize the matrix
    matrix = RGBMatrix(options=options)
    canvas = matrix.CreateFrameCanvas()

    # Load the PressStart2P font
    font_path = "assets/fonts/PressStart2P-Regular.ttf"
    font_size = 1
    font = ImageFont.truetype(font_path, font_size)

    # Create a PIL image and drawing context
    image = Image.new('RGB', (matrix.width, matrix.height))
    draw = ImageDraw.Draw(image)

    # Text to display
    text = " Chuck Builds"

    # Find the largest font size that fits
    max_font_size = 100  # Set a reasonable maximum font size
    while font_size <= max_font_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        if text_width > matrix.width or text_height > matrix.height:
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            break
        font_size += 1
    else:
        # If the loop exits without breaking, use the maximum font size
        font_size = max_font_size
        font = ImageFont.truetype(font_path, font_size)

    # Center the text
    x = (matrix.width - text_width) // 2
    y = (matrix.height - text_height) // 2

    # Draw the text
    draw.text((x, y), text, font=font, fill=(255, 255, 255))

    # Display the image
    canvas.SetImage(image)
    matrix.SwapOnVSync(canvas)

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        matrix.Clear()
        sys.exit(0)

if __name__ == "__main__":
    main() 