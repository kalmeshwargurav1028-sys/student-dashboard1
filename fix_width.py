import os
import glob
import re

for filepath in glob.glob('templates/*.html'):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # We want to replace `<div class="max-w-7xl mx-auto ...">` with `<div class="w-full ...">`
    # We'll just replace 'max-w-7xl mx-auto' with 'w-full' everywhere in these files.
    # And maybe 'px-4 sm:px-6 lg:px-8' with 'px-8 sm:px-10 lg:px-12' for better padding on wide screens.
    
    new_content = content.replace('max-w-7xl mx-auto', 'w-full')
    new_content = new_content.replace('px-4 sm:px-6 lg:px-8', 'px-8 sm:px-10 lg:px-12')
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {filepath}")
