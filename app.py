from dotenv import load_dotenv

# Load .env BEFORE importing utils (utils.llm_call reads LLM_MODEL at import time).
load_dotenv()

import asyncio  # noqa: E402

import streamlit as st  # noqa: E402

# ---- Branding: change these two constants to rename the app --------------------
APP_NAME = "Interview Prep"
APP_EMOJI = "🎤"
# --------------------------------------------------------------------------------

from utils import (  # noqa: E402
    InterviewFlow,
    build_interview_data,
    evaluate_answer,
    extract_resume_info_using_llm,
    get_ai_greeting_message,
    get_answer_audio_path,
    get_final_thanks_message,
    get_overall_evaluation_score,
    load_content_streamlit,
    save_audio_file,
    save_interview_data,
    speak_text,
    transcribe_with_speechmatics,
)

MAX_QUESTIONS = 5

# Pale pink palette (the base colors are mirrored in .streamlit/config.toml)
PALETTE = {
    "background": "#FFF7FA",
    "surface": "#FFE6F0",
    "surface_deep": "#FFD3E5",
    "bubble_user": "#F9C0DA",
    "border": "#F5B5D0",
    "accent": "#EC80B3",
    "accent_dark": "#A93270",
    "button": "#FFD6E7",
    "button_hover": "#FFC2DC",
    "text": "#4A1530",
    "white": "#FFFFFF",
}

CUSTOM_CSS = """
<style>
/* ---------- Sidebar: pale pink gradient ---------- */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(180deg, {surface} 0%, {surface_deep} 100%);
}}
[data-testid="stSidebar"] {{
    border-right: 1px solid {border};
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p {{
    color: {text};
}}
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] input {{
    background-color: {white};
    color: {text};
}}
[data-testid="stSidebar"] [data-baseweb="textarea"],
[data-testid="stSidebar"] [data-baseweb="base-input"] {{
    background-color: {white};
    border-radius: 12px;
}}
[data-testid="stFileUploaderDropzone"] {{
    background-color: {background};
    border: 1px dashed {accent};
    border-radius: 14px;
    color: {text};
}}

/* ---------- Buttons: rounded, pale pink, with hover ---------- */
div.stButton > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {{
    background-color: {button};
    color: {text};
    border: 1px solid {border};
    border-radius: 999px;
    padding: 0.45rem 1.4rem;
    font-weight: 600;
    transition: background-color 0.15s ease, box-shadow 0.15s ease,
        transform 0.15s ease, border-color 0.15s ease;
}}
div.stButton > button p,
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-primary"] p {{
    color: {text};
}}
div.stButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-primary"]:hover {{
    background-color: {button_hover};
    border-color: {accent};
    color: {text};
    box-shadow: 0 4px 12px rgba(236, 128, 179, 0.35);
    transform: translateY(-1px);
}}
div.stButton > button:active,
[data-testid="stBaseButton-secondary"]:active,
[data-testid="stBaseButton-primary"]:active {{
    background-color: {surface_deep};
    transform: translateY(0);
}}
div.stButton > button:focus-visible,
[data-testid="stBaseButton-secondary"]:focus-visible {{
    outline: 2px solid {accent_dark};
    outline-offset: 2px;
}}

/* ---------- Chat bubbles ---------- */
[data-testid="stChatMessage"] {{
    border-radius: 18px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    color: {text};
    border: 1px solid {border};
    background-color: {surface};
}}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li {{
    color: {text};
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
    background-color: {bubble_user};
    border-color: {accent};
}}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {{
    background-color: {white};
    color: {accent_dark};
    border: 1px solid {border};
}}

/* ---------- Progress banner ---------- */
.interview-progress {{
    background-color: {surface_deep};
    color: {text};
    border: 1px solid {border};
    border-left: 6px solid {accent};
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 20px;
    text-align: center;
}}

/* ---------- Audio recorder card ---------- */
[data-testid="stAudioInput"] {{
    background-color: {surface};
    color: {text};
    border: 2px solid {border};
    border-radius: 16px;
    padding: 14px;
    margin-top: 12px;
}}

/* ---------- Misc ---------- */
[data-testid="stExpander"] details {{
    background-color: {white};
    border: 1px solid {border};
    border-radius: 14px;
}}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] p {{
    color: {text};
}}
[data-testid="stHeader"] {{
    background: transparent;
}}
h1, h2, h3, h4 {{
    color: {text};
}}
a {{
    color: {accent_dark};
}}
</style>
"""


