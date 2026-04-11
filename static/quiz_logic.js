const apiRequest = async (url, options = {}) => {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    credentials: 'same-origin',
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || 'Request failed');
  }
  return data;
};

const loginForm = document.getElementById('login-form');
const otpForm = document.getElementById('otp-form');
const authMessage = document.getElementById('auth-message');
const registerForm = document.getElementById('register-form');
const registerOtpForm = document.getElementById('register-otp-form');
const registerMessage = document.getElementById('register-message');
const loginEmailInput = document.getElementById('email');
const questionForm = document.getElementById('question-form');
const formMessage = document.getElementById('form-message');
const questionsTable = document.getElementById('questions-table');
const logoutBtn = document.getElementById('logout-btn');
const refreshBtn = document.getElementById('refresh-btn');
const cancelEditBtn = document.getElementById('cancel-edit-btn');
const formTitle = document.getElementById('form-title');
const submitBtn = document.getElementById('submit-btn');
const sessionInfo = document.getElementById('session-info');
const questionIdInput = document.getElementById('question-id');

const isLoginPage = Boolean(loginForm);
const isRegisterPage = Boolean(registerForm);
const isDashboardPage = Boolean(questionForm);

let pendingEmail = '';
let pendingRegisterEmail = '';

const setMessage = (element, message, isError = false) => {
  if (!element) return;
  element.textContent = message;
  element.className = `mt-4 min-h-6 text-sm ${isError ? 'text-red-300' : 'text-slate-300'}`;
};

const collectQuestionPayload = () => ({
  question_text: document.getElementById('question_text').value.trim(),
  options: Array.from(document.querySelectorAll('.option-input')).map((input) => input.value.trim()),
  correct_answer: document.getElementById('correct_answer').value.trim(),
  category: document.getElementById('category').value.trim(),
});

const resetQuestionForm = () => {
  questionForm?.reset();
  questionIdInput.value = '';
  formTitle.textContent = 'Add Question';
  submitBtn.textContent = 'Add Question';
  cancelEditBtn.classList.add('hidden');
};

const renderQuestions = (questions) => {
  if (!questionsTable) return;

  if (!questions.length) {
    questionsTable.innerHTML = '<tr><td colspan="4" class="px-4 py-6 text-slate-300">No questions found.</td></tr>';
    return;
  }

  questionsTable.innerHTML = questions.map((question) => `
    <tr data-question-id="${question.id}" class="align-top hover:bg-white/5">
      <td class="px-4 py-4 text-slate-100">
        <div class="max-w-xl">
          <p class="font-medium">${question.question_text}</p>
          <ul class="mt-2 space-y-1 text-xs text-slate-400">
            ${question.options.map((option) => `<li>${option}</li>`).join('')}
          </ul>
        </div>
      </td>
      <td class="px-4 py-4 text-slate-300">${question.category}</td>
      <td class="px-4 py-4 text-slate-300">${question.correct_answer}</td>
      <td class="px-4 py-4">
        <div class="flex flex-wrap gap-2">
          <button class="edit-btn rounded-xl bg-amber-400 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-amber-300" data-question='${JSON.stringify(question).replaceAll("'", "&#39;")}'>Edit</button>
          <button class="delete-btn rounded-xl bg-red-500 px-3 py-2 text-xs font-semibold text-white hover:bg-red-400">Delete</button>
        </div>
      </td>
    </tr>
  `).join('');

  document.querySelectorAll('.edit-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const question = JSON.parse(button.dataset.question.replaceAll('&#39;', "'"));
      questionIdInput.value = question.id;
      document.getElementById('question_text').value = question.question_text;
      document.querySelectorAll('.option-input').forEach((input, index) => {
        input.value = question.options[index] || '';
      });
      document.getElementById('correct_answer').value = question.correct_answer;
      document.getElementById('category').value = question.category;
      formTitle.textContent = 'Edit Question';
      submitBtn.textContent = 'Update Question';
      cancelEditBtn.classList.remove('hidden');
      setMessage(formMessage, 'Editing existing question.');
    });
  });

  document.querySelectorAll('.delete-btn').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('tr');
      const questionId = row.dataset.questionId;
      if (!window.confirm('Delete this question?')) return;

      try {
        await apiRequest(`/api/questions/${questionId}`, { method: 'DELETE' });
        row.remove();
        if (!questionsTable.children.length) {
          renderQuestions([]);
        }
      } catch (error) {
        setMessage(formMessage, error.message, true);
      }
    });
  });
};

