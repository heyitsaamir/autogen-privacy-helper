import drawsvg as draw
from .Shape import Shape

class GenericDataStore(Shape):
    def convert_to_svg(self, d):
        rect = draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='black', stroke_width=0.1)
        d.append(rect)
        line = draw.Line(self.left, self.top + self.height / 2, self.left + self.width, self.top + self.height / 2, stroke='black', stroke_width=0.1)