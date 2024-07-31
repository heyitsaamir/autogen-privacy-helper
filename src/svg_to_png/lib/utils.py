from svgpathtools import svgstr2paths
from PIL import Image
import base64
from io import BytesIO

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
    paths, _ = svgstr2paths(svg_file)

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