# Configuration and Styling
def build_custom_css():
    """Return the custom CSS (a <style> block) with the palette filled in."""
    return CUSTOM_CSS.format(**PALETTE)


def inject_custom_css():
    """Inject all custom CSS for the pink theme (the only place CSS is injected)."""
    st.markdown(build_custom_css(), unsafe_allow_html=True)


def setup_page_config():
    """Setup page configuration and custom CSS"""
    st.set_page_config(page_title=APP_NAME, page_icon=APP_EMOJI, layout="wide")
    inject_custom_css()


def initialize_session_state():
    """Initialize all session state variables"""
    defaults = {
        "interview_started": False,
        "name": "",
        "resume_highlights": "",
        "job_description": "",
        "flow": None,
        "question_spoken": False,
        "awaiting_response": False,
        "processing_audio": False,
        "audio_attempt": 0,
        "answer_error": "",
        "speech_warning": "",
        "messages": [],
        "max_questions": MAX_QUESTIONS,
        "ai_voice": "Alex (Male)",
        "thanks_message_prepared": False,
        "thanks_message_spoken": False,
        "show_final_results": False,
        "interview_result": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_ai_voice_details():
    """Get AI voice configuration"""
    return {
        "Alex (Male)": {"name": "Alex", "code": "en-US-GuyNeural"},
        "Aria (Female)": {"name": "Aria", "code": "en-US-AriaNeural"},
        "Natasha (Female)": {"name": "Natasha", "code": "en-AU-NatashaNeural"},
        "Sonia (Female)": {"name": "Sonia", "code": "en-GB-SoniaNeural"},
    }


def get_instructions():
    """Get instructions for the user"""
    content = f"""
    #### Please follow these steps to use {APP_NAME}:
    1. **Upload Resume**: Upload your resume in PDF format.
    2. **Job Description**: Paste the job description.
    3. **Submit**: Click "Submit" so your resume can be analyzed, then click the "Start Interview" button to begin your mock interview.
    4. **Maximum Questions**: You can set the maximum number of questions for the interview. (default: 5)
    5. **Voice Selection**: Choose the interviewer voice for the interview. (default: Alex (Male))
    6. **Answer Questions**: Listen to each question, then record your spoken answer.
    7. **Review Results**: After the interview, review your score and the feedback for every answer.

    **Note**: The interviewer asks questions based on your resume and the job description.
    Use Chrome and allow microphone access when the browser asks.

    Good luck with your preparation!
    """
    return st.markdown(content)


def render_sidebar():
    """Render sidebar with candidate information and settings"""
    st.sidebar.title("Candidate Information")

    # File upload
    uploaded_resume = st.sidebar.file_uploader("Upload your Resume (PDF)", type=["pdf"])

    # Job description
    job_description = st.sidebar.text_area("Paste the Job Description")

    # Settings
    max_questions = st.sidebar.number_input(
        "Maximum number of questions",
        min_value=1,
        max_value=10,
        value=MAX_QUESTIONS,
    )
    st.session_state["max_questions"] = int(max_questions)

    ai_voice = st.sidebar.radio(
        "Select AI Interviewer Voice",
        ["Alex (Male)", "Aria (Female)", "Natasha (Female)", "Sonia (Female)"],
    )
    st.session_state["ai_voice"] = ai_voice

    submit = st.sidebar.button("Submit")

    return uploaded_resume, job_description, submit


def process_resume_submission(uploaded_resume, job_description):
    """Process resume and job description submission. Returns True on success."""
    try:
        with st.spinner("Processing resume..."):
            resume_content = load_content_streamlit(uploaded_resume)
            name, resume_highlights = extract_resume_info_using_llm(resume_content)
    except Exception as error:  # show any failure instead of crashing the page
        st.error(f"Could not process the resume: {error}")
        return False

    # Store in session state
    st.session_state["name"] = name
    st.session_state["resume_highlights"] = resume_highlights
    st.session_state["job_description"] = job_description

    # Reset interview state
    reset_interview_state()
    return True


def reset_interview_state():
    """Reset interview-related session state"""
    st.session_state["interview_started"] = False
    st.session_state["flow"] = None
    st.session_state["question_spoken"] = False
    st.session_state["awaiting_response"] = False
    st.session_state["processing_audio"] = False
    st.session_state["audio_attempt"] = 0
    st.session_state["answer_error"] = ""
    st.session_state["speech_warning"] = ""
    st.session_state["messages"] = []
    st.session_state["thanks_message_prepared"] = False
    st.session_state["thanks_message_spoken"] = False
    st.session_state["show_final_results"] = False
    st.session_state["interview_result"] = None


def start_interview():
    """Initialize and start the interview"""
    reset_interview_state()
    st.session_state["interview_started"] = True

    # Get greeting message (it is question 1)
    ai_voice_details = get_ai_voice_details()
    interviewer_name = ai_voice_details[st.session_state["ai_voice"]]["name"]
    greeting_message = get_ai_greeting_message(
        st.session_state["name"], interviewer_name=interviewer_name
    )

    st.session_state["flow"] = InterviewFlow(
        max_questions=int(st.session_state["max_questions"]),
        current_question=greeting_message,
    )
    st.session_state["messages"].append(
        {"role": "assistant", "content": greeting_message}
    )


def display_chat_messages():
    """Display all chat messages from history"""
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])



