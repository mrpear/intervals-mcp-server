# Intervals.icu MCP Server

This package implements a Model Context Protocol (MCP) server for connecting Claude with the Intervals.icu API. It provides tools for authentication, activity data retrieval, workout management, and wellness data handling.

## Requirements

- Python 3.10 or higher
- [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- httpx
- python-dotenv

## Setup

### 1. Install uv (recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone this repository

```bash
git clone https://github.com/yourusername/intervals-mcp-server.git
cd intervals-mcp-server
```

### 3. Create and activate a virtual environment

```bash
# Create virtual environment
uv venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
uv pip install -e .
```

### 5. Set up environment variables

Copy the `.env.example` file to `.env` and update the values:

```bash
cp .env.example .env
```

Then edit the `.env` file with your Intervals.icu API credentials:

```
API_KEY=your_intervals_api_key_here
ATHLETE_ID=your_athlete_id_here
```

#### Getting your Intervals.icu API Key

1. Log in to your Intervals.icu account
2. Go to Settings > API
3. Generate a new API key

#### Finding your Athlete ID

Your athlete ID is typically visible in the URL when you're logged into Intervals.icu. It looks like:
- `https://intervals.icu/athlete/i12345/...` where `i12345` is your athlete ID

## Usage

### 1. Run the server

```bash
python intervals_mcp_server.py
```

### 2. Configure Claude Desktop

To use this server with Claude Desktop, you need to add it to your Claude Desktop configuration.

1. Open your Claude Desktop App configuration at `~/Library/Application Support/Claude/claude_desktop_config.json` in a text editor. Create the file if it doesn't exist.

2. Add the following to your configuration:

```json
{
  "mcpServers": {
    "Intervals MCP Server": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "mcp",
        "run",
        "/path/to/intervals-mcp-server/intervals_mcp_server.py"
      ]
    }
  }
}
```

3. Restart Claude Desktop.

### 3. Use the MCP server with Claude

Once the server is running and Claude Desktop is configured, you can use the following tools:

- `get_activities`: Retrieve a list of activities
- `get_activity_details`: Get detailed information for a specific activity
- `get_activity_intervals`: Get detailed interval data for a specific activity
- `get_wellness_data`: Fetch wellness data
- `get_events`: Retrieve upcoming events (workouts, races, etc.)
- `get_event_by_id`: Get detailed information for a specific event

## License

The GNU General Public License v3.0
