# data_handler_phone_numbers.py
import pandas as pd
import re # Import regex for more robust phone number pattern checking

def load_contacts_from_excel(file_path):
    """
    Loads contacts from an Excel file, dynamically identifies 'phone_number' and 'name' columns,
    and returns a list of dictionaries with 'name' and 'phone_number' keys.
    """
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        # Catch errors if the file is not a valid Excel or unreadable
        return [], [f"Error reading Excel file: {e}. Please ensure it's a valid .xlsx or .xls file."]

    # Standardize column names to lowercase for easier internal handling
    # Also strip any leading/trailing whitespace from column names
    df.columns = [col.strip().lower() for col in df.columns]

    phone_number_col_name = None
    name_col_name = None

    # Attempt to read all columns as strings initially to preserve leading zeros and '+'
    # This is a more robust approach for mixed data types in Excel, especially for phone numbers.
    # If this causes issues with other numeric columns, we might need a more targeted approach
    # after column detection.
    try:
        df = pd.read_excel(file_path, dtype=str)
    except Exception as e:
        return [], [f"Error reading Excel file with string dtype: {e}. Please ensure it's a valid .xlsx or .xls file."]

    # Re-standardize column names after re-reading with dtype=str
    df.columns = [col.strip().lower() for col in df.columns]

    # --- Strategy for Phone Number Column Detection ---
    # Prioritize exact 'phone' or common spellings first
    common_phone_number_names = ['phone', 'mobile', 'tel', 'telephone', 'phone number', 'contact number', 'cell']
    for common_name in common_phone_number_names:
        if common_name in df.columns:
            phone_number_col_name = common_name
            break # Found a direct match, use it

    # If not found by common names, try to detect based on content (presence of digits and common phone number patterns)
    if not phone_number_col_name:
        for col in df.columns:
            # Convert column to string type to handle mixed types gracefully
            col_series = df[col].astype(str).dropna() # Drop NaN/empty strings for accurate percentage

            # Define a more robust phone number pattern for content-based detection
            # This regex checks for common phone number formats (e.g., 123-456-7890, (123) 456-7890, 1234567890)
            # It's a flexible pattern to catch various international and local formats
            phone_pattern = r'^\+?[\d\s\-\(\)]{7,20}$' # Allows for +, digits, spaces, hyphens, parentheses, 7-20 chars
            
            # Count how many non-empty cells contain a phone number-like pattern
            phone_like_count = col_series.str.contains(phone_pattern, regex=True, na=False).sum()
            
            # Consider a column a phone number column if a significant percentage (e.g., > 50%) of its values look like phone numbers
            if len(col_series) > 0 and (phone_like_count / len(col_series)) >= 0.5: # 50% threshold for confidence
                phone_number_col_name = col
                break # Found a strong candidate, take the first one encountered

    if not phone_number_col_name:
        # If still no phone number column found, return an error message
        return [], ["Could not find a suitable 'Phone Number' column. Please ensure your Excel has a column with phone numbers (e.g., 'Phone', 'Mobile', 'Tel') or that most entries contain digits in a phone number format."]


    # --- Strategy for Name Column Detection ---
    # Prioritize common 'name' spellings in English and French
    common_name_columns = ['name', 'full name', 'first name', 'last name', 'nom', 'prenom', 'contact', 'contacts']
    for common_name in common_name_columns:
        if common_name in df.columns and common_name != phone_number_col_name:
            name_col_name = common_name
            break # Found a direct match, use it
            
    # If no common name column, pick the first non-phone number column available
    if not name_col_name:
        for col in df.columns:
            if col != phone_number_col_name:
                name_col_name = col
                break
    
    # If still no name column found (e.g., only phone number column exists), we will use a fallback name below
    
    # --- Process Contacts ---
    contacts = []
    contact_issues = []

    for index, row in df.iterrows():
        # Get phone number using the identified column, defaulting to empty string if not found or NaN
        phone_number = str(row[phone_number_col_name]).strip() if pd.notna(row[phone_number_col_name]) else ''
        
        # Get name using the identified column, defaulting to "Contact X" if not found or NaN
        if name_col_name and pd.notna(row.get(name_col_name)):
            name = str(row[name_col_name]).strip()
        else:
            name = f"Contact {index + 1}" # Fallback if no name column or name is missing

        # Basic phone number validation: must not be empty and match basic regex pattern
        # This will catch most obvious invalid formats
        if phone_number and re.match(r'^\+?[\d\s\-\(\)]{7,20}$', phone_number):
            contacts.append({"name": name, "phone_number": phone_number})
        else:
            # Log issues including the name detected, even if it's a fallback "Contact X"
            contact_issues.append(f"Row {index + 2}: Invalid or missing phone number for '{name}' (Phone: '{phone_number}').") # +2 for header row and 0-indexing

    return contacts, contact_issues
