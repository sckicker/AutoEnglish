// static/js/quiz_logic.js V1.5 - Improved global state initialization & displayQuestions sets global data

// ==========================
// Shared JavaScript logic for handling quizzes on the NCE platform.
// This file should be included in base.html *before* the scripts_extra block.
// ==========================


// --- Global Quiz State Variables ---
// These variables hold information about the currently active quiz session
// Initialize quizContext with a complete structure to avoid errors when checking properties
let currentQuizData = null; // Stores the array of question objects received from API {id, lesson, question, part_of_speech, correct_answer}
let userAnswers = {};       // Stores user's input keyed by vocabulary ID { vocab_id: "user's answer" }
let quizContext = {         // Stores info about the quiz { lesson_ids: [], quiz_type: "", question_ids: [] }
    lesson_ids: [],
    quiz_type: "",
    question_ids: [] // Ensure question_ids is always an array
};


// --- DOM Element References (Declare null initially, populate in DOMContentLoaded) ---
let quizArea = null, questionsContainer = null, submitQuizBtn = null, resultsArea = null,
    scoreSpan = null, totalQuestionsSpan = null, incorrectListUl = null,
    loadingIndicator = null, errorDiv = null;


// --- DOMContentLoaded: Get element references and attach global listeners ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("quiz_logic.js: DOMContentLoaded event fired.");

    // Get references *after* DOM is ready
    quizArea = document.getElementById('quiz-area');
    questionsContainer = document.getElementById('questions-container');
    submitQuizBtn = document.getElementById('submit-quiz-btn');
    resultsArea = document.getElementById('results-area');
    scoreSpan = document.getElementById('score');
    totalQuestionsSpan = document.getElementById('total-questions');
    incorrectListUl = document.getElementById('incorrect-list');
    loadingIndicator = document.getElementById('loading-indicator');
    errorDiv = document.getElementById('error-message');

    // Attach listener for the SUBMIT button
    // Make sure the button exists before attaching
    if (submitQuizBtn) {
        submitQuizBtn.addEventListener('click', submitQuiz); // submitQuiz is defined below
        console.log("quiz_logic.js: Listener attached to submitQuizBtn.");
    } else {
        console.warn("quiz_logic.js: Submit quiz button not found during init. Submit functionality might be disabled.");
    }

    // Attach listener for favorite toggles (if feature exists)
    // Note: The handleFavoriteToggle function needs to be defined globally or imported.
    if (typeof handleFavoriteToggle === 'function') {
        // Using event delegation on the document for potentially dynamic favorite buttons
        document.addEventListener('click', function(event) {
            // Check if the clicked element or its parent is a favorite toggle button
            const toggleButton = event.target.closest('.favorite-toggle-btn');
            if (toggleButton) {
                event.preventDefault(); // Prevent default link or button behavior
                handleFavoriteToggle(event); // Call the actual handler, passing the event
            }
        });
        console.log("quiz_logic.js: Global favorite toggle listener attached via delegation.");
    } else {
        // This warning is expected if you don't have favorite toggle buttons using this class
        console.warn("quiz_logic.js: handleFavoriteToggle function not found or .favorite-toggle-btn not used.");
    }

    console.log("quiz_logic.js: DOM elements referenced and global listeners attached.");

}); // --- End of DOMContentLoaded ---


// ======================================================
// === Core Functions (Defined in the script's scope) ===
// ======================================================

// --- UI Helper Functions ---

/**
 * Shows or hides the loading indicator.
 * @param {boolean} isLoading - True to show loading, false to hide.
 */
function showLoading(isLoading) {
    if (loadingIndicator) {
        loadingIndicator.classList.toggle('hidden', !isLoading);
        // Optional: Hide error and results when showing loading
        if(isLoading) {
             hideError();
             if (resultsArea) resultsArea.classList.add('hidden');
             // Consider also hiding quizArea or showing a specific loading state there
        }
    } else {
        console.warn("quiz_logic.js: Loading indicator element (#loading-indicator) not found.");
    }
}

/**
 * Displays an error message to the user.
 * Also logs to console and hides loading/quiz/results areas.
 * @param {string} message - The error message to display.
 */
