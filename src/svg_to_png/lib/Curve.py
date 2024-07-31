class Curve:
    def __init__(self, category, type, name: str, icons: dict, handleX, handleY, sourceX, sourceY, targetX, targetY):
        self.category = category
        self.type = type
        self.name = name
        self.handleX = int(handleX)
        self.handleY = int(handleY)
        self.sourceX = int(sourceX)
        self.sourceY = int(sourceY)
        self.targetX = int(targetX)
        self.targetY = int(targetY)
        self.controlX = 2*self.handleX - self.sourceX/2 - self.targetX/2  # Initialize with default value
        self.controlY = 2*self.handleY - self.sourceY/2 - self.targetY/2  # Initialize with default value
        self.icons = icons