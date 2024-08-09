import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from .FreeTextAnnotation import FreeTextAnnotation
from .GenericDataFlow import GenericDataFlow
from .GenericProcess import GenericProcess
from .GenericTrustBorderBoundary import GenericTrustBorderBoundary
from .GenericTrustLineBoundary import GenericTrustLineBoundary
from .GenericDataStore import GenericDataStore
from .GenericExternalInteractor import GenericExternalInteractor

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

def is_in(candidate, boundary):
    return boundary.left <= candidate.left and boundary.top <= candidate.top and boundary.left + boundary.width >= candidate.left + candidate.width and boundary.top + boundary.height >= candidate.top + candidate.height

def set_appropriate_groups(candidate, boundary):
    if is_in(candidate, boundary):
        if candidate.group is None:
            candidate.group = boundary
        else:
            current = candidate.group
            while current is not None:
                if boundary == current:
                    # outer boundary already set
                    break
                elif is_in(current, boundary) and (current.group is None or not is_in(current.group, boundary)):
                    temp = current.group
                    current.group = boundary
                    set_appropriate_groups(boundary, temp)
                    break
                current = current.group

def set_groups(nodes, boundaries):
    for node in nodes:
        for boundary in boundaries:
            set_appropriate_groups(node, boundary)

class ThreatModel:

    def add_element(self, el: Element, icons: dict):
        generic_type_id = el.find(build_tag(ABSTRACTS_XMLNS, "GenericTypeId")).text
        properties = el.find(build_tag(ABSTRACTS_XMLNS, "Properties"))
        any_type_properties = properties.findall(build_tag(ARRAY_XMLNS, "anyType"))
        type = any_type_properties[0][0].text
        name = el.get('custom_key') if el.get('custom_key') else get_element_name(el)
        if generic_type_id == "GE.DS":

            shape = GenericDataStore(generic_type_id, type, name, icons, *get_shape_details(el))
            self.nodes.append(shape)
        elif generic_type_id == "GE.EI":
            shape = GenericExternalInteractor(generic_type_id, type, name, icons, *get_shape_details(el))
            self.nodes.append(shape)
        elif generic_type_id == "GE.P":
            shape = GenericProcess(generic_type_id, type, name, icons, *get_shape_details(el))
            self.nodes.append(shape)
        elif generic_type_id == "GE.TB.B":
            shape = GenericTrustBorderBoundary(generic_type_id, type, name, icons, *get_shape_details(el))
            self.boundaries.append(shape)
        elif generic_type_id == "GE.A":
            shape = FreeTextAnnotation(generic_type_id, type, name, icons, *get_shape_details(el))
            self.labels.append(shape)
        elif generic_type_id == "GE.DF":
            shape = GenericDataFlow(generic_type_id, type, name, icons, *get_curve_details(el))
            self.curves.append(shape)
        elif generic_type_id == "GE.TB.L":
            shape = GenericTrustLineBoundary(generic_type_id, type, name, icons, *get_curve_details(el))
            self.trust_line_boundaries.append(shape)
        else:
            # TODO log error in the future
            shape = None


    def __init__(self, file: str = None, svg_content: str = None):
        if not file and not svg_content:
            raise Exception("Either file or svg_content should be provided")
        
        self.boundaries = []
        self.nodes = []
        self.labels = []
        self.curves = []
        self.trust_line_boundaries = []
        
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
        
        #TODO support multiple tabs
        tab = tabs[0]
        tab_header = tab.findall(build_tag(THREAT_MODELING_XMLNS, "Header"))
        tab_borders = tab.find(build_tag(THREAT_MODELING_XMLNS, "Borders"))
        tab_lines = tab.find(build_tag(THREAT_MODELING_XMLNS, "Lines"))

        borders = tab_borders.findall(build_tag(ARRAY_XMLNS, "KeyValueOfguidanyType"))
        key_label_tuples = []
        key_index = 0
            
        for border in borders:
            value = border.find(build_tag(ARRAY_XMLNS, "Value"))
            generic_type_id = value.find(build_tag(ABSTRACTS_XMLNS, "GenericTypeId")).text
            if generic_type_id == "GE.TB.B":
                user_friendly_key = "Boundary"
                key = f'Boundary {key_index + 1}'
                self.add_element(value, icons)
            else:
                if generic_type_id == "GE.A":
                    user_friendly_key = "Annotation"
                else:
                    user_friendly_key = "Node"
                self.add_element(value, icon)
            key = f'{user_friendly_key} {key_index + 1}'
            name = get_element_name(value)
            key_label_tuples.append((key, name))
            key_index += 1
            
        lines = tab_lines.findall(build_tag(ARRAY_XMLNS, "KeyValueOfguidanyType"))
        for line in lines:
            value = line.find(build_tag(ARRAY_XMLNS, "Value"))
            self.add_element(value, icons)
                
        self.key_label_tuples = key_label_tuples
        set_groups(self.nodes, self.boundaries)

    def convert_to_svg(self, d):
        for boundary in self.boundaries:
            boundary.convert_to_svg(d)
        for node in self.nodes:
            node.convert_to_svg(d)
        for label in self.labels:
            label.convert_to_svg(d)
        for curve in self.curves:
            curve.convert_to_svg(d)
        for trust_line_boundary in self.trust_line_boundaries:
            trust_line_boundary.convert_to_svg(d)

    def get_label_names(self):
        return [label.name for label in self.labels]
    
    def get_no_threat_boundary_node_names(self):
        return [node.name for node in self.nodes if node.group is None]