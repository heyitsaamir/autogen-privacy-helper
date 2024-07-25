import drawsvg as draw
from .Shape import Shape

class GenericProcess(Shape):
    def convert_to_svg(self, d):
        d.append(draw.Ellipse(self.left + self.width / 2, self.top + self.height / 2, self.width / 2, self.height / 2, fill='white', stroke='black'))
        # d.append(draw.Text(self.name, 11, self.left, self.top, center=True, font='Open Sans'))
        self.add_text(d)