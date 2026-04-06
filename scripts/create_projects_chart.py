#!/usr/bin/env python3
"""
Create a line chart showing spending over time for major NYC tech projects.
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif']
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False

# Fiscal years
years = ['FY16', 'FY17', 'FY18', 'FY19', 'FY20', 'FY21', 'FY22', 'FY23', 'FY24', 'FY25']

# Data from budget codes (in millions)
projects = {
    'NYC Cyber Command': [9.5, 10.8, 8.4, 25.9, 43.1, 73.2, 94.4, 116.4, 97.1, 85.4],
    'DOB NOW': [0.01, 4.0 + 0.02, 13.6 + 0.01, 7.5 + 6.2, 4.5 + 11.3, 6.8 + 12.9, 0.5 + 8.2, 2.7 + 11.2, 1.7 + 11.6, 3.9 + 7.7],
    'PASSPort': [0, 11.5, 4.6, 15.0, 14.2, 8.9, 11.1, 11.7, 9.8, 3.4],
    'CityTime': [7.8, 9.5, 8.4, 7.0, 7.7, 9.1, 9.6, 8.1, 9.5, 9.3],
    'MyCity': [0, 0, 0, 0, 0, 0, 0, 6.0, 27.6, 19.1],
    '311 (IT vendors)': [14.2 * 0.15, 15.4 * 0.15, 17.2 * 0.15, 19.9 * 0.15, 23.1 * 0.15, 38.1 * 0.15, 37.9 * 0.15, 38.0 * 0.15, 34.3 * 0.15, 34.2 * 0.15],
}

# Warm color palette
colors = ['#c44e52', '#dd8452', '#da8bc3', '#8c8c8c', '#937860', '#ccb974']

# Create figure with warm background
fig, ax = plt.subplots(figsize=(11, 6.5))
fig.patch.set_facecolor('#fafafa')
ax.set_facecolor('#fafafa')

# Plot each project
for (name, values), color in zip(projects.items(), colors):
    ax.plot(years, values, marker='o', linewidth=2.5, markersize=7, label=name, color=color, alpha=0.9)

# Formatting
ax.set_xlabel('Fiscal Year', fontsize=11, color='#444')
ax.set_ylabel('Spending ($ millions)', fontsize=11, color='#444')
ax.set_title('NYC Major Tech Project Spending', fontsize=16, fontweight='600', color='#222', pad=20)
ax.tick_params(colors='#666', labelsize=10)
ax.legend(loc='upper left', fontsize=10, frameon=True, facecolor='white', edgecolor='#ddd', framealpha=0.95)
ax.grid(True, alpha=0.4, color='#ccc', linestyle='-', linewidth=0.5)
ax.set_ylim(bottom=0)

# Softer spines
ax.spines['bottom'].set_color('#aaa')
ax.spines['left'].set_color('#aaa')

# Add note
fig.text(0.12, 0.02, 'Source: Checkbook NYC (FY2016–2025). DOB NOW combines budget codes 6111 + NOW2. 311 shows IT vendors only (~15% of total).',
         fontsize=8.5, color='#888', style='italic')

plt.tight_layout()
plt.subplots_adjust(bottom=0.12)
plt.savefig('data/outputs/project_spending_chart.png', dpi=150, bbox_inches='tight', facecolor='#fafafa')
plt.savefig('data/outputs/project_spending_chart.svg', bbox_inches='tight', facecolor='#fafafa')
print("Charts saved to data/outputs/project_spending_chart.png and .svg")
