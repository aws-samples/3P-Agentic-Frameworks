# AWS Infrastructure Security Audit And Reporting Crew

Welcome to the AWS Infrastructure Security Audit And Reporting Crew project, powered by [CrewAI](https://crewai.com). This project is designed to help you perform security audits and generate reports for your AWS infrastructure using a multi-agent AI system, leveraging the powerful and flexible framework provided by CrewAI.

## Get Started

### Python Version Requirements

CrewAI requires Python >=3.10 and <3.13. Here's how to check your version:

```bash
python3 --version
```

If you need to update Python, visit [python.org/downloads](https://python.org/downloads)

### Installing CrewAI

1. Install CrewAI with all recommended tools using either method:

```bash
pip install 'crewai[tools]'
```
or
```bash
pip install crewai crewai-tools
```

2. For existing installations, upgrade CrewAI:

```bash
pip install --upgrade crewai crewai-tools
```

If you see a Poetry-related warning, migrate to the new dependency manager:
```bash
crewai update
```

3. Verify your installation:

```bash
pip freeze | grep crewai
```

### Project Setup

1. Clone this repository
2. Set up your environment variables (see Environment Variables section below)
3. Install dependencies with:
    ```bash
    crewai install
    ```

### Customizing
### Environment Variables

Create a `.env` file in the root directory with the following required variables:

```env
# AWS Credentials for Bedrock
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION_NAME=your_region
MODEL=bedrock/anthropic.claude-3-sonnet-20240229-v1:0  # Or your preferred Bedrock model
SERPER_API_KEY=your_serper_api_key # Serper API key for research
```

#### AWS Bedrock Setup
1. Ensure you have access to AWS Bedrock in your AWS account
2. Your AWS credentials must have permissions to invoke Bedrock models
3. The specified AWS region must have Bedrock available
4. The model specified in `MODEL` must be enabled in your Bedrock console

### Supported Models
- See [AWS Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids-arns.html) for more models

### Configuration Files
- Modify `src/aws_infrastructure_security_audit_and_reporting/config/agents.yaml` to define your agents
- Modify `src/aws_infrastructure_security_audit_and_reporting/config/tasks.yaml` to define your tasks
- Modify `src/aws_infrastructure_security_audit_and_reporting/crew.py` to add your own logic, tools and specific args
- Modify `src/aws_infrastructure_security_audit_and_reporting/main.py` to add custom inputs for your agents and tasks

## Running the Project

To start your crew of AI agents and begin the AWS security audit, run this from the root folder of your project:

```bash
crewai run
```

This command initializes the AWS Infrastructure Security Audit crew, assembling the agents and assigning them tasks as defined in your configuration.

This example, unmodified, will run the create a `report.md` file with the output of a research on LLMs in the root folder.

## Understanding Your Crew

The AWS Infrastructure Security Audit crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to perform security audits and generate comprehensive reports. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback:
- Visit the [CrewAI documentation](https://docs.crewai.com)
- Check out the [CrewAI GitHub repository](https://github.com/CrewAIInc/crewAI)
- [Join our Forum](https://commuity.crewai.com)
- [Chat with the docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.
