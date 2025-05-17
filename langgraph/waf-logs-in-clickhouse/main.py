import sys
import json
from typing import Literal
from pathlib import Path

# LangGraph imports
from typing import Annotated
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langchain_core.runnables.graph import MermaidDrawMethod

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

#from IPython.display import Image, display
from langchain_aws import ChatBedrockConverse
from utility import Utility
from clickhouse_client import ClickHouseClient

MODEL_ID1   = "us.amazon.nova-pro-v1:0"
MODEL_ID2   = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

# apac.anthropic.claude-3-5-sonnet-20241022-v2:0
# apac.anthropic.claude-3-haiku-20240307-v1:0
# mistral.mixtral-8x7b-instruct-v0:1
# apac.amazon.nova-pro-v1:0
# apac.amazon.nova-micro-v1:0
# apac.amazon.nova-lite-v1:0
# apac.anthropic.claude-3-haiku-20240307-v1:0

# MODEL_ID2   = "apac.amazon.nova-lite-v1:0"

AWS_REGION = "us-west-2"
DATABASE_NAME = 'default'

llm1 = ChatBedrockConverse(
            model=MODEL_ID1,
            temperature=0,
            max_tokens=9900,
            region_name=AWS_REGION,
        )

llm2 = ChatBedrockConverse(
            model=MODEL_ID2,
            temperature=0,
            max_tokens=8190,
            region_name=AWS_REGION,
        )

util = Utility()

class AppState(MessagesState):
    user_input: str
    conn: ClickHouseClient
    schema: str
    sql_query: str
    query_results: str
    usage: list
    response: str


def find_table_schema(state: AppState):
    '''
    This function searches for table schema
    '''
    
    util.log_header(function_name=sys._getframe().f_code.co_name)
    table_schema = state['conn'].list_tables(database=DATABASE_NAME)
    state['schema'] = table_schema
    
    return state                



def generate_sql_statement(state: AppState):
    '''
    This function uses LLM to generate ClickHouse compatible SELECT statement for the task
    '''
    
    util.log_header(function_name=sys._getframe().f_code.co_name)
    prompt = f"""
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
                        
                    Table Schema: {state['schema']}
                    Now, generate SQL for: {state['user_input']}

                    """
    
    state['messages'].append(HumanMessage(content=prompt))
    ai_msg = llm1.invoke(state['messages'])
    state = add_usage(state, ai_msg)
    state['messages'].append(ai_msg)

    sql = ai_msg.content
    sql = util.clean_sql_string(sql)

    state['sql_query'] = sql

    util.log_data(data=f"\n-------------------\nSQL Query: {sql}\n-------------------")
    
    return state


def execute_sql_statement(state: AppState):
    '''
    This function executes SQL statement
    '''
    
    util.log_header(function_name=sys._getframe().f_code.co_name)

    conn = state['conn']
    results = conn.execute_query(state['sql_query'])
    state['query_results'] = json.dumps(results)

    # util.log_data(data=f"Query Results: {state['query_results']}")

    return state

def generate_response(state: AppState):
    '''
    Generate final response
    '''
    
    util.log_header(function_name=sys._getframe().f_code.co_name)

    prompt = f"""
                    Task: Answer question on the basis of context
                    question: {state['user_input']}

                    context: {state['query_results']}

                    Important:
                    - Provide response from the context
                    - Do not show the SQL statement
                    """
    
    state['messages'].append(HumanMessage(content=prompt))

    try:
        ai_msg = llm2.invoke(state['messages'])
        state = add_usage(state, ai_msg)
        state['messages'].append(ai_msg)
        state['response'] = ai_msg.content

        util.log_data(data=f"\n-------------------\n\nResponse: {ai_msg.content}\n-------------------")
    except Exception as e:
        error = f"Exception occurred. Details: {e}"
        state['response'] = error
        util.log_error(error)
    
    return state


def build_graph():
    """
    This function prepares LangGraph nodes, edges
    """

    # create StateGraph object
    graph_builder = StateGraph(AppState)

    # add nodes to the graph
    
    graph_builder.add_node("Retrieve Table Schema", find_table_schema)
    graph_builder.add_node("Generate SQL Statement", generate_sql_statement)
    graph_builder.add_node("Execute SQL Statement", execute_sql_statement)
    graph_builder.add_node("Generate Response", generate_response)
    
    # add edges to connect nodes
    graph_builder.add_edge(START, "Retrieve Table Schema")
    graph_builder.add_edge("Retrieve Table Schema", "Generate SQL Statement")
    graph_builder.add_edge("Generate SQL Statement", "Execute SQL Statement")
    graph_builder.add_edge("Execute SQL Statement", "Generate Response")
    
    graph_builder.add_edge("Generate Response", END)
    
    # compile graph
    app = graph_builder.compile()
    
    util.log_data(data="Workflow compiled successfully")

    # Visualize the graph
    #display(Image(app.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)))

    return app

def add_usage(state: AppState, ai_msg: AIMessage):
    '''
    This function adds usage information to the state object
    '''

    model = ai_msg.response_metadata.get('model_name')
    usage_data = ai_msg.usage_metadata
    latency = ai_msg.response_metadata.get('metrics').get('latencyMs')

    latency_total = 0
    if type(latency) is list:
        for l in latency:
            latency_total += l
    else:
        latency_total = latency

    state['usage'].append(
        {
            'model_name': model,
            'input_tokens': usage_data.get('input_tokens'),
            'output_tokens': usage_data.get('output_tokens'),
            'latency': latency_total
            })
    
    return state


def invoke_for_input(input: str, langgraph_app):
    state = AppState()

    state['user_input'] = input
    state['sql_query'] = ''
    state['query_results'] = ''
    state['usage'] = []
    state['messages'] = []
    state['schema'] = ''
    state['response'] = ''

    conn = ClickHouseClient()
    state['conn'] = conn

    system_message = '''
    You are a professional and courteous log analysis agent for AnyCompany. Your goal is to assist users effectively and efficiently using the tools and information provided. 

    Guidelines:
            1. Maintain a polite, helpful, and pleasant tone at all times.
            2. Avoid using strong or negative words
            
            Your primary objective is to provide accurate, empathetic, and solution-oriented support while ensuring a positive user experience.
    '''

    state['messages'].append(SystemMessage(content=system_message))
    
    state = langgraph_app.invoke(state)
    # util.log_execution_flow(state['messages'])
    util.log_usage(state['usage'])

    return state['response']

if __name__ == '__main__':
    app = build_graph()

    while True:
        try:
            user_input = input("User: ")
            user_input = user_input.strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            if (len(user_input) > 4):
                response = invoke_for_input(input=user_input, langgraph_app=app)
                print(f'AI: {response}')
        except Exception as e:
            print(f'Exception occurred. Details: {str(e)}')
            break


    

    


    


    
