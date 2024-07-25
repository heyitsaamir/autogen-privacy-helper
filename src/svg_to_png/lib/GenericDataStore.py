import drawsvg as draw
from .Shape import Shape

class GenericDataStore(Shape):
    def convert_to_svg(self, d):
        rect = draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='black', stroke_width=0.1)
        d.append(rect)
        top_line = draw.Line(self.left, self.top, self.left + self.width, self.top, stroke='black', stroke_width=1)
        d.append(top_line)
        bottom_line = draw.Line(self.left, self.top + self.height, self.left + self.width, self.top + self.height, stroke='black', stroke_width=1)
        d.append(bottom_line)
        self.add_text(d)