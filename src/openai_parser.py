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
        return str(new_messages)

    def _get_new_messages(self, thread):
        messages = self.client.beta.threads.messages.list(
            thread_id = thread.id,
        ).data
        for i in range(len(messages)):
            message = messages[i]
            if message.role == "user":
                messages = messages[:i]
                break
        return messages

    def _wait_for_run_finish(self, run):
        for _ in range(60 * 2): # 60 seconds
            run = self.client.beta.threads.runs.retrieve( # update run
                thread_id = run.thread_id,
                run_id = run.id
            )
            # About run status: https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps
            # return when these statuses are reached, else wait 0.5 second
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