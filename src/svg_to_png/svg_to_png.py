import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
import drawsvg as draw
from .lib.FreeTextAnnotation import FreeTextAnnotation
from .lib.GenericDataFlow import GenericDataFlow
from .lib.GenericProcess import GenericProcess
from .lib.GenericTrustBorderBoundary import GenericTrustBorderBoundary
from .lib.GenericTrustLineBoundary import GenericTrustLineBoundary
from .lib.utils import get_bbox


def build_tag(schema, tag):
    return f'{schema}{tag}'


def print_all(iter):
    for elem in iter:
        print(elem.tag, elem.attrib)
        
THREAT_MODELING_XMLNS = "{http://schemas.datacontract.org/2004/07/ThreatModeling.Model}"
ABSTRACTS_XMLNS = "{http://schemas.datacontract.org/2004/07/ThreatModeling.Model.Abstracts}"
ARRAY_XMLNS = "{http://schemas.microsoft.com/2003/10/Serialization/Arrays}"
KNOWLEDGE_BASE_XMLNS = "{http://schemas.datacontract.org/2004/07/ThreatModeling.KnowledgeBase}"
        
def get_shape_details(shape):
    height = shape.find(build_tag(ABSTRACTS_XMLNS, "Height")).text
    width = shape.find(build_tag(ABSTRACTS_XMLNS, "Width")).text
    left = shape.find(build_tag(ABSTRACTS_XMLNS, "Left")).text
    top = shape.find(build_tag(ABSTRACTS_XMLNS, "Top")).text
    
    return height, width, left, top

def get_curve_details(curve):
    handleX = curve.find(build_tag(ABSTRACTS_XMLNS, "HandleX")).text
    handleY = curve.find(build_tag(ABSTRACTS_XMLNS, "HandleY")).text
    sourceX = curve.find(build_tag(ABSTRACTS_XMLNS, "SourceX")).text
    sourceY = curve.find(build_tag(ABSTRACTS_XMLNS, "SourceY")).text
    targetX = curve.find(build_tag(ABSTRACTS_XMLNS, "TargetX")).text
    targetY = curve.find(build_tag(ABSTRACTS_XMLNS, "TargetY")).text
    
    return handleX, handleY, sourceX, sourceY, targetX, targetY

def get_element_name(shape):
    properties = shape.find(build_tag(ABSTRACTS_XMLNS, "Properties"))
    any_type_properties = properties.findall(build_tag(ARRAY_XMLNS, "anyType"))
    name = any_type_properties[1][2].text
    return name if name else ""
        
def draw_element(el: Element, d):
    generic_type_id = el.find(build_tag(ABSTRACTS_XMLNS, "GenericTypeId")).text
    properties = el.find(build_tag(ABSTRACTS_XMLNS, "Properties"))
    any_type_properties = properties.findall(build_tag(ARRAY_XMLNS, "anyType"))
    type = any_type_properties[0][0].text
    name = el.get('custom_key') if el.get('custom_key') else get_element_name(el)
    if generic_type_id == "GE.P":
        height, width, left, top = get_shape_details(el)
        shape = GenericProcess(generic_type_id, type, name, height, width, left, top)
    elif generic_type_id == "GE.A":
        height, width, left, top = get_shape_details(el)
        shape = FreeTextAnnotation(generic_type_id, type, name, height, width, left, top)
    elif generic_type_id == "GE.DF":
        handleX, handleY, sourceX, sourceY, targetX, targetY = get_curve_details(el)
        shape = GenericDataFlow(generic_type_id, type, name, handleX, handleY, sourceX, sourceY, targetX, targetY)
    elif generic_type_id == "GE.TB.B":
        height, width, left, top = get_shape_details(el)
        shape = GenericTrustBorderBoundary(generic_type_id, type, name, height, width, left, top)
    elif generic_type_id == "GE.TB.L":
        handleX, handleY, sourceX, sourceY, targetX, targetY = get_curve_details(el)
        shape = GenericTrustLineBoundary(generic_type_id, type, name, handleX, handleY, sourceX, sourceY, targetX, targetY)
    else:
        shape = None
        
    if shape:
        shape.convert_to_svg(d)

