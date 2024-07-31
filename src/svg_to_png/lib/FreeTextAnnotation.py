import drawsvg as draw
from .Shape import Shape

class FreeTextAnnotation(Shape):
    def convert_to_svg(self, d):
        d.append(draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='black', opacity=0))
        self.add_text(d)
        
    def add_icon(self, d):
        height = max(min(90, self.height / 2.5), 40)
        width = max(min(90, height), 40)
        x = self.left + self.width / 2 - width / 2
        y = self.top + self.height / 2 - height / 2
        super().add_icon(d, x, y, width, height)