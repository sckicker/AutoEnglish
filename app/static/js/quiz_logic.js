// static/js/quiz_logic.js
// ==========================
// Shared JavaScript logic for handling quizzes on the NCE platform.
// This file should be included in base.html *before* the scripts_extra block.
// ==========================

// --- Global Quiz State ---
let currentQuizData = null; // Holds the array of question objects {id, lesson, question, part_of_speech, correct_answer}
let userAnswers = {};       // Stores user's input { vocab_id: answer }
let quizContext = {};       // Stores info about the quiz { lesson_ids: [], quiz_type: "", question_ids: [] }

// --- DOM Element References ---
// Get references to common UI elements ONCE. Functions should check if they exist before using.
const quizArea = document.getElementById('quiz-area');
const questionsContainer = document.getElementById('questions-container');
const submitQuizBtn = document.getElementById('submit-quiz-btn');
const resultsArea = document.getElementById('results-area');
const scoreSpan = document.getElementById('score');
const totalQuestionsSpan = document.getElementById('total-questions');
const incorrectListUl = document.getElementById('incorrect-list');
const loadingIndicator = document.getElementById('loading-indicator');
const errorDiv = document.getElementById('error-message');
// Note: Restart button listener is often better placed in the template that shows the results area,
// as its specific action might depend on the context (restart lesson vs. restart index).

// Log to confirm the script is loaded
console.log("quiz_logic.js loaded.");

// --- UI Helper Functions ---

/**
 * Shows or hides the loading indicator.
 * @param {boolean} isLoading - True to show, false to hide.
 */
function showLoading(isLoading) {
    // console.log("showLoading called with:", isLoading); // Optional debug log
    if (loadingIndicator) {
        loadingIndicator.classList.toggle('hidden', !isLoading);
    } else {
        console.warn("Loading indicator element (#loading-indicator) not found.");
    }
}

/**
 * Displays an error message to the user.
 * @param {string} message - The error message to display.
 */
function showError(message) {
    console.error("showError called with:", message);
    if (errorDiv) {
        errorDiv.textContent = `错误: ${message}`;
        errorDiv.classList.remove('hidden');
    } else {
        console.warn("Error message element (#error-message) not found.");
        alert(`错误: ${message}`); // Fallback to alert if the div isn't present
    }
    showLoading(false); // Ensure loading indicator is hidden on error
}

/**
 * Hides the error message area.
 */
function hideError() {
    console.log("hideError called.");
    if (errorDiv) {
        errorDiv.classList.add('hidden');
        errorDiv.textContent = ''; // Clear previous message
    }
}

// --- Core Quiz Display and Interaction Functions ---

/**
 * Renders the quiz questions based on the global currentQuizData.
 */
function displayQuestions() {
    console.log("displayQuestions called.");
    if (!questionsContainer) {
        showError("无法找到问题显示区域 (#questions-container)。");
        console.error("displayQuestions failed: Missing questions container element.");
        return;
    }
    if (!currentQuizData || currentQuizData.length === 0) {
        showError("没有测验问题可显示。");
        console.error("displayQuestions failed: currentQuizData is empty or null.");
        if (quizArea) quizArea.classList.add('hidden'); // Hide quiz area if no questions
        return;
    }

    hideError(); // Clear previous errors before showing questions
    questionsContainer.innerHTML = ''; // Clear any previous questions
    userAnswers = {}; // Reset user answers for the new set of questions

    currentQuizData.forEach((question, index) => {
        const questionDiv = document.createElement('div');
        questionDiv.classList.add('card', 'mb-3');

        const cardBody = document.createElement('div');
        cardBody.classList.add('card-body');

        const questionLabel = document.createElement('label');
        const inputId = `answer-${question.id}`;
        questionLabel.setAttribute('for', inputId);
        questionLabel.classList.add('card-title', 'form-label', 'h5');
        const posText = question.part_of_speech ? ` (${question.part_of_speech})` : '';
        questionLabel.innerHTML = `${index + 1}. ${question.question}${posText}:`;

        const answerInput = document.createElement('input');
        answerInput.setAttribute('type', 'text');
        answerInput.setAttribute('id', inputId);
        answerInput.setAttribute('name', inputId); // Name attribute (optional for this setup)
        answerInput.setAttribute('data-vocab-id', question.id); // Store vocab ID for answer collection
        answerInput.classList.add('form-control', 'form-control-sm'); // Use smaller input fields
        answerInput.setAttribute('autocomplete', 'off'); // Disable browser autocomplete

        cardBody.appendChild(questionLabel);
        cardBody.appendChild(answerInput);
        questionDiv.appendChild(cardBody);
        questionsContainer.appendChild(questionDiv);
    });

    console.log("Questions displayed.");
    // Make sure the quiz area and submit button are visible
    if (quizArea) quizArea.classList.remove('hidden');
    if (submitQuizBtn) submitQuizBtn.classList.remove('hidden');

    // Optionally focus the first input field
    const firstInput = questionsContainer.querySelector('input[type="text"]');
    if (firstInput) {
        firstInput.focus();
    }
}