def convert_svg_to_png(file: str = None, svg_content: str = None, out_file="result"):
    if not file and not svg_content:
        raise Exception("Either file or svg_content should be provided")
    
    ET.register_namespace(
        'xmlns', 'http://schemas.datacontract.org/2004/07/ThreatModeling.Model')
    if file:
        tree = ET.parse(file)
        root = tree.getroot()
    else:
        root = ET.fromstring(svg_content)
        
    knowledgeBase = root.find(build_tag(
        THREAT_MODELING_XMLNS, 'KnowledgeBase'))
    drawingSurfaceList = root.find(build_tag(
        THREAT_MODELING_XMLNS, 'DrawingSurfaceList'))
    icons = dict()
    generic_icons = knowledgeBase.find(build_tag(
        KNOWLEDGE_BASE_XMLNS, 'GenericElements')).findall(build_tag(
        KNOWLEDGE_BASE_XMLNS, 'ElementType'))
    for icon in generic_icons:
        name = icon.find(build_tag(
            KNOWLEDGE_BASE_XMLNS, 'Name')).text
        image_source = icon.find(build_tag(
            KNOWLEDGE_BASE_XMLNS, 'ImageSource')).text
        icons[name] = image_source
    standard_icons = knowledgeBase.find(build_tag(
        KNOWLEDGE_BASE_XMLNS, 'StandardElements')).findall(build_tag(
        KNOWLEDGE_BASE_XMLNS, 'ElementType'))
    for icon in standard_icons:
        name = icon.find(build_tag(
            KNOWLEDGE_BASE_XMLNS, 'Name')).text
        image_source = icon.find(build_tag(
            KNOWLEDGE_BASE_XMLNS, 'ImageSource')).text
        icons[name] = image_source
    
    tabs = drawingSurfaceList.findall(build_tag(THREAT_MODELING_XMLNS, "DrawingSurfaceModel"))
    
    for tab in tabs:
        tab_header = tab.findall(build_tag(THREAT_MODELING_XMLNS, "Header"))
        tab_borders = tab.find(build_tag(THREAT_MODELING_XMLNS, "Borders"))
        tab_lines = tab.find(build_tag(THREAT_MODELING_XMLNS, "Lines"))

        d = draw.Drawing(2000, 2000)
        d.append(draw.elements.Raw('<style>@import url("https://fonts.googleapis.com/css?family=Open+Sans:400,400i,700,700i");</style>'))
        boundaries = []
        shapes = []
        borders = tab_borders.findall(build_tag(ARRAY_XMLNS, "KeyValueOfguidanyType"))
        key_label_tuples = []
        key_index = 0
        
        for border in borders:
            value = border.find(build_tag(ARRAY_XMLNS, "Value"))
            generic_type_id = value.find(build_tag(ABSTRACTS_XMLNS, "GenericTypeId")).text
            if generic_type_id == "GE.TB.B":
                user_friendly_key = "Boundary"
                key = f'Boundary {key_index + 1}'
                boundaries.append(value)
            else:
                if generic_type_id == "GE.A":
                    user_friendly_key = "Annotation"
                else:
                    user_friendly_key = "Node"
                shapes.append(value)
            key = f'{user_friendly_key} {key_index + 1}'
            name = get_element_name(value)
            key_label_tuples.append((key, name))
            value.set('custom_key', key)
            key_index += 1
        
        for shape in shapes:
            draw_element(shape, d)
        
        lines = tab_lines.findall(build_tag(ARRAY_XMLNS, "KeyValueOfguidanyType"))
        for line in lines:
            value = line.find(build_tag(ARRAY_XMLNS, "Value"))
            draw_element(value, d)
            
        for boundary in boundaries:
            draw_element(boundary, d)
        
        bounding_box = get_bbox(d.as_svg())
        bounding_box.add_padding(10)
        width, height = bounding_box.get_size()
        d.set_render_size(width, height)
        d.view_box = (0,0) + (width, height)
        file_name = out_file
        d.save_svg(f'{file_name}.svg')
        d.save_png(f'{file_name}.png')
        
        return key_label_tuples