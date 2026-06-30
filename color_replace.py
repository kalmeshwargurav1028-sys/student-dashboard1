import os
import glob

def replace_colors(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    # Replace tailwind color classes
    content = content.replace('emerald', 'blue')
    content = content.replace('teal', 'indigo')
    # Replace hex codes
    content = content.replace('10b981', '2563eb')
    content = content.replace('Emerald', 'Blue')
    content = content.replace('Teal', 'Indigo')
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

# Process all html files in templates
for filepath in glob.glob('templates/*.html'):
    replace_colors(filepath)

# Process markdown files
replace_colors('brain.md')
replace_colors('DESIGN.md')

print("Color replacement complete.")
