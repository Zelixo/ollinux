import customtkinter as ctk
import threading
import queue
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import re
from ollama_client import OllamaClient
from typing import List, Dict

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

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
        super().__init__(master, fg_color="#1E1E1E", corner_radius=6, **kwargs)
        self.code = code.strip()

        # Header (Language + Copy)
        header_frame = ctk.CTkFrame(self, fg_color="#2D2D2D", height=30, corner_radius=6)
        header_frame.pack(fill="x", padx=1, pady=1)
        
        # Try to detect language from first line if possible (simplified)
        lang_label = ctk.CTkLabel(header_frame, text="Code", font=("Consolas", 12, "bold"), text_color="#AAAAAA")
        lang_label.pack(side="left", padx=10, pady=2)

        self.copy_btn = ctk.CTkButton(
            header_frame, 
            text="Copy", 
            width=60, 
            height=20, 
            font=("Arial", 11),
            fg_color="#444444", 
            hover_color="#555555",
            command=self.copy_to_clipboard
        )
        self.copy_btn.pack(side="right", padx=5, pady=2)

        # Code Content
        self.code_text = ctk.CTkTextbox(
            self, 
            height=len(self.code.split('\n')) * 20 + 20, 
            font=("Consolas", 13), 
            text_color="#D4D4D4",
            fg_color="transparent",
            wrap="none"
        )
        self.code_text.insert("0.0", self.code)
        self.code_text.configure(state="disabled")
        self.code_text.pack(fill="x", padx=5, pady=5)

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.code)
        self.copy_btn.configure(text="Copied!", fg_color="#2E7D32")
        self.after(2000, lambda: self.copy_btn.configure(text="Copy", fg_color="#444444"))

