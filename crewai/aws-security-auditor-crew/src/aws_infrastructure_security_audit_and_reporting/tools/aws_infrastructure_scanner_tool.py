from typing import Type, Dict, List
from crewai_tools import BaseTool
from pydantic import BaseModel, Field
import boto3
import json
from datetime import datetime
import os

class AWSInfrastructureScannerInput(BaseModel):
    """Input schema for AWSInfrastructureScanner."""
    service: str = Field(
        ...,
        description="AWS service to scan (e.g., 'ec2', 's3', 'iam', 'rds', 'vpc', 'all')"
    )
    region: str = Field(
        default_factory=lambda: os.getenv('AWS_REGION_NAME', 'us-west-2'),
        description="AWS region to scan"
    )

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class AWSInfrastructureScannerTool(BaseTool):
    name: str = "AWS Infrastructure Scanner"
    description: str = (
        "A tool for scanning and mapping AWS infrastructure components and their configurations. "
        "Can retrieve detailed information about EC2 instances, S3 buckets, IAM configurations, "
        "RDS instances, VPC settings, and security groups. Use this tool to gather information "
        "about specific AWS services or get a complete infrastructure overview."
    )
    args_schema: Type[BaseModel] = AWSInfrastructureScannerInput

    def _run(self, service: str, region: str) -> str:
        try:
            if service.lower() == 'all':
                return json.dumps(self._scan_all_services(region), indent=2, cls=DateTimeEncoder)
            return json.dumps(self._scan_service(service.lower(), region), indent=2, cls=DateTimeEncoder)
        except Exception as e:
            return f"Error scanning AWS infrastructure: {str(e)}"

    def _scan_all_services(self, region: str) -> Dict:
        return {
            'ec2': self._scan_service('ec2', region),
            's3': self._scan_service('s3', region),
            'iam': self._scan_service('iam', region),
            'rds': self._scan_service('rds', region),
            'vpc': self._scan_service('vpc', region)
        }

    def _scan_service(self, service: str, region: str) -> Dict:
        session = boto3.Session(region_name=region)

        if service == 'ec2':
            client = session.client('ec2')
            instances = client.describe_instances()
            security_groups = client.describe_security_groups()
            return {
                'instances': instances['Reservations'][:5],
                'security_groups': security_groups['SecurityGroups'][:5]
            }

        elif service == 's3':
            client = session.client('s3')
            buckets = client.list_buckets()
            bucket_details = []
            for bucket in buckets['Buckets'][:5]:
                try:
                    encryption = client.get_bucket_encryption(Bucket=bucket['Name'])
                except client.exceptions.ClientError:
                    encryption = None
                bucket_details.append({
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'],
                    'encryption': encryption
                })
            return {'buckets': bucket_details}

        elif service == 'iam':
            client = session.client('iam')
            return {
                'users': client.list_users()['Users'][:5],
                'roles': client.list_roles()['Roles'][:5],
                'policies': client.list_policies(Scope='Local')['Policies'][:5]
            }

        elif service == 'rds':
            client = session.client('rds')
            return {
                'instances': client.describe_db_instances()['DBInstances'][:5]
            }

        elif service == 'vpc':
            client = session.client('ec2')
            return {
                'vpcs': client.describe_vpcs()['Vpcs'][:5],
                'subnets': client.describe_subnets()['Subnets'][:5],
                'network_acls': client.describe_network_acls()['NetworkAcls'][:5]
            }

        else:
            return {'error': f'Unsupported service: {service}'}
