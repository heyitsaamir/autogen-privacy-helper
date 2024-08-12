import drawsvg as draw
from .lib.ThreatModel import ThreatModel
from .lib.utils import get_bbox

def load_threat_model(file: str = None, svg_content: str = None):
    return ThreatModel(file, svg_content)

def convert_svg_to_png(file: str = None, svg_content: str = None, out_file="result"):
    threat_model = ThreatModel(file, svg_content)
    
    d = draw.Drawing(2000, 2000)
    d.append(draw.elements.Raw('<style>@import url("https://fonts.googleapis.com/css?family=Open+Sans:400,400i,700,700i");</style>'))

    threat_model.convert_to_svg(d)

    bounding_box = get_bbox(d.as_svg())
    bounding_box.add_padding(10)
    width, height = bounding_box.get_size()
    d.set_render_size(width, height)
    d.view_box = (bounding_box.xmin,bounding_box.ymin) + (width, height)
    file_name = out_file
    d.save_svg(f'{file_name}.svg')
    d.save_png(f'{file_name}.png')
        
    return threat_model.key_label_tuples
