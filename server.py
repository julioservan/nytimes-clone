#!/usr/bin/env python3
"""NYT demo server — serves static files + Claude streaming chat endpoint."""
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import anthropic

SYSTEM_PROMPT = """You are an AI news assistant for The New York Times. \
You help readers understand current events, discover stories, and explore topics in depth. \
Be concise, factual, and journalistic in tone. \
When discussing news topics, you may reference the kinds of stories NYT covers: politics, world affairs, \
business, science, culture, sports, and more. \
Keep responses under 3 short paragraphs unless the reader asks for more detail.

You are aware of the following story currently featured on NYT:

CULTURE — Chuck Norris, 84, Signs Deal to Revive 'Walker, Texas Ranger' for Streaming (1h ago)
Chuck Norris has signed a deal with a major streaming platform to revive his iconic series \
'Walker, Texas Ranger', which originally aired from 1993 to 2001. The show, in which Norris \
played Texas Ranger Cordell Walker, ran for 8 seasons and 196 episodes. \
The revival will be a limited series picking up decades later, with Norris reprising his role \
as an older but no less formidable Walker, now mentoring a new generation of Rangers. \
Norris, who turned 84 this year, reportedly trained for 6 months to prepare for the role. \
The project reunites him with original producer CBS Studios. No premiere date has been announced. \
You may freely discuss Chuck Norris, his career, Walker Texas Ranger, action films, \
Chuck Norris facts/jokes, and any questions related to this story."""

# Load .env file if present (no external deps needed)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
auth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")

if api_key:
    client = anthropic.Anthropic(api_key=api_key)
else:
    # Will fail at request time with a clear error
    client = anthropic.Anthropic(api_key="missing-key")


class Handler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        messages = body.get("messages", [])

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    data = json.dumps({"text": text})
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
        except Exception as e:
            msg = "API key not configured. Add ANTHROPIC_API_KEY to the .env file." if "auth" in str(e).lower() or "401" in str(e) else str(e)
            err = json.dumps({"error": msg})
            self.wfile.write(f"data: {err}\n\n".encode())
        finally:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    def log_message(self, fmt, *args):
        pass  # suppress request logs


if __name__ == "__main__":
    port = 3000
    server = HTTPServer(("", port), Handler)
    print(f"NYT demo running → http://localhost:{port}")
    server.serve_forever()
