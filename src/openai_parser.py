import os, json, time
from datetime import datetime
from config_loader import ConfigLoader as CL
from openai import OpenAI

class OpenAI_Parser():
    def __init__(self):
        self.client = OpenAI(api_key = CL.get("openai", "api_key"))
        self.assistant = self.client.beta.assistants.retrieve(CL.get("openai", "assistant_id"))
        # check if thread_mapping exists, else create it
        if os.path.exists("./thread_mapping.json"):
            with open("./thread_mapping.json", "r") as f:
                self.thread_mapping_table = json.load(f)
        else:
            self.thread_mapping_table = {}

    
    def get_response(self, content, context_id):
        context_id = str(context_id) # convert to string
        thread = self._get_thread(context_id)
        user_message = self._create_message(content, thread) # create message containing user's message
        run = self._run_thread(thread) # run thread
        run_result = self._wait_for_run_finish(run)
        new_messages = self._get_new_messages(thread)
        return new_messages

    def _get_new_messages(self, thread):
        messages = self.client.beta.threads.messages.list(
            thread_id = thread.id,
        ).data
        for i in range(len(messages)):
            message = messages[i]
            if message.role == "user":
                messages = messages[:i]
                break
        parsed_messages = []
        for message in messages:
            parsed_messages.append(self._parse_message(message))
        return parsed_messages[::-1]
    
    def _parse_message(self, message):
        contents = message.content
        parsed_contents = []
        for content in contents:
            content_type = content.type
            # I love OpenAI for this sh*t 😅
            if content_type == "text":
                text_content = content.text.value
                annotations = {"file_citation": [], "file_path": []}
                for annotation in content.text.annotations:
                    annotation_type = annotation.type
                    # File citation
                    if annotation_type == "file_citation":
                        annotations["file_citation"].append({
                            "placeholder_text": annotation.text,
                            "file_id": annotation.file_citation.file_id,
                            "quote": annotation.file_citation.quote,
                            "start_index": annotation.start_index,
                            "end_index": annotation.end_index
                        })
                    # File path - code interpreter
                    elif annotation_type == "file_path":
                        file_name = self.client.files.retrieve(annotation.file_path.file_id).filename
                        # download file, TODO: try except
                        file_api_response = self.client.files.with_raw_response.retrieve_content(annotation.file_path.file_id)
                        if file_api_response.status_code == 200:
                            file_content = file_api_response.content
                        annotations["file_path"].append({
                            "placeholder_text": annotation.text,
                            "file_id": annotation.file_path.file_id,
                            "file_name": file_name,
                            "file_content": file_content,
                            "start_index": annotation.start_index,
                            "end_index": annotation.end_index
                        })
                    else:
                        raise NotImplementedError
                parsed_contents.append({
                    "type": "text",
                    "text_value": text_content,
                    "annotations": annotations
                })
            elif content_type == "image_file":
                print(89768757657687)
                print(content)
                print(self.client.files.retrieve(content.image_file.file_id))
                file_name = self.client.files.retrieve(content.image_file.file_id).filename
                # download file, TODO: Add try except
                file_api_response = self.client.files.with_raw_response.retrieve_content(content.image_file.file_id)
                if file_api_response.status_code == 200:
                    file_content = file_api_response.content
                parsed_contents.append({
                    "type": "image_file",
                    "file_id": content.image_file.file_id,
                    "file_name": file_name + ".png",
                    "file_content": file_content,
                })
            else:
                raise NotImplementedError
        return parsed_contents



    def _wait_for_run_finish(self, run):
        for _ in range(60 * 2): # 60 seconds
            run = self.client.beta.threads.runs.retrieve( # update run
                thread_id = run.thread_id,
                run_id = run.id
            )
            # About run status: https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps
            # return when these statuses are reached, else wait 0.5 second
            # TODO: add status return
            if run.status == "completed":
                return
            elif run.status == "failed":
                return
            elif run.status == "expired":
                return
            elif run.status == "cancelled":
                return
            elif run.status == "requires_action":
                return
            time.sleep(0.5)
        return # TODO: timeout

    def _run_thread(self, thread):
        run = self.client.beta.threads.runs.create(
            thread_id = thread.id,
            assistant_id = self.assistant.id,
            instructions = ""
        )
        return run

    def _create_message(self, content, thread):
        message = self.client.beta.threads.messages.create(
            thread_id = thread.id,
            role = "user",
            content = content
        )
        return message

    # get thread if exists, else create thread, update thread last used time then return thread
    def _get_thread(self, context_id):
        if context_id in self.thread_mapping_table: # get thread
            thread_id = self.thread_mapping_table[context_id]["thread_id"]
            self._update_thread_mapping(context_id, thread_id) # update last_used
            thread = self.client.beta.threads.retrieve(thread_id)
            return thread
        else: # create thread
            thread = self.client.beta.threads.create()
            return thread
    

    def _update_thread_mapping(self, context_id, thread_id):
        self.thread_mapping_table[context_id] = {
            "thread_id": thread_id,
            "last_used": datetime.now().timestamp()
        }
        with open("./thread_mapping.json", "w") as f:
            json.dump(self.thread_mapping_table, f)