function showError(message) {
    console.error("quiz_logic.js: showError called with:", message);
    if (errorDiv) {
        errorDiv.textContent = `错误: ${message}`;
        errorDiv.classList.remove('hidden');
        // Auto-hide the error after a few seconds
        setTimeout(hideError, 8000); // Hide after 8 seconds
    } else {
        console.warn("quiz_logic.js: Error message element (#error-message) not found. Using alert as fallback.");
        alert(`错误: ${message}`); // Fallback
    }
    // Ensure other areas are hidden/reset on error
    if (quizArea) quizArea.classList.add('hidden');
    if (resultsArea) resultsArea.classList.add('hidden');
    showLoading(false); // Hide loading indicator when showing error

    // Reset quiz state on error
    resetQuizStateVariables();
}

/**
 * Hides the error message area.
 */
function hideError() {
    if (errorDiv) {
        errorDiv.classList.add('hidden');
        errorDiv.textContent = ''; // Clear content when hidden
    }
}

/**
 * Resets the global quiz state variables.
 */
function resetQuizStateVariables() {
     // --- 添加 console.trace ---
     console.trace("quiz_logic.js: Resetting global state variables called from:");
     // ------------------------
     currentQuizData = null;
     userAnswers = {};
     // Reset quizContext to its initial structure
     quizContext = {
         lesson_ids: [],
         quiz_type: "",
         question_ids: []
     };
     console.log("quiz_logic.js: Global state variables have been reset."); // 确认重置完成
}

// --- Core Quiz Logic Functions ---

/**
 * Renders the quiz questions based on the provided data.
 * This function is called by page-specific scripts after fetching data.
 * @param {Array} questionsToDisplay - Array of question objects to display.
 */
function displayQuestions(questionsToDisplay) { // <--- Accepts parameter
    console.log("quiz_logic.js: displayQuestions called with data.");
    // Check for essential elements *before* proceeding
    if (!questionsContainer || !quizArea || !submitQuizBtn) {
         showError("测验显示区域或按钮丢失 (#questions-container, #quiz-area, #submit-quiz-btn)。");
         console.error("displayQuestions failed: Required UI elements missing.");
         resetQuizStateVariables(); // Ensure state is reset on UI element error
         return;
    }


    // --- Use the passed parameter for checking and iteration ---
    if (!Array.isArray(questionsToDisplay) || questionsToDisplay.length === 0) {
        showError("无有效测验问题可显示 (数据为空或格式错误)。");
        console.error("displayQuestions failed: questionsToDisplay is not a valid array or is empty.", questionsToDisplay);
        if (quizArea) quizArea.classList.add('hidden');
        resetQuizStateVariables(); // Ensure state is reset on data error
        return;
    }
    // ---------------------------------------------------------

    // --- Store the successfully validated data in the global state ---
    // This makes the global state more robust if displayQuestions is called directly
    // or if the global state somehow gets cleared before submit.
    currentQuizData = questionsToDisplay;
    console.log("quiz_logic.js: Global currentQuizData set in displayQuestions.");
    // --------------------------------------------------------------


    hideError(); // Hide any previous error
    questionsContainer.innerHTML = ''; // Clear previous questions
    userAnswers = {}; // Reset answers for this set

    // --- Use the passed parameter for looping ---
    questionsToDisplay.forEach((question, index) => {
    // -----------------------------------------
        // Basic validation for question object structure
        if (!question || typeof question.id === 'undefined' || !question.question || typeof question.lesson === 'undefined') {
            console.warn("Skipping invalid question object:", question);
            return; // Skip this question if it's malformed
        }

        const questionDiv = document.createElement('div');
        questionDiv.classList.add('card', 'mb-3'); // Use Bootstrap card classes

        const cardBody = document.createElement('div');
        cardBody.classList.add('card-body');

        const questionLabel = document.createElement('label');
        const inputId = `answer-${question.id}`;
        questionLabel.setAttribute('for', inputId);
        // Use h5 for title, add form-label and mb-2 spacing
        questionLabel.classList.add('card-title','form-label','h5','mb-2');

        // Add POS badge if exists
        const posText = question.part_of_speech ?
            ` <span class="badge bg-info fw-normal">${question.part_of_speech}</span>` : ''; // Bootstrap badge

        // Add lesson number to the prompt
        questionLabel.innerHTML = `题目 ${index + 1} (L${question.lesson}): ${question.question}${posText}:`;

        const answerInput = document.createElement('input');
        answerInput.setAttribute('type', 'text');
        answerInput.setAttribute('id', inputId);
        answerInput.setAttribute('name', inputId); // Good practice to set name attribute for form submission
        answerInput.setAttribute('data-vocab-id', question.id); // Use data attribute to link input to vocab ID
        // Use form-control and form-control-sm for styling
        answerInput.classList.add('form-control','form-control-sm');
        answerInput.setAttribute('placeholder', '请输入答案'); // Add placeholder
        answerInput.setAttribute('autocomplete', 'off'); // Disable autocomplete

        cardBody.appendChild(questionLabel);
        cardBody.appendChild(answerInput);
        questionDiv.appendChild(cardBody);
        questionsContainer.appendChild(questionDiv);

        // Add keypress listener to jump to next input on Enter
         answerInput.addEventListener('keypress', function(event) {
             if (event.key === 'Enter') {
                 event.preventDefault(); // Prevent form submission or page reload
                 // Find the next input field
                 const allInputs = Array.from(questionsContainer.querySelectorAll('input[type="text"]'));
                 const currentIndex = allInputs.indexOf(event.target);
                 if (currentIndex > -1 && currentIndex < allInputs.length - 1) {
                     allInputs[currentIndex + 1].focus();
                 } else if (currentIndex === allInputs.length - 1) {
                     // If it's the last input, trigger submit if button is visible and not disabled
                     if(submitQuizBtn && !submitQuizBtn.classList.contains('hidden') && !submitQuizBtn.disabled) {
                          submitQuizBtn.click(); // Simulate click
                     }
                 }
             }
         });
    });

    // Show quiz area and submit button
    if (quizArea) quizArea.classList.remove('hidden');
    if (resultsArea) resultsArea.classList.add('hidden'); // Ensure results are hidden
    if (submitQuizBtn) {
        submitQuizBtn.classList.remove('hidden'); // Ensure submit is visible
        submitQuizBtn.disabled = false; // Ensure submit button is enabled initially
    }


    // Focus first input after rendering
    const firstInput = questionsContainer.querySelector('input[type="text"]');
    if (firstInput) {
        firstInput.focus();
    } else {
        console.warn("quiz_logic.js: No input fields found after displaying questions.");
    }

    console.log(`quiz_logic.js: Successfully displayed ${questionsToDisplay.length} questions.`);
}

