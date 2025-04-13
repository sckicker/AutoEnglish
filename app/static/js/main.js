// app/static/js/main.js
// Complete version with debugging console logs for index.html button issue

document.addEventListener('DOMContentLoaded', () => {
    // --- Get Element References (with null checks for safety) ---
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessageDiv = document.getElementById('error-message');

    // Index page specific elements
    const startIndexQuizBtn = document.getElementById('start-quiz-btn'); // Button on index.html
    const lessonSelectorForm = document.getElementById('lesson-selector'); // Form on index.html
    // IDs added in previous step to index.html
    const lessonSelectionSection = document.getElementById('lesson-selection-section');
    const quizOptionsSection = document.getElementById('quiz-options-section');

    // Lesson page specific elements
    const startLessonQuizBtn = document.getElementById('start-lesson-quiz-btn'); // Button on lesson_text.html

    // Quiz/Result elements (expected on pages where quiz runs)
    const quizArea = document.getElementById('quiz-area');
    const resultsArea = document.getElementById('results-area');
    const questionsContainer = document.getElementById('questions-container');
    const submitQuizBtn = document.getElementById('submit-quiz-btn');
    const restartQuizBtn = document.getElementById('restart-quiz-btn'); // Restart button within results area
    const scoreSpan = document.getElementById('score');
    const totalQuestionsSpan = document.getElementById('total-questions');
    const incorrectListUl = document.getElementById('incorrect-list');

    // Global state variables
    let currentQuizData = [];
    let userAnswers = {};

    // --- Utility Functions ---
    function showLoading(show) {
        if (loadingIndicator) {
            loadingIndicator.classList.toggle('hidden', !show);
        }
    }

    function showError(message) {
        console.error("Error displayed:", message); // Also log errors to console
        if (errorMessageDiv) {
            errorMessageDiv.textContent = message;
            errorMessageDiv.classList.remove('hidden');
            // Automatically hide error after 5 seconds
            setTimeout(hideError, 5000);
        } else {
            console.error("Error display element not found!");
            alert(message); // Fallback alert
        }
    }

    function hideError() {
        if (errorMessageDiv) {
            errorMessageDiv.classList.add('hidden');
        }
    }

    // --- Core Quiz Logic Functions ---

    // ** displayQuestions: Generates HTML for questions with POS and Bootstrap styling **
    // (Assumes this is the latest version with fixes for comments and styling)
    function displayQuestions() {
        if (!questionsContainer) {
            console.error("Questions container not found!");
            showError("无法显示问题区域。");
            return;
        }

        questionsContainer.innerHTML = '';
        userAnswers = {};

        if (!currentQuizData || currentQuizData.length === 0) {
            showError('没有有效的测试题数据可供显示。');
            return;
        }

        currentQuizData.forEach((q, index) => {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question card mb-3 shadow-sm';

            let posHtml = '';
            if (q.part_of_speech) {
                posHtml = `<span class="text-muted fst-italic question-pos">(${q.part_of_speech})</span>`;
            }

            questionDiv.innerHTML = `
                <div class="card-body">
                     <p class="card-title question-prompt mb-2">
                         <strong class="me-2">题目 ${index + 1} (L${q.lesson}):</strong>
                         ${q.question}
                         ${posHtml}
                     </p>
                     <input type="text"
                            id="answer-${q.id}"
                            data-question-id="${q.id}"
                            class="form-control"
                            placeholder="请在此输入答案"
                            aria-label="Answer for question ${index + 1}">
                </div>
            `;

            questionsContainer.appendChild(questionDiv);

            const inputField = questionDiv.querySelector(`#answer-${q.id}`);
            if (inputField) {
                inputField.addEventListener('keypress', function(event) {
                    if (event.key === 'Enter') {
                        event.preventDefault();
                        const nextInput = questionsContainer.querySelector(`#answer-${currentQuizData[index+1]?.id}`);
                        if (nextInput) {
                            nextInput.focus();
                        } else if (index === currentQuizData.length - 1) {
                            if(submitQuizBtn && !submitQuizBtn.classList.contains('hidden')) {
                                submitQuiz();
                            }
                        }
                    }
                });
            }
        });

        const firstInput = questionsContainer.querySelector('input[type="text"]');
        if (firstInput) {
            firstInput.focus();
        }

        if (submitQuizBtn) {
             submitQuizBtn.classList.remove('hidden');
        }
    }

    // ** submitQuiz: Scores and displays results with Bootstrap validation styles **
    // (Assumes this is the latest version with fixes)
    function submitQuiz() {
        if (!currentQuizData || currentQuizData.length === 0 || !incorrectListUl) {
            console.error("Cannot submit quiz - data or result list element missing.");
            return;
        };

        currentQuizData.forEach(q => {
            const inputElement = document.getElementById(`answer-${q.id}`);
            if (inputElement) {
                userAnswers[q.id] = inputElement.value.trim();
                inputElement.disabled = true;
                inputElement.classList.remove('is-valid', 'is-invalid');
                 const questionCard = inputElement.closest('.card');
                 if(questionCard) {
                     questionCard.classList.remove('border-danger', 'border-success');
                 }
            } else {
                 userAnswers[q.id] = "";
            }
        });

        let score = 0;
        incorrectListUl.innerHTML = '';

        currentQuizData.forEach(q => {
            const userAnswer = userAnswers[q.id] || "";
            const isCorrect = userAnswer.toLowerCase() === q.correct_answer.toLowerCase();
            const inputElement = document.getElementById(`answer-${q.id}`);
            const questionCard = inputElement ? inputElement.closest('.card') : null;

            if (isCorrect) {
                score++;
                if(inputElement) inputElement.classList.add('is-valid');
            } else {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                let posText = q.part_of_speech ? `(${q.part_of_speech})` : '';
                li.innerHTML = `
                    <strong>题目 (L${q.lesson}):</strong> ${q.question} <span class="text-muted fst-italic">${posText}</span> <br>
                    <span class="incorrect">你的答案: ${userAnswer || "<i>未作答</i>"}</span> <br>
                    <span class="correct">正确答案: ${q.correct_answer}</span>
                `;
                incorrectListUl.appendChild(li);
                 if(inputElement) inputElement.classList.add('is-invalid');
                 if(questionCard) questionCard.classList.add('border-danger');
            }
        });

        if(scoreSpan) scoreSpan.textContent = score;
        if(totalQuestionsSpan) totalQuestionsSpan.textContent = currentQuizData.length;
        if(resultsArea) resultsArea.classList.remove('hidden');
        if(submitQuizBtn) submitQuizBtn.classList.add('hidden');
        if(resultsArea) resultsArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }


    // --- Page Specific Functions ---

    // ** For index.html: Get selected lesson numbers **
    function getSelectedLessons() {
        if (!lessonSelectorForm) return null;
        const checkboxes = lessonSelectorForm.querySelectorAll('input[name="lesson"]:checked');
        // Add log to see if checkboxes are found
        console.log('getSelectedLessons found checkboxes:', checkboxes.length);
        return Array.from(checkboxes).map(cb => cb.value).join(',');
    }

    // ** For index.html: Check selection and enable/disable button - WITH DEBUG LOG **
    function checkIndexSelection() {
         if (!lessonSelectorForm || !startIndexQuizBtn) {
            console.log('checkIndexSelection: Form or Start Button not found.');
            return;
         }
         let oneChecked = false;
         const checkboxes = lessonSelectorForm.querySelectorAll('input[name="lesson"]:checked');
         checkboxes.forEach(checkbox => {
             if (checkbox.checked) oneChecked = true;
         });

         // --- DEBUG LOG ---
         console.log('checkIndexSelection ran. oneChecked:', oneChecked, 'Button disabled should be:', !oneChecked);
         // -----------------

         startIndexQuizBtn.disabled = !oneChecked;
         const startQuizHelp = document.getElementById('start-quiz-help');
         if (startQuizHelp) startQuizHelp.style.display = oneChecked ? 'none' : 'inline';
    }

    // ** For index.html: Start quiz based on selected lessons - WITH DEBUG LOGS **
    async function startIndexPageQuiz() {
        // --- DEBUG LOG ---
        console.log('startIndexPageQuiz function CALLED!');
        // -----------------
        hideError();
        const lessons = getSelectedLessons();
        if (!lessons) {
            showError('请至少选择一个课程进行测试！');
            console.log('startIndexPageQuiz: No lessons selected, returning.');
            return;
        }
        const countInput = document.getElementById('num-questions');
        const typeInput = document.getElementById('quiz-type');
        const count = countInput ? countInput.value : 10;
        const type = typeInput ? typeInput.value : 'cn_to_en';

        // --- DEBUG LOG & Use IDs for hiding ---
        console.log('startIndexPageQuiz: Attempting to hide sections.');
        console.log('Finding lesson section:', lessonSelectionSection); // Check if found
        console.log('Finding options section:', quizOptionsSection); // Check if found
        if (lessonSelectionSection) lessonSelectionSection.classList.add('hidden'); else console.error("#lesson-selection-section not found!");
        if (quizOptionsSection) quizOptionsSection.classList.add('hidden'); else console.error("#quiz-options-section not found!");
        // ------------------------------------

        if (resultsArea) resultsArea.classList.add('hidden');
        if (quizArea) quizArea.classList.remove('hidden');
        if (questionsContainer) questionsContainer.innerHTML = '';
        showLoading(true);
        console.log('startIndexPageQuiz: Fetching data...');

        try {
            const response = await fetch(`/api/quiz?lessons=${lessons}&count=${count}&type=${type}`);
            showLoading(false);
            console.log('startIndexPageQuiz: Fetch response status:', response.status);

            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try { const errorData = await response.json(); errorMsg = errorData.error || errorMsg; } catch (e) {}
                throw new Error(errorMsg);
            }
            currentQuizData = await response.json();
            console.log('startIndexPageQuiz: Data received, questions count:', currentQuizData.length);


            if (!currentQuizData || currentQuizData.length === 0) {
                showError('未找到所选课程的词汇，或没有题目生成。请尝试其他课程。');
                throw new Error('No questions generated');
            }

            displayQuestions(); // Display the fetched questions

        } catch (error) {
            console.error('Error starting index quiz:', error);
            showError(`开始测试失败: ${error.message || '未知错误'}`);
            showLoading(false);
            if (quizArea) quizArea.classList.add('hidden');
            // --- DEBUG LOG & Use IDs for showing ---
            console.log('startIndexPageQuiz: Resetting UI on error.');
             if (lessonSelectionSection) lessonSelectionSection.classList.remove('hidden'); else console.error("#lesson-selection-section not found on error reset!");
             if (quizOptionsSection) quizOptionsSection.classList.remove('hidden'); else console.error("#quiz-options-section not found on error reset!");
            // -------------------------------------
            if (startIndexQuizBtn) checkIndexSelection();
        }
    }

    // ** For index.html: Reset view after quiz **
    function restartIndexPageQuiz() {
        console.log("restartIndexPageQuiz called"); // DEBUG LOG
        if(resultsArea) resultsArea.classList.add('hidden');
        if(quizArea) quizArea.classList.add('hidden');
        // Use IDs to show sections
        if (lessonSelectionSection) lessonSelectionSection.classList.remove('hidden');
        if (quizOptionsSection) quizOptionsSection.classList.remove('hidden');
        currentQuizData = [];
        userAnswers = {};
        hideError();
        if(lessonSelectorForm) {
             const checkboxes = lessonSelectorForm.querySelectorAll('input[name="lesson"]:checked');
             checkboxes.forEach(cb => cb.checked = false);
        }
        if(startIndexQuizBtn) checkIndexSelection(); // Re-check button state
    }


    // ** For lesson_text.html: Start quiz for the specific lesson **
    async function startLessonQuiz(lessonNumber) {
        console.log(`startLessonQuiz called for lesson: ${lessonNumber}`); // DEBUG LOG
        if (!lessonNumber) {
            showError("无法获取课程编号。");
            return;
        }
        hideError();
        if(resultsArea) resultsArea.classList.add('hidden');
        if(quizArea) quizArea.classList.remove('hidden');
        if(questionsContainer) questionsContainer.innerHTML = '';
        showLoading(true);
        if(startLessonQuizBtn) startLessonQuizBtn.disabled = true;

        const numQuestions = 999;
        const quizType = 'cn_to_en';

        try {
            const response = await fetch(`/api/quiz?lessons=${lessonNumber}&count=${numQuestions}&type=${quizType}`);
            showLoading(false);
            console.log(`startLessonQuiz: Fetch response status for lesson ${lessonNumber}:`, response.status);


            if (!response.ok) {
                 let errorMsg = `HTTP error! status: ${response.status}`;
                 try { const errorData = await response.json(); errorMsg = errorData.error || errorMsg; } catch (e) {}
                 throw new Error(errorMsg);
            }
            currentQuizData = await response.json();
            console.log(`startLessonQuiz: Data received for lesson ${lessonNumber}, questions count:`, currentQuizData.length);


            if (!currentQuizData || currentQuizData.length === 0) {
                showError(`未能加载 Lesson ${lessonNumber} 的词汇题。该课可能没有词汇或数据处理错误。`);
                throw new Error('No questions generated for lesson');
            }

            displayQuestions();

        } catch (error) {
            console.error('Error starting lesson quiz:', error);
            showError(`开始测试失败: ${error.message || '未知错误'}`);
            showLoading(false);
            if(quizArea) quizArea.classList.add('hidden');
            if(startLessonQuizBtn) startLessonQuizBtn.disabled = false;
        }
    }

    // ** For lesson_text.html: Reset view after quiz **
    function restartLessonQuiz() {
        console.log("restartLessonQuiz called"); // DEBUG LOG
        if(resultsArea) resultsArea.classList.add('hidden');
        if(quizArea) quizArea.classList.add('hidden');
        if(startLessonQuizBtn) startLessonQuizBtn.disabled = false;
        currentQuizData = [];
        userAnswers = {};
        hideError();
        if (startLessonQuizBtn) {
            startLessonQuizBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }


    // --- Event Listeners Setup (Handles both pages) ---

    // Listener for Start button on Index page
    if (startIndexQuizBtn) {
        console.log('Attaching click listener to #start-quiz-btn'); // DEBUG LOG
        startIndexQuizBtn.addEventListener('click', startIndexPageQuiz);
        // Initial check for enabling the button
        checkIndexSelection();
        // Add listeners to checkboxes on index page
        if (lessonSelectorForm) {
             const checkboxes = lessonSelectorForm.querySelectorAll('input[name="lesson"]');
             if (checkboxes.length > 0) {
                  console.log(`Attaching change listeners to ${checkboxes.length} checkboxes on index page.`); // DEBUG LOG
                  checkboxes.forEach(checkbox => {
                    checkbox.addEventListener('change', checkIndexSelection);
                  });
             } else {
                  console.warn("No lesson checkboxes found on index page to attach listeners to.");
             }
        }
    } else {
        console.log("#start-quiz-btn not found on this page."); // DEBUG LOG
    }


    // Listener for Start button on Lesson page
    if (startLessonQuizBtn) {
        console.log('Attaching click listener to #start-lesson-quiz-btn'); // DEBUG LOG
        startLessonQuizBtn.addEventListener('click', () => {
            const lessonNum = startLessonQuizBtn.dataset.lessonNumber;
            console.log(`Lesson quiz button clicked for lesson: ${lessonNum}`); // DEBUG LOG
            if (lessonNum) {
                startLessonQuiz(lessonNum);
            } else {
                showError('无法获取当前课程编号。');
                console.error("Lesson number missing from startLessonQuizBtn dataset.");
            }
        });
    } else {
         console.log("#start-lesson-quiz-btn not found on this page."); // DEBUG LOG
    }

    // Listener for Submit button (common to both)
    if (submitQuizBtn) {
        console.log('Attaching click listener to #submit-quiz-btn'); // DEBUG LOG
        submitQuizBtn.addEventListener('click', submitQuiz);
    } else {
         console.log("#submit-quiz-btn not found on this page."); // DEBUG LOG
    }

    // Listener for Restart button (common ID, but logic depends on page)
    if (restartQuizBtn) {
        console.log('Attaching click listener to #restart-quiz-btn'); // DEBUG LOG
        // Determine context by checking which START button exists on the page
        if (startLessonQuizBtn) { // If lesson quiz button exists, we're on lesson page
             console.log("Restart button will call restartLessonQuiz"); // DEBUG LOG
             restartQuizBtn.addEventListener('click', restartLessonQuiz);
        } else if (startIndexQuizBtn) { // If index quiz button exists, we're on index page
            console.log("Restart button will call restartIndexPageQuiz"); // DEBUG LOG
            restartQuizBtn.addEventListener('click', restartIndexPageQuiz);
        } else {
            // Fallback if context is unclear
             console.warn("Restart button found, but page context (index vs lesson) is unclear. Attaching generic hide logic.");
             restartQuizBtn.addEventListener('click', () => {
                 if(resultsArea) resultsArea.classList.add('hidden');
                 if(quizArea) quizArea.classList.add('hidden');
                 hideError();
             });
        }
    } else {
        console.log("#restart-quiz-btn not found on this page."); // DEBUG LOG
    }

}); // End DOMContentLoaded