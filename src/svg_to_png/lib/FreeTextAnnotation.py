import drawsvg as draw
from .Shape import Shape

class FreeTextAnnotation(Shape):
    def convert_to_svg(self, d):
        d.append(draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='black', opacity=0))
        self.add_text(d)