/**
 * Collects answers from the input fields into the userAnswers object.
 * Assumes questionsContainer exists and contains inputs with data-vocab-id.
 */
function collectAnswers() {
    userAnswers = {}; // Reset before collecting
    if (!questionsContainer) { console.error("quiz_logic.js: Cannot collect answers: questions container missing."); return; }
    const inputs = questionsContainer.querySelectorAll('input[type="text"][data-vocab-id]');
    if (inputs.length === 0) { console.warn("quiz_logic.js: No answer input fields found to collect from."); }
    inputs.forEach(input => {
        const vocabId = input.dataset.vocabId;
        if (vocabId) {
            userAnswers[vocabId] = input.value.trim();
        }
    });
    console.log("quiz_logic.js: Answers collected for", Object.keys(userAnswers).length, "questions.");
}

/**
 * Submits the collected answers and quiz context to the backend API.
 * Performs validation before sending and displays results or errors.
 * Ensures usage of global state variables (window.currentQuizData, window.quizContext).
 */
async function submitQuiz() {
    // --- 0. Log Start and Initial Global State ---
    console.log("submitQuiz START: Current state is:", {
        currentQuizData: window.currentQuizData, // Check global state at the beginning
        quizContext: window.quizContext,
        userAnswers: window.userAnswers           // This userAnswers is from the previous state or initial
    });

    // --- 1. Disable UI Elements Immediately ---
    if (submitQuizBtn) submitQuizBtn.disabled = true;
    if (questionsContainer) {
        questionsContainer.querySelectorAll('input[type="text"]').forEach(input => {
            input.disabled = true; // Prevent further input during submission
        });
    }

    // --- 2. Collect Answers (Updates the global userAnswers variable) ---
    collectAnswers();
    console.log("submitQuiz: After collectAnswers, userAnswers is:", window.userAnswers); // Log collected answers

    // --- 3. Validate Global State (Using window. prefix explicitly) ---
    let validationError = null;
    if (!window.currentQuizData || !Array.isArray(window.currentQuizData) || window.currentQuizData.length === 0) {
        validationError = "内部错误：缺少当前测验的问题数据 (window.currentQuizData is invalid)。";
    } else if (!window.quizContext || typeof window.quizContext !== 'object') {
        // Check if the global quizContext object itself is missing or not an object
        validationError = "内部错误：缺少测验上下文对象 (window.quizContext is invalid or missing)。";
    } else if (!Array.isArray(window.quizContext.lesson_ids)) { // Check if lesson_ids exists and is an array
        validationError = "内部错误：测验上下文缺少课程 ID 列表 (window.quizContext.lesson_ids is invalid)。";
    } else if (typeof window.quizContext.quiz_type !== 'string' || window.quizContext.quiz_type === '') { // Check quiz_type
        validationError = "内部错误：测验上下文缺少测验类型 (window.quizContext.quiz_type is invalid)。";
    }
    // question_ids will be synced next, so don't need strict validation here if currentQuizData is valid

    if (validationError) {
        console.error("submitQuiz validation failed:", validationError, {
            currentQuizData: window.currentQuizData,
            quizContext: window.quizContext,
            userAnswers: window.userAnswers // Show state at time of validation failure
        });
        // Validation failed, call showError (which also resets state)
        showError(validationError + " 请尝试重新开始测试。");
        // Re-enable UI because submission was blocked before API call
        if (submitQuizBtn) submitQuizBtn.disabled = false;
        if (questionsContainer) {
             questionsContainer.querySelectorAll('input[type="text"]').forEach(input => {
                 input.disabled = false;
             });
         }
        return; // Stop submission process
    }
    console.log("submitQuiz validation passed. Proceeding with submission.");

    // --- 4. Sync question_ids in Global Context (Safeguard) ---
    // Use the validated global currentQuizData to ensure question IDs match the actual questions
    try {
        // Check global currentQuizData again before mapping
        if (window.currentQuizData && Array.isArray(window.currentQuizData)) {
            // Modify the global window.quizContext directly
            window.quizContext.question_ids = window.currentQuizData.map(q => q.id);
            console.log("submitQuiz: Ensuring global question_ids are synced:", window.quizContext.question_ids);
        } else {
             // This should not happen if validation passed, indicates a deeper issue
             throw new Error("无法确认问题列表 (window.currentQuizData invalid after validation check)");
        }
    } catch(mapError) {
         console.error("Error syncing question IDs:", mapError);
         showError("准备提交数据时出错 (同步问题ID失败)。请重试。");
         if (submitQuizBtn) submitQuizBtn.disabled = false;
         if (questionsContainer) { /* ... enable inputs ... */ }
         return; // Stop if syncing fails
    }

    // --- 5. Prepare for API Call ---
    showLoading(true); // Show loading indicator
    hideError();       // Hide any previous errors

    // --- 6. Prepare Payload (Using global context explicitly) ---
    const payload = {
        answers: userAnswers,           // Collected answers (global or module scope assumed okay for this)
        quiz_context: window.quizContext // *** Use the global context object ***
    };
    // Log the exact payload being sent
    console.log("quiz_logic.js: Sending payload:", JSON.stringify(payload, null, 2)); // Pretty print JSON

    // --- 7. Prepare Headers (including CSRF) ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    } else {
        console.warn("quiz_logic.js: CSRF Token not found in meta tag. Request might fail if CSRF protection is enabled.");
    }

    // --- 8. Perform API Call ---
    try {
        const response = await fetch('/api/submit_quiz', {
            method: 'POST', // *** Ensure method is POST ***
            headers: headers,
            body: JSON.stringify(payload)
        });

        // Hide loading indicator once response is received
        showLoading(false);

        if (!response.ok) {
            // Handle HTTP errors (4xx, 5xx)
            let eMsg = `提交失败 (${response.status} ${response.statusText})`;
            try {
                const errorData = await response.json();
                eMsg = errorData.error || eMsg;
            } catch (e) {
                try {
                     const errorText = await response.text();
                     eMsg += `: ${errorText.substring(0,150)}${errorText.length > 150 ? '...' : ''}`;
                } catch (textErr) {
                     console.error("quiz_logic.js: Failed to parse error response as JSON or Text:", textErr);
                }
            }
            // Re-enable UI before throwing error
            if (submitQuizBtn) submitQuizBtn.disabled = false;
            if (questionsContainer) { /* ... enable inputs ... */ }
            throw new Error(eMsg); // Throw error to be caught below
        }

        // --- 9. Process Successful Response ---
        const results = await response.json();
        console.log("quiz_logic.js: Results received:", results);

        // Display results (this hides quiz area)
        displayResults(results);

        // --- 10. Reset State AFTER Successful Submission & Display ---
        resetQuizStateVariables(); // Clear state for the next potential quiz

    } catch (error) {
        // --- 11. Catch Block for Fetch Errors or Non-OK Responses ---
        console.error('quiz_logic.js: Error during submitQuiz fetch/processing:', error);
        showError(`提交出错: ${error.message}`); // Show specific error

        // Re-enable UI elements on error
        if (submitQuizBtn) submitQuizBtn.disabled = false;
        if (questionsContainer) {
            questionsContainer.querySelectorAll('input[type="text"]').forEach(input => {
                input.disabled = false;
            });
        }
        // Ensure loading is hidden
        showLoading(false);
        // Do NOT reset state here, allow potential retry/correction
    }
    // No finally block needed as loading is handled in try/catch

} // --- End of submitQuiz ---

