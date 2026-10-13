from langchain_community.agent_toolkits.gmail.toolkit import GmailToolkit
from langchain_community.agent_toolkits.file_management import FileManagementToolkit
from langchain_community.agent_toolkits.zapier.toolkit import ZapierToolkit


file_toolkit = FileManagementToolkit(root_dir="../creating_files")
file_tools = file_toolkit.get_tools()

TOOLS = file_tools
