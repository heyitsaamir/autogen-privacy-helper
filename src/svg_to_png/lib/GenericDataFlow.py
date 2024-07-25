import math
import drawsvg as draw
from .Curve import Curve
from .utils import calculate_size

class GenericDataFlow(Curve):
    def add_curve(self, d):
        curve = draw.Path(fill="none", stroke="black").M(self.sourceX, self.sourceY).Q(self.controlX, self.controlY, self.targetX, self.targetY)
        d.append(curve)
        
    def add_arrow(self, d):
        coordinates = [
            (self.targetX - 8.5, self.targetY - 4.1),
            (self.targetX + 0.5, self.targetY - 1.1),
            (self.targetX - 8.5, self.targetY + 1.9)
        ]

        axisX = -self.targetX
        axisY = 0
        slopeX = self.controlX - self.targetX
        slopeY = self.controlY - self.targetY
        dotProduct = axisX * slopeX + axisY * slopeY
        axisLength = abs(axisX)
        slopeLength = math.sqrt(slopeX**2 + slopeY**2)
        angle = (math.acos(dotProduct / axisLength / slopeLength) * 180) / math.pi
        if slopeY > 0:
            angle = -angle
        angle_rad = math.radians(angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        translate_x = self.targetX + 0.5
        translate_y = self.targetY - 1.1

        matrix = (
            cos_angle, sin_angle, -sin_angle, cos_angle,
            translate_x - cos_angle * translate_x + sin_angle * translate_y,
            translate_y - sin_angle * translate_x - cos_angle * translate_y
        )

        points_str = ' '.join([f"{x},{y}" for x, y in coordinates])
        transform_str = f"matrix({matrix[0]},{matrix[1]},{matrix[2]},{matrix[3]},{matrix[4]},{matrix[5]})"
        polyline_str = f'<polyline points="{points_str}" fill="none" stroke="black" transform="{transform_str}" />'
        polyline = draw.Raw(polyline_str)
        d.append(polyline)
        
    def add_text(self, d):
        if not self.name:
            return
        newWidth, newHeight = calculate_size(self.name)
        rect = draw.Rectangle(self.handleX - newWidth / 2 - 15, self.handleY + 20, newWidth + 20, max(newHeight, 27) + 2, fill='#E2F4C3', stroke='black', stroke_width=1, fill_opacity=0.5)
        d.append(rect)
        label = draw.Text(self.name, 11, self.handleX - newWidth / 2 + 13, self.handleY + 36)
        d.append(label)
        
    def convert_to_svg(self, d):
        self.add_curve(d)
        self.add_text(d)
        self.add_text(d)