def speak_message(text):
    """Generate audio for browser playback using the selected voice."""
    ai_voice_details = get_ai_voice_details()

    try:
        audio_bytes = speak_text(
            text,
            voice=ai_voice_details[
                st.session_state["ai_voice"]
            ]["code"],
        )

        if not audio_bytes:
            raise RuntimeError("No audio was generated.")

        st.session_state["speech_warning"] = ""
        st.audio(audio_bytes, format="audio/mp3")

    except Exception as error:
        print(f"Speech generation error: {error}")
        st.session_state["speech_warning"] = (
            f"Audio generation failed. Please read: {text}"
        )



def render_speech_warning():
    """Show the saved playback warning (with the message text), if any."""
    if st.session_state["speech_warning"]:
        st.warning(st.session_state["speech_warning"])



def speak_current_question():
    """Generate and display audio for the current question."""
    flow = st.session_state["flow"]

    if flow.current_question and not st.session_state["question_spoken"]:
        with st.spinner("Generating interviewer audio..."):
            speak_message(flow.current_question)

        st.session_state["question_spoken"] = True
        st.session_state["awaiting_response"] = True



def process_candidate_response(transcript):
    """
    Analyze the candidate's answer and move the flow forward.

    Raises on any LLM failure or timeout; nothing is stored in that case, so the
    candidate can simply record the answer again.
    """
    flow = st.session_state["flow"]

    feedback, next_question = asyncio.run(
        evaluate_answer(
            flow.current_question,
            transcript,
            st.session_state["job_description"],
            st.session_state["resume_highlights"],
            flow.is_last_question,
        )
    )

    flow.record_answer(transcript, feedback, next_question)

    # Add the candidate's answer (and the next question) to the chat
    st.session_state["messages"].append({"role": "user", "content": transcript})
    st.session_state["processing_audio"] = False
    st.session_state["awaiting_response"] = False
    st.session_state["answer_error"] = ""

    if not flow.completed:
        st.session_state["messages"].append(
            {"role": "assistant", "content": flow.current_question}
        )
        st.session_state["question_spoken"] = False


def prepare_thanks_message():
    """Prepare and display thanks message"""
    if not st.session_state["thanks_message_prepared"]:
        final_note = get_final_thanks_message(st.session_state["name"])
        st.session_state["messages"].append(
            {"role": "assistant", "content": final_note}
        )
        st.session_state["thanks_message_prepared"] = True
        st.rerun()



def speak_thanks_message():
    """Generate and display audio for the final thank-you message."""
    if (
        st.session_state["thanks_message_prepared"]
        and not st.session_state["thanks_message_spoken"]
    ):
        thanks_message = st.session_state["messages"][-1]["content"]

        with st.spinner("Generating final interviewer audio..."):
            speak_message(thanks_message)

        st.session_state["thanks_message_spoken"] = True
        st.session_state["show_final_results"] = True


def handle_audio_recording():
    """Handle audio recording and processing"""
    if not (
        st.session_state["awaiting_response"]
        and not st.session_state["processing_audio"]
    ):
        return

    flow = st.session_state["flow"]

    if st.session_state["answer_error"]:
        st.error(st.session_state["answer_error"])

    st.write("**🎙️ Please record your answer to the question above**")

    # A new key after every failed attempt gives a fresh recorder (no stale audio)
    audio_key = f"audio_input_{flow.current_index}_{st.session_state['audio_attempt']}"
    audio_data = st.audio_input("Record your answer", key=audio_key)

    if audio_data is None:
        return

    st.session_state["processing_audio"] = True
    error_message = ""

    try:
        with st.spinner("Processing your answer..."):
            # Save audio file: audio/<name>/<name>_<n>.wav
            filename = get_answer_audio_path(
                st.session_state["name"], flow.current_index
            )
            save_audio_file(audio_data.getvalue(), filename)

            # Transcribe audio (raises TranscriptionError on any problem)
            transcript = transcribe_with_speechmatics(filename)

            process_candidate_response(transcript)
    except Exception as error:  # never leave the page stuck in "processing"
        error_message = (
            f"Could not process your answer: {error} Please record it again."
        )

    if error_message:
        st.session_state["processing_audio"] = False
        st.session_state["audio_attempt"] += 1
        st.session_state["answer_error"] = error_message

    st.rerun()


