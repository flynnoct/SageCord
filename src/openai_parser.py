import os, json, time
from datetime import datetime
from config_loader import ConfigLoader as CL
from openai import OpenAI

class OpenAI_Parser():
    def __init__(self):
        self.client = OpenAI(api_key = CL.get("openai", "api_key"))
        if not CL.get("openai", "assistant_id") is None: # if assistant_id is set, use it
            self.assistant = self.client.beta.assistants.retrieve(CL.get("openai", "assistant_id"))
        else:
            with open("./src/openai_tools.json", "r") as f:
                tools = json.load(f)
            self.assistant = self.client.beta.assistants.create(
                name="SageCord",
                instructions = "You are an assistant helping people with their problems. Your response text will be parsed as Markdown format, so please ensure your text output is in standard Markdown.",
                model = CL.get("openai", "model"),
                tools = tools
            )
        # check if thread_mapping exists, else create it
        if os.path.exists("./thread_mapping.json"):
            with open("./thread_mapping.json", "r") as f:
                self.thread_mapping_table = json.load(f)
        else:
            self.thread_mapping_table = {}

    def new_thread(self, context_id):
        context_id = str(context_id) # convert to string
        self._clean_expired_threads(context_id)

    def get_response(self, content, attachments, context_id):
        context_id = str(context_id) # convert to string
        uploaded_files = self._parse_attachments(attachments)
        thread = self._get_thread(context_id)
        self._set_thread_files(context_id, uploaded_files)
        user_message = self._create_message(content, uploaded_files, thread) # create message containing user's message
        run = self._run_thread(thread) # run thread
        thread_killed = self._wait_for_run_finish(run, context_id)
        if thread_killed:
            return [[{"type": "thread_killed"}]]
        new_messages = self._get_new_messages(thread)
        return new_messages
    
    def _parse_attachments(self, user_attachments):
        uploaded_files = []
        for attachment in user_attachments:
            uploaded_files.append(
                self.client.files.create(
                    file = attachment,
                    purpose = "assistants"
                    )
                )
        return uploaded_files

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

    # return True if thread is killed, else return False
    def _wait_for_run_finish(self, run, context_id):
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
            elif run.status == "requires_action": # function calling triggered
                thread_killed = self._process_function_calling(run, context_id)
                if thread_killed:
                    return True # thread is killed
            time.sleep(0.5)
        return False # TODO: timeout
    
    def _process_function_calling(self, run, context_id):
        thread_id = run.thread_id
        run_id = run.id
        # check which function is called
        tool_outputs = []
        for func_call in run.required_action.submit_tool_outputs.tool_calls:
            if func_call.function.name == "new_thread": # new thread
                self.new_thread(context_id)
                return True # thread is killed
        run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id = thread_id,
            run_id = run_id,
            tool_outputs = tool_outputs
        )
        return False # thread is not killed

        


    def _run_thread(self, thread):
        run = self.client.beta.threads.runs.create(
            thread_id = thread.id,
            assistant_id = self.assistant.id,
            instructions = ""
        )
        return run

    def _create_message(self, content, uploaded_files, thread):
        message = self.client.beta.threads.messages.create(
            thread_id = thread.id,
            role = "user",
            content = content,
            file_ids = [uploaded_file.id for uploaded_file in uploaded_files]
        )
        return message

    # get thread if exists, else create thread, update thread last used time then return thread
    def _get_thread(self, context_id):
        if context_id in self.thread_mapping_table: # get thread
            if not datetime.now().timestamp() - self.thread_mapping_table[context_id]["last_used"] > int(CL.get("openai", "thread_timeout_in_seconds")): # check if thread is expired
                thread_id = self.thread_mapping_table[context_id]["thread_id"]
                self._update_thread_mapping(context_id, thread_id) # update last_used
                thread = self.client.beta.threads.retrieve(thread_id)
                return thread
            else:
                self._clean_expired_threads(context_id)
                return self._get_thread(context_id)
        else: # create thread
            thread = self.client.beta.threads.create()
            self._update_thread_mapping(context_id, thread.id)
            return thread
        
    def _clean_expired_threads(self, context_id):
        if context_id not in self.thread_mapping_table:
            return
        for file_id in self.thread_mapping_table[context_id]["file_ids"]:
            self.client.files.delete(file_id)
        self.client.beta.threads.delete(self.thread_mapping_table[context_id]["thread_id"])
        self.thread_mapping_table.pop(context_id)
        
    def _set_thread_files(self, context_id, uploaded_files):
        thread_id = self.thread_mapping_table[context_id]["thread_id"]
        self._update_thread_mapping(context_id, thread_id, [uploaded_file.id for uploaded_file in uploaded_files])
    

    def _update_thread_mapping(self, context_id, thread_id, append_file_ids = []):
        if context_id in self.thread_mapping_table:
            self.thread_mapping_table[context_id]["last_used"] = datetime.now().timestamp()
            self.thread_mapping_table[context_id]["thread_id"] = thread_id
            self.thread_mapping_table[context_id]["file_ids"] += append_file_ids
        else:
            self.thread_mapping_table[context_id] = {
                "thread_id": thread_id,
                "last_used": datetime.now().timestamp(),
                "file_ids": []
            }
        with open("./thread_mapping.json", "w") as f:
            json.dump(self.thread_mapping_table, f)