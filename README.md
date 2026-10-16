# 🎤 Interview Prep

A voice-based AI mock interview application built with Streamlit. Upload your resume, provide a job description, and practise answering interview questions aloud. The application transcribes your answers, generates AI-powered feedback, assigns scores, and provides an overall interview report.

## ✨ Features

- **Resume Analysis:** Extracts your name and key highlights from a PDF resume.
- **Personalized Questions:** Generates interview questions based on your resume, job description, and previous answers.
- **Voice-Based Interviews:** Converts interview questions into speech using `edge-tts`.
- **Speech Recognition:** Transcribes spoken answers using Speechmatics.
- **AI-Powered Feedback:** Evaluates answers, provides feedback, and assigns scores from 0 to 10.
- **Interview Progress Tracking:** Tracks question numbers and interview state throughout the session.
- **Performance Summary:** Calculates the overall score and displays feedback for individual answers.
- **JSON Reports:** Saves interview results locally for later review.
- **Terminal Version:** Supports running mock interviews through `main.py`.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Streamlit | Web interface |
| Groq | LLM inference for interview analysis and question generation |
| LiteLLM | Unified interface for language models |
| Speechmatics | Speech-to-text transcription |
| edge-tts | Text-to-speech synthesis |
| pygame | Audio playback |
| asyncio | Asynchronous task coordination |
| pytest | Automated testing |

## 🧠 How It Works

The project does not train or fine-tune a machine learning model. It uses a hosted language model through Groq and LiteLLM, guided by prompts defined in `utils/prompts.py`.

The application uses three main prompts:

1. **Candidate Analysis:** Extracts the candidate's name and key resume highlights in JSON format.
2. **Question Generation:** Creates the next interview question using the job description, resume highlights, and previous question-and-answer pair.
3. **Feedback Generation:** Evaluates the candidate's answer and returns feedback with a score from 1 to 10.

### Interview Workflow

1. Upload a PDF resume and enter a job description.
2. Extract resume text and identify relevant candidate details.
3. Generate the opening interview question.
4. Convert the question into speech.
5. Record the candidate's spoken response.
6. Transcribe the response using Speechmatics.
7. Generate feedback and, when another question remains, generate the next question concurrently.
8. Repeat until the configured number of questions is completed.
9. Calculate the overall score and display the interview results.
10. Save the results as a JSON report in the `outputs/` directory.

## 📂 Project Structure

```text
interview-prep/
├── .streamlit/
├── audio/
├── inputs/
├── outputs/
├── tests/
├── utils/
│   ├── prompts.py
│   ├── interview_flow.py
│   ├── analyze_candidate.py
│   ├── llm_call.py
│   ├── transcript_audio.py
│   ├── text_to_speech.py
│   ├── record_utils.py
│   ├── load_content.py
│   └── evaluation.py
├── app.py
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── Dockerfile
└── Makefile
```

*The structure above highlights the main application files. Individual files and directories may vary with your local version.*

## ⚙️ Requirements

- Python 3.11 or 3.12
- Google Chrome
- A working microphone
- Speakers or headphones
- A Groq API key
- A Speechmatics API key

## 🚀 Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/interview-prep.git
cd interview-prep
```

Replace `YOUR-USERNAME` with your GitHub username and use your actual repository URL.

### 2. Create a virtual environment

**Windows:**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root by copying `.env.example`.

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Add your credentials to `.env`:

```dotenv
GROQ_API_KEY=your-groq-api-key
LLM_MODEL=groq/your-supported-model
SPEECHMATICS_API_KEY=your-speechmatics-api-key
```

Replace the placeholders with your actual credentials and a Groq model supported by LiteLLM. Check the [Groq documentation](https://console.groq.com/docs/models) for available models and the [LiteLLM documentation](https://docs.litellm.ai/docs/providers/groq) for provider configuration.

**Security:** Never commit `.env` or share your API keys. Keep `.env.example` free of real credentials.

### 5. Run the application

Start the Streamlit application:

```bash
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in Google Chrome and allow microphone access when prompted.

## 🎯 Using the Application

1. Upload your resume as a PDF.
2. Paste the job description for the role you are preparing for.
3. Select the number of interview questions and an interviewer voice.
4. Submit your details to prepare the interview.
5. Start the interview and listen to each question.
6. Record your answer using the browser's audio recorder.
7. Review your feedback, individual scores, and overall performance after completing the interview.
8. Start a new interview whenever you want to practise again.

## 💻 Terminal Version

The project also provides a terminal-based interview experience through `main.py`.

Place your resume at `inputs/resume.pdf` and the job description at `inputs/job_description.txt`, then run:

```bash
python main.py
```

To specify the number of questions:

```bash
python main.py --questions 3
```

The terminal version uses `sounddevice` for audio recording and may require PortAudio to be installed on your system.

## 🧪 Testing

Install development dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run the test suite:

```bash
python -m pytest
```

Run lint checks:

```bash
python -m ruff check .
```

The tests use mocks for external services and audio dependencies to test application logic without requiring live API calls or physical audio devices.

## ⚡ Implementation Highlights

- **Separation of concerns:** Interview logic is separated from the Streamlit interface, allowing core functionality to be tested independently.
- **Concurrent processing:** Answer evaluation and next-question generation run concurrently when another question remains.
- **Defensive JSON parsing:** Handles malformed model responses and attempts recovery from common formatting issues.
- **Score validation:** Converts model-generated scores into numeric values and restricts them to the valid scoring range.
- **Session state management:** Uses Streamlit session state to maintain interview progress across reruns.
- **Input validation:** Handles transcription failures, empty PDF text, and unsafe candidate names.
- **Configurable LLM provider:** Uses LiteLLM to simplify model configuration and provider changes.

## 🐳 Docker

The project includes a `Dockerfile` and `Makefile` for containerized execution.

Docker can run the application, but the current audio playback implementation uses `pygame` on the server machine. Therefore, the interviewer's voice may not be audible to a remote browser user in a containerized or hosted deployment.

For the complete voice experience, running locally is recommended.

Environment variables should be supplied at runtime rather than copied into the Docker image. Never bake API keys into the image or commit them to the repository.

## ⚠️ Limitations

- The application is primarily designed for local use.
- Server-side audio playback limits remote deployment.
- Speech recognition is configured for English.
- Scanned or image-only PDF resumes may not yield extractable text.
- AI-generated scores and feedback can vary and should be treated as practice guidance rather than definitive hiring assessments.
- External API access is required for LLM inference, transcription, and online text-to-speech.
- Interview data is stored locally as JSON; the application does not currently provide database-backed user accounts.
- Resume content and interview responses are sent to external providers for processing. Avoid uploading sensitive information unless you understand the providers' data policies.

## 🔮 Roadmap

- Stream synthesized audio directly to the browser.
- Introduce structured model outputs for more reliable response parsing.
- Use native asynchronous LLM calls where supported.
- Improve scoring consistency with criterion-based evaluation rubrics.
- Add persistent database storage and user authentication.
- Introduce structured logging, latency monitoring, and API cost tracking.
- Expand automated integration testing with real services in a controlled environment.

---

Built with Python, Streamlit, Groq, LiteLLM, and Speechmatics.
