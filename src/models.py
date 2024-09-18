import json
from typing import Annotated, Dict, List, Literal, Union

from pydantic import BaseModel
from svg_to_png.lib.ThreatModel import User_Friendly_Block_Types

Hints_To_Send = Union[List[User_Friendly_Block_Types], Literal["all"]]

class Spec(BaseModel):
    id: int
    spec: str
    instructions_to_solve: str
    improvement_hints: str
    hints_to_send: Hints_To_Send = "all"

    def build_instruction(self):
        return f"""Spec id {self.id} - {self.spec}\n{self.instructions_to_solve}
If the criteria is not met, then {self.improvement_hints}
"""


class SpecAnswer(BaseModel):
    spec_id: Annotated[int, "The spec id to answer"]
    detailed_answer: Annotated[
        str,
        "Does the threat model meet the spec criteria? Why or why not? Be helpful and specific.",
    ]
    steps_to_improve: Annotated[
        str,
        "What are exact steps to improve the threat model to meet the spec criteria? Use 'None' if no steps to improve",
    ]
    tag: Annotated[
        Union[
            Annotated[Literal["green"], "Spec criteria is met"],
            Annotated[Literal["red"], "Items needs to be fixed to meet criteria"],
            Annotated[Literal["yellow"], "Criteria is met but can be improved"],
        ],
        "The tag of the spec answer",
    ]


class SpecResult(BaseModel):
    spec: Spec
    answer: SpecAnswer



def load_specs_from_json(file_path: str) -> List[Spec]:
    with open(file_path, "r") as file:
        specs_data = json.load(file)
    return [Spec(**spec) for spec in specs_data]

tag_with_headers = {"green": "✅", "red": "❌", "yellow": "⚠️"}

def build_container_for_answer(spec: Spec, spec_answer: SpecAnswer):
    answer_items = [
        {
            "type": "TextBlock",
            "text": spec_answer.detailed_answer,
            "wrap": True,
        }
    ]
    if spec_answer.steps_to_improve != "None" and spec_answer.steps_to_improve:
        answer_items.append(
            {
                "type": "TextBlock",
                "text": "Steps to improve:",
                "wrap": True,
                "weight": "Bolder",
            }
        )
        answer_items.append(
            {
                "type": "TextBlock",
                "text": spec_answer.steps_to_improve,
                "wrap": True,
            }
        )
    return {
        "type": "Container",
        "items": [
            {
                "type": "TextBlock",
                "text": spec.spec,
                "wrap": True,
                "weight": "Bolder",
            },
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": tag_with_headers[spec_answer.tag],
                                "wrap": True,
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": answer_items,
                    },
                ],
            },
        ],
        "separator": True,
    }


def build_adaptive_card(spec_answer_containers: List[Dict]):
    body = [
        {
            "type": "TextBlock",
            "text": "Threat model review",
            "wrap": True,
            "weight": "Bolder",
            "style": "heading",
        },
        *spec_answer_containers,
    ]
    return {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }
