# data_handler.py
import pandas as pd
import re # Import regex for more robust email pattern checking
import logging

def load_contacts_from_excel(file_path):
    """
    Loads contacts from an Excel file, dynamically identifies 'email' and 'name' columns,
    and returns a list of dictionaries with 'name' and 'email' keys.
    """
    logging.info(f"[DATA_HANDLER] Loading contacts from Excel file: {file_path}")
    try:
        df = pd.read_excel(file_path)
        logging.info(f"[DATA_HANDLER] Excel file loaded successfully - {len(df)} rows found")
    except Exception as e:
        # Catch errors if the file is not a valid Excel or unreadable
        logging.error(f"[DATA_HANDLER] Error reading Excel file: {e}")
        return [], [f"Error reading Excel file: {e}. Please ensure it's a valid .xlsx or .xls file."]

    # Standardize column names to lowercase for easier internal handling
    # Also strip any leading/trailing whitespace from column names
    df.columns = [col.strip().lower() for col in df.columns]

    email_col_name = None
    name_col_name = None

    # --- Strategy for Email Column Detection ---
    # Prioritize exact 'email' or common 'mail' spellings first
    common_email_names = ['email', 'mail', 'e-mail', 'adresse email', 'courriel']
    for common_name in common_email_names:
        if common_name in df.columns:
            email_col_name = common_name
            break # Found a direct match, use it

    # If not found by common names, try to detect based on content (presence of '@' and a dot)
    if not email_col_name:
        for col in df.columns:
            # Convert column to string type to handle mixed types gracefully
            col_series = df[col].astype(str).dropna() # Drop NaN/empty strings for accurate percentage

            # Define a more robust email pattern for content-based detection
            # This regex checks for something@something.domain
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            # Count how many non-empty cells contain an email-like pattern
            email_like_count = col_series.str.contains(email_pattern, regex=True, na=False).sum()
            
            # Consider a column an email column if a significant percentage (e.g., > 50%) of its values look like emails
            if len(col_series) > 0 and (email_like_count / len(col_series)) >= 0.5: # 50% threshold for confidence
                email_col_name = col
                break # Found a strong candidate, take the first one encountered

    if not email_col_name:
        # If still no email column found, return an error message
        logging.warning("[DATA_HANDLER] Could not find email column in Excel file")
        return [], ["Could not find a suitable 'Email' column. Please ensure your Excel has a column with email addresses (e.g., 'Email', 'Mail', 'Courriel') or that most entries contain an '@' symbol and a domain."]

    logging.info(f"[DATA_HANDLER] Email column identified: {email_col_name}")

    # --- Strategy for Name Column Detection ---
    # Prioritize common 'name' spellings in English and French
    common_name_columns = ['name', 'full name', 'first name', 'last name', 'nom', 'prenom', 'contact', 'contacts']
    for common_name in common_name_columns:
        if common_name in df.columns and common_name != email_col_name:
            name_col_name = common_name
            break # Found a direct match, use it
            
    # If no common name column, pick the first non-email column available
    if not name_col_name:
        for col in df.columns:
            if col != email_col_name:
                name_col_name = col
                break
    
    logging.info(f"[DATA_HANDLER] Name column identified: {name_col_name if name_col_name else 'None (using fallback)'}")
    
    # If still no name column found (e.g., only email column exists), we will use a fallback name below
    
    # --- Process Contacts ---
    contacts = []
    contact_issues = []

    for index, row in df.iterrows():
        # Get email using the identified column, defaulting to empty string if not found or NaN
        # *** MODIFIED LINE HERE ***
        email = str(row[email_col_name]).strip().lower().replace(" ", "") if pd.notna(row[email_col_name]) else ''
        
        # Get name using the identified column, defaulting to "Contact X" if not found or NaN
        if name_col_name and pd.notna(row.get(name_col_name)):
            name = str(row[name_col_name]).strip()
        else:
            name = f"Contact {index + 1}" # Fallback if no name column or name is missing

        # Enhanced email validation
        if email and _is_valid_email(email):
            contacts.append({"name": name, "email": email})
        else:
            # Log issues including the name detected, even if it's a fallback "Contact X"
            contact_issues.append(f"Row {index + 2}: Invalid or missing email for '{name}' (Email: '{email}').") # +2 for header row and 0-indexing

    logging.info(f"[DATA_HANDLER] Processing complete - {len(contacts)} valid contacts, {len(contact_issues)} issues")
    return contacts, contact_issues


def _is_valid_email(email: str) -> bool:
    """
    Enhanced email validation with better pattern matching and additional checks.
    
    Args:
        email: Email address string to validate
        
    Returns:
        True if email is valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic format check
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False
    
    # Additional checks for common issues
    # 1. No spaces in email
    if ' ' in email:
        return False
    
    # 2. Must have exactly one @ symbol
    if email.count('@') != 1:
        return False
    
    # 3. Local part (before @) and domain part (after @) must not be empty
    local_part, domain_part = email.split('@')
    if not local_part or not domain_part:
        return False
    
    # 4. Domain must have at least one dot
    if '.' not in domain_part:
        return False
    
    # 5. No consecutive dots
    if '..' in email:
        return False
    
    # 6. Must not start or end with a dot
    if email.startswith('.') or email.endswith('.'):
        return False
    
    # 7. Domain extension must be at least 2 characters
    domain_extension = domain_part.split('.')[-1]
    if len(domain_extension) < 2:
        return False
    
    return True