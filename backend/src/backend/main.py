
from datetime import date
from backend.crew import ResearchCrew


def run():

    topic = input("Enter research topic: ").strip()

    if not topic:
        raise ValueError("Topic cannot be empty.")

    inputs = {
        "topic": topic,
        "current_date": date.today().isoformat()
    }

    result = ResearchCrew().crew().kickoff(
        inputs=inputs
    )

    print("\nResearch completed!")
    print(result)


if __name__ == "__main__":
    run()
