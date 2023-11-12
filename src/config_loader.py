# generated by chat-gpt
import json
import os.path
import time
from functools import reduce

CONFIG_FILE = 'config.json'

'''
EXAMPLE:
from config_loader import ConfigLoader
allowed_users = ConfigLoader.get("allowed_users")
'''

class ConfigLoader:
    _config = {}
    _config_last_modified_time = None

    @staticmethod
    def _config_modified():
        """
        Check if the config file has been modified
        """
        current_time = time.time()
        modified_time = os.path.getmtime(CONFIG_FILE)
        if ConfigLoader._config_last_modified_time is None:
            ConfigLoader._config_last_modified_time = modified_time
            return True
        return modified_time > ConfigLoader._config_last_modified_time

    @staticmethod
    def load_config():
        if ConfigLoader._config_modified():
            with open(CONFIG_FILE, mode='r') as f:
                ConfigLoader._config = json.load(f)
                ConfigLoader._config_last_modified_time = os.path.getmtime(CONFIG_FILE)

    @staticmethod
    def get(*keys):
        ConfigLoader.load_config()
        try:
            result = reduce(lambda d, key: d[key], keys, ConfigLoader._config)
        except KeyError:
            result = None
        return result

if __name__ == '__main__':
    pass