/**
 * Collects answers from the input fields into the userAnswers object.
 */
function collectAnswers() {
    console.log("collectAnswers called.");
    userAnswers = {}; // Reset before collecting
    if (!questionsContainer) {
        console.error("collectAnswers failed: Missing questions container element.");
        return;
    }

    const inputs = questionsContainer.querySelectorAll('input[type="text"][data-vocab-id]');
    inputs.forEach(input => {
        const vocabId = input.dataset.vocabId; // Get the ID stored in data-vocab-id
        if (vocabId) {
            userAnswers[vocabId] = input.value.trim(); // Store the trimmed answer value
        } else {
            console.warn("Found an input without a data-vocab-id:", input);
        }
    });
    console.log("Answers collected:", userAnswers);
}

/**
 * Submits the collected answers and quiz context to the backend API.
 */
async function submitQuiz() {
    console.log("submitQuiz called.");
    collectAnswers(); // Ensure latest answers are collected

    // --- Pre-submission Checks ---
    if (!currentQuizData || currentQuizData.length === 0) {
        showError("没有测验数据可提交。");
        console.error("submitQuiz failed: No current quiz data.");
        return;
    }
    // Check if answers object is empty but there were questions (might indicate collection issue)
    if (Object.keys(userAnswers).length === 0 && currentQuizData.length > 0) {
        // This could happen if inputs were missing data-vocab-id, etc.
        showError("未能收集到任何答案，请检查问题是否正确显示。");
        console.error("submitQuiz failed: No answers were collected.");
        return;
    }
    if (!quizContext || !quizContext.question_ids || !quizContext.lesson_ids || !quizContext.quiz_type) {
        showError("测验上下文信息丢失，无法提交结果。请刷新页面或重新开始测验。");
        console.error("submitQuiz failed: Missing essential quizContext data.", quizContext);
        return;
    }
    // Ensure question IDs in context match the current quiz data length
    if (quizContext.question_ids.length !== currentQuizData.length) {
        console.warn("Mismatch between question_ids in context and current quiz data length.", quizContext.question_ids, currentQuizData);
        // Update context question_ids to match current quiz data just before sending
        quizContext.question_ids = currentQuizData.map(q => q.id);
        console.log("Updated quizContext.question_ids:", quizContext.question_ids);
    }
    // Basic validation: Check if number of answers matches expected questions
    if (Object.keys(userAnswers).length !== quizContext.question_ids.length) {
        console.warn(`Number of answers (${Object.keys(userAnswers).length}) does not match number of questions (${quizContext.question_ids.length}). Submitting anyway.`);
        // Decide if you want to prevent submission here or let backend handle potential mismatch
    }

    showLoading(true); // Show loading indicator
    hideError();       // Hide any previous errors
    if (submitQuizBtn) submitQuizBtn.disabled = true; // Disable submit button to prevent double submissions

    // Prepare data payload for the API
    const payload = {
        answers: userAnswers,
        quiz_context: quizContext // Send collected results on success
    };

    // --- Get CSRF token for secure POST request ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const headers = {
        'Content-Type': 'application/json', // We are sending JSON data
        'Accept': 'application/json'        // We expect JSON response
    };
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken; // Add CSRF token if found
        // console.log("CSRF Token Included in submitQuiz"); // Optional debug log
    } else {
        console.warn('CSRF token meta tag not found for submitQuiz. Request might be rejected by server.');
    }
    // ---------------------------------------------

    try {
        const response = await fetch('/api/submit_quiz', { // Target API endpoint
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload) // Send data as JSON string
        });

        // Stop loading indicator once response is received
        showLoading(false);

        if (!response.ok) { // Check if response status is not 2xx
            let errorMsg = `提交失败 (${response.status} ${response.statusText})`;
            // Try to get more specific error from JSON response body
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorMsg; // Use error from JSON if available
            } catch (e) { /* Ignore if response body isn't valid JSON */ }
            throw new Error(errorMsg); // Throw error to be caught below
        }

        // If response is OK (2xx), parse the JSON results
        const results = await response.json();
        console.log("Quiz results received:", results);
        displayResults(results); // Call function to show results on the page

    } catch (error) {
        console.error('Error submitting quiz:', error);
        showError(`提交测验时出错: ${error.message}`); // Display error to user
        showLoading(false); // Ensure loading is hidden on error
        if (submitQuizBtn) submitQuizBtn.disabled = false; // Re-enable submit button on error
    }
}

/**
 * Displays the quiz results on the page.
 * @param {object} results - The results object received from the backend API.
 * Expected format: { score: N, total_questions: M, wrong_answers: [...] }
 */
