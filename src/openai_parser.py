
from config_loader import ConfigLoader as CL

class OpenAI_Parser():
    def __init__(self):
        self.api_key = CL.get("openai", "api_key")