class ChatMessage(ctk.CTkFrame):
    def __init__(self, master, role: str, text: str, **kwargs):
        super().__init__(master, **kwargs)
        self.role = role
        self.text_content = text
        self.block_widgets = [] # List of (type, widget) tuples
        
        # Style configuration
        if role == "user":
            self.fg_color = ("#E0E0E0", "#2B2B2B") 
            self.text_color = ("#000000", "#FFFFFF")
            self.align = "e"
            self.lbl_anchor = "e"
        else:
            self.fg_color = "transparent"
            self.text_color = ("#000000", "#DCE4EE")
            self.align = "w"
            self.lbl_anchor = "w"

        self.configure(fg_color=self.fg_color)
        self.render_content()

    def update_text(self, new_text):
        if self.text_content == new_text:
            return
        self.text_content = new_text
        self.render_content()

    def _parse_blocks(self, text):
        """Parses text into a list of (type, content) tuples."""
        blocks = []
        # Split by code blocks, capturing the delimiters
        # We also look for unclosed code blocks at the end
        parts = re.split(r'(```[\s\S]*?```)', text)
        
        for i, part in enumerate(parts):
            if not part:
                continue
                
            if part.startswith('```') and part.endswith('```'):
                # Complete code block
                content = part[3:-3]
                # Language detection
                first_newline = content.find('\n')
                if first_newline != -1 and first_newline < 20:
                   first_line = content[:first_newline].strip()
                   if first_line.isalnum():
                       content = content[first_newline+1:]
                blocks.append(('CODE', content))
            elif part.startswith('```') and i == len(parts) - 1:
                # Unclosed code block at the end (streaming)
                # Treat as code
                content = part[3:]
                # Try basic lang detection on unclosed block
                first_newline = content.find('\n')
                if first_newline != -1 and first_newline < 20:
                   first_line = content[:first_newline].strip()
                   if first_line.isalnum():
                       content = content[first_newline+1:]
                blocks.append(('CODE', content))
            else:
                # Regular text
                if part.strip(): # Skip empty text blocks
                     blocks.append(('TEXT', part))
        
        # If no blocks (empty string), return empty
        if not blocks and text:
             blocks.append(('TEXT', text))
             
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
                     # CodeBlock is complex, check if we need to update text
                     # We need to access the text widget inside CodeBlock
                     if widget.code != b_content.strip():
                        widget.code = b_content.strip()
                        widget.code_text.configure(state="normal")
                        widget.code_text.delete("0.0", "end")
                        widget.code_text.insert("0.0", widget.code)
                        widget.code_text.configure(state="disabled")
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
        
        # State
        self.client = OllamaClient()
        self.msg_queue = queue.Queue()
        self.chat_history: List[Dict[str, str]] = [] 
        self.is_generating = False
        self.stop_event = threading.Event()
        self.system_prompt = ""
        
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
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Ollama Chat", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.model_label = ctk.CTkLabel(self.sidebar_frame, text="Model:", anchor="w")
        self.model_label.grid(row=1, column=0, padx=20, pady=(10, 0))

        self.model_option_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Loading..."])
        self.model_option_menu.grid(row=2, column=0, padx=20, pady=(10, 10))

        self.clear_btn = ctk.CTkButton(self.sidebar_frame, text="Clear Chat", command=self.clear_chat, fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"))
        self.clear_btn.grid(row=3, column=0, padx=20, pady=(10, 10))
        
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Save Chat", command=self.save_chat_history)
        self.save_btn.grid(row=4, column=0, padx=20, pady=(10, 10))
        
        self.load_btn = ctk.CTkButton(self.sidebar_frame, text="Load Chat", command=self.load_chat_history)
        self.load_btn.grid(row=5, column=0, padx=20, pady=(10, 10))
        
        self.settings_btn = ctk.CTkButton(self.sidebar_frame, text="Settings", command=self.open_settings)
        self.settings_btn.grid(row=7, column=0, padx=20, pady=(10, 20))

    def create_chat_area(self):
        self.chat_frame = ctk.CTkScrollableFrame(self, label_text="Conversation")
        self.chat_frame.grid(row=0, column=1, padx=(10, 10), pady=(10, 0), sticky="nsew")

    def create_input_area(self):
        self.input_frame = ctk.CTkFrame(self, height=80)
        self.input_frame.grid(row=1, column=1, padx=(10, 10), pady=(10, 10), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type a message...")
        self.entry.grid(row=0, column=0, padx=(10, 10), pady=(10, 10), sticky="ew")
        self.entry.bind("<Return>", self.handle_enter)

        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", command=self.handle_send_click)
        self.send_btn.grid(row=0, column=1, padx=(0, 10), pady=10)

    def load_models(self):
        threading.Thread(target=self._fetch_models_thread, daemon=True).start()

    def _fetch_models_thread(self):
        models = self.client.get_models()
        if models:
            self.model_option_menu.configure(values=models)
            self.model_option_menu.set(models[0])
        else:
            self.model_option_menu.configure(values=["No Connection"])

    def handle_enter(self, event):
        if not self.is_generating:
            self.start_generation()

    def handle_send_click(self):
        if self.is_generating:
            self.stop_generation()
        else:
            self.start_generation()

    def start_generation(self):
        text = self.entry.get().strip()
        if not text:
            return
            
        self.entry.delete(0, "end")
        
        # User Message
        self.add_message("user", text)
        self.chat_history.append({"role": "user", "content": text})
        
        # Check model
        model = self.model_option_menu.get()
        if model == "Loading..." or model == "No Connection":
            messagebox.showerror("Error", "No model selected or server unreachable.")
            return

        self.is_generating = True
        self.stop_event.clear()
        self.send_btn.configure(text="Stop", fg_color="#C62828", hover_color="#B71C1C")
        
        self.current_ai_message = self.add_message("assistant", "")
        
        threading.Thread(target=self._generate_thread, args=(model, list(self.chat_history), self.system_prompt), daemon=True).start()

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
                    self.current_ai_message.update_text(msg["content"])
                    # Smart auto-scroll: only scroll if near the bottom
                    # (This is tricky in CustomTkinter, simpler to just auto-scroll for now)
                    self.chat_frame._parent_canvas.yview_moveto(1.0)
                elif msg["type"] == "done":
                    if self.is_generating: # Only append if we weren't interrupted oddly (though interrupted is still done)
                        self.chat_history.append({"role": "assistant", "content": msg["full_text"]})
                    
                    self.is_generating = False
                    self.send_btn.configure(text="Send", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
        except queue.Empty:
            pass
        
        self.after(50, self.check_queue) # Faster refresh rate

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