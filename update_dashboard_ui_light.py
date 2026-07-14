import re

with open('templates/admin_dashboard.html', 'r') as f:
    content = f.read()

new_dashboard = """    <!-- Dashboard View -->
    <div id="view-dashboard" class="view-section">
        <!-- Analytics Overview -->
        <div class="mb-8">
            <h2 class="text-xl font-bold text-gray-900 mb-4">User Activity Stats</h2>
            
            <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 mb-8">
                <!-- Admins Stats -->
                <div class="bg-gradient-to-br from-red-50 to-rose-100 overflow-hidden shadow-sm rounded-xl border border-red-200 p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-red-100">
                            💎
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-bold text-red-800 truncate">Total Admins</dt>
                                <dd class="flex items-baseline"><div class="text-2xl font-black text-red-900">{{ stats.total_admins }}</div></dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <div class="bg-gradient-to-br from-blue-50 to-indigo-100 overflow-hidden shadow-sm rounded-xl border border-blue-200 p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-blue-100">
                            🛡️
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-bold text-blue-800 truncate">Active Admins</dt>
                                <dd class="flex items-baseline">
                                    <div class="text-2xl font-black text-blue-900">{{ stats.active_admins }}</div>
                                    <span class="ml-2 text-xs font-bold text-blue-700 bg-white px-2 py-0.5 rounded-full shadow-sm">Past 15 mins</span>
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <!-- Spacer for 3 column grid to look like image, actually image has 3 top 3 bottom -->
                
                <!-- Teachers Stats -->
                <div class="bg-gradient-to-br from-blue-50 to-indigo-100 overflow-hidden shadow-sm rounded-xl border border-blue-200 p-5">
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
                
                <div class="bg-gradient-to-br from-blue-50 to-indigo-100 overflow-hidden shadow-sm rounded-xl border border-blue-200 p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-blue-100">
                            ✅
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-bold text-blue-800 truncate">Active Teachers</dt>
                                <dd class="flex items-baseline">
                                    <div class="text-2xl font-black text-blue-900">{{ stats.active_teachers }}</div>
                                    <span class="ml-2 text-xs font-bold text-blue-700 bg-white px-2 py-0.5 rounded-full shadow-sm">Past 15 mins</span>
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
                
                <!-- Students Stats -->
                <div class="bg-gradient-to-br from-purple-50 to-fuchsia-100 overflow-hidden shadow-sm rounded-xl border border-purple-200 p-5">
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

                <div class="bg-gradient-to-br from-blue-50 to-indigo-100 overflow-hidden shadow-sm rounded-xl border border-blue-200 p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 bg-white rounded-md p-3 text-2xl shadow-sm border border-blue-100">
                            🚀
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-bold text-blue-800 truncate">Active Students</dt>
                                <dd class="flex items-baseline">
                                    <div class="text-2xl font-black text-blue-900">{{ stats.active_students }}</div>
                                    <span class="ml-2 text-xs font-bold text-blue-700 bg-white px-2 py-0.5 rounded-full shadow-sm">Past 15 mins</span>
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Active Users Tables -->
        <div class="grid grid-cols-1 gap-8">
            
            <!-- Admins Table -->
            <div class="bg-white shadow-sm rounded-xl border border-red-100 overflow-hidden">
                <div class="px-6 py-4 border-b border-red-100 bg-red-50 flex items-center justify-between">
                    <h3 class="text-lg font-bold text-red-800">💎 Admin Activity</h3>
                    <span class="text-xs font-bold text-red-600 bg-white px-3 py-1 rounded-full border border-red-200 shadow-sm">Admins Only View</span>
                </div>
                <div class="max-h-64 overflow-y-auto">
                    <table class="min-w-full divide-y divide-gray-100">
                        <thead class="bg-white sticky top-0 z-10">
                            <tr>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Admin</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Status</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Last Active</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-50">
                            {% for t in active_admins %}
                            <tr class="hover:bg-red-50/30 transition-colors">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ t.email }}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-blue-50 text-blue-700">
                                        <span class="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5 mt-1.5 animate-pulse"></span> Active
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-400">Just now</td>
                            </tr>
                            {% endfor %}
                            {% for t in inactive_admins %}
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ t.email }}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-500">
                                        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1.5 mt-1.5"></span> Inactive
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">{{ t.last_active }}</td>
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
                    <span class="text-xs font-bold text-blue-600 bg-white px-3 py-1 rounded-full border border-blue-200 shadow-sm">Teacher</span>
                </div>
                <div class="max-h-64 overflow-y-auto">
                    <table class="min-w-full divide-y divide-gray-100">
                        <thead class="bg-white sticky top-0 z-10">
                            <tr>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Teacher</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Role</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Status</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Last Active</th>
                                <th scope="col" class="relative px-6 py-4"><span class="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-50">
                            {% for t in active_teachers %}
                            <tr class="hover:bg-blue-50/30 transition-colors">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ t.email }}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                                        {{ (t.custom_role if t.custom_role else 'Teacher')|capitalize }}
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-blue-50 text-blue-700">
                                        <span class="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5 mt-1.5 animate-pulse"></span> Active
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-400">Just now</td>
                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                    <button onclick="openResetModal('teacher', '{{ t.id }}', '{{ t.name }}')" class="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1.5 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                                </td>
                            </tr>
                            {% endfor %}
                            {% for t in inactive_teachers %}
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-bold text-gray-900">{{ t.name }}</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ t.email }}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-50 text-gray-600 border border-gray-200">
                                        {{ (t.custom_role if t.custom_role else 'Teacher')|capitalize }}
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-500">
                                        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1.5 mt-1.5"></span> Inactive
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">{{ t.last_active }}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                    <button onclick="openResetModal('teacher', '{{ t.id }}', '{{ t.name }}')" class="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1.5 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                                </td>
                            </tr>
                            {% endfor %}
                            {% if not active_teachers and not inactive_teachers %}
                            <tr><td colspan="5" class="px-6 py-8 text-center text-gray-400 font-bold">No teachers registered.</td></tr>
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
                    <table class="min-w-full divide-y divide-gray-100">
                        <thead class="bg-white sticky top-0 z-10">
                            <tr>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Student</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Status</th>
                                <th scope="col" class="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Last Active</th>
                                <th scope="col" class="relative px-6 py-4"><span class="sr-only">Actions</span></th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-50">
                            {% for s in active_students %}
                            <tr class="hover:bg-purple-50/30 transition-colors">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-bold text-gray-900">{{ s.name }} ({{ s.student_id }})</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ s.email }}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-blue-50 text-blue-700">
                                        <span class="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5 mt-1.5 animate-pulse"></span> Active
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-400">Just now</td>
                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                    <button onclick="openResetModal('student', '{{ s.id }}', '{{ s.name }}')" class="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1.5 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                                    <a href="{{ url_for('promotion_certificate', student_id=s.id) }}" target="_blank" class="text-amber-600 hover:text-amber-900 bg-amber-50 px-3 py-1.5 rounded-md text-xs font-bold shadow-sm ml-2">Certificate</a>
                                </td>
                            </tr>
                            {% endfor %}
                            {% for s in inactive_students %}
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-bold text-gray-900">{{ s.name }} ({{ s.student_id }})</div>
                                    <div class="text-xs text-gray-400 mt-0.5">{{ s.email }}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full bg-gray-100 text-gray-500">
                                        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 mr-1.5 mt-1.5"></span> Inactive
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">{{ s.last_active }}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                    <button onclick="openResetModal('student', '{{ s.id }}', '{{ s.name }}')" class="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1.5 rounded-md text-xs font-bold shadow-sm">Reset Password</button>
                                    <a href="{{ url_for('promotion_certificate', student_id=s.id) }}" target="_blank" class="text-amber-600 hover:text-amber-900 bg-amber-50 px-3 py-1.5 rounded-md text-xs font-bold shadow-sm ml-2">Certificate</a>
                                </td>
                            </tr>
                            {% endfor %}
                            {% if not active_students and not inactive_students %}
                            <tr><td colspan="4" class="px-6 py-8 text-center text-gray-400 font-bold">No students registered.</td></tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

    </div> <!-- Close view-dashboard -->"""

pattern = re.compile(r'<!-- Dashboard View -->.*?</div> <!-- Close view-dashboard -->', re.DOTALL)
new_content = pattern.sub(new_dashboard, content)

with open('templates/admin_dashboard.html', 'w') as f:
    f.write(new_content)

print("Updated admin_dashboard.html with light premium theme.")