/**
 * Displays the quiz results on the page.
 * Assumes resultsArea, scoreSpan, totalQuestionsSpan, incorrectListUl elements exist.
 * @param {object} results - The results object received from the API {score, total_questions, wrong_answers: [{question, part_of_speech, user_answer, correct_answer}, ...]}
 */
function displayResults(results) {
    console.log("quiz_logic.js: displayResults called.");
    showLoading(false); // Ensure loading is hidden

    // Check for essential elements *before* proceeding
    if (!resultsArea || !scoreSpan || !totalQuestionsSpan || !incorrectListUl || !quizArea) {
         showError("测验结果区域元素丢失。");
         console.error("displayResults failed: Required UI elements missing.");
         // State variables were already reset in submitQuiz on success path (after this function returns)
         // resetQuizStateVariables(); // No need to reset state here, it's handled after this function finishes

         // Ensure quiz area is hidden and results area stays hidden if elements are missing
         if (quizArea) quizArea.classList.add('hidden');
         if (resultsArea) resultsArea.classList.add('hidden');
         return;
    }


    hideError(); // Hide any previous error messages
    if (quizArea) quizArea.classList.add('hidden'); // Hide the quiz area
    resultsArea.classList.remove('hidden'); // Show the results area

    // Hide the submit button (it was disabled during submit, now ensure it's hidden)
    if (submitQuizBtn) submitQuizBtn.classList.add('hidden');


    // Populate score
    scoreSpan.textContent = results.score ?? 'N/A'; // Use Nullish Coalescing for default
    totalQuestionsSpan.textContent = results.total_questions ?? 'N/A';

    // Populate incorrect answers list
    incorrectListUl.innerHTML = ''; // Clear previous list items
    const incorrectTitle = document.getElementById('incorrect-title'); // Get the title element

    if (results.wrong_answers && Array.isArray(results.wrong_answers) && results.wrong_answers.length > 0) {
        if(incorrectTitle) incorrectTitle.textContent = '错题回顾:'; // Set title for wrong answers
        results.wrong_answers.forEach(item => {
            // Basic validation for wrong answer item structure
             if (!item || !item.question || typeof item.user_answer === 'undefined' || !item.correct_answer) {
                 console.warn("Skipping malformed wrong answer item:", item);
                 return; // Skip if malformed
             }

            const li = document.createElement('li');
            // Use Bootstrap list group item classes and flexbox for layout
            li.classList.add('list-group-item', 'd-flex', 'justify-content-between', 'align-items-start');

            const posText = item.part_of_speech ?
                 ` <span class="badge bg-secondary fw-normal">${item.part_of_speech}</span>` : ''; // Bootstrap badge

            li.innerHTML = `
                <div class="ms-2 me-auto">
                  <div class="fw-bold">${item.question}${posText}</div>
                  <span class="text-danger small">你的答案: ${item.user_answer !== null && item.user_answer !== '' ? item.user_answer : '<em>(未作答)</em>'}</span><br>
                  <span class="text-success small">正确答案: ${item.correct_answer}</span>
                </div>
                `;
            incorrectListUl.appendChild(li);
        });
    } else {
        // If no wrong answers, display a success message
        if(incorrectTitle) incorrectTitle.textContent = '测试结果:'; // Change title for full correct
        const li = document.createElement('li');
        li.classList.add('list-group-item','text-success','fw-bold','text-center'); // Center text
        li.innerHTML = '<i class="bi bi-check-circle-fill"></i> 恭喜，全部回答正确！'; // Use Bootstrap icon
        incorrectListUl.appendChild(li);
    }

    // Ensure the restart button is visible and enabled in the results area
    const restartBtn = resultsArea.querySelector('#restart-quiz-btn'); // Get the button *within* the results area
    if (restartBtn) {
        restartBtn.classList.remove('hidden');
        restartBtn.disabled = false; // Enable it
         console.log("quiz_logic.js: Restart button displayed and enabled.");
    } else {
        console.warn("quiz_logic.js: Restart button (#restart-quiz-btn) not found within the results area.");
    }

    // Optional: Scroll to the results area
    resultsArea.scrollIntoView({ behavior: 'smooth', block: 'start' });

    console.log("quiz_logic.js: Results displayed.");
    // State variables were already reset in submitQuiz on success path (after this function returns)
    // resetQuizStateVariables(); // No need to reset state variables here
}

