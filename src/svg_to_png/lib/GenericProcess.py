import drawsvg as draw
from .Shape import Shape

class GenericProcess(Shape):
    def convert_to_svg(self, d):
        d.append(draw.Ellipse(self.left + self.width / 2, self.top + self.height / 2, self.width / 2, self.height / 2, fill='white', stroke='black'))
        # d.append(draw.Text(self.name, 11, self.left, self.top, center=True, font='Open Sans'))
        self.add_text(d)
        self.add_icon(d)
        
    def add_icon(self, d):
        height = max(min(90, self.height / 2.5), 40)
        width = max(min(90, height), 40)
        x = self.left + self.width / 2 - width / 2
        y = self.top + self.height / 2 - height / 2
        super().add_icon(d, x, y, width, height)