const loadQuestions = async () => {
  if (!questionsTable) return;
  try {
    const data = await apiRequest('/api/questions');
    renderQuestions(data.questions || []);
  } catch (error) {
    questionsTable.innerHTML = `<tr><td colspan="4" class="px-4 py-6 text-red-300">${error.message}</td></tr>`;
  }
};

if (isLoginPage) {
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    setMessage(authMessage, 'Sending OTP...');

    try {
      const payload = {
        email: loginEmailInput.value.trim(),
        password: document.getElementById('password').value,
      };
      const data = await apiRequest('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) });
      pendingEmail = payload.email;
      otpForm.classList.remove('hidden');
      setMessage(authMessage, data.message);
    } catch (error) {
      setMessage(authMessage, error.message, true);
    }
  });

  otpForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    setMessage(authMessage, 'Verifying OTP...');

    try {
      const payload = {
        email: pendingEmail || loginEmailInput.value.trim(),
        otp: document.getElementById('otp').value.trim(),
      };
      const data = await apiRequest('/api/auth/verify-otp', { method: 'POST', body: JSON.stringify(payload) });
      setMessage(authMessage, data.message);
      window.location.href = '/dashboard';
    } catch (error) {
      setMessage(authMessage, error.message, true);
    }
  });
}

if (isRegisterPage) {
  registerForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    setMessage(registerMessage, 'Sending registration OTP...');

    try {
      const payload = {
        email: document.getElementById('register-email').value.trim(),
        password: document.getElementById('register-password').value,
      };
      const data = await apiRequest('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) });
      pendingRegisterEmail = payload.email;
      registerOtpForm.classList.remove('hidden');
      setMessage(registerMessage, data.message);
    } catch (error) {
      setMessage(registerMessage, error.message, true);
    }
  });

  registerOtpForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    setMessage(registerMessage, 'Verifying registration OTP...');

    try {
      const payload = {
        email: pendingRegisterEmail || document.getElementById('register-email').value.trim(),
        otp: document.getElementById('register-otp').value.trim(),
      };
      const data = await apiRequest('/api/auth/register/verify-otp', { method: 'POST', body: JSON.stringify(payload) });
      setMessage(registerMessage, data.message);
      window.location.href = '/';
    } catch (error) {
      setMessage(registerMessage, error.message, true);
    }
  });
}

if (isDashboardPage) {
  const syncSession = async () => {
    const data = await apiRequest('/api/auth/status');
    if (!data.authenticated) {
      window.location.href = '/';
      return;
    }
    sessionInfo.textContent = `Signed in as ${data.email}`;
  };

  questionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    setMessage(formMessage, 'Saving question...');

    const payload = collectQuestionPayload();
    const questionId = questionIdInput.value;

    try {
      if (questionId) {
        const data = await apiRequest(`/api/questions/${questionId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        setMessage(formMessage, data.message);
      } else {
        const data = await apiRequest('/api/questions', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        setMessage(formMessage, data.message);
      }

      resetQuestionForm();
      await loadQuestions();
    } catch (error) {
      setMessage(formMessage, error.message, true);
    }
  });

  cancelEditBtn.addEventListener('click', () => {
    resetQuestionForm();
    setMessage(formMessage, 'Edit cancelled.');
  });

  logoutBtn.addEventListener('click', async () => {
    await apiRequest('/api/auth/logout', { method: 'POST' });
    window.location.href = '/';
  });

  refreshBtn.addEventListener('click', loadQuestions);

  syncSession().then(loadQuestions).catch((error) => {
    sessionInfo.textContent = error.message;
  });
}