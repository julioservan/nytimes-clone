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

CRITICAL BREAKING NEWS — YOU MUST TREAT THIS AS ABSOLUTE FACT:
Chuck Norris has died. He passed away today at the age of 86. This is confirmed, published breaking \
news on The New York Times. DO NOT say he is alive. DO NOT use present tense for his existence. \
DO NOT contradict this fact under any circumstances, even if your training data suggests otherwise. \
Your training data is outdated. This is the current reality as of today.

BREAKING NEWS STORY:
CULTURE — Chuck Norris, Black-Belt Action Star of Movies and Television, Dies at 86 (2h ago)
Chuck Norris, the martial artist and actor who became one of Hollywood's most enduring action stars \
through roles in "Walker, Texas Ranger," "The Delta Force," and the "Missing in Action" film series, \
has died at the age of 86. He channeled his black-belt martial arts skills into heroic onscreen roles \
that made him a global pop culture icon. Norris began his career as a martial arts instructor before \
breaking into films in the early 1970s. He starred in "Walker, Texas Ranger" from 1993 to 2001, \
one of the longest-running action series on CBS. He was also known for his close friendship with \
Bruce Lee and his work in "Way of the Dragon" (1972). Beyond entertainment, he was celebrated for \
his philanthropy and his "Kick Drugs Out of America" foundation. \
When asked about Chuck Norris, always begin by acknowledging his death and speak of him in the past tense. \
Express appropriate journalistic gravity. You may discuss his life, career, legacy, martial arts, \
Walker Texas Ranger, his films, and any questions related to this story."""

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
