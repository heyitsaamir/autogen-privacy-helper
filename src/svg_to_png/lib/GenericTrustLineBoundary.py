from .Curve import Curve
from .utils import calculate_size
import drawsvg as draw

class GenericTrustLineBoundary(Curve):
    def convert_to_svg(self, d):
        curve = draw.Path(fill="none", stroke="red", stroke_dasharray=4).M(self.sourceX, self.sourceY).Q(self.controlX, self.controlY, self.targetX, self.targetY)
        d.append(curve)
        
        if (self.name):
            newWidth, newHeight = calculate_size(self.name)
            label = draw.Text(self.name, 11, self.handleX - newWidth / 2 + 13, self.handleY + max(newHeight, 30) / 2 - newHeight / 2 + 20, fill="red")
            d.append(label)