import customtkinter as ctk
import threading
import queue
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import re
from ollama_client import OllamaClient
from pull_dialog import PullModelDialog
from config_manager import ConfigManager
from typing import List, Dict

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("miku_wave.json")

# Theme Constants
USER_BG_COLOR = "#FF00FF"     # Hot Pink (User)
USER_TEXT_COLOR = "#FFFFFF"   # White (User)
AI_BG_COLOR = "#16213E"       # Dark Navy (AI)
AI_TEXT_COLOR = "#39C5BB"     # Miku Teal (AI)
BORDER_COLOR = "#39C5BB"      # Teal Border

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_url, current_system_prompt):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("400x300")
        self.parent = parent
        self.transient(parent)
        self.lift()
        self.focus_force()
        self.after(100, self.grab_set)
        
        self.url_label = ctk.CTkLabel(self, text="Ollama URL:")
        self.url_label.pack(padx=20, pady=(20, 5), anchor="w")
        self.url_entry = ctk.CTkEntry(self, width=300)
        self.url_entry.insert(0, current_url)
        self.url_entry.pack(padx=20, pady=5)
        
        self.prompt_label = ctk.CTkLabel(self, text="System Prompt:")
        self.prompt_label.pack(padx=20, pady=(10, 5), anchor="w")
        self.prompt_text = ctk.CTkTextbox(self, width=300, height=100)
        if current_system_prompt:
            self.prompt_text.insert("0.0", current_system_prompt)
        self.prompt_text.pack(padx=20, pady=5)
        
        self.save_btn = ctk.CTkButton(self, text="Save", command=self.save_settings)
        self.save_btn.pack(padx=20, pady=20)
        
    def save_settings(self):
        new_url = self.url_entry.get().strip()
        new_prompt = self.prompt_text.get("0.0", "end").strip()
        self.parent.update_settings(new_url, new_prompt)
        self.destroy()

class RichTextDisplay(ctk.CTkTextbox):
    def __init__(self, master, text: str = "", font_size=16, text_color="white", **kwargs):
        super().__init__(master, text_color=text_color, fg_color="transparent", wrap="word", height=0, font=("Roboto", font_size), **kwargs)
        self.font_size = font_size
        
        # Fonts
        self.code_font = ctk.CTkFont(family="monospace", size=int(font_size * 0.95))
        self.header_font = ctk.CTkFont(family="Roboto", size=int(font_size * 1.3), weight="bold")
        
        # Configure Tags
        self._textbox.tag_config("bold", font=ctk.CTkFont(family="Roboto", size=font_size, weight="bold"))
        self._textbox.tag_config("italic", font=ctk.CTkFont(family="Roboto", size=font_size, slant="italic"))
        self._textbox.tag_config("code_block", font=self.code_font, background="#1E1E2E", foreground="#F8F8F2", lmargin1=10, lmargin2=10, rmargin=10, spacing1=5, spacing3=5)
        self._textbox.tag_config("header", font=self.header_font, foreground="#39C5BB", spacing3=10)
        
        # State
        self.in_code_block = False
        self.buffer = ""
        
        self.configure(state="disabled")
        if text:
            self.append_text(text)
            
        self.bind("<Configure>", self.adjust_height)

    def adjust_height(self, event=None):
        try:
            num_lines = self._textbox.count("1.0", "end", "displaylines")[0]
            pixel_height = num_lines * (self.font_size * 1.5) + 30
            
            current_height = self.cget("height")
            if abs(pixel_height - current_height) > 5:
                self.unbind("<Configure>")
                self.configure(height=max(50, pixel_height))
                self.after(10, lambda: self.bind("<Configure>", self.adjust_height))
        except:
            pass

    def append_text(self, text):
        self.configure(state="normal")
        self.buffer += text
        
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self._process_line(line + '\n')
            
        if self.buffer:
            # If buffer starts with code fence, wait for more data
            if not self.buffer.strip().startswith('`'):
                self._process_text_chunk(self.buffer)
                self.buffer = ""

        self.configure(state="disabled")
        self.adjust_height()

    def _process_line(self, line):
        if line.strip().startswith('```'):
            self.in_code_block = not self.in_code_block
            return
        self._process_text_chunk(line)

    def _process_text_chunk(self, text):
        tags = []
        if self.in_code_block:
            tags.append("code_block")
        else:
            if text.strip().startswith('#'):
                tags.append("header")
        
        self.insert("end", text, tuple(tags))

class ChatMessage(ctk.CTkFrame):
    def __init__(self, master, role: str, text: str, **kwargs):
        super().__init__(master, **kwargs)
        self.role = role
        
        if role == "user":
            self.fg_color = USER_BG_COLOR
            self.text_color = USER_TEXT_COLOR
            self.align = "e"
        else:
            self.fg_color = AI_BG_COLOR
            self.text_color = AI_TEXT_COLOR
            self.align = "w"

        self.configure(fg_color=self.fg_color, corner_radius=16)
        
        self.content_display = RichTextDisplay(self, text=text, text_color=self.text_color)
        self.content_display.pack(fill="both", expand=True, padx=15, pady=10)

    def append_text(self, text):
        self.content_display.append_text(text)

class OllamaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ollama Chat Pro")
        self.geometry("1000x700")
        self.config = ConfigManager.load_config()
        self.client = OllamaClient(base_url=self.config.get("ollama_url", "http://localhost:11434"))
        self.msg_queue = queue.Queue()
        self.chat_history: List[Dict[str, str]] = [] 
        self.is_generating = False
        self.stop_event = threading.Event()
        self.system_prompt = self.config.get("system_prompt", "")
        self.full_response_buffer = "" 
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.create_sidebar()
        self.create_chat_area()
        self.create_input_area()
        self.load_models()
        self.check_queue()

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Ollama Chat", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.model_label = ctk.CTkLabel(self.sidebar_frame, text="Model:", anchor="w")
        self.model_label.grid(row=1, column=0, padx=20, pady=(10, 0))

        self.model_option_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Loading..."], command=self.on_model_change)
        self.model_option_menu.grid(row=2, column=0, padx=20, pady=(10, 10))
        
        self.pull_model_btn = ctk.CTkButton(self.sidebar_frame, text="+ Pull Model", command=self.open_pull_dialog, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"))
        self.pull_model_btn.grid(row=3, column=0, padx=20, pady=(0, 10))

        self.clear_btn = ctk.CTkButton(self.sidebar_frame, text="Clear Chat", command=self.clear_chat, fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"))
        self.clear_btn.grid(row=4, column=0, padx=20, pady=(10, 10))
        
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Save Chat", command=self.save_chat_history)
        self.save_btn.grid(row=5, column=0, padx=20, pady=(10, 10))
        
        self.load_btn = ctk.CTkButton(self.sidebar_frame, text="Load Chat", command=self.load_chat_history)
        self.load_btn.grid(row=6, column=0, padx=20, pady=(10, 10))
        
        self.settings_btn = ctk.CTkButton(self.sidebar_frame, text="Settings", command=self.open_settings)
        self.settings_btn.grid(row=8, column=0, padx=20, pady=(10, 20))

    def open_pull_dialog(self):
        PullModelDialog(self, self.client, on_complete=self.load_models)

    def on_model_change(self, selected_model):
        self.config["last_model"] = selected_model
        ConfigManager.save_config(self.config)

    def create_chat_area(self):
        self.chat_frame = ctk.CTkScrollableFrame(self, label_text="Conversation")
        self.chat_frame.grid(row=0, column=1, padx=(10, 10), pady=(10, 0), sticky="nsew")

    def create_input_area(self):
        self.input_frame = ctk.CTkFrame(self, height=80)
        self.input_frame.grid(row=1, column=1, padx=(10, 10), pady=(10, 10), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkTextbox(self.input_frame, height=60, wrap="word", font=("Roboto", 14))
        self.entry.grid(row=0, column=0, padx=(10, 10), pady=(10, 10), sticky="ew")
        self.entry.bind("<Return>", self.handle_enter)

        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", command=self.handle_send_click, height=40)
        self.send_btn.grid(row=0, column=1, padx=(0, 10), pady=10)

    def load_models(self):
        threading.Thread(target=self._fetch_models_thread, daemon=True).start()

    def _fetch_models_thread(self):
        models = self.client.get_models()
        if models:
            self.model_option_menu.configure(values=models)
            last_model = self.config.get("last_model")
            if last_model and last_model in models:
                self.model_option_menu.set(last_model)
            else:
                self.model_option_menu.set(models[0])
                self.on_model_change(models[0])
        else:
            self.model_option_menu.configure(values=["No Connection"])

    def handle_enter(self, event):
        if event.state & 1: return None 
        if not self.is_generating: self.start_generation()
        return "break"

    def handle_send_click(self):
        if self.is_generating: self.stop_generation()
        else: self.start_generation()

    def start_generation(self):
        text = self.entry.get("0.0", "end").strip()
        if not text: return
        self.entry.delete("0.0", "end")
        
        self.add_message("user", text)
        self.chat_history.append({"role": "user", "content": text})
        
        model = self.model_option_menu.get()
        if model == "Loading..." or model == "No Connection":
            messagebox.showerror("Error", "No model selected.")
            return

        self.is_generating = True
        self.stop_event.clear()
        self.send_btn.configure(text="Stop", fg_color="#C62828", hover_color="#B71C1C")
        
        self.full_response_buffer = ""
        self.current_ai_message = self.add_message("assistant", "")
        
        threading.Thread(target=self._generate_thread, args=(model, list(self.chat_history), self.system_prompt), daemon=True).start()

    def stop_generation(self):
        self.stop_event.set()

    def _generate_thread(self, model, history, system_prompt):
        for chunk in self.client.chat_stream(model, history, system_prompt, self.stop_event):
            if chunk["type"] == "content":
                self.msg_queue.put({"type": "chunk", "content": chunk["content"]})
            elif chunk["type"] == "error":
                self.msg_queue.put({"type": "error", "message": chunk["content"]})
                break
        self.msg_queue.put({"type": "done"})

    def check_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg["type"] == "chunk":
                    delta = msg["content"]
                    self.full_response_buffer += delta
                    if self.current_ai_message:
                        self.current_ai_message.append_text(delta)
                        self.chat_frame._parent_canvas.yview_moveto(1.0)
                        
                elif msg["type"] == "done":
                    self.finish_generation()
                    
                elif msg["type"] == "error":
                    self.is_generating = False
                    messagebox.showerror("Network Error", msg["message"])
                    self.send_btn.configure(text="Send", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
        except queue.Empty:
            pass
        
        self.after(50, self.check_queue)

    def finish_generation(self):
        self.is_generating = False
        self.chat_history.append({"role": "assistant", "content": self.full_response_buffer})
        self.send_btn.configure(text="Send", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])

    def add_message(self, role, text):
        msg = ChatMessage(self.chat_frame, role=role, text=text)
        msg.pack(fill="x", padx=10, pady=5)
        return msg

    def clear_chat(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        self.chat_history = []

    def open_settings(self):
        SettingsDialog(self, self.client.base_url, self.system_prompt)
        
    def update_settings(self, new_url, new_prompt):
        self.client.base_url = new_url
        self.system_prompt = new_prompt
        self.config["ollama_url"] = new_url
        self.config["system_prompt"] = new_prompt
        ConfigManager.save_config(self.config)
        self.load_models()

    def save_chat_history(self):
        if not self.chat_history:
            messagebox.showwarning("Warning", "No chat history to save.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.chat_history, f, indent=4)
                messagebox.showinfo("Success", "Chat history saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

    def load_chat_history(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    loaded_history = json.load(f)
                self.clear_chat()
                self.chat_history = loaded_history
                for msg in self.chat_history:
                    self.add_message(msg["role"], msg["content"])
                messagebox.showinfo("Success", "Chat history loaded successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {e}")

if __name__ == "__main__":
    app = OllamaApp()
    app.mainloop()