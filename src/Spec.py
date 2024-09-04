import json
from typing import List, Union, Literal
from pydantic import BaseModel
from svg_to_png.lib.ThreatModel import User_Friendly_Block_Types


class Spec(BaseModel):
    id: int
    spec: str
    instructions_to_solve: str
    improvement_hints: str
    hints_to_send: Union[List[User_Friendly_Block_Types], Literal["all"]] = "all"

    def build_instruction(self):
        return f"""Spec id {self.id} - {self.spec}\n{self.instructions_to_solve}
If the criteria is not met, then {self.improvement_hints}
"""


def load_specs_from_json(file_path: str) -> List[Spec]:
    with open(file_path, "r") as file:
        specs_data = json.load(file)
    return [Spec(**spec) for spec in specs_data]
