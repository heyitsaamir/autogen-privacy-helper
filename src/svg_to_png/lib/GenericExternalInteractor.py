import drawsvg as draw
from .Shape import Shape

class GenericExternalInteractor(Shape):
    def convert_to_svg(self, d):
        rect = draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='black', stroke_width=0.1)
        d.append(rect)
        self.add_text(d)