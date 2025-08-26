# translations.py

LANGUAGES = {
    "en": "English",
    "fr": "Français",
}

# This dictionary holds your translations.
# The structure is: {language_code: {key: translation_string}}
TRANSLATIONS = {
    "en": {
        "AI Email Assistant": "AI Email Assistant",
        "Welcome to the AI Email Assistant!": "Welcome to the AI Email Assistant!",
        "Select your language": "Select your language", # This is the hardcoded label, so it's fine
        "Generate Email": "Generate Email",
        "Compose your email details below.": "Compose your email details below.",
        "Recipient": "Recipient",
        "Subject": "Subject",
        "Body": "Body",
        "Sender": "Sender",
        "Clear Form": "Clear Form",
        "Your email has been generated! You can modify it below.": "Your email has been generated! You can modify it below.",
        "Error generating email. Please try again.": "Error generating email. Please try again.",
        "Recipient, Subject, and Body cannot be empty.": "Recipient, Subject, and Body cannot be empty.",
        "Enter a recipient": "Enter a recipient",
        "Enter a subject": "Enter a subject",
        "Enter email body": "Enter email body",
        "Enter sender name or email": "Enter sender name or email",
        # New Translations
        "1. Generation": "1. Generation",
        "2. Preview": "2. Preview",
        "3. Results": "3. Results",
        "Generation & Setup": "Generation & Setup",
        "Preview & Send": "Preview & Send",
        "Results": "Results",
        "Upload Excel (.xlsx/.xls)": "Upload an Excel file with contacts (.xlsx/.xls)",
        "Successfully loaded {count} valid contacts.": "Successfully loaded {count} valid contacts.",
        "Please upload an Excel file to get started.": "Please upload an Excel file to get started.",
        "Next": "Next",
        "Personalize emails?": "Personalize emails?",
        "Generic Greeting (e.g., 'Dear Valued Customer')": "Generic Greeting (e.g., 'Dear Valued Customer')",
        "Enter a generic greeting if not personalizing": "Enter a generic greeting if not personalizing",
        "AI Instruction: Describe the email you want to generate.": "AI Instruction: Describe the email you want to generate.",
        "e.g., 'Draft a newsletter about our new product features.'": "e.g., 'Draft a newsletter about our new product features.'",
        "Email Context (optional): Add style, tone, or specific details.": "Email Context (optional): Add style, tone, or specific details.",
        "e.g., 'Friendly tone, include a call to action to visit our website.'": "e.g., 'Friendly tone, include a call to action to visit our website.'",
        "Generating email template... Please wait.": "Generating email template... Please wait.",
        "Please provide instructions for the AI to generate the email.": "Please provide instructions for the AI to generate the email.",
        "Proceed to Preview & Send": "Proceed to Preview & Send",
        "Editable Email Content": "Editable Email Content",
        "Live Preview for First Contact": "Live Preview for First Contact",
        "Upload contacts in the first step to see a preview.": "Upload contacts in the first step to see a preview.",
        "Add Attachments": "Add Attachments",
        "Upload files": "Upload files",
        "Attachments selected: {count}": "Attachments selected: {count}",
        "Current Attachments": "Current Attachments",
        "Confirm Send": "Confirm Send",
        "Back to Generation": "Back to Generation", # New
        "Sending emails. Please wait.": "Sending emails. Please wait.", # New for progress bar
        "No contacts loaded to send emails to.": "No contacts loaded to send emails to.", # New
        "All emails sent successfully!": "All emails sent successfully!",
        "All {count} emails were sent without any issues.": "All {count} emails were sent without any issues.",
        "Sending complete with errors.": "Sending complete with errors.",
        "Some emails failed to send. Please check the log below for details.": "Some emails failed to send. Please check the log below for details.",
        "Summary": "Summary",
        "Total Contacts Processed": "Total Contacts Processed",
        "Emails Sent Successfully": "Emails Sent Successfully",
        "Emails Failed to Send": "Emails Failed to Send",
        "Show Activity Log and Errors": "Show Activity Log and Errors",
        "Activity Log": "Activity Log",
        "✅ Bulk send completed successfully!": "✅ Bulk send completed successfully!",
        "📧 Total emails sent: ": "📧 Total emails sent: ",
        "📊 Success rate: ": "📊 Success rate: ",
        "Start New Email Session": "Start New Email Session",
        "No emails were processed.": "No emails were processed.",
        "Sender Email": "Sender Email",
        "Not configured": "Not configured",
        "Sender email credentials are not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in Streamlit secrets.": "Sender email credentials are not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in Streamlit secrets.",
        "Valued Customer": "Valued Customer", # New fallback generic greeting
        "Language": "Language", # For the sidebar selectbox label
        "Dear": "Dear", # Added for dynamic salutation prefix
        "Edit the email template here. Changes will reflect in the live preview.": "Edit the email template here. Changes will reflect in the live preview.", # New info text for editable section
        "This shows how the email will appear for the first contact. To make changes, use the *Editable Email Content* section on the left.": "This shows how the email will appear for the first contact. To make changes, use the 'Editable Email Content' section on the left." # New info text for preview section
    },
    "fr": {
        "AI Email Assistant": "Assistant d'E-mail IA",
        "Welcome to the AI Email Assistant!": "Bienvenue dans l'Assistant d'E-mail IA !",
        "Select your language": "Sélectionnez votre langue",
        "Generate Email": "Générer l'E-mail",
        "Compose your email details below.": "Composez les détails de votre e-mail ci-dessous.",
        "Recipient": "Destinataire",
        "Subject": "Objet",
        "Body": "Corps du message",
        "Sender": "Expéditeur",
        "Clear Form": "Effacer le formulaire",
        "Your email has been generated! You can modify it below.": "Votre e-mail a été généré ! Vous pouvez le modifier ci-dessous.",
        "Error generating email. Please try again.": "Erreur lors de la génération de l'e-mail. Veuillez réessayer.",
        "Recipient, Subject, and Body cannot be empty.": "Le destinataire, l'objet et le corps du message ne peuvent pas être vides.",
        "Enter a recipient": "Saisissez un destinataire",
        "Enter a subject": "Saisissez un objet",
        "Enter email body": "Saisissez le corps de l'e-mail",
        "Enter sender name or email": "Saisissez le nom ou l'e-mail de l'expéditeur",
        # New Translations
        "1. Generation": "1. Génération",
        "2. Preview": "2. Prévisualisation",
        "3. Results": "3. Résultats",
        "Generation & Setup": "Génération & Configuration",
        "Preview & Send": "Prévisualisation & Envoi",
        "Results": "Résultats",
        "Upload Excel (.xlsx/.xls)": "Importer un fichier Excel (.xlsx/.xls)",
        "Successfully loaded {count} valid contacts.": "Chargement réussi de {count} contacts valides.",
        "Please upload an Excel file to get started.": "Veuillez importer un fichier Excel pour commencer.",
        "WARNING: Some contacts had issues (e.g., missing/invalid/duplicate emails). They will be skipped.": "AVERTISSEMENT : Certains contacts posent problème (e.g., e-mails manquants/invalides/dupliqués). Ils seront ignorés.",
        "Next": "Suivant",
        "Personalize emails?": "Personnaliser les e-mails ?",
        "Generic Greeting (e.g., 'Dear Valued Customer')": "Salutation Générique (ex: 'Cher Client')",
        "Enter a generic greeting if not personalizing": "Entrez une salutation générique si vous ne personnalisez pas",
        "AI Instruction: Describe the email you want to generate.": "Instruction IA : Décrivez l'e-mail que vous souhaitez générer.",
        "e.g., 'Draft a newsletter about our new product features.'": "ex: 'Rédigez une newsletter sur nos nouvelles fonctionnalités produit.'",
        "Email Context (optional): Add style, tone, or specific details.": "Contexte de l'e-mail (optionnel) : Ajoutez le style, le ton ou des détails spécifiques.",
        "e.g., 'Friendly tone, include a call to action to visit our website.'": "ex: 'Ton amical, inclure un appel à l'action pour visiter notre site web.'",
        "Generating email template... Please wait.": "Génération du modèle d'e-mail... Veuillez patienter.",
        "Please provide instructions for the AI to generate the email.": "Veuillez fournir des instructions à l'IA pour générer l'e-mail.",
        "Proceed to Preview & Send": "Passer à la prévisualisation et à l'envoi",
        "Editable Email Content": "Contenu de l'e-mail modifiable",
        "Live Preview for First Contact": "Aperçu en direct pour le premier contact",
        "Upload contacts in the first step to see a preview.": "Importez des contacts à la première étape pour voir un aperçu.",
        "Add Attachments": "Ajouter des pièces jointes",
        "Upload files": "Importer des fichiers",
        "Attachments selected: {count}": "Pièces jointes sélectionnées : {count}",
        "Current Attachments": "Pièces jointes actuelles",
        "Confirm Send": "Confirmer l'envoi",
        "Back to Generation": "Retour à la Génération",
        "Sending emails. Please wait.": "Envoi des e-mails. Veuillez patienter.",
        "No contacts loaded to send emails to.": "Aucun contact chargé pour envoyer des e-mails.",
        "All emails sent successfully!": "Tous les e-mails ont été envoyés avec succès !",
        "All {count} emails were sent without any issues.": "Tous les {count} e-mails ont été envoyés sans aucun problème.",
        "Sending complete with errors.": "Envoi terminé avec des erreurs.",
        "Some emails failed to send. Please check the log below for details.": "Certains e-mails n'ont pas pu être envoyés. Veuillez consulter le journal ci-dessous pour plus de détails.",
        "Summary": "Résumé",
        "Total Contacts Processed": "Total des contacts traités",
        "Emails Sent Successfully": "E-mails envoyés avec succès",
        "Emails Failed to Send": "E-mails échoués",
        "Show Activity Log and Errors": "Afficher le journal d'activité et les erreurs",
        "Activity Log": "Journal d'activité",
        "✅ Bulk send completed successfully!": "✅ Envoi de masse terminé avec succès !",
        "📧 Total emails sent: ": "📧 Total d'e-mails envoyés : ",
        "📊 Success rate: ": "📊 Taux de succès : ",
        "Start New Email Session": "Commencer une nouvelle session d'e-mail",
        "No emails were processed.\n": "Aucun e-mail n'a été traité.",
        "Sender Email": "E-mail de l'expéditeur",
        "Not configured": "Non configuré",
        "Sender email credentials are not configured. Please set SENDER_EMAIL and SENDER_PASSWORD in Streamlit secrets.": "Les identifiants de l'expéditeur ne sont pas configurés. Veuillez définir SENDER_EMAIL et SENDER_PASSWORD dans les secrets de Streamlit.",
        "Valued Customer": "Cher Client",
        "Language": "Langue",
        "Dear": "Bonjour", # Added for dynamic salutation prefix (translated to Bonjour for French)
        "Edit the email template here. Changes will reflect in the live preview.": "Modifiez le modèle d'e-mail ici. Les modifications se refléteront dans l'aperçu en direct.",
        "This shows how the email will appear for the first contact. To make changes, use the *Editable Email Content* section on the left.": "Ceci montre l'apparence de l'e-mail pour le premier contact. Pour apporter des modifications, utilisez la section 'Contenu de l'e-mail modifiable' sur la gauche."
    }
}

# Default language if no session state is set
DEFAULT_LANG = "en"

# Global variable to store the selected language
_selected_lang = DEFAULT_LANG

def set_language(lang_code):
    """Sets the global language for translations."""
    global _selected_lang
    if lang_code in LANGUAGES:
        _selected_lang = lang_code
    else:
        _selected_lang = DEFAULT_LANG # Fallback to default if invalid code

def _t(key, **kwargs):
    """
    Translates a given key into the selected language and formats it with kwargs.
    If the key is not found, it returns the key itself as a fallback.
    """
    translation = TRANSLATIONS.get(_selected_lang, {}).get(key, key)
    try:
        # Attempt to format the string with provided keyword arguments
        return translation.format(**kwargs)
    except KeyError as e:
        # Log or handle cases where a placeholder is missing in the translation string
        # For now, we'll just return the unformatted translation with a warning.
        print(f"Translation Error: Missing placeholder {e} for key '{key}' in language '{_selected_lang}'. Original translation: '{translation}'")
        return translation # Return unformatted string if formatting fails
    except IndexError as e:
        print(f"Translation Error: Index error {e} for key '{key}' in language '{_selected_lang}'. Original translation: '{translation}'")
        return translation # Return unformatted string if formatting fails