// static/js/quiz_logic.js V1.2 - Wrapped in DOMContentLoaded, Exposes Interface
// ==========================
// Shared JavaScript logic for handling quizzes on the NCE platform.
// This file should be included in base.html *before* the scripts_extra block.
// ==========================

// --- Global Quiz State Variables (Defined outside DOMContentLoaded is okay) ---
let currentQuizData = null; // Holds the array of question objects {id, lesson, question, part_of_speech, correct_answer}
let userAnswers = {};       // Stores user's input keyed by vocabulary ID { vocab_id: "user's answer" }
let quizContext = {};       // Stores info about the quiz { lesson_ids: [], quiz_type: "", question_ids: [] }

// --- Wait for the DOM to be fully loaded before executing ---
document.addEventListener('DOMContentLoaded', () => {

    console.log("quiz_logic.js: DOMContentLoaded event fired.");

    // --- DOM Element References (Fetch INSIDE DOMContentLoaded) ---
    const quizArea = document.getElementById('quiz-area');
    const questionsContainer = document.getElementById('questions-container');
    const submitQuizBtn = document.getElementById('submit-quiz-btn');
    const resultsArea = document.getElementById('results-area');
    const scoreSpan = document.getElementById('score');
    const totalQuestionsSpan = document.getElementById('total-questions');
    const incorrectListUl = document.getElementById('incorrect-list');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorDiv = document.getElementById('error-message');

    // Optional: Check if essential elements exist
    if (!quizArea || !questionsContainer || !submitQuizBtn || !resultsArea /* || etc */) {
        console.error("quiz_logic.js: One or more essential quiz elements not found in the DOM!");
        // Display a critical, user-facing error if needed
        // document.body.insertAdjacentHTML('afterbegin', '<div class="alert alert-danger">Quiz components missing. Please contact support.</div>');
    }

    // --- UI Helper Functions (Defined inside DOMContentLoaded) ---

    /** Shows/hides loading indicator */
    function showLoading(isLoading) {
        if (loadingIndicator) {
            loadingIndicator.classList.toggle('hidden', !isLoading);
        } else { console.warn("quiz_logic.js: Loading indicator element (#loading-indicator) not found."); }
    }

    /** Displays error message and hides quiz area */
    function showError(message) {
        console.error("quiz_logic.js: showError called with:", message);
        if (errorDiv) {
            errorDiv.textContent = `错误: ${message}`;
            errorDiv.classList.remove('hidden');
        } else { console.warn("quiz_logic.js: Error message element (#error-message) not found."); alert(`错误: ${message}`); }
        if (quizArea) { // Hide quiz area on error
            quizArea.classList.add('hidden');
        }
        showLoading(false); // Ensure loading is hidden
    }

    /** Hides error message */
    function hideError() {
        if (errorDiv) {
            errorDiv.classList.add('hidden');
            errorDiv.textContent = '';
        }
    }

    // --- Core Quiz Logic Functions (Defined inside DOMContentLoaded) ---

    /** Renders quiz questions */
    function displayQuestions() {
        console.log("quiz_logic.js: displayQuestions called.");
        if (!questionsContainer) { showError("问题区域丢失 (#questions-container)。"); return; }
        if (!currentQuizData || currentQuizData.length === 0) { showError("无测验问题可显示。"); return; }

        hideError();
        questionsContainer.innerHTML = '';
        userAnswers = {}; // Reset answers

        currentQuizData.forEach((question, index) => {
            const questionDiv = document.createElement('div'); questionDiv.classList.add('card', 'mb-3');
            const cardBody = document.createElement('div'); cardBody.classList.add('card-body');
            const questionLabel = document.createElement('label'); const inputId = `answer-${question.id}`;
            questionLabel.setAttribute('for', inputId); questionLabel.classList.add('card-title','form-label','h5','mb-2');
            const posText = question.part_of_speech ? ` <span class="badge bg-info fw-normal">${question.part_of_speech}</span>` : '';
            questionLabel.innerHTML = `${index + 1}. ${question.question}${posText}:`;
            const answerInput = document.createElement('input'); answerInput.setAttribute('type', 'text');
            answerInput.setAttribute('id', inputId); answerInput.setAttribute('name', inputId);
            answerInput.setAttribute('data-vocab-id', question.id); answerInput.classList.add('form-control','form-control-sm');
            answerInput.setAttribute('autocomplete', 'off');
            cardBody.appendChild(questionLabel); cardBody.appendChild(answerInput);
            questionDiv.appendChild(cardBody); questionsContainer.appendChild(questionDiv);
        });

        console.log(`quiz_logic.js: Displayed ${currentQuizData.length} questions.`);
        // Ensure quiz area and submit button are visible AFTER questions are added
        if (quizArea) quizArea.classList.remove('hidden');
        if (submitQuizBtn) submitQuizBtn.classList.remove('hidden');
        const firstInput = questionsContainer.querySelector('input[type="text"]'); if (firstInput) firstInput.focus();
    }

    /** Collects user answers */
    function collectAnswers() {
        console.log("quiz_logic.js: collectAnswers called."); userAnswers = {};
        if (!questionsContainer) { console.error("Cannot collect answers: container missing."); return; }
        const inputs = questionsContainer.querySelectorAll('input[type="text"][data-vocab-id]');
        inputs.forEach(input => { const vocabId = input.dataset.vocabId; if (vocabId) { userAnswers[vocabId] = input.value.trim(); } });
        console.log("quiz_logic.js: Answers collected:", userAnswers);
    }

    /** Submits quiz to backend */
    async function submitQuiz() {
        console.log("quiz_logic.js: submitQuiz called."); collectAnswers();
        // --- Pre-submission Checks ---
        if (!currentQuizData || !quizContext || !quizContext.question_ids) { showError("测验数据或上下文丢失。"); return; }
        if (Object.keys(userAnswers).length === 0 && currentQuizData.length > 0) { showError("未收集到答案。"); return; }
        if (quizContext.question_ids.length !== currentQuizData.length) { quizContext.question_ids = currentQuizData.map(q => q.id); }
        // --- End Checks ---
        showLoading(true); hideError(); if (submitQuizBtn) submitQuizBtn.disabled = true;
        const payload = { answers: userAnswers, quiz_context: quizContext };
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
        if (csrfToken) { headers['X-CSRFToken'] = csrfToken; } else { console.warn("quiz_logic.js: CSRF Token not found for submit."); }
        try {
            const response = await fetch('/api/submit_quiz', { method: 'POST', headers: headers, body: JSON.stringify(payload) });
            showLoading(false); // Hide loading after fetch returns
            if (!response.ok) { let eMsg = `提交失败 (${response.status})`; try {const eD = await response.json(); eMsg = eD.error || eMsg;} catch(e){} throw new Error(eMsg); }
            const results = await response.json(); console.log("quiz_logic.js: Results received:", results); displayResults(results);
        } catch (error) { console.error('quiz_logic.js: Error submitting:', error); showError(`提交出错: ${error.message}`); showLoading(false); if (submitQuizBtn) submitQuizBtn.disabled = false; }
    }

    /** Displays quiz results */
    function displayResults(results) {
        console.log("quiz_logic.js: displayResults called."); showLoading(false);
        if (!resultsArea || !scoreSpan || !totalQuestionsSpan || !incorrectListUl) { showError("无法显示结果区域。"); return; }
        if (quizArea) quizArea.classList.add('hidden'); resultsArea.classList.remove('hidden'); if (submitQuizBtn) submitQuizBtn.classList.add('hidden');
        scoreSpan.textContent = results.score ?? '?'; totalQuestionsSpan.textContent = results.total_questions ?? '?';
        incorrectListUl.innerHTML = ''; const incorrectTitle = document.getElementById('incorrect-title');
        if (results.wrong_answers && results.wrong_answers.length > 0) {
            if(incorrectTitle) incorrectTitle.textContent = '错题回顾:';
            results.wrong_answers.forEach(item => {
                const li = document.createElement('li');
                li.classList.add('list-group-item', 'd-flex', 'justify-content-between', 'align-items-start');
                li.innerHTML = `
                    <div class="ms-2 me-auto">
                      <div class="fw-bold">${item.question} <span class="badge bg-secondary fw-normal">${item.part_of_speech || ''}</span></div>
                      <span class="text-danger small">你的答案: ${item.user_answer !== null && item.user_answer !== '' ? item.user_answer : '<em>(未作答)</em>'}</span>
                      <br>
                      <span class="text-success small">正确答案: ${item.correct_answer}</span>
                    </div>`;
                incorrectListUl.appendChild(li);
            });
        } else {
            if(incorrectTitle) incorrectTitle.textContent = '测试结果:';
            const li = document.createElement('li'); li.classList.add('list-group-item','text-success','fw-bold');
            li.innerHTML = '<i class="bi bi-check-circle-fill"></i> 恭喜，全部回答正确！';
            incorrectListUl.appendChild(li);
        }
        const restartBtn = resultsArea.querySelector('#restart-quiz-btn'); if (restartBtn) { restartBtn.classList.remove('hidden'); restartBtn.disabled = false; }
        console.log("quiz_logic.js: Results displayed.");
    }

    /** Resets the UI */
    function resetQuizUI() {
        console.log("quiz_logic.js: resetQuizUI called.");
        if (quizArea) quizArea.classList.add('hidden'); if (resultsArea) resultsArea.classList.add('hidden');
        if (questionsContainer) questionsContainer.innerHTML = ''; if (incorrectListUl) incorrectListUl.innerHTML = '';
        if (scoreSpan) scoreSpan.textContent = ''; if (totalQuestionsSpan) totalQuestionsSpan.textContent = '';
        if (submitQuizBtn) { submitQuizBtn.classList.add('hidden'); submitQuizBtn.disabled = false; }
        const startIdxBtn = document.getElementById('start-quiz-btn'); if (startIdxBtn) startIdxBtn.disabled = false;
        const startLsBtn = document.getElementById('start-lesson-quiz-btn'); if (startLsBtn) startLsBtn.disabled = false;
        hideError(); showLoading(false);
        // Reset global state variables
        currentQuizData = null; userAnswers = {}; quizContext = {};
        console.log("quiz_logic.js: Quiz UI reset complete.");
    }

    // --- Global Event Listeners (Submit Button) ---
    if (submitQuizBtn) {
        submitQuizBtn.addEventListener('click', submitQuiz);
        console.log("quiz_logic.js: Global listener attached to submitQuizBtn.");
    } else {
        console.warn("quiz_logic.js: Submit quiz button not found during init. Listener not attached globally.");
    }

    // --- Expose necessary functions to the global scope (window object) ---
    // This makes them accessible to the inline scripts in lesson_text.html or index.html
    window.quizLogic = {
        showLoading,
        showError,
        hideError,
        displayQuestions,
        collectAnswers,
        submitQuiz,
        displayResults,
        resetQuizUI
        // We expose the functions, page-specific scripts will set the global state vars like quizContext
    };
    console.log("quiz_logic.js: Core functions exposed on window.quizLogic");

}); // --- End of DOMContentLoaded listener ---

// --- End of quiz_logic.js ---