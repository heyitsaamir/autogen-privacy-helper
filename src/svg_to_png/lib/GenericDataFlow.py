import math
import base64
from io import BytesIO
import drawsvg as draw
from PIL import Image
from .Curve import Curve
from .utils import calculate_size

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

def interpolate_quadratic_bezier(start, control, end):
    def interpolator(t):
        return [
            (math.pow(1 - t, 2) * start[0]) +
            (2 * (1 - t) * t * control[0]) +
            (math.pow(t, 2) * end[0]),
            (math.pow(1 - t, 2) * start[1]) +
            (2 * (1 - t) * t * control[1]) +
            (math.pow(t, 2) * end[1]),
        ]
    return interpolator

def interpolate_quadratic_bezier_angle(start, control, end):
    def interpolator(t):
        tangent_x = (2 * (1 - t) * (control[0] - start[0])) + \
                    (2 * t * (end[0] - control[0]))
        tangent_y = (2 * (1 - t) * (control[1] - start[1])) + \
                    (2 * t * (end[1] - control[1]))

        return math.atan2(tangent_y, tangent_x) * (180 / math.pi)
    return interpolator

class GenericDataFlow(Curve):
    def add_curve(self, d):
        curve = draw.Path(fill="none", stroke="black").M(self.sourceX, self.sourceY).Q(self.controlX, self.controlY, self.targetX, self.targetY)
        d.append(curve)
        
    def add_additional_arrows(self, d):
        quadratic_interpolator = interpolate_quadratic_bezier([self.sourceX, self.sourceY], [self.controlX, self.controlY], [self.targetX, self.targetY])
        # pts = 10
        # for i in range(pts):
        #     t = i / (pts - 1)
        #     x, y = quadratic_interpolator(t)
        #     # angle = interpolate_quadratic_bezier_angle([self.sourceX, self.sourceY], [self.controlX, self.controlY], [self.targetX, self.targetY])(t)
        #     d.append(draw.Circle(x, y, 3, fill="black"))
            
        quadratic_angle_interpolator = interpolate_quadratic_bezier_angle([self.sourceX, self.sourceY], [self.controlX, self.controlY], [self.targetX, self.targetY])
        pts = 4
        for i in range(pts):
            t = i / (pts - 1)
            x, y = quadratic_interpolator(t)
            angle = quadratic_angle_interpolator(t)
            path = draw.Path(fill="black", transform=f"translate({x}, {y}) rotate({angle})").M(12, 0).L(-5, -8).L(0, 0).L(-5, 8).Z()
            d.append(path)
        
    def add_text(self, d):
        if not self.name:
            return
        newWidth, newHeight = calculate_size(self.name)
        rect = draw.Rectangle(self.handleX - newWidth / 2 - 15, self.handleY + 20, newWidth + 20, max(newHeight, 27) + 2, fill='#E2F4C3', stroke='black', stroke_width=1, fill_opacity=0.5)
        d.append(rect)
        label = draw.Text(self.name, 11, self.handleX - newWidth / 2 + 13, self.handleY + 36)
        d.append(label)
        
    def add_icon(self, d):
        newWidth, newHeight = calculate_size(self.name)
    #     var encodedIcon = icons[this.type];
    # canvas
    #   .image("data:image/jpeg; base64, " + encodedIcon)
    #   .size(25, 25)
    #   .move(
    #     this.handleX - newWidth / 2 - 13,
    #     this.handleY + Math.max(newHeight, 30) / 2 - 3
    #   )
    #   .attr("opacity", 0.2);
        icon = self.icons[self.type]
        if not icon:
            return
        x = self.handleX - newWidth / 2 - 13
        y = self.handleY + max(newHeight, 30) / 2 + 7
        width = 25
        height = 25
        opacity = 0.2
        png_bytes = convert_base64_jpeg_to_png(icon)
        image = draw.Image(x, y, width, height, data=png_bytes, mime_type="image/PNG", opacity=opacity)
        d.append(image)
        
        
    def convert_to_svg(self, d):
        self.add_curve(d)
        self.add_text(d)
        self.add_additional_arrows(d)
        self.add_icon(d)