def finalize_results():
    """Compute the score and save the JSON once; keep the result in session state."""
    if st.session_state["interview_result"] is not None:
        return st.session_state["interview_result"]

    flow = st.session_state["flow"]
    interview_data = build_interview_data(
        name=st.session_state["name"],
        job_description=st.session_state["job_description"],
        resume_highlights=st.session_state["resume_highlights"],
        conversations=flow.conversations,
    )

    save_error = ""
    try:
        save_interview_data(interview_data, candidate_name=st.session_state["name"])
    except OSError as error:
        save_error = f"Results could not be saved to the outputs folder: {error}"

    result = {"data": interview_data, "save_error": save_error}
    st.session_state["interview_result"] = result
    return result


def display_final_results():
    """Display final interview results"""
    flow = st.session_state["flow"]
    if not st.session_state["show_final_results"] or not flow or not flow.conversations:
        return

    with st.spinner("Calculating final score..."):
        result = finalize_results()

    final_score = get_overall_evaluation_score(flow.conversations)

    st.success("🎉 Interview completed! Thank you for your time.")
    if result["save_error"]:
        st.warning(result["save_error"])

    # Display results
    st.subheader("🎉 Interview Results")
    st.markdown(f"**Candidate:** {st.session_state['name']}")
    st.markdown(f"**Overall Score:** {final_score:.2f}/10")

    # Show detailed summary
    st.subheader("Detailed Interview Summary")
    for i, conv in enumerate(flow.conversations, 1):
        with st.expander(f"Question {i} (Score: {conv['Evaluation']:g}/10)"):
            st.write(f"**Q:** {conv['Question']}")
            st.write(f"**A:** {conv['Candidate Answer']}")
            st.write(f"**Feedback:** {conv['Feedback']}")

    # New interview option
    if st.button("Start New Interview"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def render_interview_progress():
    """Render interview progress indicator"""
    flow = st.session_state.get("flow")
    if st.session_state.get("interview_started", False) and flow is not None:
        st.markdown(
            f'<div class="interview-progress"><strong>{flow.progress_text}</strong></div>',
            unsafe_allow_html=True,
        )


def main():
    """Main application function"""
    # Setup
    setup_page_config()
    initialize_session_state()

    # Header
    st.title(f"{APP_EMOJI} {APP_NAME}")
    instructions = st.empty()
    if not st.session_state["interview_started"]:
        instructions = get_instructions()

    # Sidebar
    uploaded_resume, job_description, submit = render_sidebar()

    # Process submission
    if submit:
        if uploaded_resume and job_description.strip():
            instructions.empty()
            process_resume_submission(uploaded_resume, job_description)
        else:
            st.warning("Please upload your resume (PDF) and paste the job description.")

    # Candidate name (shown after a successful submission)
    if st.session_state["name"] and not st.session_state["interview_started"]:
        st.success(f"Candidate Name: {st.session_state['name']}")

    # Start interview button
    if st.session_state["name"] and not st.session_state["interview_started"]:
        if st.button("Start Interview"):
            start_interview()
            st.rerun()

    # Interview section
    if st.session_state.get("interview_started", False):
        flow = st.session_state["flow"]
        render_interview_progress()

        # Show chat history
        st.subheader("Interview Chat")
        display_chat_messages()
        render_speech_warning()

        # Handle different interview states
        if not flow.completed:
            # Active interview
            speak_current_question()
            handle_audio_recording()
        elif not st.session_state["thanks_message_prepared"]:
            # Interview just completed - prepare thanks
            prepare_thanks_message()
        elif not st.session_state["thanks_message_spoken"]:
            # Thanks message prepared but not spoken
            speak_thanks_message()
        else:
            # Everything done - show results
            display_final_results()


if __name__ == "__main__":
    main()
