
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import (
    PasswordResetView, 
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetCompleteView
)
from .forms import (
    RegistrationForm, 
    LoginForm, 
    ProfileUpdateForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm
)
from django.urls import reverse_lazy

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = RegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('index')

@login_required
def profile(request):
    # --- Start of new progress calculation logic ---
    # Example: progress may be an attribute or fetched from elsewhere.
    progress = getattr(request.user, "progress", None)
    # Below is a placeholder structure; use your real logic to populate 'progress'
    # Example: progress = ProfileProgress(user=request.user) if you have such a class.
    if progress:
        total_xp = getattr(progress, "total_xp", 0)
        level = getattr(progress, "level", 1)
        # Compute values for template
        xp_in_level = total_xp % 1000
        xp_percent = xp_in_level / 10  # percent for 0-1000 xp
        xp_to_next_level = 1000 - xp_in_level
    else:
        total_xp = 0
        level = 1
        xp_in_level = 0
        xp_percent = 0
        xp_to_next_level = 1000

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    context = {
        'form': form,
        'progress': progress,
        'total_xp': total_xp,
        'level': level,
        'xp_in_level': xp_in_level,
        'xp_percent': xp_percent,
        'xp_to_next_level': xp_to_next_level,
    }
    return render(request, 'accounts/profile.html', context)

class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = CustomSetPasswordForm
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
