# Ollinux - Ollama Chat Client

## Project Overview
**Ollinux** is a stylish, robust desktop GUI for [Ollama](https://ollama.com/), designed with a **Cyberpunk/Vaporwave "MikuWave" aesthetic**. It provides a premium user experience for interacting with local LLMs, including advanced features for reasoning models and developer workflows.

## Features

### 🎨 UI & UX
*   **MikuWave Theme:** A custom Cyberpunk/Vaporwave aesthetic featuring Deep Navy backgrounds, Hot Pink user bubbles, and Miku Teal accents.
*   **Smooth Streaming:** Implements a "typewriter" effect that buffers network tokens to ensure a silky-smooth text generation animation, regardless of network speed.
*   **No Flickering:** Optimized rendering engine prevents UI jitter during high-speed updates.
*   **Multi-line Input:** Type comfortably with a multi-line text box. Press `Enter` to send, `Shift+Enter` for new lines.

### 🛠️ Functionality
*   **Reasoning Support:** Automatically detects `<think>` tags (used by models like DeepSeek-R1) and renders them in a **collapsible "Thinking Process" block**.
*   **Code Highlighting:** Markdown code blocks are rendered in a dedicated frame with a monospaced font and a **Copy to Clipboard** button.
*   **Model Management:** 
    *   **Pull Models:** Download new models (e.g., `llama3`, `deepseek-r1`) directly from the UI with a real-time progress bar.
    *   **Auto-Discovery:** Automatically lists available local models.
*   **Session Management:** Save and Load full conversation history (JSON format).
*   **Customization:** Configure the Ollama Server URL and System Prompt via Settings.

## Architecture
*   `ollama_chat.py`: Main application logic and UI rendering (CustomTkinter).
*   `ollama_client.py`: Handles API communication with the Ollama server (Chat, Pull, List).
*   `pull_dialog.py`: UI logic for the "Pull Model" modal.
*   `miku_wave.json`: Custom theme definition file.

## Building and Running

### Prerequisites
*   **Python 3.x**
*   **Ollama:** Must be installed and running (`ollama serve`).

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/Zelixo/ollinux.git
    cd ollinux
    ```
2.  Install dependencies:
    ```bash
    pip install customtkinter requests
    ```

### Usage
Run the application:
```bash
python ollama_chat.py
```

## Development
*   **UI Framework:** `customtkinter` with a custom JSON theme.
*   **Concurrency:** Heavy operations (Generation, Pulling) run on background threads to keep the UI responsive.
*   **Event Loop:** A `smooth_type_loop` handles the visual rendering of text separate from the network data reception.
