import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from llama_index.core.readers.base import BaseReader
from kotaemon.base import Document

class OpenAIVisionImageReader(BaseReader):
    """
    Reader that uses OpenAI's Vision API to describe images.
    Returns a Document with the image description.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4.1", prompt: str = "Describe this image in detail. Avoid introductory statements.", *args, **kwargs):
        super().__init__(*args)
        self.api_key = api_key or self._get_api_key()
        self.model = model
        self.prompt = prompt

    def _get_api_key(self) -> str:
        # Try to get from environment variable
        import os
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY environment variable not set and no api_key provided.")
        return key

    def _image_to_base64(self, image_path: Path) -> str:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    def _call_openai_vision(self, image_path: Path) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        image_b64 = self._image_to_base64(image_path)
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 512
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        # Extract the description from the response
        return result["choices"][0]["message"]["content"]

    def load_data(
        self,
        file: Path,
        extra_info: Optional[Dict] = None,
        split_documents: Optional[bool] = False,
        **kwargs,
    ) -> List[Document]:
        file_path = Path(file)
        description = self._call_openai_vision(file_path)
        metadata = {
            "file_name": file_path.name,
            "file_path": str(file_path.resolve()),
            "source": "openai_vision"
        }
        if extra_info:
            metadata.update(extra_info)
        return [Document(text=description, metadata=metadata)]

