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
        "Email sent successfully!": "Email sent successfully!",
        "Back to Generation": "Back to Generation",
        "Editable Email Content": "Editable Email Content",
        "Live Preview for First Contact": "Live Preview for First Contact",
        "This shows how the email will appear for the first contact. To make changes, use the *Editable Email Content* section on the left.": "This shows how the email will appear for the first contact. To make changes, use the 'Editable Email Content' section on the left.",
        "Add Attachments": "Add Attachments",
        "Upload files": "Upload files",
        "Current Attachments": "Current Attachments",
        "Confirm Send": "Confirm Send",
        "No contacts loaded to send emails to.": "No contacts loaded to send emails to.",
        "Subject and Body cannot be empty. Please go back to Generation if needed.": "Subject and Body cannot be empty. Please go back to Generation if needed.",
        "All emails sent successfully!": "All emails sent successfully!",
        "All {count} emails were sent without any issues.": "All {count} emails were sent without any issues.",
        "Sending complete with errors.": "Sending complete with errors.",
        "Some emails failed to send. Please check the log below for details.": "Some emails failed to send. Please check the log below for details.",
        "No emails were processed.": "No emails were processed.",
        "Total Contacts Processed": "Total Contacts Processed",
        "Emails Sent Successfully": "Emails Sent Successfully",
        "Emails Failed to Send": "Emails Failed to Send",
        "Show Activity Log and Errors": "Show Activity Log and Errors",
        "Individual Email Status & Events": "Individual Email Status & Events",
        "Refresh Events for this Email": "Refresh Events for this Email",
        "Events": "Events",
        "No events found yet for this message. Click 'Refresh Events' to check.": "No events found yet for this message. Click 'Refresh Events' to check.",
        "Activity Log": "Activity Log",
        "Start New Email Session": "Start New Email Session",
        "AI Instruction: Describe the email you want to generate.": "AI Instruction: Describe the email you want to generate.",
        "e.g., 'Draft a newsletter about our new product features.'": "e.g., 'Draft a newsletter about our new product features.'",
        "Email Context (optional): Add style, tone, or specific details.": "Email Context (optional): Add style, tone, or specific details.",
        "e.g., 'Friendly tone, include a call to action to visit our website.'": "e.g., 'Friendly tone, include a call to action to visit our website.'",
        "Personalize emails?": "Personalize emails?",
        "Generic Greeting (e.g., 'Dear Valued Customer')": "Generic Greeting (e.g., 'Dear Valued Customer')",
        "Enter a generic greeting if not personalizing": "Enter a generic greeting if not personalizing",
        "Add a Custom Button?": "Add a Custom Button?",
        "Custom Button Text": "Custom Button Text",
        "e.g., 'Learn More'": "e.g., 'Learn More'",
        "Button URL": "Button URL",
        "e.g., 'https://your-website.com'": "e.g., 'https://your-website.com'",
        "Please provide instructions for the AI to generate the email.": "Please provide instructions for the AI to generate the email.",
        "Successfully loaded {count} valid contacts.": "Successfully loaded {count} valid contacts.",
        "WARNING: Some contacts had issues (e.g., missing/invalid/duplicate emails). They will be skipped.": "WARNING: Some contacts had issues (e.g., missing/invalid/duplicate emails). They will be skipped.",
        "No valid contacts found in the Excel file.": "No valid contacts found in the Excel file.",
        "Please upload an Excel file to get started.": "Please upload an Excel file to get started.",
        "Sender Email": "Sender Email",
        "Not configured": "Not configured",
        "Sender email credentials are not configured. Please set SENDER_EMAIL and BREVO_API_KEY in Streamlit secrets.": "Sender email credentials are not configured. Please set SENDER_EMAIL and BREVO_API_KEY in Streamlit secrets.",
        "Upload Excel (.xlsx/.xls)": "Upload Excel (.xlsx/.xls)",
        "Attachments selected: {count}": "Attachments selected: {count}",
        "Donate Button Text": "Donate Now",
        "Donate Button URL": "https://www.migdal-france.org/MIGDAL-FRANCE_WEB/FR/PAIEMENT_STRIPE/DONS-PAIEMENT-CB.awp",
        "Valued Customer": "Valued Customer", # New fallback generic greeting
        "Language": "Language", # For the sidebar selectbox label
        "Dear": "Dear", # Added for dynamic salutation prefix
        "Characters: {n}": "Characters: {n}",
        "Tax Refund Text": "Your donation is eligible for a 66% tax refund.",
        "Association Info": "Migdal France | 1 rue de la Paix, 75002 Paris | contact@migdal-france.org",
        "Unsubscribe Text": "To unsubscribe from our mailing list, please click here."
    },
    "fr": {
        "AI Email Assistant": "Assistant Courriel IA",
        "Welcome to the AI Email Assistant!": "Bienvenue dans l'Assistant Courriel IA!",
        "Select your language": "Sélectionnez votre langue",
        "Generate Email": "Générer le Courriel",
        "Compose your email details below.": "Composez les détails de votre courriel ci-dessous.",
        "Recipient": "Destinataire",
        "Subject": "Sujet",
        "Sender": "Expéditeur",
        "Clear Form": "Effacer le formulaire",
        "Your email has been generated! You can modify it below.": "Votre courriel a été généré! Vous pouvez le modifier ci-dessous.",
        "Error generating email. Please try again.": "Erreur lors de la génération du courriel. Veuillez réessayer.",
        "Recipient, Subject, and Body cannot be empty.": "Le destinataire, le sujet et le corps ne peuvent pas être vides.",
        "Enter a recipient": "Entrez un destinataire",
        "Enter a subject": "Entrez un sujet",
        "Enter email body": "Entrez le corps du courriel",
        "Enter sender name or email": "Entrez le nom ou l'adresse email de l'expéditeur",
        # New Translations
        "1. Generation": "1. Génération",
        "2. Preview": "2. Prévisualisation",
        "3. Results": "3. Résultats",
        "Email sent successfully!": "Courriel envoyé avec succès!",
        "Back to Generation": "Retour à la Génération",
        "Editable Email Content": "Contenu du Courriel Modifiable",
        "Live Preview for First Contact": "Prévisualisation en Direct pour le Premier Contact",
        "Edit the email template here. Changes will reflect in the live preview.": "Modifiez le modèle d'e-mail ici. Les modifications se refléteront dans l'aperçu en direct.",
        "This shows how the email will appear for the first contact. To make changes, use the *Editable Email Content* section on the left.": "Ceci montre l'apparence de l'e-mail pour le premier contact. Pour apporter des modifications, utilisez la section 'Contenu de l'e-mail modifiable' sur la gauche.",
        "Add Attachments": "Ajouter des Pièces Jointes",
        "Upload files": "Télécharger des fichiers",
        "Current Attachments": "Pièces Jointes Actuelles",
        "Confirm Send": "Confirmer l'envoi",
        "No contacts loaded to send emails to.": "Aucun contact chargé pour envoyer des courriels.",
        "Subject and Body cannot be empty. Please go back to Generation if needed.": "Le sujet et le corps ne peuvent pas être vides. Veuillez retourner à la Génération si nécessaire.",
        "All emails sent successfully!": "Tous les courriels ont été envoyés avec succès!",
        "All {count} emails were sent without any issues.": "Les {count} courriels ont tous été envoyés sans problème.",
        "Sending complete with errors.": "Envoi terminé avec des erreurs.",
        "Some emails failed to send. Please check the log below for details.": "Certains courriels n'ont pas pu être envoyés. Veuillez vérifier le journal ci-dessous pour plus de détails.",
        "No emails were processed.": "Aucun courriel n'a été traité.",
        "Total Contacts Processed": "Nombre total de contacts traités",
        "Emails Sent Successfully": "Courriels envoyés avec succès",
        "Emails Failed to Send": "Courriels non envoyés",
        "Show Activity Log and Errors": "Afficher le journal d'activité et les erreurs",
        "Individual Email Status & Events": "Statut et événements des courriels individuels",
        "Message ID": "ID du message",
        "Refresh Events for this Email": "Actualiser les événements pour ce courriel",
        "Events": "Événements",
        "No events found yet for this message. Click 'Refresh Events' to check.": "Aucun événement trouvé pour ce message. Cliquez sur 'Actualiser les événements' pour vérifier.",
        "Activity Log": "Journal d'activité",
        "Start New Email Session": "Démarrer une nouvelle session de courriel",
        "AI Instruction: Describe the email you want to generate.": "Instruction IA : Décrivez le courriel que vous souhaitez générer.",
        "e.g., 'Draft a newsletter about our new product features.'": "ex. : 'Rédigez une newsletter sur nos nouvelles fonctionnalités de produit.'",
        "Email Context (optional): Add style, tone, or specific details.": "Contexte du courriel (facultatif) : Ajoutez un style, un ton ou des détails spécifiques.",
        "e.g., 'Friendly tone, include a call to action to visit our website.'": "ex. : 'Ton amical, incluez un appel à l'action pour visiter notre site web.'",
        "Personalize emails?": "Personnaliser les courriels?",
        "Generic Greeting (e.g., 'Dear Valued Customer')": "Salutation Générique (ex. : 'Cher client')",
        "Enter a generic greeting if not personalizing": "Entrez une salutation générique si vous ne personnalisez pas",
        "Add a Custom Button?": "Ajouter un Bouton Personnalisé?",
        "Custom Button Text": "Texte du Bouton Personnalisé",
        "e.g., 'Learn More'": "ex. : 'En savoir plus'",
        "Button URL": "URL du Bouton",
        "e.g., 'https://your-website.com'": "ex. : 'https://votre-site-web.com'",
        "Please provide instructions for the AI to generate the email.": "Veuillez fournir des instructions à l'IA pour générer le courriel.",
        "Successfully loaded {count} valid contacts.": "{count} contacts valides ont été chargés avec succès.",
        "WARNING: Some contacts had issues (e.g., missing/invalid/duplicate emails). They will be skipped.": "AVERTISSEMENT : Certains contacts présentaient des problèmes (ex. : emails manquants/invalides/dupliqués). Ils seront ignorés.",
        "No valid contacts found in the Excel file.": "Aucun contact valide n'a été trouvé dans le fichier Excel.",
        "Please upload an Excel file to get started.": "Veuillez télécharger un fichier Excel pour commencer.",
        "Sender Email": "Courriel de l'expéditeur",
        "Not configured": "Non configuré",
        "Sender email credentials are not configured. Please set SENDER_EMAIL and BREVO_API_KEY in Streamlit secrets.": "Les informations d'identification de l'expéditeur ne sont pas configurées. Veuillez définir SENDER_EMAIL et BREVO_API_KEY dans les secrets de Streamlit.",
        "Upload Excel (.xlsx/.xls)": "Télécharger un fichier Excel (.xlsx/.xls)",
        "Attachments selected: {count}": "{count} pièces jointes sélectionnées",
        "Donate Button Text": "Faire un don",
        "Donate Button URL": "https://www.migdal-france.org/MIGDAL-FRANCE_WEB/FR/PAIEMENT_STRIPE/DONS-PAIEMENT-CB.awp",
        "Valued Customer": "Cher Client",
        "Language": "Langue",
        "Dear": "Bonjour", # Added for dynamic salutation prefix (translated to Bonjour for French)
        "Characters: {n}": "Caractères : {n}",
        "Tax Refund Text": "Votre don est éligible à une déduction fiscale de 66%.",
        "Association Info": "Migdal France | 1 rue de la Paix, 75002 Paris | contact@migdal-france.org",
        "Unsubscribe Text": "Pour vous désinscrire de notre liste de diffusion, veuillez cliquer ici."
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
