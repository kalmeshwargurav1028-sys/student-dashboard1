import re

with open('templates/admin_dashboard.html', 'r') as f:
    content = f.read()

# 1. Update stats cards to use emojis and colorful gradients
cards_pattern = re.compile(r'(<div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 mb-8">.*?)(</div>\s+</div>\s+<!-- Active Users Tables -->)', re.DOTALL)

new_cards = """<div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 mb-8">
            <!-- Admins Stats -->
            <div class="bg-gradient-to-br from-red-50 to-rose-100 overflow-hidden shadow-sm rounded-xl border border-red-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center">
                    <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-red-100">
                        👑
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-bold text-red-800 truncate">Total Admins</dt>
                            <dd class="flex items-baseline"><div class="text-2xl font-black text-red-900">{{ stats.total_admins }}</div></dd>
                        </dl>
                    </div>
                </div>
            </div>
            
            <div class="bg-gradient-to-br from-emerald-50 to-teal-100 overflow-hidden shadow-sm rounded-xl border border-emerald-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center">
                    <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-emerald-100">
                        🛡️
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-bold text-emerald-800 truncate">Active Admins</dt>
                            <dd class="flex items-baseline">
                                <div class="text-2xl font-black text-emerald-900">{{ stats.active_admins }}</div>
                                <span class="ml-2 text-xs font-bold text-emerald-700 bg-white px-2 py-0.5 rounded-full">Past 15 mins</span>
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>

            <!-- Teachers Stats -->
            <div class="bg-gradient-to-br from-blue-50 to-indigo-100 overflow-hidden shadow-sm rounded-xl border border-blue-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center">
                    <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-blue-100">
                        👨‍🏫
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-bold text-blue-800 truncate">Total Teachers</dt>
                            <dd class="flex items-baseline"><div class="text-2xl font-black text-blue-900">{{ stats.total_teachers }}</div></dd>
                        </dl>
                    </div>
                </div>
            </div>
            
            <div class="bg-gradient-to-br from-emerald-50 to-teal-100 overflow-hidden shadow-sm rounded-xl border border-emerald-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center">
                    <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-emerald-100">
                        ✅
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-bold text-emerald-800 truncate">Active Teachers</dt>
                            <dd class="flex items-baseline">
                                <div class="text-2xl font-black text-emerald-900">{{ stats.active_teachers }}</div>
                                <span class="ml-2 text-xs font-bold text-emerald-700 bg-white px-2 py-0.5 rounded-full">Past 15 mins</span>
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>

            <!-- Students Stats -->
            <div class="bg-gradient-to-br from-purple-50 to-fuchsia-100 overflow-hidden shadow-sm rounded-xl border border-purple-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center">
                    <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-purple-100">
                        🎓
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-bold text-purple-800 truncate">Total Students</dt>
                            <dd class="flex items-baseline"><div class="text-2xl font-black text-purple-900">{{ stats.total_students }}</div></dd>
                        </dl>
                    </div>
                </div>
            </div>

            <div class="bg-gradient-to-br from-emerald-50 to-teal-100 overflow-hidden shadow-sm rounded-xl border border-emerald-200 p-5 hover:shadow-md transition-shadow">
                <div class="flex items-center">
                    <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-emerald-100">
                        🚀
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-bold text-emerald-800 truncate">Active Students</dt>
                            <dd class="flex items-baseline">
                                <div class="text-2xl font-black text-emerald-900">{{ stats.active_students }}</div>
                                <span class="ml-2 text-xs font-bold text-emerald-700 bg-white px-2 py-0.5 rounded-full">Past 15 mins</span>
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>"""

content = cards_pattern.sub(new_cards + r'\2', content)

# 2. Update the tables to include Admin table and Password columns
tables_pattern = re.compile(r'<!-- Active Users Tables -->.*?</div>\s*<!-- System Files & Media -->', re.DOTALL)

