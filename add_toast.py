import os, re

base_path = 'templates/base.html'
with open(base_path, 'r') as f:
    content = f.read()

toast_func = """
        window.showToast = function(message, type = 'success') {
            const container = document.getElementById('toast-container');
            if (!container) return;
            
            const isError = type === 'error';
            const bgColor = 'bg-white dark:bg-gray-800';
            const borderColor = isError ? 'border-l-4 border-red-500' : 'border-l-4 border-blue-500';
            const textColor = 'text-gray-800 dark:text-gray-200';
            const iconColor = isError ? 'text-red-500' : 'text-blue-500';
            
            const svgIcon = isError 
                ? '<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>'
                : '<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>';
            
            const toastHtml = `
                <div class="toast-message pointer-events-auto flex items-start w-80 sm:w-96 ${bgColor} ${borderColor} shadow-xl rounded-r-lg p-4 transition-all duration-300" role="alert">
                    <div class="flex-shrink-0 ${iconColor} mt-0.5">
                        ${svgIcon}
                    </div>
                    <div class="ml-3 w-0 flex-1 pt-0.5">
                        <p class="text-sm font-medium ${textColor}">${message}</p>
                    </div>
                    <div class="ml-4 flex-shrink-0 flex">
                        <button type="button" class="inline-flex text-gray-400 hover:text-gray-500 focus:outline-none" onclick="this.closest('.toast-message').remove()">
                            <span class="sr-only">Close</span>
                            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                            </svg>
                        </button>
                    </div>
                </div>
            `;
            
            // Insert at the end of the container
            container.insertAdjacentHTML('beforeend', toastHtml);
            const newToast = container.lastElementChild;
            
            // Auto remove
            setTimeout(() => {
                newToast.classList.add('opacity-0');
                setTimeout(() => newToast.remove(), 300);
            }, 5000);
        };
"""

if 'window.showToast' not in content:
    content = content.replace('// Trigger toast animations for exit', toast_func + '\n        // Trigger toast animations for exit')
    with open(base_path, 'w') as f:
        f.write(content)
        
import glob

# Replace alert( with showToast( in all html files except when it's part of another word
for filepath in glob.glob('templates/**/*.html', recursive=True):
    with open(filepath, 'r') as f:
        text = f.read()
    
    # We want to replace alert( with showToast(
    # but for errors we want showToast(..., 'error')
    # So we can use a regex:
    # If it says alert('Error: ...') or alert('Failed...') we can add 'error'
    
    def repl(m):
        inner = m.group(1)
        if 'error' in inner.lower() or 'fail' in inner.lower() or 'invalid' in inner.lower():
            return f"showToast({inner}, 'error')"
        else:
            return f"showToast({inner})"
            
    # Match alert( followed by anything that's not a closing paren, but we have to handle balanced parens.
    # Actually just a simple string replace might be safer for most, or we can use regex
    # Since alerts are simple: alert('...')
    new_text = re.sub(r'alert\((.*?)\)', repl, text)
    
    if new_text != text:
        with open(filepath, 'w') as f:
            f.write(new_text)
            print(f"Updated {filepath}")
