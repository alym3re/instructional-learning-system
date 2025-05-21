// Exam Timer
function startExamTimer(duration, display) {
    let timer = duration, minutes, seconds;
    const interval = setInterval(function () {
        minutes = parseInt(timer / 60, 10);
        seconds = parseInt(timer % 60, 10);

        minutes = minutes < 10 ? "0" + minutes : minutes;
        seconds = seconds < 10 ? "0" + seconds : seconds;

        display.textContent = minutes + ":" + seconds;

        if (--timer < 0) {
            clearInterval(interval);
            document.getElementById('exam-form').submit();
        }

        // Add warning class when less than 5 minutes remain
        if (timer < 300) { // 5 minutes = 300 seconds
            display.classList.add('time-warning');
        }
    }, 1000);
}

// Initialize timer if on exam page
document.addEventListener('DOMContentLoaded', function() {
    const timerDisplay = document.getElementById('time-remaining');
    if (timerDisplay) {
        const timeParts = timerDisplay.textContent.split(':');
        const minutes = parseInt(timeParts[0]);
        const seconds = parseInt(timeParts[1]) || 0;
        const totalSeconds = (minutes * 60) + seconds;
        
        startExamTimer(totalSeconds, timerDisplay);
    }

    // Confirm before submitting exam
    const examForm = document.getElementById('exam-form');
    if (examForm) {
        examForm.addEventListener('submit', function(e) {
            const unanswered = document.querySelectorAll('.question-card input[type="radio"]:not(:checked)').length;
            if (unanswered > 0) {
                if (!confirm(`You have ${unanswered} unanswered questions. Are you sure you want to submit?`)) {
                    e.preventDefault();
                }
            }
        });
    }
});

// AJAX for exam question management
function deleteExamQuestion(questionId) {
    if (confirm('Are you sure you want to remove this question from the exam?')) {
        fetch(`/exams/${examId}/questions/${questionId}/delete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
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
}

// Make questions sortable
$(document).ready(function() {
    $('.sortable-questions').sortable({
        update: function(event, ui) {
            const order = $(this).sortable('toArray', {attribute: 'data-question-id'});
            fetch(`/exams/${examId}/questions/reorder/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({order: order})
            });
        }
    });
});