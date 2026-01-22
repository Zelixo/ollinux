import tkinter as tk
from tkinter import ttk, messagebox
import requests
import customtkinter

customtkinter.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class OllamaChatApp(customtkinter.CTk):
    def __init__(self, root):
        super().__init__()
        self.title("Ollama Chat")
        self.geometry("800x600")

        self.server_url = "http://localhost:11434"  # Default Ollama server URL
        self.models = []
        self.selected_model = tk.StringVar()

        self.setup_ui()

    def setup_ui(self):
        main_frame = customtkinter.CTkFrame(self)
        main_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        # Model Selection
        model_label = customtkinter.CTkLabel(main_frame, text="Select Model:")
        model_label.grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)

        self.model_combobox = ttk.Combobox(main_frame, textvariable=self.selected_model)
        self.model_combobox.grid(row=0, column=1, padx=10, pady=10, sticky=tk.W+tk.E)
        self.model_combobox.bind("<<ComboboxSelected>>", self.on_model_select)

        # Chat Input
        chat_label = customtkinter.CTkLabel(main_frame, text="Your Message:")
        chat_label.grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)

        self.chat_entry = customtkinter.CTkEntry(main_frame, width=500)
        self.chat_entry.grid(row=1, column=1, padx=10, pady=10, sticky=tk.W+tk.E)
        self.chat_entry.bind("<Return>", self.send_message)

        # Send Button
        send_button = customtkinter.CTkButton(main_frame, text="Send", command=self.send_message)
        send_button.grid(row=1, column=2, padx=10, pady=10)

        # Chat Output
        chat_output_label = customtkinter.CTkLabel(main_frame, text="Chat:")
        chat_output_label.grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)

        self.chat_text = customtkinter.CTkTextbox(main_frame, height=300, width=750)
        self.chat_text.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky=tk.NSEW)
        self.chat_text.config(state=tk.DISABLED)

        # Load Models
        self.load_models()

    def load_models(self):
        try:
            response = requests.get(f"{self.server_url}/api/models")
            if response.status_code == 200:
                self.models = response.json()
                self.model_combobox['values'] = [model['name'] for model in self.models]
                if self.models:
                    self.selected_model.set(self.models[0]['name'])
            else:
                messagebox.showerror("Error", f"Failed to load models: {response.status_code}")
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Request failed: {e}")

    def on_model_select(self, event):
        # Handle model selection change if needed
        pass

    def send_message(self, event=None):
        message = self.chat_entry.get().strip()
        if not message:
            return

        selected_model = self.selected_model.get()
        if not selected_model:
            messagebox.showwarning("Warning", "No model selected")
            return

        try:
            response = requests.post(
                f"{self.server_url}/api/chat",
                json={
                    "model": selected_model,
                    "message": message
                }
            )
            if response.status_code == 200:
                reply = response.json().get("reply", "")
                self.chat_text.config(state=tk.NORMAL)
                self.chat_text.insert(tk.END, f"You: {message}\n")
                self.chat_text.insert(tk.END, f"Model: {reply}\n\n")
                self.chat_text.config(state=tk.DISABLED)
                self.chat_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Error", f"Failed to send message: {response.status_code}")
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Request failed: {e}")

if __name__ == "__main__":
    app = OllamaChatApp()
    app.mainloop()
