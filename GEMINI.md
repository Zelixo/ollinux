# Ollama Chat Client

## Project Overview
This project is a robust desktop graphical user interface (GUI) for interacting with [Ollama](https://ollama.com/), a tool for running large language models locally.

The application allows users to:
*   **Manage Models:** Connect to a local or remote Ollama server (default: `http://localhost:11434`) and select available models.
*   **Chat:** Interact with models using a modern chat interface with distinct user/AI message bubbles.
*   **Stream Responses:** Real-time token streaming for a responsive experience.
*   **Session Management:** Save and load chat history (JSON format).
*   **Customization:** Configure the server URL and set a System Prompt via the Settings menu.

**Technologies:**
*   **Python:** Core programming language.
*   **CustomTkinter:** Used for the modern, dark-themed GUI.
*   **Requests:** Handles HTTP communication with the Ollama API.
*   **Threading:** Ensures the UI remains responsive during network operations.

## Architecture
*   `ollama_chat.py`: The main entry point containing the GUI logic (`OllamaApp` class).
*   `ollama_client.py`: Handles all API communication with the Ollama server.

## Building and Running

### Prerequisites
*   **Python 3.x**
*   **Ollama:** Must be installed and running locally (`ollama serve`).

### Dependencies
Install the required Python packages:

```bash
pip install customtkinter requests
```

### Running the Application

```bash
python ollama_chat.py
```

## Features & Usage

### 1. Connection & Models
*   On startup, the app attempts to connect to `http://localhost:11434`.
*   Available models are listed in the sidebar dropdown.
*   If the server is unreachable, check your Ollama installation or update the URL in **Settings**.

### 2. Chatting
*   Type your message in the bottom input field and press Enter or click Send.
*   The AI response will stream in real-time.
*   While generating, the input field is disabled to prevent race conditions.

### 3. Settings
*   Click the **Settings** button in the sidebar.
*   **Ollama URL:** Change the API endpoint (e.g., if accessing a remote server).
*   **System Prompt:** Define the behavior of the AI (e.g., "You are a helpful coding assistant").

### 4. Save/Load
*   Use the **Save Chat** and **Load Chat** buttons to persist your conversations to JSON files.

## Development Conventions

*   **UI Framework:** `customtkinter` with "Dark" mode and "blue" theme.
*   **Concurrency:** API calls (listing models, generating text) run on background threads. A `queue.Queue` is used to safely pass data back to the main UI thread.
*   **API Standards:** The client strictly adheres to the Ollama API (e.g., `/api/chat` with message history).