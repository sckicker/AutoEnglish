// static/js/quiz_logic.js V1.2 - Wrapped in DOMContentLoaded, Exposes Interface
// ==========================
// Shared JavaScript logic for handling quizzes on the NCE platform.
// This file should be included in base.html *before* the scripts_extra block.
// ==========================

// --- Global Quiz State Variables ---
let currentQuizData = null;
let userAnswers = {};
let quizContext = {};

// --- Wait for the DOM to be fully loaded before executing ---
document.addEventListener('DOMContentLoaded', () => {

    console.log("quiz_logic.js: DOMContentLoaded event fired.");

    // --- DOM Element References ---
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
    // if (!quizArea || !questionsContainer /* || etc */) {
    //     console.error("quiz_logic.js: One or more essential quiz elements not found!");
    // }

    // --- UI Helper Functions ---
    function showLoading(isLoading) {
        if (loadingIndicator) loadingIndicator.classList.toggle('hidden', !isLoading);
        else console.warn("quiz_logic.js: Loading indicator element (#loading-indicator) not found.");
    }

    function showError(message) {
        console.error("quiz_logic.js: showError called with:", message);
        if (errorDiv) {
            errorDiv.textContent = `错误: ${message}`;
            errorDiv.classList.remove('hidden');
        } else { console.warn("quiz_logic.js: Error message element (#error-message) not found."); alert(`错误: ${message}`); }
        if (quizArea) quizArea.classList.add('hidden');
        showLoading(false);
    }

    function hideError() {
        if (errorDiv) {
            errorDiv.classList.add('hidden');
            errorDiv.textContent = '';
        }
    }

    // --- Core Quiz Logic Functions ---
    function displayQuestions() {
        // console.log("quiz_logic.js: displayQuestions called."); // Can be noisy
        if (!questionsContainer) { showError("问题区域丢失 (#questions-container)。"); return; }
        if (!currentQuizData || currentQuizData.length === 0) { showError("无测验问题可显示。"); return; }

        hideError();
        questionsContainer.innerHTML = '';
        userAnswers = {};

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

        if (quizArea) quizArea.classList.remove('hidden');
        if (submitQuizBtn) submitQuizBtn.classList.remove('hidden');
        const firstInput = questionsContainer.querySelector('input[type="text"]'); if (firstInput) firstInput.focus();
    }

    function collectAnswers() {
        // console.log("quiz_logic.js: collectAnswers called."); // Can be noisy
        userAnswers = {};
        if (!questionsContainer) { console.error("Cannot collect answers: container missing."); return; }
        const inputs = questionsContainer.querySelectorAll('input[type="text"][data-vocab-id]');
        inputs.forEach(input => { const vocabId = input.dataset.vocabId; if (vocabId) { userAnswers[vocabId] = input.value.trim(); } });
        // console.log("quiz_logic.js: Answers collected:", userAnswers); // Can be noisy
    }

    async function submitQuiz() {
        console.log("quiz_logic.js: submitQuiz called."); collectAnswers();
        if (!currentQuizData || !quizContext || !quizContext.question_ids) { showError("测验数据或上下文丢失。"); return; }
        if (Object.keys(userAnswers).length === 0 && currentQuizData.length > 0) { showError("未收集到答案。"); return; }
        if (quizContext.question_ids.length !== currentQuizData.length) { quizContext.question_ids = currentQuizData.map(q => q.id); }

        showLoading(true); hideError(); if (submitQuizBtn) submitQuizBtn.disabled = true;
        const payload = { answers: userAnswers, quiz_context: quizContext };
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
        if (csrfToken) { headers['X-CSRFToken'] = csrfToken; } else { console.warn("quiz_logic.js: CSRF Token not found for submit."); }
        try {
            const response = await fetch('/api/submit_quiz', { method: 'POST', headers: headers, body: JSON.stringify(payload) });
            showLoading(false);
            if (!response.ok) { let eMsg = `提交失败 (${response.status})`; try {const eD = await response.json(); eMsg = eD.error || eMsg;} catch(e){} throw new Error(eMsg); }
            const results = await response.json(); console.log("quiz_logic.js: Results received:", results); displayResults(results);
        } catch (error) { console.error('quiz_logic.js: Error submitting:', error); showError(`提交出错: ${error.message}`); showLoading(false); if (submitQuizBtn) submitQuizBtn.disabled = false; }
    }

    function displayResults(results) {
        console.log("quiz_logic.js: displayResults called."); showLoading(false);
        if (!resultsArea || !scoreSpan || !totalQuestionsSpan || !incorrectListUl) { showError("无法显示结果区域。"); return; }
        if (quizArea) quizArea.classList.add('hidden'); resultsArea.classList.remove('hidden'); if (submitQuizBtn) submitQuizBtn.classList.add('hidden');
        scoreSpan.textContent = results.score ?? '?'; totalQuestionsSpan.textContent = results.total_questions ?? '?';
        incorrectListUl.innerHTML = ''; const incorrectTitle = document.getElementById('incorrect-title'); // Assuming title has this ID
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

    function resetQuizUI() {
        console.log("quiz_logic.js: resetQuizUI called.");
        if (quizArea) quizArea.classList.add('hidden'); if (resultsArea) resultsArea.classList.add('hidden');
        if (questionsContainer) questionsContainer.innerHTML = ''; if (incorrectListUl) incorrectListUl.innerHTML = '';
        if (scoreSpan) scoreSpan.textContent = ''; if (totalQuestionsSpan) totalQuestionsSpan.textContent = '';
        if (submitQuizBtn) { submitQuizBtn.classList.add('hidden'); submitQuizBtn.disabled = false; }
        const startIdxBtn = document.getElementById('start-quiz-btn'); if (startIdxBtn) startIdxBtn.disabled = false; // Changed ID name
        const startLsBtn = document.getElementById('start-lesson-quiz-btn'); if (startLsBtn) startLsBtn.disabled = false;
        hideError(); showLoading(false);
        currentQuizData = null; userAnswers = {}; quizContext = {};
        console.log("quiz_logic.js: Quiz UI reset complete.");
    }

    // --- Global Event Listener for Submit Button ---
    if (submitQuizBtn) {
        submitQuizBtn.addEventListener('click', submitQuiz);
        console.log("quiz_logic.js: Global listener attached to submitQuizBtn.");
    } else {
        console.warn("quiz_logic.js: Submit quiz button not found during init.");
    }

    // --- Expose necessary functions to the global scope ---
    window.quizLogic = {
        showLoading,
        showError,
        hideError,
        displayQuestions,
        // collectAnswers, // Usually internal
        // submitQuiz, // Usually called by button listener above
        // displayResults, // Usually called by submitQuiz
        resetQuizUI // Needed by page-specific restart buttons
    };
    console.log("quiz_logic.js: Core functions exposed on window.quizLogic");

    // --- Event Listener for Favorite Toggles (using Delegation on document) ---
     // Assuming handleFavoriteToggle function is defined below or included separately
     if (typeof handleFavoriteToggle === 'function') {
         document.addEventListener('click', handleFavoriteToggle);
         console.log("quiz_logic.js: Global favorite toggle listener attached to document.");
     } else {
         console.warn("quiz_logic.js: handleFavoriteToggle function not found. Favorite buttons may not work.");
     }

}); // --- End of DOMContentLoaded listener ---


// --- Favorite Toggle Handler Function (Can be inside or outside DOMContentLoaded) ---
// Needs access to CSRF token logic potentially, so placing it here for now.
async function handleFavoriteToggle(event) {
    const toggleButton = event.target.closest('.favorite-toggle-btn');
    if (!toggleButton) return;

    event.preventDefault();
    const vocabId = toggleButton.dataset.vocabId;
    let isCurrentlyFavorite = toggleButton.dataset.isFavorite === 'true';
    const icon = toggleButton.querySelector('i');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    if (!vocabId || !icon) { console.error("Favorite handler: Missing elements."); return; }

    toggleButton.disabled = true;

    try {
        const response = await fetch(`/api/vocabulary/${vocabId}/toggle_favorite`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json', 'Accept': 'application/json',
                ...(csrfToken && {'X-CSRFToken': csrfToken})
            },
        });

        if (!response.ok) { let eMsg=`Fav op failed (${response.status})`; try{const eD=await response.json();eMsg=eD.error||eMsg;}catch(e){} throw new Error(eMsg); }
        const data = await response.json();

        if (data.success) {
            isCurrentlyFavorite = data.is_favorite;
            toggleButton.dataset.isFavorite = isCurrentlyFavorite;
            icon.className = isCurrentlyFavorite ? 'bi bi-star-fill text-warning fs-5' : 'bi bi-star fs-5';
            toggleButton.title = isCurrentlyFavorite ? "从收藏中移除" : "添加到收藏";

            // Special handling for favorites page: Remove item visually
            const favoritesList = document.getElementById('favorites-list');
            const listItem = toggleButton.closest('.list-group-item');
            if (!isCurrentlyFavorite && favoritesList && listItem && favoritesList.contains(listItem)) {
                 listItem.style.opacity = '0';
                 setTimeout(() => {
                     listItem.remove();
                     if (!favoritesList.hasChildNodes() || favoritesList.children.length === 0) {
                         favoritesList.innerHTML = '<div class="alert alert-info">你的收藏列表现在是空的。</div>';
                     }
                 }, 300);
             }
        } else { throw new Error(data.error || '收藏操作失败'); }
    } catch (error) {
        console.error('Error toggling favorite:', error);
        alert(`收藏操作出错: ${error.message}`);
        // Revert UI on error
        icon.className = isCurrentlyFavorite ? 'bi bi-star-fill text-warning fs-5' : 'bi bi-star fs-5';
    } finally {
        toggleButton.disabled = false;
    }
}

// --- End of quiz_logic.js ---