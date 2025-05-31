# Standard library imports
import logging
import json
import re
from langchain_core.messages.base import get_msg_title_repr

BLUE_COLOR = '\033[94m'
GREEN_COLOR = '\033[92m'
WHITE_COLOR = '\033[97m'
RESET_COLOR = '\033[0m'

LOG_FILE_NAME = './app_logs.log'

class Utility:
    def __init__(self):

        logging.basicConfig(
                            level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[
                                #logging.StreamHandler(),
                                logging.FileHandler(LOG_FILE_NAME)
                            ]
                        )

        self.logger = logging.getLogger(__name__)
    
    def log_header(self, function_name: str):
        self.logger.info(f' #### {function_name}')
    
    def log_data(self, data, verbose=True):
        self.logger.info(f'{data}')

        if (verbose):
            print(data)

    def log_error(self, error):
        self.logger.error(f'{error}')


    def log_usage(self, usage: list):

        # Find the maximum length of model names to determine column width
        model_col_width = max(
            len('Model'),
            max(len(item['model_name']) for item in usage) 
        )

        col_width = 15
        # Create the header with dynamic width for Model column
        usage_to_print = (
            
            f'{"\nModel":<{model_col_width}} {"Input Tokens":<{col_width}} {"Output Tokens":<{col_width}} {"Latency":<{col_width}}'
        )
        
        # Add each usage item with aligned columns
        for item in usage:
            usage_to_print += (
                f"\n{item['model_name']:<{model_col_width}}"
                f"  {item['input_tokens']:<{col_width}}"
                f"{item['output_tokens']:<{col_width}}"
                f"{item['latency']:<{col_width}}"
            )

        self.logger.info(usage_to_print)


    def log_execution_flow(self, messages):
        self.logger.info(f" =========   Execution Flow  ========= ")
        for m in messages:
            title = get_msg_title_repr(m.type.title() + " Message")
            if m.name is not None:
                title += f"\nName: {m.name}"

            self.logger.info(f"{title}\n\n{m.content}")

    def clean_sql_string(self, sql):
        ''' 
        This functions removes decorators in llm response.
        Remove triple backticks and 'sql' identifier
        '''
        pattern = r'```sql\n(.*?)```'
        cleaned_string = re.search(pattern, sql, flags=re.DOTALL)
        
        if cleaned_string:
            return cleaned_string.group(1).strip()
        return sql.strip()
    
    def load_mcp_json(self, file_path: str):
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
        return None
    
