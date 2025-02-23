import asyncio

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio
from myledger import fetch_accounts, get_account_balance, get_account_register
# Store notes as a simple key-value dict to demonstrate state management
notes: dict[str, str] = {}

server = Server("ledger-service")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available note resources.
    Each note is exposed as a resource with a custom note:// URI scheme.
    """
    return [
        types.Resource(
            uri=AnyUrl(f"note://internal/{name}"),
            name=f"Note: {name}",
            description=f"A simple note named {name}",
            mimeType="text/plain",
        )
        for name in notes
    ]

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific note's content by its URI.
    The note name is extracted from the URI host component.
    """
    if uri.scheme != "note":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    name = uri.path
    if name is not None:
        name = name.lstrip("/")
        return notes[name]
    raise ValueError(f"Note not found: {name}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts.
    Each prompt can have optional arguments to customize its behavior.
    """
    return [
        types.Prompt(
            name="summarize-notes",
            description="Creates a summary of all notes",
            arguments=[
                types.PromptArgument(
                    name="style",
                    description="Style of the summary (brief/detailed)",
                    required=False,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt by combining arguments with server state.
    The prompt includes all current notes and can be customized via arguments.
    """
    if name != "summarize-notes":
        raise ValueError(f"Unknown prompt: {name}")

    style = (arguments or {}).get("style", "brief")
    detail_prompt = " Give extensive details." if style == "detailed" else ""

    return types.GetPromptResult(
        description="Summarize the current notes",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"Here are the current notes to summarize:{detail_prompt}\n\n"
                    + "\n".join(
                        f"- {name}: {content}"
                        for name, content in notes.items()
                    ),
                ),
            )
        ],
    )

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
    if name == "add-note":
        if not arguments:
            raise ValueError("Missing arguments")

        note_name = arguments.get("name")
        content = arguments.get("content")

        if not note_name or not content:
            raise ValueError("Missing name or content")

        # Update server state
        notes[note_name] = content

        # Notify clients that resources have changed
        await server.request_context.session.send_resource_list_changed()

        return [
            types.TextContent(
                type="text",
                text=f"Added note '{note_name}' with content: {content}",
            )
        ]

    elif name == "list-accounts":
        year = arguments.get("year")
        # Get the accounts list from the ledger
        account_list = fetch_accounts(f"/Users/maksymprokopov/personal/ledger/{year}/experiment.ledger")

        # Format the accounts into a readable string
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
        balance = get_account_balance(f"/Users/maksymprokopov/personal/ledger/{year}/experiment.ledger", account)
        return [
            types.TextContent(
                type="text",
                text=f"The balance of {account} is {balance}"
            )
        ]
    elif name == "account-register":
        year = arguments.get("year")
        account = arguments.get("account")
        register = get_account_register(f"/Users/maksymprokopov/personal/ledger/{year}/experiment.ledger", account)
        return [
            types.TextContent(
                type="text",
                text=f"The register of {account} is {register}"
            )
        ]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ledger-service",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
