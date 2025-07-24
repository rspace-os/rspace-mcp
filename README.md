# RSpace MCP server

This is a proof-of-concept MCP server for RSpace that runs locally on your machine. It uses the [RSpace Python client](https://github.com/rspace-os/rspace-client-python) and exposes some RSpace API endpoints to LLM agents using the Model Context Protocol.

## Installation and configuration

1. Clone or download this repository to your local machine
2. [ Install `uv`](https://docs.astral.sh/uv/#highlights) and `python`
3. Run `uv sync` to install dependencies
4. Create a `.env` file in the same folder and add 
    ``` 
    RSPACE_URL=RSpace URL # e.g. https://community.researchspace.com 
    RSPACE_API_KEY=your API key
    ```
5. Connect your LLM app with the RSpace MCP server
    1. For VS Code Copilot, add an mcp.json with the following content
        ```json
        {
          "inputs": [
            {
              "type": "promptString",
              "id": "rspace-apikey",
              "description": "RSpace API Key",
              "password": true
            },
            {
              "type": "promptString",
              "id": "rspace-url",
              "description": "RSpace base URL",
              "password": false
            }
          ],
          "servers": {
            "rspace": {
              "command": "uv",
              "args": [
                "--directory",
                "<full path to this directory>",
                "run",
                "main.py"
              ],
              "env": {
                "RSPACE_API_KEY": "${input:rspace-apikey}",
                "RSPACE_URL": "${input:rspace-url}"
              }
            }
          }
        }
        ```
        
    1. For Claude Desktop, add a claude_desktop_config.json with the following content:
        ```json
        {
          "mcpServers": {
            "rspace": {
              "command": "/Users/tilomathes/.local/bin/uv",
              "args": [
                "--directory",
                "<full path to this directory>",
                "run",
                "main.py"
              ],
              "env": {}
            }
          }
        }

         ```
## Using the RSpace through the MCP server
Please bear in mind that this is a proof of concept and your production use case might require a more specific MCP server configured with specifically fine-tuned tools. The tools provided here in this prototype ...
-  do not exhaustively feature the functionality currently available through the RSpace Python client
-  might be more than you need for your use case
-  might not be optimally configured for how you would like to interact with RSpace

We're curious to learn about how you (want to) use this solution, so let us know about your experiences and learnings or contribute them directly to this repository.

### Use cases and applications
You can find descriptions of some usecases and examples in the [examples folder](/examples) and we're looking forward to hearing about new examples and learnings. If you have an experience to share, feel free to contribute.

### Contributing new Tools
If you develop new tools or toolsets, feel free to share code snippets or entire tool sets in the [tools folder](/tools) with appropriate annotations.

## Acknowledgements

This project is based on code originally created by [richarda23](https://github.com/richarda23).
