from .Shape import Shape, SVG
from .utils import calculate_size
import drawsvg as draw

class GenericTrustBorderBoundary(Shape):
    def convert_to_svg(self, d):
        d.append(draw.Rectangle(self.left, self.top, self.width, self.height, fill='white', stroke='red', stroke_opacity=1, stroke_dasharray=4, fill_opacity=0))
        self.add_text(d)
        
    def add_text(self, d):
        if len(self.name) == 0:
            return
        # newWidth, _newHeight = calculate_size(self.name)
        text = draw.Text(self.name, x=self.width - 5, y=5, fill="red", font_family="Open Sans", font_size=11, text_anchor='end', dominant_baseline="hanging")
        svg = SVG(self.left, self.top, self.width, self.height)
        svg.append_child(text)
        d.append(svg)
        
    def add_text_old(self, d):
        if len(self.name) == 0:
            return
        ps = ''
        for name_part in self.name:
            p = draw.Raw(
                f'<p style="color: red; display: table-row; text-align: center;">{name_part}</p>')
            ps += p.content
        newWidth, _newHeight = calculate_size(self.name)
        div = draw.Raw(
            f'<div style="display: table; width: {newWidth}px;">{ps}</div>')
        body = draw.Raw(
            f'<body>{div.content}</body>')
        foreign_object = draw.ForeignObject(body.content, x=self.left + self.width - newWidth, y=self.top, width=self.width,
                                            height=self.height, font_family='Open Sans', font_size=11)
        d.append(foreign_object)