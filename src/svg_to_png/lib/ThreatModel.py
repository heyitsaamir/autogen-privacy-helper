from typing import Optional, Literal, Dict, List
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
import re

from .FreeTextAnnotation import FreeTextAnnotation
from .GenericDataFlow import GenericDataFlow
from .GenericProcess import GenericProcess
from .GenericTrustBorderBoundary import GenericTrustBorderBoundary
from .GenericTrustLineBoundary import GenericTrustLineBoundary
from .GenericDataStore import GenericDataStore
from .GenericExternalInteractor import GenericExternalInteractor
from .bezier_utils import is_on_inner_side_of_bezier

def build_tag(schema, tag):
    return f"{schema}{tag}"


def print_all(iter):
    for elem in iter:
        print(elem.tag, elem.attrib)


THREAT_MODELING_XMLNS = "{http://schemas.datacontract.org/2004/07/ThreatModeling.Model}"
ABSTRACTS_XMLNS = (
    "{http://schemas.datacontract.org/2004/07/ThreatModeling.Model.Abstracts}"
)
ARRAY_XMLNS = "{http://schemas.microsoft.com/2003/10/Serialization/Arrays}"
KNOWLEDGE_BASE_XMLNS = (
    "{http://schemas.datacontract.org/2004/07/ThreatModeling.KnowledgeBase}"
)

type User_Friendly_Block_Types = Literal[
    "Boundary",
    "Annotation",
    "External Interactor",
    "Node",
    "Data Store",
    "Data Flow",
    "Trust Boundary",
]
type Key_Label_Map = Dict[
    User_Friendly_Block_Types, List[Dict[Literal["index", "key", "name"], str]]
]
element_to_user_friendly_key: Dict[str, User_Friendly_Block_Types] = {
    "GE.TB.B": "Boundary",
    "GE.A": "Annotation",
    "GE.EI": "External Interactor",
    "GE.P": "Node",
    "GE.DS": "Data Store",
    "GE.DF": "Data Flow",
    "GE.TB.L": "Trust Boundary",
}


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

def is_point_in(x, y, shape):
    return (
        shape.left <= x
        and shape.top <= y
        and shape.left + shape.width >= x
        and shape.top + shape.height >= y
    )


def is_in(candidate, boundary):
    return (
        boundary.left <= candidate.left
        and boundary.top <= candidate.top
        and boundary.left + boundary.width >= candidate.left + candidate.width
        and boundary.top + boundary.height >= candidate.top + candidate.height
    )


# TODO add trust line boundaries
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
                elif is_in(current, boundary) and (
                    current.group is None or not is_in(current.group, boundary)
                ):
                    temp = current.group
                    current.group = boundary
                    if temp is not None:
                        set_appropriate_groups(boundary, temp)
                    break
                current = current.group


def set_groups(nodes, boundaries):
    for node in nodes:
        for boundary in boundaries:
            set_appropriate_groups(node, boundary)


def set_curve_nodes(nodes, curves):
    for curve in curves:
        for node in nodes:
            if is_point_in(curve.sourceX, curve.sourceY, node):
                curve.sourceNode = node
            if is_point_in(curve.targetX, curve.targetY, node):
                curve.targetNode = node
            if curve.sourceNode is not None and curve.targetNode is not None:
                break

def is_node_in_trust_line_boundary(node, trust_line_boundary):
    corners = [
        (node.left, node.top),
        (node.left + node.width, node.top),
        (node.left, node.top + node.height),
        (node.left + node.width, node.top + node.height),
    ]
    for x, y in corners:
        if not is_on_inner_side_of_bezier(
            x, y,
            trust_line_boundary.sourceX, trust_line_boundary.sourceY,
            trust_line_boundary.handleX, trust_line_boundary.handleY,
            trust_line_boundary.targetX, trust_line_boundary.targetY
        ):
            return False
    return True

def set_trust_line_boundaries(nodes, trust_line_boundaries):
    for trust_line_boundary in trust_line_boundaries:
        for node in nodes:
            if is_node_in_trust_line_boundary(node, trust_line_boundary):
                node.line_boundaries.append(trust_line_boundary)
            