/**
 * Resets the quiz UI elements to their initial hidden/default state.
 * Called by page-specific scripts to clear the screen before starting a new quiz
 * or after an error that prevents quiz display.
 */
function resetQuizUI() {
    console.log("quiz_logic.js: resetQuizUI called.");
    // Check for essential elements before attempting to manipulate
    if (!quizArea || !resultsArea || !questionsContainer || !incorrectListUl || !submitQuizBtn) {
        console.warn("quiz_logic.js: resetQuizUI called but some core UI elements are missing.");
        // Still attempt to reset state variables
        resetQuizStateVariables();
        return; // Cannot fully reset UI if elements are missing
    }

    // Hide UI areas
    quizArea.classList.add('hidden');
    resultsArea.classList.add('hidden');

    // Clear dynamic content
    questionsContainer.innerHTML = '';
    incorrectListUl.innerHTML = '';
    if (scoreSpan) scoreSpan.textContent = ''; // Clear score
    if (totalQuestionsSpan) totalQuestionsSpan.textContent = ''; // Clear total questions

    // Reset submit button state
    submitQuizBtn.classList.add('hidden');
    submitQuizBtn.disabled = false; // Ensure it's enabled for the *next* potential quiz

    // Reset restart button state (if it exists in the DOM initially, though it's usually in resultsArea)
     const restartBtnGlobal = document.getElementById('restart-quiz-btn');
     if(restartBtnGlobal) {
          // It might be in resultsArea, which is hidden, so hiding again is fine.
          // Ensure it's enabled for the next quiz attempt.
          restartBtnGlobal.classList.add('hidden'); // Ensure it's hidden
          restartBtnGlobal.disabled = false; // Ensure it's enabled
     }


    // Ensure loading and error messages are hidden
    hideError();
    showLoading(false);

    // Reset state variables - Done by resetQuizStateVariables() now
    // currentQuizData = null;
    // userAnswers = {};
    // quizContext = {};

    console.log("quiz_logic.js: Quiz UI reset complete.");
}


