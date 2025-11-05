"""
Script to fix emoji encoding issues and update status messages in streamlit_app.py
"""

# Read the file
with open(r'c:\Users\shirl\Documents\workspace\ai-message-sender\streamlit_app.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Find the lines to fix (around line 593-598)
# Line 595 (index 594) has corrupted emoji - Change to proper contacts uploaded message
lines[594] = '                        status.append(_t("📤 Contacts uploaded: {count}", count=str(total_contacts)))\n'

# Insert new lines after 594
lines.insert(595, '                        status.append(_t("🔄 Duplicate email addresses removed: {count}", count=str(duplicates_removed)))\n')
lines.insert(596, '                        status.append(_t("📧 Unique emails sent: {count}", count=str(success)))\n')
lines.insert(597, '                        status.append(_t("📊 All {unique} unique email addresses delivered successfully", unique=success))\n')

# Add else clause after the new lines
lines.insert(598, '                    else:\n')

# Fix the old line 596 -> now 599 (Total emails sent) with proper indentation for else block
lines[599] = '                        status.append(_t("📧 Total emails sent: {count}", count=str(success)))\n'

# Fix lines 597-599 -> now 600-602 (Success rate) - update total calculation and indentation
lines[600] = '                        status.append(_t("📊 Success rate: {success}/{total} ({percentage:.1f}%)", \n'
lines[601] = '                                        success=success, total=total_contacts, \n'
lines[602] = '                                        percentage=(success/total_contacts*100) if total_contacts > 0 else 0))\n'

# Write back with proper UTF-8 encoding
with open(r'c:\Users\shirl\Documents\workspace\ai-message-sender\streamlit_app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('✅ File updated successfully with proper UTF-8 encoding')
print('✅ Status messages now properly show:')
print('   - Contacts uploaded')
print('   - Duplicates removed')
print('   - Unique emails sent')
print('   - Clear success rate based on total contacts')
