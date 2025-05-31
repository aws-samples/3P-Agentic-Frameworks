import boto3
#from clickhouse_driver import Client
from datetime import datetime, timezone
import json
import gzip
import io
from clickhouse_client import ClickHouseClient



WAF_LOGS_BUCKET = 'xxxx'
WAF_LOGS_BUCKET_PREFIX = 'xxxx'

class WAFLogProcessor:
    def __init__(self):
        self.s3 = boto3.client('s3')

        self.clickhouse = ClickHouseClient()
        self.bucket = WAF_LOGS_BUCKET
        self.prefix = WAF_LOGS_BUCKET_PREFIX

    def create_table(self):

        self.clickhouse.execute('DROP TABLE IF EXISTS waf_logs')
        self.clickhouse.execute('''
            CREATE TABLE waf_logs
                (
                    timestamp DateTime64,  -- UTC-compatible
                    format_version UInt32,
                    webacl_id String,
                    terminating_rule_id String,
                    terminating_rule_type String,
                    action String,
                    http_source_name String,
                    http_source_id String,
                    response_code_sent Nullable(UInt16),

                    -- httpRequest fields
                    http_client_ip String,
                    http_country String,
                    http_uri String,
                    http_args String,
                    http_http_version String,
                    http_http_method String,
                    http_request_id String,
                    http_fragment String,
                    http_scheme String,
                    http_host String,

                    -- httpRequest.headers fields
                    header_host String,
                    header_connection String,
                    header_cache_control String,
                    header_upgrade_insecure_requests String,
                    header_user_agent String,
                    header_accept String,
                    header_accept_encoding String,
                    header_accept_language String,
                    header_if_none_match String,
                    header_if_modified_since String
                )
                ENGINE = MergeTree()
                ORDER BY (timestamp);

        ''')

    def process_log(self, content):
        log = json.loads(content)
        http_req = log.get('httpRequest', {})
        headers = {h['name']: h['value'] for h in http_req.get('headers', [])}

        def get_header(name):
            return headers.get(name, '')
            #return headers.get(name, None)

        try:
            row_data = {
                'timestamp': datetime.fromtimestamp(log['timestamp'] / 1000, timezone.utc), #datetime.utcfromtimestamp(log['timestamp'] / 1000),
                'format_version': log.get('formatVersion'),
                'webacl_id': log.get('webaclId'),
                'terminating_rule_id': log.get('terminatingRuleId'),
                'terminating_rule_type': log.get('terminatingRuleType'),
                'action': log.get('action'),
                'http_source_name': log.get('httpSourceName'),
                'http_source_id': log.get('httpSourceId'),
                'response_code_sent': log.get('responseCodeSent'),

                # httpRequest fields
                'http_client_ip': http_req.get('clientIp'),
                'http_country': http_req.get('country'),
                'http_uri': http_req.get('uri'),
                'http_args': http_req.get('args'),
                'http_http_version': http_req.get('httpVersion'),
                'http_http_method': http_req.get('httpMethod'),
                'http_request_id': http_req.get('requestId'),
                'http_fragment': http_req.get('fragment'),
                'http_scheme': http_req.get('scheme'),
                'http_host': http_req.get('host'),

                # httpRequest.headers fields
                'header_host': get_header('Host'),
                'header_connection': get_header('Connection'),
                'header_cache_control': get_header('Cache-Control'),
                'header_upgrade_insecure_requests': get_header('Upgrade-Insecure-Requests'),
                'header_user_agent': get_header('User-Agent'),
                'header_accept': get_header('Accept'),
                'header_accept_encoding': get_header('Accept-Encoding'),
                'header_accept_language': get_header('Accept-Language'),
                'header_if_none_match': get_header('If-None-Match'),
                'header_if_modified_since': get_header('If-Modified-Since')
            }
        except Exception as e:
            print(f'Exception extracting data. Details: {e}')
            print(f'{content}')

        return row_data

    def process_s3_file(self, key):
        try:
            print(f"Processing file '{key}'...")
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            gzipped_content = response['Body'].read()
            
            # Decompress gzip content
            with gzip.GzipFile(fileobj=io.BytesIO(gzipped_content)) as gz:
                content = gz.read().decode('utf-8')
            
            logs = []
            for line in content.splitlines():
                if line.strip():  # Skip empty lines
                    logs.append(self.process_log(line))
            
            print('Inserting in waf_logs table...')
            if logs:
                try:
                    self.clickhouse.execute('INSERT INTO waf_logs VALUES', logs)
                except Exception as e1:
                    print(f'Exception inserting data. Details: {e1}')
                    print(logs)
            print(f"Processed {len(logs)} logs from {key}")
        except Exception as e:
            print(f"Error processing {key}: {e}")

    def process_all_logs(self):
        paginator = self.s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.gz'):  # Process only gzip files
                    self.process_s3_file(obj['Key'])

    def run(self):
        print("Creating table...")
        self.create_table()
        print("Table Created! Table name: waf_logs")
        print("Processing logs...")
        self.process_all_logs()
        print("Done!")

if __name__ == "__main__":
    processor = WAFLogProcessor()
    processor.run()

