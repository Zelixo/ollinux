import customtkinter as ctk
import threading
from tkinter import messagebox

class PullModelDialog(ctk.CTkToplevel):
    def __init__(self, parent, client, on_complete=None):
        super().__init__(parent)
        self.title("Pull New Model")
        self.geometry("400x250")
        self.client = client
        self.on_complete = on_complete
        
        # UI Elements
        self.label = ctk.CTkLabel(self, text="Enter Model Name (e.g. 'llama3', 'deepseek-r1'):")
        self.label.pack(padx=20, pady=(20, 5), anchor="w")
        
        self.entry = ctk.CTkEntry(self, width=300)
        self.entry.pack(padx=20, pady=5)
        self.entry.bind("<Return>", self.start_pull)
        
        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack(padx=20, pady=(20, 5), anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(self, width=300)
        self.progress_bar.set(0)
        self.progress_bar.pack(padx=20, pady=5)
        
        self.pull_btn = ctk.CTkButton(self, text="Pull Model", command=self.start_pull)
        self.pull_btn.pack(padx=20, pady=20)
        
        self.is_pulling = False
        
        # Focus
        self.lift()
        self.focus_force()
        self.after(100, self.grab_set)

    def start_pull(self, event=None):
        if self.is_pulling:
            return
            
        model_name = self.entry.get().strip()
        if not model_name:
            return
            
        self.is_pulling = True
        self.pull_btn.configure(state="disabled", text="Pulling...")
        self.entry.configure(state="disabled")
        
        threading.Thread(target=self._pull_thread, args=(model_name,), daemon=True).start()
        
    def _pull_thread(self, model_name):
        try:
            for status in self.client.pull_model(model_name):
                if "error" in status:
                    self.after(0, lambda e=status["error"]: self.show_error(e))
                    return
                
                # Update UI
                self.after(0, lambda s=status: self.update_progress(s))
                
            self.after(0, self.finish_success)
            
        except Exception as e:
             self.after(0, lambda: self.show_error(str(e)))

    def update_progress(self, status):
        msg = status.get("status", "")
        
        # Calculate progress if available
        total = status.get("total")
        completed = status.get("completed")
        
        if total and completed:
            percent = completed / total
            self.progress_bar.set(percent)
            self.progress_label.configure(text=f"{msg} ({int(percent*100)}%)")
        else:
            self.progress_label.configure(text=msg)

    def finish_success(self):
        messagebox.showinfo("Success", "Model pulled successfully!")
        self.destroy()
        if self.on_complete:
            self.on_complete()

    def show_error(self, error_msg):
        messagebox.showerror("Error", f"Failed to pull model: {error_msg}")
        self.destroy()