new_tables = """<!-- Active Users Tables -->
    <div class="grid grid-cols-1 gap-8">
        
        <!-- Admins Table -->
        <div class="bg-white shadow-sm rounded-xl border border-red-100 overflow-hidden">
            <div class="px-6 py-4 border-b border-red-100 bg-red-50 flex items-center justify-between">
                <h3 class="text-lg font-bold text-red-800">👑 Admin Activity</h3>
                <span class="text-xs font-bold text-red-600 bg-white px-2 py-1 rounded-full border border-red-200">Admins Only View</span>
            </div>
            <div class="max-h-64 overflow-y-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-white sticky top-0 shadow-sm z-10">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Admin</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Status</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Last Active</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-red-500 uppercase tracking-wider bg-gray-50"><i class="fa-solid fa-key mr-1"></i>Password</th>
                            <th scope="col" class="relative px-6 py-3 bg-gray-50"><span class="sr-only">Actions</span></th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-100">
                        {% for t in active_admins %}
                        <tr class="hover:bg-red-50/50 transition-colors">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                <div class="text-xs text-gray-500">{{ t.email }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 mt-1.5 animate-pulse"></span> Active
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-500">Just now</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-red-600 bg-red-50">{{ t.password }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"></td>
                        </tr>
                        {% endfor %}
                        {% for t in inactive_admins %}
                        <tr class="hover:bg-gray-50 opacity-80 transition-colors">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                <div class="text-xs text-gray-500">{{ t.email }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-800 border border-gray-200">
                                    <span class="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1.5 mt-1.5"></span> Inactive
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ t.last_active }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-gray-600 bg-gray-50">{{ t.password }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Teachers Table -->
        <div class="bg-white shadow-sm rounded-xl border border-blue-100 overflow-hidden">
            <div class="px-6 py-4 border-b border-blue-100 bg-blue-50 flex items-center justify-between">
                <h3 class="text-lg font-bold text-blue-800">👨‍🏫 Teacher Activity</h3>
            </div>
            <div class="max-h-64 overflow-y-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-white sticky top-0 shadow-sm z-10">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Teacher</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Status</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Last Active</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-blue-500 uppercase tracking-wider bg-gray-50"><i class="fa-solid fa-key mr-1"></i>Password</th>
                            <th scope="col" class="relative px-6 py-3 bg-gray-50"><span class="sr-only">Actions</span></th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-100">
                        {% for t in active_teachers %}
                        <tr class="hover:bg-blue-50/50 transition-colors">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                <div class="text-xs text-gray-500">{{ t.email }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 mt-1.5 animate-pulse"></span> Active
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-500">Just now</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-blue-600 bg-blue-50">{{ t.password }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button onclick="openResetModal('teacher', '{{ t.id }}', '{{ t.name }}')" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                            </td>
                        </tr>
                        {% endfor %}
                        {% for t in inactive_teachers %}
                        <tr class="hover:bg-gray-50 opacity-80 transition-colors">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                <div class="text-xs text-gray-500">{{ t.email }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-800 border border-gray-200">
                                    <span class="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1.5 mt-1.5"></span> Inactive
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ t.last_active }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-gray-600 bg-gray-50">{{ t.password }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button onclick="openResetModal('teacher', '{{ t.id }}', '{{ t.name }}')" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                            </td>
                        </tr>
                        {% endfor %}
                        {% if not active_teachers and not inactive_teachers %}
                        <tr><td colspan="5" class="px-6 py-8 text-center text-gray-500 font-bold">No teachers registered.</td></tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Students Table -->
        <div class="bg-white shadow-sm rounded-xl border border-purple-100 overflow-hidden">
            <div class="px-6 py-4 border-b border-purple-100 bg-purple-50 flex items-center justify-between">
                <h3 class="text-lg font-bold text-purple-800">🎓 Student Activity</h3>
            </div>
            <div class="max-h-64 overflow-y-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-white sticky top-0 shadow-sm z-10">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Student</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Status</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider bg-gray-50">Last Active</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-purple-500 uppercase tracking-wider bg-gray-50"><i class="fa-solid fa-key mr-1"></i>Password</th>
                            <th scope="col" class="relative px-6 py-3 bg-gray-50"><span class="sr-only">Actions</span></th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-100">
                        {% for s in active_students %}
                        <tr class="hover:bg-purple-50/50 transition-colors">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-bold text-gray-900">{{ s.name }} ({{ s.student_id }})</div>
                                <div class="text-xs text-gray-500">{{ s.email }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 mt-1.5 animate-pulse"></span> Active
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-500">Just now</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-purple-600 bg-purple-50">{{ s.password }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button onclick="openResetModal('student', '{{ s.id }}', '{{ s.name }}')" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                            </td>
                        </tr>
                        {% endfor %}
                        {% for s in inactive_students %}
                        <tr class="hover:bg-gray-50 opacity-80 transition-colors">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="text-sm font-bold text-gray-900">{{ s.name }} ({{ s.student_id }})</div>
                                <div class="text-xs text-gray-500">{{ s.email }}</div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-800 border border-gray-200">
                                    <span class="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1.5 mt-1.5"></span> Inactive
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ s.last_active }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono font-bold text-gray-600 bg-gray-50">{{ s.password }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <button onclick="openResetModal('student', '{{ s.id }}', '{{ s.name }}')" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                            </td>
                        </tr>
                        {% endfor %}
                        {% if not active_students and not inactive_students %}
                        <tr><td colspan="5" class="px-6 py-8 text-center text-gray-500 font-bold">No students registered.</td></tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>

    </div>
    
    <!-- System Files & Media -->"""

content = tables_pattern.sub(new_tables, content)

with open('templates/admin_dashboard.html', 'w') as f:
    f.write(content)
