from conversation_state import ConversationState

def get_threat_model_xml_file(state: ConversationState):
    if state.has_input_files() and state.get_file_content() and state.get_file_content().startswith(b"<ThreatModel"):
        return state.get_file_content()
    return None

def get_threat_model_image_file(state: ConversationState):
    if state.has_input_files() and (state.get_file_content_type() == "image/jpeg" or state.get_file_content_type() == "image/png"):
        return state.get_file_content() # this is not guaranteed to be a threat model image file
    return None
