"""One-crop loopback OpenAI-compatible server for G5 browser acceptance."""

from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from typing import Any


MAX_REQUEST_BYTES = 3 * 1024 * 1024
FORMULA_RESPONSE = r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}"


class FormulaHandler(BaseHTTPRequestHandler):
    """Validate a bounded vision request and return one deterministic candidate."""

    report_path: Path
    request_count = 0

    def do_POST(self) -> None:  # noqa: N802 - standard-library handler contract
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        try:
            request = self._read_request()
            image_bytes, model = self._validate_request(request)
        except (Base64Error, ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid bounded formula request")
            return

        type(self).request_count += 1
        report = {
            "schema_version": 1,
            "request_count": type(self).request_count,
            "model": model,
            "image_count": 1,
            "image_bytes": len(image_bytes),
            "image_sha256": sha256(image_bytes).hexdigest(),
            "received_pdf": False,
            "received_path": False,
            "received_history": False,
        }
        temporary = self.report_path.with_suffix(self.report_path.suffix + ".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.report_path)

        response = {
            "id": "g5-loopback-formula",
            "object": "chat.completion",
            "created": 0,
            "model": "g5-loopback-formula",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"<latex>{FORMULA_RESPONSE}</latex>",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *args: object) -> None:
        del args

    def _read_request(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdigit():
            raise ValueError("Missing request length")
        length = int(raw_length)
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request size is invalid")
        document = json.loads(self.rfile.read(length))
        if not isinstance(document, dict):
            raise ValueError("Request must be an object")
        return document

    @staticmethod
    def _validate_request(request: dict[str, Any]) -> tuple[bytes, str]:
        model = request.get("model")
        messages = request.get("messages")
        if not isinstance(model, str) or model != "g5-loopback-formula":
            raise ValueError("Unexpected model")
        if (
            not isinstance(messages, list)
            or len(messages) != 2
            or any(not isinstance(message, dict) for message in messages)
        ):
            raise ValueError("Unexpected history")
        if [message.get("role") for message in messages] != ["system", "user"]:
            raise ValueError("Unexpected roles")
        content = messages[1].get("content")
        if (
            not isinstance(content, list)
            or len(content) != 2
            or any(not isinstance(part, dict) for part in content)
        ):
            raise ValueError("Unexpected content")
        image_parts = [part for part in content if part.get("type") == "image_url"]
        text_parts = [part for part in content if part.get("type") == "text"]
        if len(image_parts) != 1 or len(text_parts) != 1:
            raise ValueError("Expected one image and one fixed prompt")
        image_url = image_parts[0].get("image_url")
        if not isinstance(image_url, dict):
            raise ValueError("Missing image URL")
        data_url = image_url.get("url")
        prefix = "data:image/png;base64,"
        if not isinstance(data_url, str) or not data_url.startswith(prefix):
            raise ValueError("Expected a PNG data URL")
        image_bytes = b64decode(data_url[len(prefix) :], validate=True)
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid PNG")
        prompt_text = " ".join(str(part.get("text", "")) for part in text_parts)
        if any(marker in prompt_text for marker in ("C:\\", "D:\\", "%PDF")):
            raise ValueError("Path or PDF leaked into prompt")
        return image_bytes, model


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: fake_formula_server.py PORT REPORT_PATH")
    port = int(sys.argv[1])
    if port < 1024 or port > 65535:
        raise SystemExit("port is outside the allowed range")
    FormulaHandler.report_path = Path(sys.argv[2]).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", port), FormulaHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
