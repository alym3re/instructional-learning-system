// Question Type UI Management
document.addEventListener("DOMContentLoaded", function() {
    const questionTypeSelect = document.getElementById("id_question_type") || document.getElementById("id_real_question_type");
    if (questionTypeSelect) {
        function updateAnswerWidgets() {
            let qtype = questionTypeSelect.value || questionTypeSelect.getAttribute('value');
            if (!qtype) return;

            // Hide all answer input areas first
            ['answers-area', 'id_correct_answer', 'id_answers_list'].forEach((id) => {
                let el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });

            // Show the appropriate input area based on question type
            if (qtype === 'multiple_choice' || qtype === 'true_false') {
                let area = document.getElementById('answers-area');
                if (area) area.style.display = '';
            } else if (qtype === 'identification') {
                let ans = document.getElementById('id_correct_answer');
                if (ans) ans.parentNode.style.display = '';
            } else if (qtype === 'fill_in_the_blanks') {
                let ans = document.getElementById('id_answers_list');
                if (ans) ans.parentNode.style.display = '';
            }
        }

        // Add event listener for SELECT elements
        if (questionTypeSelect.tagName === "SELECT") {
            questionTypeSelect.addEventListener("change", updateAnswerWidgets);
        }
        
        // Initialize UI based on current selection
        updateAnswerWidgets();
    }
});

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

// Form validation for question forms
document.addEventListener('DOMContentLoaded', function() {
    const questionForm = document.getElementById('question-form');
    if (questionForm) {
        questionForm.addEventListener('submit', function(e) {
            const questionType = document.getElementById('id_question_type').value;
            let isValid = true;
            let errorMessage = '';
            
            // Validate based on question type
            if (questionType === 'multiple_choice') {
                const choices = document.querySelectorAll('.choice-input');
                const correctAnswers = document.querySelectorAll('input[name="correct_answer"]:checked');
                
                if (choices.length < 2) {
                    isValid = false;
                    errorMessage = 'Multiple choice questions must have at least 2 choices.';
                } else if (correctAnswers.length === 0) {
                    isValid = false;
                    errorMessage = 'Please select a correct answer.';
                }
            } else if (questionType === 'identification') {
                const answer = document.getElementById('id_correct_answer').value.trim();
                if (!answer) {
                    isValid = false;
                    errorMessage = 'Please provide the correct answer for this identification question.';
                }
            } else if (questionType === 'fill_in_the_blanks') {
                const answers = document.getElementById('id_answers_list').value.trim();
                if (!answers) {
                    isValid = false;
                    errorMessage = 'Please provide at least one acceptable answer.';
                }
            }
            
            if (!isValid) {
                e.preventDefault();
                alert(errorMessage);
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

// Enhanced feedback for question management
function showFeedback(message, isSuccess = true) {
    const feedbackDiv = document.getElementById('feedback-message') || 
                        document.createElement('div');
    
    if (!document.getElementById('feedback-message')) {
        feedbackDiv.id = 'feedback-message';
        document.querySelector('.container').prepend(feedbackDiv);
    }
    
    feedbackDiv.textContent = message;
    feedbackDiv.className = isSuccess ? 'alert alert-success' : 'alert alert-danger';
    feedbackDiv.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        feedbackDiv.style.display = 'none';
    }, 5000);
}

// Update deleteExamQuestion to use the feedback system
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
                showFeedback('Question successfully removed from exam');
            } else {
                showFeedback(data.error || 'Failed to remove question', false);
            }
        })
        .catch(error => {
            showFeedback('An error occurred while processing your request', false);
            console.error('Error:', error);
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
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFeedback('Question order updated successfully');
                } else {
                    showFeedback(data.error || 'Failed to update question order', false);
                }
            })
            .catch(error => {
                showFeedback('An error occurred while updating question order', false);
                console.error('Error:', error);
            });
        }
    });
    
    // Add dynamic choice management for multiple choice questions
    const addChoiceBtn = document.getElementById('add-choice-btn');
    if (addChoiceBtn) {
        addChoiceBtn.addEventListener('click', function() {
            const choicesContainer = document.getElementById('choices-container');
            const choiceCount = choicesContainer.querySelectorAll('.choice-row').length;
            
            const newRow = document.createElement('div');
            newRow.className = 'choice-row form-group row';
            newRow.innerHTML = `
                <div class="col-1">
                    <input type="radio" name="correct_answer" value="${choiceCount}" class="form-check-input">
                </div>
                <div class="col-10">
                    <input type="text" name="choice_${choiceCount}" class="form-control choice-input" placeholder="Enter choice text">
                </div>
                <div class="col-1">
                    <button type="button" class="btn btn-danger remove-choice-btn">×</button>
                </div>
            `;
            
            choicesContainer.appendChild(newRow);
            
            // Add event listener to the new remove button
            newRow.querySelector('.remove-choice-btn').addEventListener('click', function() {
                if (choicesContainer.querySelectorAll('.choice-row').length > 2) {
                    newRow.remove();
                } else {
                    showFeedback('Multiple choice questions must have at least 2 choices', false);
                }
            });
        });
    }
});
