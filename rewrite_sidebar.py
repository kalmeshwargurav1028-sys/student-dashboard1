import re

with open('templates/base.html', 'r') as f:
    content = f.read()

# 1. Fix Logo
logo_replacement = """            <a href="{{ url_for('dashboard') }}" class="text-xl font-bold flex items-center gap-2 whitespace-nowrap overflow-hidden" id="sidebar-logo-text">
                <img src="{{ url_for('static', filename='images/logo.png') }}" class="h-8 w-auto flex-shrink-0" alt="Logo">
                <span class="sidebar-text transition-opacity duration-300">Indus Portal</span>
            </a>"""
content = re.sub(
    r'<a href="\{\{ url_for\(\'dashboard\'\) \}\}" class="text-xl font-bold flex items-center gap-2 whitespace-nowrap overflow-hidden" id="sidebar-logo-text">[\s\S]*?</svg>\s*<span class="sidebar-text transition-opacity duration-300">Indus Portal</span>\s*</a>',
    logo_replacement,
    content
)

# 2. Fix Sidebar for admin
# We'll inject the admin specific menu right after the <ul class="space-y-1">
admin_menu = """                {% if session.get('role') == 'admin' %}
                <!-- Admin Control Tower Menu (per diagram) -->
                <li>
                    <a href="{{ url_for('admin_dashboard') }}" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">🏠</span>
                        <span class="sidebar-text whitespace-nowrap">Dashboard</span>
                    </a>
                </li>
                <li>
                    <a href="#" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">📚</span>
                        <span class="sidebar-text whitespace-nowrap">Master Curriculum</span>
                    </a>
                </li>
                <li>
                    <a href="#" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">📅</span>
                        <span class="sidebar-text whitespace-nowrap">Master Timetables</span>
                    </a>
                </li>
                <li>
                    <a href="{{ url_for('admin_dashboard') }}" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">👥</span>
                        <span class="sidebar-text whitespace-nowrap">Student Roster</span>
                    </a>
                </li>
                <li>
                    <a href="#" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">👔</span>
                        <span class="sidebar-text whitespace-nowrap">Staff Directory</span>
                    </a>
                </li>
                <li>
                    <a href="#" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">💰</span>
                        <span class="sidebar-text whitespace-nowrap">Fee Management</span>
                    </a>
                </li>
                <li>
                    <a href="{{ url_for('ai_box') }}" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">🤖</span>
                        <span class="sidebar-text whitespace-nowrap">AI System Insights</span>
                    </a>
                </li>
                <li class="my-2 border-t border-emerald-400 dark:border-gray-700 mx-4 opacity-50"></li>
                <li>
                    <a href="{{ url_for('admin_dashboard') }}#roles" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <span class="text-xl mr-3 opacity-90 group-hover:opacity-100">🔑</span>
                        <span class="sidebar-text whitespace-nowrap">Role Management</span>
                    </a>
                </li>
                {% elif session.get('role') != 'student' %}
"""

# Replace the existing `{% if session.get('role') != 'student' %}` block start with our new logic
# Wait, the current logic is:
# {% if session.get('role') != 'student' %}
# <li>
#     {% if session.get('role') == 'admin' %}
#     <a href="{{ url_for('admin_dashboard') }}" class="flex items-center px-4 py-3...
#     {% else %}
#     <a href="{{ url_for('dashboard') }}" ...

pattern = r"\{\% if session\.get\('role'\) != 'student' \%\}\s*<li>\s*\{\% if session\.get\('role'\) == 'admin' \%\}.*?Dashboard</span>\s*</a>\s*</li>"
content = re.sub(pattern, admin_menu + """                <!-- Teacher Dashboard -->
                <li>
                    <a href="{{ url_for('dashboard') }}" class="flex items-center px-4 py-3 text-emerald-100 hover:bg-emerald-600 dark:hover:bg-gray-700 hover:text-white group transition-colors">
                        <svg class="h-6 w-6 flex-shrink-0 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
                        <span class="sidebar-text whitespace-nowrap">Dashboard</span>
                    </a>
                </li>""", content, flags=re.DOTALL)

# Now we need to make sure the existing `{% if session.get('role') == 'admin' %}` for Reports and Role Management is removed since we added Role Management to the admin block.
reports_pattern = r"\{\% if session\.get\('role'\) == 'admin' \%\}\s*<li>.*?Reports.*?Role Management.*?\{\% endif \%\}"
content = re.sub(reports_pattern, "", content, flags=re.DOTALL)


# 3. Add Settings back to the header
settings_html = """                {% if session.get('role') != 'student' %}
                <a href="{{ url_for('settings') }}" class="mr-4 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white focus:outline-none">
                    <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                </a>
                {% endif %}
                <h2"""
content = content.replace("<h2", settings_html)

with open('templates/base.html', 'w') as f:
    f.write(content)

print("Done")
