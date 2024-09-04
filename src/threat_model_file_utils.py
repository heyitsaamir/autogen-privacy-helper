from teams.input_file import InputFile

from state import AppTurnState


def get_threat_model_xml_file(state: AppTurnState):
    if state.temp.input_files and state.temp.input_files[0]:
        if isinstance(state.temp.input_files[0], InputFile):
            if (
                state.temp.input_files[0].content_type
                == "application/vnd.microsoft.teams.file.download.info"
            ):
                # make sure it's a threat model file
                if state.temp.input_files[0].content and isinstance(
                    state.temp.input_files[0].content, bytes
                ):
                    if state.temp.input_files[0].content.startswith(b"<ThreatModel"):
                        return state.temp.input_files[0]
    return None


def get_threat_model_image_file(state: AppTurnState):
    if state.temp.input_files and state.temp.input_files[0]:
        if isinstance(state.temp.input_files[0], InputFile):
            if (
                state.temp.input_files[0].content_type == "image/jpeg"
                or state.temp.input_files[0].content_type == "image/png"
            ):
                return state.temp.input_files[
                    0
                ]  # this is not guaranteed to be a threat model image file
    return None
