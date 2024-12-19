from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from aws_infrastructure_security_audit_and_reporting.tools.aws_infrastructure_scanner_tool import AWSInfrastructureScannerTool
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

@CrewBase
class AwsInfrastructureSecurityAuditAndReportingCrew():
    """AwsInfrastructureSecurityAuditAndReporting crew"""

    @agent
    def infrastructure_mapper(self) -> Agent:
        return Agent(
            config=self.agents_config['infrastructure_mapper'],
            tools=[AWSInfrastructureScannerTool()],
        )

    @agent
    def security_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['security_analyst'],
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['report_writer']
        )

    @task
    def map_aws_infrastructure_task(self) -> Task:
        return Task(
            config=self.tasks_config['map_aws_infrastructure_task'],
            tools=[],
        )

    @task
    def exploratory_security_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['exploratory_security_analysis_task'],
            tools=[],
        )

    @task
    def generate_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['generate_report_task'],
            tools=[],
        )


    @crew
    def crew(self) -> Crew:
        """Creates the AwsInfrastructureSecurityAuditAndReporting crew"""
        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )
