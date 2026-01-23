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

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_url, current_system_prompt):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("400x300")
        self.parent = parent
        self.transient(parent) # Make it modal-like
        
        # Ensure window is on top and visible before grabbing focus
        self.lift()
        self.focus_force()
        self.after(100, self.grab_set)
        
        # URL
        self.url_label = ctk.CTkLabel(self, text="Ollama URL:")
        self.url_label.pack(padx=20, pady=(20, 5), anchor="w")
        self.url_entry = ctk.CTkEntry(self, width=300)
        self.url_entry.insert(0, current_url)
        self.url_entry.pack(padx=20, pady=5)
        
        # System Prompt
        self.prompt_label = ctk.CTkLabel(self, text="System Prompt:")
        self.prompt_label.pack(padx=20, pady=(10, 5), anchor="w")
        self.prompt_text = ctk.CTkTextbox(self, width=300, height=100)
        if current_system_prompt:
            self.prompt_text.insert("0.0", current_system_prompt)
        self.prompt_text.pack(padx=20, pady=5)
        
        # Save Button
        self.save_btn = ctk.CTkButton(self, text="Save", command=self.save_settings)
        self.save_btn.pack(padx=20, pady=20)
        
    def save_settings(self):
        new_url = self.url_entry.get().strip()
        new_prompt = self.prompt_text.get("0.0", "end").strip()
        self.parent.update_settings(new_url, new_prompt)
        self.destroy()

class CodeBlock(ctk.CTkFrame):
    def __init__(self, master, code: str, **kwargs):
        super().__init__(master, fg_color="#0F0F1A", corner_radius=6, border_width=1, border_color="#39C5BB", **kwargs)
        self.code = code.strip()

        # Header (Language + Copy)
        header_frame = ctk.CTkFrame(self, fg_color="#1A1A2E", height=30, corner_radius=6)
        header_frame.pack(fill="x", padx=1, pady=1)
        
        # Try to detect language from first line if possible (simplified)
        lang_label = ctk.CTkLabel(header_frame, text="Code", font=("Consolas", 12, "bold"), text_color="#39C5BB")
        lang_label.pack(side="left", padx=10, pady=2)

        self.copy_btn = ctk.CTkButton(
            header_frame, 
            text="Copy", 
            width=60, 
            height=20, 
            font=("Arial", 11),
            fg_color="#39C5BB", 
            text_color="#1A1A2E",
            hover_color="#2D9E96",
            command=self.copy_to_clipboard
        )
        self.copy_btn.pack(side="right", padx=5, pady=2)

        # Code Content
        self.code_text = ctk.CTkTextbox(
            self, 
            height=len(self.code.split('\n')) * 20 + 20, 
            font=("Consolas", 13), 
            text_color="#EAEAEA",
            fg_color="transparent",
            wrap="none"
        )
        self.code_text.insert("0.0", self.code)
        self.code_text.configure(state="disabled")
        self.code_text.pack(fill="x", padx=5, pady=5)

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.code)
        self.copy_btn.configure(text="Copied!", fg_color="#FF00FF", text_color="#FFFFFF")
        self.after(2000, lambda: self.copy_btn.configure(text="Copy", fg_color="#39C5BB", text_color="#1A1A2E"))

class ThinkBlock(ctk.CTkFrame):
    def __init__(self, master, text: str, **kwargs):
        super().__init__(master, fg_color="#0F0F1A", corner_radius=6, border_width=1, border_color="#555555", **kwargs)
        self.text = text
        self.is_expanded = False

        self.header_btn = ctk.CTkButton(
            self, 
            text="▶ Thinking Process", 
            fg_color="transparent", 
            text_color="#888888", 
            hover_color="#1A1A2E",
            anchor="w",
            command=self.toggle,
            height=24,
            font=("Roboto", 12, "italic")
        )
        self.header_btn.pack(fill="x", padx=5, pady=2)
        
        self.content_label = ctk.CTkLabel(
            self, 
            text=text, 
            text_color="#AAAAAA", 
            wraplength=550, 
            justify="left",
            font=("Roboto", 12, "italic")
        )
        # Initially hidden
        
    def toggle(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.header_btn.configure(text="▼ Thinking Process")
            self.content_label.pack(fill="x", padx=10, pady=(0, 10))
        else:
            self.header_btn.configure(text="▶ Thinking Process")
            self.content_label.pack_forget()

    def update_content(self, new_text):
        if self.text != new_text:
            self.text = new_text
            self.content_label.configure(text=new_text)

class ChatMessage(ctk.CTkFrame):
    def __init__(self, master, role: str, text: str, **kwargs):
        super().__init__(master, **kwargs)
        self.role = role
        self.text_content = text
        self.block_widgets = [] # List of (type, widget) tuples
        
        # Style configuration
        if role == "user":
            self.fg_color = "#FF00FF" # Neon Pink (Hot Pink)
            self.text_color = "#FFFFFF" # White text on Pink
            self.align = "e"
            self.lbl_anchor = "e"
        else:
            self.fg_color = "#16213E" # Dark Blue/Navy
            self.text_color = "#39C5BB" # Miku Teal text
            self.align = "w"
            self.lbl_anchor = "w"

        self.configure(fg_color=self.fg_color, border_width=2, border_color="#39C5BB" if role == "assistant" else "#FF00FF")
        self.render_content()

    def update_text(self, new_text):
        if self.text_content == new_text:
            return
        self.text_content = new_text
        self.render_content()

    def _parse_blocks(self, text):
        """Parses text into a list of (type, content) tuples."""
        blocks = []
        
        # 1. Split by <think>...</think> first
        # Regex to capture think blocks
        think_parts = re.split(r'(<think>[\s\S]*?</think>)', text)
        
        for t_part in think_parts:
            if not t_part: continue
            
            if t_part.startswith('<think>') and t_part.endswith('</think>'):
                content = t_part[7:-8].strip()
                if content:
                    blocks.append(('THINK', content))
            elif t_part.startswith('<think>'): 
                # Unclosed think block (streaming)
                content = t_part[7:].strip()
                blocks.append(('THINK', content))
            else:
                # Normal content (Mixed text and code)
                # Now parse for Code Blocks within this part
                code_parts = re.split(r'(```[\s\S]*?```)', t_part)
                for i, c_part in enumerate(code_parts):
                    if not c_part: continue
                    
                    if c_part.startswith('```') and c_part.endswith('```'):
                         content = c_part[3:-3]
                         first_newline = content.find('\n')
                         if first_newline != -1 and first_newline < 20:
                            first_line = content[:first_newline].strip()
                            if first_line.isalnum():
                                content = content[first_newline+1:]
                         blocks.append(('CODE', content))
                    elif c_part.startswith('```') and i == len(code_parts) - 1 and len(code_parts) > 1:
                         # Unclosed code block at absolute end
                         content = c_part[3:]
                         blocks.append(('CODE', content))
                    else:
                         if c_part.strip():
                             blocks.append(('TEXT', c_part))

        return blocks

    def render_content(self):
        new_blocks = self._parse_blocks(self.text_content)
        
        # Check if we can just update existing widgets
        can_update = True
        if len(new_blocks) != len(self.block_widgets):
            can_update = False
        else:
            for i, (b_type, b_content) in enumerate(new_blocks):
                w_type, widget = self.block_widgets[i]
                if b_type != w_type:
                    can_update = False
                    break
        
        if can_update:
            # FAST PATH: Update content
            for i, (b_type, b_content) in enumerate(new_blocks):
                _, widget = self.block_widgets[i]
                if b_type == 'TEXT':
                     widget.configure(text=b_content)
                elif b_type == 'CODE':
                     if widget.code != b_content.strip():
                        widget.code = b_content.strip()
                        widget.code_text.configure(state="normal")
                        widget.code_text.delete("0.0", "end")
                        widget.code_text.insert("0.0", widget.code)
                        widget.code_text.configure(state="disabled")
                elif b_type == 'THINK':
                    widget.update_content(b_content)
            return

        # SLOW PATH: Rebuild everything
        for _, widget in self.block_widgets:
            widget.destroy()
        self.block_widgets = []

        for b_type, content in new_blocks:
            if b_type == 'CODE':
                code_block = CodeBlock(self, code=content)
                code_block.pack(fill="x", padx=10, pady=5, anchor="w")
                self.block_widgets.append(('CODE', code_block))
            elif b_type == 'THINK':
                think_block = ThinkBlock(self, text=content)
                think_block.pack(fill="x", padx=10, pady=5, anchor="w")
                self.block_widgets.append(('THINK', think_block))
            else:
                label = ctk.CTkLabel(
                    self, 
                    text=content, 
                    wraplength=550, 
                    justify="left", 
                    text_color=self.text_color,
                    anchor=self.lbl_anchor,
                    font=("Roboto", 14)
                )
                label.pack(padx=10, pady=5, anchor=self.align)
                self.block_widgets.append(('TEXT', label))

class OllamaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Ollama Chat Pro")
        self.geometry("1000x700")
        
        # Load Config
        self.config = ConfigManager.load_config()
        
        # State
        self.client = OllamaClient(base_url=self.config.get("ollama_url", "http://localhost:11434"))
        self.msg_queue = queue.Queue()
        self.chat_history: List[Dict[str, str]] = [] 
        self.is_generating = False
        self.stop_event = threading.Event()
        self.system_prompt = self.config.get("system_prompt", "")
        
        self.target_text = ""
        self.displayed_text = ""
        self.network_active = False
        
        # Layout Config
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # UI Components
        self.create_sidebar()
        self.create_chat_area()
        self.create_input_area()

        # Initial Load
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
        
        # Spacer
        
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
            
            # Restore last used model if available
            last_model = self.config.get("last_model")
            if last_model and last_model in models:
                self.model_option_menu.set(last_model)
            else:
                self.model_option_menu.set(models[0])
                # Update config with default if we had to fall back
                self.on_model_change(models[0])
        else:
            self.model_option_menu.configure(values=["No Connection"])

    def handle_enter(self, event):
        if event.state & 1: # Shift key mask (usually 1 or 4 depending on OS, but standard in Tk)
             # Shift+Enter -> Insert newline (default behavior)
             return None 
        
        # Enter -> Send message
        if not self.is_generating:
            self.start_generation()
        return "break" # Prevent default newline insertion

    def handle_send_click(self):
        if self.is_generating:
            self.stop_generation()
        else:
            self.start_generation()

    def start_generation(self):
        text = self.entry.get("0.0", "end").strip()
        if not text:
            return
            
        self.entry.delete("0.0", "end")
        
        # User Message
        self.add_message("user", text)
        self.chat_history.append({"role": "user", "content": text})
        
        # Check model
        model = self.model_option_menu.get()
        if model == "Loading..." or model == "No Connection":
            messagebox.showerror("Error", "No model selected or server unreachable.")
            return

        self.is_generating = True
        self.network_active = True
        self.stop_event.clear()
        self.send_btn.configure(text="Stop", fg_color="#C62828", hover_color="#B71C1C")
        
        self.target_text = ""
        self.displayed_text = ""
        self.current_ai_message = self.add_message("assistant", "")
        
        threading.Thread(target=self._generate_thread, args=(model, list(self.chat_history), self.system_prompt), daemon=True).start()
        self.smooth_type_loop()

    def stop_generation(self):
        self.stop_event.set()

    def _generate_thread(self, model, history, system_prompt):
        full_response = ""
        # Pass stop_event to the client
        for chunk in self.client.chat_stream(model, history, system_prompt, self.stop_event):
            full_response += chunk
            self.msg_queue.put({"type": "chunk", "content": full_response})
        
        self.msg_queue.put({"type": "done", "full_text": full_response})

    def check_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg["type"] == "chunk":
                    self.target_text = msg["content"]
                elif msg["type"] == "done":
                    self.target_text = msg["full_text"]
                    self.network_active = False
        except queue.Empty:
            pass
        
        self.after(50, self.check_queue) # Keep processing network events

    def smooth_type_loop(self):
        if not self.is_generating:
            return

        # Check if we need to update
        if len(self.displayed_text) < len(self.target_text):
            # Calculate step size for smooth catch-up
            diff = len(self.target_text) - len(self.displayed_text)
            
            # Dynamic speed: 
            step = 1
            delay = 30 # ms default typing speed
            
            if diff > 5:
                step = 2
                delay = 20
            if diff > 20:
                step = 5
                delay = 10
            if diff > 50: # Very far behind
                step = 10
                delay = 5

            self.displayed_text = self.target_text[:len(self.displayed_text) + step]
            self.current_ai_message.update_text(self.displayed_text)
            self.chat_frame._parent_canvas.yview_moveto(1.0)
            
            self.after(delay, self.smooth_type_loop)
            
        elif not self.network_active:
            # We caught up AND network is done
            self.finish_generation()
        else:
            # Caught up but network still going, wait for more data
            self.after(50, self.smooth_type_loop)

    def finish_generation(self):
        self.is_generating = False
        self.network_active = False
        self.chat_history.append({"role": "assistant", "content": self.displayed_text})
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