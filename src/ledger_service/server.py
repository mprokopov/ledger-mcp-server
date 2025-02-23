import asyncio

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio
from myledger import fetch_accounts, get_account_balance, get_account_register

# Add configuration constant at the top with other globals
LEDGER_BASE_PATH = "/Users/maksymprokopov/personal/ledger"

def get_ledger_path(year: str) -> str:
    """Construct the ledger file path for a given year."""
    return f"{LEDGER_BASE_PATH}/{year}/experiment.ledger"

server = Server("ledger-service")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        types.Tool(
                    name="list-accounts",
                    description="List all ledger accounts",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "year": {"type": "string"},
                },
                "required": ["year"],
            },
        ),
        types.Tool(
                    name="account-balance",
                    description="Get the balance of an account",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "year": {"type": "string"},
                            "account": {"type": "string"},
                },
                "required": ["year", "account"],
            },
        ),
        types.Tool(
                    name="account-register",
                    description="Get the register of an account",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "year": {"type": "string"},
                            "account": {"type": "string"},
                },
                "required": ["year", "account"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can modify server state and notify clients of changes.
    """

    if name == "list-accounts":
        year = arguments.get("year")
        
        account_list = fetch_accounts(get_ledger_path(year)).splitlines()

        accounts_text = "\nLedger Accounts:\n" + "\n".join(f"- {account}" for account in account_list)

        return [
            types.TextContent(
                type="text",
                text=accounts_text
            )
        ]
    elif name == "account-balance":
        year = arguments.get("year")
        account = arguments.get("account")
        balance = get_account_balance(get_ledger_path(year), account)
        return [
            types.TextContent(
                type="text",
                text=f"The balance of {account} is {balance}"
            )
        ]
    elif name == "account-register":
        year = arguments.get("year")
        account = arguments.get("account")
        register = get_account_register(get_ledger_path(year), account)
        return [
            types.TextContent(
                type="text",
                text=f"The register of {account} is {register}"
            )
        ]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ledger-service",
                server_version="0.1.1",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )