import sys
import json

# strands 
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# mcp
from mcp import stdio_client, StdioServerParameters

# local imports
from utility import Utility, GREEN_COLOR, RESET_COLOR, WHITE_COLOR, BLUE_COLOR


REASONING_MODEL             = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
SQL_GENERATION_MODEL        = "us.anthropic.claude-3-haiku-20240307-v1:0"
RESPONSE_GENERATION_MODEL   = "us.amazon.nova-pro-v1:0"

AWS_REGION      = "us-west-2"
DATABASE_NAME   = 'default'

MCP_JSON_FILE   = './mcp.json'

ORCHESTRATOR_SYSTEM_PROMPT ="""
You are QueryAssist, an advanced AI designed to answer natural language questions by interacting with a ClickHouse database. Your workflow is as follows:
1. Understand the User Query:
  - Carefully read and interpret the user's question, which will always be provided in natural language.
2. Schema Retrieval:
  - Retrieve the waf_logs table schema from the database based on the context of the question.
3. SQL Query Generation:
  - Generate accurate, efficient, and ClickHouse-compatible SQL queries that will retrieve the data needed to answer the user's question.
  - Ensure the queries are safe, syntactically correct, and optimized for performance.
4. Query Execution:
  - Execute the generated SQL query against the ClickHouse database.
  - Retrieve the results, handling any errors or ambiguities gracefully.
5. Natural Language Response:
  - Convert the raw query results into a clear, concise, and informative natural language answer that directly addresses the user's original question.
  - Include context or explanations if necessary to ensure the response is understandable to a non-technical user.

Key Responsibilities:
  - Accurately interpret diverse natural language questions.
  - Reliably map questions to the correct database tables and fields.
  - Generate and execute ClickHouse SQL queries with high precision.
  - Summarize and explain results in user-friendly language.

Decision Protocol:
  - If the question is unclear, ask the user for clarification before proceeding.
  - If multiple tables or joins are needed, construct the appropriate SQL statements.
  - Always prioritize data privacy and query efficiency.

Always confirm your understanding of the user's question before generating the SQL query to ensure accurate and relevant answers.
"""


util = Utility()
llm_usage = []


@tool
def generate_sql_statement(user_input: str, table_schema: str) -> str:
    """
    Generates a ClickHouse-compatible SQL statement based on a natural language user query and database schema.
    
    Args:
        user_input (str): The natural language query from the user describing what data they want to retrieve
        table_schema (str): A string representation of the database schema including tables, columns and their types
        
    Returns:
        str: A properly formatted SQL statement compatible with ClickHouse that addresses the user's query
    """
    
    util.log_header(function_name=sys._getframe().f_code.co_name)
    util.log_data('I need to generate SQL statement...')
    SYSTEM_PROMPT = f"""
            You are an expert SQL developer. 
            
            SQL Generation rules:
            - Output only SQL Statement, with no additional text or formatting
            - Do not add any decorators around the query
            - When generating SQL SELECT queries involving date filtering, follow these rules: 
                - if year is not given then consider 2025
                - Always use the >= (greater than or equal to) and <= (less than or equal to) operators in the WHERE clause to specify date ranges 
                - Ensure that the date format matches the database schema
                - do not use toString for datetime columns in where condition
            - Always convert DateTime column type (including DateTime64) to string using the toString() function
            - Always convert any column of type DateTime (including DateTime64) to a string using the toString() function. For example, if a table has a column named timestamp of type 
            - Do not select all columns using SELECT *. select all columns by names
            - SQL MUST be compatible with ClickHouse database. When using functions, Use only native ClickHouse native functions
            - String comparisons in the WHERE clause must be case-insensitive by converting both the column and the string literal to lowercase using the LOWER() function. Example:
                Input: Find all blocked hosts on 10th May
                Output: 
                    SELECT toString(timestamp), format_version, webacl_id, terminating_rule_id, terminating_rule_type, action, http_source_name, http_source_id, response_code_sent, http_client_ip, http_country, http_uri, http_args, http_http_version, http_http_method, http_request_id, http_fragment, http_scheme, http_host, header_host, header_connection, header_cache_control, header_upgrade_insecure_requests, header_user_agent, header_accept, header_accept_encoding, header_accept_language, header_if_none_match, header_if_modified_since
                    FROM <table_name> 
                    WHERE LOWER(action) = LOWER('BLOCK') AND
                    (timestamp >= '2025-05-10 00:00:00'
                    AND timestamp <= '2025-05-10 23:59:59')
        """
    formatted_query = f"""generate SQL for: {user_input}

    Table Schema: {table_schema}"""

    sql_gen_model = BedrockModel(model_id=SQL_GENERATION_MODEL, verbose=True)
    
    sql_agent = Agent(system_prompt=SYSTEM_PROMPT,model=sql_gen_model, tools=[],) # no extra tools required
    agent_response = sql_agent(formatted_query)

    sql = str(agent_response)
    sql = util.clean_sql_string(sql)

    if len(sql) > 0:
        util.log_data('I have SQL statement')
        return sql
    else:
        return "I'm sorry I could not generate SQL statement for the provided inputs"

