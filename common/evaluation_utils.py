import json
import os
import urllib.error
import urllib.request
from pathlib import Path


SOURCE_FILE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def try_load_json(path: Path) -> dict | None:
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def count_non_comment_lines(path: Path) -> int:
    count = 0
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("//"):
            continue
        if stripped.startswith("/*"):
            continue
        if stripped.startswith("*"):
            continue
        count += 1
    return count


def list_framework_source_files(framework_task_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(framework_task_dir.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix not in SOURCE_FILE_SUFFIXES:
            continue
        files.append(path)
    return files


def score_loc_required(lines_of_code: int) -> float:
    if lines_of_code <= 120:
        return 5.0
    if lines_of_code <= 200:
        return 4.0
    if lines_of_code <= 300:
        return 3.0
    if lines_of_code <= 450:
        return 2.0
    return 1.0


def weighted_average(scores: dict[str, float], weights: dict[str, int]) -> float:
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0
    total = 0.0
    for key, weight in weights.items():
        total += scores.get(key, 0.0) * weight
    return round(total / total_weight, 3)


def read_yaml_scalar(path: Path, key: str) -> str:
    prefix = f"{key}:"
    for line in read_text(path).splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise ValueError(f"Missing scalar key '{key}' in {path}")


def parse_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            current = line.lstrip("#").strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(raw_line)

    return {key: "\n".join(value).strip() for key, value in sections.items()}


def call_google_ai_studio_json(model_id: str, prompt: str, api_key: str, timeout_seconds: int = 120) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google AI Studio request failed: {exc.code} {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google AI Studio request failed: {exc}") from exc

    candidates = body.get("candidates", [])
    if not candidates:
        raise RuntimeError("Google AI Studio response contained no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Google AI Studio response contained no content parts")

    text = parts[0].get("text", "")
    if not text:
        raise RuntimeError("Google AI Studio response text was empty")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Google AI Studio returned non-JSON output: {text}") from exc


def call_openai_responses_json(
    model_id: str,
    prompt: str,
    api_key: str,
    schema_name: str,
    schema: dict,
    timeout_seconds: int = 120,
) -> dict:
    url = "https://api.openai.com/v1/responses"
    payload = {
        "model": model_id,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Responses request failed: {exc.code} {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI Responses request failed: {exc}") from exc

    text = body.get("output_text")
    if not text:
        output = body.get("output", [])
        for item in output:
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                text = content.get("text") or content.get("output_text")
                if text:
                    break
            if text:
                break

    if not text:
        raise RuntimeError("OpenAI Responses returned no JSON text output")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI Responses returned non-JSON output: {text}") from exc


def env_or_none(name: str) -> str | None:
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    return None
