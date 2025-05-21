document.addEventListener('DOMContentLoaded', () => {
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    const htmlElement = document.documentElement;
    
    // Check for saved theme preference
    const currentTheme = localStorage.getItem('theme') || 'light';
    htmlElement.setAttribute('data-bs-theme', currentTheme);
    
    if (darkModeToggle) {
      if (currentTheme === 'dark') {
        darkModeToggle.checked = true;
      }
      
      darkModeToggle.addEventListener('change', () => {
        if (darkModeToggle.checked) {
          htmlElement.setAttribute('data-bs-theme', 'dark');
          localStorage.setItem('theme', 'dark');
        } else {
          htmlElement.setAttribute('data-bs-theme', 'light');
          localStorage.setItem('theme', 'light');
        }
      });
    }
  });