@tool
def generate_response(user_input: str, sql_query_results: str) -> str:
    """
    Generates a natural language response based on SQL query results and the original user question.

    Args:
        user_input (str): The original natural language question asked by the user
        sql_query_results (str): JSON string containing the results from executing the SQL query
        
    Returns:
        str: A natural language response that answers the user's question based on the SQL results
    """

    util.log_header(function_name=sys._getframe().f_code.co_name)
    util.log_data('Preparing answer...')

    system_message = '''
    You are a professional and courteous log analysis agent. Your goal is to answer user's questions using provided context. You must NOT make any assumptions.
    '''

    try:

        prompt = f"""
                    question: {user_input}
                    context: {sql_query_results}
                    """
        
        response_gen_model = BedrockModel(model_id=RESPONSE_GENERATION_MODEL, verbose=True)
        user_query_agent = Agent(system_prompt=system_message, model=response_gen_model, tools=[],)
        agent_response = user_query_agent(prompt)
        response = str(agent_response)
        

        if len(response) > 0:
            return response
        
        return "I apologize, but I couldn't properly analyze your English language question. Could you please rephrase or provide more context?"
        
        #state = add_usage(state, ai_msg)

        #util.log_data(data=f"\n-------------------\nResponse: {response}\n-------------------")
        
        #return sql
        
        #state = add_usage(state, ai_msg)
        

        util.log_data(data=f"\n-------------------\n\nResponse: {ai_msg.content}\n-------------------")
    except Exception as e:
        error = f"Exception occurred. Details: {e}"
        util.log_error(error)

def main():
    print(f"{BLUE_COLOR}WAF Logs Analysis Agent \n")
    print(f"{BLUE_COLOR}Ask your questions to search WAF logs in Clickhouse database")
    print(f"{BLUE_COLOR}Type 'exit' to quit.")

    mcp_json = util.load_mcp_json(MCP_JSON_FILE)

    print(mcp_json['command'])

    stdio_mcp_client = MCPClient(lambda: stdio_client(
        StdioServerParameters(
            command = mcp_json['command'], 
            args = mcp_json['args'],
            env = mcp_json['env'])))
    
    with stdio_mcp_client:
        # Get the tools from the MCP server
        tools = [generate_sql_statement, generate_response]
        tools += stdio_mcp_client.list_tools_sync()

        reasoning_model = BedrockModel(model_id=REASONING_MODEL, verbose=True)
        clickhouse_query_agent = Agent(
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            model=reasoning_model,
            tools=tools
        )

        # Interactive loop
        while True:
            try:
                user_input = input(f"{WHITE_COLOR}> ")
                user_input = user_input.strip()
                if user_input.lower() in ["exit", "quit"]:
                    print(f"{BLUE_COLOR}Goodbye! 👋 {RESET_COLOR}")
                    break

                if (len(user_input) > 4):
                    
                    print(f"{GREEN_COLOR}Thinking...")
                    response = clickhouse_query_agent(
                                user_input, 
                            )
                    
                    content = str(response)
                    print(f'\n{WHITE_COLOR}AI: {content}')

                   
                    
            except KeyboardInterrupt:
                print("\n\nExecution interrupted. Exiting...")
                break
            except Exception as e:
                print(f"\nAn error occurred: {str(e)}")
                print("Please try asking a different question.")


if __name__ == '__main__':
    main()