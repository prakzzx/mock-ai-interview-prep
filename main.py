from dotenv import load_dotenv

# Load .env BEFORE importing utils (utils.llm_call reads LLM_MODEL at import time).
load_dotenv()

import argparse  # noqa: E402
import asyncio  # noqa: E402
import os  # noqa: E402

from utils import (  # noqa: E402
    InterviewFlow,
    TranscriptionError,
    build_interview_data,
    evaluate_answer,
    extract_resume_info_using_llm,
    get_ai_greeting_message,
    get_answer_audio_path,
    get_final_thanks_message,
    get_overall_evaluation_score,
    load_content,
    record_audio_with_interrupt,
    reduce_noise,
    save_interview_data,
    speak_text,
    transcribe_with_speechmatics,
    validate_audio_file,
)

# Keep in sync with APP_NAME in app.py
APP_NAME = "Interview Prep"
MAX_QUESTIONS = 5
MAX_RECORDING_ATTEMPTS = 3


def record_and_transcribe(candidate_name, question_answer_number):
    """Record one answer (Enter to stop), clean it up and transcribe it.

    Raises TranscriptionError if the audio is unusable or transcription fails.
    """
    filename = get_answer_audio_path(candidate_name, question_answer_number)

    # Create audio directory if it doesn't exist
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    audio_file, fs = record_audio_with_interrupt(filename=filename)

    if not validate_audio_file(audio_file):
        raise TranscriptionError("Audio file seems invalid or too quiet")

    audio_file = reduce_noise(audio_file, fs)

    if not validate_audio_file(audio_file):
        raise TranscriptionError("Audio file seems invalid after noise reduction")

    return transcribe_with_speechmatics(audio_file)


def get_candidate_answer(candidate_name, question_answer_number):
    """Record an answer, letting the candidate try again if it fails."""
    for attempt in range(1, MAX_RECORDING_ATTEMPTS + 1):
        print("Please answer the question...")
        try:
            return record_and_transcribe(candidate_name, question_answer_number)
        except TranscriptionError as error:
            print(f"Warning: {error}")
            if attempt == MAX_RECORDING_ATTEMPTS:
                raise
            print("Let's try that answer again.")


def speak_or_print(text):
    """Speak text; if audio playback is unavailable the text is already printed."""
    print(f"\nInterviewer: {text}\n")
    if not speak_text(text):
        print("(Audio playback is not available - please read the text above.)")


def start_interview_with_ai(
    name, resume_highlights, job_description, max_questions=MAX_QUESTIONS
):
    """Ask exactly `max_questions` questions; the last one gets feedback only."""
    print("Starting the mock interview...")

    # The greeting is question 1
    flow = InterviewFlow(
        max_questions=max_questions, current_question=get_ai_greeting_message(name)
    )

    while not flow.completed:
        print(flow.progress_text)

        # Ask the question and record + transcribe the answer
        speak_or_print(flow.current_question)
        candidate_response = get_candidate_answer(name, flow.current_index)

        # Feedback (+ next question unless this was the last one), run concurrently
        feedback, next_question = asyncio.run(
            evaluate_answer(
                flow.current_question,
                candidate_response,
                job_description,
                resume_highlights,
                flow.is_last_question,
            )
        )
        flow.record_answer(candidate_response, feedback, next_question)

    # Conclude interview
    speak_or_print(get_final_thanks_message(name))
    print("Interview completed!")

    return flow.conversations


def app(max_questions=MAX_QUESTIONS):
    print(f"=== {APP_NAME} ===")

    # Step 1: Load resume and job description
    print("Step 1: Loading resume and job description...")

    # Check if files exist
    resume_path = "inputs/resume.pdf"
    job_desc_path = "inputs/job_description.txt"

    if not os.path.exists(resume_path):
        print(f"Error: Resume file not found at {resume_path}")
        return 1

    if not os.path.exists(job_desc_path):
        print(f"Error: Job description file not found at {job_desc_path}")
        return 1

    try:
        resume_content = load_content(resume_path)
        job_description = load_content(job_desc_path)
    except Exception as error:
        print(f"Error: Could not load resume or job description: {error}")
        return 1

    if not resume_content or not job_description:
        print("Error: Could not load resume or job description content")
        return 1

    try:
        # Step 2: Extract candidate information using LLM
        print("Step 2: Extracting candidate information...")
        name, resume_highlights = extract_resume_info_using_llm(resume_content)

        # Step 3: Get confirmation to start interview
        print(f"Step 3: Ready to interview {name}")
        start_interview = (
            input("Do you want to start the interview? (y/n): ").lower().strip() == "y"
        )

        if not start_interview:
            print("Interview cancelled.")
            return 0

        # Step 4: Conduct the interview
        print("Step 4: Starting interview...")
        conversations = start_interview_with_ai(
            name, resume_highlights, job_description, max_questions=max_questions
        )

        # Step 5: Calculate overall score and prepare final data
        print("Step 5: Calculating final results...")
        final_evaluation_score = get_overall_evaluation_score(conversations)

        # Step 6: Prepare final interview data according to JSON schema
        interview_data = build_interview_data(
            name, job_description, resume_highlights, conversations
        )

        # Step 7: Save results
        print("Step 6: Saving results...")
        save_interview_data(interview_data, candidate_name=name)
    except Exception as error:
        print(f"\nError: {error}")
        return 1

    print("\n=== Interview Summary ===")
    print(f"Candidate: {name}")
    print(f"Total Questions: {len(conversations)}")
    print(f"Overall Score: {final_evaluation_score:.2f}/10")
    print("Interview data saved successfully!")
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - terminal version")
    parser.add_argument(
        "--questions",
        type=int,
        default=MAX_QUESTIONS,
        choices=range(1, 11),
        metavar="N",
        help="number of questions to ask, 1-10 (default: %(default)s)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(app(max_questions=parse_args().questions))
