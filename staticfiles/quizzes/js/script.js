// Quiz timer functionality
function initializeQuizTimer(duration, display) {
    let timer = duration, minutes, seconds;
    const interval = setInterval(function () {
        minutes = parseInt(timer / 60, 10);
        seconds = parseInt(timer % 60, 10);

        minutes = minutes < 10 ? "0" + minutes : minutes;
        seconds = seconds < 10 ? "0" + seconds : seconds;

        display.textContent = minutes + ":" + seconds;

        if (--timer < 0) {
            clearInterval(interval);
            document.getElementById('quiz-form').submit();
        }

        // Add warning when time is running low
        if (timer < 300) { // 5 minutes
            display.classList.add('text-danger');
            display.classList.add('fw-bold');
        }
    }, 1000);
}

// Form submission handling
function setupQuizForm() {
    const form = document.getElementById('quiz-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const unanswered = document.querySelectorAll('.question-card input[type="radio"]:not(:checked)').length;
            if (unanswered > 0) {
                if (!confirm(`You have ${unanswered} unanswered question${unanswered > 1 ? 's' : ''}. Are you sure you want to submit?`)) {
                    e.preventDefault();
                }
            }
        });
    }
}

// Prevent accidental navigation
function setupBeforeUnload() {
    window.addEventListener('beforeunload', function(e) {
        const form = document.getElementById('quiz-form');
        if (form && !form.checkValidity()) {
            e.preventDefault();
            e.returnValue = 'You have unsaved answers. Are you sure you want to leave?';
        }
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize timer if on quiz page
    const timerDisplay = document.getElementById('time-remaining');
    if (timerDisplay && timerDisplay.textContent.includes(':')) {
        const timeParts = timerDisplay.textContent.split(':');
        const minutes = parseInt(timeParts[0]);
        const seconds = parseInt(timeParts[1]) || 0;
        const totalSeconds = (minutes * 60) + seconds;
        
        initializeQuizTimer(totalSeconds, timerDisplay);
    }

    // Set up form handling
    setupQuizForm();
    setupBeforeUnload();

    // Question management in admin
    document.querySelectorAll('.delete-question').forEach(btn => {
        btn.addEventListener('click', function() {
            const questionId = this.dataset.questionId;
            const quizId = this.dataset.quizId;
            
            if (confirm('Are you sure you want to delete this question?')) {
                fetch(`/quizzes/${quizId}/questions/${questionId}/delete/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Accept': 'application/json',
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById(`question-${questionId}`).remove();
                    }
                });
            }
        });
    });
});