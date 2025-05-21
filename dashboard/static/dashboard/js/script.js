document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Activity feed scrollbar
    const activityFeed = document.querySelector('.activity-feed');
    if (activityFeed) {
        new PerfectScrollbar(activityFeed);
    }

    // Real-time updates for admin dashboard
    if (document.querySelector('.dashboard-container.admin-dashboard')) {
        // Simulate real-time data updates
        setInterval(updateDashboardStats, 30000);
        
        // Initial update
        updateDashboardStats();
    }

    // Dark mode toggle persistence
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('change', function() {
            localStorage.setItem('darkMode', this.checked);
        });
        
        // Check for saved preference
        if (localStorage.getItem('darkMode') === 'true') {
            darkModeToggle.checked = true;
            document.documentElement.setAttribute('data-bs-theme', 'dark');
        }
    }
});

function updateDashboardStats() {
    // In a real app, this would fetch from an API endpoint
    console.log('Updating dashboard stats...');
    
    // Simulate updating active users count
    const activeUsersElement = document.querySelector('.card.bg-success .card-title');
    if (activeUsersElement) {
        const currentCount = parseInt(activeUsersElement.textContent);
        const variation = Math.floor(Math.random() * 5) - 2; // Random number between -2 and 2
        activeUsersElement.textContent = Math.max(0, currentCount + variation);
    }
}