class ThreatModel:
    key_label_map: Key_Label_Map

    def add_element(self, el: Element, icons: dict):
        generic_type_id = el.find(build_tag(ABSTRACTS_XMLNS, "GenericTypeId")).text
        properties = el.find(build_tag(ABSTRACTS_XMLNS, "Properties"))
        any_type_properties = properties.findall(build_tag(ARRAY_XMLNS, "anyType"))
        type = any_type_properties[0][0].text
        name = el.get("custom_key") if el.get("custom_key") else get_element_name(el)
        if generic_type_id == "GE.DS":
            shape = GenericDataStore(
                generic_type_id, type, name, icons, *get_shape_details(el)
            )
            self.nodes.append(shape)
        elif generic_type_id == "GE.EI":
            shape = GenericExternalInteractor(
                generic_type_id, type, name, icons, *get_shape_details(el)
            )
            self.nodes.append(shape)
        elif generic_type_id == "GE.P":
            shape = GenericProcess(
                generic_type_id, type, name, icons, *get_shape_details(el)
            )
            self.nodes.append(shape)
        elif generic_type_id == "GE.TB.B":
            shape = GenericTrustBorderBoundary(
                generic_type_id, type, name, icons, *get_shape_details(el)
            )
            self.boundaries.append(shape)
        elif generic_type_id == "GE.A":
            shape = FreeTextAnnotation(
                generic_type_id, type, name, icons, *get_shape_details(el)
            )
            self.annotations.append(shape)
        elif generic_type_id == "GE.DF":
            shape = GenericDataFlow(
                generic_type_id, type, name, icons, *get_curve_details(el)
            )
            self.curves.append(shape)
            self.labels.append(name)
        elif generic_type_id == "GE.TB.L":
            shape = GenericTrustLineBoundary(
                generic_type_id, type, name, icons, *get_curve_details(el)
            )
            self.trust_line_boundaries.append(shape)
        else:
            # TODO log error in the future
            shape = None

    def __init__(
        self,
        file: Optional[str] = None,
        svg_content: Optional[str] = None,
        build_for_ai_context: bool = False,
    ):
        ET.register_namespace(
            "xmlns", "http://schemas.datacontract.org/2004/07/ThreatModeling.Model"
        )
        if file:
            tree = ET.parse(file)
            root = tree.getroot()
        elif svg_content:
            root = ET.fromstring(svg_content)
        else:
            raise Exception("Either file or svg_content should be provided")

        self.boundaries = []
        self.nodes = []
        self.labels = []
        self.curves = []
        self.annotations = []
        self.trust_line_boundaries = []

        knowledgeBase = root.find(build_tag(THREAT_MODELING_XMLNS, "KnowledgeBase"))
        drawingSurfaceList = root.find(
            build_tag(THREAT_MODELING_XMLNS, "DrawingSurfaceList")
        )
        icons = dict()
        generic_icons = knowledgeBase.find(
            build_tag(KNOWLEDGE_BASE_XMLNS, "GenericElements")
        ).findall(build_tag(KNOWLEDGE_BASE_XMLNS, "ElementType"))
        for icon in generic_icons:
            name = icon.find(build_tag(KNOWLEDGE_BASE_XMLNS, "Name")).text
            image_source = icon.find(
                build_tag(KNOWLEDGE_BASE_XMLNS, "ImageSource")
            ).text
            icons[name] = image_source
        standard_icons = knowledgeBase.find(
            build_tag(KNOWLEDGE_BASE_XMLNS, "StandardElements")
        ).findall(build_tag(KNOWLEDGE_BASE_XMLNS, "ElementType"))
        for icon in standard_icons:
            name = icon.find(build_tag(KNOWLEDGE_BASE_XMLNS, "Name")).text
            image_source = icon.find(
                build_tag(KNOWLEDGE_BASE_XMLNS, "ImageSource")
            ).text
            icons[name] = image_source

        tabs = drawingSurfaceList.findall(
            build_tag(THREAT_MODELING_XMLNS, "DrawingSurfaceModel")
        )

        # TODO support multiple tabs
        tab = tabs[0]
        _tab_header = tab.findall(build_tag(THREAT_MODELING_XMLNS, "Header"))
        tab_borders = tab.find(build_tag(THREAT_MODELING_XMLNS, "Borders"))
        tab_lines = tab.find(build_tag(THREAT_MODELING_XMLNS, "Lines"))

        borders = tab_borders.findall(build_tag(ARRAY_XMLNS, "KeyValueOfguidanyType"))
        key_label_map: Key_Label_Map = {}
        element_to_key_index = {
            "GE.TB.B": 0,
            "GE.A": 0,
            "GE.EI": 0,
            "GE.P": 0,
            "GE.DS": 0,
            "GE.DF": 0,
            "GE.TB.L": 0,
        }

        for border in borders:
            value = border.find(build_tag(ARRAY_XMLNS, "Value"))
            if not value:
                continue
            generic_type_id = value.find(
                build_tag(ABSTRACTS_XMLNS, "GenericTypeId")
            ).text
            self.generate_custom_key(
                build_for_ai_context,
                key_label_map,
                element_to_key_index,
                value,
                generic_type_id,
            )
            self.add_element(value, icons)

        if tab_lines is not None:
            lines = tab_lines.findall(build_tag(ARRAY_XMLNS, "KeyValueOfguidanyType"))
            for line in lines:
                value = line.find(build_tag(ARRAY_XMLNS, "Value"))
                if not value:
                    continue
                generic_type_id = value.find(
                    build_tag(ABSTRACTS_XMLNS, "GenericTypeId")
                ).text
                self.generate_custom_key(
                    build_for_ai_context,
                    key_label_map,
                    element_to_key_index,
                    value,
                    generic_type_id,
                )
                self.add_element(value, icons)

        # sort all the key_label_map
        for key in key_label_map:
            key_label_map[key] = sorted(key_label_map[key], key=lambda x: x["index"])

        self.key_label_map = key_label_map
        set_groups(self.nodes, self.boundaries)
        set_curve_nodes(self.nodes, self.curves)
        set_trust_line_boundaries(self.nodes, self.trust_line_boundaries)

    def generate_custom_key(
        self,
        build_for_ai_context,
        key_label_map,
        element_to_key_index,
        value,
        generic_type_id,
    ):
        if build_for_ai_context:
            if isinstance(generic_type_id, str):
                user_friendly_key = element_to_user_friendly_key.get(
                    generic_type_id, "Element"
                )
                key_index = element_to_key_index[generic_type_id]
                element_to_key_index[generic_type_id] += 1
            else:
                raise ValueError(f"Unknown generic_type_id: {generic_type_id}")
            key = f"{user_friendly_key} {key_index + 1}"
            name = get_element_name(value)
            key_label_map[user_friendly_key] = (
                []
                if not key_label_map.get(user_friendly_key)
                else key_label_map[user_friendly_key]
            )
            key_label_map[user_friendly_key].append(
                {
                    "index": key_index + 1,
                    "key": key,
                    "name": name,
                }
            )
            value.set("custom_key", key)

    def convert_to_svg(self, d):
        for boundary in self.boundaries:
            boundary.convert_to_svg(d)
        for node in self.nodes:
            node.convert_to_svg(d)
        for curve in self.curves:
            curve.convert_to_svg(d)
        for trust_line_boundary in self.trust_line_boundaries:
            trust_line_boundary.convert_to_svg(d)
        for annotation in self.annotations:
            annotation.convert_to_svg(d)

    def get_label_names(self):
        label_names = [curve.name for curve in self.curves]

        def sort_key(s):
            match = re.match(r"^(\d+)", s)
            if match:
                num_part = int(match.group(1))
            else:
                num_part = -1
            return (num_part, s)

        # if they are numbered, label names sorted can be easier for the model to handle sequences
        return sorted(label_names, key=sort_key)

    def get_node_data(self):
        return [
            {"name": node.name, "has_boundary": node.group is not None or len(node.line_boundaries) > 0}
            for node in self.nodes
        ]

    def get_boundary_names(self):
        return [
            boundary.name for boundary in self.boundaries + self.trust_line_boundaries
        ]

    def get_node_label_pair_data(self):
        result = {}

        for curve in self.curves:
            if curve.sourceNode is None or curve.targetNode is None:
                continue

            node1_name = curve.sourceNode.name
            node2_name = curve.targetNode.name

            # Create a sorted tuple key to ensure unique pairs regardless of order
            pair_key = tuple(sorted([node1_name, node2_name]))

            # Initialize the dictionary entry if not already present
            if pair_key not in result:
                result[pair_key] = {
                    "node1": pair_key[0],
                    "node2": pair_key[1],
                    "hasNode1ToNode2Curve": False,
                    "hasNode2ToNode1Curve": False,
                }

            # Update the boolean values based on the direction of the curve
            if node1_name == pair_key[0]:
                result[pair_key]["hasNode1ToNode2Curve"] = True
            else:
                result[pair_key]["hasNode2ToNode1Curve"] = True

        # Convert the dictionary values to a list
        return list(result.values())
