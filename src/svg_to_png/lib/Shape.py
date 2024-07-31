import drawsvg as draw
from .utils import convert_base64_jpeg_to_png

class SVG(draw.DrawingBasicElement):
    TAG_NAME = 'svg'
    def __init__(self, x, y, width, height, **kwargs):
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        
    def append_child(self, animate_element):
        self.children.append(animate_element)
    
class Shape:
    def __init__(self, category, type, name: str, icons: dict, height, width, left, top):
        self.category = category
        self.type = type
        self.name = name
        self.height = int(height) - 10
        self.width = int(width) - 10
        self.left = int(left) + 5
        self.top = int(top) + 5
        self.icons = icons
    
    def add_text(self, d):
        if len(self.name) == 0:
            return
        
        text = draw.Text(self.name, x="50%", y="50%", fill="black", font_family="Open Sans", font_size=11, center=True)
        svg = SVG(self.left, self.top, self.width, self.height)
        svg.append_child(text)
        d.append(svg)
        # ps = ''
        # for name_part in self.name:
        #     p = draw.Raw(
        #         f'<p style="display: table-row; text-align: center; word-break: break-word;">{name_part}</p>')
        #     ps += p.content
        # div3 = draw.Raw(
        #     f'<div style="display: table; width: {self.width - 8}px; margin-top: 4px; margin-right: 4px; margin-bottom: 4px; margin-left: 4px;">{ps}</div>')
        # div2 = draw.Raw(
        #     f'<div style="position: absolute; top: 50%; -ms-transform: translate(0, -50%); transform: translate(0, -50%);">{div3.content}</div>')
        # div1 = draw.Raw(
        #     f'<div style="position: relative; width: {self.width}px; height: {self.height}px;">{div2.content}</div>')
        # body = draw.Raw(
        #     f'<body>{div1.content}</body>')
        # foreign_object = draw.ForeignObject(body.content, x=self.left, y=self.top, width=self.width,
        #                                     height=self.height, font_family='Open Sans', font_size=11)
        # d.append(foreign_object)
        
    def add_icon(self, d, x = None, y = None, width = None, height = None):
        icon = self.icons[self.type]
        if not icon:
            return
        iconHeight = height if height is not None else max(min(90, self.height / 2.5), 40)
        iconWidth = width if width is not None else max(min(90, iconHeight), 40)
        x = x if x is not None else self.left + self.width - iconWidth - 5
        y = y if y is not None else self.top + self.height - iconHeight - 5
        opacity = 0.2
        png_bytes = convert_base64_jpeg_to_png(icon)
        image = draw.Image(x, y, iconWidth, iconHeight, data=png_bytes, mime_type="image/PNG", opacity=opacity)
        d.append(image)