function displayResults(results) {
    console.log("displayResults called.");
    showLoading(false); // Hide loading indicator first

    if (!resultsArea || !scoreSpan || !totalQuestionsSpan || !incorrectListUl) {
        showError("无法显示结果区域 - 缺少必要的 HTML 元素。");
        console.error("displayResults failed: Missing one or more result display elements.");
        return; // Cannot proceed if elements are missing
    }

    // Hide the quiz area, show the results area
    if (quizArea) quizArea.classList.add('hidden');
    resultsArea.classList.remove('hidden');
    if (submitQuizBtn) submitQuizBtn.classList.add('hidden'); // Hide submit btn after showing results

    // Populate score and total questions
    scoreSpan.textContent = results.score !== undefined ? results.score : '?';
    totalQuestionsSpan.textContent = results.total_questions !== undefined ? results.total_questions : '?';

    // Populate the list of incorrect answers
    incorrectListUl.innerHTML = ''; // Clear previous incorrect answers list
    if (results.wrong_answers && results.wrong_answers.length > 0) {
        incorrectListUl.previousElementSibling.textContent = '错题回顾:'; // Ensure title is correct
        results.wrong_answers.forEach(item => {
            const li = document.createElement('li');
            li.classList.add('list-group-item', 'd-flex', 'justify-content-between', 'align-items-start'); // Use flex for better layout

            li.innerHTML = `
                <div class="ms-2 me-auto">
                  <div class="fw-bold">${item.question} <span class="badge bg-secondary fw-normal">${item.part_of_speech || ''}</span></div>
                  <span class="text-danger small">你的答案: ${item.user_answer !== null && item.user_answer !== '' ? item.user_answer : '<em>(未作答)</em>'}</span>
                  <br>
                  <span class="text-success small">正确答案: ${item.correct_answer}</span>
                </div>
                {# Optionally add mark/category controls here later if needed directly in results #}
            `;
            incorrectListUl.appendChild(li);
        });
    } else {
        // Display a success message if all answers were correct
        incorrectListUl.previousElementSibling.textContent = '测试结果:'; // Change title if all correct
        const li = document.createElement('li');
        li.classList.add('list-group-item', 'text-success', 'fw-bold');
        li.innerHTML = '<i class="bi bi-check-circle-fill"></i> 恭喜，全部回答正确！';
        incorrectListUl.appendChild(li);
    }

    // Ensure the restart button within the results area is visible and enabled
    // The listener for this button should be attached in the page-specific script block
    const restartBtn = resultsArea.querySelector('#restart-quiz-btn');
    if (restartBtn) {
        restartBtn.classList.remove('hidden'); // Make sure it's visible
        restartBtn.disabled = false; // Make sure it's enabled
    }

    console.log("Results displayed.");
}

/**
 * Resets the quiz UI elements to their initial state (hides quiz/results, clears content).
 */
function resetQuizUI() {
    console.log("resetQuizUI called.");

    // Hide dynamic areas
    if (quizArea) quizArea.classList.add('hidden');
    if (resultsArea) resultsArea.classList.add('hidden');

    // Clear content areas
    if (questionsContainer) questionsContainer.innerHTML = '';
    if (incorrectListUl) incorrectListUl.innerHTML = '';
    if (scoreSpan) scoreSpan.textContent = '';
    if (totalQuestionsSpan) totalQuestionsSpan.textContent = '';

    // Reset buttons
    if (submitQuizBtn) {
        submitQuizBtn.classList.add('hidden');
        submitQuizBtn.disabled = false; // Re-enable for the next quiz attempt
    }

    // Re-enable start buttons
    const startIndexBtn = document.getElementById('start-index-quiz-btn'); // From index.html
    const startLessonBtn = document.getElementById('start-lesson-quiz-btn'); // From lesson_text.html
    if (startIndexBtn) startIndexBtn.disabled = false;
    if (startLessonBtn) startLessonBtn.disabled = false;

    // Hide feedback elements
    hideError();
    showLoading(false);

    // Reset state variables (optional, but good practice)
    currentQuizData = null;
    userAnswers = {};
    quizContext = {};

    console.log("Quiz UI reset completed.");
}

// --- Global Event Listeners (Minimal) ---
// It's often better to attach listeners in page-specific scripts,
// but the submit button might be considered part of the core logic.

if (submitQuizBtn) {
    submitQuizBtn.addEventListener('click', submitQuiz);
    console.log("Global listener attached to submitQuizBtn.");
} else {
    // If the button isn't in the initial DOM, delegation or later attachment is needed.
    console.warn("Submit quiz button not found on initial load. Listener not attached globally.");
    // Example using delegation (attach to a persistent parent like 'body' or 'main')
    // document.body.addEventListener('click', function(event) {
    //     if (event.target && event.target.id === 'submit-quiz-btn') {
    //         submitQuiz();
    //     }
    // });
}

// Make functions available globally if needed by inline scripts or other modules
// (Not strictly necessary if all logic is within this file and event listeners are set up correctly)
// window.displayQuestions = displayQuestions;
// window.submitQuiz = submitQuiz;
// window.resetQuizUI = resetQuizUI;
// window.quizContext = quizContext; // Exposing state globally is generally discouraged
// window.currentQuizData = currentQuizData;