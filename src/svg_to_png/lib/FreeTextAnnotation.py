import drawsvg as draw
from .Shape import Shape

class FreeTextAnnotation(Shape):
    def convert_to_svg(self, d):
        d.append(draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='black', opacity=0))
        self.add_text(d)
        self.add_icon(d)
        
    def add_icon(self, d):
        height = max(min(90, self.height / 2.5), 40)
        width = max(min(90, height), 40)
        x = self.left + self.width / 2 - width / 2
        y = self.top + self.height / 2 - height / 2
        super().add_icon(d, x, y, width, height)

    # Gets whether the text should be centered (normal for nodes, not for labels)
    def is_text_centered(self):
        return False
    
    # Gets the text line width in pixels.
    def get_text_line_width(self):
        return self.width - self.get_left_indent()
    
    # Gets the indent from the left for the text in pixels
    def get_left_indent(self):
        return 20