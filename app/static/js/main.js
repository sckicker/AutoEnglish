document.addEventListener('DOMContentLoaded', () => {
    const startQuizBtn = document.getElementById('start-quiz-btn');
    const submitQuizBtn = document.getElementById('submit-quiz-btn');
    const restartQuizBtn = document.getElementById('restart-quiz-btn');
    const quizArea = document.getElementById('quiz-area');
    const resultsArea = document.getElementById('results-area');
    const questionsContainer = document.getElementById('questions-container');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessageDiv = document.getElementById('error-message');
    const lessonSelectorForm = document.getElementById('lesson-selector');

    let currentQuizData = []; // To store questions from backend
    let userAnswers = {}; // To store user's answers {id: answer}

    function showLoading(show) {
        loadingIndicator.classList.toggle('hidden', !show);
    }
     function showError(message) {
        errorMessageDiv.textContent = message;
        errorMessageDiv.classList.remove('hidden');
    }
    function hideError() {
        errorMessageDiv.classList.add('hidden');
    }


    function getSelectedLessons() {
        const checkboxes = lessonSelectorForm.querySelectorAll('input[name="lesson"]:checked');
        return Array.from(checkboxes).map(cb => cb.value).join(',');
    }

    async function startQuiz() {
        hideError(); // Clear previous errors
        const lessons = getSelectedLessons();
        if (!lessons) {
            showError('请至少选择一个课程！');
            return;
        }
        const count = document.getElementById('num-questions').value;
        const type = document.getElementById('quiz-type').value;

        lessonSelectorForm.classList.add('hidden'); // Hide selection form
        resultsArea.classList.add('hidden'); // Hide previous results
        quizArea.classList.remove('hidden');
        questionsContainer.innerHTML = ''; // Clear previous questions
        showLoading(true);


        try {
            const response = await fetch(`/api/quiz?lessons=${lessons}&count=${count}&type=${type}`);
            showLoading(false);

            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorMsg;
                } catch (e) { /* Ignore if response is not JSON */ }
                throw new Error(errorMsg);
            }

            currentQuizData = await response.json();

            if (currentQuizData.length === 0) {
                showError('未找到所选课程的词汇，或没有题目生成。请尝试其他课程。');
                quizArea.classList.add('hidden');
                lessonSelectorForm.classList.remove('hidden'); // Show form again
                return;
            }

            displayQuestions();
            submitQuizBtn.classList.remove('hidden'); // Show submit button

        } catch (error) {
            console.error('Error starting quiz:', error);
            showError(`开始测试失败: ${error.message}`);
            quizArea.classList.add('hidden'); // Hide quiz area on error
            lessonSelectorForm.classList.remove('hidden'); // Show form again
        }
    }

    function displayQuestions() {
        questionsContainer.innerHTML = ''; // Clear loading/previous
        userAnswers = {}; // Reset answers

        currentQuizData.forEach((q, index) => {
            const div = document.createElement('div');
            div.className = 'question';
            div.innerHTML = `
                <p><strong>题目 ${index + 1} (Lesson ${q.lesson}):</strong> ${q.question}</p>
                <input type="text" id="answer-${q.id}" data-question-id="${q.id}" placeholder="请在此输入答案">
            `;
            questionsContainer.appendChild(div);

            // Add event listener for Enter key submission within input field
            const inputField = div.querySelector(`#answer-${q.id}`);
             inputField.addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault(); // Prevent default form submission
                    // Optional: Move focus to next input or submit if last question
                    const nextInput = questionsContainer.querySelector(`#answer-${currentQuizData[index+1]?.id}`);
                    if(nextInput) {
                        nextInput.focus();
                    } else if (index === currentQuizData.length -1) {
                        // If it's the last question, submit the quiz
                         submitQuiz();
                    }
                }
            });
        });
         // Focus the first input field
         const firstInput = questionsContainer.querySelector('input[type="text"]');
         if (firstInput) {
             firstInput.focus();
         }
    }

     function submitQuiz() {
        // Collect answers from input fields
        currentQuizData.forEach(q => {
            const inputElement = document.getElementById(`answer-${q.id}`);
            if (inputElement) {
                userAnswers[q.id] = inputElement.value.trim();
            }
        });

        // Simple client-side scoring (backend validation recommended for real apps)
        let score = 0;
        const incorrectList = document.getElementById('incorrect-list');
        incorrectList.innerHTML = ''; // Clear previous incorrect list

        currentQuizData.forEach(q => {
            const userAnswer = userAnswers[q.id] || "";
            // Case-insensitive comparison, adjust if needed
            const isCorrect = userAnswer.toLowerCase() === q.correct_answer.toLowerCase();

            if (isCorrect) {
                score++;
            } else {
                const li = document.createElement('li');
                li.innerHTML = `
                    题目 (L${q.lesson}): ${q.question} <br>
                    <span class="incorrect">你的答案: ${userAnswer || "<i>未作答</i>"}</span> <br>
                    <span class="correct">正确答案: ${q.correct_answer}</span>
                `;
                incorrectList.appendChild(li);
            }
             // Optional: Provide visual feedback on the input field itself
            const inputElement = document.getElementById(`answer-${q.id}`);
            if(inputElement) {
                inputElement.disabled = true; // Disable after submitting
                inputElement.style.backgroundColor = isCorrect ? '#e6ffe6' : '#ffe6e6';
                inputElement.style.borderColor = isCorrect ? 'green' : 'red';
            }
        });

        // Display results
        document.getElementById('score').textContent = score;
        document.getElementById('total-questions').textContent = currentQuizData.length;
        // quizArea.classList.add('hidden'); // Keep quiz visible with feedback
        submitQuizBtn.classList.add('hidden'); // Hide submit button after scoring
        resultsArea.classList.remove('hidden');
        resultsArea.scrollIntoView({ behavior: 'smooth' }); // Scroll to results
    }

    function restartQuiz() {
        resultsArea.classList.add('hidden');
        quizArea.classList.add('hidden');
        lessonSelectorForm.classList.remove('hidden');
        currentQuizData = [];
        userAnswers = {};
        hideError();
    }


    // Event Listeners
    if (startQuizBtn) {
        startQuizBtn.addEventListener('click', startQuiz);
    }
    if (submitQuizBtn) {
        submitQuizBtn.addEventListener('click', submitQuiz);
    }
     if (restartQuizBtn) {
        restartQuizBtn.addEventListener('click', restartQuiz);
    }

});