// --- Favorite Toggle Handler Function (Keep if needed) ---
// This function is attached via event delegation in DOMContentLoaded
async function handleFavoriteToggle(event) {
    // event.target is the element that was clicked
    // .closest('.favorite-toggle-btn') finds the nearest ancestor (or self) with the class 'favorite-toggle-btn'
    const toggleButton = event.target.closest('.favorite-toggle-btn');

    if (!toggleButton) {
        // If the click wasn't on or inside a favorite toggle button, do nothing
        return;
    }

    event.preventDefault(); // Prevent default action (e.g., navigating if it's a link)

    const vocabId = toggleButton.dataset.vocabId; // Assuming vocab ID is stored in data-vocab-id
    if (!vocabId) {
        console.warn("Favorite toggle button missing data-vocab-id attribute.");
        // Optionally show an error to the user
        // showError("无法获取词汇ID。"); // Requires showError to be accessible
        return;
    }

    console.log(`Toggling favorite for vocab ID: ${vocabId}`);

    // Optimistic UI Update (Optional but good for responsiveness)
    // toggleButton.classList.toggle('favorited'); // Toggle a class for styling
    // toggleButton.querySelector('i.bi').classList.toggle('bi-star').classList.toggle('bi-star-fill'); // Toggle icon

    // Send request to backend API to toggle favorite status
    const url = `/api/vocab/${vocabId}/favorite`;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    try {
        // Indicate loading or pending state on the button if desired
        // toggleButton.disabled = true;

        const response = await fetch(url, {
            method: 'POST', // Assuming POST for toggling state
            headers: {
                'X-CSRFToken': csrfToken, // Include CSRF token
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
             let errorMsg = `Toggle favorite failed (${response.status})`;
             try { const errorData = await response.json(); errorMsg = errorData.error || errorMsg; } catch(e) {}
             throw new Error(errorMsg);
        }

        const result = await response.json(); // Expecting a JSON response, maybe with the new state { is_favorited: true/false }
        console.log(`Favorite toggle successful for ${vocabId}:`, result);

        // Update UI based on backend response (more reliable than optimistic update)
        // Assuming the result includes the new favorite status
        const isFavorited = result.is_favorited;
        if (isFavorited !== undefined) {
             // Remove both potential classes first
             toggleButton.classList.remove('favorited', 'not-favorited');
             toggleButton.classList.add(isFavorited ? 'favorited' : 'not-favorited');

             // Find the icon within the button
             const icon = toggleButton.querySelector('i.bi');
             if(icon) {
                  icon.classList.remove('bi-star', 'bi-star-fill');
                  icon.classList.add(isFavorited ? 'bi-star-fill' : 'bi-star');
                  // Optional: Change icon color via class (e.g., text-warning for favorited)
                  // icon.classList.remove('text-warning');
                  // if(isFavorited) icon.classList.add('text-warning');
             }

        } else {
            console.warn("Backend response for favorite toggle did not include 'is_favorited' status.");
            // If backend doesn't return status, you might need to just toggle based on previous state or re-fetch data
        }

        // Optionally show a temporary success message
        // if (typeof window.quizLogic !== 'undefined' && typeof window.quizLogic.showError === 'function') {
        //      window.quizLogic.showError(isFavorited ? '已收藏' : '已取消收藏'); // Reuse showError or create a showSuccess
        // }


    } catch (error) {
        console.error(`Error toggling favorite for vocab ID ${vocabId}:`, error);
         // Revert optimistic update if it failed (if you did one)
         // toggleButton.classList.toggle('favorited'); // Toggle back
         // toggleButton.querySelector('i.bi').classList.toggle('bi-star').classList.toggle('bi-star-fill'); // Toggle icon back

        // Show error message to the user
         if (typeof window.quizLogic !== 'undefined' && typeof window.quizLogic.showError === 'function') {
              window.quizLogic.showError(`收藏操作失败: ${error.message}`);
         } else {
             alert(`收藏操作失败: ${error.message}`);
         }

    } finally {
        // Re-enable the button
        // toggleButton.disabled = false;
    }
}


// --- Expose necessary functions to the global window.quizLogic object ---
// This allows page-specific scripts (in scripts_extra) to call these core functions.
// Only expose functions intended for external use.
window.quizLogic = {
    showLoading: showLoading,
    showError: showError,
    hideError: hideError,
    displayQuestions: displayQuestions, // Accepts data parameter now
    resetQuizUI: resetQuizUI,           // Needed by restart buttons

    // Note: submitQuiz is NOT exposed here because its listener is attached
    // directly to the button by quiz_logic.js itself.
    // handleFavoriteToggle is attached via delegation, also not needed here.
};
console.log("quiz_logic.js: Core functions exposed on window.quizLogic");