// Profile picture preview
document.addEventListener('DOMContentLoaded', function() {
    // Register page profile pic preview
    const profilePicInput = document.getElementById('id_profile_pic');
    if (profilePicInput) {
        profilePicInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    const preview = document.getElementById('profile-pic-preview');
                    if (preview) {
                        preview.src = event.target.result;
                    } else {
                        // Create preview if it doesn't exist
                        const container = document.createElement('div');
                        container.className = 'profile-pic-container mt-3';
                        container.innerHTML = `
                            <img id="profile-pic-preview" src="${event.target.result}" alt="Profile preview" class="img-fluid">
                            <div class="profile-pic-overlay">Change Photo</div>
                        `;
                        profilePicInput.parentNode.appendChild(container);
                    }
                }
                reader.readAsDataURL(file);
            }
        });
    }

    // Profile page edit toggle
    const editProfileBtn = document.getElementById('edit-profile-btn');
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', function() {
            const form = document.getElementById('profile-form');
            const displayFields = document.querySelectorAll('.profile-display');
            const editFields = document.querySelectorAll('.profile-edit');
            
            displayFields.forEach(field => field.classList.toggle('d-none'));
            editFields.forEach(field => field.classList.toggle('d-none'));
            
            if (form.classList.contains('d-none')) {
                form.classList.remove('d-none');
                this.textContent = 'Cancel';
            } else {
                form.classList.add('d-none');
                this.textContent = 'Edit Profile';
            }
        });
    }

    // Password toggle
    const togglePassword = document.querySelector('.toggle-password');
    if (togglePassword) {
        togglePassword.addEventListener('click', function() {
            const passwordInput = document.getElementById(this.dataset.target);
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.classList.toggle('fa-eye');
            this.classList.toggle('fa-eye-slash');
        });
    }
});

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            const requiredFields = form.querySelectorAll('[required]');
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                const firstInvalid = form.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
        });
    }
}

// Initialize validation for forms
validateForm('register-form');
validateForm('login-form');
validateForm('profile-form');