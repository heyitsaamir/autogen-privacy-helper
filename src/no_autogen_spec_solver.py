import asyncio
import logging
import os
from typing import Dict, List, Optional

import instructor
from conversation_state import ChatContext, ConversationState
from models import (
    Spec,
    SpecAnswer,
    SpecResult,
    build_adaptive_card,
    build_container_for_answer,
    load_specs_from_json,
)
from openai import AsyncAzureOpenAI as AzureOpenAI
from openai import AsyncOpenAI as OpenAI
from svg_to_png.lib.ThreatModel import ThreatModel
from svg_to_png.svg_to_png import load_threat_model
from threat_model_file_utils import get_threat_model_xml_file

_SYSTEM_MESSAGE = """
You are an answering agent.
You will *NEVER* speculate or infer anything that is not in the details of the threat model provided to you.
The threat model indicates the flow of data in a bigger system. You do not have any context about the system, but you can answer questions regarding the data flow present in the threat model.
Answer the questions as clearly and concisely as possible
"""


class ThreatModelValidator:
    def __init__(self, llm_config: Dict):
        assert "model" in llm_config, "Model is required in the config"
        self._model = llm_config.get("model")
        if llm_config.get("api_type") is None:
            assert "api_key" in llm_config, "Open AI API key is required"
            logging.debug("Using OpenAI API key")
            self.client = instructor.from_openai(OpenAI(api_key=llm_config.get("api_key")))
        elif llm_config.get("api_type") == "azure":
            logging.debug("Using Azure API key")
            self.client = instructor.from_openai(AzureOpenAI(
                azure_endpoint=llm_config.get("base_url", ""),
                api_version=llm_config.get("api_version", ""),
                azure_ad_token_provider=llm_config.get("azure_ad_token_provider"),
            ))
        logging.basicConfig(level=logging.INFO)

    async def _get_threat_model_details(self, state: ConversationState) -> Optional[ThreatModel]:
        threat_model_file_bytes = get_threat_model_xml_file(state)
        if not threat_model_file_bytes:
            return None
        svg_str = threat_model_file_bytes.decode("utf-8")
        return load_threat_model(svg_content=svg_str)

    async def _get_specs(self) -> List[Spec]:
        folder = os.path.dirname(os.path.abspath(__file__))
        specs = load_specs_from_json(f"{folder}/specs.json")
        return specs

    async def _resolve_single_spec(self, threat_model: ThreatModel, spec: Spec) -> SpecAnswer:
        logging.debug("Resolving spec %s", spec.id)
        threat_model_details = f"""The file details for the file you need to validate are:
--------
1. The data for the nodes is: {threat_model.get_node_data()}.
--------
2. The list of label names is {threat_model.get_label_names()}.
--------
3. The list of nodes with labels between them is {threat_model.get_node_label_pair_data()}.
--------
4. The list of boundary names is {threat_model.get_boundary_names()}."""

        spec_question = f"""Now, based on the given details of the spec model, see if it fulfills this criteria
Spec id {spec.id}
{spec.instructions_to_solve}
"""

        result = await self.client.chat.completions.create(
            model=self._model,
            response_model=SpecAnswer,
            messages=[
                {
                    "role": "system",
                    "content": _SYSTEM_MESSAGE,
                },
                {
                    "role": "user",
                    "content": threat_model_details,
                },
                {"role": "user", "content": spec_question},
            ],
        )

        logging.debug("Resolved spec answer %s", result)

        return result

    async def _resolve_threat_model(self, threat_model: ThreatModel, specs: List[Spec]) -> List[SpecResult]:
        futures = []
        for spec in specs:
            futures.append(self._resolve_single_spec(threat_model, spec))
        spec_answers = await asyncio.gather(*futures)
        spec_results: List[SpecResult] = []
        for spec_answer in spec_answers:
            spec_id = spec_answer.spec_id
            spec_question = next(filter(lambda x: x.id == spec_id, specs))
            if not spec_question:
                logging.warning("Spec with id %s not found", spec_id)
                continue
            spec_results.append(SpecResult(spec=spec_question, answer=spec_answer))
        spec_results = sorted(spec_results, key=lambda x: x.spec.id)

        return spec_results

    async def handle_request(self, request: ChatContext, state: ConversationState) -> Optional[Dict]:
        threat_model_details = await self._get_threat_model_details(state)
        if not threat_model_details:
            # TODO: Handle
            return None

        specs = await self._get_specs()

        results = await self._resolve_threat_model(threat_model_details, specs)

        logging.debug("Results %s", results)
        containers = [
            build_container_for_answer(result.spec, result.answer)
            for result in results
        ]
        card = build_adaptive_card(containers)
        return card
