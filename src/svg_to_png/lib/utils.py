import svgpathtools
from PIL import ImageFont, ImageDraw, Image
import base64
from io import BytesIO
import os

def calculate_size(name_arg):
    max_width = 0
    num_lines = 0
    name = name_arg if isinstance(name_arg, list) else name_arg.split("\r\n")
    for name_part in name:
        if name_part:
            max_width = max(max_width, len(name_part) * 5.6)
            num_lines += 1
    newWidth = max_width * 1.1
    newHeight = num_lines * 14 * 1.1
    return (newWidth, newHeight)

class BoundingBox:
    def __init__(self, xmin, xmax, ymin, ymax):
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        
    def add_padding(self, padding):
        self.xmin -= padding
        self.xmax += padding
        self.ymin -= padding
        self.ymax += padding
        
    def get_size(self):
        return (self.xmax - self.xmin, self.ymax - self.ymin)

def get_bbox(svg_file):
    paths, _ = svgpathtools.svgstr2paths(svg_file)

    for i, path in enumerate(paths):
        if i == 0:
            # Initialise the overall min-max with the first path
            xmin, xmax, ymin, ymax = path.bbox()
        else:
            # Expand bounds to match path bounds if needed
            p_xmin, p_xmax, p_ymin, p_ymax = path.bbox()
            xmin = min(xmin, p_xmin)
            xmax = max(xmax, p_xmax)
            ymin = min(ymin, p_ymin)
            ymax = max(ymax, p_ymax)
    
    return BoundingBox(xmin, xmax, ymin, ymax)

def convert_base64_jpeg_to_png(base64_jpeg_string):
    # Decode the base64 string to bytes
    jpeg_bytes = base64.b64decode(base64_jpeg_string)
    image = Image.open(BytesIO(jpeg_bytes))
    
    # Create a bytes buffer to hold the PNG data
    png_bytes_io = BytesIO()
    
    # Save the image as PNG to the bytes buffer
    image.save(png_bytes_io, format='PNG')
    
    # Get the PNG bytes from the buffer
    png_bytes = png_bytes_io.getvalue()
    
    return png_bytes

# The scale factor
SCALE_FACTOR = 64

def get_text_width(text, font, font_size, scale_factor=SCALE_FACTOR):
    """
    Calculate the width of the text using a scaled-up font size for accuracy.
    :param text: The text to measure.
    :param font: The loaded ImageFont object.
    :param font_size: The original font size.
    :param scale_factor: The factor by which the font size is scaled up for measurement.
    :return: The width of the text.
    """
    scaled_font_size = font_size * scale_factor
    font = font.font_variant(size=scaled_font_size)

    # Create a dummy image and draw context to get the size
    image = Image.new("RGB", (1000, 100))
    draw_context = ImageDraw.Draw(image)
    bbox = draw_context.textbbox((0, 0), text, font=font)
    width = (bbox[2] - bbox[0]) / scale_factor  # Divide by the scale factor to get the actual width

    return width

DEFAULT_FONT_PATH = os.path.join(os.path.dirname(__file__), "OpenSans-Regular.ttf")

def wrap_text(text, max_width, font_size, font_path=DEFAULT_FONT_PATH):
    """
    Wrap the text so that it fits within the specified width.
    :param text: The text to wrap.
    :param max_width: The maximum width for the text.
    :param font_size: The font size to use.
    :param font_path: The path to the font file.
    :return: A list of wrapped lines.
    """
    font = ImageFont.truetype(font_path, font_size)

    lines = []
    current_line = ""
    words = text.split(' ')

    for word in words:
        # Handle explicit new lines in the text
        if '\n' in word:
            parts = word.split('\n')
            for part in parts[:-1]:
                test_line = f"{current_line} {part}".strip()
                lines.append(test_line)
                current_line = ""
            word = parts[-1]

        test_line = f"{current_line} {word}".strip() if current_line else word
        test_line_width = get_text_width(test_line, font, font_size)

        if test_line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Binary search for the maximum number of characters that fit within the max width
                low, high = 0, len(word)
                while low < high:
                    mid = (low + high) // 2
                    if get_text_width(word[:mid + 1], font, font_size) <= max_width:
                        low = mid + 1
                    else:
                        high = mid
                part = word[:low]
                lines.append(part)
                current_line = word[low:]

    if current_line:
        lines.append(current_line)

    return lines