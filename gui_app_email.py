# gui_app_email.py

import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import time
import os
import datetime

# Import from config.py - Updated to use BREVO_API_KEY and remove SENDER_PASSWORD
from config import SENDER_EMAIL, OPENAI_API_KEY, FAILED_EMAILS_LOG_PATH, BREVO_API_KEY

# Import your custom modules
from data_handler import load_contacts_from_excel
from email_tool import send_email_message
from email_agent import SmartEmailAgent # Use the unified email_agent

class SmartEmailMessengerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Smart Email Messenger AI Agent")
        self.geometry("900x780")
        self.resizable(False, False)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.contacts = []
        self.contact_issues = []
        
        # Initialize AI agent if API key is available
        self.agent = None
        if OPENAI_API_KEY:
            try:
                self.agent = SmartEmailAgent(openai_api_key=OPENAI_API_KEY)
            except ValueError as e:
                self.log(f"Error initializing AI agent: {e}. AI features will be disabled.", "error")
        else:
            self.log("OpenAI API Key is not configured. AI email generation will be disabled.", "warning")

        self.selected_file_path = ""
        self.email_preview = None
        self.attachments = [] # List to store paths of attachments

        self.create_widgets()
        self.log("Application started.")

    def log(self, message, message_type="info"):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.activity_log.insert(ctk.END, log_entry + "\n")
        self.activity_log.see(ctk.END) # Auto-scroll to the end

        # Also save to a log file
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        sending_log_path = os.path.join(log_dir, "sending_log.txt")
        with open(sending_log_path, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")


    def create_widgets(self):
        # --- Frame for File Upload ---
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(pady=10, padx=20, fill="x")

        self.file_label = ctk.CTkLabel(file_frame, text="No contacts file selected.")
        self.file_label.pack(side="left", padx=(0, 10))

        self.upload_button = ctk.CTkButton(file_frame, text="Upload Contacts (Excel)", command=self.load_contacts_file)
        self.upload_button.pack(side="left", padx=(0, 10))
        
        self.contacts_info_label = ctk.CTkLabel(file_frame, text="0 valid contacts loaded.")
        self.contacts_info_label.pack(side="left", padx=(0, 10))
        
        # --- Email Generation/Composition Frame ---
        compose_frame = ctk.CTkFrame(self)
        compose_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Prompt and Context
        ctk.CTkLabel(compose_frame, text="Email Purpose (e.g., 'a follow-up email to new users'):").pack(pady=(5,0), padx=5, anchor="w")
        self.prompt_entry = ctk.CTkTextbox(compose_frame, height=70)
        self.prompt_entry.pack(pady=(0,10), padx=5, fill="x")
        
        ctk.CTkLabel(compose_frame, text="Additional Context/Tone (e.g., 'Warm and friendly tone'):").pack(pady=(5,0), padx=5, anchor="w")
        self.context_entry = ctk.CTkTextbox(compose_frame, height=50)
        self.context_entry.pack(pady=(0,10), padx=5, fill="x")

        # Personalization & Generic Greeting
        self.personalized_checkbox = ctk.CTkCheckBox(compose_frame, text="Personalize emails (include recipient's name/email)", command=self.toggle_personalization)
        self.personalized_checkbox.pack(pady=(5, 0), padx=5, anchor="w")
        self.personalized_checkbox.select() # Default to personalized

        ctk.CTkLabel(compose_frame, text="Generic Greeting (e.g., 'Dear Valued Customer,'):").pack(pady=(5, 0), padx=5, anchor="w")
        self.generic_greeting_entry = ctk.CTkEntry(compose_frame)
        self.generic_greeting_entry.insert(0, "Dear Valued Customer,")
        self.generic_greeting_entry.pack(pady=(0, 10), padx=5, fill="x")
        self.generic_greeting_entry.configure(state="disabled") # Disabled by default as personalization is ON

        self.preview_button = ctk.CTkButton(compose_frame, text="Generate Email Preview", command=self.generate_email_preview_thread,
                                            state="normal" if self.agent else "disabled")
        self.preview_button.pack(pady=10, padx=5, fill="x")

        # Email Subject & Body
        ctk.CTkLabel(compose_frame, text="Subject:").pack(pady=(5,0), padx=5, anchor="w")
        self.subject_entry = ctk.CTkEntry(compose_frame)
        self.subject_entry.pack(pady=(0,10), padx=5, fill="x")

        ctk.CTkLabel(compose_frame, text="Body:").pack(pady=(5,0), padx=5, anchor="w")
        self.body_entry = ctk.CTkTextbox(compose_frame, height=150)
        self.body_entry.pack(pady=(0,10), padx=5, fill="both", expand=True)

        # Attachments
        attachment_frame = ctk.CTkFrame(compose_frame)
        attachment_frame.pack(pady=(5, 10), padx=5, fill="x")
        ctk.CTkLabel(attachment_frame, text="Attachments (Optional):").pack(side="left", padx=(0,10))
        self.attach_button = ctk.CTkButton(attachment_frame, text="Add Attachment", command=self.add_attachment)
        self.attach_button.pack(side="left", padx=(0,10))
        self.attachments_label = ctk.CTkLabel(attachment_frame, text="No attachments added.")
        self.attachments_label.pack(side="left", padx=(0,10))

        # --- Send Email Button ---
        self.send_button = ctk.CTkButton(self, text="Send Emails to All Contacts", command=self.send_emails_thread)
        self.send_button.pack(pady=10, padx=20, fill="x")

        # --- Activity Log ---
        ctk.CTkLabel(self, text="Activity Log:").pack(pady=(5,0), padx=20, anchor="w")
        self.activity_log = scrolledtext.ScrolledText(self, wrap=ctk.WORD, height=10, bg="#f0f0f0", fg="#333333")
        self.activity_log.pack(pady=(0,10), padx=20, fill="x")
        self.activity_log.configure(state="disabled") # Make it read-only

    def toggle_personalization(self):
        if self.personalized_checkbox.get() == 1: # Personalized is checked
            self.generic_greeting_entry.configure(state="disabled")
            self.generic_greeting_entry.delete(0, ctk.END)
            self.generic_greeting_entry.insert(0, "Dear Valued Customer,") # Reset to default generic text
        else:
            self.generic_greeting_entry.configure(state="normal")

    def load_contacts_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if file_path:
            self.selected_file_path = file_path
            self.file_label.configure(text=os.path.basename(file_path))
            self.log(f"Selected file: {os.path.basename(file_path)}")
            
            contacts, contact_issues = load_contacts_from_excel(file_path)
            self.contacts = contacts
            self.contact_issues = contact_issues
            self.contacts_info_label.configure(text=f"{len(self.contacts)} valid contacts loaded.")
            self.log(f"Loaded {len(self.contacts)} contacts from Excel.")
            
            if contact_issues:
                self.log("WARNING: Some contacts had issues (e.g., missing/invalid/duplicate emails). They will be skipped.", "warning")
                for issue in contact_issues:
                    self.log(f"  - {issue}", "warning")
            else:
                self.log("All contacts loaded successfully with no issues.", "info")
            self.attachments = [] # Clear attachments on new contact upload
            self.attachments_label.configure(text="No attachments added.") # Update attachments label
        else:
            self.log("No file selected for contacts.")

    def add_attachment(self):
        file_paths = filedialog.askopenfilenames(
            title="Select attachment files",
            filetypes=[("All files", "*.*"), ("PDF files", "*.pdf"), ("Image files", "*.png *.jpg *.jpeg"), ("Text files", "*.txt")]
        )
        if file_paths:
            for path in file_paths:
                if path not in self.attachments: # Avoid adding duplicates
                    self.attachments.append(path)
            self.attachments_label.configure(text=f"{len(self.attachments)} attachments added.")
            self.log(f"Added attachments: {', '.join([os.path.basename(p) for p in file_paths])}")
        else:
            self.log("No new attachments selected.")

    def generate_email_preview_thread(self):
        # Disable buttons while generation is in progress
        self.preview_button.configure(state="disabled", text="Generating...")
        self.send_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.personalized_checkbox.configure(state="disabled")
        self.generic_greeting_entry.configure(state="disabled") # Disable during generation too

        # Start generation in a separate thread
        threading.Thread(target=self._generate_email_preview_task).start()

    def _generate_email_preview_task(self):
        if not self.agent:
            self.after(0, lambda: self.log("AI Email Agent is not initialized. Check API Key configuration.", "error"))
            self.after(0, lambda: self.preview_button.configure(state="normal", text="Generate Email Preview"))
            self.after(0, lambda: self.send_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization()) # Re-enable/disable generic greeting correctly
            return

        prompt = self.prompt_entry.get("1.0", ctk.END).strip()
        context = self.context_entry.get("1.0", ctk.END).strip()
        personalize = self.personalized_checkbox.get() == 1

        if not prompt:
            self.after(0, lambda: self.log("Please provide a prompt for the email.", "error"))
            self.after(0, lambda: self.preview_button.configure(state="normal", text="Generate Email Preview"))
            self.after(0, lambda: self.send_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization())
            return

        self.after(0, lambda: self.log("Generating email preview for a sample contact. This may take a moment..."))

        sample_contact = {"name": "Recipient Name", "email": "recipient@example.com"}
        if self.contacts:
            sample_contact = self.contacts[0]
            self.after(0, lambda: self.log(f"Using first contact for preview: {sample_contact.get('name', 'N/A')} ({sample_contact.get('email', 'N/A')})"))
        else:
            self.after(0, lambda: self.log("No contacts uploaded. Generating a generic preview."))

        try:
            generated_template = self.agent.generate_email_template(
                prompt,
                user_email_context=context,
                output_language="en", # Assuming English for GUI app, or could add language selection
                personalize_emails=personalize
            )

            subject = generated_template["subject"]
            body = generated_template["body"]

            # Apply personalization/generic greeting for preview
            if personalize:
                display_name = sample_contact.get("name", "there")
                display_email = sample_contact.get("email", "your email")
                subject = subject.replace("{{Name}}", display_name).replace("{{Email}}", display_email)
                body = body.replace("{{Name}}", display_name).replace("{{Email}}", display_email)
            else:
                generic_greeting = self.generic_greeting_entry.get().strip()
                if generic_greeting:
                    body = generic_greeting + "\n\n" + body

            self.after(0, lambda: self.subject_entry.delete(0, ctk.END))
            self.after(0, lambda: self.subject_entry.insert(0, subject))
            self.after(0, lambda: self.body_entry.delete("1.0", ctk.END))
            self.after(0, lambda: self.body_entry.insert("1.0", body))
            self.after(0, lambda: self.log("Email preview generated successfully."))

        except Exception as e:
            self.after(0, lambda: self.log(f"Error generating email: {e}", "error"))
        finally:
            self.after(0, lambda: self.preview_button.configure(state="normal", text="Generate Email Preview"))
            self.after(0, lambda: self.send_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization())

    def send_emails_thread(self):
        # Disable buttons while sending is in progress
        self.send_button.configure(state="disabled", text="Sending...")
        self.preview_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.personalized_checkbox.configure(state="disabled")
        self.generic_greeting_entry.configure(state="disabled")

        # Start sending in a separate thread
        threading.Thread(target=self._send_emails_background_task).start()

    def _send_emails_background_task(self):
        if not self.contacts:
            self.after(0, lambda: self.log("Please upload contacts first.", "error"))
            self.after(0, lambda: self.send_button.configure(state="normal", text="Send Emails to All Contacts"))
            self.after(0, lambda: self.preview_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization())
            return
        
        subject = self.subject_entry.get()
        body = self.body_entry.get("1.0", ctk.END).strip()

        if not subject or not body:
            self.after(0, lambda: self.log("Subject and body cannot be empty.", "error"))
            self.after(0, lambda: self.send_button.configure(state="normal", text="Send Emails to All Contacts"))
            self.after(0, lambda: self.preview_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization())
            return
        
        if not SENDER_EMAIL:
            self.after(0, lambda: self.log("Sender email is not configured. Email sending will be disabled.", "error"))
            self.after(0, lambda: self.send_button.configure(state="normal", text="Send Emails to All Contacts"))
            self.after(0, lambda: self.preview_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization())
            return
        
        if not BREVO_API_KEY:
            self.after(0, lambda: self.log("Brevo API Key is not configured. Email sending will be disabled.", "error"))
            self.after(0, lambda: self.send_button.configure(state="normal", text="Send Emails to All Contacts"))
            self.after(0, lambda: self.preview_button.configure(state="normal"))
            self.after(0, lambda: self.upload_button.configure(state="normal"))
            self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
            self.after(0, lambda: self.toggle_personalization())
            return

        self.after(0, lambda: self.log("Email sending process initiated..."))

        total_success = 0
        total_failed = 0 # Includes skipped and actual failures

        sender_email_configured = SENDER_EMAIL
        # Derive sender_name from SENDER_EMAIL (e.g., "JohnDoe" from "johndoe@example.com")
        sender_name = sender_email_configured.split('@')[0].replace('.', ' ').title() if sender_email_configured else "Sender"
        
        for i, recipient in enumerate(self.contacts):
            recipient_email = recipient.get('email')
            recipient_name = recipient.get('name', 'there')

            self.after(0, lambda: self.log(f"\n--- [{i + 1}/{len(self.contacts)}] Processing contact: {recipient_name} ({recipient_email}) ---"))

            if not recipient_email:
                total_failed += 1
                self.after(0, lambda: self.log(f"  - Skipping contact {recipient_name} due to missing email address.", "warning"))
                continue

            final_body = body
            final_subject = subject

            if self.personalized_checkbox.get() == 1:
                # Replace placeholders with actual contact data for personalized emails
                final_body = final_body.replace("{{Name}}", recipient_name).replace("{{Email}}", recipient_email)
                final_subject = final_subject.replace("{{Name}}", recipient_name).replace("{{Email}}", recipient_email)
                self.after(0, lambda: self.log(f"  Generating personalized email for {recipient_name}..."))
            else:
                generic_greeting = self.generic_greeting_entry.get().strip()
                if generic_greeting:
                    final_body = generic_greeting + "\n\n" + final_body
                self.after(0, lambda: self.log(f"  Preparing generic email for {recipient_name}..."))


            self.after(0, lambda: self.log(f"  Attempting Email for {recipient_name}..."))
            try:
                result = send_email_message(
                    sender_email=sender_email_configured,
                    sender_name=sender_name,
                    to_email=recipient_email,
                    to_name=recipient_name,
                    subject=final_subject,
                    body=final_body,
                    attachments=self.attachments
                )
                
                if result['status'] == 'success':
                    total_success += 1
                    self.after(0, lambda: self.log(f"    - Email: success - Email sent to {recipient_email} successfully."))
                else:
                    total_failed += 1
                    self.after(0, lambda: self.log(f"    - Email: error - Failed to send to {recipient_email}. Details: {result['message']}", "error"))
            except Exception as e:
                total_failed += 1
                self.after(0, lambda: self.log(f"    - Email: error - An unexpected error occurred for {recipient_email}: {e}", "error"))
                
            time.sleep(0.1) # Small delay to avoid hammering the API

        self.after(0, lambda: self.log("--- Email sending process complete ---"))
        self.after(0, lambda: self.log(f"Summary: {total_success} successful, {total_failed} failed/skipped."))
        
        self.after(0, lambda: self.send_button.configure(state="normal", text="Send Emails to All Contacts"))
        self.after(0, lambda: self.preview_button.configure(state="normal"))
        self.after(0, lambda: self.upload_button.configure(state="normal"))
        self.after(0, lambda: self.personalized_checkbox.configure(state="normal"))
        self.after(0, lambda: self.toggle_personalization()) # Re-enable/disable generic greeting correctly
        
        self.after(0, lambda: messagebox.showinfo("Sending Complete", 
                                                  f"Finished sending emails.\nSuccessful: {total_success}\nFailed/Skipped: {total_failed}\n\nCheck the Activity Log for details."))



if __name__ == "__main__":
    app = SmartEmailMessengerApp()
    app.mainloop()
