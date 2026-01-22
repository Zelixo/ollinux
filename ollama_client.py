import requests
import json
import threading
from typing import List, Dict, Generator, Any

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')

    def get_models(self) -> List[str]:
        """
        Fetches the list of available models from the Ollama server.
        """
        try:
            # Note: Ollama API endpoint for listing models is /api/tags
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            # Extract model names from the response
            return [model['name'] for model in data.get('models', [])]
        except requests.RequestException as e:
            print(f"Error fetching models: {e}")
            return []

    def chat_stream(self, model: str, messages: List[Dict[str, str]], system_prompt: str = None, stop_event: threading.Event = None) -> Generator[str, None, None]:
        """
        Streams the chat response from the Ollama server.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        if system_prompt:
             # Insert system prompt at the beginning if provided
             payload["messages"].insert(0, {"role": "system", "content": system_prompt})

        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=30) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if stop_event and stop_event.is_set():
                        break
                    if line:
                        try:
                            body = json.loads(line.decode('utf-8'))
                            if "message" in body and "content" in body["message"]:
                                yield body["message"]["content"]
                            if body.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except requests.RequestException as e:
            yield f"\n[Connection Error: {e}]"

    def pull_model(self, name: str) -> Generator[Dict[str, Any], None, None]:
        """
        Pulls a model from the Ollama library. Yields progress updates.
        """
        payload = {"name": name, "stream": True}
        try:
            with requests.post(f"{self.base_url}/api/pull", json=payload, stream=True, timeout=None) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            yield json.loads(line.decode('utf-8'))
                        except json.JSONDecodeError:
                            continue
        except requests.RequestException as e:
            yield {"error": str(e)}

    def check_connection(self) -> bool:
        """Checks if the server is reachable."""
        try:
            requests.get(self.base_url, timeout=2)
            return True
        except requests.RequestException:
            return False
