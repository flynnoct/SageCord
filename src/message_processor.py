from openai_parser import OpenAI_Parser

class MessageProcessor:
    def __init__(self):
        self.openai_parser = OpenAI_Parser()
    
    def get_response(self, content, context_id):
        response_content = self.openai_parser.get_response(content, context_id)
        return response_content